from __future__ import annotations

import hashlib
import json
import multiprocessing
import shutil
import weakref
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import long_range_percolation.pilot_analysis as analysis
from long_range_percolation import pilot
from long_range_percolation.trajectory import TrajectoryResult

OBSERVABLE_COLUMNS = {
    "s1_fraction": 4,
    "s2_fraction": 5,
    "q_g": 8,
    "four_sector_crossing": 9,
}


def _canonical_bytes(document: object) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _selector_document(
    *,
    sigmas: tuple[float, ...] = (0.8, 1.1),
    lengths: tuple[int, ...] = (8, 16, 32),
    kappas: tuple[float, ...] = (0.0, 1.0, 2.0, 4.0),
    values: dict[
        tuple[float, int, float],
        tuple[float, float],
    ]
    | None = None,
) -> dict[str, object]:
    values = values or {}
    estimates: list[dict[str, object]] = []
    for sigma in sigmas:
        for length in lengths:
            for kappa in kappas:
                q_g, crossing = values.get(
                    (sigma, length, kappa),
                    (float(length) + kappa, 0.1 * kappa),
                )
                estimates.append(
                    {
                        "sigma_hex": sigma.hex(),
                        "length": length,
                        "kappa_hex": kappa.hex(),
                        "replica_count": 8,
                        "means": {
                            "s1_fraction": 0.1,
                            "s2_fraction": 0.05,
                            "q_g": q_g,
                            "four_sector_crossing": crossing,
                        },
                        "standard_errors": {name: 0.01 for name in OBSERVABLE_COLUMNS},
                        "request_sha256": [
                            str(replica) * 64 for replica in range(1, 9)
                        ],
                    }
                )
    document: dict[str, object] = {
        "schema_version": analysis.ANALYSIS_SCHEMA,
        "p0_run_spec_sha256": "a" * 64,
        "p0_progress_sha256": "b" * 64,
        "source_revision": "c" * 40,
        "analysis_plan_sha256": "d" * 64,
        "observable_columns": OBSERVABLE_COLUMNS,
        "estimates": estimates,
    }
    document["analysis_document_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


def _set_selector_value(
    values: dict[tuple[float, int, float], tuple[float, float]],
    sigma: float,
    length: int,
    kappas: tuple[float, ...],
    q_g: tuple[float, ...],
    crossing: tuple[float, ...],
) -> None:
    for kappa, q_value, crossing_value in zip(kappas, q_g, crossing, strict=True):
        values[(sigma, length, kappa)] = (q_value, crossing_value)


def _tiny_complete_pilot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str = "pilot",
    value_offset: float = 0.0,
) -> tuple[Path, dict[str, object]]:
    path = pilot._write_test_pilot_run_spec(
        tmp_path / name,
        lengths=(8, 16),
        sigmas=(1.0,),
        replicas=(0, 1),
        kappas=(0.0, 0.25, 0.5),
    )

    def deterministic_trajectory(
        request: object, _kernel: np.ndarray, _alias: object
    ) -> TrajectoryResult:
        rows = np.zeros((3, 10), dtype=np.float64)
        for kappa_index in range(3):
            base = request.length / 8 + 2 * request.replica + kappa_index + value_offset
            rows[kappa_index, 4] = base
            rows[kappa_index, 5] = base + 10
            rows[kappa_index, 8] = base + 20
            rows[kappa_index, 9] = (request.replica + kappa_index) % 2
        return TrajectoryResult(
            request_sha256=pilot.request_digest(request),
            observables=rows,
            terminal_counters=np.zeros((4, 4), dtype=np.uint32),
            draw_counts=np.zeros((4, 3), dtype=np.uint64),
            event_count=0,
            duplicate_count=0,
            hash_diagnostics=np.zeros(5, dtype=np.uint64),
        )

    monkeypatch.setattr(pilot, "run_poisson_numba", deterministic_trajectory)
    spec = pilot._load_pilot_spec(
        path, verify_current_environment=False, production=False
    )
    for cell_index in range(len(spec["cells"])):
        pilot._run_test_pilot_cell(path, cell_index)
    pilot._merge_test_pilot_progress(path)
    return path, spec


