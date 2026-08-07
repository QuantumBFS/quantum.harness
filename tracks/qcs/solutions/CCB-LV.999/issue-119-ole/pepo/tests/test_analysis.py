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


def test_assess_convergence_uses_latest_complete_chi_cut_for_sparse_largest_dop(
    tmp_path: Path,
):
    """Breaks if a high-Dop/χmax-only extension cannot retain the last χ scan."""

    records = _records() + [{"dop": 16, "chi_env": 64, "value": 0.8186}]

    assessment = ANALYZER.assess_convergence(
        records,
        bp_mean=BP_MEAN,
        bp_budget=BP_BUDGET,
        target=TARGET,
    )

    assert assessment["corner"] == {"dop": 16, "chi_env": 64, "value": 0.8186}
    assert assessment["delta_dop"] == pytest.approx(0.0001)
    assert assessment["delta_chi_env"] == pytest.approx(0.0002)
    assert assessment["chi_env_reference_dop"] == 8
    assert assessment["chi_env_at_corner"] is False
    assert assessment["internally_converged"] is False
    assert assessment["comparison_status"] == "diagnostic"
    report = ANALYZER._write_report(
        assessment
        | {
            "failed_or_incomplete_cells": [],
            "successful_record_count": len(records),
        },
        tmp_path,
    )
    assert "χenv cut evaluated at Dop=8, below the Dop=16 corner" in report.read_text(
        encoding="utf-8"
    )


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


def _write_duplicate_run(
    tmp_path: Path,
    *,
    value: float,
) -> Path:
    run_dir = tmp_path / "results" / "issue119-pepo-analysis-duplicate"
    record = {"dop": 8, "chi_env": 64, "value": value}
    cell_id = "cell-0001"
    settings = {
        "delta": 0.15,
        "observable_sites": [52, 59, 72],
        "evolution_cutoff": 1e-12,
        "contraction_cutoff": 1e-12,
    }
    provenance = {
        "qasm_sha256": "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455",
        "quimb_commit": "3c89529fe0a3487133a3928201691161e110abdf",
    }
    _write_json(
        run_dir / "run_spec.json",
        {
            "run_id": "issue119-pepo-analysis-duplicate",
            "run_dir": str(run_dir),
            "settings": settings,
            "provenance": provenance,
            "cells": [
                {
                    "cell_id": cell_id,
                    "params": {"dop": 8, "chi_env": 64},
                }
            ],
        },
    )
    _write_json(
        run_dir / "cells" / cell_id / "manifest.json",
        _manifest(record),
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
        {
            "cell_id": "cell-0006",
            "status": "failed",
            "run_dir": str(run_dir),
            "params": {"dop": 2, "chi_env": 16},
            "dop": 2,
            "chi_env": 16,
            "delta": 0.15,
        }
    ]
    persisted = json.loads((output_dir / "assessment.json").read_text(encoding="utf-8"))
    assert persisted["epsilon_pepo"] == pytest.approx(0.0005)
    assert (run_dir / "parameter-scan.csv").is_file()
    assert (output_dir / "PEPO_49Q_VALIDATION.md").read_text(encoding="utf-8").count("empirical") >= 1
    assert (output_dir / "pepo-convergence.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (output_dir / "pepo-convergence.pdf").read_bytes().startswith(b"%PDF")


def test_analyze_run_uses_matching_duplicate_corner_as_determinism_check(
    tmp_path: Path,
):
    """Breaks if the planned cross-run duplicate cannot certify determinism."""

    run_dir = _write_run(tmp_path)
    duplicate_dir = _write_duplicate_run(tmp_path, value=0.8185)

    assessment = ANALYZER.analyze_run_directories(
        [run_dir, duplicate_dir],
        output_dir=tmp_path / "analysis",
        bp_mean=BP_MEAN,
        bp_budget=BP_BUDGET,
        target=TARGET,
    )

    assert assessment["successful_record_count"] == 6
    assert assessment["unique_coordinate_count"] == 5
    assert assessment["duplicate_checks"] == [
        {
            "dop": 8,
            "chi_env": 64,
            "values": [0.8185, 0.8185],
            "max_absolute_difference": 0.0,
            "tolerance": 1e-12,
            "sources": [
                {"run_dir": str(run_dir), "cell_id": "cell-0005"},
                {"run_dir": str(duplicate_dir), "cell_id": "cell-0001"},
            ],
        }
    ]


def test_analyze_run_rejects_disagreeing_duplicate_corner(tmp_path: Path):
    """Breaks if a failed determinism check can enter a convergence estimate."""

    run_dir = _write_run(tmp_path)
    duplicate_dir = _write_duplicate_run(tmp_path, value=0.8186)

    with pytest.raises(ValueError, match="duplicate.*disagree"):
        ANALYZER.analyze_run_directories(
            [run_dir, duplicate_dir],
            output_dir=tmp_path / "analysis",
            bp_mean=BP_MEAN,
            bp_budget=BP_BUDGET,
            target=TARGET,
        )


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


def test_analyze_run_rejects_uniformly_wrong_provenance_against_approved_protocol(tmp_path: Path):
    """Breaks if matching but non-approved QASM/quimb provenance is certified."""

    run_dir = _write_run(tmp_path)
    spec_path = run_dir / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["provenance"] = {"qasm_sha256": "wrong-qasm", "quimb_commit": "wrong-quimb"}
    _write_json(spec_path, spec)
    for index in range(1, 6):
        manifest_path = run_dir / "cells" / f"cell-{index:04d}" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["provenance"] = {"qasm_sha256": "wrong-qasm", "quimb_commit": "wrong-quimb"}
        _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="approved qasm_sha256"):
        ANALYZER.analyze_run_directories(
            [run_dir],
            output_dir=tmp_path / "analysis",
            bp_mean=BP_MEAN,
            bp_budget=BP_BUDGET,
            target=TARGET,
        )


