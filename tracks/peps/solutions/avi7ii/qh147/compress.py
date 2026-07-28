from __future__ import annotations

from dataclasses import dataclass
import math

import autoray as ar
import jax
import quimb.tensor as qtn

from .contract import BoundaryContractor, ThermodynamicPoint
from .pepo import FinitePEPO

jax.config.update("jax_enable_x64", True)


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


@dataclass(frozen=True)
class CompressionBudget:
    chi: int
    cutoff: float
    max_iterations: int
    optimizer: str
    requested_bond: int


@dataclass(frozen=True)
class CompressionResult:
    pepo: FinitePEPO
    initial: CompressionDiagnostics
    final: CompressionDiagnostics
    iterations: int
    loss_history: tuple[float, ...]
    max_bond: int
    mode: str
    budget: CompressionBudget


def _maximum_virtual_bond(pepo: FinitePEPO) -> int:
    inner = tuple(pepo.tn.inner_inds())
    if not inner:
        return 1
    return max(pepo.tn.ind_size(index) for index in inner)


class VariationalCompressor:
    def __init__(
        self,
        objective: CompressionObjective,
        *,
        max_iterations: int = 50,
        optimizer: str = "L-BFGS-B",
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self.objective = objective
        self.max_iterations = max_iterations
        self.optimizer = optimizer

    def compress(
        self,
        teacher: FinitePEPO,
        *,
        max_bond: int,
        mode: str,
    ) -> CompressionResult:
        self.objective._validate_mode(mode)
        if max_bond < 1:
            raise ValueError("max_bond must be positive")

        student = teacher.copy()
        student.tn.compress_all_(max_bond=max_bond, cutoff=0.0)
        seeded_bond = _maximum_virtual_bond(student)
        if seeded_bond > max_bond:
            raise RuntimeError("fixed-bond seed exceeds requested maximum")

        teacher_point = self.objective.teacher_point(teacher)
        initial = self.objective.diagnostics(
            student,
            teacher,
            teacher_point=teacher_point,
            mode=mode,
        )

        lx = teacher.lx
        ly = teacher.ly

        def loss_fn(candidate_tn):
            candidate = FinitePEPO(lx=lx, ly=ly, tn=candidate_tn)
            return self.objective.loss(
                candidate,
                teacher,
                teacher_point=teacher_point,
                mode=mode,
            )

        optimizer = qtn.TNOptimizer(
            student.tn,
            loss_fn=loss_fn,
            tags="PEPO",
            optimizer=self.optimizer,
            progbar=False,
            autodiff_backend="jax",
        )
        optimized_tn = optimizer.optimize(self.max_iterations)
        optimized = FinitePEPO(lx=lx, ly=ly, tn=optimized_tn)
        final_bond = _maximum_virtual_bond(optimized)
        if final_bond > max_bond:
            raise RuntimeError("optimizer changed the fixed PEPO bond dimension")

        final = self.objective.diagnostics(
            optimized,
            teacher,
            teacher_point=teacher_point,
            mode=mode,
        )
        history = tuple(float(value) for value in optimizer.losses)
        budget = CompressionBudget(
            chi=self.objective.contractor.chi,
            cutoff=self.objective.contractor.cutoff,
            max_iterations=self.max_iterations,
            optimizer=self.optimizer,
            requested_bond=max_bond,
        )
        return CompressionResult(
            pepo=optimized,
            initial=initial,
            final=final,
            iterations=len(history),
            loss_history=history,
            max_bond=final_bond,
            mode=mode,
            budget=budget,
        )
