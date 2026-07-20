from standard_loading_intensity.core import StandardLoadingIntensityAlgorithm


def test_algorithm_config_loads() -> None:
    config = StandardLoadingIntensityAlgorithm.__mro__[0].yaml_path()
    assert config.name == "config.yaml"
