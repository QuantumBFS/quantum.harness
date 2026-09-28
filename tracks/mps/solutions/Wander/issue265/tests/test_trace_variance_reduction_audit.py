import json

import numpy as np

from scripts.audit_trace_variance_reduction import audit


def _write_group(tmp_path, distribution, values):
    paths = []
    for seed, value in enumerate(values):
        payload = {
            "uses_target_a_or_D": False,
            "uses_target_trajectory": False,
            "regulator": {
                "field": 0.2,
                "seed": seed,
                "trace_distribution": distribution,
            },
            "iteration": {"converged": True},
            "scaled_waves_q_equals_k_over_h2": [0.0, 0.4],
            "scaled_times_tau_equals_t_h3": [0.0, 0.8],
            "structure_factors_over_chi_by_wave_then_time": [
                [[1.0, 0.0], [1.0, 0.0]],
                [[1.0, 0.0], [float(value), 0.0]],
            ],
        }
        path = tmp_path / f"{distribution}_{seed}.json"
        path.write_text(json.dumps(payload))
        paths.append(path)
    return paths


def test_variance_reduction_audit_accepts_lower_variance_compatible_mean(tmp_path):
    ordinary = _write_group(tmp_path, "rademacher", [0.8, 1.2, 0.7, 1.3])
    candidate = _write_group(tmp_path, "srht_rademacher", [0.94, 1.06, 0.96, 1.04])
    result = audit(
        ordinary,
        candidate,
        scaled_wave=0.4,
        scaled_time=0.8,
        maximum_variance_ratio=0.75,
        maximum_mean_difference_sigma=2.0,
    )
    assert result["accepted"]
    assert result["observed_real_variance_ratio"] < 0.1
    assert not result["uses_target_a_or_D"]


def test_variance_reduction_audit_rejects_shifted_mean(tmp_path):
    ordinary = _write_group(tmp_path, "rademacher", [0.9, 1.1, 0.85, 1.15])
    candidate = _write_group(tmp_path, "srht_rademacher", [1.49, 1.51, 1.48, 1.52])
    result = audit(
        ordinary,
        candidate,
        scaled_wave=0.4,
        scaled_time=0.8,
        maximum_variance_ratio=0.75,
        maximum_mean_difference_sigma=2.0,
    )
    assert not result["accepted"]
    assert result["observed_mean_difference_sigma"] > 2.0
