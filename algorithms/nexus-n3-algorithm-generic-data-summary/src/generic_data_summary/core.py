"""Generic data summary algorithm implementation."""

import math

from nexus_n3_plugin_sdk import AlgorithmBase
from nexus_n3_plugin_sdk.yaml_loader import load_yaml

from .core_schema import ComputeStage, GenericSummaryResult, SummaryStats
from .processing import (
    _iter_numeric_fields,
    _iter_vector_groups,
    update_stats,
    compute_magnitude,
)


class GenericDataSummaryAlgorithm(AlgorithmBase):
    """Compute basic summary stats for numeric fields in a fixed window."""

    name = "generic_data_summary"

    def __init__(self, address, sampling_rate, input_parameters=None):
        config = load_yaml(self.yaml_path())
        super().__init__(config)

        self.address = address
        self.sampling_rate = sampling_rate
        self.subject_id = None
        self.location = None

        self.input_parameters = input_parameters if input_parameters is not None else {}

        self.buffer = []
        self.result_count = 0

        self.window_seconds = config["standards"]["window_seconds"]
        self.window_size = int(self.window_seconds * sampling_rate)

        output_cfg = config["standards"].get("output", {})
        self.include_components = bool(output_cfg.get("include_components", True))
        self.include_magnitude = bool(output_cfg.get("include_magnitude", True))
        self.magnitude_lengths = set(output_cfg.get("magnitude_fields_only_for", [3, 4]))
        self.exclude_fields = set(output_cfg.get("exclude_fields", []))

    def on_sample(self, sample):
        self.buffer.append(sample)

        if len(self.buffer) >= self.window_size:
            delegate_cfg = self.config.get("algorithm", {}).get("compute", {})
            delegate_enabled = delegate_cfg.get("delegate", True)
            if delegate_enabled and getattr(self, "compute_delegate", None):
                delegated = self.compute_delegate(self, list(self.buffer))
                if delegated:
                    self.buffer.clear()
                    return

            result = self.execute_real_time()
            self.buffer.clear()
            self.emit_result(result)

    def execute_real_time(self):
        stats = {}
        sample_type = None

        for sample in self.buffer:
            if sample_type is None:
                sample_type = getattr(sample, "sample_type", None)

            if self.include_components:
                for key, value in _iter_numeric_fields(sample, self.exclude_fields):
                    update_stats(stats, key, value)

            if self.include_magnitude:
                for key, values in _iter_vector_groups(sample, self.exclude_fields):
                    if len(values) in self.magnitude_lengths:
                        update_stats(stats, f"{key}.mag", compute_magnitude(values))

        metrics = {}
        for key, bucket in stats.items():
            count = bucket["count"]
            if count <= 0:
                metrics[key] = SummaryStats(
                    min=None,
                    max=None,
                    mean=None,
                    rms=None,
                    standard_deviation=None,
                    count=0,
                )
                continue
            mean = bucket["sum"] / count
            mean_square = bucket["sum_squares"] / count
            variance = max(0.0, mean_square - (mean * mean))
            metrics[key] = SummaryStats(
                min=bucket["min"],
                max=bucket["max"],
                mean=mean,
                rms=math.sqrt(mean_square),
                standard_deviation=math.sqrt(variance),
                count=count,
            )

        self.result_count += 1
        return GenericSummaryResult(
            address=self.address,
            stage=ComputeStage.REAL_TIME,
            result_count=self.result_count,
            metrics=metrics,
            algorithm_name=self.name,
            subject_id=self.subject_id,
            location=self.location,
            sample_type=sample_type,
        )
