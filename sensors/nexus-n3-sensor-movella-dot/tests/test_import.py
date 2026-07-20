from nexus_n3_sensor_movella_dot.sensor import MovellaDotSensor
from nexus_n3_plugin_sdk import SensorBase


def test_sensor_class_is_a_sensor_base_subclass() -> None:
    assert issubclass(MovellaDotSensor, SensorBase)
