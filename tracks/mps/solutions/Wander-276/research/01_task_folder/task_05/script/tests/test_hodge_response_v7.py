"""Exact/coexact response identities for the N=2 SYK BPS fiber."""

from __future__ import annotations

import numpy as np

from lgeth.hodge_response import (
    HodgeResponse,
    coupling_panels,
    decomposable_curvature,
    external_covariance_eigenvalues_scalable,
    hodge_response,
    hodge_signature,
    project_moduli_tangents,
    projector_derivative_from_response,
    scalable_covariance_matched_wick,
)
from lgeth.susy_cohomology import (
    analytic_decomposable_curvature_multiplicities,
    cubic_triples,
    decomposable_couplings,
    decomposable_tangent,
    normalized_complex_couplings,
    solve_bps_frame,
)
from lgeth.wick_channels import (
    covariance_matched_wick,
    external_covariance_eigenvalues,
)


def _generic_tangent(N: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    tangent = rng.normal(size=len(cubic_triples(N))) + 1j * rng.normal(
        size=len(cubic_triples(N))
    )
    return tangent / np.linalg.norm(tangent)


def test_hodge_branches_are_orthogonal_and_equal_direct_resolvent() -> None:
    couplings = normalized_complex_couplings(6, seed=29)
    frame = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    tangent = _generic_tangent(6, seed=31)
    result = hodge_response(frame, couplings, tangent[None, :])
    cross = result.minus[0].conj().T @ result.plus[0]
    scale = np.linalg.norm(result.minus[0]) * np.linalg.norm(result.plus[0])
    assert np.linalg.norm(cross) / scale < 2e-12
    assert np.allclose(result.total, result.minus + result.plus, atol=2e-12)
    assert np.allclose(result.total, result.direct, atol=2e-11)
    assert result.branch_sum_relative_error < 2e-13
    assert result.direct_relative_error < 2e-11
    assert result.orthogonality_relative_error < 2e-12
    assert result.target_leakage < 2e-12
    assert all(result.checks.values())


def test_response_reproduces_centered_projector_derivative() -> None:
    couplings = normalized_complex_couplings(6, seed=37)
    frame = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    tangent = _generic_tangent(6, seed=41)
    response = hodge_response(frame, couplings, tangent[None, :])
    analytic = projector_derivative_from_response(
        frame.projector_frame,
        response.total[0],
    )
    errors: list[float] = []
    for step in (2e-4, 1e-4):
        plus = solve_bps_frame(
            6,
            3,
            couplings + step * tangent,
            dense_cutoff=64,
        ).projector_frame
        minus = solve_bps_frame(
            6,
            3,
            couplings - step * tangent,
            dense_cutoff=64,
        ).projector_frame
        finite = (
            plus @ plus.conj().T - minus @ minus.conj().T
        ) / (2.0 * step)
        errors.append(float(np.linalg.norm(finite - analytic) / np.linalg.norm(analytic)))
    assert errors[1] < 2e-6
    assert errors[0] / errors[1] > 3.5


def test_multiple_tangents_preserve_shapes_and_linearity() -> None:
    couplings = normalized_complex_couplings(6, seed=43)
    frame = solve_bps_frame(6, 2, couplings, dense_cutoff=64)
    first = _generic_tangent(6, seed=47)
    second = _generic_tangent(6, seed=53)
    combined = hodge_response(
        frame,
        couplings,
        np.stack([first, second, first + 2.0 * second]),
    )
    assert combined.total.shape == (3, 15, 9)
    assert np.allclose(
        combined.total[2],
        combined.total[0] + 2.0 * combined.total[1],
        atol=3e-11,
    )


def test_registered_panels_remove_radial_phase_and_have_full_support() -> None:
    couplings = normalized_complex_couplings(8, seed=59)
    panels = coupling_panels(couplings, panel_size=8, seed=61)
    assert set(panels) == {"sparse", "isotropic"}
    assert not np.allclose(panels["sparse"], panels["isotropic"])
    for values in panels.values():
        assert values.shape == (8, 56)
        assert np.max(np.abs(values @ couplings.conj())) < 2e-13
        assert np.allclose(
            values @ values.conj().T,
            np.eye(8),
            atol=2e-13,
        )


def test_moduli_projection_rejects_rank_deficient_candidates() -> None:
    couplings = normalized_complex_couplings(8, seed=67)
    candidate = np.zeros(56, dtype=complex)
    candidate[0] = 1.0
    with np.testing.assert_raises_regex(ValueError, "full rank"):
        project_moduli_tangents(
            couplings,
            np.stack([candidate, candidate]),
        )


def _synthetic_response(minus: np.ndarray, plus: np.ndarray) -> HodgeResponse:
    total = minus + plus
    return HodgeResponse(
        minus=minus,
        plus=plus,
        total=total,
        direct=total.copy(),
        branch_sum_relative_error=0.0,
        direct_relative_error=0.0,
        orthogonality_relative_error=0.0,
        target_leakage=0.0,
        checks={"synthetic": True},
    )


def test_hodge_signature_resolves_one_sided_and_balanced_limits() -> None:
    rng = np.random.default_rng(71)
    minus = rng.normal(size=(8, 12, 5)) + 1j * rng.normal(size=(8, 12, 5))
    zero = np.zeros_like(minus)
    one_sided = hodge_signature(_synthetic_response(minus, zero))
    assert one_sided.hodge_balance == 0.0
    assert one_sided.minus_weight > 0.0
    assert one_sided.plus_weight == 0.0
    balanced = hodge_signature(_synthetic_response(minus, minus.copy()))
    assert abs(balanced.hodge_balance - 1.0) < 2e-14


def test_hodge_signature_is_gauge_invariant() -> None:
    couplings = normalized_complex_couplings(6, seed=73)
    frame = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    panels = coupling_panels(couplings, panel_size=8, seed=79)
    response = hodge_response(frame, couplings, panels["isotropic"])
    reference = hodge_signature(response)
    rng = np.random.default_rng(83)
    ambient, _ = np.linalg.qr(
        rng.normal(size=(20, 20)) + 1j * rng.normal(size=(20, 20))
    )
    target, _ = np.linalg.qr(
        rng.normal(size=(18, 18)) + 1j * rng.normal(size=(18, 18))
    )
    rotated_minus = np.einsum(
        "ij,mjk,kl->mil",
        ambient,
        response.minus,
        target,
        optimize=True,
    )
    rotated_plus = np.einsum(
        "ij,mjk,kl->mil",
        ambient,
        response.plus,
        target,
        optimize=True,
    )
    rotated = hodge_signature(_synthetic_response(rotated_minus, rotated_plus))
    assert np.isclose(reference.hodge_balance, rotated.hodge_balance, atol=1e-13)
    assert np.allclose(
        reference.minus_target_eigenvalues,
        rotated.minus_target_eigenvalues,
        atol=2e-12,
    )
    assert np.allclose(
        reference.plus_external_eigenvalues,
        rotated.plus_external_eigenvalues,
        atol=2e-12,
    )
    assert np.allclose(
        reference.minus_channel_covariance,
        rotated.minus_channel_covariance,
        atol=2e-12,
    )


def test_scalable_external_spectrum_and_statistic_match_immutable_code() -> None:
    rng = np.random.default_rng(89)
    # ambient=7 is much smaller than labels*rank=40, exercising the N=14 path.
    channels = rng.normal(size=(8, 7, 5)) + 1j * rng.normal(size=(8, 7, 5))
    reference_spectrum = external_covariance_eigenvalues(channels)
    scalable_spectrum = external_covariance_eigenvalues_scalable(channels)
    assert np.allclose(reference_spectrum, scalable_spectrum, atol=2e-12)
    reference = covariance_matched_wick(channels)
    scalable = scalable_covariance_matched_wick(channels)
    assert np.isclose(reference.R4, scalable.R4, atol=2e-13)
    assert np.isclose(reference.A_left, scalable.A_left, atol=2e-13)
    assert np.isclose(reference.B_right, scalable.B_right, atol=2e-13)
    assert np.allclose(reference.tensor, scalable.tensor, atol=2e-13)
    assert np.allclose(
        reference.right_eigenvalues,
        scalable.right_eigenvalues,
        atol=2e-12,
    )


def _assert_atomic_spectrum(
    matrix: np.ndarray,
    alpha: float,
    multiplicities: dict[str, int],
) -> None:
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.conj().T))
    target = 1.0 / alpha**2
    assert np.count_nonzero(np.isclose(eigenvalues, -target, atol=2e-11)) == (
        multiplicities["negative"]
    )
    assert np.count_nonzero(np.isclose(eigenvalues, 0.0, atol=2e-11)) == (
        multiplicities["zero"]
    )
    assert np.count_nonzero(np.isclose(eigenvalues, target, atol=2e-11)) == (
        multiplicities["positive"]
    )


def test_decomposable_diagonal_curvature_recovers_exact_atoms() -> None:
    alpha = 1.7
    couplings = decomposable_couplings(6, alpha)
    frame = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    tangent = decomposable_tangent(6, "12", 3)
    response = hodge_response(frame, couplings, tangent[None, :])
    curvature = decomposable_curvature(response, 0)
    _assert_atomic_spectrum(
        curvature,
        alpha,
        analytic_decomposable_curvature_multiplicities(6, 3, "diagonal"),
    )


def test_decomposable_off_diagonal_curvature_recovers_exact_atoms() -> None:
    alpha = 1.7
    couplings = decomposable_couplings(6, alpha)
    frame = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    tangents = np.stack(
        [
            decomposable_tangent(6, "12", 3),
            decomposable_tangent(6, "13", 4),
        ]
    )
    response = hodge_response(frame, couplings, tangents)
    curvature = decomposable_curvature(response, 0, 1)
    _assert_atomic_spectrum(
        curvature,
        alpha,
        analytic_decomposable_curvature_multiplicities(
            6,
            3,
            "off_diagonal",
        ),
    )
