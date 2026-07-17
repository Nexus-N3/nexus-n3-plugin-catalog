from rs_nexus_sensor_movesense.sensor import MovesenseSensor


def test_import_sensor() -> None:
    assert MovesenseSensor.sensor_type.local_name == "Movesense"
