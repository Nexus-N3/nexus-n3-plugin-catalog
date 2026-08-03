"""Intermediate executor for loading intensity aggregation."""

from collections.abc import Mapping
from pathlib import Path

from nexus_n3_plugin_sdk import ExecutorBase, build_intermediate_result
from nexus_n3_plugin_sdk.yaml_loader import load_yaml

from .core_schema import (
    ComputeStage
)


def _items(value):
    """Return items from JSON mappings reconstructed by the plugin host."""
    if isinstance(value, Mapping):
        return value.items()
    try:
        return vars(value).items()
    except TypeError as exc:
        raise TypeError("axis_values must be a mapping or namespace") from exc

class LoadingIntensityIntermediateExecutor(ExecutorBase):
    """Aggregate per-sensor loading intensity results over time windows."""
    def __init__(self):
        """Initialize the executor and scheduling parameters."""
        config = self.__load_config()

        self.window_seconds = config["standards"]["window_seconds"]

        # scheduling specific to the algorithm
        if config["schedules"]["intermediate"]["enabled"]:
            # should equal 24 if set to 120 seconds
            # will be 2 for testing
            self.required_blocks = int(
                config["schedules"]["intermediate"]["period_seconds"] / self.window_seconds
            )
        else:
            self.required_blocks = None
        self.comparisons = config["schedules"]["intermediate"].get("comparisons", [])

        # track how many results we've already processed
        self._last_index = 0

    def __load_config(self) -> dict:
        """Load executor configuration from YAML."""
        spec = load_yaml(Path(__file__).with_name("config.yaml"))
        return spec

    def should_run(self, result_buffers):
        """
        Determine whether enough results are available to aggregate.

        Args:
            result_buffers: Mapping of address to result deque.

        Returns:
            True if aggregation should run, False otherwise.
        """
        if self.required_blocks is None:
            return False

        return all(
            len(buf) - self._last_index >= self.required_blocks
            for buf in result_buffers.values()
        )

    def run(self, result_buffers):
        """
        Aggregate the next block of results across sensors.

        Args:
            result_buffers: Mapping of address to result deque.

        Returns:
            Aggregated result dict or None.
        """
        if self.required_blocks is None:
            return None

        # take the next block for each sensor
        data = {
            addr: list(buf)[self._last_index : self._last_index + self.required_blocks]
            for addr, buf in result_buffers.items()
        }

        self._last_index += self.required_blocks

        return self.compute(data)

    def compute(self, data):
        """
        Compute averages across sensors and frequency bands.

        Args:
            data: Mapping of address to list of LIComputedResult.

        Returns:
            Aggregated result dict with averaged bands and sensor summaries.
        """
        from collections import defaultdict

        print("computing intermediate results")

        per_sensor_bands = {}
        per_sensor_locations = {}
        subject_location_bands = {}
        for addr, results in data.items():
            if not results:
                continue

            algo_name = results[0].algorithm_name
            subject_id = getattr(results[0], "subject_id", None)
            location = getattr(results[0], "location", None)
            if location:
                per_sensor_locations[addr] = location

            # Compute per-sensor averages per band/axis
            band_accumulator = defaultdict(lambda: defaultdict(list))
            for res in results:  # LIComputedResult
                for band in res.frequency_band_results:  # FrequencyBandResult
                    for axis, value in _items(band.axis_values):
                        band_accumulator[band.band_name][axis].append(value)

            per_sensor_bands[addr] = {}
            for band_name, axes in band_accumulator.items():
                per_sensor_bands[addr][band_name] = {}
                for axis, values in axes.items():
                    per_sensor_bands[addr][band_name][axis] = (
                        sum(values) / len(values) if values else None
                    )
            if subject_id and location:
                subject_location_bands.setdefault(subject_id, {})
                subject_location_bands[subject_id][location] = per_sensor_bands[addr]

        # Return structured intermediate result
        comparison_entries = []
        if self.comparisons:
            for subject_id, location_bands in subject_location_bands.items():
                for right_loc, left_loc in self.comparisons:
                    right_bands = location_bands.get(right_loc)
                    left_bands = location_bands.get(left_loc)
                    if not right_bands or not left_bands:
                        continue
                    key = f"{left_loc}_vs_{right_loc}"
                    comparison_entry = {
                        "subject_id": subject_id,
                        "kind": "comparison",
                        "pair": [left_loc, right_loc],
                        "data": {},
                    }
                    for band_name, axes in left_bands.items():
                        comparison_entry["data"].setdefault(band_name, {})
                        for axis, left_val in axes.items():
                            right_val = right_bands.get(band_name, {}).get(axis)
                            if right_val is None or left_val is None:
                                pct = None
                            else:
                                denom = (left_val + right_val) / 2.0
                                pct = None if denom == 0 else ((left_val - right_val) / denom) * 100.0
                            comparison_entry["data"][band_name][axis] = pct
                    comparison_entries.append(comparison_entry)

        algorithm_name = next(iter(data.values()))[0].algorithm_name if data else None
        results = [
            {"address": addr, "location": per_sensor_locations.get(addr), "data": bands}
            for addr, bands in per_sensor_bands.items()
        ]
        results.extend(comparison_entries)
        payload = build_intermediate_result(
            algorithm_name=algorithm_name,
            stage=ComputeStage.INTERMEDIATE_TIME,
            results=results,
        )
        return payload
