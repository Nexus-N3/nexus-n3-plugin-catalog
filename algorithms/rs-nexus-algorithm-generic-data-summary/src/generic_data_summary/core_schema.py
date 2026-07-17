"""Core schema for generic data summary results."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class ComputeStage(str, Enum):
    """Processing stages for algorithm outputs."""
    REAL_TIME = "real_time"
    INTERMEDIATE_TIME = "intermediate_time"
    CONSOLIDATED_TIME = "consolidated_time"


@dataclass
class SummaryStats:
    """Summary statistics for a numeric field."""
    min: Optional[float]
    max: Optional[float]
    mean: Optional[float]
    rms: Optional[float]
    standard_deviation: Optional[float]
    count: int


@dataclass
class GenericSummaryResult:
    """Real-time stage result for generic_data_summary algorithm."""
    address: str
    stage: ComputeStage
    result_count: int
    metrics: Dict[str, SummaryStats]

    algorithm_name: Optional[str] = None
    subject_id: Optional[str] = None
    location: Optional[str] = None
    sample_type: Optional[str] = None
