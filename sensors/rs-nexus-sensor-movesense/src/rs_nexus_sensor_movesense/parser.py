"""Movesense ECG packet parser."""

from __future__ import annotations

import struct

PACKET_TYPE_DATA = 2
ECG_SAMPLE_RATE_HZ = 200
ECG_SAMPLE_SCALE_MV = 0.38147 * 0.001


class DataView:
    """Tiny helper for little-endian binary parsing."""

    def __init__(self, data: bytes):
        self.data = data

    def _slice(self, start: int, count: int) -> bytes:
        return self.data[start:start + count]

    def get_uint_8(self, start: int) -> int:
        return int.from_bytes(self._slice(start, 1), byteorder="little", signed=False)

    def get_uint_16(self, start: int) -> int:
        return int.from_bytes(self._slice(start, 2), byteorder="little", signed=False)

    def get_uint_32(self, start: int) -> int:
        return struct.unpack("<I", self._slice(start, 4))[0]

    def get_int_32(self, start: int) -> int:
        return struct.unpack("<i", self._slice(start, 4))[0]


# uM (GSP unit for ECG)
# 10 ram 60 of flash (kilos)
def parse_ecg_packet(packet: bytes) -> list[tuple[int, float]]:
    """Return list of (timestamp, voltage_mV) from a Movesense ECG packet."""
    if not packet:
        return []

    view = DataView(packet)
    packet_type = view.get_uint_8(0)
    if packet_type != PACKET_TYPE_DATA:
        return []

    if len(packet) < 10:
        return []

    payload_len = len(packet) - 6
    if payload_len <= 0:
        return []

    timestamp = view.get_uint_32(2)
    samples: list[tuple[int, float]] = []

    if payload_len == 64:
        sample_count = 16
        for i in range(sample_count):
            offset = 6 + i * 4
            row_timestamp = timestamp + int(i * 1000 / ECG_SAMPLE_RATE_HZ)
            raw = view.get_int_32(offset)
            voltage = raw * ECG_SAMPLE_SCALE_MV
            samples.append((row_timestamp, voltage))
    elif payload_len == 32:
        sample_count = 16
        for i in range(sample_count):
            offset = 6 + i * 2
            row_timestamp = timestamp + int(i * 1000 / ECG_SAMPLE_RATE_HZ)
            raw = struct.unpack("<h", packet[offset:offset + 2])[0]
            voltage = raw * ECG_SAMPLE_SCALE_MV
            samples.append((row_timestamp, voltage))
    else:
        sample_count = payload_len // 4
        if sample_count <= 0:
            return []
        for i in range(sample_count):
            offset = 6 + i * 4
            if offset + 4 > len(packet):
                break
            row_timestamp = timestamp + int(i * 1000 / ECG_SAMPLE_RATE_HZ)
            voltage = view.get_int_32(offset) * ECG_SAMPLE_SCALE_MV
            samples.append((row_timestamp, voltage))
    return samples


def parse_hr_packet(packet: bytes) -> float | None:
    """Return heart rate value from a Movesense HR packet."""
    if not packet or len(packet) < 8:
        return None
    hr, _ = struct.unpack("<fh", packet[2:8])
    return float(hr)


def parse_hr_measurement(packet: bytes) -> int | None:
    """Parse standard BLE Heart Rate Measurement (0x2A37)."""
    if not packet:
        return None
    flags = packet[0]
    hr_16bit = flags & 0x01
    if hr_16bit:
        if len(packet) < 3:
            return None
        return int.from_bytes(packet[1:3], byteorder="little")
    if len(packet) < 2:
        return None
    return packet[1]


def parse_temp_packet(packet: bytes) -> float | None:
    """Return temperature value from a Movesense Temp packet."""
    if not packet or len(packet) < 6:
        return None
    if len(packet) >= 10:
        temp = struct.unpack("<f", packet[2:6])[0]
        if temp > 200:
            temp -= 273.15
        return float(temp)
    values = struct.unpack("<" + ((len(packet) - 6) // 4) * "f", packet[6:])
    if not values:
        return None
    temp = float(values[0])
    if temp > 200:
        temp -= 273.15
    return temp
