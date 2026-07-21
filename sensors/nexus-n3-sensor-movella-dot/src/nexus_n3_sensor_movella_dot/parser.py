"""Packet parsing helpers for the Movella DOT sensor plugin."""

from __future__ import annotations

import struct
from typing import Optional

from nexus_n3_plugin_sdk.samples import IMUSample


class MovellaDotParser:
    """Parse raw Movella DOT BLE packets into `IMUSample` objects."""

    _SAMPLE_PREFIX = struct.Struct("<I10f")

    @staticmethod
    def parse_packet(packet: bytes) -> IMUSample:
        if len(packet) < MovellaDotParser._SAMPLE_PREFIX.size:
            raise ValueError(
                f"packet too short: expected at least {MovellaDotParser._SAMPLE_PREFIX.size} bytes, "
                f"got {len(packet)}"
            )

        (
            timestamp,
            q_w,
            q_x,
            q_y,
            q_z,
            acc_x,
            acc_y,
            acc_z,
            gyr_x,
            gyr_y,
            gyr_z,
        ) = MovellaDotParser._SAMPLE_PREFIX.unpack_from(packet)

        return IMUSample(
            timestamp=int(timestamp),
            quat=(
                float(q_w),
                float(q_x),
                float(q_y),
                float(q_z),
            ),
            accel=(
                float(acc_x),
                float(acc_y),
                float(acc_z),
            ),
            gyro=(
                float(gyr_x),
                float(gyr_y),
                float(gyr_z),
            ),
            sensor_type=None,
            address=None,
            location=None,
            sampling_rate=None,
        )
