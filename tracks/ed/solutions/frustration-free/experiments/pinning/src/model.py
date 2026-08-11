"""Rice-Mele-Hubbard model with OBC and pinning potentials.

H(τ) = -Σ_{j,σ} [1 + (-1)^j δ(τ)] (c†_{jσ}c_{j+1,σ} + h.c.)    [OBC: j=0..L-2]
       + Δ(τ) Σ_{j,σ} (-1)^j n_{jσ}
       + U Σ_j n_{j↑} n_{j↓}
       + H_h^pin + H_s^pin

Pinning terms:
  H_h^pin = V_h * n_{j0}           (local potential — repels particles, attracts hole)
  H_s^pin = h_s * S^z_{j0}         (local Zeeman — pins spin defect)

Hamiltonian split for O(1) per-timestep construction:
  H(τ) = H_t + δ(τ)·H_δ + Δ(τ)·H_Δ + U·H_U + V_h·H_nj0 + h_s·H_szj0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian


@dataclass(frozen=True, eq=False)
class PinningRMHModel:
    """Rice-Mele-Hubbard model with OBC and pinning-potential pre-builds.

    Parameters
    ----------
    L : int
        Number of sites (must be even).
    U : float
        Hubbard interaction strength.
    j0 : int
        Pinning site (centre of the chain).
    t : float
        Bare hopping amplitude (default 1.0).
    N_up : int or None
        Number of up-spin fermions.  Default: (L-2)//2 (one-hole sector).
    N_down : int or None
        Number of down-spin fermions.  Default: L//2.
    """

    L: int
    U: float
    j0: int = 4
    t: float = 1.0
    N_up: int | None = None
    N_down: int | None = None
    basis: object = field(init=False, repr=False)
    H_t: object = field(init=False, repr=False)
    H_delta: object = field(init=False, repr=False)
    H_Delta: object = field(init=False, repr=False)
    H_U: object = field(init=False, repr=False)
    H_nj0: object = field(init=False, repr=False)   # n_{j0} (coeff 1.0)
    H_szj0: object = field(init=False, repr=False)  # S^z_{j0} (coeff 1.0)

    def __post_init__(self) -> None:
        self._validate_parameters()
        n_up = int(self.N_up) if self.N_up is not None else (self.L - 2) // 2
        n_down = int(self.N_down) if self.N_down is not None else self.L // 2
        object.__setattr__(self, "N_up", n_up)
        object.__setattr__(self, "N_down", n_down)
        object.__setattr__(
            self, "basis",
            spinful_fermion_basis_1d(self.L, Nf=(n_up, n_down)),
        )
        Ht, Hd, HD, HU, Hnj0, Hszj0 = self._build_all()
        object.__setattr__(self, "H_t", Ht)
        object.__setattr__(self, "H_delta", Hd)
        object.__setattr__(self, "H_Delta", HD)
        object.__setattr__(self, "H_U", HU)
        object.__setattr__(self, "H_nj0", Hnj0)
        object.__setattr__(self, "H_szj0", Hszj0)
        if self.dim <= 5000:
            self._validate_hermiticity()

    def _validate_parameters(self) -> None:
        if not isinstance(self.L, Integral) or isinstance(self.L, bool) or self.L <= 0:
            raise ValueError("L must be a positive integer")
        if self.L % 2 != 0:
            raise ValueError(f"L must be even, got {self.L}")
        if not (0 <= self.j0 < self.L):
            raise ValueError(f"j0={self.j0} out of range [0, {self.L})")
        for name, value in [("U", self.U), ("t", self.t)]:
            if not isinstance(value, Real) or isinstance(value, bool):
                raise ValueError(f"{name} must be a real number")
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        for name, value in [("N_up", self.N_up), ("N_down", self.N_down)]:
            if value is not None:
                if not isinstance(value, Integral) or isinstance(value, bool):
                    raise ValueError(f"{name} must be an integer or None")
                if value < 0 or value > self.L:
                    raise ValueError(f"{name}={value} out of range [0, {self.L}]")

    @property
    def dim(self) -> int:
        return self.basis.Ns

    @property
    def hole_density(self) -> float:
        """Total hole count = L - (N_up + N_down). Should be 1."""
        return float(self.L - self.N_up - self.N_down)

    @property
    def sz_total(self) -> float:
        """Total S^z = (N_up - N_down)/2."""
        return float(self.N_up - self.N_down) / 2.0

    def _build_all(self) -> tuple:
        """Build (H_t, H_δ, H_Δ, H_U, H_nj0, H_szj0)."""
        L = self.L
        j0 = self.j0

        up_Ht: list = []
        down_Ht: list = []
        up_Hd: list = []
        down_Hd: list = []

        # OBC: bulk bonds only (j = 0 .. L-2), no boundary bond
        for j in range(L - 1):
            up_Ht.extend([[-1.0, j, j + 1], [-1.0, j + 1, j]])
            down_Ht.extend([[-1.0, j, j + 1], [-1.0, j + 1, j]])
            hd = -((-1) ** j)  # = (-1)^{j+1}
            up_Hd.extend([[hd, j, j + 1], [hd, j + 1, j]])
            down_Hd.extend([[hd, j, j + 1], [hd, j + 1, j]])

        # staggered potential: (-1)^j * n_{jσ}
        onsite = [[(-1) ** j, j] for j in range(L)]

        kw = dict(basis=self.basis, dtype=np.complex128,
                  check_herm=False, check_symm=False, check_pcon=False)

        Ht = hamiltonian([["+-|", up_Ht], ["|+-", down_Ht]], [], **kw)
        Hd = hamiltonian([["+-|", up_Hd], ["|+-", down_Hd]], [], **kw)

        kw_float = dict(basis=self.basis, dtype=np.float64,
                        check_herm=False, check_symm=False, check_pcon=False)
        HD = hamiltonian([["n|", onsite], ["|n", onsite]], [], **kw_float)
        HU = hamiltonian(
            [["n|n", [[1.0, j, j] for j in range(L)]]], [], **kw_float,
        )

        # pinning operators (coefficient 1.0, scaled at assembly time)
        # H_nj0: n_{j0} = n_{j0,↑} + n_{j0,↓}
        Hnj0 = hamiltonian(
            [["n|", [[1.0, j0]]], ["|n", [[1.0, j0]]]], [], **kw_float,
        )
        # H_szj0: S^z_{j0} = (n_{j0,↑} - n_{j0,↓})/2
        Hszj0 = hamiltonian(
            [["n|", [[0.5, j0]]], ["|n", [[-0.5, j0]]]], [], **kw_float,
        )

        return Ht, Hd, HD, HU, Hnj0, Hszj0

    def hamiltonian_at(self, delta: float, Delta: float,
                       V_h: float = 0.0, h_s: float = 0.0):
        """Return scipy CSR matrix H(τ) = sum of all components."""
        H = (self.H_t._static.copy().astype(np.complex128)
             + delta * self.H_delta._static
             + Delta * self.H_Delta._static
             + self.U * self.H_U._static)
        if V_h != 0.0:
            H += V_h * self.H_nj0._static
        if h_s != 0.0:
            H += h_s * self.H_szj0._static
        return H

    def _validate_hermiticity(self, tolerance: float = 1e-12) -> None:
        for name, op in [("H_t", self.H_t), ("H_delta", self.H_delta),
                          ("H_Delta", self.H_Delta), ("H_U", self.H_U),
                          ("H_nj0", self.H_nj0), ("H_szj0", self.H_szj0)]:
            M = op.toarray()
            err = float(np.max(np.abs(M - M.conj().T)))
            if err >= tolerance:
                raise RuntimeError(f"{name} not Hermitian: error={err:.3e}")
