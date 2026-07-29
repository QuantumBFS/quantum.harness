from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Iterable, Mapping, Sequence
import uuid

import numpy as np
from scipy.stats import binomtest, poisson

from .alias import build_distance_alias
from .counter_rng import (
    StreamIdentity,
    derive_stream_material,
    philox4x32_10,
    philox4x32_10_reference,
)
from .edge_set import allocate_edge_set, edge_set_insert
from .enumeration import enumerate_graphs
from .geometric import sample_geometric
from .kernel import edge_probabilities, periodic_kernel
from .model import ModelSpec, canonical_edge, distance_classes, iter_unordered_edges
from .oracle import no_edge_probability, sample_quadratic
from .poisson_reference import (
    TrajectoryRequest,
    _build_reference_streams,
    _run_poisson_with_streams,
    run_poisson_reference,
)
from .poisson_sweep import run_poisson_numba
from .production_union_find import (
    allocate_union_find,
    scan_basic_observables,
    union_incremental,
)
from .runtime import runtime_capability
from .union_find import UnionFind


VALIDATION_PROTOCOL_VERSION = "challenge-194-validation-v1"
FAMILYWISE_ALPHA = 0.001
LENGTHS = (4, 6, 8, 16, 32, 64, 128, 256)
SIGMAS = (0.8, 1.0, 1.1)
KAPPAS = (0.0, 0.25, 0.7, 2.0, 6.0)
SAMPLES_BY_LENGTH = {
    4: 32768,
    6: 32768,
    8: 32768,
    16: 16384,
    32: 8192,
    64: 4096,
    128: 2048,
    256: 1024,
}
SAMPLERS = ("quadratic", "geometric", "poisson-reference", "poisson-numba")
MASTER_SEEDS = tuple(range(194_000_000, 194_032_768))

THREE_WAY_SAMPLERS = ("quadratic", "geometric", "poisson-numba")
PAIR_NAMES = (
    ("quadratic", "geometric"),
    ("quadratic", "poisson-numba"),
    ("geometric", "poisson-numba"),
)
SCALAR_COLUMNS = {
    "open-count": 0,
    "S1": 4,
    "S2": 5,
    "second-moment": 6,
    "fourth-moment": 7,
    "QG": 8,
    "four-sector": 9,
}
STATISTICAL_FAMILIES = (
    "all-graph-probability",
    "edge-class-frequency",
    "poisson-event-count",
    "no-edge",
    "bond-length",
    "component-partition",
    *SCALAR_COLUMNS,
)
EXACT_FAMILIES = (
    "philox-vectors",
    "stream-separation",
    "bounded-integer-accounting",
    "alias-invariants",
    "edge-id-uniqueness",
    "hash-full-range-growth",
    "all-graph-exact",
    "kappa-zero",
    "saturated-coupling",
    "antipodal-counts",
    "finite-parameter-extremes",
    "duplicate-limits",
    "incremental-root-scan",
    "process-order-identity",
    "sampler-structure",
)


def _strict_positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _f64(value: float) -> str:
    return float(value).hex()


@dataclass(frozen=True)
class ValidationCase:
    length: int
    sigma: float
    kappa: float
    samples: int
    seed_start: int

    @property
    def case_id(self) -> str:
        return (
            f"L{self.length}/sigma-{_f64(self.sigma)}/"
            f"kappa-{_f64(self.kappa)}"
        )


