from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from long_range_percolation import pilot
from long_range_percolation.pilot import PilotCell


def _tiny_spec(tmp_path: Path, *, replicas: tuple[int, ...] = (0,)) -> Path:
    root = tmp_path / "pilot"
    return pilot._write_test_pilot_run_spec(
        root,
        lengths=(8,),
        sigmas=(1.0,),
        replicas=replicas,
        kappas=(0.0, 0.25),
    )


def _frozen_spec(tmp_path: Path) -> Path:
    return pilot._write_test_frozen_pilot_run_spec(tmp_path / "frozen")


def test_frozen_registry_has_exact_order_grid_and_unique_identities(tmp_path: Path):
    spec = pilot._build_test_pilot_run_spec(tmp_path / "pilot")
    cells = [PilotCell.from_document(item) for item in spec["cells"]]
    assert len(cells) == 96
    assert [
        (cell.sigma, cell.length, cell.replica) for cell in cells
    ] == [
        (sigma, length, replica)
        for sigma in (0.8, 0.9, 1.0, 1.1)
        for length in (2**10, 2**14, 2**18)
        for replica in range(8)
    ]
    assert spec["protocol"]["sigmas"] == [value.hex() for value in (0.8, 0.9, 1.0, 1.1)]
    assert spec["protocol"]["kappas"] == [
        value.hex() for value in [0.0] + [0.25 * 1.25**j for j in range(15)]
    ]
    assert len({cell.request_sha256 for cell in cells}) == 96
    assert len({cell.cell_id for cell in cells}) == 96
    assert spec["rng_assignment_sha256"]


def test_run_spec_is_canonical_and_all_paths_are_relative(tmp_path: Path):
    path = _tiny_spec(tmp_path)
    payload = path.read_bytes()
    document = json.loads(payload)
    assert payload == pilot._canonical_bytes(document)
    assert document["artifact_root"] == "."
    assert "run_root" not in document
    for cell in document["cells"]:
        for key in ("cell_path", "run_path", "manifest_path"):
            assert not Path(cell[key]).is_absolute()
            assert ".." not in Path(cell[key]).parts


def test_small_cell_end_to_end_is_idempotent_and_portable(tmp_path: Path):
    path = _tiny_spec(tmp_path)
    first = pilot._run_test_pilot_cell(path, 0)
    marker = path.parent / first["manifest_path"]
    before = marker.stat().st_mtime_ns
    assert pilot._run_test_pilot_cell(path, 0) == first
    assert marker.stat().st_mtime_ns == before
    merged = pilot._merge_test_pilot_progress(path)
    assert merged["cell_count"] == 1
    assert merged["trajectory_count"] == 1
    assert pilot._verify_test_pilot_download(path)["cell_count"] == 1

    copied = tmp_path / "downloaded"
    shutil.copytree(path.parent, copied)
    assert pilot._verify_test_pilot_download(copied / "run_spec.json")[
        "cell_count"
    ] == 1


def test_duplicate_execution_has_one_equivalent_verified_winner(tmp_path: Path):
    path = _tiny_spec(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: pilot._run_test_pilot_cell(path, 0), range(2)))
    assert results[0] == results[1]
    run = next((path.parent / "cells").iterdir()) / "run"
    assert len(list((run / "trajectories").glob("trajectory-*.h5"))) == 1
    assert len(list((run / "batches").glob("batch-*.json"))) == 1


def test_different_cells_can_initialize_while_first_worker_retains_chain(
    tmp_path: Path,
):
    path = _tiny_spec(tmp_path, replicas=(0, 1))
    first_ready = Event()
    second_done = Event()

    def hold_first(stage: str) -> None:
        if stage == "after-trajectory":
            first_ready.set()
            assert second_done.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            pilot._run_test_pilot_cell,
            path,
            0,
            crash_hook=hold_first,
        )
        assert first_ready.wait(timeout=10)
        second = pilot._run_test_pilot_cell(path, 1)
        second_done.set()
        first_result = first.result(timeout=10)

    assert first_result["cell_index"] == 0
    assert second["cell_index"] == 1
    assert pilot._pending_test_pilot_cells(path) == []
    pilot._merge_test_pilot_progress(path)
    assert pilot._verify_test_pilot_download(path)["cell_count"] == 2


