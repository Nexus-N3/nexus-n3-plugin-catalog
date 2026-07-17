from rs_nexus_sensor_movella_dot.sensor import MovellaDotSensor
from rs_nexus_plugin_sdk import SensorBase


def test_sensor_class_is_a_sensor_base_subclass() -> None:
    assert issubclass(MovellaDotSensor, SensorBase)
