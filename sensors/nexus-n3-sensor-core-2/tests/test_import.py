from nexus_n3_sensor_core_2.sensor import Core2Sensor
from nexus_n3_plugin_sdk import SensorBase


def test_sensor_class_is_a_sensor_base_subclass() -> None:
    assert issubclass(Core2Sensor, SensorBase)
