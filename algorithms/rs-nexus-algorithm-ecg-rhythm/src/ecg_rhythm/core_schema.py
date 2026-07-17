"""Core schema for ECG rhythm metrics algorithm results."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class ComputeStage(str, Enum):
    """Processing stages for algorithm outputs."""
    REAL_TIME = "real_time"
    INTERMEDIATE_TIME = "intermediate_time"
    CONSOLIDATED_TIME = "consolidated_time"


@dataclass
class SQIResult:
    """Signal Quality Index components for the ECG window."""
    is_valid: bool
    reason: Optional[str]
    beats_in_window: int

    baseline_std: Optional[float] = None
    diff_std: Optional[float] = None
    clipping_fraction: Optional[float] = None
    present_fraction: Optional[float] = None


@dataclass
class ECGWindowFeatures:
    """Clinically useful rhythm features computed per window."""
    hr_mean_bpm: Optional[float]
    hr_min_bpm: Optional[float]
    hr_max_bpm: Optional[float]

    rr_mean_ms: Optional[float]
    sdnn_ms: Optional[float]
    rmssd_ms: Optional[float]
    cvrr: Optional[float]

    ectopy_count: int
    ectopy_present: bool


@dataclass
class ECGRhythmComputedResult:
    """
    Real-time stage result for ecg_rhythm_metrics algorithm.
    """
    address: str
    stage: ComputeStage
    result_count: int

    sqi: SQIResult
    features: ECGWindowFeatures
    rpeaks_ms: List[float]

    algorithm_name: Optional[str] = None
    subject_id: Optional[str] = None
    location: Optional[str] = None
