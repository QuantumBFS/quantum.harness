from __future__ import annotations

import numpy as np
import pytest

from vmcrg_ref.neural_energy import D4EvenLocalMLP
from vmcrg_ref.neural_hamiltonian import (
    NeuralHamiltonian,
    NeuralToNeuralBiasedMetropolis,
)


def _model(seed: int) -> D4EvenLocalMLP:
    model = D4EvenLocalMLP.random(1, 4, seed, feature_mode="patch")
    model.weight_out[:] = np.random.default_rng(seed + 100).normal(0.0, 0.1, 4)
    return model


def _sampler(seed: int, *, compiled: bool = False) -> NeuralToNeuralBiasedMetropolis:
    rng = np.random.default_rng(seed)
    spins = rng.choice(np.asarray([-1, 1], dtype=np.int8), size=(9, 9))
    return NeuralToNeuralBiasedMetropolis(
        spins=spins,
        microscopic_model=_model(seed + 1),
        bias_model=_model(seed + 2),
        rng=np.random.default_rng(seed + 3),
        block_size=3,
        compiled=compiled,
    )


def test_neural_microscopic_delta_matches_negative_frozen_energy() -> None:
    rng = np.random.default_rng(10)
    spins = rng.choice(np.asarray([-1, 1], dtype=np.int8), size=(7, 7))
    model = _model(11)
    hamiltonian = NeuralHamiltonian(model, spins)
    before = -model.energy(spins)
    proposal = hamiltonian.proposal(2, 4)
    trial = spins.copy()
    trial[2, 4] *= -1
    assert hamiltonian.energy == pytest.approx(before)
    assert proposal.delta_energy == pytest.approx(-model.energy(trial) - before, abs=1e-10)
    hamiltonian.commit(proposal)
    np.testing.assert_array_equal(spins, trial)
    hamiltonian.assert_consistent(atol=1e-10)


def test_neural_to_neural_total_delta_matches_full_energy() -> None:
    sampler = _sampler(20)
    before = sampler.effective_energy
    snapshot = sampler.spins.copy()
    proposal = sampler.proposal_delta(7, 8)
    trial = sampler.spins.copy()
    trial[7, 8] *= -1
    assert sampler.full_effective_energy(trial) - before == pytest.approx(
        proposal.delta_total,
        abs=1e-10,
    )
    np.testing.assert_array_equal(sampler.spins, snapshot)


def test_dual_caches_do_not_drift_after_10000_proposals() -> None:
    sampler = _sampler(30)
    sampler.run_proposals(10_000)
    sampler.assert_cache_consistent(atol=1e-10)


def test_compiled_and_reference_paths_have_identical_trajectory() -> None:
    reference = _sampler(40, compiled=False)
    compiled = _sampler(40, compiled=True)
    stream = np.random.default_rng(41)
    sites = stream.integers(0, 9, size=(200, 2), dtype=np.int64)
    uniforms = stream.random(200)
    reference.run_proposals_with_stream(sites, uniforms)
    compiled.run_proposals_with_stream(sites, uniforms)
    np.testing.assert_array_equal(compiled.spins, reference.spins)
    np.testing.assert_array_equal(compiled.block_spins, reference.block_spins)
    np.testing.assert_allclose(
        compiled.microscopic.cache.density,
        reference.microscopic.cache.density,
        atol=1e-12,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        compiled.bias_cache.density,
        reference.bias_cache.density,
        atol=1e-12,
        rtol=0.0,
    )
    assert compiled.accepted == reference.accepted
    compiled.assert_cache_consistent(atol=1e-10)


def test_handoff_is_negative_bias_up_to_one_additive_constant() -> None:
    model = _model(50)
    hamiltonian_model = model.copy()
    rng = np.random.default_rng(51)
    configurations = rng.choice(
        np.asarray([-1, 1], dtype=np.int8),
        size=(8, 7, 7),
    )
    bias = np.asarray([model.energy(spins) for spins in configurations])
    microscopic = np.asarray(
        [NeuralHamiltonian(hamiltonian_model, spins.copy()).energy for spins in configurations]
    )
    difference = microscopic + bias
    difference -= difference.mean()
    assert np.max(np.abs(difference)) <= 1e-10


def test_pure_neural_sampler_exposes_exact_zero_linear_branch() -> None:
    sampler = _sampler(60)
    np.testing.assert_array_equal(
        sampler.fixed_linear_bias,
        np.zeros(13, dtype=np.float64),
    )


def test_refresh_bias_model_preserves_state_and_rebuilds_exact_cache() -> None:
    sampler = _sampler(70, compiled=False)
    before_spins = sampler.spins.copy()
    replacement = _model(71)
    replacement.weight_out *= 2.0
    sampler.refresh_bias_model(replacement)
    np.testing.assert_array_equal(sampler.spins, before_spins)
    assert sampler.bias_model is not replacement
    assert sampler.effective_energy == pytest.approx(
        sampler.full_effective_energy(sampler.spins),
        abs=1e-10,
    )
    sampler.assert_cache_consistent()


def test_neural_hamiltonian_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.NeuralHamiltonian is NeuralHamiltonian
    assert vmcrg_ref.NeuralToNeuralBiasedMetropolis is NeuralToNeuralBiasedMetropolis
