"""One-hole Rice-Mele-Hubbard model with boundary twist.

H(θ, φ) = -Σ_{j,σ} [1 + (-1)^j δ(φ)] (c†_{jσ} c_{j+1,σ} + h.c.)
          + Δ(φ) Σ_{j,σ} (-1)^j n_{jσ}
          + U Σ_j n_{j↑} n_{j↓}

Boundary: c_{L,σ} = e^{iθ} c_{0,σ} (twist θ on boundary bond).

One-hole sector: N_up = L/2 - 1, N_down = L/2  (S^z_tot = -1/2).

For L ≡ 0 (mod 4) → PBC at θ=0; L ≡ 2 (mod 4) → anti-PBC at θ=0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian

from .pump_path import pump_path


def _is_antiperiodic(L: int) -> bool:
    """Open-shell convention: L ≡ 2 (mod 4) → anti-PBC at zero twist."""
    return L % 4 == 2


@dataclass
class OneHoleRMHModel:
    """Rice-Mele-Hubbard model in the one-hole sector with boundary twist.

    Parameters
    ----------
    L : int
        Number of sites (must be even).
    U : float
        Hubbard interaction strength.
    t : float
        Bare hopping amplitude (default 1.0).
    """

    L: int
    U: float
    t: float = 1.0

    def __post_init__(self) -> None:
        if self.L % 2 != 0:
            raise ValueError(f"L must be even, got {self.L}")
        n_down = self.L // 2
        n_up = self.L // 2 - 1  # one-hole sector (up-spin hole)
        self._n_up = n_up
        self._n_down = n_down
        self._basis = spinful_fermion_basis_1d(self.L, Nf=(n_up, n_down))
        self._antiperiodic = _is_antiperiodic(self.L)

    @property
    def basis(self):
        return self._basis

    @property
    def dim(self) -> int:
        return self._basis.Ns

    @property
    def n_up(self) -> int:
        return self._n_up

    @property
    def n_down(self) -> int:
        return self._n_down

    @property
    def antiperiodic(self) -> bool:
        return self._antiperiodic

    def hamiltonian(self, theta: float, phi: float,
                    R_delta: float = 0.4,
                    Delta_offset: float = 5.0,
                    Delta_amp: float = 2.1) -> np.ndarray:
        """Build H(θ, φ) as a dense complex matrix.

        Parameters
        ----------
        theta : float
            Boundary twist angle (flux through the ring).
        phi : float
            Pump parameter.
        R_delta : float
            Dimerisation amplitude δ = R_δ cos φ.
        Delta_offset : float
            Staggered potential offset Δ = Δ_offset + Δ_amp sin φ.
        Delta_amp : float
            Staggered potential amplitude.

        Returns
        -------
        H : np.ndarray
            Dense Hamiltonian matrix, shape (dim, dim), complex128.
        """
        delta, Delta = pump_path(phi, R_delta, Delta_offset, Delta_amp)
        return self._build_dense(theta, delta, Delta)

    def _build_dense(self, theta: float, delta: float, Delta: float) -> np.ndarray:
        """Build dense H(θ; δ, Δ) using QuSpin sparse construction."""
        L = self.L
        anti = self._antiperiodic
        t = self.t
        U_val = self.U

        # Boundary phase factor
        boundary_phase = np.exp(1j * theta)
        if anti:
            boundary_phase *= -1.0  # e^{iπ} = -1 for anti-PBC

        up_hopping: list = []
        down_hopping: list = []

        # Bulk bonds j = 0 .. L-2
        for j in range(L - 1):
            coeff = -(t + ((-1) ** j) * delta)
            up_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])
            down_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])

        # Boundary bond (L-1) ↔ 0 with twist
        bdy_coeff = -(t + ((-1) ** (L - 1)) * delta)
        fwd = bdy_coeff * boundary_phase
        bwd = bdy_coeff * np.conj(boundary_phase)
        up_hopping.extend([[fwd, L - 1, 0], [bwd, 0, L - 1]])
        down_hopping.extend([[fwd, L - 1, 0], [bwd, 0, L - 1]])

        # Staggered potential: (-1)^j * n_{jσ}
        onsite = [[Delta * ((-1) ** j), j] for j in range(L)]

        static: list = [
            ["+-|", up_hopping],
            ["|+-", down_hopping],
            ["n|", onsite],
            ["|n", onsite],
        ]

        # Hubbard U term
        if U_val != 0.0:
            static.append(["n|n", [[U_val, j, j] for j in range(L)]])

        H_sparse = hamiltonian(
            static, [], basis=self._basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        return H_sparse.toarray()


def hermiticity_error(H: np.ndarray) -> float:
    """Return max|H - H^†| for diagnostics."""
    return float(np.max(np.abs(H - H.conj().T)))