def test_aggregate_p0_groups_whole_replicas_in_canonical_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    original_loader = pilot._load_analysis_trajectory
    previous: weakref.ReferenceType[TrajectoryResult] | None = None

    def tracking_loader(
        trajectory: Path,
        expected: dict[str, str],
        required_digest: str,
    ) -> TrajectoryResult:
        nonlocal previous
        if previous is not None:
            assert previous() is None, "more than one trajectory was retained"
        result = original_loader(trajectory, expected, required_digest)
        previous = weakref.ref(result)
        return result

    monkeypatch.setattr(pilot, "_load_analysis_trajectory", tracking_loader)
    document = analysis._aggregate_test_p0(path)

    assert analysis.OBSERVABLE_COLUMNS == OBSERVABLE_COLUMNS
    assert [
        (
            estimate["sigma_hex"],
            estimate["length"],
            estimate["kappa_hex"],
        )
        for estimate in document["estimates"]
    ] == [
        ((1.0).hex(), length, kappa.hex())
        for length in (8, 16)
        for kappa in (0.0, 0.25, 0.5)
    ]
    first = document["estimates"][0]
    assert first == {
        "sigma_hex": (1.0).hex(),
        "length": 8,
        "kappa_hex": (0.0).hex(),
        "replica_count": 2,
        "means": {
            "s1_fraction": 2.0,
            "s2_fraction": 12.0,
            "q_g": 22.0,
            "four_sector_crossing": 0.5,
        },
        "standard_errors": {
            "s1_fraction": 1.0,
            "s2_fraction": 1.0,
            "q_g": 1.0,
            "four_sector_crossing": 0.5,
        },
        "request_sha256": [
            spec["cells"][0]["request_sha256"],
            spec["cells"][1]["request_sha256"],
        ],
    }


def test_aggregate_p0_binds_exact_sources_and_hashes_unsigned_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    document = analysis._aggregate_test_p0(path)
    unsigned = dict(document)
    digest = unsigned.pop("analysis_document_sha256")

    assert document["schema_version"] == "challenge-194-p0-analysis-v1"
    assert (
        document["p0_run_spec_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert (
        document["p0_progress_sha256"]
        == hashlib.sha256((path.parent / "progress.json").read_bytes()).hexdigest()
    )
    assert document["source_revision"] == spec["orchestration_revision"]
    assert document["analysis_plan_sha256"] == spec["analysis_plan_sha256"]
    assert digest == hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


@pytest.mark.parametrize("defect", ("missing", "duplicate"))
def test_aggregate_p0_rejects_missing_or_duplicate_replicas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
):
    _path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    malformed = dict(spec)
    if defect == "missing":
        malformed["cells"] = list(spec["cells"][:-1])
    else:
        malformed["protocol"] = {
            **spec["protocol"],
            "replicas": [0, 0],
        }
    with pytest.raises(RuntimeError, match=defect):
        axes = analysis._validated_axes(malformed)
        analysis._validate_cells(malformed, *axes)


@pytest.mark.parametrize(
    "defect",
    ("merged-trajectory-digest", "outer-manifest", "inner-progress"),
)
def test_aggregate_p0_rejects_forged_or_stale_verified_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    root = path.parent
    first = spec["cells"][0]
    if defect == "merged-trajectory-digest":
        target = root / "progress.json"
        document = json.loads(target.read_text(encoding="utf-8"))
        document["cells"][0]["trajectory_sha256"] = "0" * 64
    elif defect == "outer-manifest":
        target = root / first["manifest_path"]
        document = json.loads(target.read_text(encoding="utf-8"))
        document["trajectory_sha256"] = "0" * 64
    else:
        target = root / first["run_path"] / "progress.json"
        document = {"schema_version": "forged-progress"}
    target.write_bytes(_canonical_bytes(document))

    with pytest.raises(RuntimeError, match="stale|corrupt|mismatch|progress"):
        analysis._aggregate_test_p0(path)


def test_aggregate_p0_uses_retained_root_during_swap_and_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    original, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="original", value_offset=0.0
    )
    alternate, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="alternate", value_offset=1000.0
    )
    baseline = analysis._aggregate_test_p0(original)
    original_root = original.parent
    alternate_root = alternate.parent
    detached = tmp_path / "detached-original"
    events: list[str] = []

    def swap_and_restore(stage: str) -> None:
        if stage == "snapshot-verified":
            events.append(stage)
            original_root.rename(detached)
            alternate_root.rename(original_root)
        elif stage == "snapshot-closed":
            events.append(stage)
            original_root.rename(alternate_root)
            detached.rename(original_root)

    observed = analysis._aggregate_test_p0(original, _snapshot_hook=swap_and_restore)

    assert observed == baseline
    assert events == ["snapshot-verified", "snapshot-closed"]
    assert original.is_file()
    assert alternate.is_file()


