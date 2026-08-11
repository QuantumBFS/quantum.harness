"""Non-Abelian Berry curvature, Chern number, and Wilson loop.

Extends the Abelian FHS method (compute_fhs in rice-mele-chern) to
multi-band subspaces using M×M overlap matrices and SVD-based unitary
link extraction.

Key references:
  - Fukui, Hatsugai, Suzuki, JPSJ 74, 1674 (2005)
  - pythtb documentation (non-Abelian Berry flux via SVD)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FHSDiagnostics:
    """Non-Abelian FHS result.

    Attributes
    ----------
    chern_raw : float
        Total Chern number = (1/2π) Σ Arg(det(Q)).
    chern_integer : int
        Rounded Chern number.
    integer_deviation : float
        |chern_raw - chern_integer| — quantization diagnostic.
    minimum_singular_value : float
        Smallest singular value across all overlap matrices (subspace
        isolation diagnostic — must be > 0 for well-defined topology).
    maximum_absolute_flux : float
        max|Arg(det(Q))| — must be < π for admissibility.
    berry_curvature : np.ndarray
        F(θ, φ), shape (N_0, N_1).
    wilson_phases : np.ndarray or None
        Wilson loop eigenphases ν_a(φ), shape (N_1, M) if computed.
    """

    chern_raw: float
    chern_integer: int
    integer_deviation: float
    minimum_singular_value: float
    maximum_absolute_flux: float
    berry_curvature: np.ndarray
    wilson_phases: np.ndarray | None = None


def subspace_overlap_matrix(
    states_a: np.ndarray,
    states_b: np.ndarray,
) -> np.ndarray:
    """Compute M×M overlap matrix between two sets of states.

    O_{ab} = ⟨ψ_a|φ_b⟩

    Parameters
    ----------
    states_a : np.ndarray, shape (M, Ns)
        M states at one grid point.
    states_b : np.ndarray, shape (M, Ns)
        M states at a neighboring grid point.

    Returns
    -------
    O : np.ndarray, shape (M, M)
        Overlap matrix, O[a, b] = ⟨ψ_a|φ_b⟩.
    """
    # states_a.conj() @ states_b.T: (M, Ns) @ (Ns, M) = (M, M)
    return states_a.conj() @ states_b.T


def _unitary_link(O: np.ndarray, svd_threshold: float = 1e-12) -> tuple[np.ndarray, float]:
    """Extract unitary factor from overlap matrix via SVD.

    O = V @ Σ @ W^†  →  U = V @ W^†   (unitary M×M)

    Returns (U, min_singular_value).
    """
    V, S, Wdag = np.linalg.svd(O, full_matrices=False)
    min_sv = float(np.min(S))
    if min_sv <= svd_threshold:
        raise ValueError(
            f"Overlap matrix singular value {min_sv:.3e} below threshold "
            f"{svd_threshold:.3e} — subspace isolation lost"
        )
    return V @ Wdag, min_sv


def compute_fhs_nonabelian(
    states: np.ndarray,
    svd_threshold: float = 1e-12,
    admissibility_margin: float = 1e-8,
    compute_wilson: bool = True,
) -> FHSDiagnostics:
    """Compute non-Abelian FHS Chern number on a 2D grid.

    Parameters
    ----------
    states : np.ndarray, shape (N_0, N_1, M, Ns)
        M eigenstates at each grid point. Axis 0 and 1 are the two
        torus directions (e.g., θ and φ for Approach A).
    svd_threshold : float
        Minimum allowed singular value of overlap matrices.
    admissibility_margin : float
        If any |Arg(det(Q))| ≥ π - margin, raise error (grid too coarse).
    compute_wilson : bool
        Whether to compute Wilson loop eigenphases along axis 1.

    Returns
    -------
    FHSDiagnostics
    """
    if states.ndim != 4:
        raise ValueError(
            f"states must have shape (N_0, N_1, M, Ns), got {states.shape}"
        )

    N0, N1, M, Ns = states.shape
    if M < 1:
        raise ValueError("M must be ≥ 1")

    # ---- Overlap matrices in both directions ----
    # Neighbors via roll (periodic boundary)
    states_0_neighbor = np.roll(states, -1, axis=0)  # (N0, N1, M, Ns)
    states_1_neighbor = np.roll(states, -1, axis=1)

    # Overlap matrices: O_mu[m,n,a,b] = ⟨ψ_a(m,n)|ψ_b(m+Δm, n+Δn)⟩
    # Shape: (N0, N1, M, M)
    O_0 = np.einsum("mnai,mnbi->mnab", states.conj(), states_0_neighbor)
    O_1 = np.einsum("mnai,mnbi->mnab", states.conj(), states_1_neighbor)

    # ---- Unitary link extraction via SVD ----
    U_0 = np.zeros((N0, N1, M, M), dtype=np.complex128)
    U_1 = np.zeros((N0, N1, M, M), dtype=np.complex128)
    min_sv = np.inf

    for m in range(N0):
        for n in range(N1):
            U, sv = _unitary_link(O_0[m, n], svd_threshold)
            U_0[m, n] = U
            min_sv = min(min_sv, sv)

            U, sv = _unitary_link(O_1[m, n], svd_threshold)
            U_1[m, n] = U
            min_sv = min(min_sv, sv)

    # ---- Non-Abelian plaquette ----
    # Q[m,n] = U_0[m,n] @ U_1[m+1,n] @ U_0[m,n+1]^† @ U_1[m,n]^†
    U_1_shifted = np.roll(U_1, -1, axis=0)  # U_1(m+1, n)
    U_0_shifted = np.roll(U_0, -1, axis=1)  # U_0(m, n+1)

    # For each (m,n), compute the M×M plaquette matrix
    Q = np.zeros((N0, N1, M, M), dtype=np.complex128)
    for m in range(N0):
        for n in range(N1):
            Q[m, n] = (
                U_0[m, n]
                @ U_1_shifted[m, n]
                @ U_0_shifted[m, n].conj().T
                @ U_1[m, n].conj().T
            )

    # ---- Berry curvature (determinant formulation) ----
    det_Q = np.linalg.det(Q)  # shape (N0, N1), complex
    flux = np.angle(det_Q)    # Arg(det(Q)) in (-π, π]

    max_abs_flux = float(np.max(np.abs(flux)))
    if max_abs_flux >= np.pi - admissibility_margin:
        raise ValueError(
            f"Plaquette flux {max_abs_flux:.6f} reaches principal-branch "
            f"boundary π — grid too coarse"
        )

    # ---- Chern number ----
    chern_raw = float(np.sum(flux) / (2.0 * np.pi))
    chern_int = round(chern_raw)

    # ---- Wilson loop (along axis 1) ----
    wilson_phases = None
    if compute_wilson:
        wilson_phases = compute_wilson_loop(U_1)  # shape (N1, M) — actually (N0, M)

    return FHSDiagnostics(
        chern_raw=chern_raw,
        chern_integer=chern_int,
        integer_deviation=abs(chern_raw - chern_int),
        minimum_singular_value=min_sv,
        maximum_absolute_flux=max_abs_flux,
        berry_curvature=flux,
        wilson_phases=wilson_phases,
    )


def compute_wilson_loop(
    U_1: np.ndarray,
) -> np.ndarray:
    """Compute Wilson loop eigenphases along axis 1 for each slice of axis 0.

    For each fixed axis-0 index m (e.g., fixed θ), computes:
        W(m) = U_1[m,0] @ U_1[m,1] @ ... @ U_1[m,N_1-1]
    and returns its eigenphases.

    Parameters
    ----------
    U_1 : np.ndarray, shape (N_0, N_1, M, M)
        Link matrices along axis 1.

    Returns
    -------
    phases : np.ndarray, shape (N_0, M)
        Wilson loop eigenphases ν_a in [0, 2π) for each axis-0 slice.
    """
    N0, N1, M, _ = U_1.shape
    phases = np.zeros((N0, M))

    for m in range(N0):
        W = np.eye(M, dtype=np.complex128)
        for n in range(N1):
            W = U_1[m, n] @ W
        eigvals = np.linalg.eigvals(W)
        phase = np.angle(eigvals)
        # Map to [0, 2π)
        phase = np.where(phase < 0, phase + 2 * np.pi, phase)
        phases[m] = np.sort(phase)

    return phases


def compute_zak_phase(
    states: np.ndarray,
) -> float:
    """Compute 1D Zak phase (Berry phase) along a closed loop.

    For a single band (M=1) along a 1D path of N points:
        γ = Arg(Π_{n=0}^{N-1} ⟨ψ_n|ψ_{n+1}⟩)

    For M > 1 bands (non-Abelian case):
        γ = Arg(det(Π_n O_n)) where O_n^{ab} = ⟨ψ_n^a|ψ_{n+1}^b⟩

    Parameters
    ----------
    states : np.ndarray, shape (N, M, Ns)
        M states at each of N points along a closed 1D loop.

    Returns
    -------
    gamma : float
        Zak phase in radians.
    """
    N, M, Ns = states.shape
    if N < 2:
        raise ValueError("Need at least 2 points for a loop")

    if M == 1:
        # Abelian: product of scalar overlaps
        product = 1.0 + 0j
        for n in range(N):
            psi_n = states[n, 0]
            psi_next = states[(n + 1) % N, 0]
            overlap = np.dot(psi_n.conj(), psi_next)
            product *= overlap / np.abs(overlap)
        return float(np.angle(product))
    else:
        # Non-Abelian: product of M×M overlap matrices
        W = np.eye(M, dtype=np.complex128)
        for n in range(N):
            O = subspace_overlap_matrix(states[n], states[(n + 1) % N])
            # Normalize each overlap to unitary (SVD)
            U, _ = _unitary_link(O)
            W = U @ W
        eigvals = np.linalg.eigvals(W)
        # Total Zak phase = sum of eigenphases = Arg(det(W))
        gamma = float(np.sum(np.angle(eigvals)))
        return gamma


def track_subspace(
    states_current: np.ndarray,
    states_candidate: np.ndarray,
    n_lowest: int = 5,
) -> np.ndarray:
    """Track low-energy subspace by maximizing overlap.

    When there are band crossings within the low-energy subspace, simple
    energy-ordering fails.  This function selects the M states from
    `states_candidate` (which has > M states, e.g., the lowest n_lowest)
    that have maximum overlap with `states_current`.

    Parameters
    ----------
    states_current : np.ndarray, shape (M, Ns)
        Reference M states at the current grid point.
    states_candidate : np.ndarray, shape (K, Ns)
        Candidate states at a neighboring grid point (K ≥ M).
    n_lowest : int
        How many of the lowest-energy candidate states to consider
        (default: same as M, but can be larger for better tracking).

    Returns
    -------
    tracked : np.ndarray, shape (M, Ns)
        The M states from candidates that best overlap with current.
    indices : np.ndarray, shape (M,)
        Indices of the selected states in the candidate array.
    """
    M = states_current.shape[0]
    K = states_candidate.shape[0]

    # Overlap matrix: O[a, b] = |⟨ψ_a^current|ψ_b^candidate⟩|
    O = np.abs(states_current.conj() @ states_candidate.T)  # (M, K)

    # Greedy matching: for each current state, find best candidate
    # Actually, we want to maximize total overlap. For M=1 this is trivial.
    # For M>1, use the "subspace overlap" = det of M×M submatrix?
    # Simpler: match each current state to its best candidate (greedy).
    # But this can assign multiple current states to the same candidate.
    # Better: use Hungarian algorithm, or simpler: for small M, enumerate.

    selected = []
    used = set()

    for a in range(M):
        # Find best unused candidate for this current state
        best_score = -1.0
        best_idx = -1
        for b in range(K):
            if b in used:
                continue
            if O[a, b] > best_score:
                best_score = O[a, b]
                best_idx = b
        if best_idx >= 0:
            selected.append(best_idx)
            used.add(best_idx)

    # If we didn't find M unique matches (degenerate case), fill remaining
    for b in range(K):
        if len(selected) >= M:
            break
        if b not in used:
            selected.append(b)
            used.add(b)

    selected = selected[:M]
    tracked = states_candidate[selected]
    indices = np.array(selected)

    return tracked, indices
