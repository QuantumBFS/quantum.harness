"""Audited TensorCircuit-NG implementation of the paper Fig. 2 protocol.

The large benchmark uses a two-stage workflow: search for a sliced
contraction path, then execute value-and-gradient calls from that path.  Path
artifacts are stored as JSON instead of the pickle format used by the upstream
example so that accepting a path file never executes serialized Python code.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import resource
import sys
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from vqetape.tensorcircuit_baseline import (
    _configure_tensor_network_precision,
)


@dataclass(frozen=True)
class Fig2Spec:
    """Physical and initialization inputs for the Fig. 2 VQE network."""

    nqubits: int = 32
    depth: int = 16
    coupling: float = 1.0
    field: float = 1.0
    dtype: str = "complex64"
    seed: int = 42
    parameter_scale: float = 0.1

    def __post_init__(self) -> None:
        if self.nqubits < 2:
            raise ValueError("nqubits must be at least 2")
        if self.depth < 1:
            raise ValueError("depth must be positive")
        if self.dtype not in {"complex64", "complex128"}:
            raise ValueError("dtype must be complex64 or complex128")
        if self.parameter_scale <= 0:
            raise ValueError("parameter_scale must be positive")

    @property
    def parameter_shape(self) -> tuple[int, int, int]:
        return (self.depth, self.nqubits - 1, 15)

    @property
    def parameter_count(self) -> int:
        return 15 * self.depth * (self.nqubits - 1)


def fig2_cotengra_options(
    *,
    max_repeats: int = 640,
    target_size: int = 2**29,
    parallel: int = 1,
) -> dict[str, Any]:
    """Return the paper's path score and slicing policy.

    Cotengra 0.8.2 parses ``combo-640`` as
    ``log(FLOPS + 640 * WRITE)``.  The logarithm is monotone, so it has the
    exact optimizer ordering reported by the paper.
    """

    if max_repeats < 1:
        raise ValueError("max_repeats must be positive")
    if target_size < 2:
        raise ValueError("target_size must be at least 2")
    if parallel < 1:
        raise ValueError("parallel must be positive")
    return {
        "slicing_reconf_opts": {"target_size": target_size},
        "max_repeats": max_repeats,
        "minimize": "combo-640",
        "parallel": parallel,
        # Headless Slurm environments should not require cotengra's optional
        # tqdm dependency merely to render search progress.
        "progbar": False,
    }


def build_fig2_protocol(
    spec: Fig2Spec,
    *,
    max_repeats: int = 640,
    target_size: int = 2**29,
    parallel: int = 1,
) -> dict[str, Any]:
    """Build a machine-readable statement of the reproduced protocol."""

    options = fig2_cotengra_options(
        max_repeats=max_repeats,
        target_size=target_size,
        parallel=parallel,
    )
    return {
        "paper": {
            "title": (
                "TensorCircuit-NG: A Universal, Composable, and "
                "Scalable Platform for Quantum Computing and Quantum "
                "Simulation"
            ),
            "arxiv": "2602.14167",
            "figure": 2,
            "reported_hardware": "NVIDIA H200 141GB",
            "reported_single_gpu_n32_l16_step_seconds": 17.86,
            "reported_eight_gpu_n32_l16_step_seconds": 2.38,
        },
        "hamiltonian": {
            "paper_form": "-sum_i Z_i Z_{i+1} - sum_i X_i",
            "implementation": (
                "TensorNetwork FiniteTFI rotated-axis open-boundary MPO"
            ),
            "coupling": spec.coupling,
            "field": spec.field,
            "boundary": "open",
        },
        "initial_state": "plus",
        "ansatz": {
            "gate": "TensorCircuit-NG su4",
            "gate_parameterization": (
                "exp(-i * sum_k theta_k P_k), 15 nonidentity "
                "two-qubit Pauli generators"
            ),
            "layout": (
                "ladder: adjacent pairs (0,1), (1,2), ..., "
                "(nqubits-2,nqubits-1) per layer"
            ),
            "nqubits": spec.nqubits,
            "depth": spec.depth,
            "parameter_shape": list(spec.parameter_shape),
            "parameter_count": spec.parameter_count,
            "parameter_count_formula": "15 * depth * (nqubits - 1)",
        },
        "numerics": {
            "dtype": spec.dtype,
            "seed": spec.seed,
            "initialization": "jax.random.normal(PRNGKey(seed)) * scale",
            "parameter_scale": spec.parameter_scale,
            "precision": "highest",
            "seed_boundary": (
                "the paper does not state a Fig. 2 seed; seed 42 follows "
                "the upstream DistributedContractor VQE example"
            ),
        },
        "contractor": {
            "engine": "TensorCircuit-NG DistributedContractor",
            "find_execute_workflow": True,
            "max_repeats": max_repeats,
            "minimize": options["minimize"],
            "score": "FLOPS + 640 * WRITE",
            "slicing_target_elements": target_size,
            "parallel_path_workers": parallel,
            "slicing_boundary": (
                "the paper explicitly reports 2^29 elements for the "
                "40-qubit case; this runner makes the value explicit for "
                "every run"
            ),
        },
        "scope": "paper_fig2_protocol_not_matched_rzz_rx_baseline",
    }


def protocol_sha256(protocol: dict[str, Any]) -> str:
    data = json.dumps(
        protocol,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _versions() -> dict[str, str | None]:
    return {
        "tensorcircuit-ng": _package_version("tensorcircuit-ng"),
        "tensornetwork-ng": _package_version("tensornetwork-ng"),
        "jax": _package_version("jax"),
        "jaxlib": _package_version("jaxlib"),
        "cotengra": _package_version("cotengra"),
        "kahypar": _package_version("kahypar"),
        "numpy": _package_version("numpy"),
    }


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _median_and_mad(values: list[float]) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    median = float(np.median(array))
    return median, float(np.median(np.abs(array - median)))


def _runtime(spec: Fig2Spec) -> tuple[Any, Any, Any, Any, str]:
    try:
        import jax
        import jax.numpy as jnp
        import tensorcircuit as tc
        import tensornetwork as tn
    except ImportError as exc:
        raise RuntimeError(
            "Fig. 2 dependencies are missing; install VQETape with the "
            "baseline optional dependencies"
        ) from exc

    backend = tc.set_backend("jax")
    precision = _configure_tensor_network_precision(jax, backend)
    tc.set_dtype(spec.dtype)
    if spec.dtype == "complex128" and not jax.config.jax_enable_x64:
        raise RuntimeError(
            "complex128 requires JAX_ENABLE_X64=1 before importing JAX"
        )
    return jax, jnp, tc, tn, precision


def _parameters(jax: Any, jnp: Any, spec: Fig2Spec) -> Any:
    dtype = jnp.float32 if spec.dtype == "complex64" else jnp.float64
    return (
        jax.random.normal(
            jax.random.PRNGKey(spec.seed),
            shape=spec.parameter_shape,
            dtype=dtype,
        )
        * spec.parameter_scale
    )


def _nodes_fn(tc: Any, tn: Any, spec: Fig2Spec) -> Any:
    dtype = np.complex64 if spec.dtype == "complex64" else np.complex128
    # This is the exact MPO construction used by the upstream
    # DistributedContractor VQE example.  It is a rotated-axis representation
    # of the open-boundary TFIM stated in the paper.
    tn_mpo = tn.matrixproductstates.mpo.FiniteTFI(
        np.full(spec.nqubits - 1, spec.coupling),
        np.full(spec.nqubits, -spec.field),
        dtype=dtype,
    )
    mpo = tc.quantum.tn2qop(tn_mpo)

    def build_nodes(params: Any) -> list[Any]:
        circuit = tc.Circuit(spec.nqubits)
        circuit.h(range(spec.nqubits))
        for layer in range(spec.depth):
            for wire in range(spec.nqubits - 1):
                circuit.su4(
                    wire,
                    wire + 1,
                    theta=params[layer, wire],
                )
        state = circuit.get_quvector()
        return (state.adjoint() @ mpo @ state).nodes

    return build_nodes


def _encode_tree_data(tree_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a cotengra tree to JSON without losing index types."""

    return {
        "inputs": [list(term) for term in tree_data["inputs"]],
        "output": list(tree_data["output"]),
        "size_dict": [
            [index, int(size)]
            for index, size in tree_data["size_dict"].items()
        ],
        "path": [list(pair) for pair in tree_data["path"]],
        # DistributedContractor only consumes the sliced index keys when it
        # restores a path.  Cotengra's SliceInfo values are intentionally not
        # serialized.
        "sliced_indices": list(tree_data["sliced_inds"]),
    }


