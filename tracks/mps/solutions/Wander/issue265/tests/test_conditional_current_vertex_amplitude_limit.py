import numpy as np
import json

from scripts.derive_conditional_current_vertex_amplitude_limit import derive
from scripts.invert_finite_time_mori_from_walls import _require_gate


def _pair(mu: float) -> dict:
    def value(sign: int) -> float:
        return 0.231 + 0.7 * mu**2 - 1.2 * mu**4 + sign * (0.4 * mu - 0.9 * mu**3)

    tag = str(mu).replace(".", "")
    return {
        "inputs": {
            "mu": mu,
            "t_window": [50.0, 200.0],
            "target_coefficients_used": False,
            "up_condition_id": f"amp_{tag}_up",
            "down_condition_id": f"amp_{tag}_down",
        },
        "microscopic_current_vertex": {
            "up": {"a_current_vertex": value(1)},
            "down": {"a_current_vertex": value(-1)},
        },
        "mori_k0_correction": {
            "s": [0.5, 1.0, 2.0],
            "delta_K1_total_truncated": [
                -0.25 + 0.3 * mu**2,
                -0.28 - 0.2 * mu**2,
                -0.31 + 0.1 * mu**2,
            ],
        },
        "frozen_weak_projection": {"D": 1.97 + 0.5 * mu**2},
    }


def test_four_pair_certificate_recovers_one_sided_intercept_without_target() -> None:
    result = derive([_pair(mu) for mu in (0.02, 0.05, 0.10, 0.20)])
    assert result["inputs"]["target_coefficients_used"] is False
    assert result["exact_physical_zero_field_quadratic_kubo_vertex"] == 0.0
    assert np.isclose(
        result["conditional_one_sided_vertex"]["a0_one_sided"], 0.231, atol=2e-13
    )
    assert np.allclose(
        result["linear_mori_zero_amplitude"]["zero_amplitude_limit"],
        [-0.25, -0.28, -0.31],
        atol=2e-13,
    )
    assert np.isclose(
        result["declared_weak_projection_D_zero_amplitude"][
            "zero_amplitude_limit"
        ][0],
        1.97,
        atol=2e-13,
    )


def test_pair_inversion_accepts_only_complete_valid_production_outputs(tmp_path) -> None:
    payload = {
        "status": "complete",
        "all_complete": True,
        "submission_complete": True,
        "jobs": [
            {
                "status": "complete",
                "job": {"condition_id": condition_id},
                "validation": {"status": "valid"},
            }
            for condition_id in ("amp_mu002_up", "amp_mu002_down")
        ],
    }
    path = tmp_path / "production_a.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    _require_gate(path, "amp_mu002_up", "amp_mu002_down")
    payload["jobs"][1]["validation"]["status"] = "invalid"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        _require_gate(path, "amp_mu002_up", "amp_mu002_down")
    except RuntimeError:
        pass
    else:
        raise AssertionError("invalid Production A output must be rejected")
