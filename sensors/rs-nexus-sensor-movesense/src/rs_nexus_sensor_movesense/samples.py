"""Movesense sample data models."""

from dataclasses import dataclass
from typing import Any, ClassVar, List, Optional

from rs_nexus_plugin_sdk.samples.base import SensorSample


@dataclass(frozen=True)
class ECGSample(SensorSample):
    """Represents a single ECG voltage sample."""

    sample_type: ClassVar[str] = "ecg"

    voltage: Optional[float]

    @classmethod
    def csv_header(cls) -> List[str]:
        return [
            "timestamp",
            "voltage_mv",
        ]

    def to_csv_row(self) -> List[Any]:
        return [
            self.timestamp,
            self.voltage,
        ]


@dataclass(frozen=True)
class TempSample(SensorSample):
    """Represents a single temperature sample in Celsius."""

    sample_type: ClassVar[str] = "temp"

    temperature_c: Optional[float]

    @classmethod
    def csv_header(cls) -> List[str]:
        return [
            "timestamp",
            "temperature_c",
        ]

    def to_csv_row(self) -> List[Any]:
        return [
            self.timestamp,
            self.temperature_c,
        ]