def test_run_spec_read_allows_same_parent_to_gain_cells_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = _tiny_spec(tmp_path)
    descriptor_read = Event()
    parent_mutated = Event()
    original = pilot._read_descriptor_bounded
    held = False

    def hold_after_read(
        descriptor: int, maximum_size: int, description: str
    ) -> bytes:
        nonlocal held
        payload = original(descriptor, maximum_size, description)
        if description == "pilot run spec" and not held:
            held = True
            descriptor_read.set()
            assert parent_mutated.wait(timeout=10)
        return payload

    monkeypatch.setattr(pilot, "_read_descriptor_bounded", hold_after_read)
    with ThreadPoolExecutor(max_workers=1) as pool:
        loading = pool.submit(
            pilot._load_pilot_spec,
            path,
            verify_current_environment=False,
                expected_schema=pilot.TEST_RUN_SPEC_SCHEMA,
        )
        assert descriptor_read.wait(timeout=10)
        (path.parent / "cells").mkdir()
        parent_mutated.set()
        loaded = loading.result(timeout=10)

    assert loaded["run_spec_sha256"]


def test_replacing_shared_cells_inode_while_worker_retains_chain_fails(
    tmp_path: Path,
):
    path = _tiny_spec(tmp_path, replicas=(0, 1))
    cells_root = path.parent / "cells"

    def replace_cells(stage: str) -> None:
        if stage == "after-trajectory":
            cells_root.rename(path.parent / "detached-cells")
            cells_root.mkdir()

    with pytest.raises(RuntimeError, match="identity|generation"):
        pilot._run_test_pilot_cell(path, 0, crash_hook=replace_cells)


@pytest.mark.parametrize("stage", ("after-trajectory", "after-progress"))
def test_resume_after_publication_finishes_remaining_boundaries(
    tmp_path: Path, stage: str
):
    path = _tiny_spec(tmp_path)

    def stop(actual: str) -> None:
        if actual == stage:
            raise RuntimeError("injected stop")

    with pytest.raises(RuntimeError, match="injected stop"):
        pilot._run_test_pilot_cell(path, 0, crash_hook=stop)
    run = next((path.parent / "cells").iterdir()) / "run"
    assert list((run / "trajectories").glob("trajectory-*.h5"))
    if stage == "after-trajectory":
        assert not list((run / "batches").glob("batch-*.json"))
    else:
        assert (run / "progress.json").is_file()
        assert not (run.parent / "manifest.json").exists()
    result = pilot._run_test_pilot_cell(path, 0)
    assert (path.parent / result["manifest_path"]).is_file()
    assert (run / "progress.json").is_file()


@pytest.mark.parametrize("suffix", (".partial", ".intent"))
def test_stale_publication_markers_fail_closed(tmp_path: Path, suffix: str):
    path = _tiny_spec(tmp_path)
    pilot._run_test_pilot_cell(path, 0)
    cell = next((path.parent / "cells").iterdir())
    (cell / f"stale{suffix}").write_text("do not delete", encoding="utf-8")
    with pytest.raises(RuntimeError, match="publication marker"):
        pilot._run_test_pilot_cell(path, 0)
    assert (cell / f"stale{suffix}").exists()


def test_pending_and_merge_reject_missing_extra_duplicate_and_corrupt(tmp_path: Path):
    path = _tiny_spec(tmp_path, replicas=(0, 1))
    assert pilot._pending_test_pilot_cells(path) == [0, 1]
    pilot._run_test_pilot_cell(path, 0)
    assert pilot._pending_test_pilot_cells(path) == [1]
    with pytest.raises(RuntimeError, match="missing"):
        pilot._merge_test_pilot_progress(path)
    pilot._run_test_pilot_cell(path, 1)
    document = pilot._merge_test_pilot_progress(path)
    assert document["cell_count"] == document["trajectory_count"] == 2

    extra = path.parent / "cells" / "extra"
    extra.mkdir()
    with pytest.raises(RuntimeError, match="extra"):
        pilot._merge_test_pilot_progress(path)
    extra.rmdir()

    marker = path.parent / json.loads(path.read_text())["cells"][0]["manifest_path"]
    marker.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest"):
        pilot._merge_test_pilot_progress(path)


