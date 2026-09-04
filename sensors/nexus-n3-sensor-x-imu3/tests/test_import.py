from nexus_n3_sensor_x_imu3.sensor import XImu3Sensor
from nexus_n3_plugin_sdk import SensorBase


def test_sensor_class_is_a_sensor_base_subclass() -> None:
    assert issubclass(XImu3Sensor, SensorBase)
