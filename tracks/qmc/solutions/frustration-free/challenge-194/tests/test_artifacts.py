from __future__ import annotations

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
def test_json_semantics_reject_path_identity_swap_after_descriptor_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
    kind: str,
):
    trajectory, batch, hashes = _publish_valid_run(tmp_path, sample)
    target = trajectory.with_suffix(".sha256.json") if kind == "sidecar" else batch
    replacement = tmp_path.parent / f"{tmp_path.name}-replacement-{kind}.json"
    replacement.write_bytes(target.read_bytes())
    original = artifacts._read_descriptor_bounded
    swapped = False

    def read_then_swap(
        descriptor: int,
        maximum_size: int,
        description: str,
    ) -> bytes:
        nonlocal swapped
        payload = original(descriptor, maximum_size, description)
        expected_description = (
            "trajectory digest sidecar" if kind == "sidecar" else "batch manifest"
        )
        if description == expected_description and not swapped:
            swapped = True
            os.replace(replacement, target)
        return payload

    monkeypatch.setattr(artifacts, "_read_descriptor_bounded", read_then_swap)
    with pytest.raises(ArtifactIntegrityError, match="identity"):
        if kind == "sidecar":
            load_verified_trajectory(trajectory, hashes)
        else:
            reconstruct_progress(tmp_path, hashes)
    assert swapped


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


def test_publication_initializes_complete_canonical_top_level_layout(
    tmp_path: Path,
    sample: tuple[TrajectoryRequest, TrajectoryResult, dict[str, object]],
):
    publish_trajectory(tmp_path, *sample)
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
    for name in (
        "request.json",
        "environment.json",
        "seed-manifest.json",
        "capability.json",
        "manifest.json",
    ):
        assert (tmp_path / name).is_file()
        assert not (tmp_path / name).is_symlink()


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
    path.with_suffix(".sha256.json").write_bytes(b" " * (1_048_576 + 1))
    with pytest.raises(ArtifactIntegrityError, match="size|large|limit"):
        load_verified_trajectory(path, expected(request))

    root = tmp_path / "manifest"
    _, batch, hashes = _publish_valid_run(root, sample)
    batch.write_bytes(b" " * (1_048_576 + 1))
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
