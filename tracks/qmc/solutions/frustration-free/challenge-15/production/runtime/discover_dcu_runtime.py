#!/usr/bin/env python3
"""Fail-closed discovery for the reviewed Challenge 15 DCU SIF runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypeAlias


JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = (
    JSONScalar | list["JSONValue"] | Mapping[str, "JSONValue"]
)

LOCK_SCHEMA = "challenge15.dcu-runtime-lock.v1"
EXPECTED_SIF_REFERENCE = (
    "docker://image.sourcefind.cn:5000/dcu/admin/base/"
    "pytorch:2.4.1-ubuntu22.04-dtk25.04-py3.10"
)
EXPECTED_SIF_PATH = (
    "/public/home/jiangweiqi/challenge15/runtime/"
    "pytorch-2.4.1-ubuntu22.04-dtk25.04-py3.10.sif"
)
EXPECTED_SIF_SHA256 = (
    "528cad28775057afd7fabaebcbbdceff35bd7d887f6305d0e3d5484e9527aea6"
)
REPORT_PATH = (
    "/public/home/jiangweiqi/challenge15/probes/"
    "dtk-pytorch-runtime-report.txt"
)
PROBE_OUTPUT_PATH = (
    "/public/home/jiangweiqi/challenge15/probes/dtk-pytorch-probe.out"
)
PROBE_SOURCE_PATH = (
    "/public/home/jiangweiqi/challenge15/probes/dtk-pytorch-probe.py"
)
_HASH_CHUNK_BYTES = 1024 * 1024

_EXPECTED_PROBE_FACTS: dict[str, JSONValue] = {
    "python_version": "3.10",
    "python_abi": "cp310",
    "torch_version": "2.4.1",
    "torch_hip_version": "6.1.25065",
    "dtk_version": "25.04",
    "device_count": 1,
    "device_name": "BW",
    "complex128_matmul_dtype": "torch.complex128",
    "complex128_matmul_checksum_real": -600.77609644494885,
    "complex128_matmul_checksum_imag": -47.28697415611893,
    "seeded_repeat_equal": True,
    "complex_autograd_loss": 5.3125,
    "complex_autograd_grad": ["(2+4j)", "(-1+0.5j)"],
    "probe_status": "PASS",
}


def _validate_json_input(value: object, *, path: str) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite JSON numbers")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{path} keys must be strings")
            _validate_json_input(item, path=f"{path}.{key}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_input(item, path=f"{path}[{index}]")
        return
    if isinstance(value, tuple):
        raise ValueError(f"{path} JSON array must be a list, not tuple")
    raise ValueError(f"{path} contains unsupported value {type(value).__name__}")


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class RuntimeDiscovery:
    status: Literal["READY", "BLOCKED"]
    facts: Mapping[str, JSONValue]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not str or self.status not in {"READY", "BLOCKED"}:
            raise ValueError(f"invalid discovery status: {self.status!r}")
        _validate_json_input(self.facts, path="facts")
        if type(self.blockers) is not tuple or not all(
            type(blocker) is str for blocker in self.blockers
        ):
            raise ValueError("discovery blockers must be a tuple of strings")
        object.__setattr__(self, "facts", _freeze(dict(self.facts)))
        object.__setattr__(self, "blockers", tuple(self.blockers))


def _validate_frozen_json(value: object, *, path: str) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite JSON numbers")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{path} keys must be strings")
            _validate_frozen_json(item, path=f"{path}.{key}")
        return
    if type(value) is tuple:
        for index, item in enumerate(value):
            _validate_frozen_json(item, path=f"{path}[{index}]")
        return
    raise ValueError(
        f"{path} contains unsupported frozen value {type(value).__name__}"
    )


def _assert_exact_typed(actual: object, expected: object, *, path: str) -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            raise ValueError(f"{path} must be an object")
        actual_keys = set(actual)
        expected_keys = set(expected)
        if actual_keys != expected_keys:
            raise ValueError(
                f"{path} keys mismatch: expected {sorted(expected_keys)}, "
                f"got {sorted(actual_keys)}"
            )
        for key in expected:
            _assert_exact_typed(
                actual[key], expected[key], path=f"{path}.{key}"
            )
        return
    if type(expected) is list:
        if type(actual) is not list:
            raise ValueError(f"{path} JSON array must be a list")
        if len(actual) != len(expected):
            raise ValueError(f"{path} length mismatch")
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected, strict=True)
        ):
            _assert_exact_typed(
                actual_item, expected_item, path=f"{path}[{index}]"
            )
        return
    if type(expected) is tuple:
        if type(actual) is not tuple:
            raise ValueError(f"{path} frozen JSON array must be a tuple")
        if len(actual) != len(expected):
            raise ValueError(f"{path} length mismatch")
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected, strict=True)
        ):
            _assert_exact_typed(
                actual_item, expected_item, path=f"{path}[{index}]"
            )
        return
    if type(actual) is not type(expected):
        raise ValueError(
            f"{path} mismatch: expected type {type(expected).__name__}, "
            f"got {type(actual).__name__}"
        )
    if actual != expected:
        raise ValueError(f"{path} mismatch: expected {expected!r}, got {actual!r}")


def _validate_probe_facts(probe_facts: Mapping[str, object]) -> None:
    _validate_json_input(probe_facts, path="probe")
    actual_keys = set(probe_facts)
    expected_keys = set(_EXPECTED_PROBE_FACTS)
    missing = sorted(expected_keys - actual_keys)
    extra = sorted(actual_keys - expected_keys)
    if missing:
        raise ValueError(f"missing probe facts: {missing}")
    if extra:
        raise ValueError(f"extra probe facts: {extra}")
    _assert_exact_typed(probe_facts, _EXPECTED_PROBE_FACTS, path="probe")


def _read_descriptor(descriptor: int, size: int) -> bytes:
    return os.read(descriptor, size)


def _descriptor_snapshot(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _hash_regular_file_descriptor(path: Path) -> str:
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("cannot guarantee no-follow: os.O_NOFOLLOW unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"SIF artifact is not a regular file: {path}")
        digest = hashlib.sha256()
        bytes_read = 0
        while chunk := _read_descriptor(descriptor, _HASH_CHUNK_BYTES):
            if type(chunk) is not bytes:
                raise ValueError("descriptor reader returned non-bytes")
            bytes_read += len(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        if _descriptor_snapshot(after) != _descriptor_snapshot(before):
            raise ValueError(
                f"SIF path changed while hashing (descriptor metadata): {path}"
            )
        if bytes_read != after.st_size:
            raise ValueError(f"SIF size changed while hashing: {path}")
        path_after = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(path_after.st_mode)
            or _descriptor_snapshot(path_after) != _descriptor_snapshot(after)
        ):
            raise ValueError(f"SIF path changed while hashing: {path}")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _ready_facts(
    *, sif: Path, probe_facts: Mapping[str, object]
) -> dict[str, JSONValue]:
    return {
        "artifact": {
            "cached_path": str(sif),
            "reference": EXPECTED_SIF_REFERENCE,
            "sha256": EXPECTED_SIF_SHA256,
        },
        "compatibility_gates": {
            "full_nqs_smoke": "PENDING",
            "project_python_3_10": "PENDING",
        },
        "execution_constraints": {
            "apptainer_version": "1.3.4",
            "minimum_job_memory_gib": 32,
            "mount_mode": "temporary-sandbox-expansion",
            "squashfuse_available": False,
        },
        "runtime": {
            key: probe_facts[key]
            for key in (
                "python_version",
                "python_abi",
                "torch_version",
                "torch_hip_version",
                "dtk_version",
                "device_count",
                "device_name",
            )
        },
        "validation": {
            "job_id": 719032,
            "observations": {
                key: probe_facts[key]
                for key in (
                    "complex128_matmul_dtype",
                    "complex128_matmul_checksum_real",
                    "complex128_matmul_checksum_imag",
                    "seeded_repeat_equal",
                    "complex_autograd_loss",
                    "complex_autograd_grad",
                )
            },
            "probe_output_path": PROBE_OUTPUT_PATH,
            "probe_source_path": PROBE_SOURCE_PATH,
            "probe_status": probe_facts["probe_status"],
            "report_path": REPORT_PATH,
            "test_members": [
                "complex128_matmul",
                "complex_autograd",
                "seeded_replay",
            ],
        },
    }


def discover_runtime(
    *,
    sif: Path,
    sif_reference: str,
    probe_facts: Mapping[str, object],
) -> RuntimeDiscovery:
    """Validate the exact reviewed SIF and bounded-probe facts without mutation."""

    try:
        if str(sif) != EXPECTED_SIF_PATH:
            raise ValueError(
                f"SIF path mismatch: expected {EXPECTED_SIF_PATH!r}, got {str(sif)!r}"
            )
        if sif_reference != EXPECTED_SIF_REFERENCE:
            raise ValueError(
                "SIF reference mismatch: "
                f"expected {EXPECTED_SIF_REFERENCE!r}, got {sif_reference!r}"
            )
        artifact_hash = _hash_regular_file_descriptor(sif)
        if artifact_hash != EXPECTED_SIF_SHA256:
            raise ValueError(
                "SIF SHA256 mismatch: "
                f"expected {EXPECTED_SIF_SHA256}, got {artifact_hash}"
            )
        _validate_probe_facts(probe_facts)
        candidate = RuntimeDiscovery(
            "READY",
            _ready_facts(sif=sif, probe_facts=probe_facts),
            (),
        )
        _validate_ready_facts(candidate.facts)
    except (OSError, ValueError) as error:
        return RuntimeDiscovery("BLOCKED", {}, (str(error),))
    return candidate


def _validate_ready_facts(facts: Mapping[str, JSONValue]) -> None:
    try:
        _validate_frozen_json(facts, path="facts")
        expected = _freeze(
            _ready_facts(
                sif=Path(EXPECTED_SIF_PATH),
                probe_facts=_EXPECTED_PROBE_FACTS,
            )
        )
        _assert_exact_typed(facts, expected, path="facts")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"exact READY fact schema required: {error}") from error


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            _thaw(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_runtime_lock(discovery: RuntimeDiscovery, output: Path) -> None:
    """Publish a complete lock atomically, refusing BLOCKED or existing output."""

    if discovery.status != "READY":
        raise RuntimeError("runtime lock requires READY discovery")
    if discovery.blockers:
        raise ValueError("READY discovery cannot contain blockers")
    _validate_ready_facts(discovery.facts)
    payload: dict[str, JSONValue] = {
        "schema": LOCK_SCHEMA,
        "status": "READY",
        **dict(discovery.facts),
    }
    encoded = _canonical_json(payload)
    parent = output.parent
    fd, temporary_name = tempfile.mkstemp(
        dir=parent, prefix=f".{output.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sif", type=Path, required=True)
    parser.add_argument("--sif-reference", required=True)
    parser.add_argument("--probe-json", type=Path, required=True)
    parser.add_argument("--lock-output", type=Path)
    args = parser.parse_args()
    with args.probe_json.open("r", encoding="utf-8") as stream:
        probe_facts = json.load(stream)
    if not isinstance(probe_facts, dict):
        raise SystemExit("probe JSON must be an object")
    discovery = discover_runtime(
        sif=args.sif,
        sif_reference=args.sif_reference,
        probe_facts=probe_facts,
    )
    if args.lock_output is not None:
        write_runtime_lock(discovery, args.lock_output)
    print(
        _canonical_json(
            {
                "blockers": discovery.blockers,
                "facts": discovery.facts,
                "status": discovery.status,
            }
        ).decode("utf-8"),
        end="",
    )


if __name__ == "__main__":
    main()
