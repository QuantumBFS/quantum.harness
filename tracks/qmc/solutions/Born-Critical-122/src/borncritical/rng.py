"""Order-independent random-number streams for reproducible scan cells."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import numpy as np


@dataclass(frozen=True)
class StreamKey:
    base_seed: int
    model: str
    size: int
    replica: int
    stream: str

    def __post_init__(self) -> None:
        if not 0 <= self.base_seed < 1 << 128:
            raise ValueError("base_seed must satisfy 0 <= base_seed < 2**128")
        if not self.model:
            raise ValueError("model must be non-empty")
        if self.size < 1:
            raise ValueError("size must be positive")
        if self.replica < 0:
            raise ValueError("replica must be non-negative")
        if not self.stream:
            raise ValueError("stream must be non-empty")

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            {
                "base_seed": self.base_seed,
                "model": self.model,
                "replica": self.replica,
                "size": self.size,
                "stream": self.stream,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.blake2b(
            self.canonical_bytes(),
            digest_size=16,
            person=b"borncritical-rng",
        ).hexdigest()


def seed_sequence(key: StreamKey) -> np.random.SeedSequence:
    digest = hashlib.blake2b(
        key.canonical_bytes(),
        digest_size=32,
        person=b"borncritical-rng",
    ).digest()
    digest_words = np.frombuffer(digest, dtype=">u4").astype(np.uint32)
    low = key.base_seed & ((1 << 64) - 1)
    high = key.base_seed >> 64
    entropy = [
        low & 0xFFFFFFFF,
        low >> 32,
        high & 0xFFFFFFFF,
        high >> 32,
        *(int(word) for word in digest_words),
    ]
    return np.random.SeedSequence(entropy)


def make_rng(key: StreamKey) -> np.random.Generator:
    """Return a PCG64DXSM generator determined only by ``key``."""

    return np.random.Generator(np.random.PCG64DXSM(seed_sequence(key)))


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def export_rng_state(rng: np.random.Generator) -> dict[str, Any]:
    return {
        "bit_generator": type(rng.bit_generator).__name__,
        "state": _jsonable(rng.bit_generator.state),
    }


def restore_rng_state(payload: dict[str, Any]) -> np.random.Generator:
    name = payload.get("bit_generator")
    state = payload.get("state")
    if not isinstance(name, str) or not isinstance(state, dict):
        raise ValueError("invalid RNG state payload")
    bit_generator_type = getattr(np.random, name, None)
    if bit_generator_type is None:
        raise ValueError(f"unsupported NumPy bit generator {name!r}")
    bit_generator = bit_generator_type()
    bit_generator.state = state
    return np.random.Generator(bit_generator)
