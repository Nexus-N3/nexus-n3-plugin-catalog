from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import nexus_n3_sensor_x_imu3.sensor as sensor_module
from nexus_n3_sensor_x_imu3.sensor import XImu3Sensor


class FakeAnnouncement:
    device_name = "x-IMU3"
    serial_number = "6A33CA84"
    ip_address = "10.42.0.48"
    tcp_port = 7000
    udp_send = 8048
    udp_receive = 9000
    rssi = 91
    battery = 78

    def to_udp_connection_config(self):
        return "udp-config"


class FakeNetworkAnnouncement:
    calls = 0

    def get_messages_after_short_delay(self):
        self.__class__.calls += 1
        return [
            FakeAnnouncement(),
            SimpleNamespace(
                device_name="x-IMU3",
                serial_number="OFF_SUBNET",
                ip_address="192.168.1.20",
            ),
        ]


class FakeConnection:
    instances = []

    def __init__(self, config):
        self.config = config
        self.closed = False
        self.commands = []
        self.callbacks = {}
        self.removed_callbacks = []
        self._next_callback_id = 1
        self.__class__.instances.append(self)

    def open(self):
        return self

    def ping(self):
        return SimpleNamespace(serial_number="6A33CA84")

    def send_command(self, command):
        self.commands.append(command)
        return SimpleNamespace(error=None)

    def send_commands(self, commands):
        self.commands.extend(commands)
        return [SimpleNamespace(error=None) for _command in commands]

    def add_inertial_callback(self, callback):
        return self._add_callback("inertial", callback)

    def add_quaternion_callback(self, callback):
        return self._add_callback("quaternion", callback)

    def _add_callback(self, message_type, callback):
        callback_id = self._next_callback_id
        self._next_callback_id += 1
        self.callbacks[message_type] = (callback_id, callback)
        return callback_id

    def remove_callback(self, callback_id):
        self.removed_callbacks.append(callback_id)

    def close(self):
        self.closed = True


def test_discover_connect_identify_and_disconnect(monkeypatch):
    fake_ximu3 = SimpleNamespace(
        NetworkAnnouncement=FakeNetworkAnnouncement,
        Connection=FakeConnection,
    )
    monkeypatch.setattr(sensor_module, "ximu3", fake_ximu3)
    FakeConnection.instances.clear()
    sensor = XImu3Sensor()
    assert sensor.get_wifi_driver() is sensor

    async def scenario():
        devices = await sensor.discover_connected(
            SimpleNamespace(cidr="10.42.0.1/24")
        )

        assert devices == [
            {
                "address": "6A33CA84",
                "endpoint": "10.42.0.48",
                "metadata": {
                    "device_name": "x-IMU3",
                    "serial_number": "6A33CA84",
                    "ip_address": "10.42.0.48",
                    "tcp_port": 7000,
                    "udp_send_port": 8048,
                    "udp_receive_port": 9000,
                    "rssi": 91,
                    "battery": 78,
                },
            }
        ]

        device = SimpleNamespace(**devices[0])
        assert await sensor.connect_sensor(device) is True
        connection = FakeConnection.instances[-1]
        assert connection.config == "udp-config"

        await sensor.identify(None)
        assert connection.commands == ['{"strobe":null}']
        assert await sensor.disconnect_sensor() is True
        assert connection.closed is True

    asyncio.run(scenario())


def test_stream_joins_vendor_messages_by_timestamp(monkeypatch):
    fake_ximu3 = SimpleNamespace(
        NetworkAnnouncement=FakeNetworkAnnouncement,
        Connection=FakeConnection,
    )
    monkeypatch.setattr(sensor_module, "ximu3", fake_ximu3)
    FakeConnection.instances.clear()
    sensor = XImu3Sensor()
    sensor.address = "6A33CA84"
    sensor.location = "DEFAULT"
    emitted = []
    sensor.register_listener("on_data", emitted.append)

    async def scenario():
        devices = await sensor.discover_connected(
            SimpleNamespace(cidr="10.42.0.1/24")
        )
        await sensor.connect_sensor(SimpleNamespace(**devices[0]))
        connection = FakeConnection.instances[-1]

        await sensor.setup(None)
        assert connection.commands == [
            '{"ahrs_message_type":0}',
            '{"inertial_message_rate_divisor":8}',
            '{"ahrs_message_rate_divisor":8}',
        ]
        inertial_callback = connection.callbacks["inertial"][1]
        quaternion_callback = connection.callbacks["quaternion"][1]

        inertial = SimpleNamespace(
            timestamp=1_000_000,
            accelerometer_x=1.0,
            accelerometer_y=2.0,
            accelerometer_z=3.0,
            gyroscope_x=4.0,
            gyroscope_y=5.0,
            gyroscope_z=6.0,
        )
        quaternion = SimpleNamespace(
            timestamp=1_000_000,
            w=1.0,
            x=0.1,
            y=0.2,
            z=0.3,
        )

        inertial_callback(inertial)
        quaternion_callback(quaternion)
        assert emitted == []

        await sensor.start_stream(None)
        quaternion_callback(quaternion)
        inertial_callback(inertial)
        assert len(emitted) == 1
        sample = emitted[0]
        assert sample.timestamp == 1_000_000
        assert sample.sampling_rate == 50
        assert sample.quat == (1.0, 0.1, 0.2, 0.3)
        assert sample.accel == pytest.approx((9.80665, 19.6133, 29.41995))
        assert sample.gyro == (4.0, 5.0, 6.0)
        assert sample.sample_type == "imu"

        await sensor.stop_stream(None)
        inertial_callback(inertial)
        quaternion_callback(quaternion)
        assert len(emitted) == 1
        assert connection.commands[-2:] == [
            '{"udp_data_messages_enabled":true}',
            '{"udp_data_messages_enabled":false}',
        ]

        callback_ids = [item[0] for item in connection.callbacks.values()]
        await sensor.disconnect_sensor()
        assert connection.removed_callbacks == callback_ids
        assert connection.closed is True

    asyncio.run(scenario())


def test_provision_reuses_identified_candidate_without_rebinding_announcement_port(
    monkeypatch,
):
    fake_ximu3 = SimpleNamespace(
        NetworkAnnouncement=FakeNetworkAnnouncement,
        Connection=FakeConnection,
    )
    monkeypatch.setattr(sensor_module, "ximu3", fake_ximu3)
    FakeNetworkAnnouncement.calls = 0
    FakeConnection.instances.clear()
    sensor = XImu3Sensor()
    network = SimpleNamespace(cidr="10.42.0.1/24")
    target = SimpleNamespace(
        ssid="nexus-n3-sensors",
        credentials=SimpleNamespace(password="test-password"),
        channel=36,
    )
    controls = SimpleNamespace(remote_access_point_disappeared=lambda: None)

    async def scenario():
        identified = await sensor.identify_candidate(network)
        provisioned = await sensor.provision(network, target, controls)

        assert provisioned == identified
        assert FakeNetworkAnnouncement.calls == 1
        assert FakeConnection.instances[-1].config == "udp-config"

    asyncio.run(scenario())
