from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path

import pytest


EXPECTED_REFERENCE = (
    "docker://image.sourcefind.cn:5000/dcu/admin/base/"
    "pytorch:2.4.1-ubuntu22.04-dtk25.04-py3.10"
)


def _probe_facts() -> dict[str, object]:
    return {
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


@pytest.fixture
def sif(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from production.runtime import discover_dcu_runtime as runtime

    artifact = tmp_path / "runtime.sif"
    artifact.write_bytes((b"verified-sif-block-" * 100_000) + b"end")
    monkeypatch.setattr(runtime, "EXPECTED_SIF_PATH", str(artifact))
    monkeypatch.setattr(
        runtime,
        "EXPECTED_SIF_SHA256",
        hashlib.sha256(artifact.read_bytes()).hexdigest(),
    )
    return artifact


def test_runtime_discovery_returns_frozen_ready_facts_for_exact_sif(sif: Path):
    from production.runtime.discover_dcu_runtime import (
        LOCK_SCHEMA,
        discover_runtime,
    )

    before = sif.stat()
    result = discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )

    assert result.status == "READY"
    assert result.blockers == ()
    assert set(result.facts) == {
        "artifact",
        "compatibility_gates",
        "execution_constraints",
        "runtime",
        "validation",
    }
    assert result.facts["artifact"]["sha256"] == hashlib.sha256(
        sif.read_bytes()
    ).hexdigest()
    assert result.facts["runtime"] == {
        "python_version": "3.10",
        "python_abi": "cp310",
        "torch_version": "2.4.1",
        "torch_hip_version": "6.1.25065",
        "dtk_version": "25.04",
        "device_count": 1,
        "device_name": "BW",
    }
    assert result.facts["validation"]["job_id"] == 719032
    assert result.facts["validation"]["test_members"] == (
        "complex128_matmul",
        "complex_autograd",
        "seeded_replay",
    )
    assert result.facts["compatibility_gates"] == {
        "full_nqs_smoke": "PENDING",
        "project_python_3_10": "PENDING",
    }
    assert LOCK_SCHEMA == "challenge15.dcu-runtime-lock.v1"
    assert sif.stat() == before
    with pytest.raises(TypeError):
        result.facts["runtime"]["torch_version"] = "forged"
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = "BLOCKED"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "missing probe facts"),
        ("extra", "extra probe facts"),
        ("nonfinite", "finite JSON numbers"),
        ("wrong_runtime", "torch_version mismatch"),
        ("wrong_device_count", "device_count mismatch"),
        ("wrong_boolean_type", "seeded_repeat_equal mismatch"),
    ],
)
def test_runtime_discovery_blocks_invalid_probe_facts(
    sif: Path, mutation: str, message: str
):
    from production.runtime.discover_dcu_runtime import discover_runtime

    facts = _probe_facts()
    if mutation == "missing":
        del facts["torch_hip_version"]
    elif mutation == "extra":
        facts["unreviewed"] = "claim"
    elif mutation == "nonfinite":
        facts["complex_autograd_loss"] = float("nan")
    elif mutation == "wrong_runtime":
        facts["torch_version"] = "2.4.1+unverified"
    elif mutation == "wrong_device_count":
        facts["device_count"] = True
    elif mutation == "wrong_boolean_type":
        facts["seeded_repeat_equal"] = 1

    result = discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=facts,
    )

    assert result.status == "BLOCKED"
    assert result.facts == {}
    assert len(result.blockers) == 1
    assert message in result.blockers[0]


