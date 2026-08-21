"""Exact protected response for arbitrary Hermitian one-body generators.

This v6 adapter intentionally leaves the accepted v4 response module
unchanged.  It evaluates the differentiated constraint-intertwiner identity

    Q H^{-1} Q (dH) P = -Q dGamma(G) P

directly for a complete panel of band-space generators.
"""

from __future__ import annotations

import numpy as np

from .lattice import manybody_one_body_operator
from .manybody_response import KernelFrame
from .matrix_free_response import StreamedResponse, factored_parent_operator


def _project_complement(frame: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Project matrix columns orthogonally away from the protected kernel."""

    return values - frame @ (frame.conj().T @ values)


def analytic_protected_generator_response(
    system,
    kernel: KernelFrame,
    generators: np.ndarray,
) -> StreamedResponse:
    """Evaluate exact protected responses for Hermitian one-body generators.

    Parameters
    ----------
    system:
        A factorized protected parent exposing ``n_flux``, ``basis``, and
        ``constraints``.
    kernel:
        An orthonormal frame for the complete zero-mode subspace.
    generators:
        Complex array with shape ``(label, n_flux, n_flux)``.  Normalization
        and trace removal are properties of the operator prescription rather
        than of the exact response theorem, so this function only enforces
        finiteness and Hermiticity.
    """

    values = np.asarray(generators, dtype=complex)
    expected = (int(system.n_flux), int(system.n_flux))
    if values.ndim != 3 or values.shape[0] < 1 or values.shape[1:] != expected:
        raise ValueError("protected generators have the wrong shape")
    if not np.all(np.isfinite(values)):
        raise ValueError("protected generators must be finite")
    if not np.allclose(
        values,
        values.conj().transpose(0, 2, 1),
        atol=1e-11,
        rtol=1e-11,
    ):
        raise ValueError("protected generators must be Hermitian")

    frame = np.asarray(kernel.frame, dtype=complex)
    if frame.ndim != 2 or frame.shape[0] != system.basis.dimension:
        raise ValueError("kernel frame and many-body basis disagree")
    parent = factored_parent_operator(system.constraints)
    channels: list[np.ndarray] = []
    relative_residuals: list[float] = []
    fiber_norm = 0.0
    for generator in values:
        fock_generator = manybody_one_body_operator(system.basis, generator)
        generator_action = np.asarray(fock_generator @ frame)
        response = -_project_complement(frame, generator_action)
        tangent_action = -np.asarray(parent @ generator_action)
        fiber_norm = max(
            fiber_norm,
            float(np.linalg.norm(frame.conj().T @ tangent_action)),
        )
        residual = np.asarray(parent @ response) - tangent_action
        relative_residuals.append(
            float(np.linalg.norm(residual))
            / max(float(np.linalg.norm(tangent_action)), 1e-30)
        )
        channels.append(response)

    channel_array = np.asarray(channels, dtype=complex)
    leakage = max(
        float(np.linalg.norm(frame.conj().T @ response))
        for response in channel_array
    )
    return StreamedResponse(
        channels=channel_array,
        shift_values=(0.0, 0.0),
        maximum_relative_residual=max(relative_residuals),
        maximum_shift_difference=0.0,
        maximum_kernel_leakage=leakage,
        maximum_iterations=0,
        failed_columns=0,
        tangent_fiber_norm=fiber_norm,
    )
