from __future__ import annotations

import numpy as np

from spinglass3d.gauge import gauge_transform
from spinglass3d.linear_bias import LinearFeatureBasis
from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder


def test_primary_linear_baseline_uses_only_gauge_invariants() -> None:
    basis = LinearFeatureBasis.cube_v1()
    assert basis.names == (
        "q_pair_nn",
        "q_pair_face",
        "q_plaquette",
        "flux_q_pair_nn",
        "flux_q_plaquette",
    )
    assert all(feature.q_parity % 2 == 0 for feature in basis.features)
    assert all(feature.gauge_invariant for feature in basis.features)


def test_local_and_lattice_features_are_gauge_and_q_inversion_invariant() -> None:
    rng = np.random.default_rng(2026072915)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    epsilon = rng.choice(np.array([-1, 1], dtype=np.int8), size=(9, 9, 9))
    encoder = TemplateEncoder("cube", True, 1)
    basis = LinearFeatureBasis.cube_v1()
    tokens = encoder.encode(q, bonds, (0, 0, 0))
    transformed = encoder.encode(q, gauge_transform(bonds, epsilon), (0, 0, 0))
    np.testing.assert_allclose(
        basis.local_features(tokens, encoder),
        basis.local_features(transformed, encoder),
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        basis.local_features(encoder.flip_q_tokens(tokens), encoder),
        basis.local_features(tokens, encoder),
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        basis.values(-q, bonds, encoder),
        basis.values(q, bonds, encoder),
        atol=2e-13,
        rtol=0.0,
    )


def test_q_only_subset_is_labeled_as_ablation() -> None:
    subset = LinearFeatureBasis.cube_v1().q_only_ablation()
    assert subset.names == ("q_pair_nn", "q_pair_face", "q_plaquette")
    assert subset.is_primary_comparator is False
