import json

from scripts.audit_complete_trace_pairing import complete_pairing_audit


def _write(path, pairings, seed, value, samples=4):
    payload = {
        "uses_target_a_or_D": False,
        "uses_target_trajectory": False,
        "iteration": {"converged": True},
        "regulator": {
            "field": 1 / 6,
            "nodes_per_string": 12,
            "string_xi_cutoff": 6,
            "string_xi_buffer": 1,
            "scaled_rapidity_extent": 6,
            "scaled_rapidity_map_alpha": 3,
            "kernel_theta_step": 0.25,
            "fourier_points": 4,
            "samples_per_internal_wave": samples,
            "trace_pairings_per_frame": pairings,
            "trace_distribution": "srht_rademacher",
            "trace_source_layout": "shared_wave",
            "lattice_wave_number": False,
            "seed": seed,
        },
        "scaled_times_tau_equals_t_h3": [0, 1],
        "scaled_waves_q_equals_k_over_h2": [0, 0.4, -0.8, -0.4],
        "scope": {
            "full_non_diagonal_diffusion": True,
            "full_background_fdt_noise_covariance": True,
        },
        "fdt": {"positive_semidefinite": True},
        "structure_factors_over_chi_by_wave_then_time": [
            [[1, 0], [1, 0]], [[1, 0], [value, 0]]
        ],
    }
    if pairings == samples:
        payload["regulator"].update({
            "trace_pairing_strategy": "cyclic_bipartite",
            "complete_cartesian_trace_pairing": True,
        })
        payload["scope"].update({
            "complete_cartesian_trace_pairing_is_conditional_pairing_average": True,
        })
        payload["matrix_diagnostics"] = {
            "diffusion_off_diagonal_frobenius_fraction": 0.1,
            "fdt_noise_off_diagonal_frobenius_fraction": 0.1,
            "diffusion_static_metric_commutator_relative_norm": 0.0,
        }
    path.write_text(json.dumps(payload))
    return path


def test_complete_pairing_audit_accepts_all_pairs(tmp_path):
    paths = []
    base = [0.8, 1.2, 0.9, 1.1]
    candidate = [0.94, 1.06, 0.96, 1.04]
    for seed, b, c in zip(range(4), base, candidate):
        paths.append(_write(tmp_path / f"p1_{seed}.json", 1, seed, b))
        paths.append(_write(tmp_path / f"p4_{seed}.json", 4, seed, c))
    result = complete_pairing_audit(paths, required_replicates=4)
    assert result["complete_pairing_accepted"]
    assert result["candidate_pairings_per_frame"] == 4


def test_complete_pairing_audit_rejects_partial_pairing(tmp_path):
    paths = [
        _write(tmp_path / "p1.json", 1, 1, 1.0),
        _write(tmp_path / "p2.json", 2, 1, 1.0),
    ]
    try:
        complete_pairing_audit(paths, required_replicates=1)
    except ValueError as error:
        assert "P=1 and P=S" in str(error)
    else:
        raise AssertionError("partial pairing was not rejected")
