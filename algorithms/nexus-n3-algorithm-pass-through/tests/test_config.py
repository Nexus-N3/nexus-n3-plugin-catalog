from pass_through.core import PassThroughAlgorithm


def test_algorithm_config_loads() -> None:
    config = PassThroughAlgorithm.yaml_path()
    assert config.name == "config.yaml"
