"""Pre-split Rice-Mele-Hubbard Hamiltonian: H(delta) = H0 + delta * Hdelta.

Both H0 and Hdelta are QuSpin hamiltonian objects built on the same basis,
enabling O(1) per-timestep Hamiltonian construction via operator arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real

import numpy as np
from quspin.operators import hamiltonian

from quspin.basis import spinful_fermion_basis_1d


def _make_sector_basis(L: int, N_up: int, N_down: int):
    """Thin wrapper around QuSpin spinful_fermion_basis_1d."""
    return spinful_fermion_basis_1d(L, Nf=(N_up, N_down))


@dataclass(frozen=True, eq=False)
class SplitRMHModel:
    """Rice-Mele-Hubbard model with H(delta) = H0 + delta * Hdelta.

    H(delta) = -Σ_{j,σ} [t + (-1)^j·δ] (c†_{jσ}c_{j+1,σ} + h.c.)
               + Δ Σ_{j,σ} (-1)^j n_{jσ}
               + U Σ_j n_{j↑} n_{j↓}

    The δ-independent part H0 contains t-hopping, staggered potential, and U.
    Hdelta contains only the dimerisation hopping coefficients.
    """

    L: int
    Delta: float
    U: float
    t: float = 1.0
    N_up: int = field(init=False)
    N_down: int = field(init=False)
    basis: object = field(init=False, repr=False)
    H0: object = field(init=False, repr=False)
    Hdelta: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._validate_parameters()
        n = self.L // 2
        object.__setattr__(self, "N_up", n)
        object.__setattr__(self, "N_down", n)
        object.__setattr__(self, "basis", _make_sector_basis(self.L, n, n))

        H0, Hdelta = self._build_split()
        object.__setattr__(self, "H0", H0)
        object.__setattr__(self, "Hdelta", Hdelta)

        # Hermiticity check: skip for L >= 8 (toarray() would OOM)
        if self.dim <= 5000:
            self.validate_hermiticity()

    def _validate_parameters(self) -> None:
        if not isinstance(self.L, Integral) or isinstance(self.L, bool) or self.L <= 0:
            raise ValueError("L must be a positive integer")
        if self.L % 2 != 0:
            raise ValueError(f"L must be even, got {self.L}")
        for name, value in [("Delta", self.Delta), ("U", self.U), ("t", self.t)]:
            if not isinstance(value, Real) or isinstance(value, bool):
                raise ValueError(f"{name} must be a real number")
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

    def _build_split(self) -> tuple:
        """Build (H0, Hdelta) as QuSpin hamiltonian objects.

        Hopping term:  coeff = -(t + (-1)^j * delta)
                          = -t  +  (-1)^{j+1} * delta
                          = H0_part + Hdelta_part * delta

        So:
          H0_part      = -t  for all bonds
          Hdelta_part  = (-1)^{j+1} = -(-1)^j  for all bonds
        """
        L = self.L
        t = self.t

        up_H0: list = []
        down_H0: list = []
        up_Hd: list = []
        down_Hd: list = []

        for j in range(L - 1):
            # H0: coeff = -t
            up_H0.extend([[-t, j, j + 1], [-t, j + 1, j]])
            down_H0.extend([[-t, j, j + 1], [-t, j + 1, j]])
            # Hdelta: coeff = -(-1)^j
            hd = -((-1) ** j)
            up_Hd.extend([[hd, j, j + 1], [hd, j + 1, j]])
            down_Hd.extend([[hd, j, j + 1], [hd, j + 1, j]])

        # boundary bond (L-1) <-> 0
        # For even L, (-1)^L = 1, (-1)^{L-1} = -1
        # H0: coeff = -t
        up_H0.extend([[-t, L - 1, 0], [-t, 0, L - 1]])
        down_H0.extend([[-t, L - 1, 0], [-t, 0, L - 1]])
        # Hdelta: coeff = -(-1)^{L-1} for j = L-1
        hd_b = -((-1) ** (L - 1))
        up_Hd.extend([[hd_b, L - 1, 0], [hd_b, 0, L - 1]])
        down_Hd.extend([[hd_b, L - 1, 0], [hd_b, 0, L - 1]])

        # staggered onsite: Delta * (-1)^j (both spins)
        onsite = [[self.Delta * ((-1) ** j), j] for j in range(L)]

        # H0 static terms
        H0_static: list = [
            ["+-|", up_H0],
            ["|+-", down_H0],
            ["n|", onsite],
            ["|n", onsite],
        ]
        if self.U != 0.0:
            H0_static.append(["n|n", [[self.U, j, j] for j in range(L)]])

        # Hdelta static terms (dimerisation hopping only)
        Hd_static: list = [
            ["+-|", up_Hd],
            ["|+-", down_Hd],
        ]

        H0 = hamiltonian(
            H0_static, [], basis=self.basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        Hdelta = hamiltonian(
            Hd_static, [], basis=self.basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        return H0, Hdelta

    def hamiltonian_at(self, delta: float) -> object:
        """Return QuSpin hamiltonian H(delta) = H0 + delta * Hdelta."""
        if delta == 0.0:
            return self.H0
        return self.H0 + delta * self.Hdelta

    def sparse_at(self, delta: float):
        """Return scipy CSR matrix H(delta) = H0_csr + delta * Hdelta_csr.

        Uses QuSpin's internal _static CSR matrices — avoids the .dot() bug.
        """
        if delta == 0.0:
            return self.H0._static.copy()
        return self.H0._static + delta * self.Hdelta._static

    def hermiticity_error(self) -> float:
        """Maximum Hermiticity error across H0 and Hdelta."""
        H0_d = self.H0.toarray()
        Hd_d = self.Hdelta.toarray()
        e0 = float(np.max(np.abs(H0_d - H0_d.conj().T)))
        ed = float(np.max(np.abs(Hd_d - Hd_d.conj().T)))
        return max(e0, ed)

    def validate_hermiticity(self, tolerance: float = 1e-12) -> None:
        err = self.hermiticity_error()
        if err >= tolerance:
            raise RuntimeError(f"Split H not Hermitian: error={err:.3e}")

    @property
    def dim(self) -> int:
        return self.basis.Ns
