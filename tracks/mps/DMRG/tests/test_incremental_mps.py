from __future__ import annotations

import numpy as np

from vmcrg_ref.blockspin import block_majority
from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.mps_sampler import MPSBiasedMetropolis
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis
from vmcrg_ref.patch_table import PatchEnergyCache, PatchLookupTable


def nonzero_lookup(seed: int = 20260850) -> PatchLookupTable:
    return PatchLookupTable.from_model(PatchMPS.random(chi=2, seed=seed))


def test_neural_delta_matches_full_recompute() -> None:
    rng = np.random.default_rng(20260851)
    couplings = np.zeros(len(EVEN_SHAPES))
    couplings[0] = 0.436
    linear_bias = np.linspace(-0.02, 0.004, len(EVEN_SHAPES))
    lookup = nonzero_lookup()
    alpha = 0.3
    sampler = MPSBiasedMetropolis(
        IsingLattice.random(15, rng),
        couplings,
        linear_bias,
        alpha,
        lookup,
        rng,
        EVEN_SHAPES,
        compiled=False,
    )
    micro_basis = OperatorBasis(15, EVEN_SHAPES)
    block_basis = OperatorBasis(5, EVEN_SHAPES)

    for x, y in ((0, 0), (7, 4), (14, 14)):
        before = sampler.effective_hamiltonian
        proposal = sampler.proposal_delta(x, y)
        trial = sampler.lattice.spins.copy()
        trial[x, y] *= -1
        trial_block = block_majority(trial, 3)
        after = float(
            couplings @ micro_basis.values(trial)
            + linear_bias @ block_basis.values(trial_block)
            + alpha * PatchEnergyCache(trial_block, lookup).energy
        )
        assert abs((after - before) - proposal.delta_hamiltonian) < 1e-10


def test_zero_alpha_matches_traditional_effective_energy() -> None:
    rng = np.random.default_rng(20260852)
    couplings = np.zeros(len(EVEN_SHAPES))
    couplings[0] = 0.436
    linear_bias = np.linspace(-0.03, 0.006, len(EVEN_SHAPES))
    sampler = MPSBiasedMetropolis(
        IsingLattice.random(15, rng),
        couplings,
        linear_bias,
        0.0,
        nonzero_lookup(20260853),
        rng,
        EVEN_SHAPES,
        compiled=False,
    )
    expected = float(
        couplings @ sampler.micro_basis.values(sampler.lattice.spins)
        + linear_bias @ sampler.block_basis.values(sampler.rg_state.coarse_spins)
    )
    assert sampler.effective_hamiltonian == expected


def test_compiled_mps_sampler_matches_reference_trajectory() -> None:
    initial = IsingLattice.random(15, np.random.default_rng(20260854)).spins.copy()
    couplings = np.zeros(len(EVEN_SHAPES))
    couplings[0] = 0.436
    linear_bias = np.linspace(-0.02, 0.004, len(EVEN_SHAPES))
    lookup = nonzero_lookup(20260855)
    micro_basis = OperatorBasis(15, EVEN_SHAPES)
    block_basis = OperatorBasis(5, EVEN_SHAPES)
    reference = MPSBiasedMetropolis(
        IsingLattice(initial.copy()),
        couplings,
        linear_bias,
        0.2,
        lookup,
        np.random.default_rng(20260856),
        EVEN_SHAPES,
        compiled=False,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )
    compiled = MPSBiasedMetropolis(
        IsingLattice(initial.copy()),
        couplings,
        linear_bias,
        0.2,
        lookup,
        np.random.default_rng(20260856),
        EVEN_SHAPES,
        compiled=True,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )
    reference.run_sweeps(2)
    compiled.run_sweeps(2)
    np.testing.assert_array_equal(compiled.lattice.spins, reference.lattice.spins)
    np.testing.assert_array_equal(
        compiled.rg_state.coarse_spins, reference.rg_state.coarse_spins
    )
    np.testing.assert_array_equal(compiled.micro_values, reference.micro_values)
    np.testing.assert_array_equal(compiled.block_values, reference.block_values)
    np.testing.assert_array_equal(
        compiled.patch_cache.pattern_ids, reference.patch_cache.pattern_ids
    )
    np.testing.assert_allclose(
        compiled.patch_cache.values, reference.patch_cache.values, atol=1e-12, rtol=0.0
    )
    assert compiled.accepted == reference.accepted
    assert compiled.attempted == reference.attempted
    compiled.assert_cache_consistent()


def test_two_level_sampler_delta_matches_composite_full_recompute() -> None:
    rng = np.random.default_rng(20260857)
    shapes = (EVEN_SHAPES[0],)
    couplings = np.array([0.436])
    linear_bias = np.array([-0.1])
    lookup = nonzero_lookup(20260858)
    sampler = MPSBiasedMetropolis(
        IsingLattice.random(45, rng),
        couplings,
        linear_bias,
        0.15,
        lookup,
        rng,
        shapes,
        rg_levels=2,
        compiled=False,
    )
    x, y = 13, 22
    before = sampler.effective_hamiltonian
    proposal = sampler.proposal_delta(x, y)
    trial = sampler.lattice.spins.copy()
    trial[x, y] *= -1
    level1 = block_majority(trial, 3)
    level2 = block_majority(level1, 3)
    after = float(
        couplings @ sampler.micro_basis.values(trial)
        + linear_bias @ sampler.block_basis.values(level2)
        + 0.15 * PatchEnergyCache(level2, lookup).energy
    )
    assert abs((after - before) - proposal.delta_hamiltonian) < 1e-10


def test_reproducibility_same_seed() -> None:
    def run() -> tuple[np.ndarray, int, int]:
        rng = np.random.default_rng(20260859)
        couplings = np.zeros(len(EVEN_SHAPES))
        couplings[0] = 0.436
        sampler = MPSBiasedMetropolis(
            IsingLattice.random(15, rng),
            couplings,
            np.zeros(len(EVEN_SHAPES)),
            0.1,
            nonzero_lookup(20260860),
            rng,
            EVEN_SHAPES,
            compiled=True,
        )
        sampler.run_sweeps(3)
        return sampler.lattice.spins.copy(), sampler.attempted, sampler.accepted

    first = run()
    second = run()
    np.testing.assert_array_equal(first[0], second[0])
    assert first[1:] == second[1:]
