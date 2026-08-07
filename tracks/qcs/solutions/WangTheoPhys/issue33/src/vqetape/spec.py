"""Validated semantic inputs for the VQETape prototype."""

from __future__ import annotations

from hashlib import sha1
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, Literal

DTypeName = Literal["complex64", "complex128"]
InitialStateName = Literal["zero", "plus"]
ControlFlowName = Literal["unrolled", "scan"]
AdjointName = Literal["default", "remat", "segmented"]
GateRepresentation = Literal["dense", "operator_schmidt"]
HamiltonianRepresentation = Literal["pauli_sum", "mpo"]
SpatialAdjoint = Literal[
    "default",
    "remat",
    "segmented",
    "explicit",
]
SpatialSymmetry = Literal[
    "none",
    "z2-reference",
    "z2-native",
]


def dtype_bytes(dtype: DTypeName) -> int:
    """Return the number of bytes in one complex scalar."""

    try:
        return {"complex64": 8, "complex128": 16}[dtype]
    except KeyError as exc:
        raise ValueError(f"unsupported dtype: {dtype}") from exc


@dataclass(frozen=True)
class TFIMVQESpec:
    """Exact open-boundary 1D TFIM VQE workload."""

    nqubits: int
    depth: int
    coupling: float = 1.0
    field: float = 1.0
    initial_state: InitialStateName = "plus"
    dtype: DTypeName = "complex64"

    def __post_init__(self) -> None:
        if self.nqubits < 2:
            raise ValueError("nqubits must be at least 2")
        if self.depth < 1:
            raise ValueError("depth must be positive")
        if not isfinite(self.coupling) or not isfinite(self.field):
            raise ValueError("coupling and field must be finite")
        if self.initial_state not in ("zero", "plus"):
            raise ValueError(f"unsupported initial_state: {self.initial_state}")
        if self.dtype not in ("complex64", "complex128"):
            raise ValueError(f"unsupported dtype: {self.dtype}")

    @property
    def parameter_shape(self) -> tuple[int, int, int]:
        return (self.depth, 2, self.nqubits)

    @property
    def active_parameter_count(self) -> int:
        return self.depth * (2 * self.nqubits - 1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TFIMVQESpec:
        return cls(**payload)


@dataclass(frozen=True)
class ProgramConfig:
    """One concrete forward-control-flow and adjoint-schedule choice."""

    control_flow: ControlFlowName
    adjoint: AdjointName
    unroll: int = 1
    segment_length: int | None = None
    representation: Literal["statevector"] = "statevector"

    def __post_init__(self) -> None:
        if self.control_flow not in ("unrolled", "scan"):
            raise ValueError(f"unsupported control_flow: {self.control_flow}")
        if self.adjoint not in ("default", "remat", "segmented"):
            raise ValueError(f"unsupported adjoint: {self.adjoint}")
        if self.representation != "statevector":
            raise ValueError(f"unsupported representation: {self.representation}")
        if self.unroll < 1:
            raise ValueError("unroll must be positive")
        if self.control_flow == "unrolled" and self.unroll != 1:
            raise ValueError("unrolled control flow requires unroll=1")
        if self.adjoint == "segmented":
            if self.control_flow != "scan":
                raise ValueError("segmented adjoint requires scan control flow")
            if self.segment_length is None or self.segment_length < 1:
                raise ValueError("segmented adjoint requires positive segment_length")
        elif self.segment_length is not None:
            raise ValueError("segment_length is only valid for segmented adjoint")

    @property
    def label(self) -> str:
        base = f"{self.control_flow}-{self.adjoint}-u{self.unroll}"
        if self.segment_length is not None:
            return f"{base}-s{self.segment_length}"
        return base

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProgramConfig:
        return cls(**payload)


@dataclass(frozen=True)
class TensorProgramConfig:
    """One direct tensor-network path and reverse-tape policy."""

    path_strategy: Literal["greedy", "random-greedy", "auto-hq"]
    remat_policy: Literal[
        "none",
        "all",
        "output-ge-threshold",
        "term",
        "objective",
        "subtree",
        "named",
    ]
    threshold_bytes: int | None = None
    path: tuple[tuple[int, ...], ...] | None = None
    subtree_depth: int | None = None
    save_names: tuple[str, ...] | None = None
    gate_representation: GateRepresentation = "dense"
    hamiltonian_representation: HamiltonianRepresentation = "pauli_sum"
    representation: Literal["direct_tn"] = "direct_tn"

    def __post_init__(self) -> None:
        if self.path_strategy not in ("greedy", "random-greedy", "auto-hq"):
            raise ValueError(f"unsupported path_strategy: {self.path_strategy}")
        if self.remat_policy not in (
            "none",
            "all",
            "output-ge-threshold",
            "term",
            "objective",
            "subtree",
            "named",
        ):
            raise ValueError(f"unsupported remat_policy: {self.remat_policy}")
        if self.representation != "direct_tn":
            raise ValueError(f"unsupported representation: {self.representation}")
        if self.gate_representation not in ("dense", "operator_schmidt"):
            raise ValueError(
                "unsupported gate_representation: "
                f"{self.gate_representation}"
            )
        if self.hamiltonian_representation not in ("pauli_sum", "mpo"):
            raise ValueError(
                "unsupported hamiltonian_representation: "
                f"{self.hamiltonian_representation}"
            )
        if self.remat_policy == "output-ge-threshold":
            if self.threshold_bytes is None or self.threshold_bytes < 1:
                raise ValueError(
                    "threshold policy requires positive threshold_bytes"
                )
        elif self.threshold_bytes is not None:
            raise ValueError(
                "threshold_bytes is only valid for threshold policy"
            )
        if self.remat_policy == "subtree":
            if self.subtree_depth is None or self.subtree_depth < 0:
                raise ValueError(
                    "subtree policy requires nonnegative subtree_depth"
                )
        elif self.subtree_depth is not None:
            raise ValueError(
                "subtree_depth is only valid for subtree policy"
            )
        if self.remat_policy == "named":
            if self.save_names is None:
                raise ValueError("named policy requires save_names")
            if len(set(self.save_names)) != len(self.save_names):
                raise ValueError("save_names must not contain duplicates")
        elif self.save_names is not None:
            raise ValueError("save_names is only valid for named policy")

    @property
    def label(self) -> str:
        gate_label = self.gate_representation.replace("_", "-")
        hamiltonian_label = self.hamiltonian_representation.replace("_", "-")
        base = (
            f"direct-tn-{gate_label}-"
            f"{hamiltonian_label}-"
            f"{self.path_strategy}-{self.remat_policy}"
        )
        if self.threshold_bytes is not None:
            return f"{base}-b{self.threshold_bytes}"
        if self.subtree_depth is not None:
            return f"{base}-d{self.subtree_depth}"
        if self.save_names is not None:
            digest = sha1(
                "\0".join(self.save_names).encode("utf-8")
            ).hexdigest()[:8]
            return f"{base}-n{len(self.save_names)}-{digest}"
        return base

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TensorProgramConfig:
        values = dict(payload)
        if values.get("path") is not None:
            values["path"] = tuple(
                tuple(int(position) for position in step)
                for step in values["path"]
            )
        if values.get("save_names") is not None:
            values["save_names"] = tuple(str(name) for name in values["save_names"])
        return cls(**values)


@dataclass(frozen=True)
class SpatialProgramConfig:
    """One exact spatial-transfer path and reverse schedule."""

    path_strategy: Literal["greedy", "random-greedy", "auto-hq"]
    adjoint: SpatialAdjoint
    unroll: int = 1
    block_width: int = 1
    symmetry: SpatialSymmetry = "none"
    segment_length: int | None = None
    column_paths: (
        tuple[tuple[tuple[int, ...], ...], ...] | None
    ) = None
    representation: Literal["spatial_transfer"] = "spatial_transfer"

    def __post_init__(self) -> None:
        if self.path_strategy not in ("greedy", "random-greedy", "auto-hq"):
            raise ValueError(
                f"unsupported path_strategy: {self.path_strategy}"
            )
        if self.adjoint not in (
            "default",
            "remat",
            "segmented",
            "explicit",
        ):
            raise ValueError(f"unsupported adjoint: {self.adjoint}")
        if self.unroll < 1:
            raise ValueError("unroll must be positive")
        if self.block_width < 1:
            raise ValueError("block_width must be positive")
        if self.symmetry not in (
            "none",
            "z2-reference",
            "z2-native",
        ):
            raise ValueError(
                f"unsupported symmetry: {self.symmetry}"
            )
        if self.representation != "spatial_transfer":
            raise ValueError(
                f"unsupported representation: {self.representation}"
            )
        if self.adjoint == "segmented":
            if self.segment_length is None or self.segment_length < 1:
                raise ValueError(
                    "segmented adjoint requires positive segment_length"
                )
        elif self.segment_length is not None:
            raise ValueError(
                "segment_length is only valid for segmented adjoint"
            )
        if self.column_paths is not None:
            if len(self.column_paths) not in (2, 3, 4):
                raise ValueError(
                    "column paths must contain first/last, "
                    "first/block/last, or "
                    "first/block/tail/last paths"
                )
            if any(not path for path in self.column_paths):
                raise ValueError("column paths must not be empty")

    @property
    def label(self) -> str:
        base = (
            f"spatial-transfer-{self.path_strategy}-"
            f"b{self.block_width}-{self.adjoint}-u{self.unroll}"
        )
        if self.symmetry != "none":
            base = f"{base}-{self.symmetry}"
        if self.segment_length is not None:
            return f"{base}-s{self.segment_length}"
        return base

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SpatialProgramConfig:
        values = dict(payload)
        if values.get("column_paths") is not None:
            values["column_paths"] = tuple(
                tuple(
                    tuple(int(position) for position in step)
                    for step in path
                )
                for path in values["column_paths"]
            )
        return cls(**values)


@dataclass(frozen=True)
class CorrectnessTolerance:
    energy_atol: float
    gradient_rtol: float

    @classmethod
    def for_dtype(cls, dtype: DTypeName) -> CorrectnessTolerance:
        if dtype == "complex64":
            return cls(energy_atol=1e-5, gradient_rtol=1e-4)
        if dtype == "complex128":
            return cls(energy_atol=1e-10, gradient_rtol=1e-9)
        raise ValueError(f"unsupported dtype: {dtype}")


@dataclass(frozen=True)
class CompileRequest:
    """Compilation objective and measurement controls."""

    spec: TFIMVQESpec
    memory_budget_bytes: int
    expected_vqe_steps: int
    warm_repeats: int = 5
    seed: int = 0
    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.memory_budget_bytes < 1:
            raise ValueError("memory_budget_bytes must be positive")
        if self.expected_vqe_steps < 1:
            raise ValueError("expected_vqe_steps must be positive")
        if self.warm_repeats < 1:
            raise ValueError("warm_repeats must be positive")
        if self.timeout_seconds <= 0 or not isfinite(self.timeout_seconds):
            raise ValueError("timeout_seconds must be finite and positive")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spec"] = self.spec.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CompileRequest:
        values = dict(payload)
        values["spec"] = TFIMVQESpec.from_dict(values["spec"])
        return cls(**values)
