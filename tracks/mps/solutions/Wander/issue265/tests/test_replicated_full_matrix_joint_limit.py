import json

import numpy as np

from scripts.audit_replicated_full_matrix_joint_limit import audit


def _write(path, field, seed, value):
    payload = {
        "uses_target_a_or_D": False,
        "uses_target_trajectory": False,
        "regulator": {
            "field": field,
            "seed": seed,
            "nodes_per_string": 12,
            "string_xi_cutoff": 6.0,
            "string_xi_buffer": 0.5,
            "scaled_rapidity_extent": 6.0,
            "scaled_rapidity_map_alpha": 3.0,
            "kernel_theta_step": 0.25,
            "fourier_points": 4,
            "samples_per_internal_wave": 8,
            "trace_distribution": "rademacher",
            "trace_source_layout": "pairwise",
            "lattice_wave_number": False,
        },
        "scaled_times_tau_equals_t_h3": [0.0, 0.4],
        "scaled_waves_q_equals_k_over_h2": [0.0, 0.4],
        "structure_factors_over_chi_by_wave_then_time": [
            [[[1.0, 0.0][i] for i in range(2)] for _ in range(2)],
            [[1.0, 0.0], [value, 0.0]],
        ],
        "iteration": {"converged": True},
        "fdt": {"positive_semidefinite": True},
        "static_susceptibility_captured_fraction": 0.99,
    }
    path.write_text(json.dumps(payload))


def test_replicated_audit_accepts_small_trace_and_field_errors(tmp_path):
    paths = []
    for field_index, field in enumerate([0.2, 1 / 6, 0.125, 0.1]):
        for repeat in range(4):
            path = tmp_path / f"h{field_index}_seed{repeat}.json"
            _write(path, field, repeat, 0.9 + 1e-5 * field + 1e-6 * (repeat - 1.5))
            paths.append(path)
    result = audit(paths, tolerance=1e-3)
    assert result["all_required_replicates_present"]
    assert result["joint_field_limit_accepted"]


def test_replicated_audit_rejects_unresolved_field_drift(tmp_path):
    paths = []
    for field_index, field in enumerate([0.2, 1 / 6, 0.125, 0.1]):
        for repeat in range(4):
            path = tmp_path / f"h{field_index}_seed{repeat}.json"
            _write(path, field, repeat, 0.9 + 0.2 * field)
            paths.append(path)
    result = audit(paths, tolerance=1e-3)
    assert not result["joint_field_limit_accepted"]
