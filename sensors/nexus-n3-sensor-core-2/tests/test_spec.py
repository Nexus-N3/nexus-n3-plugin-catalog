from nexus_n3_sensor_core_2.sensor import Core2Sensor


def test_sensor_spec_loads() -> None:
    spec = Core2Sensor.load_raw_spec()
    assert spec["sensor"]["name"] == "Core 2"
    assert spec["sensor"]["adapter"] == "BLE"
