"""Helpers for generic numeric field extraction and summarization."""

from __future__ import annotations

import math
from dataclasses import is_dataclass
from numbers import Number
from typing import Dict, Iterable, Tuple


META_FIELDS = {
    "timestamp",
    "sensor_type",
    "address",
    "location",
    "sampling_rate",
}


def _is_number(value) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool)


def _iter_numeric_fields(sample, exclude_fields: set[str]) -> Iterable[Tuple[str, float]]:
    """
    Yield (field_name, value) for numeric fields in a sample.
    Supports scalars, tuples/lists, and dataclasses.
    """
    if is_dataclass(sample):
        data = vars(sample)
    else:
        data = getattr(sample, "__dict__", {}) or {}

    for key, value in data.items():
        if key in META_FIELDS or key in exclude_fields:
            continue
        if value is None:
            continue
        if _is_number(value):
            yield key, float(value)
        elif isinstance(value, (list, tuple)) and value:
            for idx, item in enumerate(value):
                if _is_number(item):
                    yield f"{key}.{idx}", float(item)


def _iter_vector_groups(sample, exclude_fields: set[str]) -> Iterable[Tuple[str, Tuple[float, ...]]]:
    """
    Yield (field_name, vector_values) for list/tuple fields of numeric values.
    Only yields when all items are numeric.
    """
    if is_dataclass(sample):
        data = vars(sample)
    else:
        data = getattr(sample, "__dict__", {}) or {}

    for key, value in data.items():
        if key in META_FIELDS or key in exclude_fields:
            continue
        if isinstance(value, (list, tuple)) and value:
            if all(_is_number(item) for item in value):
                yield key, tuple(float(item) for item in value)


def update_stats(stats: Dict[str, dict], key: str, value: float) -> None:
    """Update a running stats bucket for a single key."""
    bucket = stats.setdefault(
        key,
        {
            "min": value,
            "max": value,
            "sum": 0.0,
            "sum_squares": 0.0,
            "count": 0,
        },
    )
    if value < bucket["min"]:
        bucket["min"] = value
    if value > bucket["max"]:
        bucket["max"] = value
    bucket["sum"] += value
    bucket["sum_squares"] += value * value
    bucket["count"] += 1


def compute_magnitude(values: Tuple[float, ...]) -> float:
    return math.sqrt(sum(v * v for v in values))
