from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.model import EABonds
from spinglass3d.symmetry import CubicTransform, cubic_transforms, symmetry_images
from spinglass3d.templates import TemplateEncoder, TemplateKind


def _transform_lattice(
    q: np.ndarray,
    bonds: EABonds,
    encoder: TemplateEncoder,
    transform: CubicTransform,
) -> tuple[np.ndarray, EABonds]:
    matrix_inverse = transform.matrix.T.astype(np.int64)
    unit = np.ones(3, dtype=np.int64)
    if encoder.kind is TemplateKind.CUBE:
        q_shift = (unit - matrix_inverse @ unit) // 2
        bond_shift = (3**encoder.rg_level) * q_shift
    else:
        q_shift = np.zeros(3, dtype=np.int64)
        bond_shift = np.zeros(3, dtype=np.int64)

    transformed_q = np.empty_like(q)
    for site in np.ndindex(q.shape):
        source = tuple(
            int(value % q.shape[0])
            for value in matrix_inverse @ np.asarray(site) + q_shift
        )
        transformed_q[site] = q[source]

    transformed_bonds = np.empty_like(bonds.values)
    for site in np.ndindex((bonds.length,) * 3):
        source_site = (
            matrix_inverse @ np.asarray(site, dtype=np.int64) + bond_shift
        ) % bonds.length
        for target_axis in range(3):
            direction = matrix_inverse[:, target_axis]
            source_axis = int(np.flatnonzero(direction)[0])
            source_start = source_site.copy()
            if direction[source_axis] < 0:
                source_start[source_axis] = (
                    source_start[source_axis] - 1
                ) % bonds.length
            transformed_bonds[site + (target_axis,)] = bonds.values[
                tuple(int(value) for value in source_start) + (source_axis,)
            ]
    return transformed_q, EABonds(transformed_bonds)


def test_cubic_group_has_48_unique_closed_actions() -> None:
    group = cubic_transforms()
    assert len(group) == 48
    keys = {transform.key for transform in group}
    assert len(keys) == 48
    for transform in group:
        assert transform.determinant in (-1, 1)
        assert transform.inverse().key in keys
    for left in group:
        for right in group:
            assert left.compose(right).key in keys


@pytest.mark.parametrize("kind", tuple(TemplateKind))
def test_symmetry_images_and_q_inversion_are_structural(kind: TemplateKind) -> None:
    rng = np.random.default_rng(2026072911)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    encoder = TemplateEncoder(kind, conditioned=True, rg_level=1)
    tokens = encoder.encode(q, bonds, (0, 0, 0))
    images = symmetry_images(tokens, encoder)
    assert len(images) == 48
    assert all(image.shape == (encoder.token_count,) for image in images)
    assert all(set(np.unique(image)) <= {-1, 1} for image in images)
    flipped = encoder.flip_q_tokens(tokens)
    q_indices = np.asarray(encoder.q_token_indices, dtype=np.int64)
    np.testing.assert_array_equal(flipped[q_indices], -tokens[q_indices])
    disorder_indices = np.setdiff1d(np.arange(tokens.size), q_indices)
    np.testing.assert_array_equal(flipped[disorder_indices], tokens[disorder_indices])


@pytest.mark.parametrize("kind", tuple(TemplateKind))
def test_conditioned_token_group_action_is_closed(kind: TemplateKind) -> None:
    rng = np.random.default_rng(2026072912)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    encoder = TemplateEncoder(kind, True, 1)
    tokens = encoder.encode(q, bonds, (1, 2, 0))
    group = cubic_transforms()
    left = encoder.transform_tokens(tokens, group[11])
    sequential = encoder.transform_tokens(left, group[29])
    composed = encoder.transform_tokens(tokens, group[29].compose(group[11]))
    np.testing.assert_array_equal(sequential, composed)


@pytest.mark.parametrize("kind", tuple(TemplateKind))
def test_token_action_matches_joint_q_and_bond_lattice_transform(
    kind: TemplateKind,
) -> None:
    rng = np.random.default_rng(2026072913)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    encoder = TemplateEncoder(kind, True, 1)
    tokens = encoder.encode(q, bonds, (0, 0, 0))
    for transform in cubic_transforms():
        transformed_q, transformed_bonds = _transform_lattice(
            q,
            bonds,
            encoder,
            transform,
        )
        expected = encoder.transform_tokens(tokens, transform)
        actual = encoder.encode(transformed_q, transformed_bonds, (0, 0, 0))
        np.testing.assert_array_equal(actual, expected)
