from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vmcrg_ref.artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    verified_promote_directory,
)


def test_canonical_json_hash_is_key_order_independent() -> None:
    left = sha256_bytes(canonical_json_bytes({"b": 2, "a": 1}))
    right = sha256_bytes(canonical_json_bytes({"a": 1, "b": 2}))
    assert left == right


def test_atomic_json_replaces_complete_document(tmp_path: Path) -> None:
    output = tmp_path / "record.json"
    atomic_write_json(output, {"old": True})
    atomic_write_json(output, {"new": [1, 2, 3]})
    assert json.loads(output.read_text(encoding="ascii")) == {"new": [1, 2, 3]}


def test_atomic_npz_round_trip_disallows_pickle(tmp_path: Path) -> None:
    output = tmp_path / "arrays.npz"
    atomic_write_npz(output, {"values": np.arange(5, dtype=np.float64)})
    with np.load(output, allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive["values"], np.arange(5, dtype=float))


def test_verified_promote_rejects_hash_mismatch(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "x.txt").write_text("actual", encoding="ascii")
    with pytest.raises(ValueError, match="hash mismatch"):
        verified_promote_directory(
            staging,
            tmp_path / "final",
            {"x.txt": "0" * 64},
        )
    assert staging.is_dir()
    assert not (tmp_path / "final").exists()


def test_verified_promote_refuses_nonempty_destination(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    source = staging / "x.txt"
    source.write_text("actual", encoding="ascii")
    final = tmp_path / "final"
    final.mkdir()
    (final / "keep.txt").write_text("keep", encoding="ascii")
    with pytest.raises(FileExistsError, match="nonempty"):
        verified_promote_directory(staging, final, {"x.txt": sha256_file(source)})
    assert (final / "keep.txt").read_text(encoding="ascii") == "keep"
