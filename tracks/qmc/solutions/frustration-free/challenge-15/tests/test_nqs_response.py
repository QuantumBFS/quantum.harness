from __future__ import annotations

import hashlib

import jax
import numpy as np
import pytest
from scipy import sparse

import challenge15
from challenge15.fermions import DeterminantBasis, state_two_m
from challenge15.model import ModelConfig, ProjectedPfaffianNQS
from challenge15.nqs_bridge import (
    DeterminantState,
    mixed_transition_amplitude,
    nqs_determinant_state,
)
from challenge15.oracle import evaluate_exact_nqs, solve_target_sectors
from challenge15.response_operator import build_response_family
from challenge15.spec import SphereSpec
from challenge15.spectral_response import (
    exact_chiral_spectrum,
    nqs_mixed_chiral_spectrum,
)


def test_nqs_response_stable_root_exports_preserve_identity():
    assert challenge15.DeterminantState is DeterminantState
    assert challenge15.nqs_determinant_state is nqs_determinant_state
    assert (
        challenge15.nqs_mixed_chiral_spectrum
        is nqs_mixed_chiral_spectrum
    )


@pytest.fixture(scope="module")
def bridge_case():
    spec = SphereSpec(3)
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=2, hidden_width=8, depth=1, token_width=4)
    )
    spinors = np.asarray(
        [
            [1.0, 0.2j],
            [0.6 + 0.1j, 0.7],
            [0.3 - 0.2j, 0.9],
        ],
        dtype=np.complex128,
    )
    parameters = model.init(jax.random.key(1507), spec, spinors, target_l=0)
    return spec, parameters, solve_target_sectors(spec)


@pytest.mark.parametrize("target_l", [0, 2])
def test_bridge_matches_exact_nqs_multiplicity_coefficients(
    bridge_case, target_l
):
    spec, parameters, oracle = bridge_case
    metrics = evaluate_exact_nqs(
        spec,
        parameters,
        oracle,
        determinant_block=7,
        carrier_block=1,
    )
    determinant_state = nqs_determinant_state(
        spec,
        parameters,
        oracle,
        target_l=target_l,
        determinant_block=7,
        carrier_block=1,
    )
    sector = oracle.exact_sector(target_l)

    np.testing.assert_allclose(
        sector.isometry.conj().T @ determinant_state.coefficients,
        metrics.normalized_sector_coefficients(target_l),
        atol=2e-12,
        rtol=0.0,
    )


@pytest.mark.parametrize("target_l", [0, 2])
def test_bridge_state_is_canonical_normalized_and_immutable(
    bridge_case, target_l
):
    spec, parameters, oracle = bridge_case
    state = nqs_determinant_state(
        spec,
        parameters,
        oracle,
        target_l=target_l,
        determinant_block=7,
    )

    assert isinstance(state, DeterminantState)
    assert state.basis == DeterminantBasis.with_two_m(spec, 0)
    assert state.basis.states == tuple(sorted(state.basis.states))
    assert tuple(state.basis.state_index[item] for item in state.basis.states) == tuple(
        range(state.basis.dimension)
    )
    assert state.coefficients.dtype == np.dtype(np.complex128)
    assert state.coefficients.shape == (state.basis.dimension,)
    assert np.linalg.norm(state.coefficients) == pytest.approx(1.0, abs=2e-12)
    full_basis = DeterminantBasis.full(spec)
    full_coefficients = np.zeros(full_basis.dimension, dtype=np.complex128)
    full_coefficients[
        [full_basis.state_index[determinant] for determinant in state.basis.states]
    ] = state.coefficients
    outside_m_zero = np.asarray(
        [
            index
            for index, determinant in enumerate(full_basis.states)
            if state_two_m(spec, determinant) != 0
        ],
        dtype=np.int64,
    )
    np.testing.assert_array_equal(
        full_coefficients[outside_m_zero],
        np.zeros(outside_m_zero.size, dtype=np.complex128),
    )
    assert not state.coefficients.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        state.coefficients[0] = 0.0
    with pytest.raises((AttributeError, TypeError)):
        state.coefficients = np.zeros_like(state.coefficients)
    assert not hasattr(state, "__dict__")


@pytest.mark.parametrize("target_l", [0, 2])
def test_bridge_determinant_block_sizes_preserve_coefficients(
    bridge_case, target_l
):
    spec, parameters, oracle = bridge_case
    states = [
        nqs_determinant_state(
            spec,
            parameters,
            oracle,
            target_l=target_l,
            determinant_block=block_size,
            carrier_block=1,
        )
        for block_size in (1, 7, 256)
    ]

    assert all(state.basis.states == states[0].basis.states for state in states)
    for state in states[1:]:
        np.testing.assert_allclose(
            state.coefficients,
            states[0].coefficients,
            atol=2e-12,
            rtol=0.0,
        )


def test_bridge_rejects_unsupported_target_l(bridge_case):
    spec, parameters, oracle = bridge_case
    with pytest.raises(ValueError, match="target_l must be 0 or 2"):
        nqs_determinant_state(
            spec,
            parameters,
            oracle,
            target_l=1,
        )


