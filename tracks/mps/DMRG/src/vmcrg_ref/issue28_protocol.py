"""Immutable protocols and provenance for the Issue #28 easy goal."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from .artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from .operators import EVEN_SHAPES, OperatorBasis, d4_orbit


REQUIRED_STREAMS = (
    "initial_condition",
    "microscopic",
    "neural_training",
    "linear_training",
    "monitoring",
    "validation",
    "projection",
    "objective_anchor",
    "objective_neural",
    "objective_linear",
    "objective_target",
    "autocorrelation",
    "bootstrap",
)

TERMINAL_CLASSIFICATIONS = (
    "CORRECTNESS_FAILURE",
    "PROTOCOL_FAILURE",
    "SCIENTIFIC_NEGATIVE",
    "EASY_GOAL_SUCCESS",
)

_EXPECTED_GATES = {
    "local_delta_atol": 1e-10,
    "cache_drift_atol": 1e-10,
    "symmetry_atol": 5e-14,
    "operator_equivalence_upper": 0.02,
    "excess_patch_tv_upper": 0.02,
    "tau_linear_noninferiority_upper": 1.10,
    "ess_per_second_linear_noninferiority_lower": 0.90,
    "minimum_directional_seed_count": 4,
    "confidence_level": 0.95,
}

_EXPECTED_OBJECTIVE = {
    "estimator": "stratified_BAR",
    "pilot_lambda_ladder": [0.0, 0.125, 0.25, 0.5, 0.75, 0.875, 1.0],
    "minimum_bar_overlap": 0.03,
    "minimum_kish_ess_fraction": 0.10,
    "maximum_closure_z": 3.0,
    "jackknife_unit": "independent_chain",
    "bootstrap_hierarchy": ["seed_bundle", "chain"],
}


@dataclass(frozen=True)
class SeedStream:
    entropy: int
    spawn_key: tuple[int, ...]

    def seed_sequence(self) -> np.random.SeedSequence:
        return np.random.SeedSequence(self.entropy, spawn_key=self.spawn_key)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SeedStream":
        entropy = int(value["entropy"])
        spawn_key = tuple(int(item) for item in value["spawn_key"])
        if entropy < 0 or not spawn_key or any(item < 0 for item in spawn_key):
            raise ValueError("seed streams require nonnegative entropy and spawn keys")
        return cls(entropy, spawn_key)

    def to_dict(self) -> dict[str, Any]:
        return {"entropy": self.entropy, "spawn_key": list(self.spawn_key)}


@dataclass(frozen=True)
class SeedBundle:
    bundle_id: str
    streams: Mapping[str, SeedStream]


@dataclass(frozen=True)
class PhysicalSetup:
    length: int
    coupling: float
    block_size: int
    boundary: str
    reference_distribution: str


@dataclass(frozen=True)
class NeuralSpec:
    architecture: str
    radius: int
    hidden: int
    feature_mode: str


@dataclass(frozen=True)
class GaugeReferenceSpec:
    length: int
    configurations: int
    dtype: str
    byte_order: str
    seed: SeedStream


@dataclass(frozen=True)
class Issue28Protocol:
    source: Path
    protocol_sha256: str
    protocol: str
    schema_version: int
    locked_scope: bool
    ui_language: str
    physical: PhysicalSetup
    neural: NeuralSpec
    formal_rounds: int
    formal_bundles: tuple[SeedBundle, ...]
    pure_linear_bias: np.ndarray
    operator_basis_sha256: str
    gauge: GaugeReferenceSpec
    gates: Mapping[str, Any]
    objective: Mapping[str, Any]
    terminal_classifications: tuple[str, ...]
    required_streams: tuple[str, ...] = REQUIRED_STREAMS


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def canonical_operator_basis_record(length: int = 15) -> dict[str, Any]:
    basis = OperatorBasis(length, EVEN_SHAPES)
    operators = []
    for shape, count in zip(EVEN_SHAPES, basis.instance_counts):
        if count % (length * length) != 0:
            raise ValueError(f"operator {shape.name} has nonintegral per-site count")
        operators.append(
            {
                "name": shape.name,
                "vertices": [list(vertex) for vertex in shape.vertices],
                "parity": shape.parity,
                "arity": len(shape.vertices),
                "d4_orbit": [
                    [list(vertex) for vertex in orientation]
                    for orientation in d4_orbit(shape.vertices)
                ],
                "instance_count": count,
                "instances_per_site": count // (length * length),
            }
        )
    return {
        "schema_version": 1,
        "length": int(length),
        "sign_convention": "S_shape=-sum_products",
        "operators": operators,
    }


def operator_basis_sha256(length: int = 15) -> str:
    return sha256_bytes(canonical_json_bytes(canonical_operator_basis_record(length)))


def _parse_bundles(values: list[dict[str, Any]]) -> tuple[SeedBundle, ...]:
    bundles = []
    all_records: set[tuple[int, tuple[int, ...]]] = set()
    for value in values:
        streams = {
            str(name): SeedStream.from_dict(record)
            for name, record in dict(value["streams"]).items()
        }
        if set(streams) != set(REQUIRED_STREAMS):
            missing = sorted(set(REQUIRED_STREAMS) - set(streams))
            extra = sorted(set(streams) - set(REQUIRED_STREAMS))
            raise ValueError(f"seed bundle stream mismatch: missing={missing}, extra={extra}")
        for stream in streams.values():
            key = (stream.entropy, stream.spawn_key)
            if key in all_records:
                raise ValueError("duplicate RNG stream in formal seed bundles")
            all_records.add(key)
        bundles.append(SeedBundle(str(value["bundle_id"]), MappingProxyType(streams)))
    if len({bundle.bundle_id for bundle in bundles}) != len(bundles):
        raise ValueError("formal seed bundle ids must be unique")
    return tuple(bundles)


def load_issue28_protocol(path: str | Path) -> Issue28Protocol:
    source = Path(path)
    with source.open("r", encoding="ascii") as handle:
        value = json.load(handle)
    if value.get("protocol") != "issue28_pure_neural_easy_v1":
        raise ValueError("unexpected Issue #28 protocol name")
    if int(value.get("schema_version", 0)) != 1:
        raise ValueError("unsupported Issue #28 protocol schema")
    if value.get("locked_scope") is not True:
        raise ValueError("Issue #28 protocol scope must remain locked")
    if value.get("ui_language") != "zh-CN":
        raise ValueError("Issue #28 user interface language must be zh-CN")
    terminal_classifications = tuple(str(item) for item in value.get("terminal_classifications", ()))
    if terminal_classifications != TERMINAL_CLASSIFICATIONS:
        raise ValueError("Issue #28 terminal classifications changed")

    physical_value = value["physical"]
    physical = PhysicalSetup(
        length=int(physical_value["length"]),
        coupling=float(physical_value["coupling"]),
        block_size=int(physical_value["block_size"]),
        boundary=str(physical_value["boundary"]),
        reference_distribution=str(physical_value["reference_distribution"]),
    )
    if physical != PhysicalSetup(
        45,
        0.436,
        3,
        "periodic",
        "uniform_independent_ising_2d",
    ):
        raise ValueError("Issue #28 frozen physical setup changed")

    neural_value = value["neural"]
    neural = NeuralSpec(
        architecture=str(neural_value["architecture"]),
        radius=int(neural_value["radius"]),
        hidden=int(neural_value["hidden"]),
        feature_mode=str(neural_value["feature_mode"]),
    )
    if neural != NeuralSpec("D4EvenLocalMLP", 3, 32, "multiscale"):
        raise ValueError("Issue #28 frozen neural architecture changed")

    formal_rounds = int(value["formal_rounds"])
    if formal_rounds < 5:
        raise ValueError("Issue #28 requires at least five formal RG rounds")
    bundles = _parse_bundles(list(value["formal_seed_bundles"]))
    if len(bundles) != 5:
        raise ValueError("Issue #28 requires exactly five formal seed bundles")

    bias = np.asarray(value["neural"]["fixed_linear_bias"], dtype=np.float64)
    if bias.shape != (13,) or not np.array_equal(bias, np.zeros(13, dtype=np.float64)):
        raise ValueError("pure-neural protocol requires an exact zero 13-operator bias")
    bias.setflags(write=False)

    gates = dict(value["gates"])
    if gates != _EXPECTED_GATES:
        raise ValueError("Issue #28 frozen scientific gates changed")
    objective = dict(value["objective"])
    if objective != _EXPECTED_OBJECTIVE:
        raise ValueError("Issue #28 frozen objective protocol changed")

    expected_basis_hash = str(value["operator_basis_sha256"])
    actual_basis_hash = operator_basis_sha256()
    if expected_basis_hash != actual_basis_hash:
        raise ValueError(
            f"operator basis hash mismatch: expected {expected_basis_hash}, got {actual_basis_hash}"
        )

    gauge_value = value["gauge_reference"]
    gauge = GaugeReferenceSpec(
        length=int(gauge_value["length"]),
        configurations=int(gauge_value["configurations"]),
        dtype=str(gauge_value["dtype"]),
        byte_order=str(gauge_value["byte_order"]),
        seed=SeedStream.from_dict(gauge_value["seed"]),
    )
    if gauge.length != physical.length or gauge.configurations <= 0:
        raise ValueError("invalid gauge reference geometry")
    if gauge.dtype != "int8" or gauge.byte_order != "|":
        raise ValueError("gauge reference must use byte-order-independent int8")

    return Issue28Protocol(
        source=source.resolve(),
        protocol_sha256=sha256_file(source),
        protocol=str(value["protocol"]),
        schema_version=1,
        locked_scope=True,
        ui_language="zh-CN",
        physical=physical,
        neural=neural,
        formal_rounds=formal_rounds,
        formal_bundles=bundles,
        pure_linear_bias=bias,
        operator_basis_sha256=expected_basis_hash,
        gauge=gauge,
        gates=_deep_freeze(gates),
        objective=_deep_freeze(objective),
        terminal_classifications=terminal_classifications,
    )


def create_gauge_reference(
    protocol: Issue28Protocol,
    output: str | Path,
) -> dict[str, Any]:
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty gauge directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    spec = protocol.gauge
    rng = np.random.default_rng(spec.seed.seed_sequence())
    spins = rng.choice(
        np.asarray([-1, 1], dtype=np.int8),
        size=(spec.configurations, spec.length, spec.length),
    )
    if spins.dtype.str != "|i1":
        raise AssertionError("gauge reference dtype is not canonical int8")
    archive = root / "gauge_reference.npz"
    atomic_write_npz(archive, {"spins": spins})
    record = {
        "schema_version": 1,
        "generator": "numpy.default_rng.choice[-1,+1]",
        "seed": spec.seed.to_dict(),
        "shape": list(spins.shape),
        "dtype": "int8",
        "byte_order": "|",
        "raw_array_sha256": sha256_bytes(spins.tobytes(order="C")),
        "archive_sha256": sha256_file(archive),
    }
    atomic_write_json(root / "gauge_reference.json", record)
    return record
