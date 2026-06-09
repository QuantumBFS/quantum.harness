"""Tests for the mechanical stages of scripts/parameter_scan.py."""

import json
from pathlib import Path

import pytest

import parameter_scan as ps


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # single-line per the testing convention
    path.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")


def _make_manifest(run_dir: Path, cell_id: str, manifest: dict) -> None:
    cell = run_dir / "cells" / cell_id
    cell.mkdir(parents=True, exist_ok=True)
    _write_json(cell / "manifest.json", manifest)


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #
def test_plan_cell_count_and_id_format(tmp_path):
    axes = {"L": [8, 12, 16], "U": [2.0, 4.0]}
    run_dir = tmp_path / "run"
    spec = ps.build_plan(axes, "run", str(run_dir), {"chi": 100}, {"src": ["x"]})
    assert len(spec["cells"]) == 6
    assert spec["cells"][0]["cell_id"] == "cell-0001"
    assert spec["cells"][-1]["cell_id"] == "cell-0006"
    # Cartesian order: L varies slowest (insertion order preserved)
    assert spec["cells"][0]["params"] == {"L": 8, "U": 2.0}
    assert spec["cells"][1]["params"] == {"L": 8, "U": 4.0}
    assert spec["cells"][2]["params"] == {"L": 12, "U": 2.0}
    assert spec["settings"] == {"chi": 100}
    assert spec["provenance"] == {"src": ["x"]}


def test_plan_cli_writes_valid_run_spec(tmp_path, capsys):
    axes_file = tmp_path / "axes.json"
    _write_json(axes_file, {"a": [1, 2], "b": [10, 20, 30]})
    settings_file = tmp_path / "settings.json"
    _write_json(settings_file, {"knob": 5})
    prov_file = tmp_path / "prov.json"
    _write_json(prov_file, {"hash": "abc"})
    run_dir = tmp_path / "results" / "myrun"

    ps.main(
        [
            "plan",
            "--axes",
            str(axes_file),
            "--run-id",
            "myrun",
            "--run-dir",
            str(run_dir),
            "--settings",
            str(settings_file),
            "--provenance",
            str(prov_file),
        ]
    )
    out = capsys.readouterr().out
    assert "planned 6 cells" in out

    spec = json.loads((run_dir / "run_spec.json").read_text())
    assert spec["run_id"] == "myrun"
    assert spec["settings"] == {"knob": 5}
    assert spec["provenance"] == {"hash": "abc"}
    assert len(spec["cells"]) == 6
    plan = json.loads((run_dir / "parameter-scan.plan.json").read_text())
    assert plan["axes"] == {"a": [1, 2], "b": [10, 20, 30]}


def test_plan_default_run_dir_and_no_optionals(tmp_path, monkeypatch, capsys):
    axes_file = tmp_path / "axes.json"
    _write_json(axes_file, {"x": [1]})
    monkeypatch.chdir(tmp_path)
    ps.main(["plan", "--axes", str(axes_file), "--run-id", "defrun"])
    spec = json.loads((tmp_path / "results" / "defrun" / "run_spec.json").read_text())
    assert spec["settings"] == {}
    assert spec["provenance"] == {}


def test_plan_rejects_non_object_axes(tmp_path):
    axes_file = tmp_path / "axes.json"
    _write_json(axes_file, [1, 2, 3])
    with pytest.raises(SystemExit):
        ps.main(["plan", "--axes", str(axes_file), "--run-id", "r", "--run-dir", str(tmp_path)])


# --------------------------------------------------------------------------- #
# collect
# --------------------------------------------------------------------------- #
def _base_spec(run_dir: Path) -> dict:
    return {
        "run_id": "r",
        "run_dir": str(run_dir),
        "settings": {"chi": 100, "tol": 1e-8},
        "provenance": {"hash": "abc"},
        "cells": [
            {"cell_id": "cell-0001", "params": {"L": 8}},
            {"cell_id": "cell-0002", "params": {"L": 12}},
            {"cell_id": "cell-0003", "params": {"L": 16}},
            {"cell_id": "cell-0004", "params": {"L": 20}},
        ],
    }


