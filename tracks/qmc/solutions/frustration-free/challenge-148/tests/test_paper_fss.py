from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from challenge148.paper_fss import (
    analyze_paper_points,
    load_validated_paper_root,
)
from challenge148.paper_scan import build_paper_scan_plan


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = ROOT / "preregistration" / "paper-scan-v1.json"
BUILD_INFO = {
    "adapter": "QMC_SSE",
    "source_hash": "a" * 64,
    "build_hash": "b" * 64,
}


def _model(field: float, length: int, tc: float) -> float:
    d = field - tc
    yt = 1.587
    yi = -0.815
    return (
        0.62
        + 0.05 * d * length**yt
        - 0.01 * d**2 * length ** (2 * yt)
        + 0.002 * d**3 * length ** (3 * yt)
        + 0.03 * length**yi
        + 0.01 * d * length ** (yi + yt)
    )


def _synthetic_points() -> list[dict[str, object]]:
    points = []
    for lattice, center, lengths in (
        ("triangular", 4.76811, range(6, 21, 2)),
        ("honeycomb", 2.13250, range(10, 21, 2)),
    ):
        for length in lengths:
            for factor in (0.995, 0.9975, 1.0, 1.0025, 1.005):
                field = center * factor
                binder = _model(field, length, center)
                chains = []
                for sign in (-1.0, 1.0):
                    m2 = np.full(16, 1.0 + sign * 0.002)
                    m4 = np.full(16, 1.0 / binder + sign * 0.001)
                    chains.append({"m2": m2.tolist(), "m4": m4.tolist()})
                points.append(
                    {
                        "lattice": lattice,
                        "length": length,
                        "field": field,
                        "chains": chains,
                    }
                )
    return points


def test_eq23_fit_recovers_tc_covariance_ratio_and_hashes():
    result = analyze_paper_points(
        _synthetic_points(),
        plan_sha256="a" * 64,
        source_sha256="b" * 64,
        evidence_bindings=[
            {"cell_id": f"paper-{index:03d}", "sha256": "c" * 64}
            for index in range(140)
        ],
    )
    assert result["stage"] == "paper-aligned QMC_SSE finite-size reproduction"
    assert "not the final independent two-code verdict" in result["interpretation"]
    assert result["fit"]["fixed_exponents"] == {"y_t": 1.587, "y_i": -0.815}
    fits = {fit["lattice"]: fit for fit in result["fit"]["lattices"]}
    assert fits["triangular"]["tc"] == pytest.approx(4.76811, abs=2e-5)
    assert fits["honeycomb"]["tc"] == pytest.approx(2.13250, abs=2e-5)
    for fit in fits.values():
        assert np.asarray(fit["parameter_covariance"]).shape == (7, 7)
        assert fit["tc_standard_error"] > 0
        assert fit["jacobian_rank"] == 7
        assert fit["reduced_chi_square"] < 10
    comparison = result["comparison"]
    expected_ratio = 4.76811 / 2.13250
    assert comparison["triangular_divided_by_honeycomb"] == pytest.approx(
        expected_ratio, rel=2e-5
    )
    assert comparison["sqrt_5"] == pytest.approx(math.sqrt(5))
    assert math.isfinite(comparison["normalized_difference"])
    assert len(result["input_bindings"]) == 140
    assert len(result["analysis_sha256"]) == 64


@pytest.mark.parametrize("failure", ["rank", "nonfinite", "residual"])
def test_eq23_fit_failures_are_closed(failure: str):
    points = _synthetic_points()
    if failure == "rank":
        for point in points:
            point["length"] = 10
    elif failure == "nonfinite":
        points[0]["chains"][0]["m2"][0] = float("nan")
    else:
        rng = np.random.default_rng(148)
        for point in points:
            binder = float(rng.uniform(0.2, 0.9))
            for chain in point["chains"]:
                chain["m4"] = [1.0 / binder] * 16
    with pytest.raises(ValueError):
        analyze_paper_points(
            points,
            plan_sha256="a" * 64,
            source_sha256="b" * 64,
            evidence_bindings=[
                {"cell_id": f"paper-{index:03d}", "sha256": "c" * 64}
                for index in range(140)
            ],
        )


def _paper_plan(root: Path) -> dict[str, object]:
    plan = build_paper_scan_plan(
        json.loads(PREREGISTRATION.read_text()), BUILD_INFO, root
    )
    (root / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return plan


def test_paper_loader_requires_exactly_140_validated_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _paper_plan(tmp_path)
    cells_root = tmp_path / "cells"
    for cell in plan["cells"]:
        (cells_root / cell["cell_id"]).mkdir(parents=True)

    def load(root, loaded_plan, cell, cell_index):
        return (
            [
                {"m2_sum": 100.0, "m4_sum": 200.0, "sample_count": 100}
                for _ in range(16)
            ],
            {"cell_id": cell["cell_id"], "sha256": "d" * 64},
        )

    monkeypatch.setattr("challenge148.paper_fss._load_validated_cell", load)
    loaded, points, bindings = load_validated_paper_root(tmp_path)
    assert loaded == plan
    assert len(points) == 70
    assert all(len(point["chains"]) == 2 for point in points)
    assert len(bindings) == 140

    (cells_root / "unexpected").mkdir()
    with pytest.raises(ValueError, match="exactly the 140 planned cells"):
        load_validated_paper_root(tmp_path)


def test_paper_loader_rejects_tampered_real_completed_evidence(tmp_path: Path):
    from test_run_cell import _fake_executable, _load_runner

    plan = _paper_plan(tmp_path)
    cells_root = tmp_path / "cells"
    for cell in plan["cells"]:
        (cells_root / cell["cell_id"]).mkdir(parents=True)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    first = _load_runner().run_cell(tmp_path / "plan.json", 0, executable, timeout=5)
    completion = next((first / "completed-evidence").iterdir()) / "completion.json"
    completion.write_bytes(completion.read_bytes() + b" ")
    with pytest.raises(ValueError, match="cell completion|canonical"):
        load_validated_paper_root(tmp_path)


def test_paper_fss_cli_writes_only_successful_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = ROOT / "scripts" / "analyze_paper.py"
    specification = importlib.util.spec_from_file_location("analyze_paper", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    output = tmp_path / "analysis.json"
    expected = {
        "stage": "paper-aligned QMC_SSE finite-size reproduction",
        "analysis_sha256": "e" * 64,
    }
    monkeypatch.setattr(module, "analyze_paper_root", lambda root: expected)
    monkeypatch.setattr(
        module, "write_paper_analysis", lambda path, value: path.write_text("ok\n")
    )
    assert module.main(["--production-root", str(tmp_path), "--output", str(output)]) == 0
    assert output.read_text() == "ok\n"
