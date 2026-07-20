from pass_through.core import PassThroughAlgorithm


def test_import_algorithm() -> None:
    assert PassThroughAlgorithm.name == "pass_through"
