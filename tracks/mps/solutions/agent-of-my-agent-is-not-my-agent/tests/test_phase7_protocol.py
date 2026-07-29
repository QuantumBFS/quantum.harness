from pathlib import Path

import numpy as np
import pytest

import lrtfim
from lrtfim.phase7_protocol import (
    SIGMAS,
    broad_gamma_grid,
    build_broad_spec,
    build_gap_spec,
    decide_refinement,
    estimate_scan_cost,
    finalize_crossing,
    grid_hash,
    quality_flags,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fit_records() -> dict[str, dict]:
    return {
        f"{sigma:.2f}": {
            "path": f"fits/sigma-{sigma:.2f}.json",
            "fit_hash": f"fit-{sigma:.2f}",
            "coefficient_hash": f"coeff-{sigma:.2f}",
            "sigma": sigma,
            "K": 24,
            "alpha": 0.5,
            "r_fit": 2048,
        }
        for sigma in SIGMAS
    }


def test_phase7_documentation_declares_exploration_scope() -> None:
    combined_docs = "\n".join(
        (PROJECT_ROOT / relative).read_text()
        for relative in ("README.md", "docs/methodology.md", "scripts/README.md")
    )
    for token in (
        "validated local reproduction",
        "sigma=1.50,1.60,1.70,1.75,1.80,1.90,2.00",
        "K=24",
        "chi=64",
        "no thermodynamic-limit",
    ):
        assert token in combined_docs


def test_broad_grid_is_exact_and_hash_is_stable() -> None:
    expected = np.arange(120, 191, 5, dtype=float) / 100.0
    np.testing.assert_array_equal(broad_gamma_grid(), expected)
    assert grid_hash(expected) == grid_hash(expected.tolist())
    np.testing.assert_array_equal(lrtfim.broad_gamma_grid(), expected)


def test_broad_spec_has_common_grid_and_210_even_cells(tmp_path: Path) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)

    assert len(spec["cells"]) == 7 * 2 * 15
    assert {cell["sector"] for cell in spec["cells"]} == {"even"}
    assert {cell["chi"] for cell in spec["cells"]} == {64}
    assert {cell["K"] for cell in spec["cells"]} == {24}
    assert len({cell["cell_id"] for cell in spec["cells"]}) == 210
    assert len({cell["grid_hash"] for cell in spec["cells"]}) == 1
    assert spec["settings"]["approximate_mpo_compression"] is False
    assert spec["settings"]["exact_zero_pruning"] is True


def test_broad_spec_rejects_missing_fit(tmp_path: Path) -> None:
    records = fit_records()
    records.pop("1.80")
    with pytest.raises(ValueError, match="fit records"):
        build_broad_spec(records, tmp_path)


def valid_summary() -> dict:
    return {
        "status": "success",
        "converged": True,
        "direct": {
            "even": {
                "energy": -50.0,
                "variance": 1.0e-8,
                "discarded_weight": 1.0e-10,
                "sweeps": 8,
            }
        },
        "raw_observables": {
            "r_xi": 0.4,
            "xi": 25.6,
            "s_zero": 20.0,
            "s_k_min": 10.0,
        },
    }


def test_quality_flags_cover_all_selective_chi_triggers() -> None:
    summary = valid_summary()
    assert quality_flags(summary) == []

    nonconverged = valid_summary()
    nonconverged["converged"] = False
    assert "dmrg_nonconverged" in {
        flag["code"] for flag in quality_flags(nonconverged)
    }

    high_variance = valid_summary()
    high_variance["direct"]["even"]["variance"] = 1.0e-5
    assert "relative_variance" in {
        flag["code"] for flag in quality_flags(high_variance)
    }

    high_discarded = valid_summary()
    high_discarded["direct"]["even"]["discarded_weight"] = 2.0e-8
    assert "discarded_weight" in {
        flag["code"] for flag in quality_flags(high_discarded)
    }

    invalid_ratio = valid_summary()
    invalid_ratio["raw_observables"]["s_zero"] = 5.0
    assert "invalid_second_moment" in {
        flag["code"] for flag in quality_flags(invalid_ratio)
    }

    reversed_sectors = valid_summary()
    reversed_sectors["direct"]["odd"] = {
        "energy": -51.0,
        "variance": 1.0e-8,
        "discarded_weight": 1.0e-10,
        "sweeps": 8,
    }
    reversed_sectors["raw_observables"]["gap"] = -1.0
    assert "nonpositive_gap" in {
        flag["code"] for flag in quality_flags(reversed_sectors)
    }


def broad_manifests(spec: dict, sigma: float, differences: list[float]) -> dict:
    gammas = spec["axes"]["Gamma"]
    if len(differences) != len(gammas):
        raise ValueError("one difference is required per Gamma")
    manifests = {}
    for length in (32, 64):
        for gamma, difference in zip(gammas, differences, strict=True):
            cell = next(
                item
                for item in spec["cells"]
                if item["sigma"] == sigma
                and item["L"] == length
                and item["Gamma"] == gamma
            )
            manifests[cell["cell_id"]] = {
                "status": "success",
                "settings": {
                    "sigma": sigma,
                    "length": length,
                    "gamma": gamma,
                    "sector": "even",
                },
                "raw_observables": {
                    "r_xi": 1.0 + (difference if length == 32 else 0.0)
                },
            }
    return manifests