def test_aggregate_p0_uses_descriptor_progress_during_swap_and_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    original, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="original", value_offset=0.0
    )
    alternate, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="alternate", value_offset=1000.0
    )
    baseline = analysis._aggregate_test_p0(original)
    progress = original.parent / "progress.json"
    saved = original.parent / "progress.saved"
    events: list[str] = []

    def swap_and_restore(stage: str) -> None:
        if stage == "snapshot-verified":
            events.append(stage)
            progress.rename(saved)
            shutil.copyfile(alternate.parent / "progress.json", progress)
        elif stage == "snapshot-closed":
            events.append(stage)
            progress.unlink()
            saved.rename(progress)

    observed = analysis._aggregate_test_p0(original, _snapshot_hook=swap_and_restore)

    assert observed == baseline
    assert events == ["snapshot-verified", "snapshot-closed"]


def _private_snapshot_parent(tmp_path: Path) -> Path:
    parent = tmp_path / "snapshots"
    parent.mkdir(mode=0o700)
    return parent


def _snapshot_window_owner(
    parent_value: str,
    window: str,
    ready: object,
    finish: object,
) -> None:
    parent = Path(parent_value)
    process_identity = pilot._snapshot_process_identity()
    token = ("a" if window == "mkdir-before-marker" else "b") * 32
    name = pilot._snapshot_directory_name(process_identity, token)
    candidate = parent / name
    candidate.mkdir(mode=0o700)
    if window == "marker-last-before-rmdir":
        marker = candidate / pilot.PILOT_SNAPSHOT_MARKER
        marker.write_bytes(
            pilot._canonical_bytes(
                pilot._snapshot_marker_document(
                    name,
                    token,
                    process_identity,
                )
            )
        )
        marker.unlink()
    ready.send((name, candidate.stat().st_ino))
    finish.recv()
    candidate.rmdir()
    ready.send("completed")


def _assert_active_snapshot_window_survives(
    parent: Path,
    window: str,
) -> None:
    context = multiprocessing.get_context("fork")
    owner_ready, cleaner_ready = context.Pipe()
    cleaner_finish, owner_finish = context.Pipe()
    owner = context.Process(
        target=_snapshot_window_owner,
        args=(str(parent), window, cleaner_ready, owner_finish),
    )
    owner.start()
    try:
        assert owner_ready.poll(10), "snapshot owner did not reach cleanup window"
        name, inode = owner_ready.recv()
        candidate = parent / name
        parent_fd = pilot._open_validated_snapshot_parent(parent)
        try:
            pilot._cleanup_stale_owned_snapshots(parent_fd)
        finally:
            pilot.os.close(parent_fd)
        assert candidate.stat().st_ino == inode
        cleaner_finish.send("finish")
        assert owner_ready.poll(10), "snapshot owner did not complete"
        assert owner_ready.recv() == "completed"
        owner.join(10)
        assert owner.exitcode == 0
        assert not candidate.exists()
    finally:
        if owner.is_alive():
            cleaner_finish.send("finish")
            owner.join(10)
        if owner.is_alive():
            owner.kill()
            owner.join(10)