def frozen_family_denominators(
    lengths: Sequence[int],
    sigmas: Sequence[float],
    kappas: Sequence[float],
) -> dict[str, int]:
    cases = len(lengths) * len(sigmas) * len(kappas)
    edge_classes = sum(length // 2 for length in lengths) * len(sigmas) * len(kappas)
    small_graphs = sum(
        1 << (length * (length - 1) // 2)
        for length in lengths
        if length <= 6
    )
    return {
        "all-graph-probability": 3 * small_graphs * len(sigmas) * len(kappas),
        "edge-class-frequency": 3 * edge_classes,
        "poisson-event-count": 2 * cases,
        "no-edge": 4 * cases,
        "bond-length": 3 * cases,
        "component-partition": 3 * cases,
        **{name: 3 * cases for name in SCALAR_COLUMNS},
    }


@dataclass(frozen=True)
class ValidationProtocol:
    lengths: tuple[int, ...]
    sigmas: tuple[float, ...]
    kappas: tuple[float, ...]
    samples_by_length: Mapping[int, int]
    master_seeds: tuple[int, ...]
    familywise_alpha: float = FAMILYWISE_ALPHA
    permutation_replicates: int = 49_999
    multinomial_replicates: int = 49_999
    jobs: int = 1
    name: str = "production-v1"

    def __post_init__(self) -> None:
        if not self.lengths or any(
            isinstance(length, bool)
            or not isinstance(length, int)
            or length < 2
            or length % 2
            for length in self.lengths
        ):
            raise ValueError("lengths must contain positive even integers")
        if len(set(self.lengths)) != len(self.lengths):
            raise ValueError("lengths must be unique")
        for values, name, positive in (
            (self.sigmas, "sigmas", True),
            (self.kappas, "kappas", False),
        ):
            if not values or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or (float(value) <= 0.0 if positive else float(value) < 0.0)
                for value in values
            ):
                raise ValueError(f"{name} contain invalid values")
            if len(set(float(value) for value in values)) != len(values):
                raise ValueError(f"{name} must be unique")
        if set(self.samples_by_length) != set(self.lengths):
            raise ValueError("sample counts must cover every length exactly")
        for count in self.samples_by_length.values():
            _strict_positive_int(count, "sample count")
        required_seeds = max(self.samples_by_length.values())
        if (
            len(self.master_seeds) < required_seeds
            or len(set(self.master_seeds)) != len(self.master_seeds)
            or any(
                isinstance(seed, bool)
                or not isinstance(seed, int)
                or not 0 <= seed < 1 << 64
                for seed in self.master_seeds
            )
        ):
            raise ValueError("master seeds are insufficient, repeated, or invalid")
        if (
            not math.isfinite(float(self.familywise_alpha))
            or not 0.0 < float(self.familywise_alpha) < 1.0
        ):
            raise ValueError("familywise alpha must be in (0, 1)")
        _strict_positive_int(self.permutation_replicates, "permutation replicates")
        _strict_positive_int(self.multinomial_replicates, "multinomial replicates")
        _strict_positive_int(self.jobs, "jobs")

    @classmethod
    def production_v1(cls) -> ValidationProtocol:
        return cls(
            lengths=LENGTHS,
            sigmas=SIGMAS,
            kappas=KAPPAS,
            samples_by_length=dict(SAMPLES_BY_LENGTH),
            master_seeds=MASTER_SEEDS,
        )

    @classmethod
    def reduced(
        cls,
        *,
        lengths: Sequence[int] = (4,),
        sigmas: Sequence[float] = (1.0,),
        kappas: Sequence[float] = (0.0, 0.25),
        samples: int = 8,
        replicates: int = 31,
        jobs: int = 1,
    ) -> ValidationProtocol:
        count = _strict_positive_int(samples, "samples")
        frozen_lengths = tuple(lengths)
        return cls(
            lengths=frozen_lengths,
            sigmas=tuple(float(value) for value in sigmas),
            kappas=tuple(float(value) for value in kappas),
            samples_by_length={length: count for length in frozen_lengths},
            master_seeds=MASTER_SEEDS[:count],
            permutation_replicates=replicates,
            multinomial_replicates=replicates,
            jobs=jobs,
            name="reduced-test-v1",
        )

    @property
    def is_production(self) -> bool:
        return (
            self.name == "production-v1"
            and self.lengths == LENGTHS
            and self.sigmas == SIGMAS
            and self.kappas == KAPPAS
            and dict(self.samples_by_length) == SAMPLES_BY_LENGTH
            and self.master_seeds == MASTER_SEEDS
            and self.familywise_alpha == FAMILYWISE_ALPHA
            and self.permutation_replicates == 49_999
            and self.multinomial_replicates == 49_999
        )

    def require_production(self) -> None:
        if not self.is_production:
            raise ValueError("CLI requires the exact production-v1 protocol")

    @property
    def case_registry(self) -> tuple[ValidationCase, ...]:
        cases: list[ValidationCase] = []
        for length in self.lengths:
            for sigma in self.sigmas:
                for kappa in self.kappas:
                    cases.append(
                        ValidationCase(
                            length=length,
                            sigma=float(sigma),
                            kappa=float(kappa),
                            samples=self.samples_by_length[length],
                            seed_start=self.master_seeds[0],
                        )
                    )
        return tuple(cases)

    @property
    def family_denominators(self) -> dict[str, int]:
        return frozen_family_denominators(self.lengths, self.sigmas, self.kappas)


def _protocol_document(protocol: ValidationProtocol) -> dict[str, object]:
    document = {
        "version": VALIDATION_PROTOCOL_VERSION,
        "name": protocol.name,
        "lengths": list(protocol.lengths),
        "sigmas": [_f64(value) for value in protocol.sigmas],
        "kappas": [_f64(value) for value in protocol.kappas],
        "samples_by_length": {
            str(length): protocol.samples_by_length[length]
            for length in protocol.lengths
        },
        "samplers": list(SAMPLERS),
        "three_way_samplers": list(THREE_WAY_SAMPLERS),
        "master_seeds": list(protocol.master_seeds),
        "familywise_alpha": _f64(protocol.familywise_alpha),
        "family_denominators": protocol.family_denominators,
        "permutation_replicates": protocol.permutation_replicates,
        "multinomial_replicates": protocol.multinomial_replicates,
    }
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    document["sha256"] = hashlib.sha256(encoded).hexdigest()
    return document


def _check(
    family: str,
    case_id: str,
    raw: object,
    expected: object,
    threshold: float,
    margin: float,
    passed: bool,
) -> dict[str, object]:
    if not math.isfinite(float(threshold)) or not math.isfinite(float(margin)):
        raise RuntimeError("check thresholds and margins must be finite")
    return {
        "family": family,
        "case_id": case_id,
        "raw": raw,
        "expected": expected,
        "threshold": float(threshold),
        "margin": float(margin),
        "passed": bool(passed),
    }


def _exact(
    family: str,
    case_id: str,
    raw: object,
    expected: object,
    equal: bool,
    distance: float = 1.0,
) -> dict[str, object]:
    margin = 0.0 if equal else -max(float(distance), np.finfo(float).tiny)
    return _check(family, case_id, raw, expected, 0.0, margin, equal)


def assert_sampler_structure() -> None:
    root = Path(__file__).parent
    modules = ("oracle", "geometric", "poisson_reference", "poisson_sweep")
    forbidden_symbols = {
        "sample_quadratic",
        "sample_geometric",
        "run_poisson_reference",
        "_run_poisson_with_streams",
        "run_poisson_numba",
        "_run_poisson_kernel",
    }
    for module in modules:
        tree = ast.parse((root / f"{module}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            imported_module = node.module.rsplit(".", 1)[-1]
            if imported_module not in modules:
                continue
            imported_names = {alias.name for alias in node.names}
            overlap = imported_names & forbidden_symbols
            if overlap:
                raise RuntimeError(
                    f"{module} imports sampler selection logic "
                    f"from {imported_module}: {sorted(overlap)}"
                )


def _exact_checks(protocol: ValidationProtocol) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    vectors = (
        ((0, 0, 0, 0), (0, 0), (0x6627E8D5, 0xE169C58D, 0xBC57AC4C, 0x9B00DBD8)),
        (
            (0xFFFFFFFF,) * 4,
            (0xFFFFFFFF,) * 2,
            (0x408F276D, 0x41C83B0E, 0xA20BC7C6, 0x6D5451FD),
        ),
    )
    vector_pass = True
    actual_vectors = []
    for counter_words, key_words, expected in vectors:
        counter = np.asarray(counter_words, dtype=np.uint32)
        key = np.asarray(key_words, dtype=np.uint32)
        reference = philox4x32_10_reference(counter, key)
        compiled = np.empty(4, dtype=np.uint32)
        philox4x32_10(counter, key, compiled)
        actual_vectors.append([int(value) for value in compiled])
        vector_pass &= tuple(int(value) for value in reference) == expected
        vector_pass &= np.array_equal(compiled, reference)
    checks.append(
        _exact("philox-vectors", "published-random123", actual_vectors, "published", vector_pass)
    )

    identity = StreamIdentity(194, "validation", 4, "task-8", 0, 0)
    materials = [
        derive_stream_material(replace(identity, stream_id=index))
        for index in range(4)
    ]
    fingerprints = [item.material_sha256 for item in materials]
    checks.append(
        _exact(
            "stream-separation",
            "four-streams",
            fingerprints,
            "four unique digests",
            len(set(fingerprints)) == 4,
        )
    )

    bound = 2**31 + 1
    rejection_threshold = ((1 << 32) - bound) % bound
    tape = (0, 1, rejection_threshold)
    accepted = next(index for index, word in enumerate(tape) if word >= rejection_threshold)
    checks.append(
        _exact(
            "bounded-integer-accounting",
            "finite-tape",
            {"words": accepted + 1, "rejections": accepted},
            {"words": 3, "rejections": 2},
            accepted == 2,
        )
    )

    kernel = periodic_kernel(8, 1.0)
    digest = hashlib.sha256(kernel.tobytes()).hexdigest()
    alias = build_distance_alias(8, 1.0, kernel, digest)
    represented = np.zeros(4)
    for column in range(4):
        represented[column] += alias.probability[column] / 4.0
        represented[alias.alias[column]] += (1.0 - alias.probability[column]) / 4.0
    target = alias.class_weight / alias.total_rate
    alias_error = float(np.max(np.abs(represented - target)))
    checks.append(
        _exact(
            "alias-invariants",
            "L8/sigma-1",
            {"maximum_error": alias_error, "total_rate": alias.total_rate},
            {"maximum_error_lte": 32 * np.finfo(float).eps},
            alias_error <= 32 * np.finfo(float).eps,
            alias_error,
        )
    )

    edge_ids = [
        canonical_edge(256, item.distance, offset)
        for item in distance_classes(256)
        for offset in range(item.multiplicity)
    ]
    expected_edges = 256 * 255 // 2
    unique_edges = len(set(edge_ids))
    checks.append(
        _exact(
            "edge-id-uniqueness",
            "L256",
            {"count": len(edge_ids), "unique": unique_edges},
            expected_edges,
            len(edge_ids) == unique_edges == expected_edges,
        )
    )
    keys, occupied, diagnostics = allocate_edge_set(0)
    inserted = []
    for value in (0, 1, 2**63, 2**64 - 1):
        keys, occupied, fresh = edge_set_insert(keys, occupied, diagnostics, value)
        inserted.append(fresh)
    hash_ok = all(inserted) and int(diagnostics[1]) == 4 and int(diagnostics[4]) > 0
    checks.append(
        _exact(
            "hash-full-range-growth",
            "uint64-extremes",
            diagnostics.tolist(),
            {"size": 4, "grew": True},
            hash_ok,
        )
    )

    graph_residuals = {}
    graph_ok = True
    for length in (4, 6):
        if length not in protocol.lengths and protocol.is_production is False:
            continue
        for sigma in protocol.sigmas:
            for kappa in protocol.kappas:
                outcomes = tuple(enumerate_graphs(ModelSpec(length, sigma, kappa)))
                residual = abs(math.fsum(item.probability for item in outcomes) - 1.0)
                graph_residuals[
                    f"L{length}/{_f64(sigma)}/{_f64(kappa)}"
                ] = residual
                graph_ok &= len(outcomes) == 1 << (length * (length - 1) // 2)
                graph_ok &= residual <= 512 * np.finfo(float).eps
    checks.append(
        _exact(
            "all-graph-exact",
            "L<=6",
            graph_residuals,
            {"maximum_residual_lte": 512 * np.finfo(float).eps},
            graph_ok,
            max(graph_residuals.values(), default=0.0),
        )
    )

    zero_spec = ModelSpec(4, 1.0, 0.0)
    q_zero = sample_quadratic(zero_spec, np.random.default_rng(1))
    g_zero = sample_geometric(zero_spec, np.random.default_rng(2))
    checks.append(
        _exact(
            "kappa-zero",
            "L4",
            [q_zero.edges.shape[0], g_zero.edges.shape[0]],
            [0, 0],
            q_zero.edges.size == 0 and g_zero.edges.size == 0,
        )
    )
    saturated = ModelSpec(4, 1.0, np.finfo(float).max)
    with np.errstate(over="ignore", under="ignore"):
        q_full = sample_quadratic(saturated, np.random.default_rng(3))
        g_full = sample_geometric(saturated, np.random.default_rng(4))
    checks.append(
        _exact(
            "saturated-coupling",
            "L4",
            [len(q_full.edges), len(g_full.edges)],
            [6, 6],
            len(q_full.edges) == len(g_full.edges) == 6,
        )
    )
    antipodes = distance_classes(256)[-1].multiplicity
    checks.append(
        _exact("antipodal-counts", "L256", antipodes, 128, antipodes == 128)
    )
    extreme_ok = True
    extreme_raw = []
    for sigma in (math.ulp(1.0), 128.0):
        values = periodic_kernel(8, sigma)
        extreme_raw.append([float(values.min()), float(values.max())])
        extreme_ok &= bool(np.all(np.isfinite(values)) and np.all(values > 0.0))
    checks.append(
        _exact(
            "finite-parameter-extremes",
            "tiny-huge-sigma",
            extreme_raw,
            "finite positive kernels",
            extreme_ok,
        )
    )

    duplicate_request, duplicate_kernel, duplicate_alias = _poisson_inputs(
        4, 1.0, 6.0, 194, 0, "numba"
    )
    duplicate_result = run_poisson_numba(
        duplicate_request, duplicate_kernel, duplicate_alias
    )
    duplicate_ok = (
        duplicate_result.duplicate_count <= duplicate_result.event_count
        and duplicate_result.observables[-1, 0] <= 6
    )
    checks.append(
        _exact(
            "duplicate-limits",
            "L4/kappa-6",
            {
                "events": duplicate_result.event_count,
                "duplicates": duplicate_result.duplicate_count,
                "open": int(duplicate_result.observables[-1, 0]),
            },
            {"duplicates_lte_events": True, "open_lte": 6},
            duplicate_ok,
        )
    )

    parent, size, masks, moments, counts = allocate_union_find(8)
    for left, right in ((0, 1), (2, 3), (1, 2), (4, 7)):
        counts[0] += 1
        union_incremental(parent, size, masks, moments, counts, left, right)
    scanned = scan_basic_observables(parent, size, masks, moments, counts)
    moments_ok = (
        scanned.sum_size_sq == moments[0]
        and scanned.sum_size_fourth == moments[1]
    )
    checks.append(
        _exact(
            "incremental-root-scan",
            "scripted-unions",
            [scanned.sum_size_sq, scanned.sum_size_fourth],
            moments.tolist(),
            moments_ok,
        )
    )

    requests = [
        _poisson_inputs(4, 1.0, 0.7, 194, replica, "numba")
        for replica in (1, 2)
    ]
    forward = [
        run_poisson_numba(request, values, table).observables.tobytes()
        for request, values, table in requests
    ]
    reverse = {
        request.replica: run_poisson_numba(request, values, table).observables.tobytes()
        for request, values, table in reversed(requests)
    }
    order_ok = all(
        raw == reverse[request[0].replica]
        for raw, request in zip(forward, requests, strict=True)
    )
    checks.append(
        _exact(
            "process-order-identity",
            "replicas-1-2",
            [hashlib.sha256(raw).hexdigest() for raw in forward],
            "same hashes in reverse order",
            order_ok,
        )
    )
    try:
        assert_sampler_structure()
    except Exception as error:
        checks.append(
            _exact(
                "sampler-structure",
                "four-sampler-modules",
                {"error": f"{type(error).__name__}: {error}"},
                "no shared sampler selection logic",
                False,
            )
        )
    else:
        checks.append(
            _exact(
                "sampler-structure",
                "four-sampler-modules",
                "independent",
                "independent",
                True,
            )
        )
    return checks


def _poisson_inputs(
    length: int,
    sigma: float,
    kappa: float,
    master_seed: int,
    replica: int,
    implementation: str,
):
    kernel = periodic_kernel(length, sigma)
    digest = hashlib.sha256(kernel.tobytes()).hexdigest()
    request = TrajectoryRequest(
        length=length,
        sigma=sigma,
        sigma_grid_id=f"task-8-{implementation}-sigma-{_f64(sigma)}",
        kappas=np.asarray((kappa,), dtype=np.float64),
        master_seed=master_seed,
        phase="validation",
        replica=replica,
        kernel_sha256=digest,
    )
    return request, kernel, build_distance_alias(length, sigma, kernel, digest)


def _graph_observables(length: int, edges: np.ndarray, labels: np.ndarray) -> np.ndarray:
    sizes = sorted(
        (
            int(value)
            for value in np.bincount(labels)
            if int(value) > 0
        ),
        reverse=True,
    )
    largest = sizes[0]
    second = sizes[1] if len(sizes) > 1 else 0
    sum_sq = math.fsum(float(value) ** 2 for value in sizes)
    sum_fourth = math.fsum(float(value) ** 4 for value in sizes)
    masks: dict[int, int] = {}
    for vertex, label in enumerate(labels.tolist()):
        masks[label] = masks.get(label, 0) | (1 << min(3, (4 * vertex) // length))
    return np.asarray(
        (
            len(edges),
            len(sizes),
            largest,
            second,
            largest / length,
            second / length,
            sum_sq,
            sum_fourth,
            sum_fourth / (sum_sq * sum_sq),
            float(any(mask == 0b1111 for mask in masks.values())),
        ),
        dtype=np.float64,
    )


class _AuditStream:
    def __init__(self, identity: StreamIdentity):
        material = derive_stream_material(identity)
        self._key = material.key
        self._counter = material.initial_counter.copy()
        self._block = np.zeros(4, dtype=np.uint32)
        self._lane = 4

    def word(self) -> int:
        if self._lane == 4:
            self._block[:] = philox4x32_10_reference(
                self._counter, self._key
            )
            carry = 1
            for index in range(4):
                total = int(self._counter[index]) + carry
                self._counter[index] = np.uint32(total & 0xFFFFFFFF)
                carry = total >> 32
            self._lane = 0
        value = int(self._block[self._lane])
        self._lane += 1
        return value

    def uniform(self) -> float:
        return (float(self.word()) + 0.5) * (2.0**-32)

    def bounded(self, bound: int) -> int:
        threshold = ((1 << 32) - bound) % bound
        while True:
            word = self.word()
            if word >= threshold:
                return word % bound


def _audit_numba_terminal(
    request: TrajectoryRequest,
    table,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    streams = [
        _AuditStream(
            StreamIdentity(
                request.master_seed,
                request.phase,
                request.length,
                request.sigma_grid_id,
                request.replica,
                stream_id,
            )
        )
        for stream_id in range(4)
    ]
    starts = np.cumsum(
        [0, *(int(value) for value in table.multiplicity)],
        dtype=np.int64,
    )
    open_ids: set[int] = set()
    current = 0.0
    terminal = float(request.kappas[-1])
    event_count = 0
    duplicate_count = 0
    class_count = len(table.probability)
    column_rejection = ((1 << 32) - class_count) % class_count
    while terminal > 0.0:
        hazard = -math.log(streams[3].uniform())
        if hazard > (terminal - current) * float(table.total_rate):
            break
        current += hazard / float(table.total_rate)
        while True:
            column_word = streams[0].word()
            product = column_word * class_count
            if (product & 0xFFFFFFFF) >= column_rejection:
                column = product >> 32
                break
        threshold = streams[1].uniform()
        selected = (
            column
            if threshold <= float(table.probability[column])
            else int(table.alias[column])
        )
        offset = streams[2].bounded(int(table.multiplicity[selected]))
        edge_id = int(starts[selected]) + offset
        event_count += 1
        if edge_id in open_ids:
            duplicate_count += 1
        else:
            open_ids.add(edge_id)

    edges = []
    connectivity = UnionFind(request.length)
    for edge_id in sorted(open_ids):
        selected = int(np.searchsorted(starts, edge_id, side="right") - 1)
        offset = edge_id - int(starts[selected])
        edge = canonical_edge(request.length, selected + 1, offset)
        edges.append(edge)
        connectivity.union(*edge)
    edge_array = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
    return (
        _graph_observables(
            request.length, edge_array, connectivity.labels()
        ),
        edge_array,
        event_count,
        duplicate_count,
    )


def _bond_counts(length: int, edges: Iterable[Sequence[int]]) -> np.ndarray:
    counts = np.zeros(length // 2, dtype=np.int64)
    for left, right in edges:
        separation = int(right) - int(left)
        counts[min(separation, length - separation) - 1] += 1
    return counts


@dataclass
class _Samples:
    observables: dict[str, np.ndarray]
    bonds: dict[str, np.ndarray]
    partitions: dict[str, np.ndarray]
    edge_classes: dict[str, np.ndarray]
    events: dict[str, int]
    graph_masks: dict[str, np.ndarray]


def _draw_case(case: ValidationCase, seeds: tuple[int, ...]) -> _Samples:
    n = case.samples
    length = case.length
    observables = {
        sampler: np.empty((n, 10), dtype=np.float64) for sampler in SAMPLERS
    }
    bonds = {
        sampler: np.zeros(length // 2, dtype=np.int64)
        for sampler in SAMPLERS
    }
    partitions = {
        sampler: np.zeros(length, dtype=np.int64)
        for sampler in SAMPLERS
    }
    edge_classes = {
        sampler: np.zeros(length // 2, dtype=np.int64)
        for sampler in SAMPLERS
    }
    events = {"poisson-reference": 0, "poisson-numba": 0}
    graph_masks = (
        {
            sampler: np.zeros(
                1 << (length * (length - 1) // 2), dtype=np.int64
            )
            for sampler in SAMPLERS
        }
        if length <= 6
        else {}
    )
    edge_positions = (
        {edge: index for index, edge in enumerate(iter_unordered_edges(length))}
        if length <= 6
        else {}
    )
    starts = np.cumsum(
        [0, *(item.multiplicity for item in distance_classes(length))],
        dtype=np.int64,
    )

    for replica, seed in enumerate(seeds[:n]):
        spec = ModelSpec(length, case.sigma, case.kappa)
        q_rng = np.random.Generator(np.random.PCG64(seed ^ 0x5155414452415449))
        g_rng = np.random.Generator(np.random.PCG64(seed ^ 0x47454F4D45545249))
        quadratic = sample_quadratic(spec, q_rng)
        geometric = sample_geometric(spec, g_rng)
        for name, sample in (("quadratic", quadratic), ("geometric", geometric)):
            observables[name][replica] = _graph_observables(
                length, sample.edges, sample.labels
            )
            class_counts = _bond_counts(length, sample.edges)
            bonds[name] += class_counts
            edge_classes[name] += class_counts
            component_count = int(observables[name][replica, 1])
            partitions[name][component_count - 1] += 1
            if length <= 6:
                mask = sum(1 << edge_positions[tuple(edge)] for edge in sample.edges)
                graph_masks[name][mask] += 1

        ref_request, kernel, _ = _poisson_inputs(
            length, case.sigma, case.kappa, seed, replica, "reference"
        )
        streams = _build_reference_streams(ref_request)
        reference_run = _run_poisson_with_streams(ref_request, kernel, streams)
        reference = reference_run.result
        observables["poisson-reference"][replica] = reference.observables[0]
        events["poisson-reference"] += reference.event_count
        ids = reference_run.edge_ids_by_checkpoint[0]
        ref_classes = np.zeros(length // 2, dtype=np.int64)
        for edge_id in ids:
            class_index = int(np.searchsorted(starts, edge_id, side="right") - 1)
            ref_classes[class_index] += 1
        if length <= 6:
            reference_mask = 0
            for edge_id in ids:
                class_index = int(np.searchsorted(starts, edge_id, side="right") - 1)
                offset = int(edge_id - starts[class_index])
                edge = canonical_edge(length, class_index + 1, offset)
                reference_mask |= 1 << edge_positions[edge]
            graph_masks["poisson-reference"][reference_mask] += 1
        bonds["poisson-reference"] += ref_classes
        edge_classes["poisson-reference"] += ref_classes
        partitions["poisson-reference"][
            int(reference.observables[0, 1]) - 1
        ] += 1

        numba_request, kernel, table = _poisson_inputs(
            length, case.sigma, case.kappa, seed, replica, "numba"
        )
        numba_result = run_poisson_numba(numba_request, kernel, table)
        observables["poisson-numba"][replica] = numba_result.observables[0]
        events["poisson-numba"] += numba_result.event_count
        (
            audit_observables,
            audit_edges,
            audit_events,
            audit_duplicates,
        ) = _audit_numba_terminal(numba_request, table)
        if (
            not np.array_equal(audit_observables, numba_result.observables[0])
            or audit_events != numba_result.event_count
            or audit_duplicates != numba_result.duplicate_count
        ):
            raise RuntimeError(
                "independent Numba edge audit disagrees with production output"
            )
        numba_classes = _bond_counts(length, audit_edges)
        bonds["poisson-numba"] += numba_classes
        edge_classes["poisson-numba"] += numba_classes
        partitions["poisson-numba"][
            int(numba_result.observables[0, 1]) - 1
        ] += 1
        if length <= 6:
            mask = sum(
                1 << edge_positions[tuple(edge)] for edge in audit_edges
            )
            graph_masks["poisson-numba"][mask] += 1

    return _Samples(
        observables, bonds, partitions, edge_classes, events, graph_masks
    )


def _poisson_two_sided(observed: int, expected: float) -> float:
    if expected == 0.0:
        return 1.0 if observed == 0 else 0.0
    lower = float(poisson.cdf(observed, expected))
    upper = float(poisson.sf(observed - 1, expected))
    return min(1.0, 2.0 * min(lower, upper))


def _permutation_pvalue(
    left: np.ndarray,
    right: np.ndarray,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    statistic = abs(float(np.mean(left) - np.mean(right)))
    pooled = np.concatenate((left, right))
    rng = np.random.Generator(np.random.Philox(seed))
    exceed = 0
    for _ in range(replicates):
        order = rng.permutation(pooled.size)
        permuted = abs(
            float(np.mean(pooled[order[: left.size]]))
            - float(np.mean(pooled[order[left.size :]]))
        )
        exceed += int(permuted >= statistic)
    return statistic, (exceed + 1.0) / (replicates + 1.0)


def _g_statistic(counts: np.ndarray, expected: np.ndarray) -> float:
    mask = counts > 0
    if np.any(expected[mask] <= 0.0):
        return math.inf
    return float(2.0 * np.sum(counts[mask] * np.log(counts[mask] / expected[mask])))


def _multinomial_pvalue(
    left: np.ndarray,
    right: np.ndarray,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    left = np.asarray(left, dtype=np.int64)
    right = np.asarray(right, dtype=np.int64)
    pooled = left + right
    total = int(pooled.sum())
    if total == 0:
        return 0.0, 1.0
    probability = pooled / total
    expected_left = probability * int(left.sum())
    expected_right = probability * int(right.sum())
    statistic = _g_statistic(left, expected_left) + _g_statistic(right, expected_right)
    rng = np.random.Generator(np.random.Philox(seed))
    exceed = 0
    for _ in range(replicates):
        simulated_left = rng.multinomial(int(left.sum()), probability)
        simulated_right = rng.multinomial(int(right.sum()), probability)
        simulated = _g_statistic(simulated_left, expected_left) + _g_statistic(
            simulated_right, expected_right
        )
        exceed += int(simulated >= statistic)
    return statistic, (exceed + 1.0) / (replicates + 1.0)


def _statistical_checks(
    protocol: ValidationProtocol,
    case: ValidationCase,
    samples: _Samples,
    case_index: int,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    denominators = protocol.family_denominators
    kernel = periodic_kernel(case.length, case.sigma)
    probabilities = edge_probabilities(
        ModelSpec(case.length, case.sigma, case.kappa), kernel
    )
    multiplicities = np.asarray(
        [item.multiplicity for item in distance_classes(case.length)],
        dtype=np.int64,
    )
    if case.length <= 6:
        outcomes = tuple(
            enumerate_graphs(
                ModelSpec(case.length, case.sigma, case.kappa)
            )
        )
        threshold = (
            protocol.familywise_alpha
            / denominators["all-graph-probability"]
        )
        for sampler in THREE_WAY_SAMPLERS:
            counts = samples.graph_masks[sampler]
            for outcome in outcomes:
                count = int(counts[outcome.mask])
                pvalue = float(
                    binomtest(
                        count,
                        case.samples,
                        outcome.probability,
                        alternative="two-sided",
                    ).pvalue
                )
                checks.append(
                    _check(
                        "all-graph-probability",
                        f"{case.case_id}/{sampler}/mask-{outcome.mask}",
                        {
                            "successes": count,
                            "trials": case.samples,
                            "pvalue": pvalue,
                        },
                        {"probability": outcome.probability},
                        threshold,
                        pvalue - threshold,
                        pvalue >= threshold,
                    )
                )
    for sampler in THREE_WAY_SAMPLERS:
        for class_index, (count, probability, multiplicity) in enumerate(
            zip(
                samples.edge_classes[sampler],
                probabilities,
                multiplicities,
                strict=True,
            )
        ):
            trials = case.samples * int(multiplicity)
            pvalue = float(
                binomtest(int(count), trials, float(probability), alternative="two-sided").pvalue
            )
            threshold = protocol.familywise_alpha / denominators["edge-class-frequency"]
            checks.append(
                _check(
                    "edge-class-frequency",
                    f"{case.case_id}/{sampler}/d{class_index + 1}",
                    {"successes": int(count), "trials": trials, "pvalue": pvalue},
                    {"probability": float(probability)},
                    threshold,
                    pvalue - threshold,
                    pvalue >= threshold,
                )
            )

    total_rate = math.fsum(
        float(count) * float(rate)
        for count, rate in zip(multiplicities, kernel, strict=True)
    )
    for sampler in ("poisson-reference", "poisson-numba"):
        expected_events = case.samples * case.kappa * total_rate
        count = samples.events[sampler]
        pvalue = _poisson_two_sided(count, expected_events)
        threshold = protocol.familywise_alpha / denominators["poisson-event-count"]
        checks.append(
            _check(
                "poisson-event-count",
                f"{case.case_id}/{sampler}",
                {"count": count, "pvalue": pvalue},
                {"mean": expected_events},
                threshold,
                pvalue - threshold,
                pvalue >= threshold,
            )
        )

    p_none = no_edge_probability(ModelSpec(case.length, case.sigma, case.kappa))
    for sampler in SAMPLERS:
        no_edges = int(np.count_nonzero(samples.observables[sampler][:, 0] == 0.0))
        pvalue = float(
            binomtest(no_edges, case.samples, p_none, alternative="two-sided").pvalue
        )
        threshold = protocol.familywise_alpha / denominators["no-edge"]
        checks.append(
            _check(
                "no-edge",
                f"{case.case_id}/{sampler}",
                {"successes": no_edges, "trials": case.samples, "pvalue": pvalue},
                {"probability": p_none},
                threshold,
                pvalue - threshold,
                pvalue >= threshold,
            )
        )

    for pair_index, (left, right) in enumerate(PAIR_NAMES):
        for family, column in SCALAR_COLUMNS.items():
            statistic, pvalue = _permutation_pvalue(
                samples.observables[left][:, column],
                samples.observables[right][:, column],
                protocol.permutation_replicates,
                protocol.master_seeds[0] + case_index * 1000 + pair_index * 100 + column,
            )
            threshold = protocol.familywise_alpha / denominators[family]
            checks.append(
                _check(
                    family,
                    f"{case.case_id}/{left}-vs-{right}",
                    {
                        "left_sum": float(np.sum(samples.observables[left][:, column])),
                        "right_sum": float(np.sum(samples.observables[right][:, column])),
                        "left_count": case.samples,
                        "right_count": case.samples,
                        "statistic": statistic,
                        "replicates": protocol.permutation_replicates,
                        "pvalue": pvalue,
                        "seed": protocol.master_seeds[0]
                        + case_index * 1000
                        + pair_index * 100
                        + column,
                    },
                    {"equal_means": True},
                    threshold,
                    pvalue - threshold,
                    pvalue >= threshold,
                )
            )

        left_bonds = samples.bonds[left]
        right_bonds = samples.bonds[right]
        statistic, pvalue = _multinomial_pvalue(
            left_bonds,
            right_bonds,
            protocol.multinomial_replicates,
            protocol.master_seeds[0] + case_index * 1000 + pair_index * 100 + 50,
        )
        threshold = protocol.familywise_alpha / denominators["bond-length"]
        checks.append(
            _check(
                "bond-length",
                f"{case.case_id}/{left}-vs-{right}",
                {
                    "left_bins": left_bonds.tolist(),
                    "right_bins": right_bonds.tolist(),
                    "statistic": statistic,
                    "replicates": protocol.multinomial_replicates,
                    "pvalue": pvalue,
                    "seed": protocol.master_seeds[0]
                    + case_index * 1000
                    + pair_index * 100
                    + 50,
                },
                {"pooled_null": True},
                threshold,
                pvalue - threshold,
                pvalue >= threshold,
            )
        )
        left_partition = samples.partitions[left]
        right_partition = samples.partitions[right]
        statistic, pvalue = _multinomial_pvalue(
            left_partition,
            right_partition,
            protocol.multinomial_replicates,
            protocol.master_seeds[0] + case_index * 1000 + pair_index * 100 + 51,
        )
        threshold = protocol.familywise_alpha / denominators["component-partition"]
        checks.append(
            _check(
                "component-partition",
                f"{case.case_id}/{left}-vs-{right}",
                {
                    "bins": list(range(1, case.length + 1)),
                    "left_counts": left_partition.tolist(),
                    "right_counts": right_partition.tolist(),
                    "statistic": statistic,
                    "replicates": protocol.multinomial_replicates,
                    "pvalue": pvalue,
                    "seed": protocol.master_seeds[0]
                    + case_index * 1000
                    + pair_index * 100
                    + 51,
                },
                {"pooled_null": True},
                threshold,
                pvalue - threshold,
                pvalue >= threshold,
            )
        )
    return checks


def _repository_state() -> dict[str, object]:
    root = Path(__file__).resolve()
    while root != root.parent and not (root / ".git").exists():
        root = root.parent
    try:
        revision = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ("git", "status", "--porcelain"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        return {
            "source_revision": "unavailable",
            "clean_tree": False,
            "provenance_error": f"{type(error).__name__}: {error}",
        }
    return {
        "source_revision": revision,
        "clean_tree": not bool(status),
        "provenance_error": None,
    }


def canonical_report_bytes(report: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"report is not canonical finite JSON: {error}") from error


def _atomic_publish(output: Path, payload: bytes) -> None:
    if not isinstance(output, Path):
        raise ValueError("output must be a pathlib.Path")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise RuntimeError("refusing to publish through a symlink")
    if output.exists() and not output.is_file():
        raise RuntimeError("output must be a regular file")
    temporary = output.parent / f".{output.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        os.replace(temporary, output)
        directory_fd = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def payload_without_elapsed(report: Mapping[str, object]) -> dict[str, object]:
    payload = dict(report)
    payload.pop("elapsed_seconds", None)
    return payload


def _run_case_checks(
    protocol: ValidationProtocol,
    indexed_case: tuple[int, ValidationCase],
) -> list[dict[str, object]]:
    case_index, case = indexed_case
    samples = _draw_case(case, protocol.master_seeds[: case.samples])
    return _statistical_checks(protocol, case, samples, case_index)


def run_production_validation(
    protocol: ValidationProtocol,
    output: Path,
) -> dict[str, object]:
    if not isinstance(protocol, ValidationProtocol):
        raise ValueError("protocol must be a ValidationProtocol")
    started = time.perf_counter()
    denominators = protocol.family_denominators
    checks: list[dict[str, object]] = []
    try:
        checks.extend(_exact_checks(protocol))
    except Exception as error:
        checks.append(
            _exact(
                "backend-integrity",
                "exact-checks",
                {"error": f"{type(error).__name__}: {error}"},
                "all exact checks completed",
                False,
            )
        )

    indexed_cases = tuple(enumerate(protocol.case_registry))
    if protocol.jobs == 1:
        outcomes: Iterable[list[dict[str, object]] | Exception] = []
        serial_outcomes: list[list[dict[str, object]] | Exception] = []
        for indexed_case in indexed_cases:
            try:
                serial_outcomes.append(_run_case_checks(protocol, indexed_case))
            except Exception as error:
                serial_outcomes.append(error)
        outcomes = serial_outcomes
    else:
        with ThreadPoolExecutor(max_workers=protocol.jobs) as executor:
            futures = [
                executor.submit(_run_case_checks, protocol, indexed_case)
                for indexed_case in indexed_cases
            ]
            parallel_outcomes: list[list[dict[str, object]] | Exception] = []
            for future in futures:
                try:
                    parallel_outcomes.append(future.result())
                except Exception as error:
                    parallel_outcomes.append(error)
            outcomes = parallel_outcomes
    for (_, case), outcome in zip(indexed_cases, outcomes, strict=True):
        if isinstance(outcome, Exception):
            checks.append(
                _exact(
                    "backend-integrity",
                    case.case_id,
                    {
                        "error": (
                            f"{type(outcome).__name__}: {outcome}"
                        )
                    },
                    "all four backends returned valid data",
                    False,
                )
            )
        else:
            checks.extend(outcome)

    present = {item["family"] for item in checks}
    required = set(EXACT_FAMILIES) | set(STATISTICAL_FAMILIES)
    for family in sorted(required - present):
        checks.append(
            _exact(
                "missing-family",
                family,
                {"missing": family},
                "at least one completed check",
                False,
            )
        )

    checks.sort(key=lambda item: (str(item["family"]), str(item["case_id"])))
    margins = [float(item["margin"]) for item in checks]
    report: dict[str, object] = {
        "schema_version": VALIDATION_PROTOCOL_VERSION,
        "protocol": _protocol_document(protocol),
        "runtime_capability": runtime_capability(),
        "source": _repository_state(),
        "checks": checks,
        "family_count": len({str(item["family"]) for item in checks}),
        "minimum_margin": min(margins),
        "passed": all(bool(item["passed"]) for item in checks)
        and required <= {str(item["family"]) for item in checks},
        "elapsed_seconds": float(time.perf_counter() - started),
    }
    _atomic_publish(output, canonical_report_bytes(report))
    return report
