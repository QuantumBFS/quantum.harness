from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.gauge import gauge_transform
from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder, TemplateKind


@pytest.mark.parametrize(
    "kind,nq,nconditioned",
    [
        ("cross", 7, 19),
        ("face_edge", 19, 31),
        ("cube", 8, 13),
        ("factorized_3x3x3", 27, 55),
    ],
)
def test_conditioned_template_counts(
    kind: str,
    nq: int,
    nconditioned: int,
) -> None:
    encoder = TemplateEncoder(kind=kind, conditioned=True, rg_level=1)
    assert encoder.q_token_count == nq
    assert encoder.token_count == nconditioned
    assert len(encoder.q_token_indices) == nq
    q_only = TemplateEncoder(kind=kind, conditioned=False, rg_level=1)
    assert q_only.token_count == nq


@pytest.mark.parametrize("kind", tuple(TemplateKind))
def test_conditioned_encodings_are_gauge_invariant(kind: TemplateKind) -> None:
    rng = np.random.default_rng(2026072909)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    epsilon = rng.choice(np.array([-1, 1], dtype=np.int8), size=(9, 9, 9))
    encoder = TemplateEncoder(kind=kind, conditioned=True, rg_level=1)
    left = encoder.encode(q, bonds, center=(0, 0, 0))
    right = encoder.encode(q, gauge_transform(bonds, epsilon), center=(0, 0, 0))
    np.testing.assert_array_equal(left, right)


def test_level_two_disorder_paths_use_the_microscopic_preimage() -> None:
    rng = np.random.default_rng(2026072910)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(27, rng)
    encoder = TemplateEncoder("cube", conditioned=True, rg_level=2)
    baseline = encoder.encode(q, bonds, (0, 0, 0))
    values = bonds.values.copy()
    values[4, 0, 0, 0] *= -1
    changed = encoder.encode(q, EABonds(values), (0, 0, 0))
    assert not np.array_equal(baseline, changed)


@pytest.mark.parametrize("kind", tuple(TemplateKind))
def test_reverse_incidence_counts_each_changed_density(kind: TemplateKind) -> None:
    encoder = TemplateEncoder(kind, conditioned=False, rg_level=1)
    reverse = encoder.reverse_q_incidence(length=6)
    assert len(reverse) == 6**3
    assert all(len(centers) == encoder.q_token_count for centers in reverse.values())


@pytest.mark.parametrize(
    "kind,expected_count",
    [
        (TemplateKind.CROSS, 4),
        (TemplateKind.FACE_EDGE, 7),
        (TemplateKind.CUBE, 8),
        (TemplateKind.FACTORIZED_3X3X3, 8),
    ],
)
def test_reverse_incidence_deduplicates_periodic_length_two_centers(
    kind: TemplateKind,
    expected_count: int,
) -> None:
    encoder = TemplateEncoder(kind, conditioned=False, rg_level=1)
    centers = encoder.reverse_q_incidence(length=2)[(0, 0, 0)]
    assert len(centers) == expected_count
    assert len(centers) == len(set(centers))


def test_serialized_metadata_has_no_raw_bond_tokens() -> None:
    for kind in TemplateKind:
        metadata = TemplateEncoder(kind, True, 1).metadata()
        assert metadata["disorder_encoding"] in {
            "plaquette_flux",
            "spanning_tree_chords",
        }
        assert "raw_j" not in str(metadata).lower()
