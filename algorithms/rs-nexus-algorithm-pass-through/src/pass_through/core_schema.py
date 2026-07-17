"""Schema for pass-through algorithm results."""

from dataclasses import dataclass


@dataclass
class PassThroughResult:
    """Batch payload for pass-through results."""
    address: str
    algorithm_name: str
    stage: str
    sample_count: int
    samples: list
