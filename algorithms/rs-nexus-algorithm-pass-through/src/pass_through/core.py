"""Pass-through algorithm implementation with batching."""

from __future__ import annotations

import base64
import time
from dataclasses import asdict, is_dataclass

from rs_nexus_plugin_sdk import AlgorithmBase
from rs_nexus_plugin_sdk.yaml_loader import load_yaml
from .core_schema import PassThroughResult


def _encode_bytes(value):
    return base64.b64encode(value).decode("ascii")


def _serialize(value):
    if isinstance(value, bytes):
        return _encode_bytes(value)
    if is_dataclass(value):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


class PassThroughAlgorithm(AlgorithmBase):
    """Batch samples and emit them as pass-through results."""

    name = "pass_through"

    def __init__(self, address, sampling_rate, input_parameters=None):
        config = load_yaml(self.yaml_path())
        super().__init__(config)
        self.address = address
        self.sampling_rate = sampling_rate

        params = (input_parameters or config.get("inputs", {}).get("parameters", {}))
        buffer_seconds = float(params.get("buffer_seconds", 5))
        batch_size = params.get("batch_size")
        if batch_size is None:
            effective_rate = int(sampling_rate or 1)
            batch_size = max(1, int(round(effective_rate * buffer_seconds)))
        self.batch_size = int(batch_size)
        self.max_interval_ms = int(params.get("max_interval_ms", int(buffer_seconds * 1000)))

        self._buffer = []
        self._last_emit = time.monotonic()

    def on_sample(self, sample):
        self._buffer.append(sample)

        now = time.monotonic()
        elapsed_ms = (now - self._last_emit) * 1000

        if len(self._buffer) >= self.batch_size or elapsed_ms >= self.max_interval_ms:
            payload = [_serialize(s) for s in self._buffer]
            result = PassThroughResult(
                address=self.address,
                algorithm_name=self.name,
                stage="REAL_TIME",
                sample_count=len(payload),
                samples=payload,
            )
            self.emit_result(result)
            self._buffer.clear()
            self._last_emit = now
