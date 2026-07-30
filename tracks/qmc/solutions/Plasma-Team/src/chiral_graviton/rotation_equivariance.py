"""Genuine SO(3) rotation-equivariance verification for quantum states.

*Output-state tests* — verify that the resulting quantum state transforms
  correctly under many-body rotations (``rotation_equivariance_error``,
  ``scalar_invariance_error``, ``nqs_multiplet_rotation_error``).

*Architectural alignment test* — measures how naturally the raw network
  output aligns with the SO(3) symmetry sector before projection
  (``projection_alignment_quality``).
"""

from __future__ import annotations

import numpy as np
from scipy import linalg, sparse
from scipy.sparse import linalg as sparse_linalg

from .angular_momentum import angular_momentum_lowering
from .basis import FockBasis


def rotation_equivariance_error(
    bases: list[FockBasis],
    vectors: list[np.ndarray],
    total_l: int,
    *,
    axis: tuple[float, float, float] = (1.0, 2.0, 3.0),
    angle: float = 0.371,
    seed: int = 1729,
) -> float:
    """Check a generic-axis rotation against the exact spin-L representation.

    Builds the full many-body angular-momentum generators L_x, L_y, L_z across
    all (2L+1) L_z sectors, constructs the ideal spin-L representation
    matrices, applies the same finite rotation to both, and returns the norm
    of the difference.

    Parameters
    ----------
    bases : list of FockBasis
        Fock bases for M = L, L-1, ..., -L (2L+1 sectors).
    vectors : list of np.ndarray
        Normalized state vectors in each sector, same ordering as *bases*.
    total_l : int
        Total angular momentum quantum number.
    axis : tuple
        Rotation axis (will be normalized).
    angle : float
        Rotation angle in radians.

    Returns
    -------
    float
        ``||R_actual(θ,n)|ψ_superposition> - R_spin(θ,n)|ψ_superposition>||``.
    """

    if len(bases) != len(vectors):
        raise ValueError("bases and vectors must have the same length")
    n_members = 2 * total_l + 1
    if len(bases) != n_members:
        raise ValueError(f"expected {n_members} Lz sectors for L={total_l}")

    dimensions = [basis.dimension for basis in bases]
    offsets = np.cumsum([0, *dimensions])
    total_dimension = int(offsets[-1])

    # Embed the multiplet members into a common big vector.
    embedding = np.zeros((total_dimension, n_members), dtype=np.complex128)
    for column, vector in enumerate(vectors):
        embedding[offsets[column] : offsets[column + 1], column] = vector

    # Build many-body angular-momentum generators across all sectors.
    lowering = sparse.lil_matrix((total_dimension, total_dimension), dtype=np.complex128)
    for column in range(n_members - 1):
        block = angular_momentum_lowering(bases[column], bases[column + 1])
        lowering[
            offsets[column + 1] : offsets[column + 2],
            offsets[column] : offsets[column + 1],
        ] = block
    lowering = lowering.tocsr()
    raising = lowering.getH()

    m_values = np.arange(total_l, -total_l - 1, -1, dtype=float)
    actual_z = sparse.diags(
        np.concatenate(
            [np.full(dimension, m) for dimension, m in zip(dimensions, m_values)]
        ),
        format="csr",
    )
    actual_x = 0.5 * (raising + lowering)
    actual_y = -0.5j * (raising - lowering)

    # Build ideal spin-L generators.
    spin_lowering = np.zeros((n_members, n_members), dtype=np.complex128)
    for column, m in enumerate(m_values[:-1]):
        spin_lowering[column + 1, column] = np.sqrt(
            (total_l + m) * (total_l - m + 1)
        )
    spin_raising = spin_lowering.conjugate().T
    spin_x = 0.5 * (spin_raising + spin_lowering)
    spin_y = -0.5j * (spin_raising - spin_lowering)
    spin_z = np.diag(m_values)

    # Normalise the rotation axis.
    axis_arr = np.asarray(axis, dtype=np.float64)
    axis_arr /= np.linalg.norm(axis_arr)

    actual_generator = (
        axis_arr[0] * actual_x + axis_arr[1] * actual_y + axis_arr[2] * actual_z
    )
    spin_generator = (
        axis_arr[0] * spin_x + axis_arr[1] * spin_y + axis_arr[2] * spin_z
    )

    # Build a fixed superposition so different runs are comparable.
    rng = np.random.default_rng(seed)
    coefficients = rng.normal(size=n_members) + 1j * rng.normal(size=n_members)
    coefficients /= np.linalg.norm(coefficients)

    rotated_actual = sparse_linalg.expm_multiply(
        -1j * angle * actual_generator, embedding @ coefficients
    )
    rotated_expected = embedding @ (
        linalg.expm(-1j * angle * spin_generator) @ coefficients
    )
    return float(np.linalg.norm(rotated_actual - rotated_expected))


