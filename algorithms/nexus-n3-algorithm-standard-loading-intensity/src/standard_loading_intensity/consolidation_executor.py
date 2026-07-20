"""Consolidation executor for loading intensity aggregation at stream stop."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from nexus_n3_plugin_sdk import ExecutorBase, build_consolidated_result


class LoadingIntensityConsolidationExecutor(ExecutorBase):
    """Build consolidated summaries from intermediate-stage records."""

    def should_run(self, result_buffers: Dict[str, Any]) -> bool:
        # This executor is triggered explicitly on stop, not on rolling buffers.
        return bool(result_buffers)

    def run(self, result_buffers: Dict[str, Any]) -> Optional[Any]:
        # Not used by the current stop-triggered flow.
        return None

    def compute(self, data: Dict[str, Any]) -> Any:
        # Not used directly; kept for ExecutorBase compatibility.
        return data

    def consolidate(self, subject_id: str, intermediate_records: List[dict]) -> dict:
        per_sensor: Dict[str, Dict[str, Dict[str, List[float]]]] = {}
        comparisons: Dict[Tuple[str, str], Dict[str, Dict[str, List[float]]]] = {}

        for record in intermediate_records:
            if (record.get("algorithm_name") or "").strip().lower() != "standard_loading_intensity":
                continue
            for entry in record.get("results", []):
                address = entry.get("address")
                if address:
                    data = entry.get("data", {}) or {}
                    sensor_bucket = per_sensor.setdefault(address, {})
                    self._append_bands(sensor_bucket, data)
                    continue
                if entry.get("kind") == "comparison":
                    pair = entry.get("pair") or []
                    if len(pair) != 2:
                        continue
                    key = (str(pair[0]), str(pair[1]))
                    comp_bucket = comparisons.setdefault(key, {})
                    self._append_bands(comp_bucket, entry.get("data", {}) or {})

        results = []
        for address, bands in sorted(per_sensor.items()):
            metrics, count = self._summarize_bands(bands)
            results.append(
                {
                    "address": address,
                    "kind": "sensor_summary",
                    "window_count": count,
                    "data": metrics,
                }
            )

        for pair, bands in sorted(comparisons.items()):
            metrics, count = self._summarize_bands(bands)
            results.append(
                {
                    "kind": "comparison_summary",
                    "pair": [pair[0], pair[1]],
                    "window_count": count,
                    "data": metrics,
                }
            )

        payload = build_consolidated_result(
            algorithm_name="standard_loading_intensity",
            stage="consolidated_time",
            results=results,
        )
        payload["subject_id"] = subject_id
        return payload

    def _append_bands(
        self,
        target: Dict[str, Dict[str, List[float]]],
        data: Dict[str, Dict[str, Any]],
    ) -> None:
        for band_name, axes in data.items():
            band_bucket = target.setdefault(str(band_name), {})
            if not isinstance(axes, dict):
                continue
            for axis, value in axes.items():
                try:
                    as_float = float(value)
                except (TypeError, ValueError):
                    continue
                band_bucket.setdefault(str(axis), []).append(as_float)

    def _summarize_bands(
        self,
        bands: Dict[str, Dict[str, List[float]]],
    ) -> Tuple[Dict[str, Dict[str, Dict[str, float | int | None]]], int]:
        out: Dict[str, Dict[str, Dict[str, float | int | None]]] = {}
        window_count = 0
        for band_name, axes in sorted(bands.items()):
            out[band_name] = {}
            for axis, values in sorted(axes.items()):
                metrics = self._metrics(values)
                out[band_name][axis] = metrics
                window_count = max(window_count, metrics["count"])
        return out, window_count

    def _metrics(self, values: List[float]) -> Dict[str, float | int | None]:
        if not values:
            return {
                "count": 0,
                "mean": None,
                "min": None,
                "max": None,
                "p50": None,
                "p95": None,
            }
        sorted_vals = sorted(values)
        count = len(sorted_vals)
        mean = sum(sorted_vals) / count
        return {
            "count": count,
            "mean": mean,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": self._percentile(sorted_vals, 0.50),
            "p95": self._percentile(sorted_vals, 0.95),
        }

    def _percentile(self, sorted_vals: List[float], p: float) -> float:
        if not sorted_vals:
            return 0.0
        if len(sorted_vals) == 1:
            return sorted_vals[0]
        pos = (len(sorted_vals) - 1) * p
        low = int(pos)
        high = min(low + 1, len(sorted_vals) - 1)
        frac = pos - low
        return sorted_vals[low] + (sorted_vals[high] - sorted_vals[low]) * frac
