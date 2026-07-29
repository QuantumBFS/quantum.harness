from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time

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
        # JAX cannot trace Quimb's data-dependent singular-value cutoff.
        # Keep the same chi, but use a fixed-rank contraction for gradients.
        self.optimization_contractor = BoundaryContractor(
            chi=contractor.chi,
            cutoff=0.0,
        )
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

    def optimization_teacher_point(
        self,
        teacher: FinitePEPO,
    ) -> ThermodynamicPoint:
        return self.optimization_contractor.thermodynamic_point(
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
        contractor = self.optimization_contractor
        frobenius = contractor.relative_frobenius_loss(student, teacher)
        if mode == "ordinary":
            return frobenius

        student_point = contractor.thermodynamic_point(
            student,
            j=self.j,
            h=self.h,
            log_scale=0.0,
        )
        z_difference = student_point.z - teacher_point.z
        u_difference = student_point.u - teacher_point.u
        hermiticity = contractor.hermiticity_residual(student)
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


def _emit_stage(stage: str, **values) -> None:
    print(
        json.dumps(
            {"event": "compression_stage", "stage": stage, **values},
            sort_keys=True,
            allow_nan=False,
        ),
        flush=True,
    )


class VariationalCompressor:
    def __init__(
        self,
        objective: CompressionObjective,
        *,
        max_iterations: int = 50,
        optimizer: str = "L-BFGS-B",
        skip_optimization_tolerance: float | None = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self.objective = objective
        self.max_iterations = max_iterations
        self.optimizer = optimizer
        if skip_optimization_tolerance is not None and (
            not math.isfinite(skip_optimization_tolerance)
            or skip_optimization_tolerance < 0
        ):
            raise ValueError(
                "skip optimization tolerance must be finite and non-negative"
            )
        self.skip_optimization_tolerance = skip_optimization_tolerance

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

        started = time.perf_counter()
        _emit_stage("seed_start", mode=mode, max_bond=max_bond)
        student = teacher.copy()
        student.tn.compress_all_(max_bond=max_bond, cutoff=0.0)
        seeded_bond = _maximum_virtual_bond(student)
        if seeded_bond > max_bond:
            raise RuntimeError("fixed-bond seed exceeds requested maximum")
        _emit_stage(
            "seed_complete",
            mode=mode,
            elapsed_seconds=time.perf_counter() - started,
            seeded_bond=seeded_bond,
        )

        started = time.perf_counter()
        _emit_stage("teacher_point_start", mode=mode)
        teacher_point = self.objective.teacher_point(teacher)
        _emit_stage(
            "teacher_point_complete",
            mode=mode,
            elapsed_seconds=time.perf_counter() - started,
        )
        started = time.perf_counter()
        _emit_stage("initial_diagnostics_start", mode=mode)
        initial = self.objective.diagnostics(
            student,
            teacher,
            teacher_point=teacher_point,
            mode=mode,
        )
        _emit_stage(
            "initial_diagnostics_complete",
            mode=mode,
            elapsed_seconds=time.perf_counter() - started,
        )

        initial_loss = initial.as_floats().total
        if (
            self.skip_optimization_tolerance is not None
            and initial_loss <= self.skip_optimization_tolerance
        ):
            _emit_stage(
                "optimizer_skipped",
                mode=mode,
                initial_loss=initial_loss,
                tolerance=self.skip_optimization_tolerance,
            )
            budget = CompressionBudget(
                chi=self.objective.contractor.chi,
                cutoff=self.objective.contractor.cutoff,
                max_iterations=self.max_iterations,
                optimizer=self.optimizer,
                requested_bond=max_bond,
            )
            return CompressionResult(
                pepo=student,
                initial=initial,
                final=initial,
                iterations=0,
                loss_history=(initial_loss,),
                max_bond=seeded_bond,
                mode=mode,
                budget=budget,
            )

        started = time.perf_counter()
        _emit_stage("optimization_teacher_point_start", mode=mode)
        optimization_teacher_point = self.objective.optimization_teacher_point(
            teacher
        )
        _emit_stage(
            "optimization_teacher_point_complete",
            mode=mode,
            elapsed_seconds=time.perf_counter() - started,
        )

        lx = teacher.lx
        ly = teacher.ly

        def loss_fn(candidate_tn):
            candidate = FinitePEPO(lx=lx, ly=ly, tn=candidate_tn)
            return self.objective.loss(
                candidate,
                teacher,
                teacher_point=optimization_teacher_point,
                mode=mode,
            )

        def optimizer_progress(tnopt):
            loss = float(tnopt.loss)
            _emit_stage(
                "optimizer_progress",
                mode=mode,
                evaluation=int(tnopt.nevals),
                loss=loss if math.isfinite(loss) else None,
                finite=math.isfinite(loss),
            )

        _emit_stage(
            "optimizer_start",
            mode=mode,
            max_iterations=self.max_iterations,
        )
        started = time.perf_counter()
        optimizer = qtn.TNOptimizer(
            student.tn,
            loss_fn=loss_fn,
            tags="PEPO",
            optimizer=self.optimizer,
            progbar=False,
            autodiff_backend="jax",
            callback=optimizer_progress,
        )
        optimized_tn = optimizer.optimize(self.max_iterations)
        _emit_stage(
            "optimizer_complete",
            mode=mode,
            elapsed_seconds=time.perf_counter() - started,
            evaluations=int(optimizer.nevals),
        )
        optimized = FinitePEPO(lx=lx, ly=ly, tn=optimized_tn)
        final_bond = _maximum_virtual_bond(optimized)
        if final_bond > max_bond:
            raise RuntimeError("optimizer changed the fixed PEPO bond dimension")

        started = time.perf_counter()
        _emit_stage("final_diagnostics_start", mode=mode)
        final = self.objective.diagnostics(
            optimized,
            teacher,
            teacher_point=teacher_point,
            mode=mode,
        )
        _emit_stage(
            "final_diagnostics_complete",
            mode=mode,
            elapsed_seconds=time.perf_counter() - started,
        )
        history = tuple(
            value
            for value in (float(raw) for raw in optimizer.losses)
            if math.isfinite(value)
        )
        final_loss = final.as_floats().total
        if not history or not math.isclose(
            history[-1],
            final_loss,
            rel_tol=1e-12,
            abs_tol=1e-14,
        ):
            history = (*history, final_loss)
        iterations = int(optimizer.res.nit)
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
            iterations=iterations,
            loss_history=history,
            max_bond=final_bond,
            mode=mode,
            budget=budget,
        )
