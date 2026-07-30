import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from lrtfim.local_uncertainty import (
    compare_chi,
    compare_k_crossing,
    merge_sector_summaries,
    numeric_shift,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _summary(
    *,
    gamma: float,
    chi: int,
    k: int,
    even_energy: float,
    odd_energy: float,
    r_xi: float,
) -> dict:
    return {
        "status": "success",
        "settings": {
            "sigma": 1.75,
            "length": 64,
            "gamma": gamma,
            "num_exponentials": k,
            "alpha": 0.5,
            "r_fit": 2048,
        },
        "fit": {"K": k, "alpha": 0.5, "r_fit": 2048},
        "direct": {
            "even": {
                "requested_chi": chi,
                "energy": even_energy,
                "variance": 2e-7,
                "discarded_weight": 2e-9,
                "wall_seconds": 10.0,
            },
            "odd": {
                "requested_chi": chi,
                "energy": odd_energy,
                "variance": 3e-7,
                "discarded_weight": 4e-9,
                "wall_seconds": 11.0,
            },
        },
        "raw_observables": {
            "gap": odd_energy - even_energy,
            "r_xi": r_xi,
        },
    }


def test_numeric_shift_reports_absolute_and_relative_change() -> None:
    shift = numeric_shift(2.0, 2.2)
    assert shift["absolute"] == pytest.approx(0.2)
    assert shift["relative"] == pytest.approx(0.1)


def test_compare_chi_keeps_mps_uncertainty_separate() -> None:
    baseline = _summary(
        gamma=1.56,
        chi=128,
        k=24,
        even_energy=-10.0,
        odd_energy=-9.8,
        r_xi=0.35,
    )
    refined = _summary(
        gamma=1.56,
        chi=256,
        k=24,
        even_energy=-10.01,
        odd_energy=-9.805,
        r_xi=0.351,
    )
    for sector in ("even", "odd"):
        baseline["direct"][sector]["reached_chi"] = 128
        baseline["direct"][sector].pop("requested_chi")

    result = compare_chi(baseline, refined)

    assert result["kind"] == "mps"
    assert result["gap"]["reference"] == pytest.approx(0.2)
    assert result["gap"]["candidate"] == pytest.approx(0.205)
    assert result["r_xi"]["absolute"] == pytest.approx(0.001)
    assert result["runtime_seconds"]["candidate_total"] == pytest.approx(21.0)


def test_merge_sector_summaries_reconstructs_gap_without_copying_odd_rxi() -> None:
    combined = _summary(
        gamma=1.56,
        chi=256,
        k=24,
        even_energy=-10.01,
        odd_energy=-9.805,
        r_xi=0.351,
    )
    even = {**combined, "direct": {"even": combined["direct"]["even"]}}
    even["raw_observables"] = {
        key: value
        for key, value in combined["raw_observables"].items()
        if key != "gap"
    }
    odd = {**combined, "direct": {"odd": combined["direct"]["odd"]}}
    odd["raw_observables"] = {}
    for summary in (even, odd):
        summary["settings"] = dict(summary["settings"])
        for field in ("num_exponentials", "alpha", "r_fit"):
            summary["settings"].pop(field)

    merged = merge_sector_summaries(even, odd)

    assert set(merged["direct"]) == {"even", "odd"}
    assert merged["raw_observables"]["gap"] == pytest.approx(0.205)
    assert merged["raw_observables"]["r_xi"] == pytest.approx(0.351)


def test_merge_sector_summaries_accepts_combined_legacy_source() -> None:
    combined = _summary(
        gamma=1.56,
        chi=128,
        k=24,
        even_energy=-10.0,
        odd_energy=-9.8,
        r_xi=0.35,
    )

    merged = merge_sector_summaries(combined, combined)

    assert set(merged["direct"]) == {"even", "odd"}
    assert merged["raw_observables"]["gap"] == pytest.approx(0.2)


def test_k_crossing_uses_same_signed_difference_for_each_k() -> None:
    gammas = [1.56, 1.565]
    k24 = {
        32: [0.344, 0.337],
        64: [0.350, 0.334],
    }
    k32 = {
        32: [0.345, 0.338],
        64: [0.351, 0.335],
    }

    result = compare_k_crossing(gammas, k24, k32)

    assert result["status"] == "complete"
    assert result["K24"]["difference"] == pytest.approx([-0.006, 0.003])
    assert result["K32"]["difference"] == pytest.approx([-0.006, 0.003])
    assert result["K24"]["gamma"] == pytest.approx(
        result["K32"]["gamma"]
    )


def test_k_crossing_labels_cost_limited_missing_l32() -> None:
    result = compare_k_crossing(
        [1.56, 1.565],
        {32: [0.344, 0.337], 64: [0.350, 0.334]},
        {64: [0.351, 0.335]},
    )

    assert result == {
        "status": "incomplete_cost_limited",
        "reason": "K32_L32_missing",
    }


def test_analysis_cli_writes_mps_uncertainty_outputs(tmp_path: Path) -> None:
    baseline = _summary(
        gamma=1.56,
        chi=128,
        k=24,
        even_energy=-10.0,
        odd_energy=-9.8,
        r_xi=0.35,
    )
    refined = _summary(
        gamma=1.56,
        chi=256,
        k=24,
        even_energy=-10.01,
        odd_energy=-9.805,
        r_xi=0.351,
    )
    paths = {}
    for label, summary in (("chi128", baseline), ("chi256", refined)):
        for sector in ("even", "odd"):
            split = {**summary, "direct": {sector: summary["direct"][sector]}}
            split["raw_observables"] = (
                {
                    key: value
                    for key, value in summary["raw_observables"].items()
                    if key != "gap"
                }
                if sector == "even"
                else {}
            )
            path = tmp_path / f"{label}_{sector}.json"
            path.write_text(json.dumps(split))
            paths[(label, sector)] = path
    spec_path = tmp_path / "comparison-spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "mps_pairs": [
                        {
                            "gamma": 1.56,
                            "chi128_even": str(paths[("chi128", "even")]),
                            "chi128_odd": str(paths[("chi128", "odd")]),
                            "chi256_even": str(paths[("chi256", "even")]),
                            "chi256_odd": str(paths[("chi256", "odd")]),
                        }
                ],
                "k_cells": [],
            }
        )
    )
    output = tmp_path / "analysis"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "analyze_local_reproduction.py"),
            "--comparison-spec",
            str(spec_path),
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["mps"]["status"] == "complete"
    assert analysis["mps"]["comparisons"][0]["gap"]["absolute"] == pytest.approx(
        0.005
    )
    with (output / "mps-uncertainty.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["gamma"] == "1.56"
    assert float(rows[0]["gap_absolute_shift"]) == pytest.approx(0.005)


def test_analysis_cli_assembles_complete_k_crossing(tmp_path: Path) -> None:
    k_cells = []
    values = {
        24: {32: [0.344, 0.337], 64: [0.350, 0.334]},
        32: {32: [0.345, 0.338], 64: [0.351, 0.335]},
    }
    for k in (24, 32):
        for length in (32, 64):
            for gamma, r_xi in zip((1.56, 1.565), values[k][length]):
                summary = _summary(
                    gamma=gamma,
                    chi=128,
                    k=k,
                    even_energy=-float(length),
                    odd_energy=-float(length) + 0.1,
                    r_xi=r_xi,
                )
                summary["settings"]["length"] = length
                paths = {}
                for sector in ("even", "odd"):
                    split = {
                        **summary,
                        "direct": {sector: summary["direct"][sector]},
                        "raw_observables": (
                            {
                                key: value
                                for key, value in summary[
                                    "raw_observables"
                                ].items()
                                if key != "gap"
                            }
                            if sector == "even"
                            else {}
                        ),
                    }
                    if k == 24:
                        split["settings"] = dict(split["settings"])
                        for field in ("num_exponentials", "alpha", "r_fit"):
                            split["settings"].pop(field)
                    path = tmp_path / f"K{k}_L{length}_G{gamma}_{sector}.json"
                    path.write_text(json.dumps(split))
                    paths[sector] = path
                k_cells.append(
                    {
                        "K": k,
                        "L": length,
                        "Gamma": gamma,
                        "even": str(paths["even"]),
                        "odd": str(paths["odd"]),
                    }
                )
    spec_path = tmp_path / "comparison-spec.json"
    spec_path.write_text(json.dumps({"mps_pairs": [], "k_cells": k_cells}))
    output = tmp_path / "analysis"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "analyze_local_reproduction.py"),
            "--comparison-spec",
            str(spec_path),
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["mpo"]["status"] == "complete"
    assert analysis["mpo"]["crossing"]["status"] == "complete"
    assert analysis["mpo"]["crossing"]["K24"]["difference"] == pytest.approx(
        [-0.006, 0.003]
    )
    assert (output / "mpo-uncertainty.csv").is_file()
    assert (output / "rxi-by-chi-k.csv").is_file()
