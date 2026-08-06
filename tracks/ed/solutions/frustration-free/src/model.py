"""Canonical spinful Rice-Mele-Hubbard model and boundary current."""

from __future__ import annotations

from dataclasses import dataclass
from math import comb, isfinite
from numbers import Integral, Real

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian


def _real_parameter(name: str, value: object) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class ModelParameters:
    """Physical parameters for one fixed-sector pump calculation."""

    L: int = 6
    t: float = 1.0
    delta0: float = 0.9
    Delta0: float = 3.0
    delta_center: float = 0.0
    Delta_center: float = 0.0
    U: float = 0.0
    N_up: int | None = None
    N_down: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.L, Integral) or isinstance(self.L, bool) or self.L <= 0:
            raise ValueError("L must be a positive integer")
        if self.L % 2:
            raise ValueError("L must be even")

        n_up = self.L // 2 if self.N_up is None else self.N_up
        n_down = self.L // 2 if self.N_down is None else self.N_down
        for name, value in (("N_up", n_up), ("N_down", n_down)):
            if (
                not isinstance(value, Integral)
                or isinstance(value, bool)
                or not 0 <= value <= self.L
            ):
                raise ValueError(f"{name} must be an integer between 0 and L")
        object.__setattr__(self, "N_up", int(n_up))
        object.__setattr__(self, "N_down", int(n_down))

        for name in (
            "t",
            "delta0",
            "Delta0",
            "delta_center",
            "Delta_center",
            "U",
        ):
            object.__setattr__(self, name, _real_parameter(name, getattr(self, name)))


class RiceMeleHubbardModel:
    """One model and one shared many-body basis for all parameter-space points."""

    def __init__(self, parameters: ModelParameters) -> None:
        self.parameters = parameters
        self.basis = spinful_fermion_basis_1d(
            parameters.L,
            Nf=(parameters.N_up, parameters.N_down),
        )

    @property
    def L(self) -> int:
        return self.parameters.L

    def delta(self, phi: float) -> float:
        return self.parameters.delta_center + self.parameters.delta0 * np.cos(
            _real_parameter("phi", phi)
        )

    def Delta(self, phi: float) -> float:
        return self.parameters.Delta_center + self.parameters.Delta0 * np.sin(
            _real_parameter("phi", phi)
        )

    def hamiltonian(self, phi: float, theta: float):
        """Return H(phi, theta) on the model's shared basis."""
        return self.hamiltonian_from_terms(
            delta=self.delta(phi),
            Delta=self.Delta(phi),
            theta=theta,
        )

    def hamiltonian_from_terms(self, *, delta: float, Delta: float, theta: float):
        """Build H for explicit instantaneous Rice-Mele coefficients.

        Sites are zero based. The boundary hop `(L-1) -> 0` carries
        `exp(+i*theta)` and the reverse hop carries `exp(-i*theta)`.
        """
        delta = _real_parameter("delta", delta)
        Delta = _real_parameter("Delta", Delta)
        theta = _real_parameter("theta", theta)
        p = self.parameters

        up_hopping: list[list[complex | float | int]] = []
        down_hopping: list[list[complex | float | int]] = []
        for site in range(p.L - 1):
            coefficient = -(p.t + (-1) ** site * delta)
            terms = [
                [coefficient, site, site + 1],
                [coefficient, site + 1, site],
            ]
            up_hopping.extend(terms)
            down_hopping.extend(terms)

        boundary_hopping = p.t + (-1) ** (p.L - 1) * delta
        forward = -boundary_hopping * np.exp(1j * theta)
        backward = -boundary_hopping * np.exp(-1j * theta)
        boundary_terms = [
            [forward, p.L - 1, 0],
            [backward, 0, p.L - 1],
        ]
        up_hopping.extend(boundary_terms)
        down_hopping.extend(boundary_terms)

        onsite = [[Delta * (-1) ** site, site] for site in range(p.L)]
        static = [
            ["+-|", up_hopping],
            ["|+-", down_hopping],
            ["n|", onsite],
            ["|n", onsite],
        ]
        if p.U != 0.0:
            static.append(["n|n", [[p.U, site, site] for site in range(p.L)]])

        return hamiltonian(
            static,
            [],
            basis=self.basis,
            dtype=np.complex128,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )

    def current(self, phi: float, theta: float = 0.0):
        """Return the boundary charge current dH/dtheta."""
        theta = _real_parameter("theta", theta)
        boundary_hopping = (
            self.parameters.t
            + (-1) ** (self.L - 1) * self.delta(phi)
        )
        forward = -1j * boundary_hopping * np.exp(1j * theta)
        backward = 1j * boundary_hopping * np.exp(-1j * theta)
        terms = [
            [forward, self.L - 1, 0],
            [backward, 0, self.L - 1],
        ]
        return hamiltonian(
            [["+-|", terms], ["|+-", terms]],
            [],
            basis=self.basis,
            dtype=np.complex128,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )

    def hermiticity_error(self, *, phi: float, theta: float) -> float:
        matrix = self.hamiltonian(phi, theta).tocsr()
        antihermitian = matrix - matrix.getH()
        return float(np.max(np.abs(antihermitian.data))) if antihermitian.nnz else 0.0

    def validate_basis(self) -> None:
        expected = comb(self.L, self.parameters.N_up) * comb(
            self.L,
            self.parameters.N_down,
        )
        if self.basis.L != self.L or self.basis.Ns != expected:
            raise RuntimeError("basis is incompatible with the model sector")
