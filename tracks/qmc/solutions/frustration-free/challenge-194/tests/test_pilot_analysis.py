from __future__ import annotations

import hashlib
import json
import shutil
import weakref
from dataclasses import FrozenInstanceError
from pathlib import Path

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
