"""CORE 2 sample data models."""

from dataclasses import dataclass
from typing import Any, ClassVar, List, Optional

from nexus_n3_plugin_sdk.samples.base import SensorSample


@dataclass(frozen=True)
class Core2Sample(SensorSample):
    """Represents a single CORE 2 measurement notification."""

    sample_type: ClassVar[str] = "temperature"

    core_temperature: Optional[float]
    skin_temperature: Optional[float]
    core_reserved: Optional[int]
    core_data_quality: Optional[int]
    heart_rate_state: Optional[int]
    heart_rate: Optional[int]
    heat_strain_index: Optional[float]

    @classmethod
    def csv_header(cls) -> List[str]:
        return [
            "timestamp",
            "core_temperature",
            "skin_temperature",
            "core_reserved",
            "core_data_quality",
            "heart_rate_state",
            "heart_rate",
            "heat_strain_index",
        ]

    def to_csv_row(self) -> List[Any]:
        return [
            self.timestamp,
            self.core_temperature,
            self.skin_temperature,
            self.core_reserved,
            self.core_data_quality,
            self.heart_rate_state,
            self.heart_rate,
            self.heat_strain_index,
        ]