def test_refinement_uses_only_unique_observed_bracket(tmp_path: Path) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)
    differences = np.linspace(0.4, -0.3, 15).tolist()
    decision = decide_refinement(
        1.75,
        spec,
        broad_manifests(spec, 1.75, differences),
    )

    assert decision["status"] == "ready"
    assert decision["broad_bracket"] == [1.55, 1.6]
    assert decision["refinement_grid"] == pytest.approx(
        [1.55, 1.56, 1.57, 1.58, 1.59, 1.60]
    )
    assert decision["broad_Gamma_x"] == pytest.approx(1.60)
    assert decision["broad_delta_gamma_grid"] == pytest.approx(0.025)
    assert decision["broad_interpolation_differences"] == pytest.approx(
        [differences[7], differences[8]]
    )
    assert decision["broad_grid"] == spec["axes"]["Gamma"]
    assert decision["grid_hash"] == spec["settings"]["gamma_grid_hash"]


def test_refinement_leaves_missing_or_ambiguous_cases_unresolved(
    tmp_path: Path,
) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)
    none = decide_refinement(
        1.75,
        spec,
        broad_manifests(spec, 1.75, [1.0] * 15),
    )
    assert none["status"] == "unresolved_no_bracket"
    assert "refinement_grid" not in none

    alternating = [1.0] * 15
    alternating[2:5] = [-1.0, -1.0, 1.0]
    multiple = decide_refinement(
        1.75,
        spec,
        broad_manifests(spec, 1.75, alternating),
    )
    assert multiple["status"] == "unresolved_multiple_brackets"

    manifests = broad_manifests(spec, 1.75, np.linspace(1, -1, 15).tolist())
    manifests.pop(next(iter(manifests)))
    incomplete = decide_refinement(1.75, spec, manifests)
    assert incomplete["status"] == "incomplete"


def test_refinement_ignores_manifests_from_other_sigma(tmp_path: Path) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)
    target = broad_manifests(spec, 1.75, [1.0] * 15)
    other = broad_manifests(
        spec,
        1.80,
        np.linspace(1.0, -1.0, 15).tolist(),
    )

    decision = decide_refinement(1.75, spec, {**target, **other})

    assert decision["status"] == "unresolved_no_bracket"


def test_final_crossing_records_resolution_and_gap_spec(tmp_path: Path) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)
    decision = {
        "status": "ready",
        "sigma": 1.75,
        "grid_hash": spec["settings"]["gamma_grid_hash"],
        "refinement_grid": [1.55, 1.56, 1.57, 1.58, 1.59, 1.60],
    }
    refined = {
        f"L{length}_G{gamma:.2f}": {
            "status": "success",
            "settings": {"sigma": 1.75, "length": length, "gamma": gamma},
            "raw_observables": {
                "r_xi": (
                    0.5 + (1.565 - gamma)
                    if length == 32
                    else 0.5
                )
            },
        }
        for length in (32, 64)
        for gamma in decision["refinement_grid"]
    }
    final = finalize_crossing(decision, refined)
    assert final["status"] == "crossing_resolved"
    assert final["Gamma_x"] == pytest.approx(1.565)
    assert final["interpolation_points"] == [1.56, 1.57]
    assert final["delta_gamma_grid"] == pytest.approx(0.005)

    gap_spec = build_gap_spec([final], tmp_path / "gaps")
    assert len(gap_spec["cells"]) == 4
    assert {cell["sector"] for cell in gap_spec["cells"]} == {"odd"}
    assert {cell["Gamma"] for cell in gap_spec["cells"]} == {1.56, 1.57}

    assert build_gap_spec(
        [{"status": "unresolved_no_bracket", "sigma": 1.75}],
        tmp_path,
    )["cells"] == []


def timing_records() -> list[dict]:
    return [
        {
            "L": length,
            "sector": sector,
            "chi": 128,
            "wall_seconds": seconds,
            "peak_memory_gib": memory,
            "path": f"timing/L{length}-{sector}.json",
            "code_hash": "code-1",
            "hardware": {"cpu": "fixture"},
        }
        for length, sector, seconds, memory in (
            (32, "even", 80.0, 0.8),
            (32, "odd", 100.0, 0.9),
            (64, "even", 240.0, 1.6),
            (64, "odd", 300.0, 1.8),
        )
    ]


def test_cost_estimate_scales_measured_chi128_records(tmp_path: Path) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)
    estimate = estimate_scan_cost(timing_records(), spec)

    assert estimate["scaling"]["time_chi_factor"] == pytest.approx(
        (64 / 128) ** 3
    )
    assert estimate["scaling"]["memory_chi_factor"] == pytest.approx(
        (64 / 128) ** 2
    )
    assert estimate["stages"]["broad"]["cells"] == 210
    assert estimate["stages"]["refinement"]["maximum_new_even_cells"] == 56
    assert estimate["stages"]["gaps"]["maximum_odd_cells"] == 28
    assert estimate["safety_factor"] == 2.0
    assert estimate["combined"]["central_wall_seconds"] > 0.0
    assert estimate["combined"]["safety_wall_seconds"] == pytest.approx(
        2.0 * estimate["combined"]["central_wall_seconds"]
    )


def test_cost_estimate_rejects_incomplete_calibration(tmp_path: Path) -> None:
    spec = build_broad_spec(fit_records(), tmp_path)
    records = timing_records()[:-1]
    with pytest.raises(ValueError, match="calibration"):
        estimate_scan_cost(records, spec)

    records = timing_records()
    records[0]["wall_seconds"] = 0.0
    with pytest.raises(ValueError, match="positive"):
        estimate_scan_cost(records, spec)
