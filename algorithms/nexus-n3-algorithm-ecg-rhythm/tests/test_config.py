from pathlib import Path

from nexus_n3_plugin_sdk.yaml_loader import load_yaml

from ecg_rhythm.core import ECGRhythmMetricsAlgorithm


def test_algorithm_config_loads() -> None:
    config = ECGRhythmMetricsAlgorithm.yaml_path()
    assert config.name == "config.yaml"


def test_consolidated_schedule_is_disabled() -> None:
    config_path = Path(__file__).resolve().parents[1] / "src" / "ecg_rhythm" / "config.yaml"
    config = load_yaml(config_path)
    assert config["schedules"]["consolidated"]["enabled"] is False
