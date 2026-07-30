from __future__ import annotations

import numpy as np

from oracle.odd_block_tn_effective import (
    build_continuous_time_model,
    build_minimal_continuous_time_model,
    minimal_tn_blocks,
)
from oracle.odd_block_tn_stoquastic import (
    c3_count_gauge,
    c3_fock_sign_gauge,
    diagonal_sign_transform,
    maximum_offdiagonal,
)


def _tn_block(
    diagonal: tuple[float, float],
    upper: float,
    lower: float,
) -> np.ndarray:
    return (
        np.diag(diagonal)
        @ np.asarray([[1.0, upper], [0.0, 1.0]])
        @ np.asarray([[1.0, 0.0], [lower, 1.0]])
    )


def test_count_gauge_has_positive_c3_holonomy() -> None:
    phases = c3_count_gauge(5)
    for counts, phase in phases.items():
        n0, n1, n2 = counts
        rotated = (n1, n2, n0)
        fock_sign = -1 if (n0 * (n1 + n2)) % 2 else 1
        assert phases[rotated] * fock_sign * phase == 1


def test_minimal_interacting_hamiltonian_is_sign_gauge_stoquastic() -> None:
    model = build_minimal_continuous_time_model()
    gauge = c3_fock_sign_gauge(block_size=2)

    gauged_branch = diagonal_sign_transform(model.fock_branches[0], gauge)
    gauged_hamiltonian = diagonal_sign_transform(model.hamiltonian, gauge)

    assert np.min(gauged_branch) >= -1e-14
    assert maximum_offdiagonal(gauged_hamiltonian) <= 1e-14
    assert np.count_nonzero(gauged_hamiltonian - np.diag(np.diag(gauged_hamiltonian))) > 0


def test_one_gauge_covers_noncommuting_multi_atom_family() -> None:
    first = minimal_tn_blocks()
    second = (
        _tn_block((0.7, 0.5), 0.6, 0.2),
        _tn_block((0.8, 0.4), 0.3, 0.7),
        _tn_block((0.6, 0.9), 0.8, 0.1),
    )
    model = build_continuous_time_model(
        (first, second),
        couplings=(1.0, 0.7),
        directions=(1, -1),
    )
    gauge = c3_fock_sign_gauge(block_size=2)

    assert np.linalg.norm(
        model.branches[0] @ model.branches[1]
        - model.branches[1] @ model.branches[0]
    ) > 1e-3
    for fock_branch in model.fock_branches:
        assert np.min(diagonal_sign_transform(fock_branch, gauge)) >= -1e-13
        assert np.min(diagonal_sign_transform(fock_branch.T, gauge)) >= -1e-13
    assert maximum_offdiagonal(
        diagonal_sign_transform(model.hamiltonian, gauge)
    ) <= 1e-13
