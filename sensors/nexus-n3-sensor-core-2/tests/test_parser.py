"""Tests for CORE 2 BLE packet parsing."""

import struct

import pytest

from nexus_n3_sensor_core_2.parser import parse_core_temperature_packet


def test_parse_all_fields() -> None:
    """Parse a packet containing every optional field."""

    # Flags:
    # bit 0 - skin temperature valid
    # bit 1 - core reserved valid
    # bit 2 - quality/state valid
    # bit 3 - Celsius
    # bit 4 - heart rate valid
    # bit 5 - HSI valid
    flags = 0x37

    # Quality = poor (001)
    # HR state = supported, not receiving (01)
    quality_state = 0x11

    packet = struct.pack(
        "<BhhhBBB",
        flags,
        3865,   # 38.65 C
        3522,   # 35.22 C
        47,     # core reserved
        quality_state,
        120,    # bpm
        39,     # HSI 3.9
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["core_temperature"] == pytest.approx(38.65)
    assert result["skin_temperature"] == pytest.approx(35.22)
    assert result["core_reserved"] == 47
    assert result["core_data_quality"] == 1
    assert result["heart_rate_state"] == 1
    assert result["heart_rate"] == 120
    assert result["heat_strain_index"] == pytest.approx(3.9)


def test_parse_mandatory_core_temperature_only() -> None:
    """Parse the minimum valid CORE packet."""

    packet = struct.pack(
        "<Bh",
        0x00,
        3725,  # 37.25 C
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["core_temperature"] == pytest.approx(37.25)
    assert result["skin_temperature"] is None
    assert result["core_reserved"] is None
    assert result["core_data_quality"] is None
    assert result["heart_rate_state"] is None
    assert result["heart_rate"] is None
    assert result["heat_strain_index"] is None


def test_core_temperature_unavailable() -> None:
    """0x7FFF represents unavailable core temperature."""

    packet = struct.pack(
        "<Bh",
        0x00,
        0x7FFF,
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["core_temperature"] is None


def test_parse_fahrenheit_and_convert_to_celsius() -> None:
    """Temperature values encoded in Fahrenheit are normalized to Celsius."""

    flags = 0x09  # skin temperature valid + Fahrenheit

    packet = struct.pack(
        "<Bhh",
        flags,
        9860,  # 98.60 F = 37.0 C
        9500,  # 95.00 F = 35.0 C
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["core_temperature"] == pytest.approx(37.0)
    assert result["skin_temperature"] == pytest.approx(35.0)


def test_parse_quality_and_hr_state() -> None:
    """Split the quality/state byte into its two logical values."""

    flags = 0x04

    # Quality = excellent (100)
    # HR state = supported and receiving HR (10)
    quality_state = 0x24

    packet = struct.pack(
        "<BhB",
        flags,
        3700,
        quality_state,
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["core_data_quality"] == 4
    assert result["heart_rate_state"] == 2


def test_quality_and_hr_state_unavailable() -> None:
    """N/A values in the quality/state field become None."""

    flags = 0x04

    # Quality = 111 -> N/A
    # HR state = 11 -> N/A
    quality_state = 0x37

    packet = struct.pack(
        "<BhB",
        flags,
        3700,
        quality_state,
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["core_data_quality"] is None
    assert result["heart_rate_state"] is None


def test_heart_rate_zero_means_not_available() -> None:
    """CORE sends HR=0 when no heart-rate signal is available."""

    flags = 0x10

    packet = struct.pack(
        "<BhB",
        flags,
        3700,
        0,
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["heart_rate"] is None


def test_zero_hsi_is_valid() -> None:
    """HSI 0.0 is a valid value and must not be treated as missing."""

    flags = 0x20

    packet = struct.pack(
        "<BhB",
        flags,
        3700,
        0,
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["heat_strain_index"] == pytest.approx(0.0)


def test_hsi_unavailable() -> None:
    """0xFF represents unavailable Heat Strain Index."""

    flags = 0x20

    packet = struct.pack(
        "<BhB",
        flags,
        3700,
        0xFF,
    )

    result = parse_core_temperature_packet(packet)

    assert result is not None
    assert result["heat_strain_index"] is None


def test_empty_packet_is_ignored() -> None:
    assert parse_core_temperature_packet(b"") is None


def test_packet_shorter_than_mandatory_fields_is_ignored() -> None:
    assert parse_core_temperature_packet(b"\x00\x01") is None


def test_packet_truncated_inside_optional_field_is_ignored() -> None:
    # Skin-temperature flag is set, but only the mandatory
    # core-temperature bytes are present.
    packet = struct.pack(
        "<Bh",
        0x01,
        3700,
    )

    assert parse_core_temperature_packet(packet) is None


def test_packet_with_unexpected_extra_bytes_is_ignored() -> None:
    packet = struct.pack(
        "<Bh",
        0x00,
        3700,
    ) + b"\x00"

    assert parse_core_temperature_packet(packet) is None


def test_reserved_flag_bits_are_rejected() -> None:
    # Bit 6 is RFU in the current specification.
    packet = struct.pack(
        "<Bh",
        0x40,
        3700,
    )

    assert parse_core_temperature_packet(packet) is None