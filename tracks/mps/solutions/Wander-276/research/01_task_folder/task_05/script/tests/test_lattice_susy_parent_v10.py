"""Graph-cohomology parent and response tests for lattice SUSY v10."""

from __future__ import annotations

import numpy as np

from lgeth.lattice_susy_parent import (
    cycle_union_edges,
    independence_basis,
    lattice_susy_response,
    linear_supercharge,
    normalized_cycle_couplings,
    project_component_tangents,
    solve_cycle_union_frame,
)


def test_cycle_independence_counts_and_nilpotency() -> None:
    edges = cycle_union_edges(1)
    assert len(independence_basis(6, edges, 0)) == 1
    assert len(independence_basis(6, edges, 1)) == 6
    assert len(independence_basis(6, edges, 2)) == 9
    assert len(independence_basis(6, edges, 3)) == 2
    couplings = normalized_cycle_couplings(1, seed=17)
    first = linear_supercharge(6, edges, 1, couplings)
    second = linear_supercharge(6, edges, 2, couplings)
    assert first.shape == (9, 6)
    assert second.shape == (2, 9)
    assert np.linalg.norm((second @ first).toarray()) < 2e-13
    assert first.nnz > 0 and second.nnz > 0


def test_opened_cycle_union_has_complete_exponential_cohomology() -> None:
    for cycles, expected_dimension in ((1, 9), (2, 105), (3, 1389)):
        couplings = normalized_cycle_couplings(cycles, seed=29 + cycles)
        frame = solve_cycle_union_frame(cycles, couplings)
        assert len(frame.basis) == expected_dimension
        assert frame.expected_rank == 2**cycles
        assert frame.projector_frame.shape == (expected_dimension, 2**cycles)
        assert frame.q_in.nnz > 0 and frame.q_out.nnz > 0
        assert frame.gap > 1e-8
        assert np.ptp(frame.zero_energies) < 1e-9
        assert frame.kernel_residual < 2e-9
        assert frame.orthogonality_error < 2e-10


def test_component_projection_removes_all_trivial_complex_lines() -> None:
    cycles = 2
    couplings = normalized_cycle_couplings(cycles, seed=41)
    rng = np.random.default_rng(43)
    candidates = rng.normal(size=(8, 12)) + 1j * rng.normal(size=(8, 12))
    tangents = project_component_tangents(couplings, candidates, cycles)
    assert tangents.shape == (8, 12)
    assert np.allclose(tangents @ tangents.conj().T, np.eye(8), atol=5e-12)
    for component in range(cycles):
        block = slice(6 * component, 6 * (component + 1))
        overlaps = tangents[:, block] @ couplings[block].conj()
        assert np.max(np.abs(overlaps)) < 2e-12


def test_exact_and_coexact_responses_match_direct_resolvent() -> None:
    cycles = 2
    couplings = normalized_cycle_couplings(cycles, seed=47)
    frame = solve_cycle_union_frame(cycles, couplings)
    rng = np.random.default_rng(53)
    candidates = rng.normal(size=(4, 12)) + 1j * rng.normal(size=(4, 12))
    tangents = project_component_tangents(couplings, candidates, cycles)
    response = lattice_susy_response(frame, couplings, tangents)
    assert np.linalg.norm(response.minus) > 1e-8
    assert np.linalg.norm(response.plus) > 1e-8
    assert np.allclose(response.total, response.minus + response.plus, atol=2e-11)
    assert np.allclose(response.total, response.direct, atol=2e-10)
    assert response.branch_sum_relative_error < 2e-12
    assert response.direct_relative_error < 2e-10
    assert response.orthogonality_relative_error < 2e-10
    assert response.target_leakage < 2e-10
    assert all(response.checks.values())


def test_response_reproduces_centered_projector_derivative() -> None:
    cycles = 1
    couplings = normalized_cycle_couplings(cycles, seed=59)
    frame = solve_cycle_union_frame(cycles, couplings)
    rng = np.random.default_rng(61)
    candidate = rng.normal(size=(1, 6)) + 1j * rng.normal(size=(1, 6))
    tangent = project_component_tangents(couplings, candidate, cycles)[0]
    response = lattice_susy_response(frame, couplings, tangent[None, :])
    projector = frame.projector_frame
    analytic = (
        response.total[0] @ projector.conj().T
        + projector @ response.total[0].conj().T
    )
    errors = []
    for step in (2e-4, 1e-4):
        plus = solve_cycle_union_frame(cycles, couplings + step * tangent)
        minus = solve_cycle_union_frame(cycles, couplings - step * tangent)
        finite = (
            plus.projector_frame @ plus.projector_frame.conj().T
            - minus.projector_frame @ minus.projector_frame.conj().T
        ) / (2.0 * step)
        errors.append(np.linalg.norm(finite - analytic) / np.linalg.norm(analytic))
    assert errors[1] < 2e-6
    assert errors[0] / errors[1] > 3.5
