"""Exact-index contracts for the prospective chiral-kernel benchmark."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from lgeth.chiral_kernel_parent import (
    audit_chiral_case,
    build_chiral_hamiltonian,
    chiral_response,
    make_chiral_base,
    make_tangent_panel,
    zero_mode_frame,
)


def test_exact_chiral_index_gap_and_anticommutation() -> None:
    n_b, n_a = 6, 10
    matrix = make_chiral_base(n_a=n_a, n_b=n_b, seed=1401)
    hamiltonian = build_chiral_hamiltonian(matrix)
    chiral = np.diag(np.r_[np.ones(n_a), -np.ones(n_b)])
    frame = zero_mode_frame(matrix, tolerance=1e-12)
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    spectrum = np.linalg.eigvalsh(hamiltonian)

    assert hamiltonian.shape == (n_a + n_b, n_a + n_b)
    assert np.linalg.norm(chiral @ hamiltonian + hamiltonian @ chiral) < 1e-12
    assert frame.shape == (n_a + n_b, n_a - n_b)
    assert np.linalg.norm(frame.conj().T @ frame - np.eye(n_a - n_b)) < 1e-12
    assert np.linalg.norm(hamiltonian @ frame) < 1e-12
    assert np.count_nonzero(np.abs(spectrum) < 1e-10) == n_a - n_b
    assert np.min(np.abs(spectrum[np.abs(spectrum) >= 1e-10])) == pytest.approx(
        singular_values[-1], rel=1e-11, abs=1e-12
    )


def test_response_matches_centered_projector_finite_difference() -> None:
    n_b, n_a = 5, 8
    matrix = make_chiral_base(n_a=n_a, n_b=n_b, seed=2501)
    tangent = make_tangent_panel(
        n_a=n_a,
        n_b=n_b,
        count=1,
        kind="random",
        seed=2502,
    )[0]
    frame = zero_mode_frame(matrix, tolerance=1e-12)
    response = chiral_response(matrix, tangent, tolerance=1e-12)
    analytic = response @ frame.conj().T + frame @ response.conj().T
    epsilon = 2e-6
    plus = zero_mode_frame(matrix + epsilon * tangent, tolerance=1e-12)
    minus = zero_mode_frame(matrix - epsilon * tangent, tolerance=1e-12)
    finite_difference = (
        plus @ plus.conj().T - minus @ minus.conj().T
    ) / (2.0 * epsilon)

    assert np.linalg.norm(frame.conj().T @ response) < 1e-12
    assert np.linalg.norm(analytic - finite_difference) / np.linalg.norm(analytic) < 2e-7


def test_audit_reports_exact_response_and_gauge_gates() -> None:
    audit = audit_chiral_case(n_a=12, n_b=8, seed=3601)

    assert audit["nullity"] == 4
    assert audit["expected_nullity"] == 4
    assert audit["external_gap"] > 0.0
    assert audit["checks"]
    assert all(audit["checks"].values())
    assert audit["all_checks_pass"] is True
    assert audit["residuals"]["projector_finite_difference_relative"] < 1e-6
    assert audit["residuals"]["gauge_projector_relative"] < 1e-10
    assert audit["residuals"]["gauge_response_relative"] < 1e-9


def test_tangent_classes_share_count_and_frobenius_normalization() -> None:
    n_b, n_a, count = 8, 12, 7
    panels = {
        kind: make_tangent_panel(
            n_a=n_a,
            n_b=n_b,
            count=count,
            kind=kind,
            seed=4700 + index,
            bandwidth=1,
            cell_shape=(2, 3),
        )
        for index, kind in enumerate(("random", "local", "structured"))
    }

    assert all(panel.shape == (count, n_b, n_a) for panel in panels.values())
    for panel in panels.values():
        assert np.allclose(np.linalg.norm(panel, axis=(1, 2)), 1.0, atol=1e-12)

    local = panels["local"]
    allowed = np.zeros((n_b, n_a), dtype=bool)
    for row in range(n_b):
        center = int(round(row * n_a / n_b)) % n_a
        for offset in (-1, 0, 1):
            allowed[row, (center + offset) % n_a] = True
    assert np.max(np.abs(local[:, ~allowed])) == 0.0

    structured = panels["structured"]
    for tangent in structured:
        assert np.allclose(tangent[:2, :3], tangent[2:4, 3:6])


def test_invalid_or_rank_deficient_rectangular_factors_fail_closed() -> None:
    with pytest.raises(ValueError, match="n_a > n_b"):
        build_chiral_hamiltonian(np.eye(4, dtype=complex))
    deficient = np.zeros((3, 5), dtype=complex)
    deficient[:2, :2] = np.eye(2)
    with pytest.raises(ValueError, match="full row rank"):
        zero_mode_frame(deficient, tolerance=1e-12)
