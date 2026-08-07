from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NewtonFixedPointEstimate:
    candidate: np.ndarray
    correction: np.ndarray
    map_residual: np.ndarray
    predicted_residual: np.ndarray
    condition_number: float
    singular_values: np.ndarray


@dataclass(frozen=True)
class BiasNewtonCorrection:
    correction: np.ndarray
    condition_number: float
    predicted_mean: np.ndarray


def newton_fixed_point_candidate(
    input_couplings: np.ndarray,
    mapped_couplings: np.ndarray,
    jacobian: np.ndarray,
    *,
    maximum_condition_number: float = 1.0e6,
    maximum_correction: float = 0.05,
) -> NewtonFixedPointEstimate:
    """Solve one unregularized Newton step for F(K) = R(K) - K."""
    input_couplings = np.asarray(input_couplings, dtype=np.float64)
    mapped_couplings = np.asarray(mapped_couplings, dtype=np.float64)
    jacobian = np.asarray(jacobian, dtype=np.float64)
    if input_couplings.ndim != 1 or mapped_couplings.shape != input_couplings.shape:
        raise ValueError("input and mapped couplings must be equal-length vectors")
    size = input_couplings.size
    if jacobian.shape != (size, size):
        raise ValueError("Jacobian shape must match the coupling-vector dimension")
    if not (
        np.all(np.isfinite(input_couplings))
        and np.all(np.isfinite(mapped_couplings))
        and np.all(np.isfinite(jacobian))
    ):
        raise ValueError("fixed-point inputs must all be finite")
    if maximum_condition_number <= 1.0 or maximum_correction <= 0.0:
        raise ValueError("invalid Newton safety limits")

    map_residual = mapped_couplings - input_couplings
    system = np.eye(size, dtype=np.float64) - jacobian
    singular_values = np.linalg.svd(system, compute_uv=False)
    condition_number = float(singular_values[0] / singular_values[-1])
    if not np.isfinite(condition_number) or condition_number > maximum_condition_number:
        raise ValueError(
            "I-T is too ill-conditioned for an unregularized Newton step: "
            f"condition number {condition_number:.6g}"
        )
    correction = np.linalg.solve(system, map_residual)
    correction_max = float(np.max(np.abs(correction)))
    if correction_max > maximum_correction:
        raise ValueError(
            "Newton correction exceeds the predeclared trust radius: "
            f"{correction_max:.6g} > {maximum_correction:.6g}"
        )
    candidate = input_couplings + correction
    predicted_residual = map_residual + (jacobian - np.eye(size)) @ correction
    return NewtonFixedPointEstimate(
        candidate=candidate,
        correction=correction,
        map_residual=map_residual,
        predicted_residual=predicted_residual,
        condition_number=condition_number,
        singular_values=singular_values,
    )


def fixed_point_residual_report(
    candidate: np.ndarray,
    mapped_couplings: np.ndarray,
    *,
    absolute_tolerance: float = 1.0e-3,
    relative_l2_tolerance: float = 5.0e-3,
) -> dict[str, object]:
    """Evaluate the complete-vector residual against predeclared gates."""
    candidate = np.asarray(candidate, dtype=np.float64)
    mapped_couplings = np.asarray(mapped_couplings, dtype=np.float64)
    if candidate.ndim != 1 or mapped_couplings.shape != candidate.shape:
        raise ValueError("candidate and mapped couplings must be equal-length vectors")
    if absolute_tolerance <= 0.0 or relative_l2_tolerance <= 0.0:
        raise ValueError("fixed-point tolerances must be positive")
    residual = mapped_couplings - candidate
    l2 = float(np.linalg.norm(residual))
    linf = float(np.max(np.abs(residual)))
    scale = float(np.linalg.norm(candidate))
    if scale == 0.0:
        raise ValueError("cannot define a relative residual for the zero vector")
    relative_l2 = l2 / scale
    passed = linf <= absolute_tolerance and relative_l2 <= relative_l2_tolerance
    return {
        "status": "PASS" if passed else "FAIL",
        "candidate_couplings": candidate.tolist(),
        "mapped_couplings": mapped_couplings.tolist(),
        "residual": residual.tolist(),
        "l2_norm": l2,
        "linf_norm": linf,
        "relative_l2_norm": relative_l2,
        "absolute_tolerance": float(absolute_tolerance),
        "relative_l2_tolerance": float(relative_l2_tolerance),
        "criteria_source": "predeclared_implementation_acceptance_gate_not_paper_published",
    }


def bias_newton_correction(
    mean_operators: np.ndarray,
    covariance: np.ndarray,
    *,
    maximum_condition_number: float = 1.0e6,
    maximum_correction: float = 1.0e-3,
) -> BiasNewtonCorrection:
    """Solve J_new = J + Cov(S,S)^-1 <S> for a uniform target."""
    mean_operators = np.asarray(mean_operators, dtype=np.float64)
    covariance = np.asarray(covariance, dtype=np.float64)
    if mean_operators.ndim != 1 or covariance.shape != (
        mean_operators.size,
        mean_operators.size,
    ):
        raise ValueError("bias moments and covariance dimensions do not match")
    if not np.all(np.isfinite(mean_operators)) or not np.all(np.isfinite(covariance)):
        raise ValueError("bias Newton inputs must be finite")
    if not np.allclose(covariance, covariance.T, rtol=1e-10, atol=1e-10):
        raise ValueError("bias covariance must be symmetric")
    eigenvalues = np.linalg.eigvalsh(covariance)
    if eigenvalues[0] <= 0.0:
        raise ValueError("bias covariance must be positive definite")
    condition_number = float(eigenvalues[-1] / eigenvalues[0])
    if condition_number > maximum_condition_number:
        raise ValueError(
            "bias covariance is too ill-conditioned for an unregularized Newton step: "
            f"{condition_number:.6g}"
        )
    correction = np.linalg.solve(covariance, mean_operators)
    correction_max = float(np.max(np.abs(correction)))
    if correction_max > maximum_correction:
        raise ValueError(
            "bias correction exceeds the predeclared trust radius: "
            f"{correction_max:.6g} > {maximum_correction:.6g}"
        )
    predicted_mean = mean_operators - covariance @ correction
    return BiasNewtonCorrection(correction, condition_number, predicted_mean)