def test_spec_loader_rejects_provenance_drift(tmp_path: Path):
    path = _frozen_spec(tmp_path)
    document = json.loads(path.read_text())
    document["uv_lock_sha256"] = "0" * 64
    document["run_spec_sha256"] = pilot._document_hash(document, "run_spec_sha256")
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError, match="uv.lock"):
        pilot.load_pilot_run_spec(path, verify_current_environment=False)


def test_correctness_evidence_requires_checked_in_approval_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    historical = pilot.CORRECTNESS_APPROVAL_REVISION
    modules = pilot._scientific_hashes()
    package = tmp_path / "package"
    report_path = package / "report" / "report.json"
    report_path.parent.mkdir(parents=True)
    report = {
        "passed": True,
        "source": {
            "source_revision": historical,
            "clean_tree": True,
            "provenance_error": None,
        },
        "runtime_capability": {"node": "validated"},
        "checks": [],
    }
    report_path.write_bytes(pilot._canonical_bytes(report))
    validation_spec_path = package / "run_spec.json"
    validation_spec = {
        "source_revision": historical,
        "uv_lock_sha256": pilot._lock_hash(),
        "runtime_capability": report["runtime_capability"],
        "runtime_capability_sha256": "3" * 64,
        "implementation_modules": modules,
        "global_expected_checks": [],
        "cells": [{"expected_checks": []} for _ in range(120)],
    }
    validation_spec_path.write_bytes(pilot._canonical_bytes(validation_spec))
    monkeypatch.setattr(pilot, "validate_report_payload", lambda *_: None)
    monkeypatch.setattr(pilot, "validate_validation_run_spec", lambda *_args, **_kwargs: None)
    report["checks"] = [
        {
            "passed": True,
            "internal_sha256": pilot._sha256(
                pilot._canonical_bytes({"changed": True})
            ),
        }
    ]
    report_path.write_bytes(pilot._canonical_bytes(report))
    with pytest.raises(RuntimeError, match="approved correctness report SHA256"):
        pilot._verified_correctness(report_path)


@pytest.mark.parametrize(
    "mutation",
    (
        "cell-count",
        "wrong-96-cells",
        "reordered",
        "kappa",
        "sigma",
        "length",
        "replica",
        "request",
        "path",
    ),
)
def test_public_loader_never_downgrades_frozen_p0(
    tmp_path: Path, mutation: str
):
    path = _frozen_spec(tmp_path)
    document = json.loads(path.read_text())
    if mutation == "cell-count":
        document["cell_count"] = 1
    elif mutation == "wrong-96-cells":
        document["cells"] = [dict(document["cells"][0]) for _ in range(96)]
    elif mutation == "reordered":
        document["cells"][0], document["cells"][1] = (
            document["cells"][1],
            document["cells"][0],
        )
    elif mutation == "kappa":
        document["cells"][0]["kappas"][1] = (0.3).hex()
    elif mutation == "sigma":
        document["cells"][0]["sigma"] = (0.7).hex()
    elif mutation == "length":
        document["cells"][0]["length"] = 2048
    elif mutation == "replica":
        document["cells"][0]["replica"] = 9
    elif mutation == "request":
        document["cells"][0]["request_sha256"] = "f" * 64
    else:
        document["cells"][0]["run_path"] = "cells/other/run"
    document["run_spec_sha256"] = pilot._document_hash(
        document, "run_spec_sha256"
    )
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError):
        pilot.load_pilot_run_spec(path, verify_current_environment=False)


def test_public_loader_rejects_private_tiny_schema(tmp_path: Path):
    path = _tiny_spec(tmp_path)
    with pytest.raises(RuntimeError, match="schema"):
        pilot.load_pilot_run_spec(path, verify_current_environment=False)


