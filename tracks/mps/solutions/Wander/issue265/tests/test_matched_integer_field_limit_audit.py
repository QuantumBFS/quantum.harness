import json

import pytest

from scripts.audit_matched_integer_field_limit import audit


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
            "trace_pairings_per_frame": 4,
            "trace_distribution": "srht_rademacher",
            "trace_source_layout": "shared_wave",
            "lattice_wave_number": False,
        },
        "scaled_times_tau_equals_t_h3": [0.0, 0.8],
        "scaled_waves_q_equals_k_over_h2": [0.0, 0.4],
        "structure_factors_over_chi_by_wave_then_time": [
            [[1.0, 0.0], [1.0, 0.0]],
            [[1.0, 0.0], [value, 0.0]],
        ],
        "iteration": {"converged": True},
        "fdt": {"positive_semidefinite": True},
        "static_susceptibility_captured_fraction": 0.99,
    }
    path.write_text(json.dumps(payload))


def test_matched_integer_audit_requires_five_fields(tmp_path):
    paths = []
    for field_index, field in enumerate([0.2, 1 / 6, 0.125, 0.1]):
        for seed in range(4):
            path = tmp_path / f"h{field_index}_seed{seed}.json"
            _write(path, field, seed, 0.9 + 0.02 * field)
            paths.append(path)
    with pytest.raises(ValueError, match="at least five fields"):
        audit(paths)


def test_matched_integer_audit_accepts_smooth_small_uncertainty_sequence(tmp_path):
    paths = []
    fields = [0.2, 1 / 6, 0.125, 0.1, 1 / 12]
    for field_index, field in enumerate(fields):
        for seed in range(4):
            path = tmp_path / f"h{field_index}_seed{seed}.json"
            value = 0.9 + 0.02 * field - 0.01 * field**2 + 1e-6 * (seed - 1.5)
            _write(path, field, seed, value)
            paths.append(path)
    result = audit(paths)
    assert result["matched_integer_field_limit_accepted"]


def test_matched_integer_audit_rejects_nonanalytic_finest_field(tmp_path):
    paths = []
    fields = [0.2, 1 / 6, 0.125, 0.1, 1 / 12]
    for field_index, field in enumerate(fields):
        for seed in range(4):
            path = tmp_path / f"h{field_index}_seed{seed}.json"
            value = 0.9 + 0.02 * field + (0.02 if field_index == 4 else 0.0)
            _write(path, field, seed, value + 1e-6 * (seed - 1.5))
            paths.append(path)
    result = audit(paths)
    assert not result["matched_integer_field_limit_accepted"]
