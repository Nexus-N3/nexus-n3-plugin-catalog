from generic_data_summary.core import GenericDataSummaryAlgorithm


def test_algorithm_config_loads() -> None:
    config = GenericDataSummaryAlgorithm.yaml_path()
    assert config.name == "config.yaml"
