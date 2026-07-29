from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

import h5py
import numpy as np
import pytest

import long_range_percolation.artifacts as artifacts
from long_range_percolation.artifacts import (
    ArtifactIntegrityError,
    load_verified_trajectory,
    publish_batch_manifest,
    publish_trajectory as _publish_trajectory_api,
    reconstruct_progress,
)
from long_range_percolation.counter_rng import (
    RNG_VERSION,
    StreamIdentity,
    derive_stream_material,
)
from long_range_percolation.trajectory import (
    TrajectoryRequest,
    TrajectoryResult,
    request_digest,
)


HEX = {
    "source_revision": "1" * 40,
    "uv_lock_sha256": "2" * 64,
    "runtime_capability_sha256": "3" * 64,
    "analysis_plan_sha256": "not-created-pre-pilot",
    "rng_sha256": "4" * 64,
}
KERNEL_BYTES = b"challenge-194-kernel-fixture-v1"
KERNEL_SHA256 = hashlib.sha256(KERNEL_BYTES).hexdigest()


@pytest.fixture
def sample() -> tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]]:
    request = TrajectoryRequest(
        length=8,
        sigma=1.25,
        sigma_grid_id="sigma-grid-a",
        kappas=np.asarray([0.0, 0.125, 0.5], dtype=np.float64),
        master_seed=42,
        phase="pilot",
        replica=7,
        kernel_sha256=KERNEL_SHA256,
    )
    result = TrajectoryResult(
        request_sha256=request_digest(request),
        observables=np.arange(30, dtype=np.float64).reshape(3, 10) / 7.0,
        terminal_counters=np.arange(16, dtype=np.uint32).reshape(4, 4),
        draw_counts=np.arange(12, dtype=np.uint64).reshape(4, 3),
        event_count=19,
        duplicate_count=3,
        hash_diagnostics=np.arange(5, dtype=np.uint64),
    )
    provenance: dict[str, object] = {
        **HEX,
        "clean_tree": True,
        "conversion_version": "challenge-194-artifact-conversion-v1",
        "rng_version": RNG_VERSION,
    }
    return request, result, provenance


def expected(request: TrajectoryRequest) -> dict[str, str]:
    return {
        **HEX,
        "request_sha256": request_digest(request),
        "kernel_sha256": request.kernel_sha256,
        "conversion_version": "challenge-194-artifact-conversion-v1",
        "rng_version": RNG_VERSION,
    }


def _write_upstream_metadata(
    run_dir: Path,
    request: TrajectoryRequest,
    provenance: dict[str, object],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    kernel_dir = run_dir / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "kernel.bin").write_bytes(KERNEL_BYTES)
    documents = {
        "request.json": {
            "kernel_sha256": request.kernel_sha256,
            "request_sha256": request_digest(request),
            "schema_version": "test-request-v1",
        },
        "environment.json": {
            "clean_tree": provenance["clean_tree"],
            "conversion_version": provenance["conversion_version"],
            "rng_version": provenance["rng_version"],
            "runtime_capability_sha256": provenance[
                "runtime_capability_sha256"
            ],
            "schema_version": "test-environment-v1",
            "source_revision": provenance["source_revision"],
            "uv_lock_sha256": provenance["uv_lock_sha256"],
        },
        "seed-manifest.json": {
            "rng_sha256": provenance["rng_sha256"],
            "schema_version": "test-seed-manifest-v1",
        },
        "capability.json": {
            "runtime_capability_sha256": provenance[
                "runtime_capability_sha256"
            ],
            "schema_version": "test-capability-v1",
        },
        "manifest.json": {
            "analysis_plan_sha256": provenance["analysis_plan_sha256"],
            "schema_version": "test-run-manifest-v1",
            "source_revision": provenance["source_revision"],
        },
    }
    for name, document in documents.items():
        (run_dir / name).write_bytes(artifacts._canonical_json_bytes(document))


def publish_trajectory(
    run_dir: Path,
    request: TrajectoryRequest,
    result: TrajectoryResult,
    provenance: dict[str, object],
) -> Path:
    if not run_dir.is_symlink() and (
        not run_dir.exists() or not any(run_dir.iterdir())
    ):
        _write_upstream_metadata(run_dir, request, provenance)
    return _publish_trajectory_api(run_dir, request, result, provenance)


