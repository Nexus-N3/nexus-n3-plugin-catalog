from dataclasses import dataclass
import math

from generic_data_summary.core import GenericDataSummaryAlgorithm


@dataclass(frozen=True)
class _Sample:
    timestamp: int
    sensor_type: str
    address: str
    location: str | None
    sampling_rate: int | None
    value: float


def test_real_time_stats_include_rms_and_standard_deviation() -> None:
    algorithm = GenericDataSummaryAlgorithm(address="sensor-1", sampling_rate=1)
    algorithm.window_seconds = 4
    algorithm.window_size = 4

    emitted = []
    algorithm.register_result_listener(emitted.append)
    algorithm.register_compute_delegate(lambda *_args, **_kwargs: False)

    values = [1.0, 2.0, 3.0, 4.0]
    for index, value in enumerate(values):
        algorithm.on_sample(
            _Sample(
                timestamp=index,
                sensor_type="mock",
                address="sensor-1",
                location="CHEST",
                sampling_rate=1,
                value=value,
            )
        )

    assert len(emitted) == 1
    stats = emitted[0].metrics["value"]
    assert stats.min == 1.0
    assert stats.max == 4.0
    assert stats.mean == 2.5
    assert math.isclose(stats.rms, math.sqrt((1.0**2 + 2.0**2 + 3.0**2 + 4.0**2) / 4.0))
    assert math.isclose(stats.standard_deviation, math.sqrt(1.25))
    assert stats.count == 4
