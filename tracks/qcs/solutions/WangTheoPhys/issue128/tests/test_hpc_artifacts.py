from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from trottercert.cubic_field import Cubic
from trottercert.hpc_artifacts import (
    coordinate_encode_terms,
    read_shard_gzip,
    sha256_file,
    write_manifest_atomic,
    write_shard_gzip,
)
from trottercert.local_commutators import CoordinateRegistry


def _fixture(order: tuple[tuple[int, int], ...]):
    registry = CoordinateRegistry()
    for coordinate in order:
        registry.site(coordinate)
    left = registry.site((0, 0))
    right = registry.site((1, 0))
    pauli = ((1 << left) | (1 << right), 1 << right)
    return registry, {pauli: Cubic(Fraction(1, 3), Fraction(-2, 5), 7)}


def test_coordinate_encoding_is_registry_independent() -> None:
    first = _fixture(((0, 0), (1, 0)))
    second = _fixture(((1, 0), (0, 0)))
    assert coordinate_encode_terms(*first) == coordinate_encode_terms(*second)


def test_canonical_gzip_and_manifest_are_deterministic(tmp_path: Path) -> None:
    registry, terms = _fixture(((0, 0), (1, 0)))
    payload = {
        "schema_version": 1,
        "kind": "test",
        "terms": coordinate_encode_terms(registry, terms),
    }
    first = tmp_path / "first.json.gz"
    second = tmp_path / "second.json.gz"
    write_shard_gzip(first, payload)
    write_shard_gzip(second, payload)
    assert first.read_bytes() == second.read_bytes()
    assert read_shard_gzip(first) == payload
    assert sha256_file(first) == sha256_file(second)

    manifest = tmp_path / "manifest.json"
    write_manifest_atomic(manifest, {"status": "complete", "count": 1})
    first_manifest = manifest.read_bytes()
    write_manifest_atomic(manifest, {"status": "complete", "count": 1})
    assert manifest.read_bytes() == first_manifest


def test_corrupted_gzip_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "shard.json.gz"
    write_shard_gzip(path, {"schema_version": 1, "terms": []})
    raw = bytearray(path.read_bytes())
    raw[-8] ^= 1
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="gzip JSON"):
        read_shard_gzip(path)