def test_public_p0_loader_rejects_internally_rehashed_extension(tmp_path: Path):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    document = json.loads(path.read_text())
    document["run_spec_sha256"] = pilot._document_hash(
        document, "run_spec_sha256"
    )
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError, match="P0 run spec"):
        pilot.load_pilot_run_spec(path, verify_current_environment=False)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("sigmas", (0.7, 0.9, 1.0, 1.1)),
        ("lengths", (2048, 16384, 262144)),
        ("replicas", (1, 0, 2, 3, 4, 5, 6, 7)),
        ("kappas", (0.0, *tuple(0.3 * 1.25**j for j in range(15)))),
    ),
)
def test_public_loader_rejects_internally_rehashed_non_p0_registry(
    tmp_path: Path, field: str, value: tuple[object, ...]
):
    root = tmp_path / "pilot"
    kwargs = {field: value}
    document = pilot._build_test_pilot_run_spec(root, **kwargs)
    document["schema_version"] = pilot.RUN_SPEC_SCHEMA
    document["run_spec_sha256"] = pilot._document_hash(
        document, "run_spec_sha256"
    )
    root.mkdir()
    path = root / "run_spec.json"
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError):
        pilot.load_pilot_run_spec(path, verify_current_environment=False)


def test_bounded_json_reader_rejects_limit_plus_one_malformed_and_deep(
    tmp_path: Path
):
    valid = tmp_path / "valid.json"
    valid.write_bytes(pilot._canonical_bytes({"schema_version": "test"}))
    pilot._read_canonical(
        valid, "test", maximum_size=valid.stat().st_size
    )
    with pytest.raises(RuntimeError, match="byte-size"):
        pilot._read_canonical(
            valid, "test", maximum_size=valid.stat().st_size - 1
        )

    oversized = tmp_path / "oversized.json"
    with oversized.open("wb") as stream:
        stream.truncate(pilot.PILOT_RUN_SPEC_MAX_BYTES + 1)
    with pytest.raises(RuntimeError, match="byte-size"):
        pilot._read_canonical(
            oversized,
            "oversized",
            maximum_size=pilot.PILOT_RUN_SPEC_MAX_BYTES,
        )

    malformed = tmp_path / "malformed.json"
    malformed.write_bytes(b"{")
    with pytest.raises(RuntimeError, match="valid JSON"):
        pilot._read_canonical(malformed, "malformed", maximum_size=16)

    deep: object = "leaf"
    for _ in range(pilot.PILOT_JSON_MAX_DEPTH + 1):
        deep = [deep]
    deep_path = tmp_path / "deep.json"
    deep_path.write_bytes(pilot._canonical_bytes({"value": deep}))
    with pytest.raises(RuntimeError, match="depth"):
        pilot._read_canonical(deep_path, "deep", maximum_size=4096)

    with pytest.raises(RuntimeError, match="string"):
        pilot._validate_json_bounds("x" * (pilot.PILOT_JSON_MAX_STRING + 1))
    with pytest.raises(RuntimeError, match="sequence"):
        pilot._validate_json_bounds(
            [None] * (pilot.PILOT_JSON_MAX_CONTAINER + 1)
        )
    pilot._validate_json_bounds([None, None], maximum_nodes=3)
    with pytest.raises(RuntimeError, match="node"):
        pilot._validate_json_bounds([None, None, None], maximum_nodes=3)


def test_correctness_documents_use_their_larger_frozen_node_budget(
    tmp_path: Path,
):
    document = {"values": [None, None, None]}
    path = tmp_path / "correctness.json"
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError, match="node"):
        pilot._read_canonical(
            path,
            "ordinary document",
            maximum_size=path.stat().st_size,
            maximum_nodes=3,
        )
    loaded, _ = pilot._read_canonical(
        path,
        "correctness document",
        maximum_size=path.stat().st_size,
        maximum_nodes=pilot.CORRECTNESS_JSON_MAX_NODES,
    )
    assert loaded == document


def test_descriptor_read_rejects_file_replacement_and_same_size_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "document.json"
    original = pilot._canonical_bytes({"schema_version": "test", "value": "aa"})
    replacement = pilot._canonical_bytes({"schema_version": "test", "value": "bb"})
    assert len(original) == len(replacement)
    path.write_bytes(original)
    real_read = pilot._read_descriptor_bounded

    def swapping_read(descriptor: int, maximum: int, description: str) -> bytes:
        payload = real_read(descriptor, maximum, description)
        other = tmp_path / "other.json"
        other.write_bytes(replacement)
        os.replace(other, path)
        return payload

    monkeypatch.setattr(pilot, "_read_descriptor_bounded", swapping_read)
    with pytest.raises(RuntimeError, match="identity|generation|changed"):
        pilot._read_canonical(path, "document", maximum_size=4096)


