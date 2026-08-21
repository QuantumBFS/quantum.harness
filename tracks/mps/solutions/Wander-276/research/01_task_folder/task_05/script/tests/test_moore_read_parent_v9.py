"""Exact-count and factorization tests for the Moore--Read v9 parent."""

from __future__ import annotations

from math import factorial

import numpy as np
import pytest

from lgeth.combinatorics import (
    clustered_zero_mode_count,
    cyclic_kr_admissible,
    occupation_states,
)
from lgeth.lattice import BosonBasis
from lgeth.moore_read_audit import audit_moore_read_case
from lgeth.moore_read_parent import (
    build_continuum_moore_read_parent,
    coherent_state_constraint_frame,
    three_body_annihilation_constraints,
)


def _explicit_normalized_field_cube_row(
    basis: BosonBasis,
    field: np.ndarray,
) -> np.ndarray:
    values = np.asarray(field, dtype=complex)
    if basis.n_particles != 3 or values.shape != (basis.n_orbitals,):
        raise ValueError("explicit field-cube check requires exactly three bosons")
    amplitudes = np.empty(basis.dimension, dtype=complex)
    for column, state in enumerate(basis.states):
        denominator = 1
        orbital_product = 1.0 + 0.0j
        for orbital, occupation in enumerate(state):
            denominator *= factorial(occupation)
            orbital_product *= values[orbital] ** occupation
        amplitudes[column] = np.sqrt(6.0 / denominator) * orbital_product
    return amplitudes


def test_clustered_zero_mode_count_matches_direct_enumeration() -> None:
    expected = sum(
        cyclic_kr_admissible(state, k=2, r=2)
        for state in occupation_states(4, 6)
    )
    assert clustered_zero_mode_count(4, 6) == expected


def test_clustered_zero_mode_count_rejects_overfilled_torus() -> None:
    with pytest.raises(ValueError, match="n_flux"):
        clustered_zero_mode_count(7, 6)


def test_three_body_single_orbital_normalization() -> None:
    basis = BosonBasis(1, 3)
    constraints, intermediate = three_body_annihilation_constraints(
        basis,
        np.ones((1, 1), dtype=complex),
    )
    assert intermediate.n_particles == 0
    assert constraints.shape == (1, 1)
    assert np.allclose(constraints.toarray(), [[1.0]])


def test_three_body_constraint_matches_explicit_field_cube() -> None:
    basis = BosonBasis(3, 3)
    frame = np.asarray(
        [
            [1.0, 2.0, -0.5],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=complex,
    )
    constraints, intermediate = three_body_annihilation_constraints(
        basis,
        frame,
    )
    assert intermediate.dimension == 1
    expected = _explicit_normalized_field_cube_row(basis, frame[0])
    assert np.allclose(constraints.toarray()[0], expected)


def test_continuum_moore_read_parent_exposes_factor_interface() -> None:
    system = build_continuum_moore_read_parent(4, 6)
    assert system.n_particles == 4
    assert system.n_flux == 6
    assert system.intermediate_basis.n_particles == 1
    assert system.constraints.shape[1] == system.basis.dimension
    parent = system.constraints.conj().T @ system.constraints
    assert np.allclose(parent.toarray(), parent.toarray().conj().T)
    assert np.min(np.linalg.eigvalsh(parent.toarray())) > -1e-10


def test_coherent_state_frame_is_complete_and_normalized() -> None:
    frame = coherent_state_constraint_frame(6)
    assert frame.shape == (36, 6)
    assert np.linalg.matrix_rank(frame) == 6
    assert np.allclose(np.linalg.norm(frame, axis=1), 1.0)


def test_small_moore_read_parent_matches_clustered_count() -> None:
    audit = audit_moore_read_case(4, 6, seed=2026081601)
    assert audit.expected_rank == audit.observed_rank
    assert audit.internal_bandwidth < 1e-9
    assert audit.external_gap > 0.0
    assert audit.kernel_residual < 1e-7
    assert all(audit.checks.values())


def test_moore_read_transport_moves_projector_without_splitting() -> None:
    audit = audit_moore_read_case(4, 6, seed=2026081601)
    assert audit.generator_commutator_norm > 1e-8
    assert audit.projector_distance > 1e-8
    assert audit.transported_constraint_residual < 1e-8
    assert audit.tangent_fiber_norm < 1e-8