@pytest.mark.parametrize("particles", [2, 3])
def test_mixed_transition_matches_dense_direct_contraction(particles):
    basis = DeterminantBasis.with_two_m(SphereSpec(particles), 0)
    coefficients = np.arange(1, basis.dimension + 1, dtype=np.complex128)
    coefficients += 0.25j * coefficients[::-1]
    initial = DeterminantState(basis, coefficients)
    rows = basis.dimension + 2
    dense_operator = np.arange(
        1, rows * basis.dimension + 1, dtype=np.float64
    ).reshape(rows, basis.dimension)
    dense_operator = dense_operator + 0.125j * dense_operator[::-1]
    operator = sparse.csr_matrix(dense_operator)
    final = np.linspace(0.5, 1.5, rows).astype(np.complex128)
    final += 0.2j * final[::-1]

    actual = mixed_transition_amplitude(final, operator, initial)
    expected = np.vdot(final, operator.toarray() @ initial.coefficients)

    assert actual == pytest.approx(expected, rel=0.0, abs=1e-13)


def test_mixed_transition_rejects_invalid_domain_codomain_and_state():
    basis = DeterminantBasis.with_two_m(SphereSpec(2), 0)
    initial = DeterminantState(
        basis, np.ones(basis.dimension, dtype=np.complex128)
    )
    valid = sparse.identity(basis.dimension, format="csr")

    with pytest.raises(ValueError, match="domain"):
        mixed_transition_amplitude(
            np.ones(basis.dimension),
            sparse.csr_matrix((basis.dimension, basis.dimension + 1)),
            initial,
        )
    with pytest.raises(ValueError, match="codomain"):
        mixed_transition_amplitude(
            np.ones(basis.dimension + 1),
            valid,
            initial,
        )
    with pytest.raises(ValueError, match="final.*finite"):
        mixed_transition_amplitude(
            np.full(basis.dimension, np.nan),
            valid,
            initial,
        )

    forged = DeterminantState(basis, initial.coefficients)
    writable = np.array(forged.coefficients, copy=True)
    writable *= 2.0
    writable.flags.writeable = False
    object.__setattr__(forged, "coefficients", writable)
    with pytest.raises(ValueError, match="unit"):
        mixed_transition_amplitude(
            np.ones(basis.dimension),
            valid,
            forged,
        )

    writable = np.array(initial.coefficients, copy=True)
    object.__setattr__(forged, "coefficients", writable)
    with pytest.raises(ValueError, match="immutable"):
        mixed_transition_amplitude(
            np.ones(basis.dimension),
            valid,
            forged,
        )


def _assert_mixed_matches_exact(actual, expected):
    assert actual.ground_energy == pytest.approx(
        expected.ground_energy, rel=0.0, abs=1e-12
    )
    assert actual.delta_weight == pytest.approx(
        expected.delta_weight, rel=0.0, abs=1e-12
    )
    assert actual.contrast == pytest.approx(
        expected.contrast, rel=0.0, abs=1e-12
    )
    for helicity in ("+", "-"):
        actual_channel = actual.channels[helicity]
        expected_channel = expected.channels[helicity]
        np.testing.assert_allclose(
            [
                actual_channel.total_weight,
                actual_channel.direct_sum_weight,
                actual_channel.recovered_fraction,
                actual_channel.lowest_weight,
                actual_channel.pole_fraction,
            ],
            [
                expected_channel.total_weight,
                expected_channel.direct_sum_weight,
                expected_channel.recovered_fraction,
                expected_channel.lowest_weight,
                expected_channel.pole_fraction,
            ],
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            [pole.energy for pole in actual_channel.poles],
            [pole.energy for pole in expected_channel.poles],
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            [pole.weight for pole in actual_channel.poles],
            [pole.weight for pole in expected_channel.poles],
            rtol=0.0,
            atol=1e-12,
        )


@pytest.mark.parametrize("particles", [2, 3])
def test_mixed_exact_ground_recovers_exact_spectrum_and_payload(particles):
    spec = SphereSpec(particles)
    oracle = solve_target_sectors(spec)
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }
    ground_sector = oracle.exact_sector(0)
    coefficients = ground_sector.isometry @ ground_sector.eigenvectors[:, 0]
    initial = DeterminantState(
        DeterminantBasis.with_two_m(spec, 0), coefficients
    )

    actual = nqs_mixed_chiral_spectrum(oracle, families, initial)
    expected = exact_chiral_spectrum(oracle, families)

    _assert_mixed_matches_exact(actual, expected)
    payload = actual.to_payload()
    assert payload["initial_state_kind"] == "nqs-determinant"
    assert payload["initial_coefficient_sha256"] == hashlib.sha256(
        initial.coefficients.tobytes(order="C")
    ).hexdigest()
    assert payload["estimator_scope"] == (
        "exact-finite-Hilbert contraction with exact-ED L=2 finals; "
        "not an unbiased coordinate-Monte-Carlo estimator"
    )


@pytest.mark.parametrize("particles", [2, 3])
def test_mixed_spectrum_is_global_phase_invariant(particles):
    spec = SphereSpec(particles)
    oracle = solve_target_sectors(spec)
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }
    ground_sector = oracle.exact_sector(0)
    coefficients = ground_sector.isometry @ ground_sector.eigenvectors[:, 0]
    basis = DeterminantBasis.with_two_m(spec, 0)

    reference = nqs_mixed_chiral_spectrum(
        oracle, families, DeterminantState(basis, coefficients)
    )
    phased = nqs_mixed_chiral_spectrum(
        oracle,
        families,
        DeterminantState(basis, coefficients * np.exp(0.37j)),
    )

    for helicity in ("+", "-"):
        np.testing.assert_allclose(
            [pole.weight for pole in phased.channels[helicity].poles],
            [pole.weight for pole in reference.channels[helicity].poles],
            rtol=0.0,
            atol=1e-12,
        )
