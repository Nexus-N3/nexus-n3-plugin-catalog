"""CORE 2 sensor implementation."""

from __future__ import annotations

import logging
import time

from nexus_n3_plugin_sdk import BatteryStatus, SensorBase, SensorType

from .parser import parse_core_temperature_packet
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

    def _declared_timestamp_source(self, stream: str) -> str | None:
        return (
            self._data_stream_specs
            .get(stream.lower(), {})
            .get("timestamp_source")
        ) 

    def consume_input(self, source_plugin_id: str, payload) -> bool:
        """External input is not implemented yet."""
        return False

    async def setup(
        self,
        adapter,
        enable_battery: bool = False,
        enable_button: bool = False,
    ):
        """Configure CORE 2 after connection."""

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

    async def stop_stream(self, adapter):
        """Stop CORE 2 live measurement notifications."""

        if not self._measurement_notify_enabled:
            return

        measurement_uuid = (
            self.transport_spec["services"]["core_temperature"]
            ["characteristics"]["measurement"]["uuid"]
        )

        unset_notify = getattr(adapter, "unset_notify_callback", None)
        if callable(unset_notify):
            await unset_notify(
                self.transport_client,
                measurement_uuid,
            )
        elif (
            hasattr(adapter, "execute")
            and hasattr(self.transport_client, "stop_notify")
        ):
            await adapter.execute(self.transport_client.stop_notify, measurement_uuid)

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
