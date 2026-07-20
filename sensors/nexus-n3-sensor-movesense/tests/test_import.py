from nexus_n3_sensor_movesense.sensor import MovesenseSensor


def test_import_sensor() -> None:
    assert MovesenseSensor.sensor_type.local_name == "Movesense"