def _decode_tree_data(encoded: dict[str, Any]) -> dict[str, Any]:
    required = {
        "inputs",
        "output",
        "size_dict",
        "path",
        "sliced_indices",
    }
    if set(encoded) != required:
        raise ValueError("path tree_data has unexpected fields")
    return {
        "inputs": [tuple(term) for term in encoded["inputs"]],
        "output": tuple(encoded["output"]),
        "size_dict": dict(encoded["size_dict"]),
        "path": [tuple(pair) for pair in encoded["path"]],
        "sliced_inds": {
            index: None for index in encoded["sliced_indices"]
        },
    }


def _tree_stats(tree_data: dict[str, Any]) -> dict[str, int | float]:
    import cotengra as ctg

    tree = ctg.ContractionTree.from_path(
        inputs=tree_data["inputs"],
        output=tree_data["output"],
        size_dict=tree_data["size_dict"],
        path=tree_data["path"],
    )
    for index in tree_data["sliced_inds"]:
        tree.remove_ind_(index)
    stats = tree.contract_stats()
    return {
        "slices": int(tree.nslices),
        "flops": int(stats["flops"]),
        "write": int(stats["write"]),
        "max_size_elements": int(stats["size"]),
        "arithmetic_intensity": float(tree.arithmetic_intensity()),
    }


