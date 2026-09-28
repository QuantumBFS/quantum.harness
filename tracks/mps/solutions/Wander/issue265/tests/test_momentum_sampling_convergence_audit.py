import json

from scripts.audit_momentum_sampling_convergence import audit


def _inputs(tmp_path, count, offsets):
    paths = []
    for seed, offset in enumerate(offsets):
        payload = {
            "uses_target_a_or_D": False,
            "uses_target_trajectory": False,
            "regulator": {
                "field": 0.2,
                "seed": seed,
                "trace_distribution": "srht_rademacher",
                "trace_source_layout": "shared_wave",
                "trace_pairings_per_frame": 4,
                "momentum_samples_per_external_wave": count,
            },
            "iteration": {"converged": True},
            "fdt": {"positive_semidefinite": True},
            "scope": {
                "full_non_diagonal_diffusion": True,
                "full_background_fdt_noise_covariance": True,
            },
            "matrix_diagnostics": {
                "diffusion_off_diagonal_frobenius_fraction": 0.18,
                "fdt_noise_off_diagonal_frobenius_fraction": 0.05,
                "diffusion_static_metric_commutator_relative_norm": 1e-17,
            },
            "scaled_waves_q_equals_k_over_h2": [0.0, 0.25],
            "scaled_times_tau_equals_t_h3": [0.0, 0.8],
            "structure_factors_over_chi_by_wave_then_time": [
                [[1.0, 0.0], [1.0, 0.0]],
                [[1.0, 0.0], [0.8 + offset, 0.0]],
            ],
        }
        path = tmp_path / f"P{count}_{seed}.json"
        path.write_text(json.dumps(payload))
        paths.append(path)
    return paths


def test_paired_momentum_sampling_audit_accepts_small_difference(tmp_path):
    lower = _inputs(tmp_path, 4, [-2e-4, 2e-4, -1e-4, 1e-4])
    higher = _inputs(tmp_path, 8, [0.0, 0.0, 0.0, 0.0])
    result = audit(lower, higher, tolerance=1e-3, sigma_multiplier=2.0)
    assert result["accepted"]
    assert result["higher_momentum_samples"] == 8
    assert result["trace_pairings_per_frame"] == 4


def test_paired_momentum_sampling_audit_rejects_resolved_shift(tmp_path):
    lower = _inputs(tmp_path, 4, [0.0, 0.0, 0.0, 0.0])
    higher = _inputs(tmp_path, 8, [0.01, 0.01, 0.01, 0.01])
    result = audit(lower, higher, tolerance=1e-3, sigma_multiplier=2.0)
    assert not result["accepted"]
    assert result["maximum_paired_difference_sigma_bound"] > 1e-3
