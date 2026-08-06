"""Low-energy spectrum on the (K, φ) grid.

Strategy: Diagonalize H(θ=0, φ) in the FULL Fock basis, then assign
crystal momentum K = -i ln⟨T_2⟩ to each eigenstate via the T_2 operator.
Group states by K sector and keep the lowest M per sector.

This avoids the complexity of expanding K-sector-projected eigenvectors
back to the full basis, and gives us eigenstates directly in a common
basis for overlap/Topology computations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.sparse import csr_matrix

from .k_sectors import KSectorProjectors
from .model import OneHoleRMHModel, hermiticity_error


@dataclass
class SpectrumResult:
    """K-resolved low-energy spectrum.

    Attributes
    ----------
    L, U, R_delta : model parameters
    N_K, N_phi : grid dimensions
    M : number of eigenvalues kept per (K, φ)
    K_values, phi_values : grid coordinates
    energies : E_α(K, φ), shape (N_K, N_phi, M)
    eigenstates : full-basis eigenvectors, shape (N_K, N_phi, M, Ns)
    isolation_gaps : Δ_iso = E_{M+1} - E_M, shape (N_K, N_phi)
    t2_expectations : ⟨T_2⟩ for diagnostic, shape (N_K, N_phi, M)
    hermiticity_errors : max|H - H^†| per grid point
    wall_time_s
    """

    L: int
    U: float
    R_delta: float
    N_K: int
    N_phi: int
    M: int
    K_values: np.ndarray
    phi_values: np.ndarray
    energies: np.ndarray
    eigenstates: np.ndarray
    isolation_gaps: np.ndarray
    t2_expectations: np.ndarray
    hermiticity_errors: np.ndarray
    wall_time_s: float
    sector_dims: dict = field(default_factory=dict)


def _assign_k_sector(
    t2_expectation: complex,
    K_values: np.ndarray,
    tolerance: float = 1e-8,
) -> int:
    """Assign K-sector index based on ⟨T_2⟩ expectation value.

    Returns the index of the closest K value, or -1 if no match within tolerance.
    """
    phase = np.angle(t2_expectation)
    # Normalize to [0, 2π)
    if phase < 0:
        phase += 2 * np.pi

    # Find closest K value
    diffs = np.abs(np.angle(np.exp(1j * (K_values - phase))))
    idx = int(np.argmin(diffs))
    if diffs[idx] < tolerance:
        return idx
    return -1


def compute_k_resolved_spectrum(
    model: OneHoleRMHModel,
    projectors: KSectorProjectors,
    N_phi: int = 12,
    M: int = 10,
    R_delta: float = 0.4,
    Delta_offset: float = 5.0,
    Delta_amp: float = 2.1,
) -> SpectrumResult:
    """Compute low-energy spectrum on (K, φ) grid.

    For each φ, diagonalizes H(θ=0, φ) fully, assigns K to each eigenstate
    via ⟨ψ|T_2|ψ⟩, then groups by K sector and keeps the lowest M states.

    Parameters
    ----------
    model : OneHoleRMHModel
        Pre-built model in one-hole sector.
    projectors : KSectorProjectors
        Contains T_2-based projectors and K_values.
    N_phi : int
        Number of φ grid points.
    M : int
        Number of eigenvalues to keep per (K, φ).
    R_delta : float
        Dimerisation amplitude.
    Delta_offset, Delta_amp : float
        Staggered potential parameters.

    Returns
    -------
    SpectrumResult
    """
    t0 = time.perf_counter()
    L = model.L
    N_K = projectors.N_cells
    K_values = projectors.K_values.copy()
    phi_values = np.linspace(0, 2 * np.pi, N_phi, endpoint=False)
    Ns = model.dim

    energies = np.full((N_K, N_phi, M), np.nan)
    eigenstates_arr = np.zeros((N_K, N_phi, M, Ns), dtype=np.complex128)
    isolation_gaps = np.full((N_K, N_phi), np.nan)
    t2_expectations = np.full((N_K, N_phi, M), np.nan + 1j * np.nan)
    hermiticity_errors = np.full((N_K, N_phi), np.nan)

    # Build T_2 as dense matrix for expectation value computation
    from .k_sectors import build_t2
    T2_sparse = build_t2(model.basis)
    T2_dense = np.asarray(T2_sparse.todense())

    # Count states per K sector (for consistency check)
    sector_counts = {m: 0 for m in range(N_K)}

    for ip, phi in enumerate(phi_values):
        # Build full Hamiltonian at θ = 0
        H_full = model.hamiltonian(
            theta=0.0, phi=phi,
            R_delta=R_delta, Delta_offset=Delta_offset, Delta_amp=Delta_amp,
        )

        herm_err = hermiticity_error(H_full)
        if herm_err >= 1e-10:
            raise RuntimeError(
                f"H not Hermitian at φ={phi:.4f}: error={herm_err:.3e}"
            )

        # Full diagonalization
        evals, evecs = np.linalg.eigh(H_full)

        # Assign K to each eigenstate and group
        # For each eigenstate, compute ⟨T_2⟩
        sector_states: dict[int, list[tuple[float, np.ndarray, complex]]] = {
            m: [] for m in range(N_K)
        }

        for alpha in range(len(evals)):
            psi = evecs[:, alpha]
            t2_exp = complex(np.dot(np.conj(psi), T2_dense @ psi))
            # Convert to complex phase
            # T_2 is unitary, so |t2_exp| ≈ 1 for pure K states
            ks = _assign_k_sector(t2_exp, K_values)
            if ks >= 0:
                sector_states[ks].append((evals[alpha], psi.copy(), t2_exp))
            # States that don't match any K (shouldn't happen) are dropped

        # For each K sector, sort by energy and keep lowest M
        for ik in range(N_K):
            states = sector_states[ik]
            if not states:
                continue
            states.sort(key=lambda x: x[0])  # sort by energy
            n_keep = min(M, len(states))
            sector_counts[ik] = len(states)

            for alpha in range(n_keep):
                e, psi, t2 = states[alpha]
                energies[ik, ip, alpha] = e
                eigenstates_arr[ik, ip, alpha] = psi
                t2_expectations[ik, ip, alpha] = t2

            # Isolation gap: E_M - E_{M-1}
            if len(states) > M:
                isolation_gaps[ik, ip] = states[M][0] - states[M - 1][0]

        hermiticity_errors[ik, ip] = herm_err  # same for all K at this φ

        # Quick progress indicator
        if (ip + 1) % 4 == 0:
            pass  # quiet

    wall_t = time.perf_counter() - t0

    return SpectrumResult(
        L=L,
        U=model.U,
        R_delta=R_delta,
        N_K=N_K,
        N_phi=N_phi,
        M=M,
        K_values=K_values,
        phi_values=phi_values,
        energies=energies,
        eigenstates=eigenstates_arr,
        isolation_gaps=isolation_gaps,
        t2_expectations=t2_expectations,
        hermiticity_errors=hermiticity_errors,
        wall_time_s=wall_t,
        sector_dims=sector_counts,
    )
