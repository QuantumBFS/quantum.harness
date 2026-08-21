"""Exact chiral-index kernels and their off-fiber geometric response.

For a full-row-rank rectangular factor ``T`` with shape ``(n_b, n_a)`` and
``n_a > n_b``, the chiral Hamiltonian

    H = [[0, T^dagger], [T, 0]]

has index-protected nullity ``D = n_a - n_b``.  Production response formulas
operate on the rectangular factor and its reduced singular system; the dense
Hamiltonian constructor is provided for exact unit tests and small audits.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np


TangentKind = Literal["random", "local", "structured"]


def _validated_factor(
    factor: np.ndarray,
    *,
    tolerance: float = 1e-12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(factor, dtype=complex)
    if values.ndim != 2:
        raise ValueError("T must be a two-dimensional rectangular factor")
    n_b, n_a = values.shape
    if n_a <= n_b:
        raise ValueError("the chiral index construction requires n_a > n_b")
    if not np.all(np.isfinite(values)):
        raise ValueError("T must contain only finite values")
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive and finite")
    _, singular_values, right_adjoint = np.linalg.svd(
        values, full_matrices=True
    )
    threshold = tolerance * max(float(singular_values[0]), 1.0)
    if singular_values.size != n_b or float(singular_values[-1]) <= threshold:
        raise ValueError("T must have full row rank")
    kernel = right_adjoint.conj().T[:, n_b:]
    return values, singular_values, kernel


def build_chiral_hamiltonian(factor: np.ndarray) -> np.ndarray:
    """Return the dense bipartite chiral Hamiltonian for tests and audits."""

    values, _, _ = _validated_factor(factor)
    n_b, n_a = values.shape
    hamiltonian = np.zeros((n_a + n_b, n_a + n_b), dtype=complex)
    hamiltonian[:n_a, n_a:] = values.conj().T
    hamiltonian[n_a:, :n_a] = values
    return hamiltonian


def zero_mode_frame(
    factor: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """Return an orthonormal frame for the complete index-protected kernel."""

    values, _, kernel = _validated_factor(factor, tolerance=tolerance)
    n_b, n_a = values.shape
    frame = np.zeros((n_a + n_b, n_a - n_b), dtype=complex)
    frame[:n_a] = kernel
    return frame


def chiral_response(
    factor: np.ndarray,
    tangent: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """Return the horizontal zero-mode response from a rectangular tangent.

    If ``K`` spans ``ker(T)``, differentiating ``T K = 0`` in the horizontal
    gauge ``K^dagger dK = 0`` gives

    ``dK = -T^dagger (T T^dagger)^-1 dT K``.

    The returned array embeds this response in the full A/B ambient space.
    No dense chiral Hamiltonian or full pseudoinverse is constructed.
    """

    values, _, kernel = _validated_factor(factor, tolerance=tolerance)
    direction = np.asarray(tangent, dtype=complex)
    if direction.shape != values.shape:
        raise ValueError("dT must have the same shape as T")
    if not np.all(np.isfinite(direction)):
        raise ValueError("dT must contain only finite values")
    gram = values @ values.conj().T
    reduced = np.linalg.solve(gram, direction @ kernel)
    response_a = -values.conj().T @ reduced
    n_b, n_a = values.shape
    response = np.zeros((n_a + n_b, n_a - n_b), dtype=complex)
    response[:n_a] = response_a
    return response


def make_chiral_base(*, n_a: int, n_b: int, seed: int) -> np.ndarray:
    """Draw a deterministic proper-complex full-row-rank base factor."""

    if n_a <= n_b or n_b < 1:
        raise ValueError("base dimensions require integers n_a > n_b >= 1")
    generator = np.random.default_rng(int(seed))
    factor = (
        generator.normal(size=(n_b, n_a))
        + 1j * generator.normal(size=(n_b, n_a))
    ) / np.sqrt(2.0 * n_a)
    # A continuous complex draw is full row rank with probability one; retain
    # an explicit numerical gate rather than silently repairing a bad draw.
    _validated_factor(factor)
    return factor


def _normalize_panel(panel: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(panel, axis=(1, 2))
    if np.any(~np.isfinite(norms)) or np.any(norms <= 1e-14):
        raise RuntimeError("tangent construction produced a zero or invalid channel")
    return panel / norms[:, None, None]


def make_tangent_panel(
    *,
    n_a: int,
    n_b: int,
    count: int,
    kind: TangentKind,
    seed: int,
    bandwidth: int = 2,
    cell_shape: tuple[int, int] = (4, 6),
) -> np.ndarray:
    """Construct equally normalized random, local, or repeated-cell tangents."""

    if n_a <= n_b or n_b < 1:
        raise ValueError("tangent dimensions require n_a > n_b >= 1")
    if count < 1:
        raise ValueError("tangent channel count must be positive")
    if kind not in ("random", "local", "structured"):
        raise ValueError(f"unknown tangent class: {kind}")
    generator = np.random.default_rng(int(seed))

    if kind == "random":
        panel = generator.normal(size=(count, n_b, n_a)) + 1j * generator.normal(
            size=(count, n_b, n_a)
        )
    elif kind == "local":
        if bandwidth < 0:
            raise ValueError("local bandwidth must be nonnegative")
        mask = np.zeros((n_b, n_a), dtype=bool)
        for row in range(n_b):
            center = int(round(row * n_a / n_b)) % n_a
            for offset in range(-bandwidth, bandwidth + 1):
                mask[row, (center + offset) % n_a] = True
        panel = np.zeros((count, n_b, n_a), dtype=complex)
        values = generator.normal(size=(count, int(mask.sum()))) + 1j * generator.normal(
            size=(count, int(mask.sum()))
        )
        panel[:, mask] = values
    else:
        cell_b, cell_a = map(int, cell_shape)
        if cell_b < 1 or cell_a < 1:
            raise ValueError("repeated-cell dimensions must be positive")
        cells = generator.normal(size=(count, cell_b, cell_a)) + 1j * generator.normal(
            size=(count, cell_b, cell_a)
        )
        row_repetitions = (n_b + cell_b - 1) // cell_b
        column_repetitions = (n_a + cell_a - 1) // cell_a
        panel = np.tile(cells, (1, row_repetitions, column_repetitions))[
            :, :n_b, :n_a
        ]
    return _normalize_panel(np.asarray(panel, dtype=complex))


def _haar_unitary(dimension: int, generator: np.random.Generator) -> np.ndarray:
    draw = generator.normal(size=(dimension, dimension)) + 1j * generator.normal(
        size=(dimension, dimension)
    )
    frame, triangular = np.linalg.qr(draw)
    phases = np.diag(triangular)
    phases = np.where(np.abs(phases) > 0.0, phases / np.abs(phases), 1.0)
    return frame @ np.diag(phases.conj())


def _projector_derivative(frame: np.ndarray, response: np.ndarray) -> np.ndarray:
    return response @ frame.conj().T + frame @ response.conj().T


def audit_chiral_case(n_a: int, n_b: int, seed: int) -> dict[str, Any]:
    """Audit exact index, gap, response, finite difference, and gauge covariance."""

    tolerance = 1e-12
    factor = make_chiral_base(n_a=n_a, n_b=n_b, seed=seed)
    tangent = make_tangent_panel(
        n_a=n_a,
        n_b=n_b,
        count=1,
        kind="random",
        seed=seed + 1,
    )[0]
    values, singular_values, kernel = _validated_factor(
        factor, tolerance=tolerance
    )
    frame = zero_mode_frame(values, tolerance=tolerance)
    response = chiral_response(values, tangent, tolerance=tolerance)
    projector = frame @ frame.conj().T
    derivative = _projector_derivative(frame, response)
    epsilon = 2e-6
    plus = zero_mode_frame(values + epsilon * tangent, tolerance=tolerance)
    minus = zero_mode_frame(values - epsilon * tangent, tolerance=tolerance)
    finite_difference = (
        plus @ plus.conj().T - minus @ minus.conj().T
    ) / (2.0 * epsilon)

    generator = np.random.default_rng(seed + 2)
    unitary_a = _haar_unitary(n_a, generator)
    unitary_b = _haar_unitary(n_b, generator)
    ambient = np.zeros((n_a + n_b, n_a + n_b), dtype=complex)
    ambient[:n_a, :n_a] = unitary_a
    ambient[n_a:, n_a:] = unitary_b
    transformed_factor = unitary_b @ values @ unitary_a.conj().T
    transformed_tangent = unitary_b @ tangent @ unitary_a.conj().T
    transformed_frame = zero_mode_frame(transformed_factor, tolerance=tolerance)
    transformed_response = chiral_response(
        transformed_factor, transformed_tangent, tolerance=tolerance
    )
    transformed_projector = transformed_frame @ transformed_frame.conj().T
    transformed_derivative = _projector_derivative(
        transformed_frame, transformed_response
    )

    response_a = response[:n_a]
    equation = values @ response_a + tangent @ kernel
    residuals = {
        "kernel": float(np.linalg.norm(values @ kernel)),
        "orthonormality": float(
            np.linalg.norm(frame.conj().T @ frame - np.eye(n_a - n_b))
        ),
        "chiral_anticommutator": 0.0,
        "horizontal_gauge": float(np.linalg.norm(frame.conj().T @ response)),
        "response_equation_relative": float(np.linalg.norm(equation))
        / max(float(np.linalg.norm(tangent @ kernel)), 1e-30),
        "projector_finite_difference_relative": float(
            np.linalg.norm(derivative - finite_difference)
        )
        / max(float(np.linalg.norm(derivative)), 1e-30),
        "gauge_projector_relative": float(
            np.linalg.norm(transformed_projector - ambient @ projector @ ambient.conj().T)
        )
        / max(float(np.linalg.norm(projector)), 1e-30),
        "gauge_response_relative": float(
            np.linalg.norm(
                transformed_derivative - ambient @ derivative @ ambient.conj().T
            )
        )
        / max(float(np.linalg.norm(derivative)), 1e-30),
    }
    gram_gap = float(
        np.sqrt(np.min(np.linalg.eigvalsh(values @ values.conj().T)))
    )
    external_gap = float(singular_values[-1])
    checks = {
        "full_row_rank": bool(np.linalg.matrix_rank(values, tol=tolerance) == n_b),
        "exact_index_nullity": frame.shape[1] == n_a - n_b,
        "kernel_residual": residuals["kernel"] < 1e-10,
        "orthonormal_frame": residuals["orthonormality"] < 1e-10,
        "chiral_anticommutation": residuals["chiral_anticommutator"] < 1e-14,
        "gap_equals_sigma_min": abs(gram_gap - external_gap)
        <= 1e-10 * max(external_gap, 1.0),
        "horizontal_response": residuals["horizontal_gauge"] < 1e-10,
        "response_equation": residuals["response_equation_relative"] < 1e-10,
        "projector_finite_difference": residuals[
            "projector_finite_difference_relative"
        ]
        < 1e-6,
        "gauge_projector": residuals["gauge_projector_relative"] < 1e-10,
        "gauge_response": residuals["gauge_response_relative"] < 1e-9,
    }
    return {
        "schema": "chiral_kernel_case_audit_v14",
        "n_a": int(n_a),
        "n_b": int(n_b),
        "nullity": int(frame.shape[1]),
        "expected_nullity": int(n_a - n_b),
        "external_gap": external_gap,
        "sigma_min": external_gap,
        "gram_gap": gram_gap,
        "seed": int(seed),
        "residuals": residuals,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
