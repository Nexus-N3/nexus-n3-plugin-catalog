"""CORE 2 sensor implementation."""

from __future__ import annotations

import logging
import time
import asyncio
import math
import threading

from nexus_n3_plugin_sdk import BatteryStatus, SensorBase, SensorType

from .parser import (
    CONTROL_POINT_EXTERNAL_HR_OPCODE,
    CONTROL_POINT_RESULT_SUCCESS,
    parse_control_point_response,
    parse_core_temperature_packet,
)
from .samples import Core2Sample


class Core2Sensor(SensorBase):
    """CORE 2 BLE sensor implementation."""

    sensor_type = SensorType("Core 2", 9000)
    SAMPLE_CLASS = Core2Sample
    SPEC_PATH = "Core2Spec.yaml"

    def __init__(self, sensor=None):
        self.logger = logging.getLogger(self.sensor_type.local_name)

        spec = self.load_raw_spec()
        self._data_stream_specs = spec.get("data_streams", {})
        super().__init__(self.sensor_type, spec)

        self.transport_spec = spec["transport"][self.adapter]

        self._measurement_notify_enabled = False

        self._adapter = None

        self._control_point_notify_enabled = False
        self._control_point_lock = asyncio.Lock()
        self._control_point_response_event = threading.Event()
        self._control_point_response = None

        self._external_hr_active = False
        self._pending_heart_rate = None

    def _declared_timestamp_source(self, stream: str) -> str | None:
        return (
            self._data_stream_specs
            .get(stream.lower(), {})
            .get("timestamp_source")
        ) 

    async def consume_input(self, source_plugin_id: str, payload) -> bool:
        """Consume a routed heart-rate sample and forward it to CORE."""

        schema = str(getattr(payload, "schema", "") or "").lower()
        output_name = str(getattr(payload, "output_name", "") or "").lower()

        if schema != "hr" and output_name != "hr":
            return False

        sample = getattr(payload, "payload", None)
        if sample is None:
            return False

        heart_rate = getattr(sample, "heart_rate", None)

        if heart_rate is None:
            bpm = None
        else:
            try:
                value = float(heart_rate)
            except (TypeError, ValueError):
                return False

            if not math.isfinite(value):
                return False

            bpm = int(round(value))

            if bpm < 1 or bpm > 255:
                return False

        # A source can begin streaming before CORE depending on start order.
        # Preserve the latest value and apply it once CORE is ready.
        if not self._measurement_notify_enabled:
            self._pending_heart_rate = bpm
            return True

        try:
            return await self._set_external_heart_rate(bpm)
        except Exception:
            self.logger.exception(
                "Failed to forward external HR to CORE 2 at %s",
                self.address,
            )
            return False

    async def setup(
        self,
        adapter,
        enable_battery: bool = False,
        enable_button: bool = False,
    ):
        """Configure CORE 2 after connection."""

        self._adapter = adapter

        if enable_battery and self.has_capability("notify_battery"):
            battery_uuid = (
                self.transport_spec["services"]["battery"]
                ["characteristics"]["battery_level"]["uuid"]
            )

            # CORE battery state is read once during setup. Keeping battery
            # read-only ensures the measurement characteristic owns the
            # gateway's binary notification stream.
            try:
                batt = await adapter.read(
                    self.transport_client,
                    battery_uuid,
                )
                self.on_battery("", batt)
            except Exception:
                self.logger.exception(
                    "Failed to read battery level for %s",
                    self.address,
                )

    async def start_stream(self, adapter):
        """Start CORE 2 live measurement notifications."""

        self._adapter = adapter

        if self._measurement_notify_enabled:
            return

        measurement_uuid = (
            self.transport_spec["services"]["core_temperature"]
            ["characteristics"]["measurement"]["uuid"]
        )

        await adapter.set_notify_callback(
            self.transport_client,
            measurement_uuid,
            self.on_data_packet,
        )

        self._measurement_notify_enabled = True

        if self._pending_heart_rate is not None:
            pending = self._pending_heart_rate
            self._pending_heart_rate = None

            try:
                await self._set_external_heart_rate(pending)
            except Exception:
                self.logger.exception(
                    "Failed to apply pending external HR to CORE 2 at %s",
                    self.address,
                )

    async def _ensure_control_point_subscription(self):
        """Enable CORE Control Point procedure-complete indications."""

        if self._control_point_notify_enabled:
            return

        if self._adapter is None:
            raise RuntimeError("CORE 2 adapter is not available")

        control_point_uuid = (
            self.transport_spec["services"]["core_temperature"]
            ["characteristics"]["control_point"]["uuid"]
        )

        await self._adapter.set_notify_callback(
            self.transport_client,
            control_point_uuid,
            self.on_control_point_packet,
            indicate=True,
        )

        self._control_point_notify_enabled = True

    async def _set_external_heart_rate(
        self,
        bpm: int | None,
    ) -> bool:
        """Set or disable CORE external heart-rate input."""

        if self._adapter is None:
            return False

        await self._ensure_control_point_subscription()

        control_point_uuid = (
            self.transport_spec["services"]["core_temperature"]
            ["characteristics"]["control_point"]["uuid"]
        )

        if bpm is None:
            command = bytes([
                CONTROL_POINT_EXTERNAL_HR_OPCODE
            ])
        else:
            command = bytes([
                CONTROL_POINT_EXTERNAL_HR_OPCODE,
                bpm,
            ])

        # CORE Control Point procedures must not overlap.
        async with self._control_point_lock:
            self._control_point_response = None
            self._control_point_response_event.clear()

            await self._adapter.write(
                self.transport_client,
                control_point_uuid,
                command,
            )

            completed = await asyncio.to_thread(
                self._control_point_response_event.wait,
                5.0,
            )

            if not completed:
                self.logger.error(
                    "Timed out waiting for CORE Control Point response"
                )
                return False

            response = self._control_point_response

            if response is None:
                return False

            if (
                response["request_opcode"]
                != CONTROL_POINT_EXTERNAL_HR_OPCODE
            ):
                self.logger.error(
                    "Unexpected CORE Control Point response opcode: %s",
                    response["request_opcode"],
                )
                return False

            if (
                response["result_code"]
                != CONTROL_POINT_RESULT_SUCCESS
            ):
                self.logger.error(
                    "CORE external HR request failed: result_code=%s",
                    response["result_code"],
                )
                return False

            self._external_hr_active = bpm is not None

            return True

    def on_control_point_packet(
        self,
        sender,
        packet: bytes,
    ):
        """Handle CORE Control Point procedure-complete indications."""

        response = parse_control_point_response(packet)

        if response is None:
            return

        self._control_point_response = response
        self._control_point_response_event.set()

    async def stop_stream(self, adapter):
        """Stop CORE 2 live measurement notifications."""

        if not self._measurement_notify_enabled:
            return

        # If N3 supplied external HR during this session, tell CORE to
        # stop using it before the connection/measurement stream ends.
        if self._external_hr_active:
            try:
                await self._set_external_heart_rate(None)
            except Exception:
                self.logger.exception(
                    "Failed to disable external HR for %s",
                    self.address,
                )

        measurement_uuid = (
            self.transport_spec["services"]["core_temperature"]
            ["characteristics"]["measurement"]["uuid"]
        )

        unset_notify = getattr(
            adapter,
            "unset_notify_callback",
            None,
        )

        if callable(unset_notify):
            await unset_notify(
                self.transport_client,
                measurement_uuid,
            )
        elif (
            hasattr(adapter, "execute")
            and hasattr(
                self.transport_client,
                "stop_notify",
            )
        ):
            await adapter.execute(
                self.transport_client.stop_notify,
                measurement_uuid,
            )

        self._measurement_notify_enabled = False


    def battery_status(self, batt_bytes: bytes) -> BatteryStatus:
        """Convert raw BLE Battery Level bytes into a battery status model."""

        if len(batt_bytes) < 1:
            raise ValueError(
                "battery payload too short: "
                f"expected at least 1 byte, got {len(batt_bytes)}"
            )

        level = int.from_bytes(
            batt_bytes[0:1],
            byteorder="little",
            signed=False,
        )

        if level > 100:
            raise ValueError(f"battery level out of range: {level}")

        return BatteryStatus(level, False)

    def on_battery(self, sender, batt_bytes: bytes):
        """Emit `on_battery` events when battery data arrives."""

        if not batt_bytes:
            self.logger.warning(
                "Battery read returned empty bytes for %s",
                self.address,
            )
            return

        try:
            battery = self.battery_status(batt_bytes)
        except Exception:
            self.logger.exception(
                "Failed to parse battery payload for %s",
                self.address,
            )
            return

        self._emit(
            "on_battery",
            {
                "address": self.address,
                "battery": battery,
            },
        )

    def on_data_packet(self, sender, packet: bytes):
        """Parse and emit CORE 2 measurement samples."""

        # The CORE Body Temperature characteristic does not provide a
        # device timestamp. Populate the sample timestamp from host wall
        # clock as a best-effort metric timestamp.

        timestamp = int(time.time() * 1000)

        try:
            values = parse_core_temperature_packet(packet)
        except Exception:
            self.logger.exception(
                "Failed to parse CORE 2 packet for %s",
                self.address,
            )
            return

        if values is None:
            return

        sample = Core2Sample(
            timestamp=timestamp,
            sensor_type=self.name,
            address=self.address,
            location=self.location,
            sampling_rate=self.attributes.get("SAMPLING_RATE"),
            declared_timestamp_source=self._declared_timestamp_source(
                "temperature" 
            ),
            **values,
        )

        self._emit("on_data", sample)