def test_publication_rejects_parent_swap_to_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    parent = tmp_path / "parent"
    parent.mkdir()
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    real_link = pilot._link_at

    def swapping_link(
        source: str, destination: str, source_fd: int, destination_fd: int
    ) -> None:
        moved = tmp_path / "moved"
        os.rename(parent, moved)
        parent.symlink_to(hostile, target_is_directory=True)
        real_link(source, destination, source_fd, destination_fd)

    monkeypatch.setattr(pilot, "_link_at", swapping_link)
    with pytest.raises(RuntimeError, match="parent|identity|changed"):
        pilot._publish_once(
            parent / "marker.json", {"schema_version": "test"}
        )
    assert not (hostile / "marker.json").exists()


def test_publication_rejects_noncooperating_destination_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    destination = tmp_path / "marker.json"
    real_link = pilot._link_at

    def racing_link(
        source: str, target: str, source_fd: int, destination_fd: int
    ) -> None:
        descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=destination_fd,
        )
        try:
            os.write(
                descriptor,
                pilot._canonical_bytes({"schema_version": "hostile"}),
            )
        finally:
            os.close(descriptor)
        real_link(source, target, source_fd, destination_fd)

    monkeypatch.setattr(pilot, "_link_at", racing_link)
    with pytest.raises(RuntimeError, match="other bytes"):
        pilot._publish_once(destination, {"schema_version": "expected"})


def test_cell_root_replacement_after_descriptor_open_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = _tiny_spec(tmp_path)
    cell = PilotCell.from_document(json.loads(path.read_text())["cells"][0])
    cell_root = path.parent / cell.cell_path
    real_flock = pilot.fcntl.flock
    swapped = False

    def swapping_flock(descriptor: int, operation: int) -> None:
        nonlocal swapped
        if (
            operation == pilot.fcntl.LOCK_EX
            and not swapped
            and cell_root.exists()
        ):
            swapped = True
            cell_root.rename(path.parent / "detached-cell")
            cell_root.mkdir()
        real_flock(descriptor, operation)

    monkeypatch.setattr(pilot.fcntl, "flock", swapping_flock)
    with pytest.raises(RuntimeError, match="directory identity changed"):
        pilot._run_test_pilot_cell(path, 0)


def test_approval_registry_rejects_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    real = pilot._approval_registry_path()
    linked = tmp_path / "approval.json"
    linked.symlink_to(real)
    monkeypatch.setattr(pilot, "_approval_registry_path", lambda: linked)
    with pytest.raises(RuntimeError, match="symlink"):
        pilot._load_approval_registry()


def test_approval_registry_digest_is_independently_pinned_after_clean_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fabricated = json.loads(pilot._approval_registry_path().read_text())
    fabricated["report_sha256"] = "a" * 64
    fabricated["run_spec_sha256"] = "b" * 64
    replacement = tmp_path / "approval.json"
    replacement.write_bytes(pilot._canonical_bytes(fabricated))
    monkeypatch.setattr(pilot, "_approval_registry_path", lambda: replacement)
    monkeypatch.setattr(
        pilot,
        "_repository_state",
        lambda: {
            "source_revision": "f" * 40,
            "clean_tree": True,
            "provenance_error": None,
        },
    )

    pilot._current_source(require_clean=True)
    with pytest.raises(RuntimeError, match="pinned SHA256"):
        pilot._load_approval_registry()


def test_descriptor_hash_rejects_same_size_source_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source.py"
    source.write_bytes(b"original\n")
    replacement = tmp_path / "replacement.py"
    replacement.write_bytes(b"changed!\n")
    assert source.stat().st_size == replacement.stat().st_size
    real_hash = pilot._artifacts._hash_descriptor

    def swapping_hash(descriptor: int, description: str) -> tuple[str, int]:
        result = real_hash(descriptor, description)
        os.replace(replacement, source)
        return result

    monkeypatch.setattr(pilot, "_hash_descriptor", swapping_hash, raising=False)
    with pytest.raises(RuntimeError, match="identity|generation|changed"):
        pilot._file_hash(source)


