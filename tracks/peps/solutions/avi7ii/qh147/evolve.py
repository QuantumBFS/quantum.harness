from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback

import numpy as np
import psutil

from .checkpoint import Checkpoint, latest_checkpoint, load_checkpoint, save_checkpoint
from .compress import (
    CompressionObjective,
    ThermodynamicTolerances,
    ThermodynamicWeights,
    VariationalCompressor,
)
from .contract import BoundaryContractor
from .pepo import FinitePEPO
from .trotter import second_order_gates


_MODES = {"ordinary", "thermodynamic"}


@dataclass(frozen=True)
class ChainConfig:
    lx: int
    ly: int
    j: float
    h: float
    delta_beta: float
    beta_stop: float
    max_bond: int
    teacher_bond: int
    chi: int
    cutoff: float
    max_iterations: int
    optimizer: str
    epsilon_z: float
    epsilon_u: float
    contraction_noise: float
    lambda_z: float
    lambda_u: float
    lambda_hermiticity: float
    hermiticity_tolerance: float
    loss_acceptance_tolerance: float

    def __post_init__(self) -> None:
        if self.lx < 1 or self.ly < 1:
            raise ValueError("lattice extents must be positive")
        if not math.isfinite(self.j) or self.j <= 0:
            raise ValueError("J must be finite and positive")
        if not math.isfinite(self.h) or self.h < 0:
            raise ValueError("field must be finite and non-negative")
        if not math.isfinite(self.delta_beta) or self.delta_beta <= 0:
            raise ValueError("delta beta must be finite and positive")
        if not math.isfinite(self.beta_stop) or self.beta_stop <= 0:
            raise ValueError("beta stop must be finite and positive")
        steps = round(self.beta_stop / self.delta_beta)
        if not math.isclose(
            steps * self.delta_beta,
            self.beta_stop,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("beta stop must be an exact delta-beta multiple")
        if self.max_bond < 1:
            raise ValueError("maximum bond must be positive")
        if self.teacher_bond < self.max_bond:
            raise ValueError("teacher bond must not be smaller than student bond")
        if self.chi < 1:
            raise ValueError("chi must be positive")
        if not math.isfinite(self.cutoff) or self.cutoff < 0:
            raise ValueError("contraction cutoff must be finite and non-negative")
        if self.max_iterations < 1:
            raise ValueError("maximum iterations must be positive")
        if not self.optimizer:
            raise ValueError("optimizer must be non-empty")
        ThermodynamicTolerances(
            z=self.epsilon_z,
            u=self.epsilon_u,
            contraction_noise=self.contraction_noise,
        )
        ThermodynamicWeights(
            z=self.lambda_z,
            u=self.lambda_u,
            hermiticity=self.lambda_hermiticity,
        )
        for name, value in (
            ("hermiticity tolerance", self.hermiticity_tolerance),
            ("loss acceptance tolerance", self.loss_acceptance_tolerance),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

    @property
    def steps(self) -> int:
        return round(self.beta_stop / self.delta_beta)

    def config_sha256(self) -> str:
        payload = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ChainResult:
    accepted_betas: tuple[float, ...]
    resumed_from: float
    latest: Checkpoint | None


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _maximum_virtual_bond(pepo: FinitePEPO) -> int:
    inner = tuple(pepo.tn.inner_inds())
    return max((pepo.tn.ind_size(index) for index in inner), default=1)


def _production_compressor(config: ChainConfig, mode: str):
    contractor = BoundaryContractor(chi=config.chi, cutoff=config.cutoff)
    objective = CompressionObjective(
        contractor,
        j=config.j,
        h=config.h,
        tolerances=ThermodynamicTolerances(
            z=config.epsilon_z,
            u=config.epsilon_u,
            contraction_noise=config.contraction_noise,
        ),
        weights=ThermodynamicWeights(
            z=config.lambda_z,
            u=config.lambda_u,
            hermiticity=config.lambda_hermiticity,
        ),
    )
    return VariationalCompressor(
        objective,
        max_iterations=config.max_iterations,
        optimizer=config.optimizer,
        skip_optimization_tolerance=config.loss_acceptance_tolerance,
    )


def _complete_sequence(
    checkpoint_root: Path,
    *,
    completed_steps: int,
    config: ChainConfig,
    config_hash: str,
    mode: str,
) -> tuple[Checkpoint, ...]:
    checkpoints = []
    for step in range(1, completed_steps + 1):
        beta = round(step * config.delta_beta, 12)
        path = checkpoint_root / f"beta-{beta:.6f}"
        checkpoint = load_checkpoint(
            path,
            expected_config_sha256=config_hash,
        )
        if checkpoint.mode != mode:
            raise ValueError("checkpoint compression mode mismatch")
        checkpoints.append(checkpoint)
    return tuple(checkpoints)


def _finite_diagnostics(values: dict[str, object]) -> bool:
    return all(
        isinstance(value, (int, float)) and math.isfinite(float(value))
        for value in values.values()
    )


def run_chain(
    config: ChainConfig,
    run_root: Path,
    *,
    mode: str,
    compressor_factory=None,
    stop_after_steps: int | None = None,
) -> ChainResult:
    if mode not in _MODES:
        raise ValueError("compression mode must be ordinary or thermodynamic")
    if stop_after_steps is not None and stop_after_steps < 0:
        raise ValueError("stop-after-steps must be non-negative")

    run_root = Path(run_root)
    mode_root = run_root / mode
    checkpoint_root = mode_root / "checkpoints"
    config_hash = config.config_sha256()
    latest = latest_checkpoint(
        checkpoint_root,
        expected_config_sha256=config_hash,
    )
    if latest is None:
        pepo = FinitePEPO.identity(config.lx, config.ly)
        log_scale = 0.0
        completed_steps = 0
        resumed_from = 0.0
        accepted = []
    else:
        if latest.mode != mode:
            raise ValueError("checkpoint compression mode mismatch")
        if (latest.pepo.lx, latest.pepo.ly) != (config.lx, config.ly):
            raise ValueError("checkpoint lattice mismatch")
        completed_steps = round(latest.beta / config.delta_beta)
        if not math.isclose(
            completed_steps * config.delta_beta,
            latest.beta,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("checkpoint beta is outside the configured grid")
        sequence = _complete_sequence(
            checkpoint_root,
            completed_steps=completed_steps,
            config=config,
            config_hash=config_hash,
            mode=mode,
        )
        latest = sequence[-1]
        pepo = latest.pepo
        log_scale = latest.log_scale
        resumed_from = latest.beta
        accepted = [checkpoint.beta for checkpoint in sequence]

    compressor_builder = compressor_factory or _production_compressor
    compressor = compressor_builder(config, mode)
    validator = BoundaryContractor(chi=config.chi, cutoff=config.cutoff)
    gates = second_order_gates(
        config.lx,
        config.ly,
        j=config.j,
        h=config.h,
        delta_beta=config.delta_beta,
    )
    accepted_this_call = 0

    for step in range(completed_steps + 1, config.steps + 1):
        if (
            stop_after_steps is not None
            and accepted_this_call >= stop_after_steps
        ):
            break
        beta = round(step * config.delta_beta, 12)
        started = time.perf_counter()
        try:
            print(
                json.dumps(
                    {
                        "event": "evolution_stage",
                        "stage": "teacher_gates_start",
                        "mode": mode,
                        "beta": beta,
                        "gate_count": len(gates),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            teacher = pepo.copy()
            for gate in gates:
                teacher.apply_gate(
                    gate,
                    max_bond=config.teacher_bond,
                    cutoff=config.cutoff,
                )
            print(
                json.dumps(
                    {
                        "event": "evolution_stage",
                        "stage": "teacher_gates_complete",
                        "mode": mode,
                        "beta": beta,
                        "elapsed_seconds": time.perf_counter() - started,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            result = compressor.compress(
                teacher,
                max_bond=config.max_bond,
                mode=mode,
            )
            initial = asdict(result.initial.as_floats())
            final = asdict(result.final.as_floats())
            if not _finite_diagnostics(initial) or not _finite_diagnostics(final):
                raise FloatingPointError("non-finite compression diagnostics")
            if final["total"] > (
                initial["total"] + config.loss_acceptance_tolerance
            ):
                raise RuntimeError("objective loss increased")
            actual_bond = _maximum_virtual_bond(result.pepo)
            if result.max_bond > config.max_bond or actual_bond > config.max_bond:
                raise RuntimeError("compressed PEPO exceeds requested bond")

            removed_log_scale = result.pepo.renormalize_tensors()
            candidate_log_scale = log_scale + removed_log_scale
            point = validator.thermodynamic_point(
                result.pepo,
                j=config.j,
                h=config.h,
                log_scale=candidate_log_scale,
            ).as_floats()
            hermiticity = float(validator.hermiticity_residual(result.pepo))
            if not all(
                math.isfinite(value)
                for value in (point.z, point.u, hermiticity)
            ):
                raise FloatingPointError("non-finite acceptance diagnostic")
            if hermiticity > config.hermiticity_tolerance:
                raise RuntimeError("Hermiticity tolerance exceeded")

            diagnostics = {
                "initial": initial,
                "final": final,
                "iterations": result.iterations,
                "loss_history": list(result.loss_history),
                "max_bond": actual_bond,
                "budget": asdict(result.budget),
                "z": point.z,
                "u": point.u,
                "hermiticity_residual": hermiticity,
                "wall_seconds": time.perf_counter() - started,
                "peak_memory_bytes": psutil.Process().memory_info().rss,
            }
            path = checkpoint_root / f"beta-{beta:.6f}"
            print(
                json.dumps(
                    {
                        "event": "evolution_stage",
                        "stage": "checkpoint_start",
                        "mode": mode,
                        "beta": beta,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            latest = save_checkpoint(
                path,
                result.pepo,
                beta=beta,
                mode=mode,
                log_scale=candidate_log_scale,
                config_sha256=config_hash,
                diagnostics=diagnostics,
            )
            print(
                json.dumps(
                    {
                        "event": "evolution_stage",
                        "stage": "checkpoint_complete",
                        "mode": mode,
                        "beta": beta,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            pepo = latest.pepo
            log_scale = candidate_log_scale
            accepted.append(beta)
            accepted_this_call += 1
            _atomic_json(
                mode_root / "manifest.json",
                {
                    "status": "complete" if step == config.steps else "running",
                    "mode": mode,
                    "config_sha256": config_hash,
                    "accepted_betas": accepted,
                    "latest_beta": beta,
                },
            )
            print(
                json.dumps(
                    {
                        "event": "accepted",
                        "mode": mode,
                        "beta": beta,
                        **diagnostics,
                    },
                    sort_keys=True,
                    allow_nan=False,
                ),
                flush=True,
            )
        except Exception as error:
            failure = {
                "status": "failed",
                "mode": mode,
                "beta": beta,
                "config_sha256": config_hash,
                "error": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
            _atomic_json(mode_root / "failure.json", failure)
            print(json.dumps({"event": "failed", **failure}), flush=True)
            raise RuntimeError(f"beta {beta:g} failed: {error}") from error

    return ChainResult(
        accepted_betas=tuple(accepted),
        resumed_from=resumed_from,
        latest=latest,
    )
