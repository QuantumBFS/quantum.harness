"""Validated contracts for VQE time-to-solution experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any, Literal

from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
)

OptimizerName = Literal[
    "adam",
    "lbfgs",
    "natural-gradient",
]
InitializationName = Literal[
    "zeros",
    "random",
    "recycled",
]
ParametersPayload = tuple[
    tuple[tuple[float, ...], tuple[float, ...]],
    ...,
]


def _parameters_from_value(
    value: Any,
) -> ParametersPayload:
    return tuple(
        (
            tuple(float(item) for item in layer[0]),
            tuple(float(item) for item in layer[1]),
        )
        for layer in value
    )


def _program_from_dict(
    payload: dict[str, Any],
) -> ProgramConfig | SpatialProgramConfig:
    if payload.get("representation") == "spatial_transfer":
        return SpatialProgramConfig.from_dict(payload)
    return ProgramConfig.from_dict(payload)


@dataclass(frozen=True)
class VQETrainingRequest:
    """One complete optimizer/program/initialization experiment."""

    spec: TFIMVQESpec
    program: ProgramConfig | SpatialProgramConfig
    optimizer: OptimizerName
    initialization: InitializationName
    target_energy_error: float
    max_steps: int
    seed: int = 0
    learning_rate: float = 0.05
    damping: float = 1e-3
    ground_energy: float | None = None
    recycled_source_spec: TFIMVQESpec | None = None
    recycled_parameters: ParametersPayload | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.program,
            (ProgramConfig, SpatialProgramConfig),
        ):
            raise ValueError(
                "training program must be statevector or spatial"
            )
        if self.optimizer not in (
            "adam",
            "lbfgs",
            "natural-gradient",
        ):
            raise ValueError(
                f"unsupported optimizer: {self.optimizer}"
            )
        if self.initialization not in (
            "zeros",
            "random",
            "recycled",
        ):
            raise ValueError(
                "unsupported initialization: "
                f"{self.initialization}"
            )
        if (
            self.target_energy_error <= 0
            or not isfinite(self.target_energy_error)
        ):
            raise ValueError(
                "target_energy_error must be finite and positive"
            )
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")
        if (
            self.learning_rate <= 0
            or not isfinite(self.learning_rate)
        ):
            raise ValueError(
                "learning_rate must be finite and positive"
            )
        if self.damping <= 0 or not isfinite(self.damping):
            raise ValueError(
                "damping must be finite and positive"
            )
        if (
            self.ground_energy is not None
            and not isfinite(self.ground_energy)
        ):
            raise ValueError("ground_energy must be finite")

        recycling_values = (
            self.recycled_source_spec,
            self.recycled_parameters,
        )
        if self.initialization == "recycled":
            if any(value is None for value in recycling_values):
                raise ValueError(
                    "recycled initialization requires source "
                    "spec and parameters"
                )
            assert self.recycled_source_spec is not None
            assert self.recycled_parameters is not None
            expected = (
                self.recycled_source_spec.depth,
                2,
                self.recycled_source_spec.nqubits,
            )
            actual = (
                len(self.recycled_parameters),
                (
                    len(self.recycled_parameters[0])
                    if self.recycled_parameters
                    else 0
                ),
                (
                    len(self.recycled_parameters[0][0])
                    if self.recycled_parameters
                    else 0
                ),
            )
            if actual != expected or any(
                len(row)
                != self.recycled_source_spec.nqubits
                for layer in self.recycled_parameters
                for row in layer
            ):
                raise ValueError(
                    "recycled parameter shape does not match "
                    "source spec"
                )
        elif any(value is not None for value in recycling_values):
            raise ValueError(
                "recycled source is only valid for recycled "
                "initialization"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "program": self.program.to_dict(),
            "optimizer": self.optimizer,
            "initialization": self.initialization,
            "target_energy_error": self.target_energy_error,
            "max_steps": self.max_steps,
            "seed": self.seed,
            "learning_rate": self.learning_rate,
            "damping": self.damping,
            "ground_energy": self.ground_energy,
            "recycled_source_spec": (
                self.recycled_source_spec.to_dict()
                if self.recycled_source_spec is not None
                else None
            ),
            "recycled_parameters": (
                [
                    [list(row) for row in layer]
                    for layer in self.recycled_parameters
                ]
                if self.recycled_parameters is not None
                else None
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> VQETrainingRequest:
        values = dict(payload)
        values["spec"] = TFIMVQESpec.from_dict(
            values["spec"]
        )
        values["program"] = _program_from_dict(
            values["program"]
        )
        if values.get("recycled_source_spec") is not None:
            values["recycled_source_spec"] = (
                TFIMVQESpec.from_dict(
                    values["recycled_source_spec"]
                )
            )
        if values.get("recycled_parameters") is not None:
            values["recycled_parameters"] = (
                _parameters_from_value(
                    values["recycled_parameters"]
                )
            )
        return cls(**values)


@dataclass(frozen=True)
class VQEStep:
    """One synchronized expensive objective evaluation."""

    evaluation: int
    optimizer_step: int
    energy: float
    energy_error: float
    gradient_norm: float
    elapsed_seconds: float
    metric_condition: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VQEStep:
        return cls(**payload)


@dataclass(frozen=True)
class VQETrainingResult:
    """Measured outcome of one complete VQE training run."""

    request: VQETrainingRequest
    converged: bool
    evaluations: int
    optimizer_steps: int
    compile_seconds: float
    first_execute_seconds: float
    optimization_seconds: float
    time_to_target_seconds: float | None
    total_seconds: float
    peak_rss_bytes: int
    ground_energy: float
    target_energy: float
    final_energy: float
    final_parameters: ParametersPayload
    trace: tuple[VQEStep, ...]
    initialization_provenance: dict[str, Any] = field(
        default_factory=dict
    )
    failure: str | None = None
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "program_label": self.request.program.label,
            "converged": self.converged,
            "evaluations": self.evaluations,
            "optimizer_steps": self.optimizer_steps,
            "compile_seconds": self.compile_seconds,
            "first_execute_seconds": (
                self.first_execute_seconds
            ),
            "optimization_seconds": (
                self.optimization_seconds
            ),
            "time_to_target_seconds": (
                self.time_to_target_seconds
            ),
            "total_seconds": self.total_seconds,
            "peak_rss_bytes": self.peak_rss_bytes,
            "ground_energy": self.ground_energy,
            "target_energy": self.target_energy,
            "final_energy": self.final_energy,
            "final_parameters": [
                [list(row) for row in layer]
                for layer in self.final_parameters
            ],
            "trace": [
                item.to_dict() for item in self.trace
            ],
            "initialization_provenance": (
                self.initialization_provenance
            ),
            "failure": self.failure,
            "skipped": self.skipped,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> VQETrainingResult:
        values = dict(payload)
        values.pop("program_label", None)
        values["request"] = VQETrainingRequest.from_dict(
            values["request"]
        )
        values["final_parameters"] = _parameters_from_value(
            values["final_parameters"]
        )
        values["trace"] = tuple(
            VQEStep.from_dict(item)
            for item in values["trace"]
        )
        return cls(**values)
