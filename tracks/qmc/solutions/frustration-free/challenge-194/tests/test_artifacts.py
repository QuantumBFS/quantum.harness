from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path

import h5py
import numpy as np
import pytest

import long_range_percolation.artifacts as artifacts
from long_range_percolation.artifacts import (
    ArtifactIntegrityError,
    load_verified_trajectory,
    publish_batch_manifest,
    publish_trajectory,
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
        kernel_sha256="a" * 64,
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
        assert attrs["schema_version"] == "challenge-194-trajectory-artifact-v1"
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
        "schema_version": "challenge-194-trajectory-digest-v1",
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
    ("_flush_hdf5", "_fsync_file", "_semantic_reload", "_hash_file", "_replace"),
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
        raise OSError(f"crash at {boundary}")

    monkeypatch.setattr(artifacts, boundary, crash)
    with pytest.raises(OSError, match="crash"):
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
    duplicate.with_suffix(".sha256.json").write_bytes(
        trajectory.with_suffix(".sha256.json").read_bytes()
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
    def publish() -> Path:
        return publish_trajectory(tmp_path, *sample)

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
    root.mkdir()
    (root / "trajectories").symlink_to(real, target_is_directory=True)
    with pytest.raises(ArtifactIntegrityError, match="symlink"):
        publish_trajectory(root, *sample)
