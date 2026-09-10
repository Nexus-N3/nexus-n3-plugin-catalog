from __future__ import annotations

from pathlib import Path
import struct
import sys

from nexus_n3_sensor_movesense.parser import (
    ECG_SAMPLE_RATE_HZ,
    parse_ecg_packet,
    parse_hr_packet,
    parse_temp_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
BLE_TOOLING_ROOT = REPO_ROOT / "nexus-n3-ble-tooling"

if str(BLE_TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(BLE_TOOLING_ROOT))

from Movesense.profile import (  # type: ignore
    parse_ecg_sample_timestamps_ms,
    parse_ecg_sample_values_mv,
    parse_hr_value,
    parse_temp_value,
)


def _build_ecg_packet_32bit() -> bytes:
    timestamp_ms = 123456
    samples = [1000 + index for index in range(16)]
    payload = bytearray([2, 100])
    payload.extend(struct.pack("<I", timestamp_ms))
    for sample in samples:
        payload.extend(struct.pack("<i", sample))
    return bytes(payload)


def _build_ecg_packet_16bit() -> bytes:
    timestamp_ms = 654321
    samples = [100 + index for index in range(16)]
    payload = bytearray([2, 100])
    payload.extend(struct.pack("<I", timestamp_ms))
    for sample in samples:
        payload.extend(struct.pack("<h", sample))
    return bytes(payload)


def test_ecg_parser_matches_ble_tooling_for_32bit_payload():
    packet = _build_ecg_packet_32bit()

    plugin_rows = parse_ecg_packet(packet)
    tooling_timestamps = parse_ecg_sample_timestamps_ms(packet, ECG_SAMPLE_RATE_HZ)
    tooling_values = parse_ecg_sample_values_mv(packet)

    assert plugin_rows == list(zip(tooling_timestamps, tooling_values))


def test_ecg_parser_matches_ble_tooling_for_16bit_payload():
    packet = _build_ecg_packet_16bit()

    plugin_rows = parse_ecg_packet(packet)
    tooling_timestamps = parse_ecg_sample_timestamps_ms(packet, ECG_SAMPLE_RATE_HZ)
    tooling_values = parse_ecg_sample_values_mv(packet)

    assert plugin_rows == list(zip(tooling_timestamps, tooling_values))


def test_hr_parser_matches_ble_tooling():
    packet = bytes([2, 1]) + struct.pack("<f", 72.5) + bytes([0x00, 0x00])

    assert parse_hr_packet(packet) == parse_hr_value(packet)


def test_temp_parser_matches_ble_tooling():
    packet = bytes([2, 2]) + struct.pack("<f", 36.75) + bytes([0x00, 0x00, 0x00, 0x00])

    assert parse_temp_packet(packet) == parse_temp_value(packet)
