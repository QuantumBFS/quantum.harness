"""Cross-sector hole and particle creation for the Rice-Mele-Hubbard model.

Applies c_{j↑} (hole) or c†_{j↑} (particle) to a state in the half-filling
sector, producing a state in the one-hole or one-particle sector via manual
bitwise basis-integer mapping with Jordan-Wigner fermionic signs.

QuSpin spinful basis encoding (uint32):
  bits  0 … L-1  → down-spin occupation
  bits  L … 2L-1 → up-spin occupation
"""

from __future__ import annotations

import numpy as np


def _state_to_up_down(state_int: int, L: int) -> tuple[int, int]:
    """Split a combined QuSpin basis integer into (up_state, down_state).

    QuSpin spinful basis encoding:
      bits 0..L-1   → down-spin occupation
      bits L..2L-1  → up-spin occupation

    basis.index(up_state, down_state) takes the two parts separately.
    """
    mask = (1 << L) - 1
    up = int(state_int >> L)
    down = int(state_int & mask)
    return up, down


def _basis_index(basis, state_int: int, L: int) -> int:
    """Look up the linear index of a combined basis state integer."""
    up, down = _state_to_up_down(state_int, L)
    return basis.index(up, down)


def d_pbc(j: int, j0: float, L: int) -> float:
    """Minimum distance on a periodic ring of length L."""
    d = abs(float(j) - j0)
    return min(d, L - d)


def create_hole(
    model_N,
    model_Nm1,
    psi_gs: np.ndarray,
    j: int,
) -> np.ndarray:
    """Apply c_{j↑} to |GS⟩, returning a state in the one-hole basis.

    Parameters
    ----------
    model_N : SplitRMHModel
        Half-filling model (source sector).
    model_Nm1 : SplitRMHModel
        One-hole model (target sector).
    psi_gs : np.ndarray, shape (dim_N,)
        Ground state vector in the half-filling basis.
    j : int
        Site index (0-indexed) where the hole is created.

    Returns
    -------
    psi_hole : np.ndarray, shape (dim_Nm1,)
        Normalized state vector in the one-hole basis.
    """
    L = model_N.L
    basis_N = model_N.basis
    basis_Nm1 = model_Nm1.basis
    dim_Nm1 = model_Nm1.dim

    states_N = basis_N.states  # (dim_N,), uint32
    up_bit_j = np.uint32(1 << (L + j))

    # Mask for up-spin bits at sites 0..j-1
    mask_left_up = np.uint32(((1 << j) - 1) << L)

    # Filter to states where up-spin bit at j is set
    has_up = (states_N & up_bit_j) != 0
    idx_has = np.where(has_up)[0]
    n_contrib = len(idx_has)

    if n_contrib == 0:
        raise RuntimeError(f"No basis states with up-spin at site {j}")

    # Jordan-Wigner signs
    left_popcount = np.array(
        [int((int(s) & int(mask_left_up)).bit_count()) & 1 for s in states_N[idx_has]],
        dtype=np.float64,
    )
    signs = np.where(left_popcount > 0, -1.0, 1.0)  # (-1)^{popcount}

    # Target integers: clear the up-spin bit at j
    target_ints = states_N[idx_has] ^ up_bit_j

    # Amplitudes
    amps = psi_gs[idx_has] * signs

    # Accumulate into target basis
    psi_hole = np.zeros(dim_Nm1, dtype=np.complex128)
    for idx_src, target_int, amp in zip(idx_has, target_ints, amps):
        if abs(amp) < 1e-30:
            continue
        idx_target = _basis_index(basis_Nm1, int(target_int), L)
        psi_hole[idx_target] += amp

    # Normalize
    norm = np.linalg.norm(psi_hole)
    if norm < 1e-30:
        raise RuntimeError(f"Hole state has zero norm at site {j}")
    psi_hole /= norm

    return psi_hole


