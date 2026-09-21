"""CORE 2 BLE packet parser."""

from __future__ import annotations

import struct


FLAG_SKIN_TEMPERATURE = 0x01
FLAG_CORE_RESERVED = 0x02
FLAG_QUALITY_STATE = 0x04
FLAG_TEMPERATURE_FAHRENHEIT = 0x08
FLAG_HEART_RATE = 0x10
FLAG_HEAT_STRAIN_INDEX = 0x20

RFU_MASK = 0xC0

TEMPERATURE_UNAVAILABLE = 0x7FFF
HEAT_STRAIN_INDEX_UNAVAILABLE = 0xFF

CONTROL_POINT_RESPONSE_OPCODE = 0x80
CONTROL_POINT_EXTERNAL_HR_OPCODE = 0x13

CONTROL_POINT_RESULT_SUCCESS = 0x01
CONTROL_POINT_RESULT_OPCODE_NOT_SUPPORTED = 0x02
CONTROL_POINT_RESULT_INVALID_PARAMETER = 0x03
CONTROL_POINT_RESULT_OPERATION_FAILED = 0x04


class DataView:
    """Tiny helper for little-endian binary parsing."""

    def __init__(self, data: bytes):
        self.data = data

    def _slice(self, start: int, count: int) -> bytes:
        return self.data[start:start + count]

    def get_uint_8(self, start: int) -> int:
        return int.from_bytes(
            self._slice(start, 1),
            byteorder="little",
            signed=False,
        )

    def get_int_16(self, start: int) -> int:
        return struct.unpack("<h", self._slice(start, 2))[0]


def parse_control_point_response(packet: bytes) -> dict[str, int | bytes] | None:
    """Parse a CORE Control Point procedure-complete indication."""

    if not packet or len(packet) < 3:
        return None

    if packet[0] != CONTROL_POINT_RESPONSE_OPCODE:
        return None

    return {
        "request_opcode": packet[1],
        "result_code": packet[2],
        "response_parameter": packet[3:],
    }

def parse_core_temperature_packet(
    packet: bytes,
) -> dict[str, float | int | None] | None:
    """Parse a CORE Body Temperature characteristic notification."""

    if not packet or len(packet) < 3:
        return None

    view = DataView(packet)

    flags = view.get_uint_8(0)

    # Bits 6-7 are reserved in the current specification.
    if flags & RFU_MASK:
        return None

    offset = 1
    temperature_is_fahrenheit = bool(
        flags & FLAG_TEMPERATURE_FAHRENHEIT
    )

    # Core temperature is mandatory.
    if offset + 2 > len(packet):
        return None

    core_raw = view.get_int_16(offset)
    offset += 2

    if core_raw == TEMPERATURE_UNAVAILABLE:
        core_temperature = None
    else:
        core_temperature = core_raw / 100.0

        if temperature_is_fahrenheit:
            core_temperature = _fahrenheit_to_celsius(
                core_temperature
            )

    skin_temperature = None
    core_reserved = None
    quality_state_raw = None
    core_data_quality = None
    heart_rate_state = None
    heart_rate = None
    heat_strain_index = None

    # Optional skin temperature.
    if flags & FLAG_SKIN_TEMPERATURE:
        if offset + 2 > len(packet):
            return None

        skin_raw = view.get_int_16(offset)
        offset += 2

        if skin_raw == TEMPERATURE_UNAVAILABLE:
            skin_temperature = None
        else:
            skin_temperature = skin_raw / 100.0

            if temperature_is_fahrenheit:
                skin_temperature = _fahrenheit_to_celsius(
                    skin_temperature
                )

    # Optional CORE reserved value.
    if flags & FLAG_CORE_RESERVED:
        if offset + 2 > len(packet):
            return None

        core_reserved = view.get_int_16(offset)
        offset += 2

    # Optional quality and state.
    if flags & FLAG_QUALITY_STATE:
        if offset + 1 > len(packet):
            return None

        quality_state = view.get_uint_8(offset)
        offset += 1
        quality_state_raw = quality_state

        quality = quality_state & 0x07
        state = (quality_state >> 4) & 0x03

        # 0b111 means quality information is unavailable.
        core_data_quality = None if quality == 0x07 else quality

        # 0b11 means HRM state information is unavailable.
        heart_rate_state = None if state == 0x03 else state

    # Optional heart rate.
    if flags & FLAG_HEART_RATE:
        if offset + 1 > len(packet):
            return None

        heart_rate_raw = view.get_uint_8(offset)
        offset += 1

        # CORE sends zero when no HR signal is being received.
        heart_rate = None if heart_rate_raw == 0 else heart_rate_raw

    # Optional Heat Strain Index.
    if flags & FLAG_HEAT_STRAIN_INDEX:
        if offset + 1 > len(packet):
            return None

        hsi_raw = view.get_uint_8(offset)
        offset += 1

        if hsi_raw != HEAT_STRAIN_INDEX_UNAVAILABLE:
            heat_strain_index = hsi_raw / 10.0

    # Some CORE 2 firmware appends one byte in the HSI position even when
    # FLAG_HEAT_STRAIN_INDEX is clear. The flag remains authoritative, so the
    # byte is tolerated but is not exposed as a measurement.
    remaining = len(packet) - offset
    if remaining:
        if not (flags & FLAG_HEAT_STRAIN_INDEX) and remaining == 1:
            pass
        else:
            return None

    return {
        "flags": flags,
        "core_temperature": core_temperature,
        "skin_temperature": skin_temperature,
        "core_reserved": core_reserved,
        "quality_state_raw": quality_state_raw,
        "core_data_quality": core_data_quality,
        "heart_rate_state": heart_rate_state,
        "heart_rate": heart_rate,
        "heat_strain_index": heat_strain_index,
    }


def _fahrenheit_to_celsius(value: float) -> float:
    """Convert Fahrenheit to Celsius."""

    return (value - 32.0) * 5.0 / 9.0
