"""Movesense ECG sensor implementation."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from rs_nexus_plugin_sdk import SensorBase, SensorType
from rs_nexus_plugin_sdk.samples.hr import HRSample

from .samples import ECGSample, TempSample

from .parser import (
    parse_ecg_packet,
    parse_hr_packet,
    parse_hr_measurement,
    parse_temp_packet,
    ECG_SAMPLE_RATE_HZ,
)


class MovesenseSensor(SensorBase):
    """Movesense ECG sensor class (adapter: BLE)."""

    sensor_type = SensorType("Movesense", 9002)
    SPEC_PATH = "MovesenseSpec.yaml"
    SAMPLE_CLASS = ECGSample

    def __init__(self, sensor=None):
        self.logger = logging.getLogger(self.sensor_type.local_name)
        spec = self.load_raw_spec()
        super().__init__(self.sensor_type, spec)
        self.transport_spec = spec["transport"][self.adapter]
        self._subscriptions = {}
        self._ecg_rate = ECG_SAMPLE_RATE_HZ
        self._hr_standard = bool(self.transport_spec.get("standard_hr"))
        self._hr_enabled = False
        self._gsp_notify_enabled = False
        self._debug_packet_seen = False
        self._pending_gsp_info = {}
        self._next_gsp_ref = 200

    def _get_streams(self) -> list[str]:
        streams = self.attributes.get("STREAMS") or ["ECG", "HR"]
        normalized = []
        for stream in streams:
            value = str(stream).upper()
            if value in ("ECG", "HR", "TEMP"):
                normalized.append(value)
        if os.getenv("NEXUS_STREAM_DEBUG", "0") in ("1", "true", "TRUE"):
            print(f"[STREAM_DEBUG] Movesense streams={normalized}")
        return normalized

    async def _ensure_services(self, adapter):
        """Refresh GATT services to ensure characteristic UUIDs are available."""
        services = getattr(self.transport_client, "services", None)
        if services is None:
            get_services = getattr(self.transport_client, "get_services", None)
            if callable(get_services) and hasattr(adapter, "execute"):
                await adapter.execute(get_services)

    async def _send_gsp_get(self, adapter, path: str, ref: int | None = None):
        """Send a GSP GET command and track the response."""
        if ref is None:
            ref = self._next_gsp_ref
            self._next_gsp_ref = min(254, self._next_gsp_ref + 1)
        payload = bytes([4, ref]) + path.encode("utf-8")
        print(f"Movesense GET payload: {payload}")
        self._pending_gsp_info[ref] = path
        write_uuid = self.transport_spec["services"]["write"]["uuid"]
        await adapter.write(self.transport_client, write_uuid, payload)

    async def setup(self, adapter, enable_battery: bool = False, enable_button: bool = False):
        """Configure BLE notifications for ECG data."""
        await self._ensure_services(adapter)
        streams = self._get_streams()
        if "ECG" in streams or (not self._hr_standard and "HR" in streams):
            notify_uuid = self.transport_spec["services"]["notify"]["uuid"]
            await adapter.set_notify_callback(
                self.transport_client,
                notify_uuid,
                self.on_data_packet,
            )
            self._gsp_notify_enabled = True
        if self._hr_standard and "HR" in streams:
            hr_uuid = self.transport_spec["services"]["heart_rate"]["uuid"]
            await adapter.set_notify_callback(
                self.transport_client,
                hr_uuid,
                self.on_hr_packet,
            )
            self._hr_enabled = True

    async def start_stream(self, adapter):
        """Start selected Movesense streams."""
        await self._ensure_services(adapter)
        write_uuid = self.transport_spec["services"]["write"]["uuid"]
        self._subscriptions = {}

        streams = self._get_streams()
        if not streams:
            return
        if os.getenv("NEXUS_STREAM_DEBUG", "0") in ("1", "true", "TRUE"):
            print(f"[STREAM_DEBUG] Starting streams={streams}")

        stream_ids = self.transport_spec["services"]["write"].get("stream_ids", {})
        next_id = 1
        for stream in streams:
            if stream == "ECG":
                rate = self.attributes.get("SAMPLING_RATE") or ECG_SAMPLE_RATE_HZ
                self._ecg_rate = int(rate)
                suffix = self.attributes.get("ECG_PATH_SUFFIX", "mv")
                if suffix:
                    path = f"/Meas/ECG/{self._ecg_rate}/{suffix}"
                else:
                    path = f"/Meas/ECG/{self._ecg_rate}"
                sub_id = int(stream_ids.get("ecg", next_id))
            elif stream == "HR":
                if self._hr_standard:
                    continue
                await self._send_gsp_get(adapter, "/Meas/HR/Info")
                path = "/Meas/HR"
                sub_id = int(stream_ids.get("hr", next_id))
            elif stream == "TEMP":
                await self._send_gsp_get(adapter, "/Meas/Temp/Info")
                path = "/Meas/Temp"
                sub_id = int(stream_ids.get("temp", next_id))
            else:
                continue

            payload = bytes([1, sub_id]) + path.encode("utf-8")
            print(f"Movesense subscribe payload: {payload}")
            await adapter.write(self.transport_client, write_uuid, payload)
            self._subscriptions[sub_id] = stream
            next_id = max(next_id, sub_id + 1)

    async def stop_stream(self, adapter):
        """Stop selected Movesense streams."""
        await self._ensure_services(adapter)
        write_uuid = self.transport_spec["services"]["write"]["uuid"]
        for sub_id in list(self._subscriptions.keys()):
            await adapter.write(self.transport_client, write_uuid, bytes([2, sub_id]))
        self._subscriptions = {}

        if self._gsp_notify_enabled:
            notify_uuid = self.transport_spec["services"]["notify"]["uuid"]
            if hasattr(adapter, "execute") and hasattr(self.transport_client, "stop_notify"):
                await adapter.execute(self.transport_client.stop_notify, notify_uuid)
            self._gsp_notify_enabled = False
        if self._hr_enabled:
            hr_uuid = self.transport_spec["services"]["heart_rate"]["uuid"]
            if hasattr(adapter, "execute") and hasattr(self.transport_client, "stop_notify"):
                await adapter.execute(self.transport_client.stop_notify, hr_uuid)
            self._hr_enabled = False

    def on_data_packet(self, sender, packet: bytes):
        """Parse ECG packets and emit ECGSample entries."""
        debug = os.getenv("NEXUS_ECG_DEBUG", "0") in ("1", "true", "TRUE")
        hr_debug = os.getenv("NEXUS_HR_DEBUG", "0") in ("1", "true", "TRUE")
        if not packet or len(packet) < 2:
            return

        if not self._debug_packet_seen:
            print(f"Movesense notify header: type={packet[0]} ref={packet[1]} len={len(packet)}")
            self._debug_packet_seen = True

        if packet[0] == 1 and len(packet) >= 4:
            ref = packet[1]
            if ref in self._pending_gsp_info:
                status = int.from_bytes(packet[2:4], byteorder="little")
                data = packet[4:]
                path = self._pending_gsp_info.pop(ref)
                print(f"Movesense GET response for {path}: status={status} data_len={len(data)}")
                if data:
                    print(f"Movesense GET raw data: {data.hex()}")
            else:
                status = int.from_bytes(packet[2:4], byteorder="little")
                print(f"Movesense GSP response: ref={ref} status={status} len={len(packet)}")
            return

        sub_id = packet[1]
        stream = self._subscriptions.get(sub_id)
        if not stream:
            return

        if stream == "ECG":
            try:
                samples = parse_ecg_packet(packet)
            except Exception as exc:
                self._emit("on_error", {"address": self.address, "error": str(exc)})
                return

            if not samples:
                print(f"Movesense ECG packet ignored: type={packet[0]} ref={packet[1]} len={len(packet)}")
                return
            if debug:
                first_ts = samples[0][0]
                last_ts = samples[-1][0]
                print(
                    f"[ECG_DEBUG] ECG packet samples={len(samples)} "
                    f"ts_span_ms={last_ts - first_ts} "
                    f"first_ts={first_ts} last_ts={last_ts}"
                )

            for timestamp, voltage in samples:
                sample = ECGSample(
                    timestamp=timestamp,
                    sensor_type=self.name,
                    address=self.address,
                    location=self.location,
                    sampling_rate=self._ecg_rate,
                    voltage=voltage,
                )
                self._emit("on_data", sample)
        elif stream == "HR":
            if hr_debug:
                count = getattr(self, "_hr_packet_count", 0) + 1
                self._hr_packet_count = count
                if count == 1 or count % 10 == 0:
                    print(f"[HR_DEBUG] HR packets={count} last_len={len(packet)}")
            try:
                hr_value = parse_hr_packet(packet)
            except Exception as exc:
                self._emit("on_error", {"address": self.address, "error": str(exc)})
                return
            if hr_value is None:
                return

            sample = HRSample(
                timestamp=int(time.time() * 1000),
                sensor_type=self.name,
                address=self.address,
                location=self.location,
                sampling_rate=None,
                heart_rate=hr_value,
            )
            self._emit("on_data", sample)
        elif stream == "TEMP":
            try:
                print(f"Movesense TEMP packet raw: {packet.hex()}")
                temp_value = parse_temp_packet(packet)
            except Exception as exc:
                self._emit("on_error", {"address": self.address, "error": str(exc)})
                return
            if temp_value is None:
                return
            sample = TempSample(
                timestamp=int(time.time() * 1000),
                sensor_type=self.name,
                address=self.address,
                location=self.location,
                sampling_rate=None,
                temperature_c=temp_value,
            )
            self._emit("on_data", sample)

    def on_hr_packet(self, sender, packet: bytes):
        """Parse standard HR measurement packets."""
        hr_value = parse_hr_measurement(packet)
        if hr_value is None:
            return
        sample = HRSample(
            timestamp=int(time.time() * 1000),
            sensor_type=self.name,
            address=self.address,
            location=self.location,
            sampling_rate=None,
            heart_rate=float(hr_value),
        )
        self._emit("on_data", sample)
