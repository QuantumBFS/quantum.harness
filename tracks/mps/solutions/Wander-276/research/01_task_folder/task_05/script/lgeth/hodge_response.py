"""Exact/coexact BPS-projector responses for cubic N=2 SYK complexes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .susy_cohomology import BPSFrame, cubic_supercharge, cubic_triples
from .wick_channels import (
    WickResult,
    channel_covariance,
    four_channel_tensor,
    target_covariance,
    whiten_channel_labels,
)


@dataclass(frozen=True)
class HodgeResponse:
    """Resolved complement-to-BPS response for a tangent panel."""

    minus: np.ndarray
    plus: np.ndarray
    total: np.ndarray
    direct: np.ndarray
    branch_sum_relative_error: float
    direct_relative_error: float
    orthogonality_relative_error: float
    target_leakage: float
    checks: dict[str, bool]


@dataclass(frozen=True)
class HodgeSignature:
    """Gauge-invariant safe two-point data for a resolved response panel."""

    channel_count: int
    target_rank: int
    minus_weight: float
    plus_weight: float
    hodge_balance: float
    minus_channel_covariance: np.ndarray
    plus_channel_covariance: np.ndarray
    minus_target_eigenvalues: np.ndarray
    plus_target_eigenvalues: np.ndarray
    minus_external_eigenvalues: np.ndarray
    plus_external_eigenvalues: np.ndarray
    minus_target_effective_rank: float
    plus_target_effective_rank: float
    minus_external_effective_rank: float
    plus_external_effective_rank: float
    minus_target_entropy: float
    plus_target_entropy: float
    minus_external_entropy: float
    plus_external_entropy: float
    orthogonality_relative_error: float


def _relative_error(first: np.ndarray, second: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(second)), np.finfo(float).tiny)
    return float(np.linalg.norm(first - second) / denominator)


def _pseudoinverse_apply(frame: BPSFrame, rhs: np.ndarray) -> np.ndarray:
    complement = np.asarray(frame.complement_frame, dtype=complex)
    energies = np.asarray(frame.positive_energies, dtype=float)
    if complement.shape[1] != energies.size or np.any(energies <= 0.0):
        raise ValueError("BPS complement frame and energies are inconsistent")
    coordinates = complement.conj().T @ np.asarray(rhs, dtype=complex)
    return complement @ (coordinates / energies[:, None])


def projector_derivative_from_response(
    projector_frame: np.ndarray,
    response: np.ndarray,
) -> np.ndarray:
    """Reconstruct dP from X = (1-P)dP P."""

    frame = np.asarray(projector_frame, dtype=complex)
    values = np.asarray(response, dtype=complex)
    if values.shape != frame.shape:
        raise ValueError("projector frame and response shape disagree")
    derivative = values @ frame.conj().T + frame @ values.conj().T
    return 0.5 * (derivative + derivative.conj().T)


def project_moduli_tangents(
    couplings: np.ndarray,
    candidates: np.ndarray,
    *,
    relative_tolerance: float = 1e-12,
) -> np.ndarray:
    """Remove the complex radial/phase line and orthonormalize row tangents."""

    coefficients = np.asarray(couplings, dtype=complex)
    values = np.asarray(candidates, dtype=complex)
    if coefficients.ndim != 1 or values.ndim != 2:
        raise ValueError("couplings and tangent candidates have wrong dimensions")
    if values.shape[1] != coefficients.size or values.shape[0] < 1:
        raise ValueError("tangent candidates have the wrong shape")
    norm_squared = float(np.vdot(coefficients, coefficients).real)
    if norm_squared <= 0.0:
        raise ValueError("coupling vector has zero norm")
    overlaps = values @ coefficients.conj()
    projected = values - np.outer(overlaps / norm_squared, coefficients)
    q, r = np.linalg.qr(projected.T, mode="reduced")
    diagonal = np.diag(r)
    scale = max(float(np.linalg.norm(projected, ord=2)), np.finfo(float).tiny)
    if diagonal.size != values.shape[0] or np.any(
        np.abs(diagonal) <= float(relative_tolerance) * scale
    ):
        raise ValueError("projected tangent candidates do not have full rank")
    phases = diagonal / np.abs(diagonal)
    q = q * phases[None, :]
    tangents = np.asarray(q.T, dtype=complex)
    if not np.allclose(
        tangents @ tangents.conj().T,
        np.eye(values.shape[0]),
        atol=5e-13,
        rtol=5e-13,
    ):
        raise RuntimeError("moduli tangent orthonormalization failed")
    if float(np.max(np.abs(tangents @ coefficients.conj()))) > 5e-13:
        raise RuntimeError("moduli tangent retains radial or phase leakage")
    return tangents


def coupling_panels(
    couplings: np.ndarray,
    panel_size: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Return deterministic sparse and isotropic coupling-space panels."""

    coefficients = np.asarray(couplings, dtype=complex)
    size = int(panel_size)
    if coefficients.ndim != 1 or not 1 <= size < coefficients.size - 1:
        raise ValueError("invalid coupling panel dimensions")
    sparse_seed, isotropic_seed = np.random.SeedSequence(int(seed)).spawn(2)
    sparse_rng = np.random.default_rng(sparse_seed)
    isotropic_rng = np.random.default_rng(isotropic_seed)
    coordinates = sparse_rng.permutation(coefficients.size)[:size]
    sparse_candidates = np.eye(coefficients.size, dtype=complex)[coordinates]
    isotropic_candidates = isotropic_rng.normal(
        size=(size, coefficients.size)
    ) + 1j * isotropic_rng.normal(size=(size, coefficients.size))
    return {
        "sparse": project_moduli_tangents(coefficients, sparse_candidates),
        "isotropic": project_moduli_tangents(
            coefficients,
            isotropic_candidates,
        ),
    }


