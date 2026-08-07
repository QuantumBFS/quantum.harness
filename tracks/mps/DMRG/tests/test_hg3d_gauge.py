from __future__ import annotations

import numpy as np

from spinglass3d.gauge import canonical_chords, gauge_transform
from spinglass3d.model import EABonds, energy


def test_full_lattice_gauge_transform_preserves_energy() -> None:
    rng = np.random.default_rng(2026072908)
    bonds = EABonds.sample(6, rng)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(6, 6, 6))
    epsilon = rng.choice(np.array([-1, 1], dtype=np.int8), size=spins.shape)
    transformed = gauge_transform(bonds, epsilon)
    np.testing.assert_array_equal(epsilon * spins, (epsilon * spins).astype(np.int8))
    assert energy(spins, bonds) == energy(epsilon * spins, transformed)


def test_canonical_chords_are_vertex_gauge_invariant() -> None:
    edges = {
        (0, 1): -1,
        (0, 2): 1,
        (1, 2): -1,
        (1, 3): 1,
        (2, 3): -1,
    }
    tree = ((0, 1), (0, 2), (1, 3))
    epsilon = {0: 1, 1: -1, 2: -1, 3: 1}
    transformed = {
        edge: sign * epsilon[edge[0]] * epsilon[edge[1]]
        for edge, sign in edges.items()
    }
    np.testing.assert_array_equal(
        canonical_chords(edges, tree),
        canonical_chords(transformed, tree),
    )
