"""Conversion helpers for vendor X-IMU3 message objects."""

from __future__ import annotations

# The ximu3 API reports calibrated acceleration in g.  This fixed unit
# conversion is independent of the environmental gravity supplied to an
# algorithm (for example Earth, Moon, or zero-g).
METRES_PER_SECOND_SQUARED_PER_G = 9.80665


def parse_inertial_message(message) -> tuple[int, tuple[float, ...], tuple[float, ...]]:
    """Convert an installed ``ximu3.InertialMessage`` to canonical Nexus units."""

    return (
        int(message.timestamp),
        (
            float(message.accelerometer_x) * METRES_PER_SECOND_SQUARED_PER_G,
            float(message.accelerometer_y) * METRES_PER_SECOND_SQUARED_PER_G,
            float(message.accelerometer_z) * METRES_PER_SECOND_SQUARED_PER_G,
        ),
        (
            float(message.gyroscope_x),
            float(message.gyroscope_y),
            float(message.gyroscope_z),
        ),
    )


def parse_quaternion_message(message) -> tuple[int, tuple[float, ...]]:
    """Convert an installed ``ximu3.QuaternionMessage`` to Nexus values."""

    return (
        int(message.timestamp),
        (float(message.w), float(message.x), float(message.y), float(message.z)),
    )
