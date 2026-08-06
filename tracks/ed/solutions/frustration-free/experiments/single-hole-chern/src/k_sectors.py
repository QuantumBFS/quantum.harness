"""T_2 operator (2-site translation) and K-sector projection.

For the Rice-Mele-Hubbard model with 2-site unit cells, the 2-site
translation T_2 commutes with H: [H, T_2] = 0.  This module constructs
T_2 on the full Fock basis and builds projectors onto each K sector.

K values (L sites, 2-site unit cells → L/2 sectors):
    K = 4π·m / L   for m = 0, 1, ..., L/2 - 1

Projector construction via discrete Fourier transform:
    P_m = (1/N) Σ_{n=0}^{N-1} e^{-i·2πmn/N} T_2^n    (N = L/2)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix, eye, issparse


def _rotate_bits_left(x: int, shift: int, width: int) -> int:
    """Circular left-rotate the lowest `width` bits of `x` by `shift`."""
    mask = (1 << width) - 1
    x &= mask
    return ((x << shift) | (x >> (width - shift))) & mask


def _t2_on_fock_state(s: int, L: int) -> int:
    """Apply T_2 (translation by 2 sites) to spinful-fermion Fock integer.

    QuSpin convention for spinful_fermion_basis_1d:
      - bits 0 .. L-1     : down-spin occupations
      - bits L .. 2L-1    : up-spin occupations

    T_2 maps site j → (j+2) mod L for both spin species, which corresponds
    to a left-rotation by 2 of the L low bits and the L high bits.
    """
    low = _rotate_bits_left(s, 2, L)
    high = _rotate_bits_left(s >> L, 2, L)
    return low | (high << L)


def build_t2(basis) -> csr_matrix:
    """Build the 2-site translation operator T_2 on the given QuSpin basis.

    Parameters
    ----------
    basis : quspin.basis.spinful_fermion_basis_1d
        The full Fock basis for one (N_up, N_down) sector.

    Returns
    -------
    T2 : csr_matrix
        Sparse permutation matrix of shape (Ns, Ns).
    """
    L = basis.L
    Ns = basis.Ns

    # Precompute integer-to-index mapping
    int_to_idx = {int(s): i for i, s in enumerate(basis.states)}

    row_ind: list[int] = []
    col_ind: list[int] = []
    data: list[float] = []

    for i, s in enumerate(basis.states):
        t2_s = _t2_on_fock_state(int(s), L)
        j = int_to_idx[t2_s]
        row_ind.append(i)
        col_ind.append(j)
        data.append(1.0)

    return csr_matrix((data, (row_ind, col_ind)), shape=(Ns, Ns))


@dataclass(frozen=True)
class KSectorProjectors:
    """Projectors P_K onto each crystal-momentum K sector.

    Attributes
    ----------
    L : int
        Number of sites.
    N_cells : int
        Number of 2-site unit cells (= L/2).
    K_values : np.ndarray
        Crystal momenta K = 4π·m/L for m = 0..N_cells-1.
    projectors : dict[int, csr_matrix]
        P_K[m] for each K sector.  Each is a sparse CSR matrix (Ns, Ns).
        P_K projectors are Hermitian, idempotent, and sum to identity.
    sector_dims : dict[int, int]
        Dimension (number of basis states) in each K sector.
    """

    L: int
    N_cells: int
    K_values: np.ndarray
    projectors: dict[int, csr_matrix]
    sector_dims: dict[int, int]

    @property
    def Ns(self) -> int:
        first = next(iter(self.projectors.values()))
        return first.shape[0]

    def verify(self, tolerance: float = 1e-10) -> dict[str, float]:
        """Run numerical sanity checks on the projectors.

        Returns dict with error metrics:
          - 'max_off_diag':  max ||P_m @ P_n|| for m ≠ n   (should be ~0)
          - 'max_non_herm':  max ||P_m - P_m^†||            (should be ~0)
          - 'sum_deviation': ||Σ P_m - I||                   (should be ~0)
          - 'max_idempotent': max ||P_m^2 - P_m||            (should be ~0)
        """
        N_cells = self.N_cells
        metrics: dict[str, float] = {}

        # Orthogonality: P_m @ P_n for m ≠ n
        max_off = 0.0
        for m in range(N_cells):
            for n in range(m + 1, N_cells):
                prod = self.projectors[m] @ self.projectors[n]
                norm = float(np.linalg.norm(prod.todense() if issparse(prod) else prod, ord="fro"))
                if norm > max_off:
                    max_off = norm
        metrics["max_off_diag"] = max_off

        # Hermiticity
        max_herm = 0.0
        for m in range(N_cells):
            Pm = self.projectors[m]
            Pm_dense = Pm.todense() if issparse(Pm) else Pm
            diff = Pm_dense - Pm_dense.conj().T
            norm = float(np.linalg.norm(diff, ord="fro"))
            if norm > max_herm:
                max_herm = norm
        metrics["max_non_herm"] = max_herm

        # Completeness: Σ P_m = I
        total = sum(
            (self.projectors[m].todense() if issparse(self.projectors[m]) else self.projectors[m])
            for m in range(N_cells)
        )
        identity = np.eye(self.Ns)
        metrics["sum_deviation"] = float(np.linalg.norm(total - identity, ord="fro"))

        # Idempotence: P_m^2 = P_m
        max_idem = 0.0
        for m in range(N_cells):
            Pm = self.projectors[m]
            Pm_dense = Pm.todense() if issparse(Pm) else Pm
            prod = Pm_dense @ Pm_dense
            diff = prod - Pm_dense
            norm = float(np.linalg.norm(diff, ord="fro"))
            if norm > max_idem:
                max_idem = norm
        metrics["max_idempotent"] = max_idem

        return metrics


def build_k_projectors(basis) -> KSectorProjectors:
    """Construct K-sector projectors for the given QuSpin basis.

    Uses the discrete Fourier transform of T_2:
        P_m = (1/N) Σ_{n=0}^{N-1} e^{-i·2πmn/N} T_2^n

    Parameters
    ----------
    basis : quspin.basis.spinful_fermion_basis_1d
        Full Fock basis.

    Returns
    -------
    KSectorProjectors
        Contains K values, projectors, and sector dimensions.
    """
    L = basis.L
    Ns = basis.Ns
    N_cells = L // 2  # number of 2-site unit cells

    T2 = build_t2(basis)

    # Precompute powers of T_2
    # T2_powers[0] = I, T2_powers[n] = T_2^n
    T2_powers: list[csr_matrix] = [eye(Ns, format="csr")]
    for _ in range(1, N_cells):
        T2_powers.append(T2_powers[-1] @ T2)

    K_values = np.array([4.0 * np.pi * m / L for m in range(N_cells)])
    projectors: dict[int, csr_matrix] = {}
    sector_dims: dict[int, int] = {}

    for m in range(N_cells):
        P = csr_matrix((Ns, Ns), dtype=np.complex128)
        for n in range(N_cells):
            phase = np.exp(-2j * np.pi * m * n / N_cells)
            P += phase * T2_powers[n]
        P /= N_cells
        # Force Hermitian (should be exact up to floating point)
        P_dense = P.todense() if issparse(P) else P
        P_dense = 0.5 * (P_dense + P_dense.conj().T)
        projectors[m] = csr_matrix(P_dense)
        # Sector dimension = trace of projector (number of states in this sector)
        sector_dims[m] = int(round(float(np.trace(P_dense).real)))

    return KSectorProjectors(
        L=L,
        N_cells=N_cells,
        K_values=K_values,
        projectors=projectors,
        sector_dims=sector_dims,
    )


def project_hamiltonian(H_full: np.ndarray, P: csr_matrix) -> np.ndarray:
    """Project a dense Hamiltonian into a K sector.

    H_K = P^† @ H_full @ P   (dense, Hermitian)

    Parameters
    ----------
    H_full : np.ndarray
        Full Hamiltonian in the Fock basis, shape (Ns, Ns), dense.
    P : csr_matrix
        Projector onto K sector, shape (Ns, Ns).

    Returns
    -------
    H_K : np.ndarray
        Projected Hamiltonian in the K-sector subspace, shape (d_K, d_K).
        Only the non-zero block is returned (compressed).
    """
    P_dense = P.todense() if issparse(P) else np.asarray(P)
    # P @ H @ P: project on both sides
    HP = H_full @ P_dense
    HK_full = P_dense.conj().T @ HP

    # Compress: find the non-zero subspace
    # The projector has rank d_K; we find an orthonormal basis for its column space
    # via the eigendecomposition: P has eigenvalues 0 and 1, keep 1-eigenvectors.
    eigvals, eigvecs = np.linalg.eigh(P_dense)
    # Keep eigenvectors with eigenvalue ≈ 1
    mask = eigvals > 0.5
    basis_vecs = eigvecs[:, mask]  # shape (Ns, d_K)

    # Project H into this basis
    HK_reduced = basis_vecs.conj().T @ HK_full @ basis_vecs

    # Force Hermitian
    HK_reduced = 0.5 * (HK_reduced + HK_reduced.conj().T)

    return np.asarray(HK_reduced, dtype=np.float64)