def test_publication_rejects_ancestor_replacement_before_descriptor_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ancestor = tmp_path / "ancestor"
    parent = ancestor / "parent"
    parent.mkdir(parents=True)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    swapped = False

    def swapping_open(name: str, parent_fd: int) -> int:
        nonlocal swapped
        if name == "ancestor" and not swapped:
            swapped = True
            ancestor.rename(tmp_path / "detached-ancestor")
            (ancestor / "parent").mkdir(parents=True)
        return os.open(name, flags, dir_fd=parent_fd)

    monkeypatch.setattr(
        pilot, "_open_directory_at", swapping_open, raising=False
    )
    with pytest.raises(RuntimeError, match="ancestor|generation|identity"):
        pilot._publish_once(parent / "marker.json", {"schema_version": "test"})


def test_directory_chain_accepts_generation_only_metadata_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "root"
    root.mkdir()
    descriptor = os.open(
        root,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    original = os.fstat(descriptor)
    real_lstat = Path.lstat

    class Drifted:
        st_dev = original.st_dev
        st_ino = original.st_ino
        st_mode = original.st_mode
        st_nlink = original.st_nlink
        st_uid = original.st_uid
        st_gid = original.st_gid
        st_size = original.st_size + 4096
        st_mtime_ns = original.st_mtime_ns + 1
        st_ctime_ns = original.st_ctime_ns + 1

    def drifted_lstat(path: Path):
        if path == root:
            return Drifted()
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", drifted_lstat)
    try:
        pilot._require_directory_chain(
            [(root, descriptor, original)],
            allow_final_mutation=False,
        )
        opened = pilot._open_directory_chain(root, create=False)
        pilot._close_directory_chain(opened)
    finally:
        os.close(descriptor)


def test_cell_swap_and_restore_during_work_fails_closed(
    tmp_path: Path,
):
    path = _tiny_spec(tmp_path)
    cell = PilotCell.from_document(json.loads(path.read_text())["cells"][0])
    cell_root = path.parent / cell.cell_path

    def swap_and_restore(stage: str) -> None:
        if stage == "after-trajectory":
            detached = path.parent / "detached-cell"
            cell_root.rename(detached)
            detached.rename(cell_root)

    with pytest.raises(RuntimeError, match="generation changed"):
        pilot._run_test_pilot_cell(path, 0, crash_hook=swap_and_restore)


def test_download_verification_requires_merged_progress(tmp_path: Path):
    path = _tiny_spec(tmp_path)
    pilot._run_test_pilot_cell(path, 0)
    assert not (path.parent / pilot.MERGED_NAME).exists()
    with pytest.raises(RuntimeError, match="merged pilot progress is missing"):
        pilot._verify_test_pilot_download(path)


def test_public_download_verifier_rejects_missing_merged_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    run_spec = tmp_path / pilot.RUN_SPEC_NAME
    monkeypatch.setattr(
        pilot,
        "_merged_document",
        lambda *_args, **_kwargs: {"schema_version": pilot.MERGED_SCHEMA},
    )
    with pytest.raises(RuntimeError, match="merged pilot progress is missing"):
        pilot.verify_pilot_download(run_spec)


@pytest.mark.parametrize("kind", ("source", "runtime", "engine", "analysis"))
def test_current_environment_rejects_every_bound_provenance_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
):
    path = _frozen_spec(tmp_path)
    revision = json.loads(path.read_text())["orchestration_revision"]
    monkeypatch.setattr(
        pilot,
        "_current_source",
        lambda **_: {
            "source_revision": revision,
            "clean_tree": True,
            "provenance_error": None,
        },
    )
    if kind == "source":
        monkeypatch.setattr(
            pilot,
            "_current_source",
            lambda **_: {
                "source_revision": "f" * 40,
                "clean_tree": True,
                "provenance_error": None,
            },
        )
        match = "orchestration revision"
    elif kind == "runtime":
        monkeypatch.setattr(
            pilot, "_runtime_document", lambda: ({"changed": True}, "f" * 64)
        )
        match = "runtime capability"
    elif kind == "engine":
        modules = pilot._scientific_hashes()
        modules[next(iter(modules))] = "f" * 64
        monkeypatch.setattr(pilot, "_scientific_hashes", lambda: modules)
        match = "scientific engine"
    else:
        monkeypatch.setattr(pilot, "_analysis_plan_hash", lambda: "f" * 64)
        match = "analysis plan"
    with pytest.raises(RuntimeError, match=match):
        pilot.load_pilot_run_spec(path, verify_current_environment=True)
