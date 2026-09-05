"""X-IMU3 Wi-Fi sensor implementation."""

from __future__ import annotations

import ipaddress
import json
import logging
import threading
from collections import Counter

from nexus_n3_plugin_sdk import SensorBase, SensorType
import ximu3

from .parser import parse_inertial_message, parse_quaternion_message
from .samples import IMUSample


# X-IMU3 inertial and AHRS data are generated at 400 Hz.  The values below
# are the divisors published by the vendor's DeviceSettings definition.
MESSAGE_RATE_DIVISORS = {
    1: 400,
    2: 200,
    4: 100,
    5: 80,
    8: 50,
    10: 40,
    16: 25,
    20: 20,
    25: 16,
    40: 10,
    50: 8,
    80: 5,
    100: 4,
    200: 2,
    400: 1,
}
MAX_PENDING_MESSAGES = 256


class XImu3Sensor(SensorBase):
    """X-IMU3 sensor using the vendor UDP connection API."""

    sensor_type = SensorType("X-IMU3", 9000)
    SAMPLE_CLASS = IMUSample
    SPEC_PATH = "XImu3Spec.yaml"

    def __init__(self, sensor=None):
        self.logger = logging.getLogger(self.sensor_type.local_name)
        spec = self.load_raw_spec()
        super().__init__(self.sensor_type, spec)
        self.transport_spec = spec.get("transport", {}).get(self.adapter, {})
        self._connection = None
        self._connection_configs: dict[str, object] = {}
        self._identified_candidate: dict | None = None
        self._identified_candidate_network: str | None = None
        self._callback_ids: list[int] = []
        self._sample_lock = threading.Lock()
        self._diagnostics_lock = threading.Lock()
        self._pending_inertial: dict[int, tuple[tuple[float, ...], tuple[float, ...]]] = {}
        self._pending_quaternion: dict[int, tuple[float, ...]] = {}
        self._streaming = False
        self._diagnostic_counts: Counter[str] = Counter()
        self._first_sample_timestamp_us: int | None = None
        self._last_sample_timestamp_us: int | None = None
        self._configured_sampling_rate_hz: int | None = None

    def get_wifi_driver(self):
        """Expose this plugin as a driver for direct core development runs."""

        return self

    async def discover_connected(self, network) -> list[dict]:
        """Return announced X-IMU3 devices on the Nexus sensor subnet."""

        # The vendor binding owns native resources with thread affinity.  The
        # isolated plugin host already keeps this work outside the core loop.
        return self._discover_connected_sync(network)

    def _discover_connected_sync(self, network) -> list[dict]:
        """Discover and cache vendor UDP configurations on one subnet."""
        self._increment_diagnostic("discovery_attempts")
        expected_network = ipaddress.ip_interface(network.cidr).network
        devices = []
        configs: dict[str, object] = {}

        announcements = ximu3.NetworkAnnouncement().get_messages_after_short_delay()
        self._increment_diagnostic("announcements_seen", len(announcements))
        for announcement in announcements:
            if not str(announcement.device_name).casefold().startswith("x-imu3"):
                continue
            try:
                address = ipaddress.ip_address(str(announcement.ip_address))
            except ValueError:
                continue
            if address not in expected_network:
                continue

            serial_number = str(announcement.serial_number).strip()
            if not serial_number:
                continue
            configs[serial_number] = announcement.to_udp_connection_config()
            self._increment_diagnostic("announcements_accepted")
            devices.append(
                {
                    "address": serial_number,
                    "endpoint": str(address),
                    "metadata": {
                        "device_name": str(announcement.device_name),
                        "serial_number": serial_number,
                        "ip_address": str(address),
                        "tcp_port": int(announcement.tcp_port),
                        "udp_send_port": int(announcement.udp_send),
                        "udp_receive_port": int(announcement.udp_receive),
                        "rssi": int(announcement.rssi),
                        "battery": int(announcement.battery),
                    },
                }
            )

        self._connection_configs = configs
        return devices

    async def classify_access_points(self, access_points) -> list[dict]:
        """Claim open X-IMU3 provisioning access points."""

        candidates = []
        for access_point in access_points:
            if not str(access_point.ssid).casefold().startswith("x-imu3"):
                continue
            if bool(getattr(access_point, "secured", False)):
                continue
            candidates.append(
                {
                    "access_point": {
                        "id": str(access_point.id),
                        "ssid": str(access_point.ssid),
                        "bssid": str(access_point.bssid),
                        "strength": int(access_point.strength),
                        "frequency_mhz": int(access_point.frequency_mhz),
                        "secured": False,
                    },
                    "confidence": 100,
                    "metadata": {"vendor": "xio-technologies"},
                }
            )
        return candidates

    async def provision(self, network, target, controls) -> dict:
        """Configure an AP-mode X-IMU3 to join the Nexus sensor network."""

        device = self._identified_candidate
        identified_network = self._identified_candidate_network
        self._identified_candidate = None
        self._identified_candidate_network = None
        if device is None or identified_network != str(network.cidr):
            raise RuntimeError(
                "The X-IMU3 provisioning candidate must be identified on the "
                "current network before provisioning"
            )
        serial_number = device["address"]
        config = self._connection_configs.get(serial_number)
        if config is None:
            raise RuntimeError(
                f"No UDP configuration is cached for X-IMU3 {serial_number!r}"
            )
        password = target.credentials.password
        if not password:
            raise RuntimeError("The Nexus sensor AP password is not configured")
        if target.channel is None:
            raise RuntimeError("The Nexus sensor AP channel is not configured")

        connection = ximu3.Connection(config).open()
        try:
            response = connection.ping()
            if not response or str(response.serial_number) != serial_number:
                raise RuntimeError("X-IMU3 did not answer before provisioning")

            commands = [
                json.dumps({"wi_fi_client_ssid": target.ssid}, separators=(",", ":")),
                json.dumps({"wi_fi_client_key": password}, separators=(",", ":")),
                json.dumps({"wi_fi_client_channel": int(target.channel)}, separators=(",", ":")),
                json.dumps({"wi_fi_client_dhcp_enabled": True}, separators=(",", ":")),
                json.dumps({"wireless_mode": 1}, separators=(",", ":")),
                '{"save":null}',
            ]
            responses = connection.send_commands(commands)
            self._require_command_success(responses, "configure Wi-Fi client")
            try:
                apply_response = connection.send_command('{"apply":null}')
            except Exception:
                # Applying client mode normally removes the sensor AP before
                # the command response completes.
                pass
            else:
                if apply_response is not None and getattr(apply_response, "error", None):
                    raise RuntimeError(
                        f"X-IMU3 apply failed: {apply_response.error}"
                    )
            disappeared = getattr(controls, "remote_access_point_disappeared", None)
            if callable(disappeared):
                disappeared()
            return device
        finally:
            connection.close()

    async def identify_candidate(self, network) -> dict:
        """Identify the AP-mode sensor before changing its configuration."""

        self._identified_candidate = None
        self._identified_candidate_network = None
        devices = self._discover_connected_sync(network)
        if len(devices) != 1:
            raise RuntimeError(
                f"Expected one X-IMU3 on the provisioning network, found {len(devices)}"
            )
        self._identified_candidate = devices[0]
        self._identified_candidate_network = str(network.cidr)
        return self._identified_candidate

    @staticmethod
    def _require_command_success(responses, operation: str) -> None:
        """Raise when any vendor command response reports a failure."""
        if responses is None:
            raise RuntimeError(f"X-IMU3 returned no responses while trying to {operation}")
        for response in responses:
            if response is None:
                raise RuntimeError(f"X-IMU3 returned an empty response while trying to {operation}")
            error = getattr(response, "error", None)
            if error:
                raise RuntimeError(f"X-IMU3 failed to {operation}: {error}")

    async def connect_sensor(self, sensor_or_device, device=None, adapter=None) -> bool:
        """Open and verify the UDP connection for a discovered sensor."""

        _ = adapter
        target_device = device if device is not None else sensor_or_device
        return self._connect_sensor_sync(target_device)

    def _connect_sensor_sync(self, device) -> bool:
        """Open and ping the cached vendor UDP configuration."""
        self._increment_diagnostic("connect_attempts")
        serial_number = str(device.address)
        config = self._connection_configs.get(serial_number)
        if config is None:
            raise RuntimeError(f"X-IMU3 {serial_number!r} is no longer announcing")

        self._disconnect_sensor_sync()
        connection = ximu3.Connection(config).open()
        try:
            response = connection.ping()
            if not response or str(response.serial_number) != serial_number:
                raise RuntimeError(f"X-IMU3 {serial_number!r} did not answer UDP ping")
        except Exception:
            self._increment_diagnostic("connect_errors")
            connection.close()
            raise

        self._connection = connection
        self._increment_diagnostic("connect_successes")
        return True

    async def disconnect_sensor(self, sensor=None) -> bool:
        """Close the active vendor connection without changing host Wi-Fi."""

        _ = sensor
        return self._disconnect_sensor_sync()

    def _disconnect_sensor_sync(self) -> bool:
        """Remove callbacks and close the active vendor connection."""
        if self._connection is None:
            return True
        self._streaming = False
        self._clear_pending_samples()
        self._remove_stream_callbacks()
        try:
            self._connection.close()
        finally:
            self._connection = None
        self._increment_diagnostic("disconnects")
        return True

    def consume_input(self, source_plugin_id: str, payload) -> bool:
        """Accept forwarded input from another plugin when this plugin needs it."""
        return False

    async def setup(self, adapter, enable_battery: bool = False, enable_button: bool = False):
        """Configure matched inertial/quaternion UDP messages after connect."""

        _ = adapter, enable_battery, enable_button
        connection = self._require_connection()
        sampling_rate = int(self.attributes.get("SAMPLING_RATE") or 50)
        try:
            divisor = MESSAGE_RATE_DIVISORS[sampling_rate]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported X-IMU3 sampling rate {sampling_rate}; "
                f"expected one of {sorted(MESSAGE_RATE_DIVISORS)}"
            ) from exc
        self._configured_sampling_rate_hz = sampling_rate

        commands = [
            '{"ahrs_message_type":0}',
            json.dumps(
                {"inertial_message_rate_divisor": divisor}, separators=(",", ":")
            ),
            json.dumps(
                {"ahrs_message_rate_divisor": divisor}, separators=(",", ":")
            ),
        ]
        self._require_command_success(
            connection.send_commands(commands), "configure data messages"
        )
        self._register_stream_callbacks()

    async def identify(self, adapter):
        """Strobe the device LED using the vendor command API."""

        if self._connection is None:
            raise RuntimeError("X-IMU3 is not connected")
        response = self._connection.send_command('{"strobe":null}')
        self._emit("on_identify", {"address": self.address})
        return response

    async def start_stream(self, adapter):
        """Enable X-IMU3 UDP data messages."""

        _ = adapter
        if self._streaming:
            return
        connection = self._require_connection()
        self._register_stream_callbacks()
        self._clear_pending_samples()
        self._streaming = True
        self._increment_diagnostic("stream_starts")
        try:
            response = connection.send_command('{"udp_data_messages_enabled":true}')
            self._require_command_success([response], "enable UDP data messages")
        except Exception:
            self._streaming = False
            self._increment_diagnostic("stream_start_errors")
            raise

    async def stop_stream(self, adapter):
        """Disable X-IMU3 UDP data messages without persisting the setting."""

        _ = adapter
        if not self._streaming:
            return
        self._streaming = False
        self._increment_diagnostic("stream_stops")
        self._clear_pending_samples()
        connection = self._require_connection()
        response = connection.send_command('{"udp_data_messages_enabled":false}')
        self._require_command_success([response], "disable UDP data messages")

    def _require_connection(self):
        """Return the active vendor connection or reject the operation."""
        if self._connection is None:
            raise RuntimeError("X-IMU3 is not connected")
        return self._connection

    def _register_stream_callbacks(self) -> None:
        """Register inertial and quaternion callbacks exactly once."""
        if self._callback_ids:
            return
        connection = self._require_connection()
        callback_ids = []
        try:
            callback_ids.append(
                int(connection.add_inertial_callback(self._on_inertial_message))
            )
            callback_ids.append(
                int(connection.add_quaternion_callback(self._on_quaternion_message))
            )
        except Exception:
            for callback_id in callback_ids:
                connection.remove_callback(callback_id)
            raise
        self._callback_ids = callback_ids

    def _remove_stream_callbacks(self) -> None:
        """Best-effort remove all callbacks from the vendor connection."""
        connection = self._connection
        callback_ids, self._callback_ids = self._callback_ids, []
        if connection is None:
            return
        for callback_id in callback_ids:
            try:
                connection.remove_callback(callback_id)
            except Exception:
                self.logger.exception(
                    "Failed to remove X-IMU3 callback %s", callback_id
                )

    def _on_inertial_message(self, message) -> None:
        """Parse and join one vendor inertial callback message."""
        self._increment_diagnostic("inertial_messages")
        try:
            timestamp, accel, gyro = parse_inertial_message(message)
            self._join_sample(timestamp, accel=accel, gyro=gyro)
        except Exception:
            self._increment_diagnostic("inertial_callback_errors")
            self.logger.exception("Failed to process an X-IMU3 inertial message")

    def _on_quaternion_message(self, message) -> None:
        """Parse and join one vendor quaternion callback message."""
        self._increment_diagnostic("quaternion_messages")
        try:
            timestamp, quat = parse_quaternion_message(message)
            self._join_sample(timestamp, quat=quat)
        except Exception:
            self._increment_diagnostic("quaternion_callback_errors")
            self.logger.exception("Failed to process an X-IMU3 quaternion message")

    def _join_sample(self, timestamp: int, *, accel=None, gyro=None, quat=None) -> None:
        """Join inertial and quaternion halves by device timestamp."""
        sample = None
        with self._sample_lock:
            if not self._streaming:
                return
            if quat is not None:
                inertial = self._pending_inertial.pop(timestamp, None)
                if inertial is None:
                    self._pending_quaternion[timestamp] = quat
                else:
                    sample = self._make_sample(timestamp, quat, *inertial)
            else:
                quaternion = self._pending_quaternion.pop(timestamp, None)
                if quaternion is None:
                    self._pending_inertial[timestamp] = (accel, gyro)
                else:
                    sample = self._make_sample(timestamp, quaternion, accel, gyro)
            inertial_evictions = self._trim_pending(self._pending_inertial)
            quaternion_evictions = self._trim_pending(self._pending_quaternion)
        if inertial_evictions:
            self._increment_diagnostic(
                "pending_inertial_evictions", inertial_evictions
            )
        if quaternion_evictions:
            self._increment_diagnostic(
                "pending_quaternion_evictions", quaternion_evictions
            )
        if sample is not None:
            self._record_complete_sample(timestamp)
            self._emit("on_data", sample)

    def _make_sample(self, timestamp, quat, accel, gyro) -> IMUSample:
        """Construct a canonical SDK IMU sample from paired values."""
        return IMUSample(
            timestamp=timestamp,
            sensor_type=self.name,
            address=self.address,
            location=self.location,
            sampling_rate=int(self.attributes.get("SAMPLING_RATE") or 50),
            quat=quat,
            accel=accel,
            gyro=gyro,
        )

    @staticmethod
    def _trim_pending(messages: dict) -> int:
        """Bound an unmatched-message map and return its eviction count."""
        evictions = 0
        while len(messages) > MAX_PENDING_MESSAGES:
            messages.pop(next(iter(messages)))
            evictions += 1
        return evictions

    def _clear_pending_samples(self) -> None:
        """Clear unmatched halves and account for discarded messages."""
        with self._sample_lock:
            inertial_count = len(self._pending_inertial)
            quaternion_count = len(self._pending_quaternion)
            self._pending_inertial.clear()
            self._pending_quaternion.clear()
        self._increment_diagnostic("pending_inertial_cleared", inertial_count)
        self._increment_diagnostic("pending_quaternion_cleared", quaternion_count)

    def reset_session_diagnostics(self) -> None:
        """Reset counters without changing connection or stream state."""

        with self._diagnostics_lock:
            self._diagnostic_counts.clear()
            self._first_sample_timestamp_us = None
            self._last_sample_timestamp_us = None

    def get_diagnostics_snapshot(self) -> dict:
        """Return connection, message pairing, and stream-rate diagnostics."""

        with self._diagnostics_lock:
            counts = dict(self._diagnostic_counts)
            first_timestamp = self._first_sample_timestamp_us
            last_timestamp = self._last_sample_timestamp_us
        with self._sample_lock:
            pending_inertial = len(self._pending_inertial)
            pending_quaternion = len(self._pending_quaternion)

        complete_samples = counts.get("complete_samples", 0)
        observed_rate = None
        if (
            complete_samples > 1
            and first_timestamp is not None
            and last_timestamp is not None
            and last_timestamp > first_timestamp
        ):
            observed_rate = round(
                (complete_samples - 1) * 1_000_000
                / (last_timestamp - first_timestamp),
                3,
            )
        return {
            "transport": "ximu3_udp",
            "address": self.address,
            "connected": self._connection is not None,
            "streaming": self._streaming,
            "configured_sampling_rate_hz": self._configured_sampling_rate_hz,
            "observed_sampling_rate_hz": observed_rate,
            "first_sample_timestamp_us": first_timestamp,
            "last_sample_timestamp_us": last_timestamp,
            "pending_inertial_messages": pending_inertial,
            "pending_quaternion_messages": pending_quaternion,
            "counters": counts,
        }

    def _increment_diagnostic(self, name: str, amount: int = 1) -> None:
        """Increment one thread-safe plugin diagnostic counter."""
        if not amount:
            return
        with self._diagnostics_lock:
            self._diagnostic_counts[name] += amount

    def _record_complete_sample(self, timestamp: int) -> None:
        """Record sample cadence and infer missing or reordered timestamps."""
        with self._diagnostics_lock:
            previous = self._last_sample_timestamp_us
            self._diagnostic_counts["complete_samples"] += 1
            if self._first_sample_timestamp_us is None:
                self._first_sample_timestamp_us = timestamp
            if previous is not None:
                delta = timestamp - previous
                if delta <= 0:
                    self._diagnostic_counts["out_of_order_samples"] += 1
                elif self._configured_sampling_rate_hz:
                    expected = 1_000_000 / self._configured_sampling_rate_hz
                    if delta > expected * 1.5:
                        missing = max(round(delta / expected) - 1, 1)
                        self._diagnostic_counts["timestamp_gap_events"] += 1
                        self._diagnostic_counts["estimated_missing_samples"] += missing
            self._last_sample_timestamp_us = timestamp
