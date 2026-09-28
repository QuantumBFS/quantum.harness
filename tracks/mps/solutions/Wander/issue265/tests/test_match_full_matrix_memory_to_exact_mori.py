from __future__ import annotations

import numpy as np

from scripts.match_full_matrix_memory_to_exact_mori import derive


def _payload(seed: int, perturbation: float = 0.0) -> dict[str, object]:
    times = np.linspace(0.0, 40.0, 401)
    memory = np.exp(-0.4 * times) * np.cos(0.2 * times)
    memory *= 1.0 + perturbation * np.exp(-0.2 * times)
    pairs = [[[0.0, 0.0] for _ in times] for _ in range(4)]
    pairs[1] = [[float(value), 0.0] for value in memory]
    pairs[3] = [[float(value), 0.0] for value in memory]
    structure = np.exp(-0.01 * times)
    structure_pairs = [[[1.0, 0.0] for _ in times] for _ in range(4)]
    structure_pairs[1] = [[float(value), 0.0] for value in structure]
    structure_pairs[3] = [[float(value), 0.0] for value in structure]
    return {
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "times": times.tolist(),
        "waves": [0.0, 0.17, -0.34, -0.17],
        "regulator": {
            "field": 0.2,
            "mode_count": 32,
            "nodes_per_string": 8,
            "string_xi_cutoff": 4.0,
            "fourier_points": 4,
            "wave_step": 0.17,
            "trace_pairings_per_frame": 2,
            "trace_source_layout": "shared_wave",
            "seed": seed,
        },
        "iteration": {"converged": True},
        "scope": {
            "full_non_diagonal_diffusion": True,
            "full_background_fdt_noise_covariance": True,
            "colored_memory_available_for_exact_mori_prefix_matching": True,
            "white_noise_contact_inserted_into_colored_memory": False,
        },
        "projected_colored_continuity_memory_by_wave_then_time": pairs,
        "structure_factors_over_chi_by_wave_then_time": structure_pairs,
    }


def test_replicated_full_matrix_memory_preserves_exact_prefix_without_poles() -> None:
    payloads = [
        _payload(265, 0.001),
        _payload(1265, -0.001),
        _payload(2265, 0.0005),
        _payload(3265, -0.0005),
    ]
    result = derive(
        payloads,
        laplace_frequencies=np.asarray([0.1, 0.2, 0.4, 0.8]),
        spectral_nodes=128,
        spectral_maximum=20.0,
        time_tail_fraction=0.75,
        hierarchy_dt=0.1,
    )
    assert result["gates"]["exact_finite_k_mu16_prefix_preserved"]
    assert result["gates"]["positive_continuum_terminator"]
    assert not result["scope"]["finite_pole_count_assumed"]
    assert not result["scope"]["second_hydrodynamic_field_assumed"]
    assert not result["scope"]["target_fit_performed"]
    assert not result["gates"]["physical_F1_certified"]
    completion = result["time_domain_microscopic_completion"]
    assert completion["exact_prefix_mori_kernel"][0] == 0.5
    assert completion["exact_prefix_structure_factor_over_chi"][0] == 1.0
    assert completion["terminator_obtained_by_top_level_continuity_inversion"]
    assert not result["fine_exact_prefix_match"][
        "hydrodynamic_force_shape_used_as_deep_terminator"
    ]