def test_collect_classifies_all_statuses(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    # cell-0001 success, cell-0002 failed, cell-0003 missing manifest, cell-0004 pending (no dir)
    _make_manifest(run_dir, "cell-0001", {"converged": True, "energy": -1.0})
    _make_manifest(run_dir, "cell-0002", {"converged": False, "energy": -0.5})
    (run_dir / "cells" / "cell-0003").mkdir(parents=True)  # dir, no manifest

    report = ps.collect(spec, run_dir, "converged", "true", ["energy"])
    sc = report["status_counts"]
    assert sc == {"success": 1, "failed": 1, "missing": 1, "pending": 1}
    # every planned cell present in rows
    assert len(report["rows"]) == 4
    ids = [r["cell_id"] for r in report["rows"]]
    assert ids == ["cell-0001", "cell-0002", "cell-0003", "cell-0004"]
    statuses = {r["cell_id"]: r["status"] for r in report["rows"]}
    assert statuses["cell-0001"] == "success"
    assert statuses["cell-0002"] == "failed"
    assert statuses["cell-0003"] == "missing"
    assert statuses["cell-0004"] == "pending"
    # value field pulled
    assert report["rows"][0]["energy"] == -1.0
    # missing/pending get empty value column
    assert report["rows"][2]["energy"] == ""
    assert report["rows"][3]["energy"] == ""


def test_collect_no_success_field_means_present_is_success(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    _make_manifest(run_dir, "cell-0001", {"energy": -1.0})
    report = ps.collect(spec, run_dir, None, "true", [])
    assert report["status_counts"]["success"] == 1


def test_collect_success_field_missing_in_manifest_is_failed(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    _make_manifest(run_dir, "cell-0001", {"energy": -1.0})  # no 'converged'
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert report["status_counts"]["failed"] == 1


def test_collect_constant_vs_varying_settings(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    # echoed settings: chi constant, tol varies
    _make_manifest(run_dir, "cell-0001", {"converged": True, "settings": {"chi": 100, "tol": 1e-8}})
    _make_manifest(run_dir, "cell-0002", {"converged": True, "settings": {"chi": 100, "tol": 1e-6}})
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert report["constant_settings"] == {"chi": "100"}
    assert "tol" in report["varying_settings"]
    assert len(report["varying_settings"]["tol"]) == 2


def test_collect_consensus_violation(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {"consensus_fields": ["protocol"]}
    _make_manifest(run_dir, "cell-0001", {"converged": True, "protocol": "A"})
    _make_manifest(run_dir, "cell-0002", {"converged": True, "protocol": "B"})
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert any("protocol" in v for v in report["consensus_violations"])


def test_collect_no_consensus_violation_when_constant(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {"consensus_fields": ["protocol"]}
    _make_manifest(run_dir, "cell-0001", {"converged": True, "protocol": "A"})
    _make_manifest(run_dir, "cell-0002", {"converged": True, "protocol": "A"})
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert report["consensus_violations"] == []


def test_collect_manifest_contract_checks(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {
        "manifest_contract": {
            "energy": {"type": "bounds", "min": -2.0, "max": 0.0},
            "method": {"type": "membership", "values": ["dmrg", "ed"]},
            "label": {"type": "nonempty"},
            "tag": {"type": "equality", "value": "v1"},
            "evidence": {"type": "evidence-set", "members": ["limit", "symmetry"]},
            "optional_x": {"type": "optional"},
        }
    }
    # cell-0001 all good
    _make_manifest(
        run_dir,
        "cell-0001",
        {
            "converged": True,
            "energy": -1.0,
            "method": "dmrg",
            "label": "ok",
            "tag": "v1",
            "evidence": ["limit", "symmetry"],
        },
    )
    # cell-0002 violates several
    _make_manifest(
        run_dir,
        "cell-0002",
        {
            "converged": True,
            "energy": 5.0,  # out of bounds
            "method": "qmc",  # not in membership
            "label": "",  # empty
            "tag": "v2",  # not equal
            "evidence": ["limit"],  # missing symmetry
        },
    )
    report = ps.collect(spec, run_dir, "converged", "true", [])
    v = "\n".join(report["contract_violations"])
    assert "cell-0002: energy" in v
    assert "cell-0002: method" in v
    assert "cell-0002: label" in v
    assert "cell-0002: tag" in v
    assert "cell-0002: evidence" in v
    # cell-0001 should not appear
    assert "cell-0001" not in v


def test_collect_contract_bounds_nonnumeric_and_missing_required(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {
        "manifest_contract": {
            "energy": {"type": "bounds", "min": 0.0},
            "must": {"type": "required"},
        }
    }
    _make_manifest(run_dir, "cell-0001", {"converged": True, "energy": "notnum"})
    report = ps.collect(spec, run_dir, "converged", "true", [])
    v = "\n".join(report["contract_violations"])
    assert "not numeric" in v
    assert "must: missing" in v


def test_collect_provenance_violation(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {"provenance_fields": ["provenance.hash"]}
    _make_manifest(run_dir, "cell-0001", {"converged": True, "provenance": {"hash": "WRONG"}})
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert any("hash" in v for v in report["provenance_violations"])


def test_collect_cli_writes_csv_with_every_cell(tmp_path, capsys):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec_path = run_dir / "run_spec.json"
    _write_json(spec_path, spec)
    _make_manifest(run_dir, "cell-0001", {"converged": True, "energy": -1.0})
    _make_manifest(run_dir, "cell-0002", {"converged": False, "energy": -0.5})

    ps.main(
        [
            "collect",
            "--run-spec",
            str(spec_path),
            "--success-field",
            "converged",
            "--value-field",
            "energy",
        ]
    )
    out = capsys.readouterr().out
    assert "success=1 failed=1 missing=0 pending=2" in out
    csv_text = (run_dir / "parameter-scan.csv").read_text()
    lines = csv_text.strip().splitlines()
    assert lines[0].split(",") == ["cell_id", "L", "status", "energy"]
    # 4 planned cells -> 4 data rows
    assert len(lines) == 5


def test_collect_cli_reports_violations(tmp_path, capsys):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {"consensus_fields": ["protocol"]}
    spec_path = run_dir / "run_spec.json"
    _write_json(spec_path, spec)
    _make_manifest(run_dir, "cell-0001", {"converged": True, "protocol": "A"})
    _make_manifest(run_dir, "cell-0002", {"converged": True, "protocol": "B"})
    ps.main(["collect", "--run-spec", str(spec_path), "--success-field", "converged"])
    out = capsys.readouterr().out
    assert "CONSENSUS VIOLATION" in out


def test_collect_cli_relative_rundir_falls_back_to_spec_dir(tmp_path, capsys):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["run_dir"] = "results/nonexistent-relative"
    spec_path = run_dir / "run_spec.json"
    _write_json(spec_path, spec)
    _make_manifest(run_dir, "cell-0001", {"converged": True})
    ps.main(["collect", "--run-spec", str(spec_path), "--success-field", "converged"])
    # CSV should land next to the spec, not at the bogus relative path
    assert (run_dir / "parameter-scan.csv").exists()


def test_collect_provenance_bare_field_name(tmp_path):
    # provenance_fields given as a bare key resolves against shared_prov directly
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec["assemble"] = {"provenance_fields": ["hash"]}
    _make_manifest(run_dir, "cell-0001", {"converged": True, "hash": "WRONG"})
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert any("hash" in v for v in report["provenance_violations"])


def test_collect_cli_prints_constant_settings(tmp_path, capsys):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    spec_path = run_dir / "run_spec.json"
    _write_json(spec_path, spec)
    _make_manifest(run_dir, "cell-0001", {"converged": True, "settings": {"chi": 100}})
    _make_manifest(run_dir, "cell-0002", {"converged": True, "settings": {"chi": 100}})
    ps.main(["collect", "--run-spec", str(spec_path), "--success-field", "converged"])
    out = capsys.readouterr().out
    assert "constant settings" in out


def test_collect_corrupt_manifest_is_missing(tmp_path):
    run_dir = tmp_path / "run"
    spec = _base_spec(run_dir)
    cell = run_dir / "cells" / "cell-0001"
    cell.mkdir(parents=True)
    (cell / "manifest.json").write_text("{not valid json", encoding="utf-8")
    report = ps.collect(spec, run_dir, "converged", "true", [])
    assert report["status_counts"]["missing"] == 1


# --------------------------------------------------------------------------- #
# shape
# --------------------------------------------------------------------------- #
def _rows(x_vals, y_vals, x_name="x", y_name="y"):
    return [{x_name: str(x), y_name: str(y)} for x, y in zip(x_vals, y_vals)]


def test_shape_monotone():
    rows = _rows([1, 2, 3, 4], [1.0, 2.5, 3.1, 3.9])
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Monotone"
    assert res["all"]["metric"] == "increasing"


def test_shape_asymptoting():
    rows = _rows([1, 2, 3, 4, 5], [0.0, 1.0, 1.5, 1.75, 1.875])
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Asymptoting"


def test_shape_power_law_like():
    xs = [1.0, 2.0, 4.0, 8.0, 16.0]
    ys = [x**2.0 for x in xs]
    rows = _rows(xs, ys)
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Power-law-like"


def test_shape_extremum():
    rows = _rows([1, 2, 3, 4, 5], [0.0, 1.0, 2.0, 1.0, 0.0])
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Extremum"


def test_shape_step_like():
    rows = _rows([1, 2, 3, 4, 5], [1.0, 1.05, 5.0, 5.05, 5.1])
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Step-like"


def test_shape_crossing():
    rows = []
    # series A increasing, series B decreasing -> they cross
    for x, y in zip([1, 2, 3], [0.0, 1.0, 2.0]):
        rows.append({"x": str(x), "y": str(y), "s": "A"})
    for x, y in zip([1, 2, 3], [2.0, 1.0, 0.0]):
        rows.append({"x": str(x), "y": str(y), "s": "B"})
    res = ps.shape_from_csv(rows, "x", "y", "s")
    assert "_crossing" in res
    assert res["_crossing"]["label"] == "Crossing"
    assert "A" in res and "B" in res


def test_shape_drifting():
    rows = _rows([1, 2, 3, 4, 5], [0.0, 1.0, -1.0, 2.0, -2.0])
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Drifting/oscillating"


def test_shape_insufficient_points():
    rows = _rows([1], [1.0])
    res = ps.shape_from_csv(rows, "x", "y", None)
    assert res["all"]["label"] == "Drifting/oscillating"
    assert res["all"]["metric"] == "insufficient-points"


def test_shape_cli(tmp_path, capsys):
    csv_path = tmp_path / "scan.csv"
    csv_path.write_text("x,y\n1,0.0\n2,5.0\n3,5.5\n", encoding="utf-8")
    ps.main(["shape", "--csv", str(csv_path), "--x-axis", "x", "--value-col", "y"])
    out = capsys.readouterr().out
    assert "shape:" in out
    payload = json.loads(out.splitlines()[0])
    assert "all" in payload and "label" in payload["all"]


# --------------------------------------------------------------------------- #
# plot
# --------------------------------------------------------------------------- #
def test_plot_arity_1(tmp_path):
    rows = _rows([1, 2, 3, 4], [1.0, 2.0, 3.0, 4.0])
    out = tmp_path / "p1.png"
    ps.plot_from_csv(rows, ["x"], "y", None, out)
    assert out.exists() and out.stat().st_size > 0


def test_plot_arity_1_with_errorbar(tmp_path):
    rows = [{"x": str(x), "y": str(x * 1.0), "e": "0.1"} for x in [1, 2, 3]]
    out = tmp_path / "p1e.png"
    ps.plot_from_csv(rows, ["x"], "y", "e", out)
    assert out.exists()


def test_plot_arity_2(tmp_path):
    rows = []
    for s in ["10", "20"]:
        for x in [1, 2, 3]:
            rows.append({"x": str(x), "s": s, "y": str(x + int(s))})
    out = tmp_path / "p2.png"
    ps.plot_from_csv(rows, ["x", "s"], "y", None, out)
    assert out.exists()


def test_plot_arity_3_heatmap(tmp_path):
    rows = []
    for a in [1, 2, 3]:
        for b in [10, 20]:
            for c in [100]:
                rows.append({"a": str(a), "b": str(b), "c": str(c), "y": str(a * b)})
    out = tmp_path / "p3.png"
    ps.plot_from_csv(rows, ["a", "b", "c"], "y", None, out)
    assert out.exists()


def test_plot_cli_with_comma_axes(tmp_path, capsys):
    csv_path = tmp_path / "scan.csv"
    csv_path.write_text("x,y\n1,1.0\n2,2.0\n3,3.0\n", encoding="utf-8")
    out = tmp_path / "out.png"
    ps.main(["plot", "--csv", str(csv_path), "--axes", "x", "--value-col", "y", "--out", str(out)])
    printed = capsys.readouterr().out.strip()
    assert printed == str(out)
    assert out.exists()


def test_plot_cli_with_axes_file(tmp_path):
    csv_path = tmp_path / "scan.csv"
    csv_path.write_text("x,y\n1,1.0\n2,2.0\n", encoding="utf-8")
    axes_file = tmp_path / "axes.json"
    axes_file.write_text(json.dumps({"x": [1, 2]}), encoding="utf-8")
    out = tmp_path / "outf.png"
    ps.main(
        [
            "plot",
            "--csv",
            str(csv_path),
            "--axes",
            str(axes_file),
            "--value-col",
            "y",
            "--out",
            str(out),
        ]
    )
    assert out.exists()


def test_resolve_axes_rejects_non_object_file(tmp_path):
    axes_file = tmp_path / "axes.json"
    axes_file.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(SystemExit):
        ps._resolve_axes(str(axes_file))


def test_plot_default_out(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / "scan.csv"
    csv_path.write_text("x,y\n1,1.0\n2,2.0\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ps.main(["plot", "--csv", str(csv_path), "--axes", "x", "--value-col", "y"])
    assert (tmp_path / "parameter-scan.png").exists()
