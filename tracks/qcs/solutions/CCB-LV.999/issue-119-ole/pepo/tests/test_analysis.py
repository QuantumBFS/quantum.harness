"""Behavioral tests for the PEPO two-axis convergence analysis."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


OLE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
ANALYZER_SCRIPT = OLE_ROOT / "scripts" / "analyze_pepo.py"
SCAN_SCRIPT = WORKSPACE_ROOT / "scripts" / "parameter_scan.py"
ARRAY_SCRIPT = OLE_ROOT / "scripts" / "run_pepo_array_cell.py"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ANALYZER = _load_script("analyze_pepo_test", ANALYZER_SCRIPT)
ARRAY_RUNNER = _load_script("run_pepo_array_cell_analysis_test", ARRAY_SCRIPT)


BP_MEAN = 0.8183229131612796
BP_BUDGET = 0.0044
TARGET = 0.001


def _records() -> list[dict[str, float]]:
    return [
        {"dop": 2, "chi_env": 64, "value": 0.8179},
        {"dop": 4, "chi_env": 64, "value": 0.8182},
        {"dop": 8, "chi_env": 16, "value": 0.8180},
        {"dop": 8, "chi_env": 32, "value": 0.8183},
        {"dop": 8, "chi_env": 64, "value": 0.8185},
    ]


def test_assess_convergence_uses_last_two_axis_displacements():
    """Breaks if the empirical envelope is not ΔDop + Δχenv at the corner."""

    assessment = ANALYZER.assess_convergence(
        _records(),
        bp_mean=BP_MEAN,
        bp_budget=BP_BUDGET,
        target=TARGET,
    )

    assert assessment["delta_dop"] == pytest.approx(0.0003)
    assert assessment["delta_chi_env"] == pytest.approx(0.0002)
    assert assessment["epsilon_pepo"] == pytest.approx(0.0005)
    assert assessment["corner"] == {"dop": 8, "chi_env": 64, "value": 0.8185}
    assert assessment["internally_converged"] is True
    assert assessment["agrees_with_bp"] is True
    assert assessment["comparison_status"] == "agreement"


def test_assess_convergence_refuses_missing_completed_corner():
    """Breaks if an absent Dmax/χmax cell can be silently analyzed as a corner."""

    records = [record for record in _records() if record["dop"] != 8 or record["chi_env"] != 64]

    with pytest.raises(ValueError, match="corner"):
        ANALYZER.assess_convergence(records, BP_MEAN, BP_BUDGET, TARGET)


def test_assess_convergence_requires_three_levels_on_both_axes():
    """Breaks if two-point cuts can be labelled a stable convergence trend."""

    records = [record for record in _records() if record["dop"] != 2]

    with pytest.raises(ValueError, match="three distinct"):
        ANALYZER.assess_convergence(records, BP_MEAN, BP_BUDGET, TARGET)


def test_assess_convergence_marks_growing_last_difference_unresolved():
    """Breaks if a worsening final χenv displacement still passes convergence."""

    records = _records()
    records[-1]["value"] = 0.8191

    assessment = ANALYZER.assess_convergence(records, BP_MEAN, BP_BUDGET, TARGET)

    assert assessment["trend"]["chi_env"]["growing"] is True
    assert assessment["internally_converged"] is False
    assert assessment["comparison_status"] == "diagnostic"


def test_assess_convergence_rejects_empirical_envelope_above_target():
    """Breaks if a ΔDop + Δχenv budget over 0.001 is declared converged."""

    records = [
        {"dop": 2, "chi_env": 64, "value": 0.8166},
        {"dop": 4, "chi_env": 64, "value": 0.8173},
        {"dop": 8, "chi_env": 16, "value": 0.8166},
        {"dop": 8, "chi_env": 32, "value": 0.8173},
        {"dop": 8, "chi_env": 64, "value": 0.8179},
    ]

    assessment = ANALYZER.assess_convergence(records, BP_MEAN, BP_BUDGET, TARGET)

    assert assessment["epsilon_pepo"] == pytest.approx(0.0012)
    assert assessment["internally_converged"] is False


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _manifest(record: dict[str, float], *, status: str = "success", quimb: str = "3c89529fe0a3487133a3928201691161e110abdf") -> dict:
    return {
        "status": status,
        "params": {"dop": int(record["dop"]), "chi_env": int(record["chi_env"])},
        "settings": {
            "delta": 0.15,
            "observable_sites": [52, 59, 72],
            "evolution_cutoff": 1e-12,
            "contraction_cutoff": 1e-12,
        },
        "provenance": {
            "qasm_sha256": "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455",
            "quimb_commit": quimb,
        },
        "result": {"value_real": record["value"], "value_imag": 0.0},
    }


def _write_run(tmp_path: Path, *, changed_quimb: bool = False) -> Path:
    run_dir = tmp_path / "results" / "issue119-pepo-analysis"
    cells = []
    for index, record in enumerate(_records(), start=1):
        cell_id = f"cell-{index:04d}"
        cells.append({"cell_id": cell_id, "params": {"dop": int(record["dop"]), "chi_env": int(record["chi_env"])}})
        quimb = "different" if changed_quimb and index == 2 else "3c89529fe0a3487133a3928201691161e110abdf"
        _write_json(run_dir / "cells" / cell_id / "manifest.json", _manifest(record, quimb=quimb))
    failed_id = "cell-0006"
    cells.append({"cell_id": failed_id, "params": {"dop": 2, "chi_env": 16}})
    _write_json(run_dir / "cells" / failed_id / "manifest.json", _manifest({"dop": 2, "chi_env": 16, "value": 0.0}, status="failure"))
    _write_json(
        run_dir / "run_spec.json",
        {
            "run_id": "issue119-pepo-analysis",
            "run_dir": str(run_dir),
            "settings": {
                "delta": 0.15,
                "observable_sites": [52, 59, 72],
                "evolution_cutoff": 1e-12,
                "contraction_cutoff": 1e-12,
            },
            "provenance": {
                "qasm_sha256": "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455",
                "quimb_commit": "3c89529fe0a3487133a3928201691161e110abdf",
            },
            "cells": cells,
        },
    )
    return run_dir


def test_analyze_run_writes_auditable_records_report_and_two_cut_figure(tmp_path: Path):
    """Breaks if failed cells vanish or the declared analysis artifacts are absent."""

    run_dir = _write_run(tmp_path)
    output_dir = tmp_path / "analysis"

    assessment = ANALYZER.analyze_run_directories(
        [run_dir],
        output_dir=output_dir,
        bp_mean=BP_MEAN,
        bp_budget=BP_BUDGET,
        target=TARGET,
    )

    assert assessment["status_counts"] == {"success": 5, "failed": 1, "missing": 0, "pending": 0}
    assert assessment["successful_record_count"] == 5
    assert assessment["failed_or_incomplete_cells"] == [
        {"cell_id": "cell-0006", "status": "failed", "run_dir": str(run_dir)}
    ]
    persisted = json.loads((output_dir / "assessment.json").read_text(encoding="utf-8"))
    assert persisted["epsilon_pepo"] == pytest.approx(0.0005)
    assert (run_dir / "parameter-scan.csv").is_file()
    assert (output_dir / "PEPO_49Q_VALIDATION.md").read_text(encoding="utf-8").count("empirical") >= 1
    assert (output_dir / "pepo-convergence.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (output_dir / "pepo-convergence.pdf").read_bytes().startswith(b"%PDF")


def test_analyze_run_rejects_inconsistent_successful_provenance(tmp_path: Path):
    """Breaks if incompatible successful environments are combined into one estimate."""

    run_dir = _write_run(tmp_path, changed_quimb=True)

    with pytest.raises(ValueError, match="quimb"):
        ANALYZER.analyze_run_directories(
            [run_dir],
            output_dir=tmp_path / "analysis",
            bp_mean=BP_MEAN,
            bp_budget=BP_BUDGET,
            target=TARGET,
        )


def test_analyze_run_detects_delta_overridden_by_a_control_axis(tmp_path: Path):
    """Breaks if a per-cell δ=0 control is mistaken for shared δ=0.15."""

    run_dir = _write_run(tmp_path)
    spec_path = run_dir / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    control = {"dop": 16, "chi_env": 128, "value": 1.0}
    spec["cells"].append(
        {"cell_id": "cell-0007", "params": {"dop": 16, "chi_env": 128, "delta": 0}}
    )
    _write_json(spec_path, spec)
    control_manifest = _manifest(control)
    control_manifest["params"]["delta"] = 0
    _write_json(run_dir / "cells" / "cell-0007" / "manifest.json", control_manifest)

    with pytest.raises(ValueError, match="delta"):
        ANALYZER.analyze_run_directories(
            [run_dir],
            output_dir=tmp_path / "analysis",
            bp_mean=BP_MEAN,
            bp_budget=BP_BUDGET,
            target=TARGET,
        )


def test_generic_planner_and_array_inspection_enumerate_the_four_pilot_cells(tmp_path: Path):
    """Breaks if the public planner and array adapter disagree about pilot cells."""

    axes = tmp_path / "axes.json"
    settings = tmp_path / "settings.json"
    provenance = tmp_path / "provenance.json"
    run_dir = tmp_path / "results" / "issue119-pepo-pilot"
    _write_json(axes, {"dop": [2, 4], "chi_env": [16, 32]})
    _write_json(settings, {"delta": 0.15, "evolution_cutoff": 1e-12, "contraction_cutoff": 1e-12})
    _write_json(provenance, {"qasm_sha256": "fixed", "quimb_commit": "fixed"})

    subprocess.run(
        [
            sys.executable,
            str(SCAN_SCRIPT),
            "plan",
            "--axes", str(axes),
            "--settings", str(settings),
            "--provenance", str(provenance),
            "--run-id", "issue119-pepo-pilot",
            "--run-dir", str(run_dir),
        ],
        check=True,
        cwd=WORKSPACE_ROOT,
    )
    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    # The generic planner accepts temporary absolute output locations; the
    # hermetic array adapter intentionally accepts only its repo-root runtime
    # layout. Inspection itself does not need the temporary plan directory.
    spec["run_dir"] = "results/issue119-pepo-pilot"
    payloads = [ARRAY_RUNNER.selected_payload(spec, selector) for selector in range(1, 5)]

    assert [payload["params"] for payload in payloads] == [
        {"dop": 2, "chi_env": 16},
        {"dop": 2, "chi_env": 32},
        {"dop": 4, "chi_env": 16},
        {"dop": 4, "chi_env": 32},
    ]
