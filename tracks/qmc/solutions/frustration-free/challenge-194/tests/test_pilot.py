from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

import pytest

import long_range_percolation.pilot as pilot
from long_range_percolation.pilot import (
    PilotCell,
    merge_pilot_progress,
    pending_pilot_cells,
    verify_pilot_download,
)


def _tiny_spec(tmp_path: Path, *, replicas: tuple[int, ...] = (0,)) -> Path:
    root = tmp_path / "pilot"
    return pilot._write_test_pilot_run_spec(
        root,
        lengths=(8,),
        sigmas=(1.0,),
        replicas=replicas,
        kappas=(0.0, 0.25),
    )


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
    assert verify_pilot_download(path)["cell_count"] == 1

    copied = tmp_path / "downloaded"
    shutil.copytree(path.parent, copied)
    assert verify_pilot_download(copied / "run_spec.json")["cell_count"] == 1


def test_duplicate_execution_has_one_equivalent_verified_winner(tmp_path: Path):
    path = _tiny_spec(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: pilot._run_test_pilot_cell(path, 0), range(2)))
    assert results[0] == results[1]
    run = next((path.parent / "cells").iterdir()) / "run"
    assert len(list((run / "trajectories").glob("trajectory-*.h5"))) == 1
    assert len(list((run / "batches").glob("batch-*.json"))) == 1


def test_resume_after_trajectory_publication_finishes_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = _tiny_spec(tmp_path)

    def stop(stage: str) -> None:
        if stage == "after-trajectory":
            raise RuntimeError("injected stop")

    with pytest.raises(RuntimeError, match="injected stop"):
        pilot._run_test_pilot_cell(path, 0, crash_hook=stop)
    run = next((path.parent / "cells").iterdir()) / "run"
    assert list((run / "trajectories").glob("trajectory-*.h5"))
    assert not list((run / "batches").glob("batch-*.json"))
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
    assert pending_pilot_cells(path, verify_current_environment=False) == [0, 1]
    pilot._run_test_pilot_cell(path, 0)
    assert pending_pilot_cells(path, verify_current_environment=False) == [1]
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
    path = _tiny_spec(tmp_path)
    document = json.loads(path.read_text())
    document["uv_lock_sha256"] = "0" * 64
    document["run_spec_sha256"] = pilot._document_hash(document, "run_spec_sha256")
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError, match="uv.lock"):
        pilot.load_pilot_run_spec(path, verify_current_environment=False)


@pytest.mark.parametrize("kind", ("source", "runtime", "engine", "analysis"))
def test_current_environment_rejects_every_bound_provenance_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
):
    path = _tiny_spec(tmp_path)
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
