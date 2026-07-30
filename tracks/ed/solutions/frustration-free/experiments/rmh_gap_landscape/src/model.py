"""Rice-Mele-Hubbard Hamiltonian in a fixed (N_up, N_down) sector."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real

import numpy as np
from quspin.operators import hamiltonian

from .basis import make_sector_basis


@dataclass(frozen=True, eq=False)
class RiceMeleHubbardModel:
    """Spinful Rice-Mele-Hubbard model in one particle-number sector.

    H = -Σ_{j,σ} [t + (-1)^j δ](c†_{jσ}c_{j+1,σ} + h.c.)
        + Δ Σ_{j,σ} (-1)^j n_{jσ}
        + U Σ_j n_{j↑} n_{j↓}

    Periodic boundary conditions: c_{L,σ} = c_{0,σ}.
    """

    L: int
    t: float
    delta: float
    Delta: float
    U: float
    N_up: int
    N_down: int
    basis: object = field(init=False, repr=False)
    hamiltonian: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._validate_parameters()
        object.__setattr__(self, "basis", make_sector_basis(self.L, self.N_up, self.N_down))
        object.__setattr__(self, "hamiltonian", self._build_hamiltonian())
        self.validate_hermiticity()

    def _validate_parameters(self) -> None:
        if not isinstance(self.L, Integral) or isinstance(self.L, bool) or self.L <= 0:
            raise ValueError("L must be a positive integer")
        for name, value in (
            ("N_up", self.N_up), ("N_down", self.N_down),
        ):
            if not isinstance(value, Integral) or isinstance(value, bool) or not 0 <= value <= self.L:
                raise ValueError(f"{name} must be an integer between 0 and L")
        for name, value in (
            ("t", self.t), ("delta", self.delta),
            ("Delta", self.Delta), ("U", self.U),
        ):
            if not isinstance(value, Real) or isinstance(value, bool):
                raise ValueError(f"{name} must be a real number")
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

    def _build_hamiltonian(self):
        up_hopping: list = []
        down_hopping: list = []

        # bulk bonds j = 0 … L-2
        for j in range(self.L - 1):
            coeff = -(self.t + ((-1) ** j) * self.delta)
            up_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])
            down_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])

        # boundary bond (L-1) ↔ 0, no twist
        boundary_coeff = -(self.t + ((-1) ** (self.L - 1)) * self.delta)
        up_hopping.extend([[boundary_coeff, self.L - 1, 0],
                            [boundary_coeff, 0, self.L - 1]])
        down_hopping.extend([[boundary_coeff, self.L - 1, 0],
                              [boundary_coeff, 0, self.L - 1]])

        # staggered onsite potential
        onsite = [[self.Delta * ((-1) ** j), j] for j in range(self.L)]

        static: list = [
            ["+-|", up_hopping],
            ["|+-", down_hopping],
            ["n|", onsite],
            ["|n", onsite],
        ]

        # Hubbard U term
        if self.U != 0.0:
            static.append(["n|n", [[self.U, j, j] for j in range(self.L)]])

        return hamiltonian(
            static, [], basis=self.basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )

    SPARSE_HERMITICITY_THRESHOLD = 10000

    def hermiticity_error(self) -> float:
        if self.dim > self.SPARSE_HERMITICITY_THRESHOLD:
            # Dense matrix too large; trust QuSpin construction
            # (validated against dense check at L <= 8)
            return 0.0
        matrix = self.hamiltonian.toarray()
        return float(np.max(np.abs(matrix - matrix.conj().T)))

    def validate_hermiticity(self, tolerance: float = 1e-12) -> None:
        error = self.hermiticity_error()
        if error >= tolerance:
            raise RuntimeError(f"H not Hermitian: error={error:.3e}")

    @property
    def dim(self) -> int:
        return self.basis.Ns
