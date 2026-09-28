import json
from pathlib import Path

import numpy as np

from scripts.evaluate_giant_diagonal_outer import (
    evaluate,
    evaluate_adaptive_rapidity_fft,
)


ROOT = Path(__file__).resolve().parents[1]


def test_shared_fft_outer_diagonal_quadrature_is_finite() -> None:
    result = evaluate(
        matching_scale=0.2,
        xi_extent=6.0,
        xi_points=10,
        dressing_xi_extent=10.0,
        dressing_xi_points=40,
        rapidity_extent=6.0,
        rapidity_points=48,
    )
    assert np.isfinite(result["outer_leading_integral"])
    assert np.isfinite(result["outer_first_integral"])
    assert result["outer_leading_integral"] > 0.0
    assert result["diagnostics"]["leading_resolvent_max_abs_error"] < 1e-10
    assert result["diagnostics"]["physical_D1_certified"] is False


def test_adaptive_rapidity_outer_quadrature_resolves_narrow_layer() -> None:
    result = evaluate_adaptive_rapidity_fft(
        matching_scale=0.2,
        xi_extent=6.0,
        xi_points=8,
        dressing_xi_extent=10.0,
        dressing_xi_points=32,
        rapidity_extent=8.0,
        rapidity_step=0.25,
        rapidity_nodes_per_string=12,
    )
    assert result["method"] == "outer_giant_diagonal_adaptive_rapidity_fft"
    assert np.isfinite(result["outer_full_leading_integral"])
    assert result["outer_leading_integral"] > result["outer_full_leading_integral"]
    assert result["outer_cross_leading_integral"] > 0.0
    assert result["diagnostics"]["leading_resolvent_max_abs_error"] < 1e-10


def test_outer_matching_artifact_fails_closed_without_inner_overlap() -> None:
    payload = json.loads(
        (ROOT / "docs/giant_diagonal_outer_matching_audit.json").read_text()
    )
    assert len(payload["rows"]) == 4
    gates = payload["gates"]
    assert gates["outer_leading_monotone_as_eta_decreases"] is True
    assert gates["outer_first_has_matching_scale_plateau"] is False
    assert gates["cross_has_nonzero_leading_on_fixed_u_grid"] is True
    assert gates["smallest_eta_cross_leading"] > 0.1
    assert gates["fixed_u_rapidity_resolution_converged"] is False
    assert gates["artifact_superseded_by_adaptive_u_over_xi_audit"] is True
    assert gates["fixed_string_inner_overlap_evaluated"] is False
    assert gates["outer_value_alone_eligible_for_physical_D1"] is False
    assert gates["physical_D1_certified"] is False
