from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian


@dataclass(frozen=True, eq=False)
class RiceMeleModel:
    """Spinful Rice-Mele model in a fixed particle-number sector."""

    L: int
    t: float
    delta: float
    Delta: float
    theta: float
    N_up: int
    N_down: int
    basis: object = field(init=False, repr=False)
    hamiltonian: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._validate_parameters()
        object.__setattr__(
            self,
            "basis",
            spinful_fermion_basis_1d(
                self.L,
                Nf=(self.N_up, self.N_down),
            ),
        )
        object.__setattr__(self, "hamiltonian", self._build_hamiltonian())
        self.validate_hermiticity()

    def _validate_parameters(self) -> None:
        if not isinstance(self.L, Integral) or isinstance(self.L, bool) or self.L <= 0:
            raise ValueError("L must be a positive integer")
        for name, value in (("N_up", self.N_up), ("N_down", self.N_down)):
            if (
                not isinstance(value, Integral)
                or isinstance(value, bool)
                or not 0 <= value <= self.L
            ):
                raise ValueError(f"{name} must be an integer between 0 and L")
        for name, value in (
            ("t", self.t),
            ("delta", self.delta),
            ("Delta", self.Delta),
            ("theta", self.theta),
        ):
            if not isinstance(value, Real) or isinstance(value, bool):
                raise ValueError(f"{name} must be a real number")
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

    def _build_hamiltonian(self):
        up_hopping = []
        down_hopping = []
        for j in range(self.L - 1):
            coefficient = -(self.t + (-1) ** (j + 1) * self.delta)
            up_hopping.extend([[coefficient, j, j + 1], [coefficient, j + 1, j]])
            down_hopping.extend([[coefficient, j, j + 1], [coefficient, j + 1, j]])

        boundary_coefficient = -(self.t + (-1) ** self.L * self.delta)
        forward_boundary = boundary_coefficient * np.exp(1j * self.theta)
        backward_boundary = boundary_coefficient * np.exp(-1j * self.theta)
        up_hopping.extend(
            [[forward_boundary, self.L - 1, 0], [backward_boundary, 0, self.L - 1]]
        )
        down_hopping.extend(
            [[forward_boundary, self.L - 1, 0], [backward_boundary, 0, self.L - 1]]
        )

        onsite = [[self.Delta * (-1) ** (j + 1), j] for j in range(self.L)]
        static = [
            ["+-|", up_hopping],
            ["|+-", down_hopping],
            ["n|", onsite],
            ["|n", onsite],
        ]
        return hamiltonian(
            static,
            [],
            basis=self.basis,
            dtype=np.complex128,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )

    def hermiticity_error(self) -> float:
        matrix = self.hamiltonian.toarray()
        return float(np.max(np.abs(matrix - matrix.conj().T)))

    def validate_hermiticity(self, tolerance: float = 1e-12) -> None:
        error = self.hermiticity_error()
        if error >= tolerance:
            raise RuntimeError(f"Hamiltonian is not Hermitian: error={error:.3e}")

    def parameters(self) -> dict[str, int | float]:
        return {
            "L": self.L,
            "t": self.t,
            "delta": self.delta,
            "Delta": self.Delta,
            "theta": self.theta,
            "N_up": self.N_up,
            "N_down": self.N_down,
        }
