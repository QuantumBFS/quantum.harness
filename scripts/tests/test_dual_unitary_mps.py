import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "dual_unitary_mps.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dual_unitary_mps", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dual_gate_is_unitary_in_both_directions():
    module = _load_module()
    gate = module.dual_unitary_gate(np.random.default_rng(7))
    identity = np.eye(4)
    np.testing.assert_allclose(gate.conj().T @ gate, identity, atol=2e-12)
    dual = module.dual_reshuffle(gate)
    np.testing.assert_allclose(dual.conj().T @ dual, identity, atol=2e-12)


def test_layer_event_is_random_access_deterministic():
    module = _load_module()
    first = module.layer_event(8, 0.14, 1234, 11)
    second = module.layer_event(8, 0.14, 1234, 11)
    assert first.pairs == second.pairs
    assert first.measured_sites == second.measured_sites
    np.testing.assert_array_equal(
        first.measurement_uniforms, second.measurement_uniforms
    )
    for left, right in zip(first.gates, second.gates):
        np.testing.assert_array_equal(left, right)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"L": 7, "p": 0.14, "seed": 1, "step": 0},
        {"L": 8, "p": -0.01, "seed": 1, "step": 0},
        {"L": 8, "p": 1.01, "seed": 1, "step": 0},
        {"L": 8, "p": 0.14, "seed": 1, "step": -1},
    ],
)
def test_layer_event_rejects_invalid_parameters(kwargs):
    module = _load_module()
    with pytest.raises(ValueError):
        module.layer_event(**kwargs)


@pytest.mark.parametrize("L,chi", [(4, 4), (6, 8)])
def test_untruncated_mps_matches_dense_record_probability(L, chi):
    module = _load_module()
    kwargs = dict(
        L=L,
        p=0.37,
        seed=41,
        burn_in_steps=2,
        record_steps=7,
    )
    dense = module.run_dense_oracle(**kwargs)
    mps = module.run_mps_trajectory(**kwargs, chi=chi, cutoff=0.0)
    np.testing.assert_allclose(
        mps["cumulative_record_cost"],
        dense["cumulative_record_cost"],
        rtol=2e-10,
        atol=2e-11,
    )
    assert mps["outcome_counts"] == dense["outcome_counts"]
    assert mps["discarded_weight_sum"] < 1e-24


def test_mps_measurement_matches_dense_projection():
    module = _load_module()
    vectors = module.product_state_vectors(5, seed=73)
    mps = module.CanonicalMPS.product_state(vectors)
    dense = module.product_state_dense(vectors)
    gate = module.dual_unitary_gate(np.random.default_rng(9))
    mps.apply_adjacent_gate(1, gate, chi=16, cutoff=0.0)
    module.apply_dense_gate_inplace(dense, gate, (1, 2), 5)

    outcome, probability = mps.measure_z(2, uniform=0.63)
    dense_outcome, dense_probability = module.measure_dense_z_inplace(
        dense, 2, 5, uniform=0.63
    )

    assert outcome == dense_outcome
    assert probability == pytest.approx(dense_probability, abs=2e-13)
    overlap = np.vdot(dense, mps.to_dense())
    assert abs(abs(overlap) - 1.0) < 2e-12


def test_truncating_gate_reports_discarded_weight_and_respects_chi():
    module = _load_module()
    vectors = module.product_state_vectors(4, seed=5)
    mps = module.CanonicalMPS.product_state(vectors)
    gate = module.dual_unitary_gate(np.random.default_rng(17))
    discarded = mps.apply_adjacent_gate(1, gate, chi=1, cutoff=0.0)
    assert 0.0 < discarded < 1.0
    assert mps.max_bond <= 1
    assert np.linalg.norm(mps.to_dense()) == pytest.approx(1.0, abs=2e-12)


def test_trajectory_progress_is_periodic_and_flushed(capsys):
    module = _load_module()
    module.run_mps_trajectory(
        L=4,
        p=0.14,
        chi=4,
        seed=101,
        burn_in_steps=1,
        record_steps=3,
        cutoff=0.0,
        progress_every=2,
    )
    output = capsys.readouterr().out
    assert "step=2/4" in output
    assert "step=4/4" in output


def test_gate_split_falls_back_to_robust_svd_driver(monkeypatch):
    module = _load_module()
    vectors = module.product_state_vectors(4, seed=23)
    mps = module.CanonicalMPS.product_state(vectors)
    gate = module.dual_unitary_gate(np.random.default_rng(29))

    def fail_gesdd(*args, **kwargs):
        raise np.linalg.LinAlgError("SVD did not converge")

    monkeypatch.setattr(module.np.linalg, "svd", fail_gesdd)
    discarded = mps.apply_adjacent_gate(1, gate, chi=4, cutoff=0.0)
    assert discarded >= 0.0
    assert np.all(np.isfinite(mps.to_dense()))
