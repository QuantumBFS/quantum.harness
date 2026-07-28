from __future__ import annotations

from dataclasses import dataclass
import math

import autoray as ar

from .contract import BoundaryContractor, ThermodynamicPoint
from .pepo import FinitePEPO


@dataclass(frozen=True)
class ThermodynamicTolerances:
    z: float
    u: float
    contraction_noise: float

    def __post_init__(self) -> None:
        values = (self.z, self.u, self.contraction_noise)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("thermodynamic tolerances must be finite and positive")
        if self.z <= self.contraction_noise or self.u <= self.contraction_noise:
            raise ValueError("thermodynamic tolerances must exceed contraction noise")


@dataclass(frozen=True)
class ThermodynamicWeights:
    z: float
    u: float
    hermiticity: float

    def __post_init__(self) -> None:
        values = (self.z, self.u, self.hermiticity)
        if not all(math.isfinite(value) and value >= 0 for value in values):
            raise ValueError("thermodynamic weights must be finite and non-negative")


@dataclass(frozen=True)
class CompressionDiagnostics:
    total: object
    frobenius: object
    z_penalty: object
    u_penalty: object
    hermiticity_penalty: object
    z_difference: object
    u_difference: object

    def as_floats(self) -> "CompressionDiagnostics":
        def convert(value: object) -> float:
            return float(ar.do("real", value))

        return CompressionDiagnostics(
            total=convert(self.total),
            frobenius=convert(self.frobenius),
            z_penalty=convert(self.z_penalty),
            u_penalty=convert(self.u_penalty),
            hermiticity_penalty=convert(self.hermiticity_penalty),
            z_difference=convert(self.z_difference),
            u_difference=convert(self.u_difference),
        )


class CompressionObjective:
    def __init__(
        self,
        contractor: BoundaryContractor,
        j: float,
        h: float,
        tolerances: ThermodynamicTolerances,
        weights: ThermodynamicWeights,
    ) -> None:
        if not math.isfinite(j) or not math.isfinite(h):
            raise ValueError("Hamiltonian couplings must be finite")
        self.contractor = contractor
        self.j = j
        self.h = h
        self.tolerances = tolerances
        self.weights = weights

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in {"ordinary", "thermodynamic"}:
            raise ValueError("mode must be 'ordinary' or 'thermodynamic'")

    def teacher_point(self, teacher: FinitePEPO) -> ThermodynamicPoint:
        return self.contractor.thermodynamic_point(
            teacher,
            j=self.j,
            h=self.h,
            log_scale=0.0,
        )

    def loss(
        self,
        student: FinitePEPO,
        teacher: FinitePEPO,
        *,
        teacher_point: ThermodynamicPoint,
        mode: str,
    ):
        self._validate_mode(mode)
        frobenius = self.contractor.relative_frobenius_loss(student, teacher)
        if mode == "ordinary":
            return frobenius

        student_point = self.contractor.thermodynamic_point(
            student,
            j=self.j,
            h=self.h,
            log_scale=0.0,
        )
        z_difference = student_point.z - teacher_point.z
        u_difference = student_point.u - teacher_point.u
        hermiticity = self.contractor.hermiticity_residual(student)
        return (
            frobenius
            + self.weights.z * (z_difference / self.tolerances.z) ** 2
            + self.weights.u * (u_difference / self.tolerances.u) ** 2
            + self.weights.hermiticity * hermiticity**2
        )

    def diagnostics(
        self,
        student: FinitePEPO,
        teacher: FinitePEPO,
        *,
        teacher_point: ThermodynamicPoint,
        mode: str,
    ) -> CompressionDiagnostics:
        self._validate_mode(mode)
        frobenius = self.contractor.relative_frobenius_loss(student, teacher)
        student_point = self.contractor.thermodynamic_point(
            student,
            j=self.j,
            h=self.h,
            log_scale=0.0,
        )
        z_difference = student_point.z - teacher_point.z
        u_difference = student_point.u - teacher_point.u
        hermiticity = self.contractor.hermiticity_residual(student)
        z_penalty = self.weights.z * (z_difference / self.tolerances.z) ** 2
        u_penalty = self.weights.u * (u_difference / self.tolerances.u) ** 2
        hermiticity_penalty = self.weights.hermiticity * hermiticity**2
        total = frobenius
        if mode == "thermodynamic":
            total = total + z_penalty + u_penalty + hermiticity_penalty
        return CompressionDiagnostics(
            total=total,
            frobenius=frobenius,
            z_penalty=z_penalty,
            u_penalty=u_penalty,
            hermiticity_penalty=hermiticity_penalty,
            z_difference=z_difference,
            u_difference=u_difference,
        )
