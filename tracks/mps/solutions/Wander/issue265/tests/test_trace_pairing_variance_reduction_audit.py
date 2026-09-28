import json

from scripts.audit_trace_pairing_variance_reduction import audit


def _write(path, pairing_count, seed, value):
    payload = {
        "uses_target_a_or_D": False,
        "uses_target_trajectory": False,
        "regulator": {
            "field": 1 / 6,
            "seed": seed,
            "nodes_per_string": 12,
            "string_xi_cutoff": 6.0,
            "string_xi_buffer": 0.5,
            "scaled_rapidity_extent": 6.0,
            "scaled_rapidity_map_alpha": 3.0,
            "kernel_theta_step": 0.25,
            "fourier_points": 4,
            "samples_per_internal_wave": 8,
            "trace_pairings_per_frame": pairing_count,
            "trace_distribution": "srht_rademacher",
            "trace_source_layout": "shared_wave",
            "lattice_wave_number": False,
        },
        "iteration": {"converged": True},
        "fdt": {"positive_semidefinite": True},
        "scope": {
            "full_non_diagonal_diffusion": True,
            "full_background_fdt_noise_covariance": True,
        },
        "scaled_times_tau_equals_t_h3": [0.0, 0.8],
        "scaled_waves_q_equals_k_over_h2": [0.0, 0.4],
        "structure_factors_over_chi_by_wave_then_time": [
            [[1.0, 0.0], [1.0, 0.0]],
            [[1.0, 0.0], [value, 0.0]],
        ],
    }
    if pairing_count > 1:
        payload["matrix_diagnostics"] = {
            "diffusion_off_diagonal_frobenius_fraction": 0.18,
            "fdt_noise_off_diagonal_frobenius_fraction": 0.05,
            "diffusion_static_metric_commutator_relative_norm": 1e-17,
        }
    path.write_text(json.dumps(payload))


def test_pairing_audit_accepts_unbiased_variance_reduction(tmp_path):
    paths = []
    for count, noise in [(1, [-0.03, 0.03, -0.02, 0.02]), (4, [-0.01, 0.01, -0.008, 0.008])]:
        for seed, delta in enumerate(noise):
            path = tmp_path / f"p{count}_seed{seed}.json"
            _write(path, count, seed, 0.85 + delta)
            paths.append(path)
    result = audit(paths)
    assert result["trace_pairing_variance_reduction_accepted"]
    assert result["rows"][1]["real_variance_ratio_to_single_pairing"] < 1
    assert result["rows"][1]["endpoint_complex_sem"] < result["rows"][0]["endpoint_complex_sem"]
    assert result["rows"][1]["plugin_minimum_independent_replicates_for_target_sem"] < result["rows"][0]["plugin_minimum_independent_replicates_for_target_sem"]
    assert result["replicate_count_estimate_is_plugin_not_acceptance_evidence"]
    assert result["rows"][1]["full_matrix_operator_evidence"]["diffusion_off_diagonal_frobenius_fraction_range"] == [0.18, 0.18]


def test_pairing_audit_rejects_mean_shift(tmp_path):
    paths = []
    for count, center in [(1, 0.85), (4, 0.95)]:
        for seed, delta in enumerate([-0.01, 0.01, -0.008, 0.008]):
            path = tmp_path / f"p{count}_seed{seed}.json"
            _write(path, count, seed, center + delta)
            paths.append(path)
    result = audit(paths)
    assert not result["trace_pairing_variance_reduction_accepted"]
