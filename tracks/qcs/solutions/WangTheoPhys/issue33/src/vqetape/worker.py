"""Fresh-process benchmark worker used by :mod:`vqetape.benchmark`."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

import jax
import numpy as np

from vqetape.ad_analysis import analyze_spatial_transfer
from vqetape.estimate import estimate_program
from vqetape.metrics import median_and_mad
from vqetape.programs import build_value_and_grad
from vqetape.selection import CandidateResult
from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spatial_programs import (
    build_spatial_energy,
    modeled_spatial_checkpoint_count,
)
from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
    TensorProgramConfig,
    dtype_bytes,
)
from vqetape.tape import profile_saved_residuals
from vqetape.tn_vqe import build_tn_energy
from vqetape.symmetry import (
    z2_boundary_sector,
    z2_symmetry_applicability,
)


def _synchronize(value: Any) -> Any:
    return jax.block_until_ready(value)


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
        if callable(value) or not isinstance(value, (int, float, type(None))):
            continue
        result[name] = value
    return result


def _parameters(spec: TFIMVQESpec, seed: int):
    rng = np.random.default_rng(seed)
    real_dtype = np.float32 if spec.dtype == "complex64" else np.float64
    return np.asarray(
        rng.normal(loc=0.0, scale=0.1, size=spec.parameter_shape),
        dtype=real_dtype,
    )


def run_worker(payload: dict[str, Any]) -> CandidateResult:
    spec = TFIMVQESpec.from_dict(payload["spec"])
    program_kind = payload.get("program_kind", "statevector")
    if program_kind == "direct_tn":
        config = TensorProgramConfig.from_dict(payload["config"])
    elif program_kind == "spatial_transfer":
        config = SpatialProgramConfig.from_dict(payload["config"])
    else:
        config = ProgramConfig.from_dict(payload["config"])
    theta = _parameters(spec, int(payload["seed"]))
    if isinstance(config, TensorProgramConfig):
        energy_function, path_program, remat_steps = build_tn_energy(
            spec,
            path_strategy=config.path_strategy,
            remat_policy=config.remat_policy,
            threshold_bytes=config.threshold_bytes,
            explicit_path=config.path,
            subtree_depth=config.subtree_depth,
            save_names=config.save_names,
            gate_representation=config.gate_representation,
            hamiltonian_representation=(
                config.hamiltonian_representation
            ),
        )
        residual_profile = profile_saved_residuals(energy_function, theta)
        executable = jax.jit(jax.value_and_grad(energy_function))
        contractions_per_energy = (
            2 * spec.nqubits - 1
            if config.hamiltonian_representation == "pauli_sum"
            else 1
        )
        static_estimate = {
            "gate_representation": config.gate_representation,
            "hamiltonian_representation": (
                config.hamiltonian_representation
            ),
            "tensor_count": path_program.tensor_count,
            "input_tensor_elements": path_program.input_tensor_elements,
            "path_flops": path_program.flops,
            "contractions_per_energy": contractions_per_energy,
            "estimated_energy_flops": (
                path_program.flops * contractions_per_energy
            ),
            "estimated_energy_tensor_bindings": (
                path_program.tensor_count * contractions_per_energy
            ),
            "largest_intermediate_elements": (
                path_program.largest_intermediate_elements
            ),
            "contraction_steps": len(path_program.steps),
            "rematerialized_steps": (
                max(0, 2 * len(path_program.steps) - len(remat_steps))
                if config.remat_policy == "named"
                else len(remat_steps)
            ),
            "rematerialized_units": (
                max(0, 2 * len(path_program.steps) - len(remat_steps))
                if config.remat_policy == "named"
                else len(remat_steps)
            ),
            "saved_named_units": (
                len(config.save_names)
                if config.save_names is not None
                else 0
            ),
            "max_step_output_bytes": max(path_program.step_output_bytes),
            "residual_profile": residual_profile.to_dict(),
        }
    elif isinstance(config, SpatialProgramConfig):
        transfer = plan_spatial_transfer(
            spec,
            config.path_strategy,
            explicit_paths=config.column_paths,
            block_width=config.block_width,
        )
        energy_function = build_spatial_energy(spec, config)
        residual_profile = profile_saved_residuals(
            energy_function,
            theta,
        )
        executable = jax.jit(jax.value_and_grad(energy_function))
        bulk_flops = (
            transfer.bulk.flops
            if transfer.bulk is not None
            else 0
        )
        tail_flops = (
            transfer.tail.flops
            if transfer.tail is not None
            else 0
        )
        boundary_bytes = (
            transfer.boundary_dimension * dtype_bytes(spec.dtype)
        )
        symmetry_sector = None
        if config.symmetry != "none":
            applicable, reason = z2_symmetry_applicability(
                spec
            )
            if not applicable:
                raise ValueError(reason)
            symmetry_sector = z2_boundary_sector(
                transfer.boundary_shape
            )
        recurrent_boundary_dimension = (
            symmetry_sector.active_count
            if symmetry_sector is not None
            else transfer.boundary_dimension
        )
        recurrent_boundary_bytes = (
            recurrent_boundary_dimension
            * dtype_bytes(spec.dtype)
        )
        checkpoint_count = modeled_spatial_checkpoint_count(
            spec,
            config,
        )
        static_estimate = {
            "representation": "spatial_transfer",
            "path_strategy": config.path_strategy,
            "adjoint": config.adjoint,
            "symmetry": config.symmetry,
            "unroll": config.unroll,
            "block_width": config.block_width,
            "segment_length": config.segment_length,
            "boundary_rank": len(transfer.boundary_shape),
            "boundary_shape": list(transfer.boundary_shape),
            "boundary_dimension": transfer.boundary_dimension,
            "boundary_bytes": boundary_bytes,
            "recurrent_boundary_dimension": (
                recurrent_boundary_dimension
            ),
            "recurrent_boundary_bytes": (
                recurrent_boundary_bytes
            ),
            "symmetry_sector": (
                symmetry_sector.to_dict()
                if symmetry_sector is not None
                else None
            ),
            "symmetry_execution": (
                "dense"
                if config.symmetry == "none"
                else (
                    "expand-contract-gather-reference"
                    if config.symmetry == "z2-reference"
                    else "bcoo-native"
                )
            ),
            "bulk_columns": max(0, spec.nqubits - 2),
            "bulk_blocks": transfer.bulk_block_count,
            "tail_width": transfer.tail_width,
            "first_path_flops": transfer.first.flops,
            "bulk_path_flops": bulk_flops,
            "bulk_block_path_flops": bulk_flops,
            "tail_path_flops": tail_flops,
            "last_path_flops": transfer.last.flops,
            "estimated_energy_flops": (
                transfer.first.flops
                + transfer.bulk_block_count * bulk_flops
                + tail_flops
                + transfer.last.flops
            ),
            "modeled_checkpoint_boundaries": checkpoint_count,
            "modeled_checkpoint_bytes": (
                checkpoint_count
                * recurrent_boundary_bytes
            ),
            "first_largest_intermediate_elements": (
                transfer.first.largest_intermediate_elements
            ),
            "bulk_largest_intermediate_elements": (
                transfer.bulk.largest_intermediate_elements
                if transfer.bulk is not None
                else 0
            ),
            "tail_largest_intermediate_elements": (
                transfer.tail.largest_intermediate_elements
                if transfer.tail is not None
                else 0
            ),
            "last_largest_intermediate_elements": (
                transfer.last.largest_intermediate_elements
            ),
            "differentiated_cost": (
                analyze_spatial_transfer(transfer).to_dict()
            ),
            "residual_profile": residual_profile.to_dict(),
        }
    else:
        executable = build_value_and_grad(spec, config)
        static_estimate = estimate_program(spec, config).to_dict()

    lower_started = time.perf_counter()
    lowered = executable.lower(theta)
    compiled = lowered.compile()
    compile_seconds = time.perf_counter() - lower_started

    first_started = time.perf_counter()
    first_energy, first_gradient = compiled(theta)
    _synchronize((first_energy, first_gradient))
    first_execute_seconds = time.perf_counter() - first_started

    warm_times: list[float] = []
    final_energy = first_energy
    final_gradient = first_gradient
    for _ in range(int(payload["warm_repeats"])):
        started = time.perf_counter()
        final_energy, final_gradient = compiled(theta)
        _synchronize((final_energy, final_gradient))
        warm_times.append(time.perf_counter() - started)
    warm_median, warm_mad = median_and_mad(warm_times)

    return CandidateResult(
        config=config,
        compile_seconds=compile_seconds,
        first_execute_seconds=first_execute_seconds,
        warm_seconds_median=warm_median,
        warm_seconds_mad=warm_mad,
        peak_rss_bytes=_peak_rss_bytes(),
        energy_abs_error=0.0,
        gradient_relative_l2_error=0.0,
        valid=True,
        worker_pid=os.getpid(),
        parent_pid=int(payload["parent_pid"]),
        energy=float(np.asarray(final_energy)),
        gradient=np.asarray(final_gradient).tolist(),
        jax_memory_analysis=_memory_analysis(compiled),
        static_estimate=static_estimate,
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True, type=Path)
    parser.add_argument("--result-json", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.request_json.read_text(encoding="utf-8"))
        result = run_worker(payload)
    except Exception as exc:
        config_payload = payload.get("config") if "payload" in locals() else None
        if config_payload is None:
            raise
        representation = config_payload.get("representation")
        if representation == "direct_tn":
            failed_config = TensorProgramConfig.from_dict(config_payload)
        elif representation == "spatial_transfer":
            failed_config = SpatialProgramConfig.from_dict(config_payload)
        else:
            failed_config = ProgramConfig.from_dict(config_payload)
        result = CandidateResult(
            config=failed_config,
            valid=False,
            failure=f"{type(exc).__name__}: {exc}",
            worker_pid=os.getpid(),
            parent_pid=payload.get("parent_pid"),
            peak_rss_bytes=_peak_rss_bytes(),
        )
    _write_json_atomic(args.result_json, result.to_dict())
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
