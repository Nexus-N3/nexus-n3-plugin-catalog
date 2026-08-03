from types import SimpleNamespace

from standard_loading_intensity.intermediate_executor import (
    LoadingIntensityIntermediateExecutor,
)


def test_compute_accepts_namespace_axis_values_from_plugin_host() -> None:
    executor = LoadingIntensityIntermediateExecutor()
    results = [
        SimpleNamespace(
            algorithm_name="standard_loading_intensity",
            subject_id="subject-1",
            location="HEAD",
            frequency_band_results=[
                SimpleNamespace(
                    band_name="0-3",
                    axis_values=SimpleNamespace(x=2.0, y=4.0, z=6.0, mag=8.0),
                )
            ],
        ),
        SimpleNamespace(
            algorithm_name="standard_loading_intensity",
            subject_id="subject-1",
            location="HEAD",
            frequency_band_results=[
                SimpleNamespace(
                    band_name="0-3",
                    axis_values=SimpleNamespace(x=4.0, y=6.0, z=8.0, mag=10.0),
                )
            ],
        ),
    ]

    payload = executor.compute({"D4:22:CD:00:A8:FD": results})

    assert payload["algorithm_name"] == "standard_loading_intensity"
    assert payload["results"] == [
        {
            "address": "D4:22:CD:00:A8:FD",
            "location": "HEAD",
            "data": {
                "0-3": {
                    "x": 3.0,
                    "y": 5.0,
                    "z": 7.0,
                    "mag": 9.0,
                }
            },
        }
    ]
