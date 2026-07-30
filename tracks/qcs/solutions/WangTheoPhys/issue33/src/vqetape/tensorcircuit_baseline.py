"""Audited TensorCircuit-NG baselines for VQETape workloads."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from vqetape.spec import TFIMVQESpec


class _TimedOptimizer:
    """Measure path-search time without changing an optimizer's result."""

    def __init__(self, optimizer: Any) -> None:
        self.optimizer = optimizer
        self.seconds = 0.0
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return self.optimizer(*args, **kwargs)
        finally:
            self.seconds += time.perf_counter() - started
            self.calls += 1


def matched_parameters(
    spec: TFIMVQESpec,
    seed: int,
) -> np.ndarray:
    """Generate the exact parameter tensor used by VQETape workers."""

    rng = np.random.default_rng(seed)
    real_dtype = np.float32 if spec.dtype == "complex64" else np.float64
    return np.asarray(
        rng.normal(
            loc=0.0,
            scale=0.1,
            size=spec.parameter_shape,
        ),
        dtype=real_dtype,
    )


def build_protocol(
    spec: TFIMVQESpec,
    seed: int,
) -> dict[str, Any]:
    """Return the comparison contract shared by VQETape and the baseline."""

    return {
        "hamiltonian": "-sum_i Z_i Z_{i+1} - sum_i X_i",
        "coupling": spec.coupling,
        "field": spec.field,
        "boundary": "open",
        "initial_state": spec.initial_state,
        "ansatz": "plus_then_rzz_rx",
        "gate_order": "rzz_then_rx_per_layer",
        "nqubits": spec.nqubits,
        "depth": spec.depth,
        "dtype": spec.dtype,
        "parameter_shape": list(spec.parameter_shape),
        "active_parameter_count": spec.active_parameter_count,
        "padding_parameter": "rzz[layer, nqubits - 1]",
        "seed": seed,
        "parameter_distribution": (
            "numpy.default_rng.normal(loc=0, scale=0.1)"
        ),
        "comparison_scope": "matched_rzz_rx_not_fig2_su4",
    }


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _memory_analysis(compiled: Any) -> dict[str, int | float | None]:
    try:
        analysis = compiled.memory_analysis()
    except (AttributeError, RuntimeError, TypeError):
        return {}
    if analysis is None:
        return {}
    result: dict[str, int | float | None] = {}
    for name in dir(analysis):
        if name.startswith("_"):
            continue
        try:
            value = getattr(analysis, name)
        except (AttributeError, RuntimeError):
            continue
        if callable(value) or not isinstance(
            value,
            (int, float, type(None)),
        ):
            continue
        result[name] = value
    return result


def _median_and_mad(values: list[float]) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))
    return median, mad


def _configure_tensor_network_precision(jax: Any, backend: Any) -> str:
    """Make TensorNetwork honor JAX's requested matmul precision.

    TensorNetwork passes an explicit ``Precision.DEFAULT`` to every JAX
    ``tensordot`` unless its cached backend is updated.  That explicit value
    takes precedence over ``JAX_DEFAULT_MATMUL_PRECISION`` and enables TF32 on
    NVIDIA GPUs even when the surrounding JAX program requests ``highest``.
    """

    from tensornetwork.backends import backend_factory

    configured = jax.config.jax_default_matmul_precision
    name = "default" if configured is None else str(configured).lower()
    if name in {"highest", "float32"}:
        precision = jax.lax.Precision.HIGHEST
    elif name == "high":
        precision = jax.lax.Precision.HIGH
    else:
        precision = jax.lax.Precision.DEFAULT

    backend.jax_precision = precision
    tensor_network_backend = backend_factory.get_backend("jax")
    tensor_network_backend.jax_precision = precision
    return str(precision)


