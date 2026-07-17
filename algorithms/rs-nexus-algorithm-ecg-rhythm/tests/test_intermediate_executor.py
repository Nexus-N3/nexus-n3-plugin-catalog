from collections import deque
from dataclasses import dataclass, field

from ecg_rhythm.intermediate_executor import ECGRhythmIntermediateExecutor


@dataclass
class _DummySQI:
    is_valid: bool = True


@dataclass
class _DummyFeatures:
    hr_mean_bpm: float | None = 72.0
    rmssd_ms: float | None = 75.0
    cvrr: float | None = 0.14
    ectopy_present: bool = False


@dataclass
class _DummyResult:
    algorithm_name: str = "ecg_rhythm_metrics"
    sqi: _DummySQI = field(default_factory=_DummySQI)
    features: _DummyFeatures = field(default_factory=_DummyFeatures)


def test_intermediate_executor_uses_history_for_persistence_rules() -> None:
    executor = ECGRhythmIntermediateExecutor()
    buffers = {"movesense": deque()}

    for _ in range(6):
        buffers["movesense"].append(_DummyResult())

    payload = None
    for _ in range(6):
        assert executor.should_run(buffers) is True
        payload = executor.run(buffers)

    assert payload is not None
    result = payload["results"][0]

    assert result["lookback_windows"] == 6
    assert result["good_sqi_windows"] == 6
    assert result["flags"]["valid_for_rhythm"] is True
    assert result["flags"]["af_suspected"] is True
