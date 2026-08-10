from __future__ import annotations

import jax
import jax.numpy as jnp

from challenge15.physics_data import orbital_table
from challenge15.spec import SphereSpec


def normalized_spinors(theta, phi):
    """Return north-chart normalized spinors with u real and nonnegative.

    This uses z_N(theta, phi) = (cos(theta/2), exp(-i phi) sin(theta/2)).
    """
    theta_array = jnp.asarray(theta, dtype=jnp.float64)
    phi_array = jnp.asarray(phi, dtype=jnp.float64)
    theta_array, phi_array = jnp.broadcast_arrays(theta_array, phi_array)
    half_theta = theta_array / 2.0
    spinors = jnp.stack(
        (
            jnp.cos(half_theta),
            jnp.sin(half_theta) * jnp.exp(-1j * phi_array),
        ),
        axis=-1,
    )
    return _normalize_physical_spinors(spinors)


def north_lll_orbitals(spinors, spec: SphereSpec):
    """Evaluate LLL orbitals after normalizing supplied physical spinors."""
    return raw_north_lll_polynomials(_normalize_physical_spinors(spinors), spec)


def raw_north_lll_polynomials(spinors, spec: SphereSpec):
    """Evaluate homogeneous LLL polynomials without normalizing spinors.

    This raw polynomial boundary preserves exact holomorphic degree and is used
    by algebraic carrier construction. Use ``north_lll_orbitals`` for physical
    points whose representative should first be normalized.
    """
    spinors_array = _as_nonzero_spinors(spinors)
    u = spinors_array[..., 0]
    v = spinors_array[..., 1]
    table = orbital_table(spec)
    values = [
        coeff * (u ** power_u) * (v ** power_v)
        for coeff, power_u, power_v in zip(
            table.normalizations,
            table.u_powers,
            table.v_powers,
            strict=True,
        )
    ]
    return jnp.stack(values, axis=-1)


def south_lll_orbitals(spinors, spec: SphereSpec, return_transition: bool = False):
    """Return south-chart orbitals and the exact transition phase if requested.

    Supplied nonzero spinors are normalized as physical representatives before
    orbital evaluation, matching ``north_lll_orbitals``.

    For north-chart spinors from ``normalized_spinors``, the south chart uses
    z_S(theta, phi) = exp(i phi) z_N(theta, phi), so every degree-``two_q``
    orbital acquires the one-particle monopole transition
    exp(i * two_q * phi). For arbitrary nonzero spinors, the physical
    azimuth is extracted from the gauge-invariant overlap coordinate
    u * conjugate(v), whose phase is +phi for the canonical convention
    v = exp(-i phi) sin(theta / 2). The north/south transition is defined only
    on the overlap where both chart coordinates are nonzero; this function
    returns unit phase at the poles by convention.
    """
    spinors_array = _normalize_physical_spinors(spinors)
    north = raw_north_lll_polynomials(spinors_array, spec)
    transition = _north_south_transition(spinors_array, spec.two_q)
    south = transition[..., None] * north
    if return_transition:
        return south, transition
    return south


def rotate_spinors(spinors, rotation):
    spinors_array = _normalize_physical_spinors(spinors)
    rotation_array = _normalize_su2(rotation)
    rotated = jnp.einsum("...ab,...b->...a", rotation_array, spinors_array)
    return _normalize_physical_spinors(rotated)


def _as_nonzero_spinors(spinors):
    spinors_array = jnp.asarray(spinors, dtype=jnp.complex128)
    if spinors_array.shape[-1] != 2:
        raise ValueError("spinors must have last axis of length 2")
    norms = jnp.linalg.norm(spinors_array, axis=-1, keepdims=True)
    if not isinstance(norms, jax.core.Tracer) and bool(jnp.any(norms == 0.0)):
        raise ValueError("spinors must have nonzero norm")
    return spinors_array


def _normalize_physical_spinors(spinors):
    spinors_array = _as_nonzero_spinors(spinors)
    norms = jnp.linalg.norm(spinors_array, axis=-1, keepdims=True)
    return spinors_array / norms


def _normalize_su2(rotation):
    rotation_array = jnp.asarray(rotation, dtype=jnp.complex128)
    if rotation_array.shape[-2:] != (2, 2):
        raise ValueError("rotation must have shape (..., 2, 2)")
    determinants = (
        rotation_array[..., 0, 0] * rotation_array[..., 1, 1]
        - rotation_array[..., 0, 1] * rotation_array[..., 1, 0]
    )
    if bool(jnp.any(jnp.abs(determinants) == 0.0)):
        raise ValueError("rotation must have nonzero determinant")
    normalized = rotation_array / jnp.sqrt(determinants)[..., None, None]
    identity = jnp.broadcast_to(
        jnp.eye(2, dtype=jnp.complex128),
        normalized.shape[:-2] + (2, 2),
    )
    unitary_check = normalized.conj().swapaxes(-1, -2) @ normalized
    if not bool(jnp.allclose(unitary_check, identity, atol=1e-12, rtol=1e-12)):
        raise ValueError("rotation must be proportional to an SU(2) matrix")
    return normalized


def _north_south_transition(spinors, two_q: int):
    overlap = spinors[..., 0] * jnp.conjugate(spinors[..., 1])
    overlap_phase = jnp.where(
        jnp.abs(overlap) > 1e-15,
        overlap / jnp.abs(overlap),
        jnp.ones_like(overlap),
    )
    return overlap_phase**two_q