def test_snapshot_preflight_rejects_aggregate_over_budget_before_payload_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    for trajectory in path.parent.glob("cells/*/run/trajectories/*.h5"):
        with trajectory.open("r+b") as stream:
            stream.truncate(40 * 1024 * 1024)
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before aggregate preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    with pytest.raises(RuntimeError, match="aggregate byte budget"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []


def test_snapshot_preflight_rejects_extra_entry_before_payload_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    (path.parent / spec["cells"][0]["cell_path"] / "unknown.bin").write_bytes(b"x")
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before layout preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    with pytest.raises(RuntimeError, match="unknown snapshot layout entry"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []


def test_snapshot_capacity_failure_occurs_before_payload_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before capacity preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    monkeypatch.setattr(
        pilot.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_bavail=0, f_frsize=4096),
    )
    with pytest.raises(RuntimeError, match="snapshot filesystem capacity"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []
    assert pilot.PILOT_SNAPSHOT_SAFETY_RESERVE_BYTES > 0


def test_snapshot_copy_global_counter_rejects_file_growth_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    request = path.parent / spec["cells"][0]["run_path"] / "request.json"
    parent = _private_snapshot_parent(tmp_path)
    stages: list[str] = []

    def grow_after_preflight(stage: str) -> None:
        if stage == "snapshot-preflighted":
            stages.append(stage)
            with request.open("ab") as stream:
                stream.write(b" ")

    with pytest.raises(RuntimeError, match="snapshot byte budget changed during copy"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=parent,
            _snapshot_hook=grow_after_preflight,
        )
    assert stages == ["snapshot-preflighted"]
    assert list(parent.iterdir()) == []


def test_snapshot_exception_removes_uniquely_owned_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    parent = _private_snapshot_parent(tmp_path)

    def fail_during_copy(stage: str) -> None:
        if stage == "snapshot-copy-start":
            raise RuntimeError("injected snapshot failure")

    with pytest.raises(RuntimeError, match="injected snapshot failure"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=parent,
            _snapshot_hook=fail_during_copy,
        )
    assert list(parent.iterdir()) == []


def test_snapshot_cleanup_removes_ownership_marker_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    parent = _private_snapshot_parent(tmp_path)
    original_unlink = pilot.os.unlink
    removed_names: list[str] = []

    def tracking_unlink(
        name: str,
        *,
        dir_fd: int | None = None,
    ) -> None:
        removed_names.append(name)
        original_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(pilot.os, "unlink", tracking_unlink)
    analysis._aggregate_test_p0(path, snapshot_parent=parent)

    assert removed_names[-1] == pilot.PILOT_SNAPSHOT_MARKER
    assert list(parent.iterdir()) == []


def test_stale_cleanup_preserves_active_mkdir_before_marker_window(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    _assert_active_snapshot_window_survives(parent, "mkdir-before-marker")


def test_stale_cleanup_preserves_active_marker_last_before_rmdir_window(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    _assert_active_snapshot_window_survives(
        parent,
        "marker-last-before-rmdir",
    )


def test_stale_cleanup_removes_proven_dead_markerless_snapshot(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    name = pilot._snapshot_directory_name(
        (2_147_483_647, f"linux-{'0' * 32}-1"),
        "c" * 32,
    )
    candidate = parent / name
    candidate.mkdir(mode=0o700)

    parent_fd = pilot._open_validated_snapshot_parent(parent)
    try:
        pilot._cleanup_stale_owned_snapshots(parent_fd)
    finally:
        pilot.os.close(parent_fd)

    assert not candidate.exists()


def test_stale_cleanup_leaves_unverifiable_markerless_snapshot(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    name = pilot._snapshot_directory_name(
        (pilot.os.getpid(), None),
        "d" * 32,
    )
    candidate = parent / name
    candidate.mkdir(mode=0o700)
    inode = candidate.stat().st_ino

    parent_fd = pilot._open_validated_snapshot_parent(parent)
    try:
        pilot._cleanup_stale_owned_snapshots(parent_fd)
    finally:
        pilot.os.close(parent_fd)

    assert candidate.stat().st_ino == inode
    candidate.rmdir()


def test_pilot_estimate_is_immutable():
    estimate = analysis.PilotEstimate(
        sigma=1.0,
        length=8,
        kappa=0.25,
        replica_count=2,
        means={"q_g": 0.5},
        standard_errors={"q_g": 0.1},
        request_sha256=("1" * 64, "2" * 64),
    )
    with pytest.raises(FrozenInstanceError):
        estimate.length = 16
    with pytest.raises(TypeError):
        estimate.means["q_g"] = 1.0


def test_select_p1_brackets_selects_unique_common_interval():
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 2.0, 4.0)
    _set_selector_value(
        values, 0.8, 16, kappas, (4.0, 2.0, 1.0, 0.0), (0.0, 0.1, 0.2, 0.9)
    )
    _set_selector_value(
        values, 0.8, 32, kappas, (3.0, 1.0, 2.0, 3.0), (0.0, 0.2, 0.8, 1.0)
    )

    selected = analysis.select_p1_brackets(
        _selector_document(sigmas=(0.8,), values=values)
    )

    assert selected["requires_p0_extension"] is False
    bracket = selected["brackets"][0]
    assert bracket["sigma_hex"] == (0.8).hex()
    assert bracket["lower_kappa_hex"] == (1.0).hex()
    assert bracket["upper_kappa_hex"] == (2.0).hex()
    assert bracket["lengths"] == [16, 32]
    assert bracket["estimator_evidence"]["q_g"]["marked"] is True
    assert bracket["estimator_evidence"]["four_sector_crossing"]["marked"] is True
    assert bracket["tie_break"] == {
        "rule": "narrowest_interval_then_lower_coupling",
        "candidate_count": 1,
        "selected_width_hex": (1.0).hex(),
    }


def test_select_p1_brackets_breaks_common_interval_ties_deterministically():
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 3.0, 5.0, 8.0)
    for length, q_g in (
        (16, (9.0, 3.0, 1.0, 3.0, 3.0)),
        (32, (8.0, 1.0, 2.0, 1.0, 2.0)),
    ):
        _set_selector_value(
            values,
            0.8,
            length,
            kappas,
            q_g,
            (0.0, 0.2, 0.8, 0.2, 0.8),
        )

    selected = analysis.select_p1_brackets(
        _selector_document(sigmas=(0.8,), kappas=kappas, values=values)
    )

    bracket = selected["brackets"][0]
    assert bracket["lower_kappa_hex"] == (1.0).hex()
    assert bracket["upper_kappa_hex"] == (3.0).hex()
    assert bracket["tie_break"]["candidate_count"] == 2


def test_select_p1_brackets_requests_extension_without_common_interval():
    selected = analysis.select_p1_brackets(_selector_document(sigmas=(0.8,), values={}))

    assert selected["requires_p0_extension"] is True
    assert selected["brackets"] == [
        {
            "sigma_hex": (0.8).hex(),
            "status": "requires_p0_extension",
            "reason": "no_nonzero_interval_marked_by_both_estimators",
            "lengths": [16, 32],
        }
    ]


def test_select_p1_brackets_uses_maximum_control_slope():
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 3.0, 5.0)
    _set_selector_value(
        values,
        1.1,
        32,
        kappas,
        (1.0, 1.0, 1.0, 1.0),
        (0.0, 0.1, 0.9, 1.0),
    )

    selected = analysis.select_p1_brackets(
        _selector_document(sigmas=(1.1,), kappas=kappas, values=values)
    )

    bracket = selected["brackets"][0]
    assert bracket["purpose"] == "crossover_refinement"
    assert bracket["lower_kappa_hex"] == (1.0).hex()
    assert bracket["upper_kappa_hex"] == (3.0).hex()
    assert bracket["estimator_evidence"]["absolute_slope_hex"] == (0.4).hex()
    assert bracket["tie_break"]["rule"] == "maximum_absolute_slope_then_lower_coupling"


@pytest.mark.parametrize(
    ("defect", "match"),
    (
        ("zero-only", "zero-coupling"),
        ("reordered", "canonical coupling order"),
        ("nan", "finite"),
        ("missing-largest", "largest-size estimates"),
    ),
)
def test_select_p1_brackets_rejects_malformed_evidence(defect: str, match: str):
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 2.0, 4.0)
    if defect == "zero-only":
        _set_selector_value(
            values,
            0.8,
            16,
            kappas,
            (2.0, 1.0, 1.0, 1.0),
            (0.2, 0.8, 0.8, 0.8),
        )
        _set_selector_value(
            values,
            0.8,
            32,
            kappas,
            (1.0, 2.0, 2.0, 2.0),
            (0.2, 0.8, 0.8, 0.8),
        )
    document = _selector_document(sigmas=(0.8,), values=values)
    estimates = document["estimates"]
    assert isinstance(estimates, list)
    if defect == "reordered":
        estimates[5], estimates[6] = estimates[6], estimates[5]
    elif defect == "nan":
        estimates[-1]["means"]["q_g"] = float("nan")
    elif defect == "missing-largest":
        estimates.pop()
    if defect not in ("zero-only", "nan"):
        unsigned = dict(document)
        unsigned.pop("analysis_document_sha256")
        document["analysis_document_sha256"] = hashlib.sha256(
            _canonical_bytes(unsigned)
        ).hexdigest()

    with pytest.raises(RuntimeError, match=match):
        analysis.select_p1_brackets(document)
