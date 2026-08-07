"""Deterministic algebra helpers for the hard-spin classical O(n) proof.

The functions in this module are regression checks for identities proved in
``ON_PROOF_AUDIT.md``.  They do not replace the analytic argument.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def _validate_dimension(n: int) -> None:
    if isinstance(n, bool) or not isinstance(n, int) or n < 2:
        raise ValueError("the hard-spin O(n) proof requires an integer n >= 2")


def _validate_transverse(n: int, transverse: int) -> None:
    _validate_dimension(n)
    if (
        isinstance(transverse, bool)
        or not isinstance(transverse, int)
        or transverse < 1
        or transverse >= n
    ):
        raise ValueError(
            "transverse is a zero-based component index in {1, ..., n-1}"
        )


def rotation_generator_matrix(n: int, transverse: int) -> np.ndarray:
    """Return the generator rotating component 0 into ``transverse``.

    With this convention, for a column spin ``s``,

    ``(G @ s)[0] = -s[transverse]`` and
    ``(G @ s)[transverse] = s[0]``.
    """

    _validate_transverse(n, transverse)
    generator = np.zeros((n, n), dtype=np.float64)
    generator[0, transverse] = -1.0
    generator[transverse, 0] = 1.0
    return generator


def rotate_in_plane(
    spin: Sequence[float],
    angle: float,
    transverse: int,
) -> np.ndarray:
    """Rotate a spin in the (0, transverse) internal plane."""

    vector = np.asarray(spin, dtype=np.float64)
    if vector.ndim != 1:
        raise ValueError("spin must be a one-dimensional vector")
    _validate_transverse(int(vector.size), transverse)
    if not math.isfinite(angle):
        raise ValueError("angle must be finite")
    rotated = vector.copy()
    cosine = math.cos(angle)
    sine = math.sin(angle)
    longitudinal = vector[0]
    transverse_value = vector[transverse]
    rotated[0] = cosine * longitudinal - sine * transverse_value
    rotated[transverse] = (
        sine * longitudinal + cosine * transverse_value
    )
    return rotated


def pair_plane_projection(
    first: Sequence[float],
    second: Sequence[float],
    transverse: int,
) -> float:
    """Return s_0 t_0 + s_a t_a for the selected rotation plane."""

    s = np.asarray(first, dtype=np.float64)
    t = np.asarray(second, dtype=np.float64)
    if s.ndim != 1 or t.ndim != 1 or s.shape != t.shape:
        raise ValueError("the two spins must be vectors of equal dimension")
    _validate_transverse(int(s.size), transverse)
    return float(s[0] * t[0] + s[transverse] * t[transverse])


def pair_second_variation_exact(
    first: Sequence[float],
    second: Sequence[float],
    u: complex,
    v: complex,
    transverse: int,
    coupling: float = 1.0,
) -> float:
    r"""Evaluate the Hermitian second variation by generator matrices.

    This computes

    .. math::

       (\bar u L_s+\bar v L_t)(u L_s+v L_t)
       [-J\,s\cdot t]

    without substituting the simplified projected-pair formula.
    """

    s = np.asarray(first, dtype=np.float64)
    t = np.asarray(second, dtype=np.float64)
    if s.ndim != 1 or t.ndim != 1 or s.shape != t.shape:
        raise ValueError("the two spins must be vectors of equal dimension")
    n = int(s.size)
    generator = rotation_generator_matrix(n, transverse)
    if not math.isfinite(coupling) or coupling < 0.0:
        raise ValueError("coupling must be finite and nonnegative")
    u_complex = complex(u)
    v_complex = complex(v)
    g_s = generator @ s
    g_t = generator @ t
    g2_s = generator @ g_s
    g2_t = generator @ g_t
    f_ss = -coupling * float(np.dot(g2_s, t))
    f_tt = -coupling * float(np.dot(s, g2_t))
    f_st = -coupling * float(np.dot(g_s, g_t))
    result = (
        abs(u_complex) ** 2 * f_ss
        + np.conjugate(u_complex) * v_complex * f_st
        + np.conjugate(v_complex) * u_complex * f_st
        + abs(v_complex) ** 2 * f_tt
    )
    if abs(float(np.imag(result))) > 2e-13:
        raise ArithmeticError("Hermitian second variation is not real")
    return float(np.real(result))


def pair_second_variation_formula(
    first: Sequence[float],
    second: Sequence[float],
    u: complex,
    v: complex,
    transverse: int,
    coupling: float = 1.0,
) -> float:
    """Evaluate J |u-v|^2 (s_0 t_0 + s_a t_a)."""

    if not math.isfinite(coupling) or coupling < 0.0:
        raise ValueError("coupling must be finite and nonnegative")
    projection = pair_plane_projection(first, second, transverse)
    return float(coupling * abs(complex(u) - complex(v)) ** 2 * projection)


def transverse_parseval_sides(spins: np.ndarray) -> tuple[float, float]:
    r"""Return Fourier and real-space sides of the transverse Parseval sum.

    ``spins`` has shape ``(L_1, ..., L_d, n)``.  NumPy's unnormalized forward
    transform matches the convention
    :math:`A_q^a=\sum_x e^{-iqx}S_x^a`.
    """

    field = np.asarray(spins, dtype=np.float64)
    if field.ndim < 2:
        raise ValueError("spins must contain at least one lattice axis")
    n = int(field.shape[-1])
    _validate_dimension(n)
    lattice_shape = field.shape[:-1]
    volume = int(np.prod(lattice_shape))
    transformed = np.fft.fftn(
        field[..., 1:],
        axes=tuple(range(field.ndim - 1)),
    )
    fourier_side = float(np.sum(np.abs(transformed) ** 2))
    real_side = float(volume * np.sum(field[..., 1:] ** 2))
    return fourier_side, real_side