def _positive_spectrum(values: np.ndarray, rtol: float = 1e-12) -> np.ndarray:
    spectrum = np.maximum(np.asarray(values, dtype=float), 0.0)
    if spectrum.size == 0:
        return spectrum
    largest = float(np.max(spectrum))
    if largest <= 0.0:
        return np.empty(0, dtype=float)
    return spectrum[spectrum > float(rtol) * largest]


def _effective_rank(values: np.ndarray) -> float:
    spectrum = _positive_spectrum(values)
    if spectrum.size == 0:
        return 0.0
    return float(np.sum(spectrum) ** 2 / np.sum(spectrum**2))


def _spectral_entropy(values: np.ndarray) -> float:
    spectrum = _positive_spectrum(values)
    if spectrum.size <= 1:
        return 0.0
    probabilities = spectrum / np.sum(spectrum)
    return float(
        -np.sum(probabilities * np.log(probabilities)) / np.log(spectrum.size)
    )


def _branch_spectra(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    branch = np.asarray(values, dtype=complex)
    target_rank = branch.shape[-1]
    if float(np.linalg.norm(branch)) <= np.finfo(float).tiny:
        return np.zeros(target_rank, dtype=float), np.empty(0, dtype=float)
    target = np.linalg.eigvalsh(target_covariance(branch))
    target = np.maximum(np.asarray(target, dtype=float), 0.0)
    external = external_covariance_eigenvalues_scalable(branch)
    return target, external


def external_covariance_eigenvalues_scalable(
    channels: np.ndarray,
    rtol: float = 1e-12,
) -> np.ndarray:
    """Return the external spectrum from the smaller exact Gram side.

    The nonzero spectra of ``S S^dagger`` and ``S^dagger S`` agree.  Choosing
    the smaller side changes neither the observable nor the null covariance,
    while avoiding the prohibitive ``(mD)^2`` allocation at central N=14.
    """

    values = np.asarray(channels, dtype=complex)
    if values.ndim != 3:
        raise ValueError("channels must have shape (label, ambient, rank)")
    labels, ambient, rank = values.shape
    stacked = values.transpose(1, 0, 2).reshape(ambient, labels * rank)
    if ambient <= labels * rank:
        covariance = stacked @ stacked.conj().T / labels
    else:
        covariance = stacked.conj().T @ stacked / labels
    covariance = 0.5 * (covariance + covariance.conj().T)
    eigenvalues = np.linalg.eigvalsh(covariance)
    largest = max(float(eigenvalues[-1]), 0.0)
    if largest <= 0.0:
        raise ValueError("external covariance has no positive support")
    return np.asarray(
        eigenvalues[eigenvalues > float(rtol) * largest],
        dtype=float,
    )


def scalable_covariance_matched_wick(
    channels: np.ndarray,
    rtol: float = 1e-10,
) -> WickResult:
    """Evaluate the frozen four-channel statistic with scalable covariance."""

    whitened = whiten_channel_labels(channels, rtol=rtol)
    values = whitened.channels
    rank = values.shape[-1]
    left = target_covariance(values)
    left_eigenvalues = np.linalg.eigvalsh(left)
    right_eigenvalues = external_covariance_eigenvalues_scalable(values)
    left_trace = float(np.sum(left_eigenvalues))
    right_trace = float(np.sum(right_eigenvalues))
    A_left = (
        rank
        * float(np.sum(left_eigenvalues**2))
        / (left_trace * left_trace)
    )
    B_right = (
        rank
        * float(np.sum(right_eigenvalues**2))
        / (right_trace * right_trace)
    )
    tensor = four_channel_tensor(values)
    identity = np.eye(values.shape[0])
    wick = (
        A_left * np.einsum("mn,rs->mnrs", identity, identity)
        + B_right * np.einsum("ms,rn->mnrs", identity, identity)
    )
    connected = tensor - wick
    denominator = float(np.linalg.norm(wick))
    if denominator <= 0.0:
        raise RuntimeError("Wick tensor has zero norm")
    return WickResult(
        tensor=tensor,
        wick_tensor=wick,
        connected=connected,
        R4=float(np.linalg.norm(connected) / denominator),
        A_left=A_left,
        B_right=B_right,
        left_eigenvalues=left_eigenvalues,
        right_eigenvalues=right_eigenvalues,
        channel_covariance_eigenvalues=whitened.covariance_eigenvalues,
    )


def hodge_signature(response: HodgeResponse) -> HodgeSignature:
    """Reduce a resolved response to safe gauge-invariant two-point data."""

    minus = np.asarray(response.minus, dtype=complex)
    plus = np.asarray(response.plus, dtype=complex)
    if minus.shape != plus.shape or minus.ndim != 3:
        raise ValueError("Hodge branches must share (label, ambient, rank) shape")
    minus_weight = float(np.sum(np.abs(minus) ** 2))
    plus_weight = float(np.sum(np.abs(plus) ** 2))
    total_weight = minus_weight + plus_weight
    if total_weight <= 0.0:
        raise ValueError("Hodge response has zero total weight")
    balance = float(4.0 * minus_weight * plus_weight / total_weight**2)
    minus_target, minus_external = _branch_spectra(minus)
    plus_target, plus_external = _branch_spectra(plus)
    minus_channel = (
        channel_covariance(minus)
        if minus_weight > np.finfo(float).tiny
        else np.zeros((minus.shape[0], minus.shape[0]), dtype=complex)
    )
    plus_channel = (
        channel_covariance(plus)
        if plus_weight > np.finfo(float).tiny
        else np.zeros((plus.shape[0], plus.shape[0]), dtype=complex)
    )
    cross_scale = max(
        float(np.linalg.norm(minus) * np.linalg.norm(plus)),
        np.finfo(float).tiny,
    )
    cross = np.einsum(
        "mai,maj->mij",
        minus.conj(),
        plus,
        optimize=True,
    )
    orthogonality = float(np.linalg.norm(cross) / cross_scale)
    return HodgeSignature(
        channel_count=int(minus.shape[0]),
        target_rank=int(minus.shape[-1]),
        minus_weight=minus_weight,
        plus_weight=plus_weight,
        hodge_balance=balance,
        minus_channel_covariance=minus_channel,
        plus_channel_covariance=plus_channel,
        minus_target_eigenvalues=minus_target,
        plus_target_eigenvalues=plus_target,
        minus_external_eigenvalues=minus_external,
        plus_external_eigenvalues=plus_external,
        minus_target_effective_rank=_effective_rank(minus_target),
        plus_target_effective_rank=_effective_rank(plus_target),
        minus_external_effective_rank=_effective_rank(minus_external),
        plus_external_effective_rank=_effective_rank(plus_external),
        minus_target_entropy=_spectral_entropy(minus_target),
        plus_target_entropy=_spectral_entropy(plus_target),
        minus_external_entropy=_spectral_entropy(minus_external),
        plus_external_entropy=_spectral_entropy(plus_external),
        orthogonality_relative_error=orthogonality,
    )


def decomposable_curvature(
    response: HodgeResponse,
    first: int,
    second: int | None = None,
) -> np.ndarray:
    """Return the Hermitian Appendix-D curvature matrix from Hodge branches."""

    minus = np.asarray(response.minus, dtype=complex)
    plus = np.asarray(response.plus, dtype=complex)
    left = int(first)
    if not 0 <= left < minus.shape[0]:
        raise IndexError("first curvature channel is out of range")
    if second is None:
        curvature = (
            minus[left].conj().T @ minus[left]
            - plus[left].conj().T @ plus[left]
        )
    else:
        right = int(second)
        if not 0 <= right < minus.shape[0] or right == left:
            raise IndexError("second curvature channel is invalid")
        ordered = (
            minus[left].conj().T @ minus[right]
            - plus[right].conj().T @ plus[left]
        )
        curvature = ordered + ordered.conj().T
    return 0.5 * (curvature + curvature.conj().T)


def hodge_response(
    frame: BPSFrame,
    couplings: np.ndarray,
    tangents: np.ndarray,
    *,
    tolerance: float = 5e-10,
) -> HodgeResponse:
    """Compute exact, coexact, summed, and direct resolvent responses."""

    coefficients = np.asarray(couplings, dtype=complex)
    directions = np.asarray(tangents, dtype=complex)
    coordinates = len(cubic_triples(frame.N))
    if coefficients.shape != (coordinates,):
        raise ValueError("cubic coupling vector has the wrong shape")
    if directions.ndim != 2 or directions.shape[1] != coordinates:
        raise ValueError("tangent panel has the wrong shape")
    if directions.shape[0] < 1:
        raise ValueError("tangent panel is empty")
    projector = np.asarray(frame.projector_frame, dtype=complex)
    minus_values: list[np.ndarray] = []
    plus_values: list[np.ndarray] = []
    direct_values: list[np.ndarray] = []
    for tangent in directions:
        dq_in = cubic_supercharge(frame.N, frame.charge - 3, tangent)
        dq_out = cubic_supercharge(frame.N, frame.charge, tangent)
        rhs_minus = frame.q_in @ (dq_in.getH() @ projector)
        rhs_plus = frame.q_out.getH() @ (dq_out @ projector)
        d_hamiltonian = (
            dq_in @ frame.q_in.getH()
            + frame.q_in @ dq_in.getH()
            + dq_out.getH() @ frame.q_out
            + frame.q_out.getH() @ dq_out
        ).tocsr()
        rhs_direct = d_hamiltonian @ projector
        minus_values.append(-_pseudoinverse_apply(frame, rhs_minus))
        plus_values.append(-_pseudoinverse_apply(frame, rhs_plus))
        direct_values.append(-_pseudoinverse_apply(frame, rhs_direct))
    minus = np.asarray(minus_values, dtype=complex)
    plus = np.asarray(plus_values, dtype=complex)
    direct = np.asarray(direct_values, dtype=complex)
    total = minus + plus
    branch_sum_error = _relative_error(total, minus + plus)
    direct_error = _relative_error(total, direct)
    orthogonality_errors: list[float] = []
    for left, right in zip(minus, plus, strict=True):
        scale = max(
            float(np.linalg.norm(left) * np.linalg.norm(right)),
            np.finfo(float).tiny,
        )
        orthogonality_errors.append(
            float(np.linalg.norm(left.conj().T @ right) / scale)
        )
    orthogonality_error = max(orthogonality_errors)
    total_norm = max(float(np.linalg.norm(total)), np.finfo(float).tiny)
    leakage = float(
        np.linalg.norm(
            np.einsum(
                "ir,mij->mrj",
                projector.conj(),
                total,
                optimize=True,
            )
        )
        / total_norm
    )
    checks = {
        "finite_response": bool(
            np.all(np.isfinite(total.real)) and np.all(np.isfinite(total.imag))
        ),
        "branch_sum": branch_sum_error < float(tolerance),
        "direct_resolvent": direct_error < float(tolerance),
        "hodge_orthogonality": orthogonality_error < float(tolerance),
        "target_leakage": leakage < float(tolerance),
    }
    return HodgeResponse(
        minus=minus,
        plus=plus,
        total=total,
        direct=direct,
        branch_sum_relative_error=branch_sum_error,
        direct_relative_error=direct_error,
        orthogonality_relative_error=orthogonality_error,
        target_leakage=leakage,
        checks=checks,
    )