def _configure_contractor(
    tc: Any,
    contractor: str,
) -> tuple[dict[str, Any], _TimedOptimizer | None]:
    if contractor == "greedy":
        tc.set_contractor("greedy", preprocessing=True)
        return (
            {
                "name": "greedy",
                "preprocessing": True,
                "source": "TensorCircuit-NG built-in",
            },
            None,
        )
    if contractor != "omeco":
        raise ValueError(f"unsupported contractor: {contractor}")

    try:
        import omeco
    except ImportError as exc:
        raise RuntimeError(
            "OMECo is required for contractor='omeco'; install "
            "VQETape with the baseline optional dependencies"
        ) from exc

    trials = 16
    iterations = 16
    betas = np.geomspace(0.1, 10.0, iterations).tolist()
    score = omeco.ScoreFunction(
        tc_weight=1.0,
        sc_weight=0.0,
        rw_weight=64.0,
        sc_target=20.0,
    )
    raw_optimizer = omeco.TreeSA(
        ntrials=trials,
        niters=iterations,
        betas=betas,
        score=score,
    )
    optimizer = _TimedOptimizer(
        tc.cons.OMEOptimizer(raw_optimizer)
    )
    tc.set_contractor(
        "custom",
        optimizer=optimizer,
        preprocessing=True,
    )
    return (
        {
            "name": "omeco",
            "optimizer": "TreeSA",
            "ntrials": trials,
            "niters": iterations,
            "betas": betas,
            "score": {
                "tc_weight": 1.0,
                "sc_weight": 0.0,
                "rw_weight": 64.0,
                "sc_target": 20.0,
            },
            "preprocessing": True,
            "source": (
                "TensorCircuit-NG "
                "examples/benchmark_jax_vs_torch_vqe.py"
            ),
        },
        optimizer,
    )


def _tfim_sparse_hamiltonian(
    tc: Any,
    spec: TFIMVQESpec,
) -> Any:
    structures: list[list[int]] = []
    weights: list[float] = []
    for wire in range(spec.nqubits - 1):
        term = [0] * spec.nqubits
        term[wire] = 3
        term[wire + 1] = 3
        structures.append(term)
        weights.append(-spec.coupling)
    for wire in range(spec.nqubits):
        term = [0] * spec.nqubits
        term[wire] = 1
        structures.append(term)
        weights.append(-spec.field)

    with tc.runtime_backend("numpy"):
        coo = tc.quantum.PauliStringSum2COO(
            structures,
            weights,
            numpy=True,
        )
    return tc.backend.coo_sparse_matrix_from_numpy(coo)


def _value_function(
    tc: Any,
    spec: TFIMVQESpec,
) -> Any:
    hamiltonian = _tfim_sparse_hamiltonian(tc, spec)
    backend = tc.backend

    def value(params: Any) -> Any:
        circuit = tc.Circuit(spec.nqubits)
        if spec.initial_state == "plus":
            for wire in range(spec.nqubits):
                circuit.h(wire)
        for layer in range(spec.depth):
            for wire in range(spec.nqubits - 1):
                circuit.rzz(
                    wire,
                    wire + 1,
                    theta=params[layer, 0, wire],
                )
            for wire in range(spec.nqubits):
                circuit.rx(
                    wire,
                    theta=params[layer, 1, wire],
                )
        energy = tc.templates.measurements.operator_expectation(
            circuit,
            hamiltonian,
        )
        return backend.real(energy)

    return value


def _read_reference(path: Path) -> tuple[float, np.ndarray, str]:
    data = path.read_bytes()
    payload = json.loads(data)
    candidate = payload["candidate"]
    return (
        float(candidate["energy"]),
        np.asarray(candidate["gradient"]),
        hashlib.sha256(data).hexdigest(),
    )