def search_fig2_path(
    spec: Fig2Spec,
    *,
    max_repeats: int = 640,
    target_size: int = 2**29,
    parallel: int = 1,
) -> dict[str, Any]:
    """Search one path and return a safe, self-describing JSON payload."""

    jax, jnp, tc, tn, precision = _runtime(spec)
    from tensorcircuit.experimental import DistributedContractor

    protocol = build_fig2_protocol(
        spec,
        max_repeats=max_repeats,
        target_size=target_size,
        parallel=parallel,
    )
    params = _parameters(jax, jnp, spec)
    nodes_fn = _nodes_fn(tc, tn, spec)
    options = fig2_cotengra_options(
        max_repeats=max_repeats,
        target_size=target_size,
        parallel=parallel,
    )
    started = time.perf_counter()
    tree_data = DistributedContractor._get_tree_data(
        nodes_fn,
        params,
        options,
    )
    path_seconds = time.perf_counter() - started
    return {
        "schema_version": 1,
        "artifact_type": "tensorcircuit_ng_fig2_path",
        "protocol": protocol,
        "protocol_sha256": protocol_sha256(protocol),
        "implementation": {
            "name": "TensorCircuit-NG DistributedContractor",
            "source_repository": (
                "https://github.com/tensorcircuit/tensorcircuit-ng"
            ),
            "upstream_example": "examples/distributed_interface_vqe.py",
            "versions": _versions(),
        },
        "runtime": {
            "jax_backend": jax.default_backend(),
            "jax_devices": [str(device) for device in jax.devices()],
            "jax_default_matmul_precision": os.environ.get(
                "JAX_DEFAULT_MATMUL_PRECISION"
            ),
            "tensor_network_jax_precision": precision,
            "python": sys.version,
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "slurm_node": os.environ.get("SLURMD_NODENAME"),
        },
        "path_search": {
            "seconds": path_seconds,
            "options": options,
            "tree_stats": _tree_stats(tree_data),
        },
        "tree_data": _encode_tree_data(tree_data),
    }


def _spec_from_protocol(protocol: dict[str, Any]) -> Fig2Spec:
    ansatz = protocol["ansatz"]
    numerics = protocol["numerics"]
    hamiltonian = protocol["hamiltonian"]
    return Fig2Spec(
        nqubits=int(ansatz["nqubits"]),
        depth=int(ansatz["depth"]),
        coupling=float(hamiltonian["coupling"]),
        field=float(hamiltonian["field"]),
        dtype=str(numerics["dtype"]),
        seed=int(numerics["seed"]),
        parameter_scale=float(numerics["parameter_scale"]),
    )


def validate_path_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported Fig. 2 path schema")
    if payload.get("artifact_type") != "tensorcircuit_ng_fig2_path":
        raise ValueError("not a TensorCircuit-NG Fig. 2 path artifact")
    protocol = payload.get("protocol")
    if not isinstance(protocol, dict):
        raise ValueError("path artifact has no protocol")
    if payload.get("protocol_sha256") != protocol_sha256(protocol):
        raise ValueError("path protocol checksum mismatch")
    spec = _spec_from_protocol(protocol)
    if list(spec.parameter_shape) != protocol["ansatz"]["parameter_shape"]:
        raise ValueError("path parameter shape is inconsistent")
    if spec.parameter_count != protocol["ansatz"]["parameter_count"]:
        raise ValueError("path parameter count is inconsistent")
    tree_data = payload.get("tree_data")
    if not isinstance(tree_data, dict):
        raise ValueError("path artifact has no tree_data")
    _decode_tree_data(tree_data)


def run_fig2_path(
    payload: dict[str, Any],
    *,
    warm_repeats: int = 3,
    verify_direct: bool = False,
) -> dict[str, Any]:
    """Execute a searched path and optionally compare a small dense control."""

    if warm_repeats < 1:
        raise ValueError("warm_repeats must be positive")
    validate_path_payload(payload)
    spec = _spec_from_protocol(payload["protocol"])
    if verify_direct and spec.nqubits > 10:
        raise ValueError("direct verification is limited to at most 10 qubits")

    jax, jnp, tc, tn, precision = _runtime(spec)
    from tensorcircuit.experimental import DistributedContractor

    params = _parameters(jax, jnp, spec)
    nodes_fn = _nodes_fn(tc, tn, spec)
    tree_data = _decode_tree_data(payload["tree_data"])
    contractor = DistributedContractor(
        nodes_fn=nodes_fn,
        params=params,
        tree_data=tree_data,
    )

    first_started = time.perf_counter()
    energy, gradient = contractor.value_and_grad(params)
    jax.block_until_ready((energy, gradient))
    first_seconds = time.perf_counter() - first_started

    warm_times: list[float] = []
    for _ in range(warm_repeats):
        started = time.perf_counter()
        energy, gradient = contractor.value_and_grad(params)
        jax.block_until_ready((energy, gradient))
        warm_times.append(time.perf_counter() - started)
    warm_median, warm_mad = _median_and_mad(warm_times)

    energy_value = float(np.asarray(energy))
    gradient_value = np.asarray(gradient)
    correctness: dict[str, Any] | None = None
    if verify_direct:
        backend = tc.backend

        def direct_value(values: Any) -> Any:
            nodes = nodes_fn(values)
            contracted = tc.cons.contractor(
                nodes,
                output_edge_order=tn.get_all_dangling(nodes),
            )
            return backend.real(backend.sum(contracted.tensor))

        direct = backend.jit(backend.value_and_grad(direct_value))
        reference_energy, reference_gradient = direct(params)
        jax.block_until_ready((reference_energy, reference_gradient))
        reference_energy_value = float(np.asarray(reference_energy))
        reference_gradient_value = np.asarray(reference_gradient)
        energy_error = abs(energy_value - reference_energy_value)
        denominator = max(
            float(np.linalg.norm(reference_gradient_value)),
            1e-12,
        )
        gradient_error = float(
            np.linalg.norm(gradient_value - reference_gradient_value)
            / denominator
        )
        tolerance = 1e-5 if spec.dtype == "complex64" else 1e-9
        correctness = {
            "reference": "direct unsliced contraction of identical nodes",
            "energy_abs_error": energy_error,
            "gradient_relative_l2_error": gradient_error,
            "tolerance": tolerance,
            "tolerance_passed": (
                energy_error <= tolerance and gradient_error <= tolerance
            ),
        }

    return {
        "schema_version": 1,
        "artifact_type": "tensorcircuit_ng_fig2_run",
        "protocol": payload["protocol"],
        "protocol_sha256": payload["protocol_sha256"],
        "path_tree_stats": _tree_stats(tree_data),
        "runtime": {
            "jax_backend": jax.default_backend(),
            "jax_devices": [str(device) for device in jax.devices()],
            "jax_default_matmul_precision": os.environ.get(
                "JAX_DEFAULT_MATMUL_PRECISION"
            ),
            "tensor_network_jax_precision": precision,
            "python": sys.version,
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "slurm_node": os.environ.get("SLURMD_NODENAME"),
            "cuda_visible_devices": os.environ.get(
                "CUDA_VISIBLE_DEVICES"
            ),
            "versions": _versions(),
        },
        "timings": {
            "first_value_and_grad_seconds": first_seconds,
            "first_call_includes_jit_compile": True,
            "warm_value_and_grad_seconds": warm_times,
            "warm_value_and_grad_seconds_median": warm_median,
            "warm_value_and_grad_seconds_mad": warm_mad,
        },
        "memory": {
            "peak_rss_bytes": _peak_rss_bytes(),
            "nvml_job_peak_mib": None,
        },
        "result": {
            "energy": energy_value,
            "gradient_shape": list(gradient_value.shape),
            "gradient_l2_norm": float(np.linalg.norm(gradient_value)),
            "gradient_sha256": hashlib.sha256(
                np.ascontiguousarray(gradient_value).tobytes()
            ).hexdigest(),
        },
        "correctness": correctness,
    }
