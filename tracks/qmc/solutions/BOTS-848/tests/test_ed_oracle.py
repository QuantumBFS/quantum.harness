from __future__ import annotations

import json
import math

import pytest

from benchmark_v0.ed_oracle import run_ed_oracle, write_json_report


@pytest.fixture(scope="module")
def oracle_result() -> dict[str, object]:
    return run_ed_oracle(n_electrons=6, two_q=15, filling=1.0 / 3.0)


def test_n6_oracle_resolves_l0_ground_and_complete_l2_multiplet(
    oracle_result: dict[str, object],
) -> None:
    assert oracle_result["system"] == {
        "n_electrons": 6,
        "two_q": 15,
        "q": 7.5,
        "filling": 1.0 / 3.0,
        "geometry": "Haldane sphere",
        "polarization": "fully polarized fermions",
    }
    ground = oracle_result["states"]["ground"]
    multiplet = oracle_result["states"]["l2_multiplet"]

    assert ground["L"] == 0
    assert ground["M"] == 0
    assert ground["is_unique"] is True
    assert ground["l2_expectation"] == pytest.approx(0.0, abs=1.0e-8)
    assert ground["l2_variance"] < 1.0e-7
    assert [state["M"] for state in multiplet] == [-2, -1, 0, 1, 2]
    for state in multiplet:
        assert state["L"] == 2
        assert state["l2_expectation"] == pytest.approx(6.0, abs=1.0e-8)
        assert state["l2_variance"] < 1.0e-7


def test_n6_oracle_has_consistent_raw_and_paper_energy_views(
    oracle_result: dict[str, object],
) -> None:
    raw = oracle_result["energies"]["raw_lll"]
    paper = oracle_result["energies"]["paper_convention"]

    assert set(raw["excited_energies_by_m"]) == {"-2", "-1", "0", "1", "2"}
    assert raw["gap"] > 0.0
    assert paper["total"]["gap"] == pytest.approx(
        math.sqrt(5.0 / 6.0) * raw["gap"]
    )
    assert paper["per_particle"]["ground_energy"] == pytest.approx(
        paper["total"]["ground_energy"] / 6.0
    )
    assert oracle_result["statistics"]["standard_error"] == 0.0


def test_n6_oracle_passes_all_benchmark_v0_diagnostics(
    oracle_result: dict[str, object],
) -> None:
    diagnostics = oracle_result["diagnostics"]
    gates = oracle_result["gates"]

    assert diagnostics["so3_commutator_residual"] < 5.0e-10
    assert diagnostics["multiplet_splitting"] < 5.0e-10
    assert diagnostics["max_l2_error"] < 1.0e-8
    assert diagnostics["max_l2_variance"] < 1.0e-7
    assert set(gates) == {
        "lll_valid",
        "antisymmetry_valid",
        "so3_equivariance_valid",
        "l2_casimir_valid",
        "fivefold_multiplet_valid",
        "zero_statistical_error_valid",
        "ed_reference_valid",
        "reproducible_run_valid",
        "ed_oracle_valid",
    }
    assert all(gates.values())
    assert oracle_result["benchmark_v0"] == {
        "pass": False,
        "status": "ed_reference_ready",
        "pending": [
            "nqs_vmc_candidate",
            "mc_error_valid",
            "ed_crosscheck_valid",
        ],
    }


def test_oracle_report_round_trips_as_json(
    oracle_result: dict[str, object], tmp_path
) -> None:
    output = tmp_path / "run.json"

    write_json_report(oracle_result, output)
    restored = json.loads(output.read_text(encoding="utf-8"))

    assert restored["schema_version"] == "challenge-15-benchmark-v0.1"
    assert restored["runtime"]["python_version"]
    assert restored["runtime"]["numpy_version"]
    assert restored["runtime"]["scipy_version"]
    assert restored["gates"]["ed_oracle_valid"] is True
    assert restored["benchmark_v0"]["pass"] is False