def test_runtime_discovery_blocks_missing_wrong_path_reference_and_hash(
    tmp_path: Path, sif: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    cases = []
    cases.append(
        runtime.discover_runtime(
            sif=tmp_path / "missing.sif",
            sif_reference=EXPECTED_REFERENCE,
            probe_facts=_probe_facts(),
        )
    )
    monkeypatch.setattr(runtime, "EXPECTED_SIF_PATH", str(tmp_path / "other.sif"))
    cases.append(
        runtime.discover_runtime(
            sif=sif,
            sif_reference=EXPECTED_REFERENCE,
            probe_facts=_probe_facts(),
        )
    )
    monkeypatch.setattr(runtime, "EXPECTED_SIF_PATH", str(sif))
    cases.append(
        runtime.discover_runtime(
            sif=sif,
            sif_reference="docker://unreviewed/runtime:latest",
            probe_facts=_probe_facts(),
        )
    )
    monkeypatch.setattr(runtime, "EXPECTED_SIF_SHA256", "0" * 64)
    cases.append(
        runtime.discover_runtime(
            sif=sif,
            sif_reference=EXPECTED_REFERENCE,
            probe_facts=_probe_facts(),
        )
    )

    for result in cases:
        assert result.status == "BLOCKED"
        assert result.facts == {}
        assert result.blockers


def test_runtime_lock_is_atomic_create_only_and_requires_ready(
    sif: Path, tmp_path: Path
):
    from production.runtime.discover_dcu_runtime import (
        RuntimeDiscovery,
        discover_runtime,
        write_runtime_lock,
    )

    output = tmp_path / "runtime-lock.json"
    blocked = RuntimeDiscovery("BLOCKED", {}, ("authentication required",))
    with pytest.raises(RuntimeError, match="READY"):
        write_runtime_lock(blocked, output)

    ready = discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    write_runtime_lock(ready, output)
    original = output.read_bytes()
    payload = json.loads(original)
    assert payload["schema"] == "challenge15.dcu-runtime-lock.v1"
    assert payload["status"] == "READY"
    assert original.endswith(b"\n")
    assert b"NaN" not in original
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []

    with pytest.raises(FileExistsError):
        write_runtime_lock(ready, output)
    assert output.read_bytes() == original
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_runtime_lock_revalidates_ready_facts_before_publication(tmp_path: Path):
    from production.runtime.discover_dcu_runtime import (
        RuntimeDiscovery,
        write_runtime_lock,
    )

    output = tmp_path / "runtime-lock.json"
    with pytest.raises(ValueError, match="finite JSON|exact READY fact schema"):
        forged = RuntimeDiscovery(
            "READY",
            {"runtime": {"torch_version": float("inf")}},
            (),
        )
        write_runtime_lock(forged, output)
    assert not output.exists()


def test_tracked_runtime_lock_is_canonical_and_keeps_compatibility_pending():
    from production.runtime.discover_dcu_runtime import (
        RuntimeDiscovery,
        write_runtime_lock,
    )

    lock = (
        Path(__file__).parents[1]
        / "production"
        / "runtime"
        / "dcu25.04-runtime-lock.json"
    )
    encoded = lock.read_bytes()
    payload = json.loads(encoded)
    assert payload["schema"] == "challenge15.dcu-runtime-lock.v1"
    assert payload["status"] == "READY"
    assert payload["artifact"] == {
        "cached_path": (
            "/public/home/jiangweiqi/challenge15/runtime/"
            "pytorch-2.4.1-ubuntu22.04-dtk25.04-py3.10.sif"
        ),
        "reference": EXPECTED_REFERENCE,
        "sha256": (
            "528cad28775057afd7fabaebcbbdceff35bd7d887f6305d0e3d5484e9527aea6"
        ),
    }
    assert payload["compatibility_gates"] == {
        "full_nqs_smoke": "PENDING",
        "project_python_3_10": "PENDING",
    }
    assert payload["validation"]["job_id"] == 719032
    assert encoded == (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()

    # Exercise the same strict publication validator without replacing the lock.
    discovery = RuntimeDiscovery(
        "READY",
        {
            key: value
            for key, value in payload.items()
            if key not in {"schema", "status"}
        },
        (),
    )
    with pytest.raises(FileExistsError):
        write_runtime_lock(discovery, lock)


def _mutable_ready_facts(sif: Path) -> dict[str, object]:
    from production.runtime import discover_dcu_runtime as runtime

    ready = runtime.discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    assert ready.status == "READY"
    return json.loads(runtime._canonical_json(ready.facts))


@pytest.mark.parametrize(
    "mutation",
    [
        "integer_as_float",
        "bool_as_int",
        "job_bool_as_int",
        "test_members_mapping",
        "test_members_string",
        "test_members_tuple",
        "gradient_tuple",
        "nested_extra",
        "nested_missing",
        "nested_nonfinite",
    ],
)
def test_runtime_lock_rejects_malformed_nested_ready_facts(
    sif: Path, tmp_path: Path, mutation: str
):
    from production.runtime.discover_dcu_runtime import (
        RuntimeDiscovery,
        write_runtime_lock,
    )

    facts = _mutable_ready_facts(sif)
    if mutation == "integer_as_float":
        facts["execution_constraints"]["minimum_job_memory_gib"] = 32.0
    elif mutation == "bool_as_int":
        facts["execution_constraints"]["squashfuse_available"] = 0
    elif mutation == "job_bool_as_int":
        facts["validation"]["job_id"] = True
    elif mutation == "test_members_mapping":
        facts["validation"]["test_members"] = {
            "0": "complex128_matmul",
            "1": "complex_autograd",
            "2": "seeded_replay",
        }
    elif mutation == "test_members_string":
        facts["validation"]["test_members"] = (
            "complex128_matmulcomplex_autogradseeded_replay"
        )
    elif mutation == "test_members_tuple":
        facts["validation"]["test_members"] = (
            "complex128_matmul",
            "complex_autograd",
            "seeded_replay",
        )
    elif mutation == "gradient_tuple":
        facts["validation"]["observations"]["complex_autograd_grad"] = (
            "(2+4j)",
            "(-1+0.5j)",
        )
    elif mutation == "nested_extra":
        facts["runtime"]["unreviewed"] = "claim"
    elif mutation == "nested_missing":
        del facts["validation"]["probe_status"]
    elif mutation == "nested_nonfinite":
        facts["validation"]["observations"][
            "complex128_matmul_checksum_real"
        ] = float("inf")

    output = tmp_path / f"{mutation}.json"
    with pytest.raises(ValueError):
        discovery = RuntimeDiscovery("READY", facts, ())
        write_runtime_lock(discovery, output)
    assert not output.exists()


def test_probe_rejects_tuple_for_json_array(sif: Path):
    from production.runtime.discover_dcu_runtime import discover_runtime

    facts = _probe_facts()
    facts["complex_autograd_grad"] = ("(2+4j)", "(-1+0.5j)")
    result = discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=facts,
    )
    assert result.status == "BLOCKED"
    assert "JSON array must be a list" in result.blockers[0]


def test_sif_hashing_rejects_symlink(
    sif: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    symlink = tmp_path / "linked-runtime.sif"
    symlink.symlink_to(sif)
    monkeypatch.setattr(runtime, "EXPECTED_SIF_PATH", str(symlink))
    result = runtime.discover_runtime(
        sif=symlink,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    assert result.status == "BLOCKED"
    assert result.facts == {}


def test_sif_hashing_rejects_path_swap_after_descriptor_open(
    sif: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    real_read = os.read
    replaced = False

    def swap_then_read(fd: int, size: int) -> bytes:
        nonlocal replaced
        if not replaced:
            replaced = True
            moved = sif.with_suffix(".original")
            sif.rename(moved)
            sif.write_bytes(b"replacement")
        return real_read(fd, size)

    monkeypatch.setattr(runtime, "_read_descriptor", swap_then_read)
    result = runtime.discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    assert result.status == "BLOCKED"
    assert "path changed while hashing" in result.blockers[0]


def test_sif_hashing_uses_bounded_descriptor_reads(
    sif: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    real_read = os.read
    requested_sizes: list[int] = []

    def recording_read(fd: int, size: int) -> bytes:
        requested_sizes.append(size)
        return real_read(fd, size)

    monkeypatch.setattr(runtime, "_HASH_CHUNK_BYTES", 4096)
    monkeypatch.setattr(runtime, "_read_descriptor", recording_read)
    result = runtime.discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    assert result.status == "READY"
    assert len(requested_sizes) > 2
    assert set(requested_sizes) == {4096}


def test_sif_hashing_rejects_special_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    directory = tmp_path / "not-a-regular-sif"
    directory.mkdir()
    monkeypatch.setattr(runtime, "EXPECTED_SIF_PATH", str(directory))
    result = runtime.discover_runtime(
        sif=directory,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    assert result.status == "BLOCKED"
    assert "regular file" in result.blockers[0]


def test_sif_hashing_fails_if_nofollow_is_unavailable(
    sif: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    monkeypatch.delattr(runtime.os, "O_NOFOLLOW")
    result = runtime.discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    assert result.status == "BLOCKED"
    assert "O_NOFOLLOW" in result.blockers[0]


def test_runtime_lock_cleans_temporary_file_when_publication_fails(
    sif: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from production.runtime import discover_dcu_runtime as runtime

    ready = runtime.discover_runtime(
        sif=sif,
        sif_reference=EXPECTED_REFERENCE,
        probe_facts=_probe_facts(),
    )
    output = tmp_path / "runtime-lock.json"

    def fail_link(source: Path, destination: Path) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr(runtime.os, "link", fail_link)
    with pytest.raises(OSError, match="injected publication failure"):
        runtime.write_runtime_lock(ready, output)
    assert not output.exists()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []
