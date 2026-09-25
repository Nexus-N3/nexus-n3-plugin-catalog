from __future__ import annotations

import asyncio
from types import SimpleNamespace

from nexus_n3_sensor_core_2.sensor import Core2Sensor


class FakeAdapter:
    def __init__(self):
        self.notify_calls = []
        self.unset_notify_calls = []

    async def set_notify_callback(self, client, uuid, callback, **kwargs):
        self.notify_calls.append((client, uuid, callback, kwargs))

    async def unset_notify_callback(self, client, uuid):
        self.unset_notify_calls.append((client, uuid))


def heart_rate_payload(value):
    return SimpleNamespace(
        schema="hr",
        output_name="hr",
        payload=SimpleNamespace(heart_rate=value),
    )


def test_consume_input_before_start_stores_pending_hr_without_writing():
    sensor = Core2Sensor()
    writes = []

    async def set_external_heart_rate(bpm):
        writes.append(bpm)
        return True

    sensor._set_external_heart_rate = set_external_heart_rate

    async def scenario():
        assert await sensor.consume_input("movesense", heart_rate_payload(72))

    asyncio.run(scenario())

    assert writes == []
    assert sensor._pending_heart_rate == 72


def test_consume_input_while_streaming_writes_external_hr():
    sensor = Core2Sensor()
    adapter = FakeAdapter()
    writes = []

    async def set_external_heart_rate(bpm):
        writes.append(bpm)
        return True

    sensor._set_external_heart_rate = set_external_heart_rate

    async def scenario():
        await sensor.start_stream(adapter)
        assert await sensor.consume_input("movesense", heart_rate_payload(73))

    asyncio.run(scenario())

    assert writes == [73]
    assert sensor._pending_heart_rate is None


def test_consume_input_during_stop_does_not_generate_another_write():
    sensor = Core2Sensor()
    adapter = FakeAdapter()
    disable_started = asyncio.Event()
    allow_disable_to_finish = asyncio.Event()
    writes = []

    async def set_external_heart_rate(bpm):
        writes.append(bpm)
        if bpm is None:
            disable_started.set()
            await allow_disable_to_finish.wait()
        return True

    sensor._set_external_heart_rate = set_external_heart_rate

    async def scenario():
        await sensor.start_stream(adapter)
        sensor._external_hr_active = True

        stop_task = asyncio.create_task(sensor.stop_stream(adapter))
        await disable_started.wait()

        assert await sensor.consume_input("movesense", heart_rate_payload(74))
        assert writes == [None]

        allow_disable_to_finish.set()
        await stop_task

    asyncio.run(scenario())

    assert sensor._pending_heart_rate == 74


def test_pending_hr_is_applied_on_next_start():
    sensor = Core2Sensor()
    adapter = FakeAdapter()
    writes = []

    async def set_external_heart_rate(bpm):
        writes.append(bpm)
        return True

    sensor._set_external_heart_rate = set_external_heart_rate

    async def scenario():
        assert await sensor.consume_input("movesense", heart_rate_payload(75))
        await sensor.start_stream(adapter)

    asyncio.run(scenario())

    assert writes == [75]
    assert sensor._pending_heart_rate is None