def create_hole_wavepacket(
    model_N,
    model_Nm1,
    psi_gs: np.ndarray,
    j0: float | None = None,
    sigma: float = 1.2,
    k0: float = 0.0,
) -> np.ndarray:
    """Create a Gaussian hole wavepacket.

    |ψ_h⟩ ∝ Σ_j f_j e^{i k₀ (j - j₀)} c_{j↑} |GS⟩

    where f_j = exp(-d_PBC(j, j₀)² / (2σ²)).

    Parameters
    ----------
    model_N, model_Nm1 : SplitRMHModel
        Half-filling and one-hole models.
    psi_gs : np.ndarray, shape (dim_N,)
        Ground state in the half-filling sector.
    j0 : float or None
        Wavepacket center.  Defaults to L/2.
    sigma : float
        Gaussian width in site units.
    k0 : float
        Momentum offset (0 or π/2).

    Returns
    -------
    psi_wp : np.ndarray, shape (dim_Nm1,)
        Normalized wavepacket state.
    """
    L = model_N.L
    if j0 is None:
        j0 = float(L // 2)

    dim_Nm1 = model_Nm1.dim
    psi_wp = np.zeros(dim_Nm1, dtype=np.complex128)

    for j in range(L):
        d = d_pbc(j, j0, L)
        f_j = np.exp(-d ** 2 / (2.0 * sigma ** 2))
        phase = np.exp(1j * k0 * (j - j0))
        weight = f_j * phase

        if abs(weight) < 1e-30:
            continue

        psi_hole_j = create_hole(model_N, model_Nm1, psi_gs, j)
        psi_wp += weight * psi_hole_j

    # Normalize
    norm = np.linalg.norm(psi_wp)
    if norm < 1e-30:
        raise RuntimeError("Wavepacket has zero norm")
    psi_wp /= norm

    return psi_wp


# ---------------------------------------------------------------------------
# Particle creation (c†_{j↑})
# ---------------------------------------------------------------------------


def create_particle(
    model_N,
    model_Np1,
    psi_gs: np.ndarray,
    j: int,
) -> np.ndarray:
    """Apply c†_{j↑} to |GS⟩, returning a state in the one-particle basis.

    Parameters
    ----------
    model_N : SplitRMHModel
        Half-filling model (source sector).
    model_Np1 : SplitRMHModel
        One-particle model (target sector), N_up = L/2 + 1.
    psi_gs : np.ndarray, shape (dim_N,)
        Ground state vector in the half-filling basis.
    j : int
        Site index (0-indexed) where the particle is created.

    Returns
    -------
    psi_particle : np.ndarray, shape (dim_Np1,)
        Normalized state vector in the one-particle basis.
    """
    L = model_N.L
    basis_N = model_N.basis
    basis_Np1 = model_Np1.basis
    dim_Np1 = model_Np1.dim

    states_N = basis_N.states  # (dim_N,), uint32
    up_bit_j = np.uint32(1 << (L + j))

    # Mask for up-spin bits at sites 0..j-1
    mask_left_up = np.uint32(((1 << j) - 1) << L)

    # Filter to states where up-spin bit at j is CLEAR (empty)
    has_empty = (states_N & up_bit_j) == 0
    idx_has = np.where(has_empty)[0]
    n_contrib = len(idx_has)

    if n_contrib == 0:
        raise RuntimeError(f"No basis states with empty up-spin at site {j}")

    # Jordan-Wigner signs: same as hole — depends on fermions to the left
    left_popcount = np.array(
        [int((int(s) & int(mask_left_up)).bit_count()) & 1 for s in states_N[idx_has]],
        dtype=np.float64,
    )
    signs = np.where(left_popcount > 0, -1.0, 1.0)

    # Target integers: set the up-spin bit at j
    target_ints = states_N[idx_has] | up_bit_j

    # Amplitudes
    amps = psi_gs[idx_has] * signs

    # Accumulate into target basis
    psi_particle = np.zeros(dim_Np1, dtype=np.complex128)
    for idx_src, target_int, amp in zip(idx_has, target_ints, amps):
        if abs(amp) < 1e-30:
            continue
        idx_target = _basis_index(basis_Np1, int(target_int), L)
        psi_particle[idx_target] += amp

    # Normalize
    norm = np.linalg.norm(psi_particle)
    if norm < 1e-30:
        raise RuntimeError(f"Particle state has zero norm at site {j}")
    psi_particle /= norm

    return psi_particle


def create_particle_wavepacket(
    model_N,
    model_Np1,
    psi_gs: np.ndarray,
    j0: float | None = None,
    sigma: float = 1.2,
    k0: float = 0.0,
) -> np.ndarray:
    """Create a Gaussian particle wavepacket.

    |ψ_p⟩ ∝ Σ_j f_j e^{i k₀ (j - j₀)} c†_{j↑} |GS⟩

    where f_j = exp(-d_PBC(j, j₀)² / (2σ²)).

    Parameters
    ----------
    model_N, model_Np1 : SplitRMHModel
        Half-filling and one-particle models.
    psi_gs : np.ndarray, shape (dim_N,)
        Ground state in the half-filling sector.
    j0 : float or None
        Wavepacket center.  Defaults to L/2.
    sigma : float
        Gaussian width in site units.
    k0 : float
        Momentum offset (0 or π/2).

    Returns
    -------
    psi_wp : np.ndarray, shape (dim_Np1,)
        Normalized wavepacket state.
    """
    L = model_N.L
    if j0 is None:
        j0 = float(L // 2)

    dim_Np1 = model_Np1.dim
    psi_wp = np.zeros(dim_Np1, dtype=np.complex128)

    for j in range(L):
        d = d_pbc(j, j0, L)
        f_j = np.exp(-d ** 2 / (2.0 * sigma ** 2))
        phase = np.exp(1j * k0 * (j - j0))
        weight = f_j * phase

        if abs(weight) < 1e-30:
            continue

        psi_particle_j = create_particle(model_N, model_Np1, psi_gs, j)
        psi_wp += weight * psi_particle_j

    # Normalize
    norm = np.linalg.norm(psi_wp)
    if norm < 1e-30:
        raise RuntimeError("Wavepacket has zero norm")
    psi_wp /= norm

    return psi_wp