def test_trajectory_round_trip_preserves_complete_resampling_unit(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, result, provenance = sample
    path = publish_trajectory(tmp_path, request, result, provenance)
    loaded = load_verified_trajectory(path, expected(request))
    np.testing.assert_array_equal(loaded.observables, result.observables)
    np.testing.assert_array_equal(loaded.terminal_counters, result.terminal_counters)
    np.testing.assert_array_equal(loaded.draw_counts, result.draw_counts)
    np.testing.assert_array_equal(loaded.hash_diagnostics, result.hash_diagnostics)
    assert (loaded.event_count, loaded.duplicate_count) == (19, 3)
    with pytest.raises(FileExistsError):
        publish_trajectory(tmp_path, request, result, provenance)


def test_hdf5_schema_is_exact_and_little_endian(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, provenance = sample
    path = publish_trajectory(tmp_path, *sample)
    with h5py.File(path, "r") as stream:
        assert set(stream) == {"request", "result", "rng"}
        assert set(stream["request"]) == {"kappas"}
        assert set(stream["result"]) == {
            "draw_counts",
            "hash_diagnostics",
            "observables",
            "terminal_counters",
        }
        assert set(stream["rng"]) == {
            "initial_counters",
            "key_material_sha256",
            "keys",
        }
        assert stream["request/kappas"].shape == (3,)
        assert stream["result/observables"].shape == (3, 10)
        assert stream["result/terminal_counters"].shape == (4, 4)
        assert stream["result/draw_counts"].shape == (4, 3)
        assert stream["result/hash_diagnostics"].shape == (5,)
        assert stream["rng/initial_counters"].shape == (4, 4)
        assert stream["rng/keys"].shape == (4, 2)
        assert stream["rng/key_material_sha256"].shape == (4,)
        assert stream["request/kappas"].dtype.str == "<f8"
        assert stream["result/observables"].dtype.str == "<f8"
        assert stream["result/terminal_counters"].dtype.str == "<u4"
        assert stream["result/draw_counts"].dtype.str == "<u8"
        assert stream["result/hash_diagnostics"].dtype.str == "<u8"
        attrs = dict(stream.attrs)
        assert attrs["schema_version"] == artifacts.TRAJECTORY_SCHEMA
        assert attrs["rng_version"] == RNG_VERSION
        assert attrs["conversion_version"] == provenance["conversion_version"]
        assert attrs["request_sha256"] == request_digest(request)
        assert attrs["kernel_sha256"] == request.kernel_sha256
        assert attrs["clean_tree"] == np.uint8(1)
        for key, value in HEX.items():
            assert attrs[key] == value
        assert attrs["event_count"] == np.uint64(19)
        assert attrs["duplicate_count"] == np.uint64(3)
        assert attrs["length"] == np.uint64(8)
        assert attrs["master_seed"] == np.uint64(42)
        assert attrs["replica"] == np.uint64(7)
        assert attrs["phase"] == "pilot"
        assert attrs["sigma_grid_id"] == "sigma-grid-a"
        assert attrs["sigma"] == np.float64(1.25)
        expected_material = [
            derive_stream_material(
                StreamIdentity(
                    master_seed=request.master_seed,
                    phase=request.phase,
                    length=request.length,
                    sigma_grid_id=request.sigma_grid_id,
                    replica=request.replica,
                    stream_id=index,
                )
            )
            for index in range(4)
        ]
        np.testing.assert_array_equal(
            stream["rng/initial_counters"],
            np.stack([item.initial_counter for item in expected_material]),
        )
        np.testing.assert_array_equal(
            stream["rng/keys"], np.stack([item.key for item in expected_material])
        )
        assert list(stream["rng/key_material_sha256"].asstr()[:]) == [
            item.material_sha256 for item in expected_material
        ]
    sidecar = json.loads(path.with_suffix(".sha256.json").read_text())
    payload = path.read_bytes()
    assert sidecar == {
        "artifact_size": len(payload),
        "schema_version": artifacts.TRAJECTORY_DIGEST_SCHEMA,
        "trajectory_id": request_digest(request),
        "trajectory_sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_deterministic_regeneration_is_byte_identical(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    first = publish_trajectory(tmp_path / "a", *sample)
    second = publish_trajectory(tmp_path / "b", *sample)
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".sha256.json").read_bytes() == second.with_suffix(
        ".sha256.json"
    ).read_bytes()


@pytest.mark.parametrize(
    "boundary",
    (
        "_flush_hdf5",
        "_fsync_file",
        "_semantic_reload",
        "_hash_descriptor",
        "_replace",
    ),
)
def test_pre_rename_crashes_leave_detectable_partial_without_final(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    boundary: str,
):
    request, _, _ = sample
    original = getattr(artifacts, boundary)

    def crash(*args, **kwargs):
        if (
            boundary == "_hash_descriptor"
            and len(args) >= 2
            and args[1] != "trajectory"
        ):
            return original(*args, **kwargs)
        raise OSError(f"crash at {boundary}")

    monkeypatch.setattr(artifacts, boundary, crash)
    with pytest.raises((OSError, ArtifactIntegrityError)):
        publish_trajectory(tmp_path, *sample)
    final = tmp_path / "trajectories" / f"trajectory-{request_digest(request)}.h5"
    assert not final.exists()
    assert list((tmp_path / "trajectories").glob("*.partial"))
    assert list((tmp_path / "trajectories").glob("*.intent"))
    monkeypatch.setattr(artifacts, boundary, original)
    with pytest.raises(ArtifactIntegrityError, match="intent"):
        reconstruct_progress(tmp_path, expected(request))


@pytest.mark.parametrize("failing_call", (1, 2, 3))
def test_directory_fsync_crashes_fail_closed_at_every_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    failing_call: int,
):
    request, _, _ = sample
    calls = 0
    original = artifacts._fsync_directory

    def crash_at_boundary(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == failing_call:
            raise OSError("directory fsync crash")
        original(path)

    monkeypatch.setattr(artifacts, "_fsync_directory", crash_at_boundary)
    with pytest.raises(OSError, match="directory fsync crash"):
        publish_trajectory(tmp_path, *sample)
    final = tmp_path / "trajectories" / f"trajectory-{request_digest(request)}.h5"
    assert final.exists() is (failing_call >= 2)
    assert list((tmp_path / "trajectories").glob("*.intent"))
    with pytest.raises(ArtifactIntegrityError, match="intent"):
        reconstruct_progress(tmp_path, expected(request))


def test_existing_valid_file_is_not_removed_or_overwritten_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    path = publish_trajectory(tmp_path, *sample)
    before = path.read_bytes()
    monkeypatch.setattr(
        artifacts, "_replace", lambda *_: (_ for _ in ()).throw(OSError("forbidden"))
    )
    with pytest.raises(FileExistsError):
        publish_trajectory(tmp_path, *sample)
    assert path.read_bytes() == before


def _publish_valid_run(
    root: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
) -> tuple[Path, Path, dict[str, str]]:
    request, _, _ = sample
    trajectory = publish_trajectory(root, *sample)
    batch = publish_batch_manifest(root, "batch-0001", [trajectory])
    return trajectory, batch, expected(request)


def test_batch_manifest_and_progress_are_canonical_and_reconstructible(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    trajectory, batch, hashes = _publish_valid_run(tmp_path, sample)
    batch_document = json.loads(batch.read_text())
    assert batch.read_bytes() == (
        json.dumps(
            batch_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
        + b"\n"
    )
    assert batch_document["members"] == [
        {
            "path": f"trajectories/{trajectory.name}",
            "trajectory_id": sample[1].request_sha256,
            "trajectory_sha256": hashlib.sha256(trajectory.read_bytes()).hexdigest(),
        }
    ]
    first = reconstruct_progress(tmp_path, hashes)
    progress_path = tmp_path / "progress.json"
    original = progress_path.read_bytes()
    progress_path.unlink()
    second = reconstruct_progress(tmp_path, hashes)
    assert second == first
    assert progress_path.read_bytes() == original
    assert first["trajectory_count"] == 1
    assert first["batch_count"] == 1


@pytest.mark.parametrize(
    "mutation",
    (
        "truncate",
        "dataset",
        "request",
        "source",
        "dirty",
        "lock",
        "kernel",
        "analysis",
        "rng",
    ),
)
def test_corrupt_or_stale_trajectory_is_rejected(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    mutation: str,
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    hashes = expected(request)
    if mutation == "truncate":
        path.write_bytes(path.read_bytes()[:128])
    elif mutation == "dataset":
        with h5py.File(path, "r+") as stream:
            stream["result/observables"][0, 0] += 1.0
    else:
        attribute = {
            "request": "request_sha256",
            "source": "source_revision",
            "dirty": "clean_tree",
            "lock": "uv_lock_sha256",
            "kernel": "kernel_sha256",
            "analysis": "analysis_plan_sha256",
            "rng": "rng_sha256",
        }[mutation]
        with h5py.File(path, "r+") as stream:
            stream.attrs[attribute] = np.uint8(0) if mutation == "dirty" else (
                "0" * (40 if mutation == "source" else 64)
            )
    with pytest.raises(ArtifactIntegrityError):
        load_verified_trajectory(path, hashes)


@pytest.mark.parametrize("kind", ("unknown", "partial", "intent", "symlink"))
def test_reconstruction_rejects_unknown_stale_or_symlink_entries(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    kind: str,
):
    _, _, hashes = _publish_valid_run(tmp_path, sample)
    trajectories = tmp_path / "trajectories"
    if kind == "unknown":
        (trajectories / "unknown.bin").write_bytes(b"x")
    elif kind == "partial":
        (trajectories / ".trajectory-x.1.a.partial").write_bytes(b"x")
    elif kind == "intent":
        (trajectories / ".trajectory-x.1.a.intent").write_bytes(b"{}\n")
    else:
        (trajectories / f"trajectory-{'0' * 64}.h5").symlink_to(
            next(trajectories.glob("*.h5"))
        )
    with pytest.raises(ArtifactIntegrityError):
        reconstruct_progress(tmp_path, hashes)


def test_reconstruction_rejects_duplicate_id_missing_member_and_unbatched_member(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    trajectory, batch, hashes = _publish_valid_run(tmp_path, sample)
    duplicate = trajectory.with_name(f"trajectory-{'f' * 64}.h5")
    duplicate.write_bytes(trajectory.read_bytes())
    duplicate_sidecar = json.loads(
        trajectory.with_suffix(".sha256.json").read_text()
    )
    duplicate_sidecar["trajectory_id"] = "f" * 64
    duplicate.with_suffix(".sha256.json").write_bytes(
        artifacts._canonical_json_bytes(duplicate_sidecar)
    )
    with pytest.raises(ArtifactIntegrityError, match="duplicate"):
        reconstruct_progress(tmp_path, hashes)
    duplicate.unlink()
    duplicate.with_suffix(".sha256.json").unlink()

    document = json.loads(batch.read_text())
    document["members"][0]["path"] = "trajectories/trajectory-" + "e" * 64 + ".h5"
    batch.write_bytes(artifacts._canonical_json_bytes(document))
    with pytest.raises(ArtifactIntegrityError, match="missing|stale"):
        reconstruct_progress(tmp_path, hashes)

    batch.unlink()
    with pytest.raises(ArtifactIntegrityError, match="manifest"):
        reconstruct_progress(tmp_path, hashes)


def test_batch_publication_rejects_missing_duplicate_foreign_and_unsafe_ids(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    path = publish_trajectory(tmp_path, *sample)
    with pytest.raises(ArtifactIntegrityError):
        publish_batch_manifest(tmp_path, "batch-1", [path, path])
    with pytest.raises(ArtifactIntegrityError):
        publish_batch_manifest(tmp_path, "batch-1", [tmp_path / "missing.h5"])
    with pytest.raises(ValueError):
        publish_batch_manifest(tmp_path, "../escape", [path])
    foreign = tmp_path.parent / path.name
    foreign.write_bytes(path.read_bytes())
    with pytest.raises(ArtifactIntegrityError):
        publish_batch_manifest(tmp_path, "batch-1", [foreign])


def test_concurrent_trajectory_publication_never_clobbers(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    _write_upstream_metadata(tmp_path, sample[0], sample[2])

    def publish() -> Path:
        return _publish_trajectory_api(tmp_path, *sample)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish) for _ in range(2)]
    outcomes = [future.exception() for future in futures]
    assert sum(error is None for error in outcomes) == 1
    assert sum(isinstance(error, FileExistsError) for error in outcomes) == 1
    path = next((tmp_path / "trajectories").glob("*.h5"))
    load_verified_trajectory(path, expected(sample[0]))


def test_concurrent_batch_publication_never_clobbers(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    path = publish_trajectory(tmp_path, *sample)

    def publish() -> Path:
        return publish_batch_manifest(tmp_path, "batch-1", [path])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish) for _ in range(2)]
    outcomes = [future.exception() for future in futures]
    assert sum(error is None for error in outcomes) == 1
    assert sum(isinstance(error, FileExistsError) for error in outcomes) == 1


def test_run_and_managed_directories_must_not_be_symlinks(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ArtifactIntegrityError, match="symlink"):
        publish_trajectory(alias, *sample)
    root = tmp_path / "root"
    _write_upstream_metadata(root, sample[0], sample[2])
    (root / "trajectories").symlink_to(real, target_is_directory=True)
    with pytest.raises(ArtifactIntegrityError, match="symlink"):
        publish_trajectory(root, *sample)


def _refresh_digest(path: Path) -> None:
    payload = path.read_bytes()
    path.with_suffix(".sha256.json").write_bytes(
        artifacts._canonical_json_bytes(
            {
                "artifact_size": len(payload),
                "schema_version": artifacts.TRAJECTORY_DIGEST_SCHEMA,
                "trajectory_id": path.stem.removeprefix("trajectory-"),
                "trajectory_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    )


def test_hash_and_hdf5_semantics_use_the_same_open_inode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    hostile = tmp_path / "hostile.h5"
    shutil.copyfile(path, hostile)
    with h5py.File(hostile, "r+") as stream:
        stream["result/observables"][0, 0] = 999.0
    original_hash = artifacts._hash_descriptor
    swapped = False

    def hash_then_swap(descriptor: int, description: str) -> tuple[str, int]:
        nonlocal swapped
        result = original_hash(descriptor, description)
        if description == "trajectory" and not swapped:
            swapped = True
            os.replace(hostile, path)
        return result

    monkeypatch.setattr(artifacts, "_hash_descriptor", hash_then_swap)
    with pytest.raises(ArtifactIntegrityError, match="identity|mutat|digest"):
        load_verified_trajectory(path, expected(request))
    assert swapped


@pytest.mark.parametrize("kind", ("sidecar", "manifest"))
@pytest.mark.parametrize("stage", ("after-read", "after-parse", "after-validation"))
@pytest.mark.parametrize("replacement_kind", ("identical", "different"))
def test_json_semantics_bind_each_boundary_to_path_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    kind: str,
    stage: str,
    replacement_kind: str,
):
    trajectory, batch, hashes = _publish_valid_run(tmp_path, sample)
    target = trajectory.with_suffix(".sha256.json") if kind == "sidecar" else batch
    replacement = tmp_path.parent / f"{tmp_path.name}-replacement-{kind}.json"
    replacement.write_bytes(
        target.read_bytes()
        if replacement_kind == "identical"
        else artifacts._canonical_json_bytes({"different_inode": True})
    )
    original_inode = target.stat().st_ino
    original_read = artifacts._read_descriptor_bounded
    original_loads = artifacts.json.loads
    original_canonical = artifacts._canonical_json_bytes
    original_stable = artifacts._require_stable_descriptor
    expected_description = (
        "trajectory digest sidecar" if kind == "sidecar" else "batch manifest"
    )
    armed = False
    swapped = False

    def swap() -> None:
        nonlocal swapped
        assert not swapped
        os.replace(replacement, target)
        swapped = True

    def read_then_swap(
        descriptor: int,
        maximum_size: int,
        description: str,
    ) -> bytes:
        nonlocal armed
        payload = original_read(descriptor, maximum_size, description)
        if description == expected_description:
            armed = True
            if stage == "after-read":
                swap()
        return payload

    def loads_then_swap(payload: bytes):
        document = original_loads(payload)
        if armed and stage == "after-parse" and not swapped:
            swap()
        return document

    def validate_then_swap(document: object) -> bytes:
        payload = original_canonical(document)
        if armed and stage == "after-validation" and not swapped:
            swap()
        return payload

    def ignore_descriptor_metadata_swap(
        descriptor: int,
        original: os.stat_result,
        description: str,
    ) -> os.stat_result:
        if description == expected_description:
            return os.fstat(descriptor)
        return original_stable(descriptor, original, description)

    monkeypatch.setattr(artifacts, "_read_descriptor_bounded", read_then_swap)
    monkeypatch.setattr(artifacts.json, "loads", loads_then_swap)
    monkeypatch.setattr(artifacts, "_canonical_json_bytes", validate_then_swap)
    monkeypatch.setattr(
        artifacts, "_require_stable_descriptor", ignore_descriptor_metadata_swap
    )
    with pytest.raises(ArtifactIntegrityError, match="identity"):
        if kind == "sidecar":
            load_verified_trajectory(trajectory, hashes)
        else:
            reconstruct_progress(tmp_path, hashes)
    assert swapped
    assert not replacement.exists()
    assert target.stat().st_ino != original_inode


@pytest.mark.parametrize("indirection", ("external-link", "vds", "external-storage"))
def test_hdf5_storage_indirection_is_rejected_before_external_data_can_govern(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    indirection: str,
):
    request, result, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    external_h5 = tmp_path / "external.h5"
    external_raw = tmp_path / "external.raw"
    if indirection in {"external-link", "vds"}:
        with h5py.File(external_h5, "w") as stream:
            stream.create_dataset("observables", data=result.observables)
    with h5py.File(path, "r+") as stream:
        del stream["result/observables"]
        if indirection == "external-link":
            stream["result"]["observables"] = h5py.ExternalLink(
                str(external_h5), "observables"
            )
        elif indirection == "vds":
            layout = h5py.VirtualLayout(shape=(3, 10), dtype="<f8")
            layout[:] = h5py.VirtualSource(
                str(external_h5), "observables", shape=(3, 10)
            )
            stream["result"].create_virtual_dataset("observables", layout)
        else:
            dataset = stream["result"].create_dataset(
                "observables",
                shape=(3, 10),
                dtype="<f8",
                external=[(str(external_raw), 0, h5py.h5f.UNLIMITED)],
            )
            dataset[...] = result.observables
    _refresh_digest(path)
    if indirection in {"external-link", "vds"}:
        with h5py.File(external_h5, "r+") as stream:
            stream["observables"][0, 0] = 777.0
    else:
        with external_raw.open("r+b") as stream:
            stream.seek(0)
            stream.write(np.float64(777.0).tobytes())
    with pytest.raises(ArtifactIntegrityError, match="link|virtual|external|storage"):
        load_verified_trajectory(path, expected(request))


def test_hdf5_soft_link_and_unexpected_object_are_rejected(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    for name, mutate in (
        (
            "soft",
            lambda stream: stream.__setitem__(
                "unexpected", h5py.SoftLink("/result/observables")
            ),
        ),
        ("object", lambda stream: stream.create_group("unexpected")),
    ):
        root = tmp_path / name
        path = publish_trajectory(root, *sample)
        with h5py.File(path, "r+") as stream:
            mutate(stream)
        _refresh_digest(path)
        with pytest.raises(ArtifactIntegrityError, match="link|tree|membership"):
            load_verified_trajectory(path, expected(request))


def test_hostile_final_installed_between_precheck_and_install_is_never_clobbered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    hostile = b"hostile-winner-must-survive"
    original = artifacts._replace

    def install_hostile_then_continue(partial: Path, final: Path) -> None:
        final.write_bytes(hostile)
        original(partial, final)

    monkeypatch.setattr(artifacts, "_replace", install_hostile_then_continue)
    with pytest.raises((FileExistsError, ArtifactIntegrityError)):
        publish_trajectory(tmp_path, *sample)
    final = (
        tmp_path
        / "trajectories"
        / f"trajectory-{request_digest(request)}.h5"
    )
    assert final.read_bytes() == hostile


def test_installed_trajectory_inode_is_rehashed_before_staged_link_is_removed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    original = artifacts._install_no_clobber

    def install_then_mutate(source: Path, destination: Path) -> None:
        original(source, destination)
        if destination.suffix == ".h5":
            with destination.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"hostile!")

    monkeypatch.setattr(artifacts, "_install_no_clobber", install_then_mutate)
    with pytest.raises(ArtifactIntegrityError, match="digest|parse|HDF5"):
        publish_trajectory(tmp_path, *sample)
    assert list((tmp_path / "trajectories").glob("*.intent"))


def test_installed_batch_inode_bytes_are_verified_before_partial_removal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    trajectory = publish_trajectory(tmp_path, *sample)
    original = artifacts.os.link

    def link_then_mutate(
        source: Path,
        destination: Path,
        *,
        follow_symlinks: bool = True,
    ) -> None:
        original(source, destination, follow_symlinks=follow_symlinks)
        if str(destination).endswith("batch-hostile.json"):
            Path(destination).write_bytes(b'{"hostile":true}\n')

    monkeypatch.setattr(artifacts.os, "link", link_then_mutate)
    with pytest.raises(ArtifactIntegrityError, match="installed|bytes|canonical"):
        publish_batch_manifest(tmp_path, "hostile", [trajectory])
    assert (tmp_path / "batches" / "batch-hostile.json").read_bytes() == (
        b'{"hostile":true}\n'
    )


def test_publish_json_rejects_oversized_document_before_any_filesystem_output(
    tmp_path: Path,
):
    final = tmp_path / "batch-too-large.json"
    document = {
        "batch_id": "too-large",
        "members": [],
        "padding": "x" * artifacts.MAX_JSON_BYTES,
        "schema_version": artifacts.BATCH_SCHEMA,
    }
    with pytest.raises(ArtifactIntegrityError, match="size|limit|large"):
        artifacts._publish_json_once(
            final, document, artifacts.BATCH_SCHEMA
        )
    assert not final.exists()
    assert list(tmp_path.iterdir()) == []


def test_batch_member_limit_rejects_before_iteration_or_final_creation(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    trajectory = publish_trajectory(tmp_path, *sample)

    class OverLimitSequence(Sequence[Path]):
        def __len__(self) -> int:
            return 4097

        def __getitem__(self, index: int) -> Path:
            raise AssertionError("over-limit sequence was iterated")

    final = tmp_path / "batches" / "batch-too-many.json"
    with pytest.raises(ArtifactIntegrityError, match="member|limit"):
        publish_batch_manifest(
            tmp_path,
            "too-many",
            OverLimitSequence(),  # type: ignore[arg-type]
        )
    assert not final.exists()
    assert trajectory.exists()


@pytest.mark.parametrize(
    "parser_error",
    (
        RecursionError("nested"),
        OverflowError("overflow"),
        ValueError("malformed"),
    ),
)
def test_json_parser_failures_are_normalized_without_publishing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    parser_error: Exception,
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)

    def fail_parser(payload: bytes):
        raise parser_error

    monkeypatch.setattr(artifacts.json, "loads", fail_parser)
    with pytest.raises(ArtifactIntegrityError, match="JSON|parse|read"):
        load_verified_trajectory(path, expected(request))


def test_json_memory_error_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)

    def fail_parser(payload: bytes):
        raise MemoryError("allocation refused")

    monkeypatch.setattr(artifacts.json, "loads", fail_parser)
    with pytest.raises(MemoryError, match="allocation refused"):
        load_verified_trajectory(path, expected(request))


def test_post_first_hdf5_verification_mutation_keeps_intent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    final = (
        tmp_path
        / "trajectories"
        / f"trajectory-{request_digest(request)}.h5"
    )
    original = artifacts._load_hdf5_verified
    final_verifications = 0

    def verify_then_mutate(path: Path, *args, **kwargs):
        nonlocal final_verifications
        if path == final:
            final_verifications += 1
        result = original(path, *args, **kwargs)
        if path == final and final_verifications == 1:
            with path.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"after-first-verify")
        return result

    monkeypatch.setattr(artifacts, "_load_hdf5_verified", verify_then_mutate)
    with pytest.raises(ArtifactIntegrityError, match="digest|HDF5|parse"):
        publish_trajectory(tmp_path, *sample)
    assert final_verifications >= 2
    assert final.read_bytes().startswith(b"after-first-verify")
    assert list((tmp_path / "trajectories").glob("*.intent"))


def test_hdf5_mutation_during_sidecar_verification_keeps_intent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    final = (
        tmp_path
        / "trajectories"
        / f"trajectory-{request_digest(request)}.h5"
    )
    original = artifacts._verify_installed_bytes
    mutated = False
    sidecar_verifications = 0

    def mutate_during_sidecar(path: Path, payload: bytes, description: str) -> None:
        nonlocal mutated, sidecar_verifications
        if description == "trajectory digest sidecar":
            sidecar_verifications += 1
            if sidecar_verifications == 2:
                with final.open("r+b") as stream:
                    stream.seek(0)
                    stream.write(b"during-sidecar")
                mutated = True
        original(path, payload, description)

    monkeypatch.setattr(
        artifacts, "_verify_installed_bytes", mutate_during_sidecar
    )
    with pytest.raises(ArtifactIntegrityError, match="digest|HDF5|parse"):
        publish_trajectory(tmp_path, *sample)
    assert mutated
    assert sidecar_verifications == 2
    assert final.read_bytes().startswith(b"during-sidecar")
    assert list((tmp_path / "trajectories").glob("*.intent"))


def test_sidecar_mutation_immediately_before_intent_removal_keeps_intent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    sidecar = (
        tmp_path
        / "trajectories"
        / f"trajectory-{request_digest(request)}.sha256.json"
    )
    original = artifacts._fsync_directory
    calls = 0
    hostile = artifacts._canonical_json_bytes({"hostile": True})

    def mutate_after_staged_unlink_fsync(path: Path) -> None:
        nonlocal calls
        original(path)
        calls += 1
        if calls == 2:
            sidecar.write_bytes(hostile)

    monkeypatch.setattr(
        artifacts, "_fsync_directory", mutate_after_staged_unlink_fsync
    )
    with pytest.raises(ArtifactIntegrityError, match="sidecar|bytes|digest"):
        publish_trajectory(tmp_path, *sample)
    assert sidecar.read_bytes() == hostile
    assert list((tmp_path / "trajectories").glob("*.intent"))


def test_intent_cleanup_failure_performs_recovery_directory_fsync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    calls: list[int] = []
    original = artifacts._fsync_directory

    def fail_cleanup_once(path: Path) -> None:
        calls.append(len(calls) + 1)
        if len(calls) == 3:
            raise OSError("cleanup fsync")
        original(path)

    monkeypatch.setattr(artifacts, "_fsync_directory", fail_cleanup_once)
    with pytest.raises(OSError, match="cleanup fsync"):
        publish_trajectory(tmp_path, *sample)
    assert calls == [1, 2, 3, 4]
    assert list((tmp_path / "trajectories").glob("*.intent"))


def test_intent_recovery_fsync_failure_raises_distinct_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    calls = 0
    original = artifacts._fsync_directory

    def fail_cleanup_and_recovery(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls in (3, 4):
            raise OSError(f"fsync-{calls}")
        original(path)

    monkeypatch.setattr(artifacts, "_fsync_directory", fail_cleanup_and_recovery)
    with pytest.raises(ArtifactIntegrityError, match="recovery.*fsync"):
        publish_trajectory(tmp_path, *sample)
    assert calls == 4
    assert list((tmp_path / "trajectories").glob("*.intent"))


@pytest.mark.parametrize(
    ("attribute", "stale"),
    (
        ("rng_version", "philox-stale"),
        ("conversion_version", "conversion-stale"),
    ),
)
def test_caller_cannot_bless_stale_frozen_versions(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    attribute: str,
    stale: str,
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    with h5py.File(path, "r+") as stream:
        stream.attrs[attribute] = stale
    _refresh_digest(path)
    stale_expected = expected(request)
    stale_expected[attribute] = stale
    with pytest.raises(ArtifactIntegrityError, match="version|stale"):
        load_verified_trajectory(path, stale_expected)


def test_publication_preserves_upstream_metadata_and_initializes_only_owned_namespaces(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    upstream = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    _publish_trajectory_api(tmp_path, *sample)
    assert {path.name for path in tmp_path.iterdir()} == {
        "request.json",
        "environment.json",
        "kernel",
        "seed-manifest.json",
        "capability.json",
        "trajectories",
        "batches",
        "manifest.json",
    }
    for name in ("kernel", "trajectories", "batches"):
        assert (tmp_path / name).is_dir()
        assert not (tmp_path / name).is_symlink()
    assert {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and path.relative_to(tmp_path) in upstream
    } == upstream
    assert all(b'"status":"reserved"' not in payload for payload in upstream.values())


def test_publication_requires_real_upstream_metadata_before_owned_outputs(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    root = tmp_path / "missing-upstream"
    root.mkdir()
    with pytest.raises(ArtifactIntegrityError, match="metadata|missing|layout"):
        _publish_trajectory_api(root, *sample)
    assert set(root.iterdir()) == set()


@pytest.mark.parametrize(
    "name",
    (
        "request.json",
        "environment.json",
        "seed-manifest.json",
        "capability.json",
        "manifest.json",
        "kernel/kernel.bin",
    ),
)
def test_upstream_metadata_hash_is_bound_into_trajectory_and_rechecked(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    name: str,
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    target = tmp_path / name
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ArtifactIntegrityError, match="metadata|kernel|digest"):
        load_verified_trajectory(path, expected(request))


def test_reconstruction_is_verify_only_and_rejects_empty_or_missing_layout(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ArtifactIntegrityError, match="layout|missing|empty"):
        reconstruct_progress(empty, expected(request))
    assert list(empty.iterdir()) == []

    root = tmp_path / "missing"
    _, _, hashes = _publish_valid_run(root, sample)
    (root / "capability.json").unlink()
    with pytest.raises(ArtifactIntegrityError, match="layout|missing"):
        reconstruct_progress(root, hashes)
    assert not (root / "capability.json").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unavailable")
def test_reconstruction_rejects_wrong_kinds_fifo_and_hardlink_alias(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    root = tmp_path / "fifo"
    _, _, hashes = _publish_valid_run(root, sample)
    capability = root / "capability.json"
    capability.unlink()
    os.mkfifo(capability)
    assert stat.S_ISFIFO(capability.lstat().st_mode)
    with pytest.raises(ArtifactIntegrityError, match="regular|kind|layout"):
        reconstruct_progress(root, hashes)

    alias_root = tmp_path / "alias"
    _, _, alias_hashes = _publish_valid_run(alias_root, sample)
    environment = alias_root / "environment.json"
    environment.unlink()
    os.link(alias_root / "request.json", environment)
    with pytest.raises(ArtifactIntegrityError, match="alias|link|layout"):
        reconstruct_progress(alias_root, alias_hashes)


def test_oversized_json_sidecar_and_manifest_are_rejected_before_parse(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path / "sidecar", *sample)
    path.with_suffix(".sha256.json").write_bytes(
        b" " * (artifacts.MAX_JSON_BYTES + 1)
    )
    with pytest.raises(ArtifactIntegrityError, match="size|large|limit"):
        load_verified_trajectory(path, expected(request))

    root = tmp_path / "manifest"
    _, batch, hashes = _publish_valid_run(root, sample)
    batch.write_bytes(b" " * (artifacts.MAX_JSON_BYTES + 1))
    with pytest.raises(ArtifactIntegrityError, match="size|large|limit"):
        reconstruct_progress(root, hashes)


def test_deeply_nested_bounded_json_fails_closed(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    path.with_suffix(".sha256.json").write_bytes(b"[" * 2000 + b"]" * 2000)
    with pytest.raises(ArtifactIntegrityError, match="read|JSON|parse"):
        load_verified_trajectory(path, expected(request))


def test_sparse_over_limit_kappa_shape_is_rejected_before_dataset_read(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    with h5py.File(path, "r+") as stream:
        del stream["request/kappas"]
        stream["request"].create_dataset(
            "kappas",
            shape=(4097,),
            maxshape=(None,),
            chunks=(1,),
            dtype="<f8",
        )
    _refresh_digest(path)
    with pytest.raises(ArtifactIntegrityError, match="kappa|shape|resource|storage"):
        load_verified_trajectory(path, expected(request))


@pytest.mark.parametrize("storage", ("chunked", "compressed"))
def test_noncanonical_dataset_storage_tricks_are_rejected(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    storage: str,
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    with h5py.File(path, "r+") as stream:
        values = stream["request/kappas"][...]
        del stream["request/kappas"]
        kwargs = {"chunks": (3,)}
        if storage == "compressed":
            kwargs["compression"] = "gzip"
        stream["request"].create_dataset(
            "kappas", data=values, dtype="<f8", **kwargs
        )
    _refresh_digest(path)
    with pytest.raises(ArtifactIntegrityError, match="storage|chunk|compression"):
        load_verified_trajectory(path, expected(request))


@pytest.mark.parametrize(
    ("attribute", "value"),
    (
        ("clean_tree", np.uint64(1)),
        ("length", np.uint32(8)),
        ("sigma", np.float32(1.25)),
        ("event_count", np.uint32(19)),
    ),
)
def test_hdf5_scalar_attribute_dtype_confusion_is_rejected(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    attribute: str,
    value: np.generic,
):
    request, _, _ = sample
    path = publish_trajectory(tmp_path, *sample)
    with h5py.File(path, "r+") as stream:
        del stream.attrs[attribute]
        stream.attrs.create(attribute, value)
    _refresh_digest(path)
    with pytest.raises(ArtifactIntegrityError, match="dtype|representation"):
        load_verified_trajectory(path, expected(request))


def _rewrite_json(path: Path, document: object) -> None:
    path.write_bytes(artifacts._canonical_json_bytes(document))


def test_request_json_hash_is_authoritative_for_changed_request_same_kernel(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    changed = TrajectoryRequest(
        length=request.length,
        sigma=request.sigma,
        sigma_grid_id=request.sigma_grid_id,
        kappas=request.kappas,
        master_seed=request.master_seed,
        phase=request.phase,
        replica=request.replica + 1,
        kernel_sha256=request.kernel_sha256,
    )
    with pytest.raises(ArtifactIntegrityError, match="request_sha256|request"):
        artifacts._verify_upstream_metadata(tmp_path, expected(changed))


@pytest.mark.parametrize(
    "variant",
    ("missing", "nested-decoy", "ambiguous", "duplicate-key", "wrong-type"),
)
def test_request_json_requires_unambiguous_top_level_request_hash(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    variant: str,
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    path = tmp_path / "request.json"
    document = json.loads(path.read_bytes())
    authoritative = document["request_sha256"]
    if variant == "missing":
        del document["request_sha256"]
    elif variant == "nested-decoy":
        document["request_sha256"] = "f" * 64
        document["decoy"] = {"request_sha256": authoritative}
    elif variant == "ambiguous":
        document["decoy"] = {"request_sha256": "f" * 64}
    elif variant == "duplicate-key":
        path.write_bytes(
            (
                "{"
                f'"kernel_sha256":"{request.kernel_sha256}",'
                f'"request_sha256":"{"f" * 64}",'
                f'"request_sha256":"{authoritative}",'
                '"schema_version":"test-request-v1"'
                "}\n"
            ).encode()
        )
    else:
        document["request_sha256"] = 17
    if variant != "duplicate-key":
        _rewrite_json(path, document)
    with pytest.raises(ArtifactIntegrityError, match="request_sha256|request|ambiguous"):
        artifacts._verify_upstream_metadata(tmp_path, expected(request))


@pytest.mark.parametrize(
    ("name", "field"),
    (
        ("request.json", "kernel_sha256"),
        ("environment.json", "clean_tree"),
        ("environment.json", "conversion_version"),
        ("environment.json", "rng_version"),
        ("environment.json", "runtime_capability_sha256"),
        ("environment.json", "source_revision"),
        ("environment.json", "uv_lock_sha256"),
        ("seed-manifest.json", "rng_sha256"),
        ("capability.json", "runtime_capability_sha256"),
        ("manifest.json", "analysis_plan_sha256"),
        ("manifest.json", "source_revision"),
    ),
)
def test_nested_decoy_never_satisfies_authoritative_metadata_path(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    name: str,
    field: str,
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    path = tmp_path / name
    document = json.loads(path.read_bytes())
    authoritative = document[field]
    document[field] = False if field == "clean_tree" else "f" * 64
    document["decoy"] = {field: authoritative}
    _rewrite_json(path, document)
    with pytest.raises(ArtifactIntegrityError, match=field):
        artifacts._verify_upstream_metadata(tmp_path, expected(request))


@pytest.mark.parametrize("replacement_kind", ("identical-inode", "same-inode-mutation"))
def test_aggregate_metadata_rechecks_first_file_after_later_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    replacement_kind: str,
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    first = tmp_path / "capability.json"
    replacement = tmp_path.parent / f"{tmp_path.name}-capability-replacement.json"
    replacement.write_bytes(first.read_bytes())
    original = artifacts._read_descriptor_bounded
    changed = False

    def mutate_first_during_later_read(
        descriptor: int,
        maximum_size: int,
        description: str,
    ) -> bytes:
        nonlocal changed
        payload = original(descriptor, maximum_size, description)
        if description == "upstream metadata request.json" and not changed:
            if replacement_kind == "identical-inode":
                os.replace(replacement, first)
            else:
                document = json.loads(first.read_bytes())
                document["runtime_capability_sha256"] = "5" * 64
                _rewrite_json(first, document)
            changed = True
        return payload

    monkeypatch.setattr(
        artifacts, "_read_descriptor_bounded", mutate_first_during_later_read
    )
    with pytest.raises(ArtifactIntegrityError, match="identity|mutat|snapshot|metadata"):
        artifacts._verify_upstream_metadata(tmp_path, expected(request))
    assert changed


def test_aggregate_metadata_rechecks_first_kernel_member_after_later_member(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    first = tmp_path / "kernel" / "kernel.bin"
    (tmp_path / "kernel" / "zz.bin").write_bytes(b"later-kernel-member")
    original = artifacts._hash_descriptor
    kernel_hash_calls = 0
    changed = False

    def mutate_first_during_later_hash(
        descriptor: int,
        description: str,
    ) -> tuple[str, int]:
        nonlocal kernel_hash_calls, changed
        result = original(descriptor, description)
        if description == "kernel metadata file":
            kernel_hash_calls += 1
            if kernel_hash_calls == 2:
                with first.open("r+b") as stream:
                    stream.seek(0)
                    stream.write(b"mutated!")
                changed = True
        return result

    monkeypatch.setattr(artifacts, "_hash_descriptor", mutate_first_during_later_hash)
    with pytest.raises(ArtifactIntegrityError, match="mutat|snapshot|metadata|digest"):
        artifacts._verify_upstream_metadata(tmp_path, expected(request))
    assert changed
    assert kernel_hash_calls >= 2


@pytest.mark.parametrize("replacement_kind", ("identical-inode", "same-inode-mutation"))
def test_aggregate_final_sweep_catches_first_file_changed_during_second_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    replacement_kind: str,
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    first = tmp_path / "capability.json"
    replacement = tmp_path.parent / f"{tmp_path.name}-final-replacement.json"
    replacement.write_bytes(first.read_bytes())
    original = artifacts._read_descriptor_bounded
    request_reads = 0
    changed = False

    def mutate_after_first_was_second_pass_checked(
        descriptor: int,
        maximum_size: int,
        description: str,
    ) -> bytes:
        nonlocal request_reads, changed
        payload = original(descriptor, maximum_size, description)
        if description == "upstream metadata request.json":
            request_reads += 1
            if request_reads == 2:
                if replacement_kind == "identical-inode":
                    os.replace(replacement, first)
                else:
                    document = json.loads(first.read_bytes())
                    document["runtime_capability_sha256"] = "5" * 64
                    _rewrite_json(first, document)
                changed = True
        return payload

    monkeypatch.setattr(
        artifacts,
        "_read_descriptor_bounded",
        mutate_after_first_was_second_pass_checked,
    )
    with pytest.raises(ArtifactIntegrityError, match="identity|mutat|snapshot|metadata"):
        artifacts._verify_upstream_metadata(tmp_path, expected(request))
    assert changed
    assert request_reads >= 2


def test_aggregate_final_sweep_catches_kernel_changed_during_second_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    first = tmp_path / "kernel" / "kernel.bin"
    (tmp_path / "kernel" / "zz.bin").write_bytes(b"later-kernel-member")
    original = artifacts._hash_descriptor
    kernel_hash_calls = 0
    changed = False

    def mutate_after_first_was_second_pass_checked(
        descriptor: int,
        description: str,
    ) -> tuple[str, int]:
        nonlocal kernel_hash_calls, changed
        result = original(descriptor, description)
        if description == "kernel metadata file":
            kernel_hash_calls += 1
            if kernel_hash_calls == 4:
                with first.open("r+b") as stream:
                    stream.seek(0)
                    stream.write(b"mutated!")
                changed = True
        return result

    monkeypatch.setattr(
        artifacts, "_hash_descriptor", mutate_after_first_was_second_pass_checked
    )
    with pytest.raises(ArtifactIntegrityError, match="mutat|snapshot|metadata|digest"):
        artifacts._verify_upstream_metadata(tmp_path, expected(request))
    assert changed
    assert kernel_hash_calls >= 4


def test_frozen_json_limit_fits_worst_case_batch_and_progress():
    ids = [f"{index:064x}" for index in range(artifacts.MAX_BATCH_MEMBERS)]
    members = [
        {
            "path": f"trajectories/trajectory-{trajectory_id}.h5",
            "trajectory_id": trajectory_id,
            "trajectory_sha256": "f" * 64,
        }
        for trajectory_id in ids
    ]
    batch = {
        "batch_id": "b" * 128,
        "members": members,
        "schema_version": artifacts.BATCH_SCHEMA,
    }
    trajectories = list(members)
    batches = [
        {
            "batch_id": f"{index:0128x}",
            "path": f"batches/batch-{index:0128x}.json",
            "trajectory_count": 1,
        }
        for index in range(artifacts.MAX_BATCH_MEMBERS)
    ]
    progress = {
        "batch_count": len(batches),
        "batches": batches,
        "schema_version": artifacts.PROGRESS_SCHEMA,
        "trajectory_count": len(trajectories),
        "trajectories": trajectories,
    }
    worst_case = max(
        len(artifacts._canonical_json_bytes(batch)),
        len(artifacts._canonical_json_bytes(progress)),
    )
    assert worst_case + artifacts.MAX_JSON_SAFETY_BYTES <= artifacts.MAX_JSON_BYTES


def test_reconstruction_rejects_global_trajectory_count_over_frozen_limit(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, provenance = sample
    _write_upstream_metadata(tmp_path, request, provenance)
    trajectories = tmp_path / "trajectories"
    trajectories.mkdir()
    (tmp_path / "batches").mkdir()
    for index in range(artifacts.MAX_BATCH_MEMBERS + 1):
        (trajectories / f"trajectory-{index:064x}.h5").touch()
    with pytest.raises(ArtifactIntegrityError, match="count|limit"):
        reconstruct_progress(tmp_path, expected(request))


def test_json_publication_accepts_exact_limit_and_rejects_limit_plus_one(
    tmp_path: Path,
):
    schema = "test-json-boundary-v1"
    base = {"padding": "", "schema_version": schema}
    overhead = len(artifacts._canonical_json_bytes(base))
    accepted_document = {
        "padding": "x" * (artifacts.MAX_JSON_BYTES - overhead),
        "schema_version": schema,
    }
    accepted = tmp_path / "accepted.json"
    artifacts._publish_json_once(accepted, accepted_document, schema)
    assert accepted.stat().st_size == artifacts.MAX_JSON_BYTES

    rejected_document = {
        "padding": "x" * (artifacts.MAX_JSON_BYTES - overhead + 1),
        "schema_version": schema,
    }
    rejected = tmp_path / "rejected.json"
    with pytest.raises(ArtifactIntegrityError, match="size|limit"):
        artifacts._publish_json_once(rejected, rejected_document, schema)
    assert not rejected.exists()


def test_v2_schema_registry_and_v1_trajectory_rejection(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    request, _, _ = sample
    assert artifacts.TRAJECTORY_SCHEMA.endswith("-v2")
    assert artifacts.TRAJECTORY_DIGEST_SCHEMA.endswith("-v2")
    assert artifacts.BATCH_SCHEMA.endswith("-v2")
    assert artifacts.PROGRESS_SCHEMA.endswith("-v2")
    path = publish_trajectory(tmp_path, *sample)
    with h5py.File(path, "r+") as stream:
        stream.attrs["schema_version"] = "challenge-194-trajectory-artifact-v1"
    _refresh_digest(path)
    with pytest.raises(ArtifactIntegrityError, match="schema|stale"):
        load_verified_trajectory(path, expected(request))
