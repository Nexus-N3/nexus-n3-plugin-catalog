from nexus_n3_sensor_movesense.sensor import MovesenseSensor


def test_sensor_spec_loads() -> None:
    spec = MovesenseSensor.load_raw_spec()
    assert spec["sensor"]["name"] == "Movesense"
    assert spec["sensor"]["adapter"] == "BLE"
