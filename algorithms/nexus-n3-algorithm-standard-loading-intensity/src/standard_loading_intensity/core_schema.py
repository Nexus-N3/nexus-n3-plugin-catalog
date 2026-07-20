"""Schemas for standard loading intensity results."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

# this is generic to all alogrithms
class ComputeStage(str, Enum):
    """Processing stages for algorithm outputs."""
    REAL_TIME = "real_time"
    INTERMEDIATE_TIME = "intermediate_time"
    CONSOLIDATED_TIME = "consolidated_time"

@dataclass
class FrequencyBandResult:
    """Per-band loading intensity values for each axis."""
    band_name: str
    axis_values: Dict[str, float]  # x, y, z -> LI value

@dataclass
class LIComputedResult:
    """
    Real-time stage result for standard_loading_intensity algorithm.
    """
    address: str
    stage: ComputeStage
    result_count: int
    frequency_band_results: List[FrequencyBandResult]
    algorithm_name: str | None = None   # <-- add this
    subject_id: str | None = None
    location: str | None = None
