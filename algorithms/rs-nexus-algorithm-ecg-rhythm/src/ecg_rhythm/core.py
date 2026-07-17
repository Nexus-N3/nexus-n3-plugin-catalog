import os
import numpy as np

from rs_nexus_plugin_sdk import AlgorithmBase
from rs_nexus_plugin_sdk.yaml_loader import load_yaml

from .core_schema import (
    ComputeStage,
    SQIResult,
    ECGWindowFeatures,
    ECGRhythmComputedResult,
)
from .processing import (
    bandpass_filter,
    detrend_ma,
    detect_rpeaks_derivative_energy,
    compute_rr_ms,
    rr_features,
    hr_from_rr,
    ectopy_flags,
    compute_sqi,
)


class ECGRhythmMetricsAlgorithm(AlgorithmBase):
    """Compute rhythm features from ECG in fixed windows."""

    name = "ecg_rhythm_metrics"

    def __init__(self, address, sampling_rate, input_parameters=None):
        config = load_yaml(self.yaml_path())
        super().__init__(config)

        self.address = address
        self.sampling_rate = sampling_rate

        self.subject_id = None
        self.location = None

        self.input_parameters = (
            input_parameters
            if input_parameters is not None
            else config.get("inputs", {}).get("parameters", {})
        )

        self.buffer = []
        self.result_count = 0

        self.window_seconds = config["standards"]["window_seconds"]
        self.window_size = int(self.window_seconds * sampling_rate)
        self._debug = os.getenv("NEXUS_ECG_DEBUG", "0") in ("1", "true", "TRUE")

        self.filter_cfg = config["standards"].get("pre_filter", {})
        self.detrend_cfg = config["standards"].get("detrend", {})
        self.detector_cfg = config["standards"].get("rpeak_detector", {})
        self.sqi_cfg = config["standards"].get("sqi", {})
        self.ectopy_cfg = config["standards"].get(
            "ectopy",
            {"enabled": True, "short_rr_ratio": 0.75, "long_rr_ratio": 1.20},
        )

    def on_sample(self, sample):
        sample_type = getattr(sample, "sample_type", None)
        if sample_type and sample_type != "ecg":
            return
        if sample_type is None and not hasattr(sample, "voltage"):
            return
        self.buffer.append(sample)

        if len(self.buffer) >= self.window_size:
            if self._debug:
                ts = [s.timestamp for s in self.buffer if getattr(s, "timestamp", None) is not None]
                if ts:
                    span_ms = max(ts) - min(ts)
                else:
                    span_ms = None
                print(
                    f"[ECG_DEBUG] window_ready address={self.address} "
                    f"samples={len(self.buffer)} span_ms={span_ms} "
                    f"sampling_rate={self.sampling_rate} window_seconds={self.window_seconds}"
                )
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
        # Extract timestamp + voltage; guard Optional[float] voltage
        total_n = len(self.buffer)
        present = [(s.timestamp, s.voltage) for s in self.buffer if s.voltage is not None]
        present_fraction = (len(present) / total_n) if total_n > 0 else 0.0

        # Use only present samples for processing
        if len(present) >= 2:
            t_ms = np.array([float(t) for (t, v) in present], dtype=float)
            x = np.array([float(v) for (t, v) in present], dtype=float)
        else:
            # Not enough data to process; emit invalid window
            t_ms = np.array([float(s.timestamp) for s in self.buffer], dtype=float)
            x = np.zeros((len(self.buffer),), dtype=float)

        # Pre-filter (bandpass)
        if self.filter_cfg.get("enabled", False) and len(x) >= 10:
            x_f = bandpass_filter(
                x,
                fs=self.sampling_rate,
                low_hz=float(self.filter_cfg["low_cutoff_hz"]),
                high_hz=float(self.filter_cfg["high_cutoff_hz"]),
                order=int(self.filter_cfg.get("order", 4)),
            )
        else:
            x_f = x

        # Detrend (baseline removal)
        x_dt = x_f
        if self.detrend_cfg.get("enabled", False) and len(x_f) >= 10:
            x_dt = detrend_ma(
                x_f,
                fs=self.sampling_rate,
                window_seconds=float(self.detrend_cfg.get("window_seconds", 0.8)),
            )

        # R-peaks
        rpeaks = []
        if self.detector_cfg.get("enabled", True) and len(x_dt) >= 20:
            thr_cfg = self.detector_cfg.get("threshold", {})
            k = float(thr_cfg.get("k", 3.0))

            rpeaks = detect_rpeaks_derivative_energy(
                x_dt,
                t_ms=t_ms,
                fs=self.sampling_rate,
                qrs_smooth_ms=float(self.detector_cfg.get("qrs_smooth_ms", 100)),
                refractory_ms=float(self.detector_cfg.get("refractory_ms", 250)),
                k=k,
            )

        # SQI
        sqi_dict = compute_sqi(
            x_raw=x,
            x_detrended=x_dt,
            rpeaks_ms=rpeaks,
            cfg=self.sqi_cfg,
            present_fraction=present_fraction,
        )
        sqi = SQIResult(**sqi_dict)

        # Features
        hr_mean = hr_min = hr_max = None
        rr_mean = sdnn = rmssd = cvrr = None
        ectopy_count = 0

        if sqi.is_valid and len(rpeaks) >= 2:
            rr = compute_rr_ms(rpeaks)
            feats = rr_features(rr)
            if feats:
                rr_mean, sdnn, rmssd, cvrr = feats

            hr_inst = hr_from_rr(rr)
            if hr_inst.size:
                hr_mean = float(np.mean(hr_inst))
                hr_min = float(np.min(hr_inst))
                hr_max = float(np.max(hr_inst))

            if self.ectopy_cfg.get("enabled", True):
                ectopy_count = ectopy_flags(
                    rr,
                    short_ratio=float(self.ectopy_cfg.get("short_rr_ratio", 0.75)),
                    long_ratio=float(self.ectopy_cfg.get("long_rr_ratio", 1.20)),
                )

        features = ECGWindowFeatures(
            hr_mean_bpm=hr_mean,
            hr_min_bpm=hr_min,
            hr_max_bpm=hr_max,
            rr_mean_ms=rr_mean,
            sdnn_ms=sdnn,
            rmssd_ms=rmssd,
            cvrr=cvrr,
            ectopy_count=int(ectopy_count),
            ectopy_present=bool(ectopy_count > 0),
        )

        self.result_count += 1

        result = ECGRhythmComputedResult(
            address=self.address,
            stage=ComputeStage.REAL_TIME,
            result_count=self.result_count,
            sqi=sqi,
            features=features,
            rpeaks_ms=rpeaks,
            algorithm_name=self.name,
            subject_id=self.subject_id,
            location=self.location,
        )

        print(f"[ALGO] Emitting result {result.result_count} for {result.address}")
        return result
