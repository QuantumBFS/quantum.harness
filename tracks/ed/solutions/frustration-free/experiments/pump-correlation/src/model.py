"""Split Rice-Mele-Hubbard model with open-shell boundary conditions.

H(τ) = -Σ_{j,σ} [1 + (-1)^j δ(τ)] (c†_{jσ}c_{j+1,σ} + h.c.)
       + Δ(τ) Σ_{j,σ} (-1)^j n_{jσ}
       + U Σ_j n_{j↑} n_{j↓}

Open-shell convention (arXiv:2308.03756v2):
  L ≡ 0 (mod 4): PBC  (L=8,12)
  L ≡ 2 (mod 4): anti-PBC (L=6,10,14)

Hamiltonian split for O(1) per-timestep construction:
  H(τ) = H_t + δ(τ)·H_δ + Δ(τ)·H_Δ + U·H_U
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian


def _is_antiperiodic(L: int) -> bool:
    """Open-shell convention: L ≡ 2 mod 4 → anti-PBC."""
    return L % 4 == 2


@dataclass(frozen=True, eq=False)
class SplitRMHModel:
    """Rice-Mele-Hubbard model split into four sparse (CSR) components.

    Parameters
    ----------
    L : int
        Number of sites (must be even).
    U : float
        Hubbard interaction strength.
    t : float
        Bare hopping amplitude (default 1.0).
    N_up : int or None
        Number of up-spin fermions.  Defaults to L//2 (half-filling).
    N_down : int or None
        Number of down-spin fermions.  Defaults to L//2 (half-filling).
    """

    L: int
    U: float
    t: float = 1.0
    N_up: int | None = None
    N_down: int | None = None
    basis: object = field(init=False, repr=False)
    H_t: object = field(init=False, repr=False)   # bare hopping
    H_delta: object = field(init=False, repr=False)  # dimerisation × δ
    H_Delta: object = field(init=False, repr=False)  # staggered potential × Δ
    H_U: object = field(init=False, repr=False)     # Hubbard interaction × U
    _antiperiodic: bool = field(init=False)

    def __post_init__(self) -> None:
        self._validate_parameters()
        n_up = int(self.N_up) if self.N_up is not None else self.L // 2
        n_down = int(self.N_down) if self.N_down is not None else self.L // 2
        object.__setattr__(self, "N_up", n_up)
        object.__setattr__(self, "N_down", n_down)
        anti = _is_antiperiodic(self.L)
        object.__setattr__(self, "_antiperiodic", anti)
        object.__setattr__(
            self, "basis",
            spinful_fermion_basis_1d(self.L, Nf=(n_up, n_down)),
        )
        Ht, Hd, HD, HU = self._build_all()
        object.__setattr__(self, "H_t", Ht)
        object.__setattr__(self, "H_delta", Hd)
        object.__setattr__(self, "H_Delta", HD)
        object.__setattr__(self, "H_U", HU)
        if self.dim <= 5000:
            self._validate_hermiticity()

    def _validate_parameters(self) -> None:
        if not isinstance(self.L, Integral) or isinstance(self.L, bool) or self.L <= 0:
            raise ValueError("L must be a positive integer")
        if self.L % 2 != 0:
            raise ValueError(f"L must be even, got {self.L}")
        for name, value in [("U", self.U), ("t", self.t)]:
            if not isinstance(value, Real) or isinstance(value, bool):
                raise ValueError(f"{name} must be a real number")
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        for name, value in [("N_up", self.N_up), ("N_down", self.N_down)]:
            if value is not None:
                if not isinstance(value, Integral) or isinstance(value, bool):
                    raise ValueError(f"{name} must be an integer or None, got {type(value)}")
                if value < 0 or value > self.L:
                    raise ValueError(f"{name}={value} out of range [0, {self.L}]")

    @property
    def dim(self) -> int:
        return self.basis.Ns

    @property
    def antiperiodic(self) -> bool:
        return self._antiperiodic

    def _build_all(self) -> tuple:
        """Build (H_t, H_δ, H_Δ, H_U) as QuSpin hamiltonian objects.

        Hopping decomposition:
          coeff = -(1 + (-1)^j δ) = -1 + (-1)^{j+1} δ
        So H_t uses coefficient -1, H_δ uses coefficient (-1)^{j+1}.

        Boundary: PBC uses same coefficients; anti-PBC multiplies by e^{iπ} = -1.
        """
        L = self.L
        anti = self._antiperiodic
        boundary_sign = -1.0 if anti else 1.0

        up_Ht: list = []
        down_Ht: list = []
        up_Hd: list = []
        down_Hd: list = []

        # bulk bonds
        for j in range(L - 1):
            up_Ht.extend([[-1.0, j, j + 1], [-1.0, j + 1, j]])
            down_Ht.extend([[-1.0, j, j + 1], [-1.0, j + 1, j]])
            hd = -((-1) ** j)  # = (-1)^{j+1}
            up_Hd.extend([[hd, j, j + 1], [hd, j + 1, j]])
            down_Hd.extend([[hd, j, j + 1], [hd, j + 1, j]])

        # boundary bond (L-1) ↔ 0
        bt = -1.0 * boundary_sign
        up_Ht.extend([[bt, L - 1, 0], [bt, 0, L - 1]])
        down_Ht.extend([[bt, L - 1, 0], [bt, 0, L - 1]])
        hd_b = -((-1) ** (L - 1)) * boundary_sign
        up_Hd.extend([[hd_b, L - 1, 0], [hd_b, 0, L - 1]])
        down_Hd.extend([[hd_b, L - 1, 0], [hd_b, 0, L - 1]])

        # staggered potential: (-1)^j * n_{jσ}
        onsite = [[(-1) ** j, j] for j in range(L)]

        # H_t: bare hopping only
        Ht = hamiltonian(
            [["+-|", up_Ht], ["|+-", down_Ht]],
            [], basis=self.basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        # H_δ: dimerisation hopping only
        Hd = hamiltonian(
            [["+-|", up_Hd], ["|+-", down_Hd]],
            [], basis=self.basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        # H_Δ: staggered potential only
        HD = hamiltonian(
            [["n|", onsite], ["|n", onsite]],
            [], basis=self.basis, dtype=np.float64,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        # H_U: Hubbard interaction only
        HU = hamiltonian(
            [["n|n", [[1.0, j, j] for j in range(L)]]],
            [], basis=self.basis, dtype=np.float64,
            check_herm=False, check_symm=False, check_pcon=False,
        )
        return Ht, Hd, HD, HU

    def hamiltonian_at(self, delta: float, Delta: float):
        """Return scipy CSR matrix H(τ) = H_t + δ·H_δ + Δ·H_Δ + U·H_U."""
        H = (self.H_t._static.copy().astype(np.complex128)
             + delta * self.H_delta._static
             + Delta * self.H_Delta._static
             + self.U * self.H_U._static)
        return H

    def _validate_hermiticity(self, tolerance: float = 1e-12) -> None:
        """Check hermiticity of H_t, H_δ, H_Δ, H_U (small dim only)."""
        for name, op in [("H_t", self.H_t), ("H_delta", self.H_delta),
                          ("H_Delta", self.H_Delta), ("H_U", self.H_U)]:
            M = op.toarray()
            err = float(np.max(np.abs(M - M.conj().T)))
            if err >= tolerance:
                raise RuntimeError(f"{name} not Hermitian: error={err:.3e}")
