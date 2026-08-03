from standard_loading_intensity.consolidation_executor import (
    LoadingIntensityConsolidationExecutor,
)


def test_consolidates_persisted_intermediate_records() -> None:
    executor = LoadingIntensityConsolidationExecutor()
    records = [
        {
            "algorithm_name": "standard_loading_intensity",
            "stage": "intermediate_time",
            "results": [
                {
                    "address": "D4:22:CD:00:A8:FD",
                    "location": "HEAD",
                    "data": {"0-3": {"x": value, "mag": value * 2}},
                }
            ],
        }
        for value in (2.0, 4.0)
    ]

    payload = executor.consolidate("subject-1", records)

    assert payload["algorithm_name"] == "standard_loading_intensity"
    assert payload["stage"] == "consolidated_time"
    assert payload["subject_id"] == "subject-1"
    assert payload["results"] == [
        {
            "address": "D4:22:CD:00:A8:FD",
            "kind": "sensor_summary",
            "window_count": 2,
            "data": {
                "0-3": {
                    "mag": {
                        "count": 2,
                        "mean": 6.0,
                        "min": 4.0,
                        "max": 8.0,
                        "p50": 6.0,
                        "p95": 7.8,
                    },
                    "x": {
                        "count": 2,
                        "mean": 3.0,
                        "min": 2.0,
                        "max": 4.0,
                        "p50": 3.0,
                        "p95": 3.9,
                    },
                }
            },
        }
    ]


def test_ignores_records_from_other_algorithms() -> None:
    executor = LoadingIntensityConsolidationExecutor()

    payload = executor.consolidate(
        "subject-1",
        [{"algorithm_name": "another_algorithm", "results": []}],
    )

    assert payload["results"] == []
