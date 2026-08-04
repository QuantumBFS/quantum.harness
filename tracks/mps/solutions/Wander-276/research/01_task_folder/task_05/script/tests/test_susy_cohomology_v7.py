"""Algebra and rank tests for the charge-resolved N=2 SYK complex."""

from __future__ import annotations

from math import comb

import numpy as np

from lgeth.susy_cohomology import (
    analytic_decomposable_curvature_multiplicities,
    charge_basis,
    charge_hamiltonian,
    cubic_supercharge,
    cubic_triples,
    decomposable_bps_rank,
    decomposable_couplings,
    decomposable_tangent,
    expected_generic_bps_rank,
    normalized_complex_couplings,
    solve_bps_frame,
)


def test_charge_bases_and_cubic_triples_have_exact_counts() -> None:
    assert len(charge_basis(8, 3)) == comb(8, 3)
    assert charge_basis(8, -1) == ()
    assert charge_basis(8, 9) == ()
    triples = cubic_triples(8)
    assert len(triples) == comb(8, 3)
    assert triples[0] == (0, 1, 2)
    assert triples[-1] == (5, 6, 7)


def test_cubic_supercharge_is_nontrivially_nilpotent() -> None:
    couplings = normalized_complex_couplings(8, seed=7)
    q1 = cubic_supercharge(8, 1, couplings)
    q4 = cubic_supercharge(8, 4, couplings)
    product = (q4 @ q1).toarray()
    assert product.shape == (8, 8)
    assert np.linalg.norm(product) < 2e-14
    assert np.linalg.norm(q1.toarray()) > 0.0
    assert np.linalg.norm(q4.toarray()) > 0.0


def test_charge_hamiltonian_is_positive_hermitian() -> None:
    couplings = normalized_complex_couplings(6, seed=11)
    hamiltonian = charge_hamiltonian(6, 3, couplings).toarray()
    assert hamiltonian.shape == (20, 20)
    assert np.allclose(hamiltonian, hamiltonian.conj().T, atol=1e-13)
    eigenvalues = np.linalg.eigvalsh(hamiltonian)
    assert float(eigenvalues[0]) > -1e-12
    assert float(eigenvalues[-1]) > 1e-4


def test_registered_even_charge_sectors_have_exact_generic_bps_ranks() -> None:
    couplings = normalized_complex_couplings(6, seed=17)
    central = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    adjacent = solve_bps_frame(6, 2, couplings, dense_cutoff=64)
    assert expected_generic_bps_rank(6, 3) == 18
    assert expected_generic_bps_rank(6, 2) == 9
    assert central.projector_frame.shape == (20, 18)
    assert adjacent.projector_frame.shape == (15, 9)
    for frame in (central, adjacent):
        assert frame.gap > 1e-8
        assert frame.kernel_residual < 1e-11
        assert frame.orthogonality_error < 1e-12
        assert frame.complement_frame.shape[1] == len(frame.positive_energies)


def test_bps_projector_is_deterministic_at_fixed_couplings() -> None:
    couplings = normalized_complex_couplings(6, seed=23)
    first = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    second = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    first_projector = first.projector_frame @ first.projector_frame.conj().T
    second_projector = second.projector_frame @ second.projector_frame.conj().T
    assert np.allclose(first_projector, second_projector, atol=2e-13)


def test_odd_system_size_is_outside_registered_rank_contract() -> None:
    with np.testing.assert_raises_regex(ValueError, "even N"):
        expected_generic_bps_rank(7, 3)


def test_decomposable_rank_and_tangent_contracts() -> None:
    couplings = decomposable_couplings(8, alpha=1.7)
    triples = cubic_triples(8)
    assert np.count_nonzero(couplings) == 1
    assert couplings[triples.index((0, 1, 2))] == 1.7
    tangent = decomposable_tangent(8, "12", 3)
    assert np.count_nonzero(tangent) == 1
    assert tangent[triples.index((0, 1, 3))] == 1.0
    assert decomposable_bps_rank(8, 4) == 60
    frame = solve_bps_frame(
        8,
        4,
        couplings,
        dense_cutoff=128,
        expected_rank_override=decomposable_bps_rank(8, 4),
    )
    assert frame.projector_frame.shape == (70, 60)


def test_decomposable_multiplicity_formulas_are_complete() -> None:
    diagonal = analytic_decomposable_curvature_multiplicities(6, 3, "diagonal")
    off_diagonal = analytic_decomposable_curvature_multiplicities(
        6,
        3,
        "off_diagonal",
    )
    assert diagonal == {"negative": 1, "zero": 16, "positive": 1}
    assert off_diagonal == {"negative": 2, "zero": 14, "positive": 2}
