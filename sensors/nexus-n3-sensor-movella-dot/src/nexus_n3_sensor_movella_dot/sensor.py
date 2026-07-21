"""Movella DOT sensor plugin implementation."""

from __future__ import annotations

import logging

from nexus_n3_plugin_sdk import BatteryStatus, SensorBase, SensorType
from nexus_n3_plugin_sdk.samples import IMUSample

from .parser import MovellaDotParser


class MovellaDotSensor(SensorBase):
    """BLE Movella DOT sensor implementation."""

    sensor_type = SensorType("Movella DOT", 2182)
    SAMPLE_CLASS = IMUSample
    SPEC_PATH = "MovellaDotSpec.yaml"

    def __init__(self, sensor=None):
        self.logger = logging.getLogger(self.sensor_type.local_name)
        spec = self._load_decoded_spec()
        super().__init__(self.sensor_type, spec)
        self.transport_spec = spec["transport"][self.adapter]

    def _load_decoded_spec(self) -> dict:
        """Load and decode the YAML specification for Movella DOT BLE commands."""
        spec = self.load_raw_spec()
        if spec["sensor"]["adapter"] == "BLE":
            transport_spec = spec["transport"]["BLE"]
            for service_name, service in transport_spec["services"].items():
                commands = service.get("commands")
                if not commands:
                    continue
                decoded_commands = {}
                for cmd_name, cmd_value in commands.items():
                    if isinstance(cmd_value, dict):
                        decoded = {}
                        expected_len = None
                        for rate, hex_str in cmd_value.items():
                            if not isinstance(hex_str, str):
                                raise TypeError(
                                    f"{service_name}.{cmd_name}[{rate}] must be hex string"
                                )
                            if len(hex_str) % 2 != 0:
                                raise ValueError(
                                    f"{service_name}.{cmd_name}[{rate}] hex string has odd length"
                                )
                            payload = bytes.fromhex(hex_str)
                            if expected_len is None:
                                expected_len = len(payload)
                            elif len(payload) != expected_len:
                                raise ValueError(
                                    f"{service_name}.{cmd_name}[{rate}] "
                                    f"length {len(payload)} != expected {expected_len}"
                                )
                            decoded[int(rate)] = payload
                        decoded_commands[cmd_name] = decoded
                    elif isinstance(cmd_value, str):
                        if len(cmd_value) % 2 != 0:
                            raise ValueError(f"{service_name}.{cmd_name} hex string has odd length")
                        decoded_commands[cmd_name] = bytes.fromhex(cmd_value)
                    else:
                        raise TypeError(
                            f"{service_name}.{cmd_name} must be hex string or rate map"
                        )
                service["commands"] = decoded_commands
        return spec

    def consume_input(self, source_plugin_id: str, payload) -> bool:
        """Movella DOT does not consume forwarded plugin input."""
        return False

    async def setup(self, adapter, enable_battery: bool = False, enable_button: bool = False):
        """Configure BLE notifications and sensor settings after connect."""
        if self.has_capability("set_payload"):
            await adapter.set_notify_callback(
                self.transport_client,
                self.transport_spec["payload_size"]["long"],
                self.on_data_packet,
            )

        if self.has_capability("set_data_rate"):
            rate = self.attributes.get("SAMPLING_RATE", 60)
            rate_cmds = self.transport_spec["services"]["device_control"]["commands"]["set_data_rate"]
            if rate not in rate_cmds:
                rate = 60 if 60 in rate_cmds else next(iter(rate_cmds))
            await adapter.write(
                self.transport_client,
                self.transport_spec["services"]["device_control"]["uuid"],
                rate_cmds[rate],
            )

        if enable_battery and self.has_capability("notify_battery"):
            await adapter.set_notify_callback(
                self.transport_client,
                self.transport_spec["services"]["battery"]["uuid"],
                self.on_battery,
            )
            batt = await adapter.read(
                self.transport_client,
                self.transport_spec["services"]["battery"]["uuid"],
            )
            self.on_battery("", batt)

        if enable_button and self.has_capability("button"):
            await adapter.set_notify_callback(
                self.transport_client,
                self.transport_spec["services"]["device_report"]["uuid"],
                self.on_button,
            )

    async def start_stream(self, adapter):
        """Start streaming measurements."""
        await adapter.write(
            self.transport_client,
            self.transport_spec["services"]["measurement"]["uuid"],
            self.transport_spec["services"]["measurement"]["commands"]["start"],
        )

    async def stop_stream(self, adapter):
        """Stop streaming measurements."""
        await adapter.write(
            self.transport_client,
            self.transport_spec["services"]["measurement"]["uuid"],
            self.transport_spec["services"]["measurement"]["commands"]["stop"],
        )

    async def identify(self, adapter):
        """Send identify command if the sensor supports it."""
        if not self.has_capability("identify"):
            return
        char = await adapter.read(
            self.transport_client,
            self.transport_spec["services"]["device_control"]["uuid"],
        )
        identify_char = (
            self.transport_spec["services"]["device_control"]["commands"]["identify"] + char[3:]
        )
        await adapter.write(
            self.transport_client,
            self.transport_spec["services"]["device_control"]["uuid"],
            identify_char,
        )

    def battery_status(self, batt_bytes: bytes) -> BatteryStatus:
        """Convert raw battery bytes into a battery status model."""
        if len(batt_bytes) < 2:
            raise ValueError(f"battery payload too short: expected 2 bytes, got {len(batt_bytes)}")
        level = int.from_bytes(batt_bytes[0:1], byteorder="little", signed=True)
        charging = int.from_bytes(batt_bytes[1:2], byteorder="little", signed=True)
        return BatteryStatus(level, bool(charging))

    def on_battery(self, sender, batt_bytes: bytes):
        """Emit `on_battery` events when battery data arrives."""
        if not batt_bytes:
            self.logger.warning("Battery read returned empty bytes for %s", self.address)
            return
        self._emit(
            "on_battery",
            {
                "address": self.address,
                "battery": self.battery_status(batt_bytes),
            },
        )

    def on_button(self, sender, event: bytes):
        """Emit `on_button` events on single press."""
        press_type = event[0]
        if press_type == 5:
            self._emit(
                "on_button",
                {
                    "address": self.address,
                    "location": self.location,
                    "button_press": press_type,
                },
            )

    def on_connection_status_changed(self):
        """Placeholder for connection status hooks."""
        return

    def on_data_packet(self, sender, packet: bytes):
        """Parse and emit IMU samples from raw BLE packets."""
        self._process_packet(packet)

    def _process_packet(self, packet: bytes):
        """Decode a raw Movella packet and emit an enriched IMU sample."""
        try:
            sample = MovellaDotParser.parse_packet(packet)
        except Exception:
            self.logger.exception("Failed to parse packet for %s", self.address)
            return

        enriched = IMUSample(
            timestamp=sample.timestamp,
            quat=sample.quat,
            accel=sample.accel,
            gyro=sample.gyro,
            sensor_type=self.name,
            address=self.address,
            location=self.location,
            sampling_rate=self.attributes.get("SAMPLING_RATE"),
        )
        self._emit("on_data", enriched)