def test_analyze_run_rejects_successful_manifest_not_matching_its_run_spec(tmp_path: Path):
    """Breaks if a successful cell can alter its planned Dop after enumeration."""

    run_dir = _write_run(tmp_path)
    manifest_path = run_dir / "cells" / "cell-0001" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["params"]["dop"] = 3
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="manifest params.dop must match run_spec"):
        ANALYZER.analyze_run_directories(
            [run_dir],
            output_dir=tmp_path / "analysis",
            bp_mean=BP_MEAN,
            bp_budget=BP_BUDGET,
            target=TARGET,
        )


@pytest.mark.parametrize(
    ("field", "wrong_value", "error"),
    [
        ("observable_sites", [1, 2, 3], "approved observable_sites"),
        ("evolution_cutoff", 1e-9, "approved evolution_cutoff"),
        ("contraction_cutoff", 1e-9, "approved contraction_cutoff"),
        ("delta", 0.2, "approved delta"),
    ],
)
def test_analyze_run_rejects_uniformly_wrong_settings_against_approved_protocol(
    tmp_path: Path,
    field: str,
    wrong_value: object,
    error: str,
):
    """Breaks if matching but non-approved PEPO settings can reach assessment."""

    run_dir = _write_run(tmp_path)
    spec_path = run_dir / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["settings"][field] = wrong_value
    _write_json(spec_path, spec)
    for index in range(1, 6):
        manifest_path = run_dir / "cells" / f"cell-{index:04d}" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["settings"][field] = wrong_value
        _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match=error):
        ANALYZER.analyze_run_directories(
            [run_dir],
            output_dir=tmp_path / "analysis",
            bp_mean=BP_MEAN,
            bp_budget=BP_BUDGET,
            target=TARGET,
        )


def test_analyze_run_preserves_unavailable_planned_coordinates(tmp_path: Path):
    """Breaks if failed, missing, or pending cells lose their declared scan coordinates."""

    run_dir = _write_run(tmp_path)
    spec_path = run_dir / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["cells"].extend(
        [
            {"cell_id": "cell-0007", "params": {"dop": 16, "chi_env": 64}},
            {"cell_id": "cell-0008", "params": {"dop": 16, "chi_env": 128, "delta": 0}},
        ]
    )
    _write_json(spec_path, spec)
    (run_dir / "cells" / "cell-0007").mkdir(parents=True)

    output_dir = tmp_path / "analysis"
    assessment = ANALYZER.analyze_run_directories(
        [run_dir],
        output_dir=output_dir,
        bp_mean=BP_MEAN,
        bp_budget=BP_BUDGET,
        target=TARGET,
    )

    assert assessment["failed_or_incomplete_cells"] == [
        {
            "cell_id": "cell-0006",
            "status": "failed",
            "run_dir": str(run_dir),
            "params": {"dop": 2, "chi_env": 16},
            "dop": 2,
            "chi_env": 16,
            "delta": 0.15,
        },
        {
            "cell_id": "cell-0007",
            "status": "missing",
            "run_dir": str(run_dir),
            "params": {"dop": 16, "chi_env": 64},
            "dop": 16,
            "chi_env": 64,
            "delta": 0.15,
        },
        {
            "cell_id": "cell-0008",
            "status": "pending",
            "run_dir": str(run_dir),
            "params": {"dop": 16, "chi_env": 128, "delta": 0},
            "dop": 16,
            "chi_env": 128,
            "delta": 0.0,
        },
    ]
    persisted = json.loads((output_dir / "assessment.json").read_text(encoding="utf-8"))
    assert persisted["failed_or_incomplete_cells"] == assessment["failed_or_incomplete_cells"]
    markdown = (output_dir / "PEPO_49Q_VALIDATION.md").read_text(encoding="utf-8")
    assert "Dop=2, χenv=16, δ=0.15" in markdown
    assert "Dop=16, χenv=128, δ=0" in markdown


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
