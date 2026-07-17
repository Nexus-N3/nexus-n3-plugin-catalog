from pathlib import Path

from rs_nexus_plugin_sdk.executor_base import ExecutorBase, build_intermediate_result
from rs_nexus_plugin_sdk.yaml_loader import load_yaml

from .core_schema import ComputeStage


class ECGRhythmIntermediateExecutor(ExecutorBase):
    """Aggregate per-sensor ECG rhythm window features with persistence logic."""
    def __init__(self):
        config = self.__load_config()

        self.window_seconds = config["standards"]["window_seconds"]

        if config["schedules"]["intermediate"]["enabled"]:
            self.required_blocks = int(
                config["schedules"]["intermediate"]["period_seconds"] / self.window_seconds
            )
        else:
            self.required_blocks = None

        self.persistence = config["schedules"]["intermediate"].get("persistence", {})
        self.rules = config["schedules"]["intermediate"].get("episode_rules", {})

        self._last_index = 0

    def __load_config(self) -> dict:
        return load_yaml(Path(__file__).resolve().parent / "config.yaml")

    def should_run(self, result_buffers):
        if self.required_blocks is None:
            return False
        return all(
            len(buf) - self._last_index >= self.required_blocks
            for buf in result_buffers.values()
        )

    def run(self, result_buffers):
        if self.required_blocks is None:
            return None

        next_index = self._last_index + self.required_blocks
        data = {
            # Keep full history up to the current execution point so persistence
            # rules can evaluate their configured lookback windows.
            addr: list(buf)[:next_index]
            for addr, buf in result_buffers.items()
        }
        self._last_index = next_index
        return self.compute(data)

    def compute(self, data):
        lookback = int(self.persistence.get("lookback_windows", 6))
        min_good = int(self.persistence.get("min_good_sqi_windows", 4))

        results = []

        for addr, window_results in data.items():
            if not window_results:
                continue

            # Take last lookback windows from what we have
            recent = window_results[-lookback:]
            good = [r for r in recent if getattr(r, "sqi", None) and r.sqi.is_valid]
            good_count = len(good)

            out = {
                "address": addr,
                "lookback_windows": len(recent),
                "good_sqi_windows": good_count,
                "flags": {},
            }

            if good_count < min_good:
                out["flags"]["valid_for_rhythm"] = False
                out["flags"]["af_suspected"] = False
                out["flags"]["brady_episode"] = False
                out["flags"]["tachy_episode"] = False
                results.append(out)
                continue

            out["flags"]["valid_for_rhythm"] = True

            # AF suspected (screening-style persistence on irregularity)
            af_cfg = self.rules.get("af_suspected", {})
            if af_cfg.get("enabled", True):
                cvrr_th = float(af_cfg.get("cvrr_threshold", 0.10))
                rmssd_th = float(af_cfg.get("rmssd_threshold_ms", 50))
                min_windows = int(af_cfg.get("min_windows_meeting_rule", 4))

                meet = 0
                for r in good:
                    f = r.features
                    if f.cvrr is not None and f.rmssd_ms is not None:
                        if f.cvrr >= cvrr_th and f.rmssd_ms >= rmssd_th:
                            meet += 1

                out["flags"]["af_suspected"] = bool(meet >= min_windows)
                out["af_rule"] = {
                    "meet_windows": meet,
                    "required": min_windows,
                    "cvrr_threshold": cvrr_th,
                    "rmssd_threshold_ms": rmssd_th,
                }
            else:
                out["flags"]["af_suspected"] = False

            # Brady episode
            br_cfg = self.rules.get("bradycardia", {})
            if br_cfg.get("enabled", True):
                hr_th = float(br_cfg.get("hr_threshold_bpm", 50))
                min_w = int(br_cfg.get("min_windows", 3))
                lows = sum(
                    1 for r in good
                    if r.features.hr_mean_bpm is not None and r.features.hr_mean_bpm < hr_th
                )
                out["flags"]["brady_episode"] = bool(lows >= min_w)
                out["brady_rule"] = {"below_threshold_windows": lows, "required": min_w, "hr_threshold_bpm": hr_th}
            else:
                out["flags"]["brady_episode"] = False

            # Tachy episode
            ta_cfg = self.rules.get("tachycardia", {})
            if ta_cfg.get("enabled", True):
                hr_th = float(ta_cfg.get("hr_threshold_bpm", 120))
                min_w = int(ta_cfg.get("min_windows", 3))
                highs = sum(
                    1 for r in good
                    if r.features.hr_mean_bpm is not None and r.features.hr_mean_bpm > hr_th
                )
                out["flags"]["tachy_episode"] = bool(highs >= min_w)
                out["tachy_rule"] = {"above_threshold_windows": highs, "required": min_w, "hr_threshold_bpm": hr_th}
            else:
                out["flags"]["tachy_episode"] = False

            # Ectopy context
            out["ectopy_windows"] = sum(1 for r in good if r.features.ectopy_present)

            results.append(out)

        algorithm_name = next(iter(data.values()))[0].algorithm_name if data else None
        return build_intermediate_result(
            algorithm_name=algorithm_name,
            stage=ComputeStage.INTERMEDIATE_TIME,
            results=results,
        )
