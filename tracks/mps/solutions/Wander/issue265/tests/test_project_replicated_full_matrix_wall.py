import argparse
import hashlib
import json

import numpy as np
import pytest

from scripts.project_replicated_full_matrix_wall import derive
from scripts.project_replicated_full_matrix_wall import (
    _analytic_selfsimilar_strong_projection,
    _validate_field_audit,
)


def _field_audit(tmp_path, inputs, fields):
    hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in inputs
    }
    path = tmp_path / "matched_field_audit.json"
    path.write_text(json.dumps({
        "uses_target_a_or_D": False,
        "uses_target_trajectory": False,
        "matched_integer_field_limit_accepted": True,
        "degrees_tested": [1, 2, 3],
        "fields_descending": sorted(fields, reverse=True),
        "input_sha256_by_file": hashes,
    }))
    return path


def test_theory_wall_projection_uses_replicated_q_grid_without_targets(tmp_path):
    tau = 27 / (10 * np.pi)
    wave_count = 32
    waves = 0.25 * (np.fft.fftfreq(wave_count) * wave_count)
    inputs = []
    fields = (0.2, 1 / 6, 0.125, 0.1, 1 / 12)
    for field in fields:
        for seed in range(4):
            structure = np.exp(-0.5 * waves**2) * (
                1 + 1e-4 * field * waves**2 + 1e-6 * (seed - 1.5) * waves**2
            )
            payload = {
                "uses_target_a_or_D": False,
                "uses_target_trajectory": False,
                "regulator": {"field": field, "seed": seed},
                "iteration": {"converged": True},
                "scaled_times_tau_equals_t_h3": [tau],
                "scaled_waves_q_equals_k_over_h2": waves.tolist(),
                "structure_factors_over_chi_by_wave_then_time": [
                    [[[float(value), 0.0]][0] for _ in range(1)] for value in structure
                ],
            }
            path = tmp_path / f"h{field}_seed{seed}.json"
            path.write_text(json.dumps(payload))
            inputs.append(path)
    args = argparse.Namespace(
        inputs=inputs,
        field_audit=_field_audit(tmp_path, inputs, fields),
        required_replicates=4,
        scaled_time=tau,
        scaled_time_tolerance=1e-12,
        bootstrap_replicates=0,
        bootstrap_seed=265,
        maximum_relative_scheme_width=0.1,
        maximum_fourier_tail=0.01,
        minimum_valid_bootstrap_fraction=0.9,
        maximum_relative_projection_disagreement=0.1,
        length=160,
        profile_start=50.0,
        profile_stop=70.0,
        dt=1.0,
        fit_start=51.0,
        fit_stop=69.0,
        x_crop=(-60.0, 60.0),
        y_maximum=12.0,
        y_points=801,
    )
    result = derive(args)
    assert not result["uses_target_trajectory"]
    assert not result["uses_target_a_or_D"]
    assert not result["physical_a_or_D_identified"]
    assert len(result["integer_degree_projections"]) == 3
    for row in result["integer_degree_projections"].values():
        assert np.isfinite(row["a"])
        assert np.isfinite(row["D"])
        assert np.isfinite(row["analytic_selfsimilar_strong_projection"]["a"])
        assert np.isfinite(row["analytic_selfsimilar_strong_projection"]["D"])


def test_bootstrap_runs_and_reports_projection_agreement_gate(tmp_path):
    tau = 27 / (10 * np.pi)
    wave_count = 32
    waves = 0.25 * (np.fft.fftfreq(wave_count) * wave_count)
    inputs = []
    fields = (0.2, 1 / 6, 0.125, 0.1, 1 / 12)
    for field in fields:
        for seed in range(4):
            structure = np.exp(-0.5 * waves**2) * (
                1 + 1e-5 * (field + seed) * waves**2
            )
            payload = {
                "uses_target_a_or_D": False,
                "uses_target_trajectory": False,
                "regulator": {"field": field, "seed": seed},
                "iteration": {"converged": True},
                "scaled_times_tau_equals_t_h3": [tau],
                "scaled_waves_q_equals_k_over_h2": waves.tolist(),
                "structure_factors_over_chi_by_wave_then_time": [
                    [[float(value), 0.0]] for value in structure
                ],
            }
            path = tmp_path / f"bootstrap_h{field}_seed{seed}.json"
            path.write_text(json.dumps(payload))
            inputs.append(path)
    args = argparse.Namespace(
        inputs=inputs,
        field_audit=_field_audit(tmp_path, inputs, fields),
        required_replicates=4,
        scaled_time=tau,
        scaled_time_tolerance=1e-12,
        bootstrap_replicates=2,
        bootstrap_seed=265,
        maximum_relative_scheme_width=0.1,
        maximum_fourier_tail=0.01,
        minimum_valid_bootstrap_fraction=0.0,
        maximum_relative_projection_disagreement=10.0,
        length=160,
        profile_start=50.0,
        profile_stop=70.0,
        dt=1.0,
        fit_start=51.0,
        fit_stop=69.0,
        x_crop=(-60.0, 60.0),
        y_maximum=12.0,
        y_points=801,
    )
    result = derive(args)
    assert all(row["valid_replicates"] == 2 for row in result["bootstrap_by_integer_degree"].values())
    observed = result["identification_gate"][
        "observed_maximum_relative_projection_disagreement"
    ]
    assert set(observed) == {"a", "D"}


def test_factored_strong_projection_matches_numerical_time_quadrature():
    from scipy.special import erf

    y = np.linspace(-9, 9, 4001)
    wall = 0.5 * erf(y / np.sqrt(2))
    scale = 1.17
    alpha = 2 / 3
    analytic = _analytic_selfsimilar_strong_projection(
        y, wall, scale=scale, time_start=50, time_stop=200, alpha=alpha
    )
    first = np.gradient(wall, y, edge_order=2)
    second = np.gradient(first, y, edge_order=2)
    times = np.linspace(50, 200, 4001)
    pp = np.trapezoid(wall**2 * first**2, y) / scale * times ** (-alpha)
    pq = -np.trapezoid(wall * first * second, y) / scale**2 * times ** (-2 * alpha)
    qq = np.trapezoid(second**2, y) / scale**3 * times ** (-3 * alpha)
    pt = alpha * np.trapezoid(y * wall * first**2, y) * times ** (-1)
    qt = -alpha * np.trapezoid(y * first * second, y) / scale * times ** (-alpha - 1)
    matrix = np.array(
        [
            [np.trapezoid(pp, times), np.trapezoid(pq, times)],
            [np.trapezoid(pq, times), np.trapezoid(qq, times)],
        ]
    )
    response = np.array([np.trapezoid(pt, times), np.trapezoid(qt, times)])
    numerical = np.linalg.solve(matrix, response)
    assert np.allclose(
        numerical,
        [analytic["a"], analytic["D"]],
        rtol=2e-7,
        atol=2e-7,
    )


def test_projection_rejects_unaccepted_field_audit(tmp_path):
    audit = tmp_path / "rejected.json"
    audit.write_text(json.dumps({
        "uses_target_a_or_D": False,
        "uses_target_trajectory": False,
        "matched_integer_field_limit_accepted": False,
    }))
    with pytest.raises(ValueError, match="has not been accepted"):
        _validate_field_audit(audit, inputs=[], fields=np.asarray([]))