def scalar_invariance_error(basis: FockBasis, vector: np.ndarray) -> float:
    """Verify an L=0 state is annihilated by L_-.

    A state in the M=0 sector that satisfies L_+|psi>=0 (enforced by
    projection) and L_-|psi>=0 (verified here) is a true SO(3) scalar
    and therefore invariant under all rotations.

    Parameters
    ----------
    basis : FockBasis
        The M=0 (L_z=0) Fock basis.
    vector : np.ndarray
        Normalized state vector in the M=0 sector.

    Returns
    -------
    float
        ``||L_-|psi>||`` -- the norm of the lowered state.  Should be
        zero (within numerical tolerance) for a genuine L=0 state.
    """

    if basis.two_lz != 0:
        raise ValueError("scalar invariance test requires an M=0 sector")
    target = FockBasis(basis.system, basis.two_lz - 2)
    lowering = angular_momentum_lowering(basis, target)
    lowered = lowering @ np.asarray(vector, dtype=np.complex128)
    return float(np.linalg.norm(lowered))


def nqs_multiplet_rotation_error(
    highest_basis: FockBasis,
    highest_vector: np.ndarray,
    total_l: int,
    *,
    axis: tuple[float, float, float] = (1.0, 2.0, 3.0),
    angle: float = 0.371,
) -> float:
    """Build the full L multiplet from a highest-weight state and test rotation.

    Repeatedly applies L_- to construct all M components, then calls
    ``rotation_equivariance_error`` to verify finite-rotation behaviour.

    Parameters
    ----------
    highest_basis : FockBasis
        Fock basis for the M=L (highest-weight) sector.
    highest_vector : np.ndarray
        Normalized highest-weight state vector.
    total_l : int
        Total angular momentum quantum number.

    Returns
    -------
    float
        Rotation equivariance error (see ``rotation_equivariance_error``).
    """

    if highest_basis.two_lz != 2 * total_l:
        raise ValueError("highest_basis must be the M=L sector")

    basis = highest_basis
    vector = np.asarray(highest_vector, dtype=np.complex128)
    vector /= np.linalg.norm(vector)

    bases: list[FockBasis] = []
    vectors: list[np.ndarray] = []

    for m in range(total_l, -total_l - 1, -1):
        bases.append(basis)
        vectors.append(vector.copy())
        if m == -total_l:
            break
        target = FockBasis(basis.system, basis.two_lz - 2)
        vector = angular_momentum_lowering(basis, target) @ vector
        expected_norm = np.sqrt((total_l + m) * (total_l - m + 1))
        vector /= expected_norm
        basis = target

    return rotation_equivariance_error(bases, vectors, total_l, axis=axis, angle=angle)


# ---------------------------------------------------------------------------
# Architectural projection-alignment diagnostic
# ---------------------------------------------------------------------------


def projection_alignment_quality(
    nqs,  # SO3EquivariantNQS
    parameters: np.ndarray,
) -> dict[int, float]:
    """Measure how naturally the raw MLP output aligns with the SO(3) sector.

    Returns ``{total_l: alignment_ratio}`` where each ratio is
    ``||P v_raw|| / ||v_raw||`` in [0, 1].  Higher values mean the
    CG-tensor-square architecture produces states already close to the
    correct symmetry sector, needing less correction from projection.

    This replaces the physically-incorrect "input rotation invariance"
    test — occupation numbers of a Fock state do not transform cleanly
    under single-particle rotations, so feature-level invariance is not
    the right diagnostic.  The projection-alignment metric directly
    measures what matters: how much the architecture helps the symmetry.
    """
    return {
        total_l: nqs.projection_alignment(parameters, total_l)
        for total_l in (0, 2)
    }
