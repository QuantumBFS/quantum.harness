#!/usr/bin/env python3
"""Deterministic rank-3 versus full-word rebuild kernel benchmark.

The default grid is intended for a scheduled benchmark job, not a login node.
Every timed reference operation reconstructs T from the complete word with
structured_product and then calls factor_dense. The fast operation applies the
rank-3 formula to the same state and candidate. Insert and its corresponding
endpoint delete are benchmarked separately.

BLAS thread variables are forced to one before NumPy or the CTQMC module is
imported.
"""
from __future__ import annotations

import os

_BLAS_THREAD_ENV = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
for _name in _BLAS_THREAD_ENV:
    os.environ[_name] = "1"

import argparse
import contextlib
import gc
import hashlib
import io
import json
import math
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import scipy

import large_lattice_ctqmc as ctqmc


ALGORITHM_ID = "rank3-vs-full-word-rebuild-v1"
DEFAULT_SIZES = (4, 8, 12, 16)
DEFAULT_BETA = 4.0
DEFAULT_SEED = 121_730_001
DEFAULT_REPEATS = 9
DEFAULT_WARMUP = 2
DEFAULT_CONDITION_MAX = 1.0e12
FROZEN_MODEL = {
    "epsilon": 0.01,
    "kappa": 0.02,
    "s": 0.25,
    "g_A": 0.25,
    "g_B": 0.25,
}
CORRECTNESS_THRESHOLDS = {
    "matrix_relative_inf": 1.0e-9,
    "logdet_absolute": 1.0e-9,
    "det_ratio_relative": 1.0e-9,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def source_commit() -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root(),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if len(value) == 40 else None


def numpy_configuration() -> str:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        np.__config__.show()
    return stream.getvalue()


def optional_threadpool_info() -> Optional[List[Mapping[str, Any]]]:
    try:
        from threadpoolctl import threadpool_info
    except ImportError:
        return None
    result: List[Mapping[str, Any]] = []
    for item in threadpool_info():
        result.append({
            str(key): value
            for key, value in item.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        })
    return result


def finite_or_none(value: float) -> Optional[float]:
    value = float(value)
    return value if math.isfinite(value) else None


def assert_finite_json(value: Any, path: str = "root") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite JSON value at {path}")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            assert_finite_json(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_finite_json(child, f"{path}[{index}]")


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_resource_tsv(
    path: Path, wall_seconds: float, max_rss_kb: Optional[int]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rss = 0 if max_rss_kb is None else int(max_rss_kb)
    if not math.isfinite(wall_seconds) or wall_seconds < 0 or rss <= 0:
        raise ValueError("invalid resource measurement")
    raw = (
        f"elapsed_seconds\t{wall_seconds:.17g}\n"
        f"max_rss_kb\t{rss}\n"
    )
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def relative_inf_error(actual: np.ndarray, reference: np.ndarray) -> float:
    return float(
        np.linalg.norm(actual - reference, np.inf)
        / max(1.0, np.linalg.norm(reference, np.inf))
    )


def word_digest(word: Sequence[ctqmc.Event]) -> str:
    raw = json.dumps(
        [event.to_json() for event in word],
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def build_catalog() -> List[ctqmc.LocalVertex]:
    return ctqmc.build_vertex_catalog(
        FROZEN_MODEL["epsilon"],
        FROZEN_MODEL["kappa"],
        FROZEN_MODEL["s"],
        FROZEN_MODEL["g_A"],
        FROZEN_MODEL["g_B"],
    )


def sample_event(
    rng: np.random.Generator,
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
) -> ctqmc.Event:
    triangle_id = int(rng.integers(geometry.n_triangles))
    vertex_id = int(rng.integers(len(catalog)))
    return ctqmc.Event(triangle_id, vertex_id)


def dense_word_factors(
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
    word: Sequence[ctqmc.Event],
) -> ctqmc.DenseFactors:
    product = ctqmc.structured_product(
        geometry.n_sites,
        geometry.triangles,
        catalog,
        word,
    )
    return ctqmc.factor_dense(product)


def timed_call(function: Any) -> Tuple[Any, int]:
    started = time.perf_counter_ns()
    result = function()
    elapsed = time.perf_counter_ns() - started
    return result, int(elapsed)


def fast_left_update(
    factors: ctqmc.DenseFactors,
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
    event: ctqmc.Event,
    block: np.ndarray,
    fallback_word: Sequence[ctqmc.Event],
    condition_max: float,
) -> Tuple[ctqmc.DenseFactors, float, Mapping[str, Any]]:
    triangle = geometry.triangles[event.triangle_id]
    proposal = ctqmc.low_rank_left_proposal(
        factors,
        triangle.sites,
        block,
        condition_max=condition_max,
    )
    metadata: Dict[str, Any] = {
        "fallback": False,
        "proposal_condition": finite_or_none(proposal.condition),
        "local_solve_residual_inf":
            finite_or_none(proposal.local_solve_residual_inf),
    }
    if proposal.needs_rebuild:
        rebuilt = dense_word_factors(geometry, catalog, fallback_word)
        metadata["fallback"] = True
        return rebuilt, float(rebuilt.logdet - factors.logdet), metadata
    if proposal.zero_weight:
        raise ctqmc.NumericalStabilityError(
            "strict-support benchmark encountered zero weight"
        )
    updated = ctqmc.apply_low_rank_proposal(factors, proposal)
    return updated, float(proposal.log_det_ratio), metadata


def update_error(
    fast: ctqmc.DenseFactors,
    dense: ctqmc.DenseFactors,
    fast_log_ratio: float,
    dense_log_ratio: float,
) -> Mapping[str, float]:
    return {
        "T_relative_inf": relative_inf_error(fast.T, dense.T),
        "Q_relative_inf": relative_inf_error(fast.Q, dense.Q),
        "logdet_absolute": abs(float(fast.logdet - dense.logdet)),
        "log_ratio_absolute": abs(float(fast_log_ratio - dense_log_ratio)),
        "det_ratio_relative": abs(
            math.expm1(float(fast_log_ratio - dense_log_ratio))
        ),
    }


def max_error(samples: Sequence[Mapping[str, float]]) -> Mapping[str, float]:
    names = (
        "T_relative_inf",
        "Q_relative_inf",
        "logdet_absolute",
        "log_ratio_absolute",
        "det_ratio_relative",
    )
    return {
        name: max(float(sample[name]) for sample in samples)
        for name in names
    }


def correctness_pass(
    insert_error: Mapping[str, float],
    delete_error: Mapping[str, float],
) -> bool:
    for error in (insert_error, delete_error):
        if error["T_relative_inf"] > CORRECTNESS_THRESHOLDS["matrix_relative_inf"]:
            return False
        if error["Q_relative_inf"] > CORRECTNESS_THRESHOLDS["matrix_relative_inf"]:
            return False
        if error["logdet_absolute"] > CORRECTNESS_THRESHOLDS["logdet_absolute"]:
            return False
        if error["log_ratio_absolute"] > CORRECTNESS_THRESHOLDS["logdet_absolute"]:
            return False
        if error["det_ratio_relative"] > CORRECTNESS_THRESHOLDS["det_ratio_relative"]:
            return False
    return True


def latency_summary(samples_ns: Sequence[int]) -> Mapping[str, Any]:
    values = [int(value) for value in samples_ns]
    return {
        "median_ns": float(statistics.median(values)),
        "minimum_ns": min(values),
        "maximum_ns": max(values),
        "samples_ns": values,
    }


def benchmark_size(
    L: int,
    beta: float,
    seed: int,
    repeats: int,
    warmup: int,
    condition_max: float = DEFAULT_CONDITION_MAX,
) -> Mapping[str, Any]:
    if L < 2:
        raise ValueError("L must be at least 2")
    if beta <= 0.0:
        raise ValueError("beta must be positive")
    if repeats < 1 or warmup < 0:
        raise ValueError("repeats must be positive and warmup nonnegative")
    geometry = ctqmc.build_triangular_geometry(L, L)
    catalog = build_catalog()
    order = int(math.ceil(beta * geometry.n_sites))
    local_seed = int(seed + 1_000_003 * L)
    rng = np.random.Generator(np.random.PCG64DXSM(local_seed))
    base_word = tuple(
        sample_event(rng, geometry, catalog) for _ in range(order)
    )
    candidates = tuple(
        sample_event(rng, geometry, catalog)
        for _ in range(warmup + repeats)
    )
    base_factors = dense_word_factors(geometry, catalog, base_word)

    fast_insert_ns: List[int] = []
    dense_insert_ns: List[int] = []
    fast_delete_ns: List[int] = []
    dense_delete_ns: List[int] = []
    insert_errors: List[Mapping[str, float]] = []
    delete_errors: List[Mapping[str, float]] = []
    fallback_counts = {"insert": 0, "delete": 0}
    finite_conditions: List[float] = []
    finite_local_residuals: List[float] = []
    nonfinite_condition_count = 0
    nonfinite_local_residual_count = 0

    def one_iteration(
        candidate: ctqmc.Event,
        timed: bool,
        reverse_order: bool,
    ) -> None:
        nonlocal nonfinite_condition_count, nonfinite_local_residual_count
        vertex = catalog[candidate.vertex_id]
        inserted_word = base_word + (candidate,)

        def fast_insert_call() -> Tuple[ctqmc.DenseFactors, float, Mapping[str, Any]]:
            return fast_left_update(
                base_factors,
                geometry,
                catalog,
                candidate,
                vertex.block,
                inserted_word,
                condition_max,
            )

        def dense_insert_call() -> ctqmc.DenseFactors:
            return dense_word_factors(geometry, catalog, inserted_word)

        if reverse_order:
            dense_insert, dense_i_ns = timed_call(dense_insert_call)
            fast_insert, fast_i_ns = timed_call(fast_insert_call)
        else:
            fast_insert, fast_i_ns = timed_call(fast_insert_call)
            dense_insert, dense_i_ns = timed_call(dense_insert_call)
        fast_insert_factors, fast_insert_ratio, insert_metadata = fast_insert
        dense_insert_ratio = float(dense_insert.logdet - base_factors.logdet)

        def fast_delete_call() -> Tuple[ctqmc.DenseFactors, float, Mapping[str, Any]]:
            return fast_left_update(
                fast_insert_factors,
                geometry,
                catalog,
                candidate,
                vertex.block_inv,
                base_word,
                condition_max,
            )

        def dense_delete_call() -> ctqmc.DenseFactors:
            return dense_word_factors(geometry, catalog, base_word)

        if reverse_order:
            fast_delete, fast_d_ns = timed_call(fast_delete_call)
            dense_delete, dense_d_ns = timed_call(dense_delete_call)
        else:
            dense_delete, dense_d_ns = timed_call(dense_delete_call)
            fast_delete, fast_d_ns = timed_call(fast_delete_call)
        fast_delete_factors, fast_delete_ratio, delete_metadata = fast_delete
        dense_delete_ratio = float(
            dense_delete.logdet - dense_insert.logdet
        )

        if not timed:
            return
        fast_insert_ns.append(fast_i_ns)
        dense_insert_ns.append(dense_i_ns)
        fast_delete_ns.append(fast_d_ns)
        dense_delete_ns.append(dense_d_ns)
        insert_errors.append(update_error(
            fast_insert_factors,
            dense_insert,
            fast_insert_ratio,
            dense_insert_ratio,
        ))
        delete_errors.append(update_error(
            fast_delete_factors,
            dense_delete,
            fast_delete_ratio,
            dense_delete_ratio,
        ))
        for move, metadata in (
            ("insert", insert_metadata),
            ("delete", delete_metadata),
        ):
            fallback_counts[move] += int(bool(metadata["fallback"]))
            condition = metadata["proposal_condition"]
            residual = metadata["local_solve_residual_inf"]
            if condition is None:
                nonfinite_condition_count += 1
            else:
                finite_conditions.append(float(condition))
            if residual is None:
                nonfinite_local_residual_count += 1
            else:
                finite_local_residuals.append(float(residual))

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for index, candidate in enumerate(candidates[:warmup]):
            one_iteration(candidate, timed=False, reverse_order=bool(index % 2))
        for index, candidate in enumerate(candidates[warmup:]):
            one_iteration(candidate, timed=True, reverse_order=bool(index % 2))
    finally:
        if gc_was_enabled:
            gc.enable()

    insert_fast = latency_summary(fast_insert_ns)
    insert_dense = latency_summary(dense_insert_ns)
    delete_fast = latency_summary(fast_delete_ns)
    delete_dense = latency_summary(dense_delete_ns)
    insert_max_error = max_error(insert_errors)
    delete_max_error = max_error(delete_errors)
    passed = correctness_pass(insert_max_error, delete_max_error)
    return {
        "L": L,
        "N": geometry.n_sites,
        "beta": beta,
        "target_order_rule": "ceil(beta*N)",
        "order": order,
        "seed": local_seed,
        "word_sha256": word_digest(base_word),
        "candidate_sha256": word_digest(candidates),
        "repeats": repeats,
        "warmup": warmup,
        "latency": {
            "insert": {
                "rank3": insert_fast,
                "full_word_rebuild": insert_dense,
                "speedup_dense_over_rank3":
                    insert_dense["median_ns"] / insert_fast["median_ns"],
            },
            "delete": {
                "rank3": delete_fast,
                "full_word_rebuild": delete_dense,
                "speedup_dense_over_rank3":
                    delete_dense["median_ns"] / delete_fast["median_ns"],
            },
        },
        "correctness": {
            "pass": passed,
            "thresholds": dict(CORRECTNESS_THRESHOLDS),
            "insert_max_error": insert_max_error,
            "delete_max_error": delete_max_error,
        },
        "fallback_count": fallback_counts,
        "proposal_diagnostics": {
            "maximum_finite_condition":
                max(finite_conditions) if finite_conditions else None,
            "maximum_finite_local_solve_residual_inf":
                max(finite_local_residuals)
                if finite_local_residuals else None,
            "nonfinite_condition_count": nonfinite_condition_count,
            "nonfinite_local_solve_residual_count":
                nonfinite_local_residual_count,
        },
    }


def run_benchmark(
    sizes: Sequence[int] = DEFAULT_SIZES,
    beta: float = DEFAULT_BETA,
    seed: int = DEFAULT_SEED,
    repeats: int = DEFAULT_REPEATS,
    warmup: int = DEFAULT_WARMUP,
    condition_max: float = DEFAULT_CONDITION_MAX,
) -> Mapping[str, Any]:
    normalized_sizes = tuple(int(size) for size in sizes)
    if not normalized_sizes:
        raise ValueError("at least one size is required")
    script_path = Path(__file__).resolve()
    ctqmc_path = Path(ctqmc.__file__).resolve()
    cases = [
        benchmark_size(
            L,
            beta,
            seed,
            repeats,
            warmup,
            condition_max,
        )
        for L in normalized_sizes
    ]
    commit = source_commit()
    report: Dict[str, Any] = {
        "schema_version": 1,
        "algorithm_id": ALGORITHM_ID,
        "status": "benchmark_complete_unvalidated",
        "claim_boundary":
            "Kernel correctness and timing ingredients only; no publication or "
            "end-to-end Monte Carlo claim.",
        "parameters": {
            "sizes": list(normalized_sizes),
            "beta": beta,
            "order_rule": "ceil(beta*N)",
            "seed": seed,
            "repeats": repeats,
            "warmup": warmup,
            "woodbury_condition_max": condition_max,
            "model": dict(FROZEN_MODEL),
        },
        "timing_protocol": {
            "clock": "time.perf_counter_ns",
            "paired_same_word_and_candidate": True,
            "alternating_method_order": True,
            "garbage_collector_disabled_during_timing": True,
            "full_reference_definition":
                "structured_product(complete word) followed by factor_dense",
            "rank3_definition":
                "low_rank_left_proposal followed by apply_low_rank_proposal",
        },
        "single_thread_blas": {
            "set_before_numpy_import": True,
            "environment": {
                name: os.environ.get(name) for name in _BLAS_THREAD_ENV
            },
            "threadpool_info": optional_threadpool_info(),
        },
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "numpy_configuration": numpy_configuration(),
            "perf_counter_resolution_seconds":
                time.get_clock_info("perf_counter").resolution,
        },
        "provenance": {
            "source_commit": commit,
            "source_commit_role":
                "repository base commit; benchmark files may be uncommitted",
            "benchmark_source": str(
                script_path.relative_to(repository_root())
            ),
            "benchmark_source_sha256": sha256_file(script_path),
            "ctqmc_source": str(
                ctqmc_path.relative_to(repository_root())
            ),
            "ctqmc_source_sha256": sha256_file(ctqmc_path),
        },
        "cases": cases,
        "overall_correctness_pass": all(
            bool(case["correctness"]["pass"]) for case in cases
        ),
        "total_fallback_count": {
            "insert": sum(
                int(case["fallback_count"]["insert"]) for case in cases
            ),
            "delete": sum(
                int(case["fallback_count"]["delete"]) for case in cases
            ),
        },
        "machine_auditable_pass_ingredients": {
            "correctness_thresholds": dict(CORRECTNESS_THRESHOLDS),
            "per_case_correctness_boolean": True,
            "raw_latency_samples_recorded": True,
            "fallback_counts_recorded": True,
            "source_and_environment_hashes_recorded": True,
            "speedup_is_reported_not_claimed": True,
        },
    }
    assert_finite_json(report)
    return report


def parse_sizes(value: str) -> Tuple[int, ...]:
    try:
        result = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be comma-separated integers") from exc
    if not result or min(result) < 2:
        raise argparse.ArgumentTypeError("all sizes must be at least 2")
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        type=parse_sizes,
        default=DEFAULT_SIZES,
        help="comma-separated L values; default 4,8,12,16",
    )
    parser.add_argument("--beta", type=float, default=DEFAULT_BETA)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument(
        "--condition-max",
        type=float,
        default=DEFAULT_CONDITION_MAX,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resource-output", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    report = run_benchmark(
        sizes=args.sizes,
        beta=args.beta,
        seed=args.seed,
        repeats=args.repeats,
        warmup=args.warmup,
        condition_max=args.condition_max,
    )
    if args.resource_output is not None:
        atomic_write_resource_tsv(
            args.resource_output,
            float(time.perf_counter() - started),
            ctqmc.linux_max_rss_kb(),
        )
    if args.output is not None:
        atomic_write_json(args.output, report)
        print(json.dumps({
            "status": report["status"],
            "overall_correctness_pass":
                report["overall_correctness_pass"],
            "output": str(args.output),
        }, allow_nan=False))
    else:
        print(json.dumps(
            report,
            indent=None if args.compact else 2,
            sort_keys=True,
            allow_nan=False,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
