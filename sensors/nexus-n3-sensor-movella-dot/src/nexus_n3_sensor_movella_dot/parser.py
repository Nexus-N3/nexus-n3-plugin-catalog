"""Packet parsing helpers for the Movella DOT sensor plugin."""

from __future__ import annotations

from typing import Optional

import numpy as np

from nexus_n3_plugin_sdk.samples import IMUSample


class MovellaDotParser:
    """Parse raw Movella DOT BLE packets into `IMUSample` objects."""

    @staticmethod
    def parse_packet(packet: bytes) -> IMUSample:
        dtype = np.dtype(
            [
                ("timestamp", np.uint32),
                ("q_w", np.float32),
                ("q_x", np.float32),
                ("q_y", np.float32),
                ("q_z", np.float32),
                ("acc_x", np.float32),
                ("acc_y", np.float32),
                ("acc_z", np.float32),
                ("gyr_x", np.float32),
                ("gyr_y", np.float32),
                ("gyr_z", np.float32),
                ("_pad0", np.int64),
                ("_pad1", np.int64),
                ("_pad2", np.int16),
                ("_pad3", np.int8),
            ]
        )

        row = np.frombuffer(packet, dtype=dtype)[0]

        return IMUSample(
            timestamp=int(row["timestamp"]),
            quat=(
                float(row["q_w"]),
                float(row["q_x"]),
                float(row["q_y"]),
                float(row["q_z"]),
            ),
            accel=(
                float(row["acc_x"]),
                float(row["acc_y"]),
                float(row["acc_z"]),
            ),
            gyro=(
                float(row["gyr_x"]),
                float(row["gyr_y"]),
                float(row["gyr_z"]),
            ),
            sensor_type=None,
            address=None,
            location=None,
            sampling_rate=None,
        )
