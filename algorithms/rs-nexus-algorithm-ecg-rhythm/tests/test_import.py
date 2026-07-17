from ecg_rhythm.core import ECGRhythmMetricsAlgorithm
from ecg_rhythm.intermediate_executor import ECGRhythmIntermediateExecutor


def test_import_algorithm() -> None:
    assert ECGRhythmMetricsAlgorithm.name == "ecg_rhythm_metrics"
    assert ECGRhythmIntermediateExecutor is not None
