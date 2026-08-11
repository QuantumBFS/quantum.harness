from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from floquet_if_manybody.error_map import (
    audit_grid_manifest,
    build_error_record,
    correlation_error,
    heat_error,
    trace_distance,
)


def _result(method: str) -> dict[str, object]:
    return {
        "method": method,
        "converged": True,
        "model_hash": "same",
        "model": {"normalization": "bounded"},
        "phase_state": {
            "real": [[1.0, 0.0], [0.0, 0.0]],
            "imag": [[0.0, 0.0], [0.0, 0.0]],
        },
        "correlation": {
            "delay": [0.0, 1.0],
            "connected": {"real": [1.0, 0.5], "imag": [0.0, 0.0]},
        },
        "frequency": [0.0, 1.0],
        "continuous": [0.0, 1.0],
        "evidence": [],
    }


def test_trace_distance_diagonal_example() -> None:
    first = np.diag([0.75, 0.25]).astype(complex)
    second = np.diag([0.5, 0.5]).astype(complex)
    assert trace_distance(first, second) == pytest.approx(0.25)


def test_identical_curves_have_zero_error() -> None:
    grid = np.linspace(0, 1, 5)
    curve = np.exp(-grid) + 1j * grid
    assert correlation_error(grid, curve, grid, curve) == pytest.approx(0.0)
    assert heat_error(grid, curve.real, grid, curve.real) == pytest.approx(0.0)


@pytest.mark.parametrize("field", ["model_hash", "normalization", "frequency"])
def test_build_record_rejects_incompatible_inputs(field: str) -> None:
    exact = _result("pt_tempo_multitime")
    markov = deepcopy(exact)
    markov["method"] = "floquet_markov_qr"
    if field == "model_hash":
        markov["model_hash"] = "different"
    elif field == "normalization":
        markov["model"]["normalization"] = "kac"  # type: ignore[index]
    else:
        markov["frequency"] = [0.0, 2.0]
    with pytest.raises(ValueError, match=field):
        build_error_record(exact, markov)


def test_build_record_rejects_unconverged_exact_input() -> None:
    exact = _result("pt_tempo_multitime")
    exact["converged"] = False
    with pytest.raises(ValueError, match="converged"):
        build_error_record(exact, _result("floquet_markov_qr"))


@pytest.mark.parametrize(
    "method",
    ["pt_tempo_multitime", "uniform_tempo_floquet_multitime"],
)
def test_build_record_accepts_approved_process_tensor_methods(method: str) -> None:
    record = build_error_record(_result(method), _result("floquet_markov_qr"))
    assert record["status"] == "converged"
    assert record["exact_method"] == method


def test_grid_audit_accepts_explicit_resource_masks() -> None:
    alphas = (0.025, 0.05, 0.1)
    ratios = (0.75, 1.0, 1.25)
    points = [
        {
            "alpha": alpha,
            "drive_ratio": ratio,
            "status": (
                "resource_ceiling" if (alpha, ratio) == (0.1, 1.25) else "converged"
            ),
            "metrics": None if (alpha, ratio) == (0.1, 1.25) else {"heat": 0.1},
        }
        for alpha in alphas
        for ratio in ratios
    ]
    audit = audit_grid_manifest({"points": points}, alphas, ratios)
    assert audit["complete"]
    assert audit["masked_points"] == 1
