from nexus_n3_sensor_x_imu3.sensor import XImu3Sensor


def test_sensor_spec_loads() -> None:
    spec = XImu3Sensor.load_raw_spec()
    assert spec["sensor"]["name"] == "X-IMU3"
    assert spec["sensor"]["adapter"] == "WIFI"
    assert spec["attributes"]["SAMPLING_RATE"]["default"] == 50
    assert spec["data_streams"]["imu"]["sample_type"] == "IMUSample"
    assert "standard_loading_intensity" in spec["computations"]
    assert "generic_data_summary" in spec["computations"]
