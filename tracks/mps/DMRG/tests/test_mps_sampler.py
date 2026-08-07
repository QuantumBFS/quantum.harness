from __future__ import annotations

import numpy as np

from vmcrg_ref.exact import exact_nearest_neighbor_moments
from vmcrg_ref.fast import FastMultiOperatorBiasedMetropolis
from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


def test_metropolis_small_lattice_against_exact() -> None:
    coupling = 0.31
    shape = (EVEN_SHAPES[0],)
    rng = np.random.default_rng(20260900)
    basis = OperatorBasis(4, shape)
    sampler = FastMultiOperatorBiasedMetropolis(
        IsingLattice.random(4, rng),
        np.array([coupling]),
        np.zeros(1),
        rng,
        shape,
        block_size=1,
        micro_basis=basis,
        block_basis=basis,
    )
    sampler.run_sweeps(2000)
    micro_sum, _, _, _ = sampler.measure_moments(
        measurements=30000, sweeps_between=1
    )
    sampled_mean = float(micro_sum[0] / 30000)
    exact_mean, _ = exact_nearest_neighbor_moments(4, coupling)
    assert abs(sampled_mean - exact_mean) < 0.25
