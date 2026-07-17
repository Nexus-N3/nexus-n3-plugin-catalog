"""Standard loading intensity algorithm implementation."""

import os
import time
from datetime import datetime
import logging

from rs_nexus_plugin_sdk import AlgorithmBase
from rs_nexus_plugin_sdk.yaml_loader import load_yaml

from .core_schema import (
    FrequencyBandResult,
    LIComputedResult,
    ComputeStage
)
from .processing import (
    extract_axes,
    pre_filter_axes,
    compute_li_for_signal,
    vector_magnitude,
    normalise_gravity
)

#from collections import defaultdict, deque
logger = logging.getLogger("standard_loading_intensity")

class StandardLoadingIntensityAlgorithm(AlgorithmBase):
    """Compute loading intensity across configured frequency bands."""

    name = "standard_loading_intensity" # should match the directory name
    _EPSILON = 1e-9

    def __init__(self, address, sampling_rate, input_parameters=None):
        """
        Initialize the algorithm instance.

        Args:
            address: Sensor address for this algorithm instance.
            sampling_rate: Sampling rate in Hz.
            input_parameters: Optional parameter overrides.
        """
        config = self.__load_config()
        super().__init__(config)

        self.address = address
        self.sampling_rate = sampling_rate
        self.subject_id = None
        self.location = None
        
        default_parameters = config.get("inputs", {}).get("parameters", {}) or {}
        self.input_parameters = self._resolve_input_parameters(
            input_parameters=input_parameters,
            default_parameters=default_parameters,
        )

        self.buffer = []
        self.result_count = 0

        self.window_seconds = config["standards"]["window_seconds"]
        self.window_size = int(self.window_seconds * sampling_rate)
        self._last_emit_time = None

        self.f_bands = config["standards"]["frequency_bands"]
        self.filter_cfg = config["standards"].get("pre_filter", {})
        self._perf_enabled = _env_flag("NEXUS_PERF_LOG", default=False)

    def _resolve_input_parameters(self, input_parameters, default_parameters):
        """
        Merge/normalize algorithm input parameters with support for named gravity presets.

        Supported forms:
        - {"gravity": 9.80665}
        - {"gravity_option": "moon", "gravity_options": {...}}
        - {"gravity_option": "mars"}  # uses configured defaults map
        """
        params = dict(default_parameters or {})
        if isinstance(input_parameters, dict):
            params.update(input_parameters)

        options = params.get("gravity_options")
        if not isinstance(options, dict):
            options = {}
        normalized_options = {}
        for key, value in options.items():
            key_str = str(key).strip().lower()
            try:
                normalized_options[key_str] = float(value)
            except (TypeError, ValueError):
                continue
        params["gravity_options"] = normalized_options

        gravity_option = params.get("gravity_option")
        resolved_gravity = None
        if gravity_option is not None:
            option_key = str(gravity_option).strip().lower()
            if option_key in normalized_options:
                resolved_gravity = normalized_options[option_key]
                params["gravity_option"] = option_key

        if resolved_gravity is None:
            try:
                resolved_gravity = float(params.get("gravity"))
            except (TypeError, ValueError):
                resolved_gravity = float(default_parameters.get("gravity", 9.80665))

        # In zero-g mode, use near-zero sentinel handling in `normalise_gravity`
        # (it bypasses normalization instead of dividing by zero).
        if abs(resolved_gravity) < self._EPSILON:
            resolved_gravity = 0.0

        params["gravity"] = resolved_gravity
        return params


    def __load_config(self) -> dict:
        """Load algorithm configuration from YAML."""
        spec = load_yaml(self.yaml_path())
        return spec

    def on_sample(self, sample):
        """
        Ingest a sample and emit results when the window is full.

        Args:
            sample: Sensor sample payload.
        """

        self.buffer.append(sample)

        if len(self.buffer) >= self.window_size:
            window_end_ts = time.time()
            if self._perf_enabled and len(self.buffer) != self.window_size:
                logger.info(
                    "perf window size mismatch address=%s expected=%s got=%s",
                    self.address,
                    self.window_size,
                    len(self.buffer),
                )
            delegate_cfg = self.config.get("algorithm", {}).get("compute", {})
            delegate_enabled = delegate_cfg.get("delegate", True)
            if delegate_enabled and getattr(self, "compute_delegate", None):
                delegated = self.compute_delegate(self, list(self.buffer))
                if delegated:
                    self.buffer.clear()
                    return
            t0 = time.perf_counter()
            result  = self.execute_real_time()
            if self._perf_enabled:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "perf compute time algo=%s address=%s samples=%s ms=%.2f",
                    self.name,
                    self.address,
                    self.window_size,
                    elapsed_ms,
                )
            self.buffer.clear()
            emit_ts = time.time()
            latency_ms = (emit_ts - window_end_ts) * 1000.0
            interval_s = None
            if self._last_emit_time is not None:
                interval_s = emit_ts - self._last_emit_time
            self._last_emit_time = emit_ts
            if self._perf_enabled:
                logger.info(
                    "perf latency algo=%s address=%s interval_s=%s window_end_time=%s compute_emit_time=%s latency_ms=%.2f",
                    self.name,
                    self.address,
                    f"{interval_s:.3f}" if interval_s is not None else "first",
                    datetime.fromtimestamp(window_end_ts).isoformat(timespec="milliseconds"),
                    datetime.fromtimestamp(emit_ts).isoformat(timespec="milliseconds"),
                    latency_ms,
                )
            self.emit_result(result)

    def execute_real_time(self):
        """
        Compute a real-time loading intensity result for the current buffer.

        Returns:
            LIComputedResult instance.
        """
        ax, ay, az = extract_axes(self.buffer)
        ax, ay, az = normalise_gravity(ax,ay,az, self.input_parameters["gravity"])
        amag = vector_magnitude([ax, ay, az])

        if self.filter_cfg.get("enabled", False):
            ax, ay, az, amag = pre_filter_axes(
                ax, ay, az, amag,
                sampling_rate=self.sampling_rate,
                low_cutoff=self.filter_cfg["low_cutoff_hz"],
                high_cutoff=self.filter_cfg["high_cutoff_hz"],
                order=self.filter_cfg["order"]
            )

        self.result_count += 1

        frequency_band_results = []

        for f_low, f_high in self.f_bands:
            band_name = f"{f_low}-{f_high}"

            band_result = FrequencyBandResult(
                band_name=band_name,
                axis_values={
                    "x": compute_li_for_signal(ax, self.sampling_rate, (f_low, f_high)),
                    "y": compute_li_for_signal(ay, self.sampling_rate, (f_low, f_high)),
                    "z": compute_li_for_signal(az, self.sampling_rate, (f_low, f_high)),
                    'mag': compute_li_for_signal(amag, self.sampling_rate, (f_low, f_high)),
                }
            )

            frequency_band_results.append(band_result)

        result = LIComputedResult(
            address=self.address,
            stage=ComputeStage.REAL_TIME,
            result_count=self.result_count,
            frequency_band_results=frequency_band_results,
            algorithm_name=self.name,
            subject_id=self.subject_id,
            location=self.location,
        )


        print(
            f"[ALGO] Emitting result {result.result_count} "
            f"for {result.address} at {result.location}"
        )

        return result


def _env_flag(name, default=False):
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}

        
