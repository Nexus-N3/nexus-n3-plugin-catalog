from generic_data_summary.core import GenericDataSummaryAlgorithm


def test_import_algorithm() -> None:
    assert GenericDataSummaryAlgorithm.name == "generic_data_summary"