def run_baseline(
    *,
    spec: TFIMVQESpec,
    seed: int,
    warm_repeats: int,
    contractor: str,
    reference_path: Path | None = None,
) -> dict[str, Any]:
    """Run one fresh-process TensorCircuit-NG matched baseline."""

    if warm_repeats < 1:
        raise ValueError("warm_repeats must be positive")

    try:
        import jax
        import jax.numpy as jnp
        import tensorcircuit as tc
    except ImportError as exc:
        raise RuntimeError(
            "TensorCircuit-NG baseline dependencies are missing; install "
            "VQETape with the baseline optional dependencies"
        ) from exc

    backend = tc.set_backend("jax")
    tensor_network_precision = _configure_tensor_network_precision(
        jax,
        backend,
    )
    tc.set_dtype(spec.dtype)
    contractor_manifest, timed_optimizer = _configure_contractor(
        tc,
        contractor,
    )
    params = jnp.asarray(matched_parameters(spec, seed))
    value = _value_function(tc, spec)
    executable = backend.jit(backend.value_and_grad(value))

    compile_started = time.perf_counter()
    lowered = executable.lower(params)
    compiled = lowered.compile()
    compile_seconds = time.perf_counter() - compile_started

    first_started = time.perf_counter()
    first_energy, first_gradient = compiled(params)
    jax.block_until_ready((first_energy, first_gradient))
    first_execute_seconds = time.perf_counter() - first_started

    warm_times: list[float] = []
    energy = first_energy
    gradient = first_gradient
    for _ in range(warm_repeats):
        started = time.perf_counter()
        energy, gradient = compiled(params)
        jax.block_until_ready((energy, gradient))
        warm_times.append(time.perf_counter() - started)
    warm_median, warm_mad = _median_and_mad(warm_times)

    energy_value = float(np.asarray(energy))
    gradient_value = np.asarray(gradient)
    correctness: dict[str, Any] | None = None
    reference: dict[str, Any] | None = None
    if reference_path is not None:
        reference_energy, reference_gradient, reference_sha = (
            _read_reference(reference_path)
        )
        energy_error = abs(energy_value - reference_energy)
        gradient_denominator = max(
            float(np.linalg.norm(reference_gradient)),
            1e-12,
        )
        gradient_error = float(
            np.linalg.norm(gradient_value - reference_gradient)
            / gradient_denominator
        )
        energy_tolerance = 1e-5 if spec.dtype == "complex64" else 1e-10
        gradient_tolerance = (
            1e-5 if spec.dtype == "complex64" else 1e-9
        )
        correctness = {
            "energy_abs_error": energy_error,
            "gradient_relative_l2_error": gradient_error,
            "energy_tolerance": energy_tolerance,
            "gradient_tolerance": gradient_tolerance,
            "tolerance_passed": (
                energy_error <= energy_tolerance
                and gradient_error <= gradient_tolerance
            ),
        }
        reference = {
            "path": str(reference_path),
            "sha256": reference_sha,
            "energy": reference_energy,
            "gradient_l2_norm": float(
                np.linalg.norm(reference_gradient)
            ),
        }

    path_search_seconds = (
        timed_optimizer.seconds
        if timed_optimizer is not None
        else None
    )
    path_search_calls = (
        timed_optimizer.calls
        if timed_optimizer is not None
        else None
    )
    return {
        "schema_version": 1,
        "implementation": {
            "name": "TensorCircuit-NG",
            "package": "tensorcircuit-ng",
            "source_repository": (
                "https://github.com/tensorcircuit/tensorcircuit-ng"
            ),
            "official_example": (
                "examples/benchmark_jax_vs_torch_vqe.py"
            ),
            "versions": {
                "tensorcircuit-ng": _package_version(
                    "tensorcircuit-ng"
                ),
                "tensornetwork-ng": _package_version(
                    "tensornetwork-ng"
                ),
                "jax": _package_version("jax"),
                "jaxlib": _package_version("jaxlib"),
                "numpy": _package_version("numpy"),
                "omeco": _package_version("omeco"),
                "cotengra": _package_version("cotengra"),
            },
        },
        "protocol": build_protocol(spec, seed),
        "contractor": {
            **contractor_manifest,
            "path_search_seconds": path_search_seconds,
            "path_search_calls": path_search_calls,
        },
        "runtime": {
            "jax_backend": jax.default_backend(),
            "jax_devices": [str(device) for device in jax.devices()],
            "jax_default_matmul_precision": os.environ.get(
                "JAX_DEFAULT_MATMUL_PRECISION"
            ),
            "tensor_network_jax_precision": (
                tensor_network_precision
            ),
            "python": sys.version,
            "pid": os.getpid(),
        },
        "timings": {
            "compile_seconds": compile_seconds,
            "compile_includes_path_search": True,
            "first_execute_seconds": first_execute_seconds,
            "warm_seconds": warm_times,
            "warm_seconds_median": warm_median,
            "warm_seconds_mad": warm_mad,
        },
        "memory": {
            "peak_rss_bytes": _peak_rss_bytes(),
            "jax_memory_analysis": _memory_analysis(compiled),
            "nvml_job_peak_mib": None,
        },
        "result": {
            "energy": energy_value,
            "gradient": gradient_value.tolist(),
            "gradient_l2_norm": float(
                np.linalg.norm(gradient_value)
            ),
        },
        "reference": reference,
        "correctness": correctness,
    }
