from nexus_n3_sensor_movella_dot.sensor import MovellaDotSensor


def test_sensor_spec_loads() -> None:
    spec = MovellaDotSensor.load_raw_spec()
    assert spec["sensor"]["name"] == "Movella DOT"
    assert spec["sensor"]["adapter"] == "BLE"
    assert "notify_battery" in spec["capabilities"]
    assert spec["attributes"]["SAMPLING_RATE"]["default"] == 60
