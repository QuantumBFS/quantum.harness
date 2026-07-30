from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "cpmc_lab_fig4" / "finalize_cpmc_fig4abc.py"
SPEC = importlib.util.spec_from_file_location("cpmc_finalizer", SCRIPT)
assert SPEC and SPEC.loader
finalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalizer)


ENERGIES = (
    -18.578624239043,
    -16.601405,
    -15.015970,
    -13.767692,
    -12.792335,
    -12.032910,
    -11.435664,
    -10.956222,
    -10.564015,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _make_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    (run_dir / "figs").mkdir(parents=True)
    run_json = {
        "model": {"couplings": {"$U/t$": "0,2,4,6,8"}},
        "scope": {"label": "old"},
        "method": {"tool": "old", "settings": {}, "note": "old"},
        "actual": [], "risks": [], "figures": [],
    }
    (run_dir / "run.json").write_text(json.dumps(run_json), encoding="utf-8")
    for point in finalizer.POINTS:
        point_dir = run_dir / "raw" / point
        point_dir.mkdir(parents=True)
        is_smoke = point == "smoke"
        u = 4 if is_smoke else int(point[1:])
        energy = -2.4426 if is_smoke else ENERGIES[u]
        block_count = 20 if is_smoke else 150
        marker = {
            "status": "complete", "point": point, "U_over_t": u,
            "seed": 1729, "energy": energy, "stderr": 0.001,
            "wall_seconds": 1.0, "accepted": True, "mat_file": "result.mat",
        }
        (point_dir / "DONE.json").write_text(json.dumps(marker), encoding="utf-8")
        (point_dir / "result.mat").write_bytes(b"test fixture")
        summary = {field: marker[field] for field in (
            "point", "U_over_t", "seed", "energy", "stderr", "wall_seconds", "accepted", "mat_file"
        )}
        summary["accepted"] = 1
        _write_csv(
            point_dir / "summary.csv",
            ["point", "U_over_t", "seed", "energy", "stderr", "wall_seconds", "accepted", "mat_file"],
            [summary],
        )
        _write_csv(
            point_dir / "block_energies.csv", ["block", "energy"],
            [{"block": index + 1, "energy": energy} for index in range(block_count)],
        )
    return run_dir


def test_finalizer_builds_all_panels_diagnostics_and_manifest(tmp_path):
    run_dir = _make_run(tmp_path)
    assert finalizer.main([str(run_dir)]) == 0
    for name in (
        "fig4a_total_energy.svg", "fig4b_potential_double_occupancy.svg",
        "fig4c_kinetic.svg",
    ):
        assert (run_dir / "figs" / name).is_file()
    assert (run_dir / "mc_diagnostics.csv").is_file()
    assert (run_dir / "artifact_manifest.json").is_file()
    data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert [figure["id"] for figure in data["figures"]] == [
        "Figure 4(a), full integer grid",
        "Figure 4(b), full integer grid",
        "Figure 4(c), full integer grid",
    ]
    assert all(figure["results"]["match"] == "yes" for figure in data["figures"])


def test_finalizer_rejects_partial_marker_and_removes_stale_finalized(tmp_path):
    run_dir = _make_run(tmp_path)
    (run_dir / "FINALIZED.txt").write_text("stale", encoding="utf-8")
    marker_path = run_dir / "raw" / "u4" / "DONE.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["status"] = "partial"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(RuntimeError, match="not complete"):
        finalizer.main([str(run_dir)])
    assert not (run_dir / "FINALIZED.txt").exists()


def test_finalizer_rejects_nonfinite_block(tmp_path):
    run_dir = _make_run(tmp_path)
    block_path = run_dir / "raw" / "u6" / "block_energies.csv"
    rows = list(csv.DictReader(block_path.open(encoding="utf-8")))
    rows[4]["energy"] = "NaN"
    _write_csv(block_path, ["block", "energy"], rows)
    with pytest.raises(RuntimeError, match="non-finite"):
        finalizer.main([str(run_dir)])


def test_finalizer_fails_scientific_mismatch_without_finalized_marker(tmp_path):
    run_dir = _make_run(tmp_path)
    (run_dir / "FINALIZED.txt").write_text("stale", encoding="utf-8")
    point_dir = run_dir / "raw" / "u4"
    marker_path = point_dir / "DONE.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["energy"] += 2.0
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    rows = list(csv.DictReader((point_dir / "summary.csv").open(encoding="utf-8")))
    rows[0]["energy"] = marker["energy"]
    _write_csv(point_dir / "summary.csv", list(rows[0]), rows)
    blocks = [{"block": index + 1, "energy": marker["energy"]} for index in range(150)]
    _write_csv(point_dir / "block_energies.csv", ["block", "energy"], blocks)
    with pytest.raises(RuntimeError, match="scientific comparison gate failed"):
        finalizer.main([str(run_dir)])
    assert not (run_dir / "FINALIZED.txt").exists()


def test_three_vs_five_point_difference_is_recorded_as_systematic(tmp_path):
    run_dir = _make_run(tmp_path)
    rows = {point: finalizer.read_summary(run_dir, point) for point in finalizer.POINTS}
    derived = finalizer.derive_observables(rows, finalizer.read_ed_reference())
    assert derived[4]["potential_fd_systematic"] > 0
    assert derived[4]["potential_total_uncertainty"] >= derived[4]["potential_fd_systematic"]
