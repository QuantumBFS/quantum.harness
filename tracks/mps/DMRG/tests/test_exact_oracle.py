from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from vmcrg_ref.exact_oracle import (
    compare_small_neural_gradients,
    enumerate_rectangular_blocking,
    exact_handoff_energy,
    exact_local_energy_delta,
    exact_objective,
    exact_objective_per_site,
    exact_parameter_gradient,
    flatten_mlp_gradient,
    target_distribution_distances,
)


def test_3x6_oracle_enumerates_every_microstate() -> None:
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    assert result.microstate_count == 2**18
    assert result.coarse_shape == (1, 2)
    assert result.coarse_state_count == 4
    np.testing.assert_allclose(result.coarse_probability.sum(), 1.0, atol=1e-15)
    assert np.all(result.coarse_probability > 0.0)


def test_exact_objective_gradient_matches_finite_difference() -> None:
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    features = result.coarse_nn[:, None]
    target = np.full(result.coarse_state_count, 1.0 / result.coarse_state_count)
    theta = np.array([0.1])
    grad = exact_parameter_gradient(result, features, theta, target)
    epsilon = 1e-6
    plus = exact_objective(result, features @ (theta + epsilon), target)
    minus = exact_objective(result, features @ (theta - epsilon), target)
    assert grad[0] == pytest.approx((plus - minus) / (2.0 * epsilon), abs=1e-8)


def test_exact_objective_normalizes_by_coarse_sites_not_state_count() -> None:
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    target = np.full(result.coarse_state_count, 1.0 / result.coarse_state_count)
    bias = np.array([0.0, 0.2, -0.1, 0.4])
    total = exact_objective(result, bias, target)
    assert exact_objective_per_site(result, bias, target) == pytest.approx(total / 2.0)


def test_target_distance_and_bias_sign_are_explicit() -> None:
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    target = np.full(result.coarse_state_count, 1.0 / result.coarse_state_count)
    distances = target_distribution_distances(result.coarse_probability, target)
    assert distances["total_variation"] >= 0.0
    assert distances["jensen_shannon"] >= 0.0
    bias = np.arange(result.coarse_state_count, dtype=np.float64)
    np.testing.assert_array_equal(exact_handoff_energy(bias), -bias)


def test_rectangular_local_energy_delta_matches_full_recomputation() -> None:
    rng = np.random.default_rng(2026072804)
    spins = rng.choice(np.asarray([-1, 1], dtype=np.int8), size=(3, 6))
    before = exact_local_energy_delta(spins, 0, 0, 0.436, direct_only=True)
    trial = spins.copy()
    trial[0, 0] *= -1
    direct = exact_local_energy_delta(trial, 0, 0, 0.436, direct_only=True)
    assert before != direct
    assert exact_local_energy_delta(spins, 0, 0, 0.436) == pytest.approx(
        direct - before
    )


def test_oracle_rejects_bad_target_and_nondivisible_blocks() -> None:
    with pytest.raises(ValueError, match="divisible"):
        enumerate_rectangular_blocking(4, 6, 3, 0.436)
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    with pytest.raises(ValueError, match="probability"):
        exact_objective(result, np.zeros(result.coarse_state_count), np.array([1.0]))


def test_exact_oracle_cli_writes_json_from_fresh_checkout(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    output = tmp_path / "n0"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/issue28_exact_oracle.py",
            "--protocol",
            "config/issue28_n0_v1.json",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (output / "exact_blocking.json").is_file()
    assert (output / "neural_gradient.json").is_file()
    assert (output / "manifest.json").is_file()


def test_exact_oracle_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.enumerate_rectangular_blocking is enumerate_rectangular_blocking


def test_legacy_exact_module_reexports_n0_blocking_oracle() -> None:
    from vmcrg_ref.exact import enumerate_rectangular_blocking as legacy

    assert legacy is enumerate_rectangular_blocking


def test_small_identity_oracle_gradients_agree() -> None:
    report = compare_small_neural_gradients(
        length=3,
        radius=1,
        hidden=3,
        seed=2026072801,
    )
    assert report["jax_vs_analytic_linf"] <= 1e-9
    assert report["jax_vs_finite_difference_linf"] <= 1e-6
    assert report["exact_vs_mc_all_z_below"]
    assert report["exact_vs_mc_max_abs_z"] <= report[
        "mc_bonferroni_critical_abs_z"
    ]
    assert report["jax_devices"]


def test_jax_gradient_helpers_are_exported() -> None:
    import vmcrg_ref

    assert vmcrg_ref.flatten_mlp_gradient is flatten_mlp_gradient
    assert callable(vmcrg_ref.jax_exact_neural_gradient)


def test_n0_config_rejects_jax_platform_or_precision_drift() -> None:
    from scripts.issue28_exact_oracle import validate_n0_config

    value = json.loads(Path("config/issue28_n0_v1.json").read_text(encoding="ascii"))
    value["jax"]["platform"] = "gpu"
    with pytest.raises(ValueError, match="JAX"):
        validate_n0_config(value)
