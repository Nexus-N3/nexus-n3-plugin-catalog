"""Simulated CORE 2 BLE notification stream."""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable

from nexus_n3_sensor_core_2.sensor import Core2Sensor


CORE_NOTIFICATION_RATE_HZ = 1.0


def build_core2_packet(
    *,
    core_temperature: float,
    skin_temperature: float,
    core_reserved: int = 0,
    data_quality: int = 3,
    heart_rate_state: int = 2,
    heart_rate: int = 120,
    heat_strain_index: float = 3.0,
) -> bytes:
    """Build a valid CORE Body Temperature BLE notification."""

    # All optional fields present, temperatures in Celsius.
    flags = 0x37

    core_raw = round(core_temperature * 100)
    skin_raw = round(skin_temperature * 100)
    hsi_raw = round(heat_strain_index * 10)

    quality_state = (
        (data_quality & 0x07)
        | ((heart_rate_state & 0x03) << 4)
    )

    return struct.pack(
        "<BhhhBBB",
        flags,
        core_raw,
        skin_raw,
        core_reserved,
        quality_state,
        heart_rate,
        hsi_raw,
    )


async def simulate_core2_stream(
    callback: Callable,
    *,
    duration_seconds: int = 10,
) -> None:
    """Emit simulated CORE 2 BLE notifications at 1 Hz."""

    interval = 1.0 / CORE_NOTIFICATION_RATE_HZ

    core_temperature = 37.20
    skin_temperature = 34.10

    for packet_number in range(duration_seconds):

        # Simulate skin temperature changing every two seconds.
        if packet_number > 0 and packet_number % 2 == 0:
            skin_temperature += 0.01

        # Core temperature deliberately remains unchanged during this
        # short simulation. BLE notifications still arrive at 1 Hz.

        packet = build_core2_packet(
            core_temperature=core_temperature,
            skin_temperature=skin_temperature,
            core_reserved=0,
            data_quality=3,
            heart_rate_state=2,
            heart_rate=120,
            heat_strain_index=3.2,
        )

        print(
            f"[SIM] packet={packet_number} "
            f"raw={packet.hex()} "
            f"core={core_temperature:.2f} "
            f"skin={skin_temperature:.2f}"
        )

        callback(None, packet)

        await asyncio.sleep(interval)


def _capture_emit(event_name, payload) -> None:
    """Print events emitted by the simulated sensor."""

    print(f"[EMIT] {event_name}: {payload}")


async def main() -> None:
    """Run the CORE 2 simulator directly."""

    sensor = Core2Sensor()

    # Supply the metadata normally populated by Nexus/Core.
    sensor.address = "CORE2-SIM"
    sensor.location = "CHEST"

    # Replace the normal Nexus event emitter so we can see what the
    # sensor implementation produces.
    sensor._emit = _capture_emit

    print("Starting CORE 2 simulator...")
    print(f"Notification rate: {CORE_NOTIFICATION_RATE_HZ} Hz")
    print()

    await simulate_core2_stream(
        sensor.on_data_packet,
        duration_seconds=10,
    )

    print()
    print("CORE 2 simulation complete.")


if __name__ == "__main__":
    asyncio.run(main())