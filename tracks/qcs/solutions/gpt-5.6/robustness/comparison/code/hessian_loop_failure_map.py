#!/usr/bin/env python3
"""Failure map for low-rank Hessian closed-loop Rydberg-CZ calibration.

This is the consolidated implementation for the proposal derived from
arXiv:2606.05060v1.  It uses the paper's perfect-blockade three-level model and
the analytical pulse parameters published in Evered et al., Nature 622, 268
(2023).  The script:

1. validates the analytical CZ and its five-dimensional fidelity Hessian;
2. scans distortion magnitude and principal/null-space orientation;
3. separates exact landscape failure from seven-point line-fit failure;
4. diagnoses Hessian breakdown, subspace rotation, channel residuals, noise,
   and explicitly named "weird/ill" controls;
5. writes nine figures and incremental machine-readable evidence.

Run from the repository root:

    JAX_ENABLE_X64=true MPLCONFIGDIR=/tmp/hessian-loop-mpl \
      .venv/bin/python \
      robustness/comparison/code/hessian_loop_failure_map.py \
      --run-dir /tmp/ql1f-robustness-full

Use ``--baseline-only`` to execute only the source-gate and Hessian acceptance
gate.  ``--run-dir`` is mandatory and must name a new or empty directory, so a
run cannot silently overwrite the archived evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hessian-loop-mpl")

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import matplotlib
import numpy as np
import scipy
from jax import lax
from scipy import optimize

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


Array = jax.Array
ETA_VALUES = np.asarray([0.01, 0.03, 0.06, 0.10, 0.20, 0.35, 0.60, 1.00])
P_VALUES = np.asarray([0.0, 0.5, 1.0])
NOISE_VALUES = np.asarray([0.0, 1e-6, 1e-5, 1e-4, 1e-3])
SUCCESS_TARGET = 1e-5
MAX_CYCLES = 8
SOURCE_SCRIPT_PATH = "code/hessian_loop_failure_map.py"
REQUIREMENTS_PATH = "requirements.txt"
MANIFEST_PATH = "artifact_manifest.json"
PROGRESS_PATH = "progress.json"


def progress(message: str) -> None:
    print(message, flush=True)


def dump_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_record() -> dict[str, Any]:
    comparison_root = Path(__file__).resolve().parent.parent
    records: dict[str, Any] = {}
    for name, relative_path in (
        ("script", SOURCE_SCRIPT_PATH),
        ("requirements", REQUIREMENTS_PATH),
    ):
        source_path = comparison_root / relative_path
        records[name] = {
            "path": relative_path,
            "bytes": source_path.stat().st_size,
            "sha256": sha256_file(source_path),
        }
    return records


def input_settings(
    model: "RydbergCZModel", args: argparse.Namespace
) -> dict[str, Any]:
    return {
        "execution": {
            "baseline_only": bool(args.baseline_only),
            "seeds_per_cell": int(args.seeds),
            "max_wall_seconds": float(args.max_wall_seconds),
        },
        "model": {
            "name": "perfect-blockade symmetric Rydberg-CZ",
            "n_time": int(model.n_time),
            "real_control_coordinates": int(2 * model.n_time),
            "omega_scale": float(model.omega_scale),
            "amplitude_phase": float(model.amplitude_phase),
            "phase_frequency": float(model.phase_frequency),
            "phase_offset": float(model.phase_offset),
            "detuning_offset": float(model.detuning_offset),
            "duration": float(model.duration),
        },
        "scan": {
            "eta_values": [float(value) for value in ETA_VALUES],
            "p_parallel_values": [float(value) for value in P_VALUES],
            "noise_values": [float(value) for value in NOISE_VALUES],
            "noise_eta_values": [0.06, 0.35],
            "success_target": float(SUCCESS_TARGET),
            "maximum_cycles": int(MAX_CYCLES),
            "line_fit_samples": 7,
            "line_fit_bracket_expansions": 4,
            "distortion_sine_modes": 12,
            "active_rank_relative_threshold": 1e-8,
            "hamiltonian_strengths": [0.0, 0.05, 0.10, 0.20, 0.40],
            "named_pathologies": [
                "pure-null",
                "zero-crossing",
                "symmetry-breaking",
                "new-leakage",
                "slow-drift",
                "actuator-clipping",
            ],
        },
        "randomness": {
            "generator": "numpy.random.default_rng",
            "seed_schedule": "deterministic integer formulas in source",
        },
    }


def timing_record(started: float) -> dict[str, Any]:
    wall_seconds = time.perf_counter() - started
    return {
        "wall_seconds": wall_seconds,
        "clock": "time.perf_counter",
        "scope": (
            "End-to-end process wall time from immediately before the first "
            "output write through summary construction."
        ),
        "jax_warm_cold_state": "uncontrolled",
        "interpretation": (
            "Host load, CPU model, JAX/XLA compilation caches, and cold-versus-"
            "warm process state can materially change this diagnostic timing. "
            "It is not a scientific acceptance criterion."
        ),
    }


def manifest_candidate(relative_path: str) -> bool:
    return (
        relative_path not in {MANIFEST_PATH, PROGRESS_PATH}
        and not relative_path.endswith(".tmp")
    )


def build_artifact_manifest(run_dir: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(run_dir).as_posix()
        if not manifest_candidate(relative_path):
            continue
        artifacts.append(
            {
                "path": relative_path,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": 1,
        "manifest_is_self_contained": False,
        "excluded_paths": [MANIFEST_PATH, PROGRESS_PATH, "*.tmp"],
        "artifacts": artifacts,
    }


def write_artifact_manifest(run_dir: Path) -> None:
    dump_json(build_artifact_manifest(run_dir), run_dir / MANIFEST_PATH)


def prepare_run_directory(parser: argparse.ArgumentParser, requested: Path) -> Path:
    run_dir = requested.expanduser().resolve()
    if run_dir.exists():
        if not run_dir.is_dir():
            parser.error(f"--run-dir is not a directory: {requested}")
        if any(run_dir.iterdir()):
            parser.error(
                "--run-dir must be new or empty; refusing to overwrite existing "
                f"evidence: {requested}"
            )
    else:
        run_dir.mkdir(parents=True)
    (run_dir / "data").mkdir()
    (run_dir / "figs").mkdir()
    return run_dir


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def block_float(value: Array | float) -> float:
    if isinstance(value, jax.Array):
        value.block_until_ready()
    return float(np.asarray(value))


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Two-sided Wilson score interval for a binomial success fraction."""
    if total <= 0:
        return 0.0, 1.0
    fraction = successes / total
    denominator = 1.0 + z**2 / total
    center = (fraction + z**2 / (2.0 * total)) / denominator
    half_width = (
        z
        * math.sqrt(
            fraction * (1.0 - fraction) / total + z**2 / (4.0 * total**2)
        )
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def wrap_phase(value: Array) -> Array:
    return jnp.arctan2(jnp.sin(value), jnp.cos(value))


def environment_record() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "jax": jax.__version__,
        "jaxlib": jax.lib.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "jax_devices": [str(device) for device in jax.devices()],
        "jax_x64": bool(jax.config.x64_enabled),
    }


class RydbergCZModel:
    """Exact piecewise-constant propagation in the perfect-blockade sectors."""

    def __init__(self, n_time: int = 256):
        self.n_time = int(n_time)
        self.omega_scale = 1.0
        self.amplitude_phase = 2.0 * np.pi * 0.1122
        self.phase_frequency = 1.0431 * self.omega_scale
        self.phase_offset = -0.7318
        self.detuning_offset = 0.0
        self.duration = 2.0 * np.pi * 1.215 / self.omega_scale
        self.dt = self.duration / self.n_time
        self.times = (np.arange(self.n_time) + 0.5) * self.dt
        phase = (
            self.amplitude_phase
            * np.cos(self.phase_frequency * self.times - self.phase_offset)
            + self.detuning_offset * self.times
        )
        self.omega0_np = self.omega_scale * np.exp(1j * phase)
        self.omega0 = jnp.asarray(self.omega0_np, dtype=jnp.complex128)
        self.x0_np = np.concatenate([self.omega0_np.real, self.omega0_np.imag])
        self.x0 = jnp.asarray(self.x0_np, dtype=jnp.float64)
        self.eye2 = jnp.eye(2, dtype=jnp.complex128)
        self.eye3 = jnp.eye(3, dtype=jnp.complex128)

        baseline_a1, baseline_l1 = self._propagate_sector(self.omega0, 1.0, 0.0)
        baseline_a2, baseline_l2 = self._propagate_sector(
            self.omega0, np.sqrt(2.0), 0.0
        )
        self.baseline_a1 = baseline_a1
        self.baseline_a2 = baseline_a2
        self.baseline_l1 = baseline_l1
        self.baseline_l2 = baseline_l2
        self.baseline_leakage = jnp.asarray(
            [jnp.abs(baseline_l1) ** 2, jnp.abs(baseline_l2) ** 2]
        )

        self.loss = jax.jit(self._loss)
        self.loss_batch = jax.jit(jax.vmap(self._loss))
        self.diagnostics = jax.jit(self._diagnostics)
        self.channel_metric = jax.jit(self._channel_metric)
        self.channel_jacobian = jax.jit(jax.jacrev(self._channel_features))
        self.hessian = jax.jit(self._gauss_newton_hessian)
        self.loss_detuning = jax.jit(self._loss_detuning)
        self.loss_detuning_batch = jax.jit(
            jax.vmap(self._loss_detuning, in_axes=(0, None))
        )
        self.loss_asymmetric = jax.jit(self._loss_asymmetric)
        self.loss_asymmetric_batch = jax.jit(
            jax.vmap(self._loss_asymmetric, in_axes=(0, None))
        )
        self.loss_new_leakage = jax.jit(self._loss_new_leakage)
        self.loss_new_leakage_batch = jax.jit(
            jax.vmap(self._loss_new_leakage, in_axes=(0, None))
        )
        self.loss_clipped = jax.jit(self._loss_clipped)
        self.loss_clipped_batch = jax.jit(
            jax.vmap(self._loss_clipped, in_axes=(0, None))
        )

    def _complex_control(self, x: Array) -> Array:
        return x[: self.n_time] + 1j * x[self.n_time :]

    def _two_level_step(
        self, unitary: Array, values: tuple[Array, Array, Array]
    ) -> tuple[Array, None]:
        omega, coupling, detuning = values
        amplitude = 0.5 * coupling * omega
        half_detuning = 0.5 * detuning
        q = jnp.sqrt(jnp.abs(amplitude) ** 2 + half_detuning**2)
        hprime = jnp.asarray(
            [[-half_detuning, jnp.conj(amplitude)], [amplitude, half_detuning]],
            dtype=jnp.complex128,
        )
        sinc_factor = self.dt * jnp.sinc(q * self.dt / jnp.pi)
        step = jnp.exp(-0.5j * detuning * self.dt) * (
            jnp.cos(q * self.dt) * self.eye2 - 1j * sinc_factor * hprime
        )
        return step @ unitary, None

    def _propagate_sector(
        self, omega: Array, coupling: float, detuning: float | Array
    ) -> tuple[Array, Array]:
        detunings = jnp.broadcast_to(jnp.asarray(detuning), (self.n_time,))
        couplings = jnp.broadcast_to(jnp.asarray(coupling), (self.n_time,))
        final, _ = lax.scan(
            self._two_level_step,
            self.eye2,
            (omega, couplings, detunings),
        )
        return final[0, 0], final[1, 0]

    def _three_level_step(
        self, unitary: Array, values: tuple[Array, Array]
    ) -> tuple[Array, None]:
        primary, extra = values
        a = 0.5 * primary
        b = 0.5 * extra
        hamiltonian = jnp.asarray(
            [
                [0.0, jnp.conj(a), jnp.conj(b)],
                [a, 0.0, 0.0],
                [b, 0.0, 0.0],
            ],
            dtype=jnp.complex128,
        )
        q = jnp.sqrt(jnp.abs(a) ** 2 + jnp.abs(b) ** 2)
        linear = -1j * self.dt * jnp.sinc(q * self.dt / jnp.pi)
        quadratic = (
            -0.5
            * self.dt**2
            * jnp.sinc(q * self.dt / (2.0 * jnp.pi)) ** 2
        )
        step = self.eye3 + linear * hamiltonian + quadratic * (
            hamiltonian @ hamiltonian
        )
        return step @ unitary, None

    def _propagate_three_level(
        self, primary: Array, extra: Array
    ) -> tuple[Array, Array, Array]:
        final, _ = lax.scan(
            self._three_level_step, self.eye3, (primary, extra)
        )
        return final[0, 0], final[1, 0], final[2, 0]

    def _average_fidelity(
        self, a00: Array, a01: Array, a10: Array, a11: Array
    ) -> Array:
        # Local single-qubit Z phases are freely correctable.  For a diagonal
        # CZ, choose those phases from the two single-excitation return
        # amplitudes, leaving only the nonlinear controlled phase observable.
        q01 = a01 / jnp.maximum(jnp.abs(a01), 1e-30)
        q10 = a10 / jnp.maximum(jnp.abs(a10), 1e-30)
        diagonal = jnp.asarray(
            [
                a00,
                jnp.abs(a01),
                jnp.abs(a10),
                -jnp.conj(q01 * q10) * a11,
            ]
        )
        fidelity = (
            jnp.abs(jnp.sum(diagonal)) ** 2 + jnp.sum(jnp.abs(diagonal) ** 2)
        ) / 20.0
        return jnp.real(fidelity)

    def _loss(self, x: Array) -> Array:
        omega = self._complex_control(x)
        a1, _ = self._propagate_sector(omega, 1.0, 0.0)
        a2, _ = self._propagate_sector(omega, np.sqrt(2.0), 0.0)
        return 1.0 - self._average_fidelity(1.0 + 0.0j, a1, a1, a2)

    def _channel_features(self, x: Array) -> Array:
        """Five first-order channels that span the paper's Hessian.

        Subtracting the rounded source pulse's residual leakage and nonlinear
        phase does not change the Jacobian, but makes the local quadratic model
        explicitly describe distortion-induced error rather than source
        rounding.
        """
        omega = self._complex_control(x)
        a1, l1 = self._propagate_sector(omega, 1.0, 0.0)
        a2, l2 = self._propagate_sector(omega, np.sqrt(2.0), 0.0)
        controlled_phase = wrap_phase(jnp.angle(a2) - 2.0 * jnp.angle(a1))
        baseline_phase = wrap_phase(
            jnp.angle(self.baseline_a2) - 2.0 * jnp.angle(self.baseline_a1)
        )
        return jnp.asarray(
            [
                jnp.real(l1 - self.baseline_l1),
                jnp.imag(l1 - self.baseline_l1),
                jnp.real(l2 - self.baseline_l2),
                jnp.imag(l2 - self.baseline_l2),
                wrap_phase(controlled_phase - baseline_phase),
            ],
            dtype=jnp.float64,
        )

    def _channel_metric(self, x: Array) -> Array:
        """Nonlinear five-channel error relative to the rounded source pulse."""
        features = self._channel_features(x)
        weights = jnp.asarray([0.5, 0.5, 0.25, 0.25, 0.15])
        return jnp.sum(weights * features**2)

    def _gauss_newton_hessian(self, x: Array) -> Array:
        jacobian = jax.jacrev(self._channel_features)(x)
        # 1-F = 1/2 |l_01|^2 + 1/4 |l_11|^2
        #       + 3/20 theta_CZ^2 + O(delta Omega^3).
        weights = jnp.asarray([0.5, 0.5, 0.25, 0.25, 0.15])
        # Match the convention 1-F = 1/2 delta^T H delta.
        return 2.0 * jacobian.T @ (weights[:, None] * jacobian)

    def _diagnostics(self, x: Array) -> Array:
        omega = self._complex_control(x)
        a1, l1 = self._propagate_sector(omega, 1.0, 0.0)
        a2, l2 = self._propagate_sector(omega, np.sqrt(2.0), 0.0)
        controlled_phase = wrap_phase(jnp.angle(a2) - 2.0 * jnp.angle(a1))
        nonlinear_phase = wrap_phase(controlled_phase - jnp.pi)
        return jnp.asarray(
            [
                self._loss(x),
                jnp.abs(l1) ** 2,
                jnp.abs(l2) ** 2,
                jnp.angle(a1),
                jnp.angle(a2),
                nonlinear_phase,
                controlled_phase,
            ],
            dtype=jnp.float64,
        )

    def _loss_detuning(self, x: Array, detuning: Array) -> Array:
        omega = self._complex_control(x)
        a1, _ = self._propagate_sector(omega, 1.0, detuning)
        a2, _ = self._propagate_sector(omega, np.sqrt(2.0), detuning)
        return 1.0 - self._average_fidelity(1.0 + 0.0j, a1, a1, a2)

    def _loss_asymmetric(self, x: Array, differential: Array) -> Array:
        omega = self._complex_control(x)
        a01, _ = self._propagate_sector(omega + differential, 1.0, 0.0)
        a10, _ = self._propagate_sector(omega - differential, 1.0, 0.0)
        a11, _ = self._propagate_sector(omega, np.sqrt(2.0), 0.0)
        return 1.0 - self._average_fidelity(1.0 + 0.0j, a01, a10, a11)

    def _loss_new_leakage(self, x: Array, extra: Array) -> Array:
        omega = self._complex_control(x)
        a01, _, _ = self._propagate_three_level(omega, extra)
        a10, _ = self._propagate_sector(omega, 1.0, 0.0)
        a11, _ = self._propagate_sector(omega, np.sqrt(2.0), 0.0)
        return 1.0 - self._average_fidelity(1.0 + 0.0j, a01, a10, a11)

    def _loss_clipped(self, x: Array, maximum: Array) -> Array:
        omega = self._complex_control(x)
        amplitude = jnp.abs(omega)
        effective = omega * jnp.minimum(1.0, maximum / jnp.maximum(amplitude, 1e-30))
        effective_x = jnp.concatenate([jnp.real(effective), jnp.imag(effective)])
        return self._loss(effective_x)

    def target_controlled_phase(self) -> float:
        return block_float(
            wrap_phase(
                jnp.angle(self.baseline_a2) - 2.0 * jnp.angle(self.baseline_a1)
            )
        )


@dataclass
class Evaluator:
    scalar: Callable[..., Array]
    batch: Callable[..., Array]
    args: tuple[Any, ...] = ()

    def one(self, x: np.ndarray) -> float:
        return block_float(self.scalar(jnp.asarray(x), *self.args))

    def many(self, xs: np.ndarray) -> np.ndarray:
        values = self.batch(jnp.asarray(xs), *self.args)
        values.block_until_ready()
        return np.asarray(values, dtype=float)


def smooth_distortion(
    model: RydbergCZModel,
    principal: np.ndarray,
    seed: int,
    p_parallel: float,
    eta: float,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    tau = model.times / model.duration
    modes = np.arange(1, 13)
    basis = np.sin(np.pi * tau[:, None] * modes[None, :])
    real = basis @ rng.normal(size=len(modes))
    imag = basis @ rng.normal(size=len(modes))
    raw = np.concatenate([real, imag])
    raw /= np.linalg.norm(raw)
    parallel = principal @ (principal.T @ raw)
    perpendicular = raw - parallel
    pnorm = np.linalg.norm(parallel)
    qnorm = np.linalg.norm(perpendicular)
    if pnorm < 1e-12:
        parallel = principal[:, seed % principal.shape[1]]
        pnorm = 1.0
    if qnorm < 1e-12:
        trial = np.roll(raw, 1)
        perpendicular = trial - principal @ (principal.T @ trial)
        qnorm = np.linalg.norm(perpendicular)
    direction = (
        np.sqrt(p_parallel) * parallel / pnorm
        + np.sqrt(1.0 - p_parallel) * perpendicular / qnorm
    )
    direction /= np.linalg.norm(direction)
    return float(eta) * np.sqrt(model.n_time) * direction


def seven_point_loop(
    evaluator: Evaluator,
    initial: np.ndarray,
    principal: np.ndarray,
    *,
    seed: int,
    noise_sigma: float = 0.0,
    maximum_cycles: int = MAX_CYCLES,
    success_target: float = SUCCESS_TARGET,
    drift_per_cycle: np.ndarray | None = None,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    x = np.asarray(initial, dtype=float).copy()
    n_time = x.size // 2
    trace: list[dict[str, Any]] = [
        {
            "step": 0,
            "cycle": 0,
            "mode": -1,
            "exact_infidelity": evaluator.one(x),
            "scan_radius": 0.0,
            "fit_curvature": np.nan,
            "fit_vertex": 0.0,
        }
    ]
    if trace[0]["exact_infidelity"] <= success_target:
        return {
            "success": True,
            "cycles": 0,
            "steps": 0,
            "final_infidelity": trace[0]["exact_infidelity"],
            "x_final": x,
            "trace": trace,
        }
    base_radius = 0.10 * np.sqrt(n_time)
    for cycle in range(maximum_cycles):
        if drift_per_cycle is not None and cycle > 0:
            x = x + drift_per_cycle
        for mode_index in range(principal.shape[1]):
            direction = principal[:, mode_index]
            # A closed loop should refine its coefficient resolution as it
            # approaches the optimum.  Reusing a wide bracket creates a purely
            # numerical floor even on a quadratic landscape.
            radius = base_radius * (0.5**cycle)
            fit_curvature = np.nan
            vertex = 0.0
            exact_values = np.asarray([])
            for _ in range(4):
                coefficients = np.linspace(-radius, radius, 7)
                candidates = x[None, :] + coefficients[:, None] * direction[None, :]
                exact_values = evaluator.many(candidates)
                observed = exact_values + rng.normal(
                    loc=0.0, scale=noise_sigma, size=exact_values.shape
                )
                discrete_index = int(np.argmin(observed))
                if discrete_index in (0, len(coefficients) - 1):
                    radius *= 2.0
                    continue
                break
            design = np.column_stack(
                [coefficients**2, coefficients, np.ones_like(coefficients)]
            )
            fitted, *_ = np.linalg.lstsq(design, observed, rcond=None)
            curvature, slope, _ = fitted
            fit_curvature = float(curvature)
            if np.isfinite(curvature) and curvature > 0.0:
                vertex = float(np.clip(-slope / (2.0 * curvature), -radius, radius))
            else:
                vertex = float(coefficients[int(np.argmin(observed))])
            x = x + vertex * direction
            exact = evaluator.one(x)
            trace.append(
                {
                    "step": len(trace),
                    "cycle": cycle + 1,
                    "mode": mode_index,
                    "exact_infidelity": exact,
                    "scan_radius": radius,
                    "fit_curvature": fit_curvature,
                    "fit_vertex": vertex,
                }
            )
            if exact <= success_target:
                return {
                    "success": True,
                    "cycles": cycle + 1,
                    "steps": len(trace) - 1,
                    "final_infidelity": exact,
                    "x_final": x,
                    "trace": trace,
                }
    return {
        "success": bool(trace[-1]["exact_infidelity"] <= success_target),
        "cycles": maximum_cycles,
        "steps": len(trace) - 1,
        "final_infidelity": trace[-1]["exact_infidelity"],
        "x_final": x,
        "trace": trace,
    }


def exact_line_loop(
    evaluator: Evaluator,
    initial: np.ndarray,
    principal: np.ndarray,
    maximum_cycles: int = MAX_CYCLES,
) -> dict[str, Any]:
    x = np.asarray(initial, dtype=float).copy()
    radius = 0.8 * np.sqrt(x.size // 2)
    trace = [
        {
            "step": 0,
            "cycle": 0,
            "mode": -1,
            "exact_infidelity": evaluator.one(x),
        }
    ]
    for cycle in range(maximum_cycles):
        for mode_index in range(principal.shape[1]):
            direction = principal[:, mode_index]

            def objective(coefficient: float) -> float:
                return evaluator.one(x + coefficient * direction)

            result = optimize.minimize_scalar(
                objective,
                bounds=(-radius, radius),
                method="bounded",
                options={"xatol": 1e-6, "maxiter": 40},
            )
            x = x + float(result.x) * direction
            exact = evaluator.one(x)
            trace.append(
                {
                    "step": len(trace),
                    "cycle": cycle + 1,
                    "mode": mode_index,
                    "exact_infidelity": exact,
                }
            )
            if exact <= SUCCESS_TARGET:
                return {
                    "success": True,
                    "cycles": cycle + 1,
                    "steps": len(trace) - 1,
                    "final_infidelity": exact,
                    "x_final": x,
                    "trace": trace,
                }
    return {
        "success": False,
        "cycles": maximum_cycles,
        "steps": len(trace) - 1,
        "final_infidelity": trace[-1]["exact_infidelity"],
        "x_final": x,
        "trace": trace,
    }


def principal_angle(
    reference: np.ndarray, candidate: np.ndarray
) -> tuple[float, float]:
    singular_values = np.linalg.svd(reference.T @ candidate, compute_uv=False)
    singular_values = np.clip(singular_values, 0.0, 1.0)
    angles = np.degrees(np.arccos(singular_values))
    return float(np.max(angles)), float(np.min(singular_values))


def hessian_decomposition(
    model: RydbergCZModel, x: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hessian = np.asarray(model.hessian(jnp.asarray(x)).block_until_ready())
    hessian = 0.5 * (hessian + hessian.T)
    eigenvalues, eigenvectors = np.linalg.eigh(hessian)
    order = np.argsort(eigenvalues)[::-1]
    return hessian, eigenvalues[order], eigenvectors[:, order]


def baseline_stage(
    model: RydbergCZModel, run_dir: Path
) -> dict[str, Any]:
    progress("Baseline 1/3: compiling exact pulse propagation...",)
    started = time.perf_counter()
    diagnostics = np.asarray(model.diagnostics(model.x0).block_until_ready())
    propagation_seconds = time.perf_counter() - started
    progress(
        "Baseline 2/3: compiling and diagonalizing the 512×512 fidelity Hessian..."
    )
    hessian_started = time.perf_counter()
    hessian, eigenvalues, eigenvectors = hessian_decomposition(model, model.x0_np)
    hessian_seconds = time.perf_counter() - hessian_started
    positive_reference = max(float(eigenvalues[0]), 1e-30)
    active_rank = int(np.count_nonzero(eigenvalues / positive_reference > 1e-8))
    controlled_phase = model.target_controlled_phase()
    phase_error_to_pi = abs(abs(controlled_phase) - np.pi)
    baseline_infidelity = float(diagnostics[0])
    accepted = (
        baseline_infidelity <= 1e-5
        and active_rank == 5
        and phase_error_to_pi <= 5e-4
    )
    payload = {
        "accepted": accepted,
        "baseline_infidelity": baseline_infidelity,
        "leakage_01": float(diagnostics[1]),
        "leakage_11": float(diagnostics[2]),
        "controlled_phase": controlled_phase,
        "phase_error_to_pi": phase_error_to_pi,
        "active_rank": active_rank,
        "largest_eigenvalue": float(eigenvalues[0]),
        "sixth_to_first_eigenvalue": float(
            abs(eigenvalues[5]) / positive_reference
        ),
        "propagation_compile_seconds": propagation_seconds,
        "hessian_compile_seconds": hessian_seconds,
        "environment": environment_record(),
    }
    np.savez(
        run_dir / "data" / "baseline.npz",
        x0=model.x0_np,
        omega0=model.omega0_np,
        times=model.times,
        hessian=hessian,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        diagnostics=diagnostics,
    )
    dump_json(payload, run_dir / "data" / "baseline.json")
    progress(
        "Baseline 3/3: "
        f"1-F={baseline_infidelity:.3e}, rank={active_rank}, "
        f"|controlled phase|-pi={phase_error_to_pi:.2e}, accepted={accepted}"
    )
    if not accepted:
        raise RuntimeError(
            "Baseline acceptance failed; extension scan is blocked. "
            f"Evidence: {run_dir / 'data' / 'baseline.json'}"
        )
    return {
        "payload": payload,
        "hessian": hessian,
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "principal": eigenvectors[:, :5],
    }


def plot_baseline(
    model: RydbergCZModel,
    baseline: dict[str, Any],
    out: Path,
) -> None:
    eigenvalues = baseline["eigenvalues"]
    principal = baseline["principal"]
    tau = model.times / model.duration
    fig = plt.figure(figsize=(13.5, 8.2), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.0, 1.25])
    ax_amp = fig.add_subplot(grid[0, 0])
    ax_phase = fig.add_subplot(grid[0, 1])
    ax_spec = fig.add_subplot(grid[0, 2])
    ax_real = fig.add_subplot(grid[1, :2])
    ax_imag = fig.add_subplot(grid[1, 2])
    ax_amp.plot(tau, np.abs(model.omega0_np), color="#3b6fb6", lw=2)
    ax_amp.set(xlabel="normalized time  t/T", ylabel="|Ω_c|/Ω", title="Analytical pulse")
    ax_phase.plot(tau, np.unwrap(np.angle(model.omega0_np)), color="#8b5fbf", lw=2)
    ax_phase.set(xlabel="normalized time  t/T", ylabel="phase ϕ (rad)", title="Pulse phase")
    normalized = np.abs(eigenvalues) / max(abs(eigenvalues[0]), 1e-30)
    ax_spec.semilogy(np.arange(1, 15), normalized[:14], "o-", color="#167f7a")
    ax_spec.axhline(1e-8, ls="--", color="0.45", lw=1, label="rank threshold")
    ax_spec.axvspan(0.5, 5.5, color="#3b6fb6", alpha=0.10)
    ax_spec.set(
        xlabel="Hessian mode",
        ylabel="|λᵢ|/λ₁",
        title="Five-mode fidelity Hessian",
        ylim=(1e-13, 2),
    )
    ax_spec.legend(frameon=False)
    colors = plt.cm.viridis(np.linspace(0.05, 0.9, 5))
    scale = np.sqrt(model.n_time)
    for index, color in enumerate(colors):
        ax_real.plot(tau, scale * principal[: model.n_time, index], color=color, label=f"v{index+1}")
        ax_imag.plot(tau, scale * principal[model.n_time :, index], color=color)
    ax_real.set(
        xlabel="normalized time  t/T",
        ylabel="√N Re(vᵢ)",
        title="Principal directions — real quadrature",
    )
    ax_imag.set(
        xlabel="normalized time  t/T",
        ylabel="√N Im(vᵢ)",
        title="Principal directions — imaginary quadrature",
    )
    ax_real.legend(ncol=5, frameon=False, loc="upper center")
    fig.suptitle("Source-gate acceptance: exact CZ and rank-five Hessian", fontsize=15)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def core_scan(
    model: RydbergCZModel,
    principal: np.ndarray,
    hessian: np.ndarray,
    run_dir: Path,
    seeds: int,
    deadline: float,
) -> tuple[list[dict[str, Any]], dict[tuple[float, float, int], dict[str, Any]]]:
    evaluator = Evaluator(model.loss, model.loss_batch)
    rows: list[dict[str, Any]] = []
    runs: dict[tuple[float, float, int], dict[str, Any]] = {}
    total = len(ETA_VALUES) * len(P_VALUES) * seeds
    completed = 0
    scan_started = time.perf_counter()
    for eta in ETA_VALUES:
        if time.perf_counter() > deadline:
            raise TimeoutError("Local scientific-runtime limit reached during core scan")
        for p_parallel in P_VALUES:
            for seed in range(seeds):
                delta = smooth_distortion(
                    model, principal, seed, float(p_parallel), float(eta)
                )
                initial = model.x0_np + delta
                initial_loss = evaluator.one(initial)
                nonlinear_channel_error = block_float(
                    model.channel_metric(jnp.asarray(initial))
                )
                quadratic = float(0.5 * delta @ hessian @ delta)
                result = seven_point_loop(
                    evaluator,
                    initial,
                    principal,
                    seed=10_000 + 100 * seed + int(1000 * eta) + int(10 * p_parallel),
                )
                key = (float(eta), float(p_parallel), seed)
                runs[key] = result
                relative_residual = abs(nonlinear_channel_error - quadratic) / max(
                    nonlinear_channel_error, 1e-10
                )
                rows.append(
                    {
                        "eta": float(eta),
                        "p_parallel": float(p_parallel),
                        "seed": seed,
                        "initial_infidelity": initial_loss,
                        "nonlinear_channel_error": nonlinear_channel_error,
                        "quadratic_infidelity": quadratic,
                        "quadratic_absolute_residual": nonlinear_channel_error
                        - quadratic,
                        "quadratic_relative_residual": relative_residual,
                        "success": bool(result["success"]),
                        "cycles": int(result["cycles"]),
                        "steps": int(result["steps"]),
                        "final_infidelity": float(result["final_infidelity"]),
                        "improvement_factor": initial_loss
                        / max(float(result["final_infidelity"]), 1e-16),
                    }
                )
                completed += 1
        write_csv(rows, run_dir / "data" / "core_scan.csv")
        progress(
            f"Core scan: eta={eta:.2f} complete, {completed}/{total} trials; "
            f"core-scan wall={time.perf_counter() - scan_started:.1f}s"
        )
    return rows, runs


def representative_oracle_runs(
    model: RydbergCZModel,
    principal: np.ndarray,
) -> dict[float, dict[str, Any]]:
    evaluator = Evaluator(model.loss, model.loss_batch)
    output: dict[float, dict[str, Any]] = {}
    for eta in (0.10, 0.35, 0.60):
        delta = smooth_distortion(model, principal, 0, 0.5, eta)
        output[eta] = exact_line_loop(evaluator, model.x0_np + delta, principal)
    return output


def subspace_rotation_scan(
    model: RydbergCZModel,
    principal: np.ndarray,
    run_dir: Path,
    deadline: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p_parallel in P_VALUES:
        for eta in ETA_VALUES:
            if time.perf_counter() > deadline:
                raise TimeoutError("Local scientific-runtime limit reached during rotation scan")
            delta = smooth_distortion(model, principal, 0, float(p_parallel), float(eta))
            _, eigenvalues, eigenvectors = hessian_decomposition(
                model, model.x0_np + delta
            )
            angle, overlap = principal_angle(principal, eigenvectors[:, :5])
            rows.append(
                {
                    "eta": float(eta),
                    "p_parallel": float(p_parallel),
                    "largest_principal_angle_deg": angle,
                    "minimum_subspace_overlap": overlap,
                    "local_positive_modes": int(np.count_nonzero(eigenvalues > 1e-10)),
                }
            )
        write_csv(rows, run_dir / "data" / "subspace_rotation.csv")
        progress(f"Subspace rotation: p_parallel={p_parallel:.1f} complete")
    return rows


def compute_channel_rows(
    model: RydbergCZModel,
    principal: np.ndarray,
    core_runs: dict[tuple[float, float, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for eta in (0.10, 0.35, 0.60):
        delta = smooth_distortion(model, principal, 0, 0.5, eta)
        initial = model.x0_np + delta
        final = np.asarray(core_runs[(eta, 0.5, 0)]["x_final"])
        for stage, x in (("initial", initial), ("final", final)):
            diagnostics = np.asarray(model.diagnostics(jnp.asarray(x)).block_until_ready())
            rows.append(
                {
                    "eta": eta,
                    "stage": stage,
                    "infidelity": float(diagnostics[0]),
                    "leakage_01": float(diagnostics[1]),
                    "leakage_11": float(diagnostics[2]),
                    "nonlinear_phase_abs": abs(float(diagnostics[5])),
                    "phase_proxy": float(diagnostics[5] ** 2 / 5.0),
                }
            )
    return rows


def noise_scan(
    model: RydbergCZModel,
    principal: np.ndarray,
    run_dir: Path,
    seeds: int,
    deadline: float,
) -> list[dict[str, Any]]:
    evaluator = Evaluator(model.loss, model.loss_batch)
    rows: list[dict[str, Any]] = []
    for eta in (0.06, 0.35):
        for sigma in NOISE_VALUES:
            for seed in range(seeds):
                if time.perf_counter() > deadline:
                    raise TimeoutError("Local scientific-runtime limit reached during noise scan")
                delta = smooth_distortion(model, principal, seed, 1.0, eta)
                result = seven_point_loop(
                    evaluator,
                    model.x0_np + delta,
                    principal,
                    seed=700_000 + seed + int(eta * 1000) + int(sigma * 1e8),
                    noise_sigma=float(sigma),
                )
                curvatures = [
                    row["fit_curvature"]
                    for row in result["trace"][1:]
                    if np.isfinite(row.get("fit_curvature", np.nan))
                ]
                rows.append(
                    {
                        "eta": eta,
                        "sigma_F": float(sigma),
                        "seed": seed,
                        "success": bool(result["success"]),
                        "final_infidelity": float(result["final_infidelity"]),
                        "median_fitted_curvature": float(np.median(curvatures))
                        if curvatures
                        else np.nan,
                        "nonpositive_fit_fraction": float(
                            np.mean(np.asarray(curvatures) <= 0)
                        )
                        if curvatures
                        else np.nan,
                    }
                )
            write_csv(rows, run_dir / "data" / "noise_scan.csv")
            progress(
                f"Noise scan: eta={eta:.2f}, sigma_F={sigma:.0e} complete"
            )
    return rows


def pathology_runs(
    model: RydbergCZModel,
    principal: np.ndarray,
    run_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    standard = Evaluator(model.loss, model.loss_batch)
    outputs: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    pure_null = model.x0_np + smooth_distortion(model, principal, 2, 0.0, 0.60)
    outputs["pure-null"] = seven_point_loop(
        standard, pure_null, principal, seed=8101
    )

    tau = model.times / model.duration
    envelope = np.exp(-0.5 * ((tau - 0.5) / 0.075) ** 2)
    zero_delta_complex = -1.05 * model.omega0_np * envelope
    zero_delta = np.concatenate([zero_delta_complex.real, zero_delta_complex.imag])
    zero_initial = model.x0_np + zero_delta
    outputs["zero-crossing"] = seven_point_loop(
        standard, zero_initial, principal, seed=8102
    )

    differential_complex = (
        0.18
        * model.omega0_np
        * np.sin(2.0 * np.pi * tau)
        * np.exp(0.4j)
    )
    asym = Evaluator(
        model.loss_asymmetric,
        model.loss_asymmetric_batch,
        (jnp.asarray(differential_complex),),
    )
    outputs["symmetry-breaking"] = seven_point_loop(
        asym, model.x0_np, principal, seed=8103
    )

    extra_complex = (
        0.18
        * model.omega0_np
        * np.sin(np.pi * tau)
        * np.exp(1.1j)
    )
    new_leak = Evaluator(
        model.loss_new_leakage,
        model.loss_new_leakage_batch,
        (jnp.asarray(extra_complex),),
    )
    outputs["new-leakage"] = seven_point_loop(
        new_leak, model.x0_np, principal, seed=8104
    )

    drift = smooth_distortion(model, principal, 8, 0.0, 0.02)
    drift_initial = model.x0_np + smooth_distortion(model, principal, 3, 1.0, 0.20)
    outputs["slow-drift"] = seven_point_loop(
        standard,
        drift_initial,
        principal,
        seed=8105,
        drift_per_cycle=drift,
    )

    clipped = Evaluator(model.loss_clipped, model.loss_clipped_batch, (jnp.asarray(1.05),))
    clip_initial = model.x0_np + smooth_distortion(model, principal, 4, 1.0, 0.35)
    outputs["actuator-clipping"] = seven_point_loop(
        clipped, clip_initial, principal, seed=8106
    )

    for name, result in outputs.items():
        rows.append(
            {
                "pathology": name,
                "initial_infidelity": float(result["trace"][0]["exact_infidelity"]),
                "final_infidelity": float(result["final_infidelity"]),
                "success": bool(result["success"]),
                "cycles": int(result["cycles"]),
                "steps": int(result["steps"]),
            }
        )
    write_csv(rows, run_dir / "data" / "pathology_scan.csv")
    progress("Named stress probes: 6/6 complete")
    return outputs, rows


def hamiltonian_error_scan(
    model: RydbergCZModel,
    principal: np.ndarray,
    run_dir: Path,
) -> list[dict[str, Any]]:
    strengths = np.asarray([0.0, 0.05, 0.10, 0.20, 0.40])
    tau = model.times / model.duration
    shape = model.omega0_np * np.sin(np.pi * tau) * np.exp(1.1j)
    rows: list[dict[str, Any]] = []
    for strength in strengths:
        detuning = Evaluator(
            model.loss_detuning,
            model.loss_detuning_batch,
            (jnp.asarray(strength),),
        )
        det_result = seven_point_loop(
            detuning, model.x0_np, principal, seed=9000 + int(100 * strength)
        )
        rows.append(
            {
                "mechanism": "detuning (existing channels)",
                "strength": float(strength),
                "before_fidelity": 1.0 - float(det_result["trace"][0]["exact_infidelity"]),
                "after_fidelity": 1.0 - float(det_result["final_infidelity"]),
                "success": bool(det_result["success"]),
            }
        )
        extra = jnp.asarray(strength * shape)
        new_leak = Evaluator(
            model.loss_new_leakage,
            model.loss_new_leakage_batch,
            (extra,),
        )
        leak_result = seven_point_loop(
            new_leak, model.x0_np, principal, seed=9100 + int(100 * strength)
        )
        rows.append(
            {
                "mechanism": "new leakage channel",
                "strength": float(strength),
                "before_fidelity": 1.0 - float(leak_result["trace"][0]["exact_infidelity"]),
                "after_fidelity": 1.0 - float(leak_result["final_infidelity"]),
                "success": bool(leak_result["success"]),
            }
        )
    write_csv(rows, run_dir / "data" / "hamiltonian_error_scan.csv")
    progress("Hamiltonian-channel comparison: complete")
    return rows


def plot_trajectories(
    core_runs: dict[tuple[float, float, int], dict[str, Any]],
    oracle: dict[float, dict[str, Any]],
    out: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), sharey=True, constrained_layout=True)
    for ax, eta in zip(axes, (0.10, 0.35, 0.60), strict=True):
        fitted = core_runs[(eta, 0.5, 0)]["trace"]
        exact = oracle[eta]["trace"]
        ax.semilogy(
            [row["step"] for row in fitted],
            [max(row["exact_infidelity"], 1e-14) for row in fitted],
            "o-",
            ms=3,
            label="seven-point fit",
            color="#d97706",
        )
        ax.semilogy(
            [row["step"] for row in exact],
            [max(row["exact_infidelity"], 1e-14) for row in exact],
            "s-",
            ms=3,
            label="exact line minimum",
            color="#167f7a",
        )
        ax.axhline(SUCCESS_TARGET, color="0.35", ls="--", lw=1)
        ax.set(xlabel="accepted mode update", title=f"η={eta:.2f},  p∥=0.5")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("exact gate infidelity  1−F")
    axes[0].legend(frameon=False)
    fig.suptitle("Closed-loop trajectories: geometry oracle versus paper-like scans")
    fig.savefig(out, dpi=180)
    plt.close(fig)


def grouped_core(rows: list[dict[str, Any]]) -> dict[tuple[float, float], list[dict[str, Any]]]:
    grouped: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((float(row["eta"]), float(row["p_parallel"])), []).append(row)
    return grouped


def plot_failure_map(rows: list[dict[str, Any]], out: Path) -> None:
    grouped = grouped_core(rows)
    success = np.zeros((len(P_VALUES), len(ETA_VALUES)))
    median_initial = np.zeros_like(success)
    for iy, p in enumerate(P_VALUES):
        for ix, eta in enumerate(ETA_VALUES):
            cell = grouped[(float(eta), float(p))]
            success[iy, ix] = np.mean([bool(row["success"]) for row in cell])
            median_initial[iy, ix] = np.median(
                [float(row["initial_infidelity"]) for row in cell]
            )
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.5), constrained_layout=True)
    image = axes[0].imshow(
        success,
        origin="lower",
        aspect="auto",
        vmin=0,
        vmax=1,
        cmap="RdYlGn",
    )
    axes[0].set(
        xticks=np.arange(len(ETA_VALUES)),
        xticklabels=[f"{v:g}" for v in ETA_VALUES],
        yticks=np.arange(len(P_VALUES)),
        yticklabels=[f"{v:g}" for v in P_VALUES],
        xlabel="relative waveform distortion  η",
        ylabel="principal-space power fraction  p∥",
        title="Success fraction: final 1−F ≤ 10⁻⁵ within eight cycles",
    )
    for iy in range(len(P_VALUES)):
        for ix in range(len(ETA_VALUES)):
            axes[0].text(
                ix,
                iy,
                f"{success[iy, ix]:.1f}",
                ha="center",
                va="center",
                fontsize=9,
            )
    fig.colorbar(image, ax=axes[0], label="success fraction (10 seeds)")
    for iy, p in enumerate(P_VALUES):
        axes[1].semilogy(
            ETA_VALUES,
            np.maximum(median_initial[iy], 1e-12),
            "o-",
            label=f"p∥={p:g}",
        )
    axes[1].set(
        xlabel="relative waveform distortion  η",
        ylabel="median initial infidelity",
        title="The same η is not the same physical error",
    )
    axes[1].grid(alpha=0.2)
    axes[1].legend(frameon=False, ncol=3)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_quadratic_breakdown(rows: list[dict[str, Any]], out: Path) -> None:
    grouped = grouped_core(rows)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    colors = ["#7e57c2", "#d97706", "#167f7a"]
    for p, color in zip(P_VALUES, colors, strict=True):
        exact_median = []
        quad_median = []
        residual_median = []
        residual_hi = []
        for eta in ETA_VALUES:
            cell = grouped[(float(eta), float(p))]
            exact = np.asarray(
                [row["nonlinear_channel_error"] for row in cell], dtype=float
            )
            quad = np.asarray([row["quadratic_infidelity"] for row in cell], dtype=float)
            residual = np.asarray(
                [row["quadratic_relative_residual"] for row in cell], dtype=float
            )
            exact_median.append(np.median(exact))
            quad_median.append(np.median(np.maximum(quad, 1e-16)))
            residual_median.append(np.median(residual))
            residual_hi.append(np.quantile(residual, 0.9))
        axes[0].loglog(ETA_VALUES, exact_median, "o-", color=color, label=f"exact, p∥={p:g}")
        axes[0].loglog(ETA_VALUES, quad_median, "--", color=color, alpha=0.75)
        axes[1].loglog(ETA_VALUES, residual_median, "o-", color=color, label=f"p∥={p:g}")
        axes[1].fill_between(
            ETA_VALUES, residual_median, residual_hi, color=color, alpha=0.15
        )
    axes[0].set(
        xlabel="relative distortion  η",
        ylabel="distortion-induced five-channel error",
        title="Solid: nonlinear channels; dashed: Hessian prediction",
    )
    axes[1].axhline(0.1, color="0.35", ls="--", label="10% breakdown criterion")
    axes[1].set(
        xlabel="relative distortion  η",
        ylabel="relative model discrepancy",
        title="Higher-order breakdown",
    )
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.legend(frameon=False, fontsize=8)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_rotation(rows: list[dict[str, Any]], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), constrained_layout=True)
    for p in P_VALUES:
        cell = sorted(
            [row for row in rows if float(row["p_parallel"]) == float(p)],
            key=lambda row: float(row["eta"]),
        )
        axes[0].semilogx(
            [row["eta"] for row in cell],
            [row["largest_principal_angle_deg"] for row in cell],
            "o-",
            label=f"p∥={p:g}",
        )
        axes[1].semilogx(
            [row["eta"] for row in cell],
            [row["minimum_subspace_overlap"] for row in cell],
            "o-",
            label=f"p∥={p:g}",
        )
    axes[0].set(
        xlabel="relative distortion  η",
        ylabel="largest principal angle (degrees)",
        title="Rotation away from nominal five-mode space",
    )
    axes[1].set(
        xlabel="relative distortion  η",
        ylabel="minimum singular overlap",
        title="Worst retained nominal direction",
        ylim=(-0.03, 1.03),
    )
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.legend(frameon=False)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_channels(rows: list[dict[str, Any]], out: Path) -> None:
    labels: list[str] = []
    leakage_01: list[float] = []
    leakage_11: list[float] = []
    phase_proxy: list[float] = []
    for eta in (0.10, 0.35, 0.60):
        for stage in ("initial", "final"):
            row = next(
                row
                for row in rows
                if row["eta"] == eta and row["stage"] == stage
            )
            labels.append(f"η={eta:g}\n{stage}")
            leakage_01.append(row["leakage_01"])
            leakage_11.append(row["leakage_11"])
            phase_proxy.append(row["phase_proxy"])
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(12, 5.2), constrained_layout=True)
    width = 0.25
    floor = 1e-10
    ax.bar(
        x - width,
        np.maximum(leakage_01, floor),
        width=width,
        label="|01⟩ leakage",
        color="#4c78a8",
    )
    ax.bar(
        x,
        np.maximum(leakage_11, floor),
        width=width,
        label="|11⟩ leakage",
        color="#f58518",
    )
    ax.bar(
        x + width,
        np.maximum(phase_proxy, floor),
        width=width,
        label="nonlinear-phase proxy",
        color="#54a24b",
    )
    ax.set_yscale("log")
    ax.set(
        xticks=x,
        xticklabels=labels,
        ylabel="channel diagnostic",
        title="What remains after the nominal five-direction loop?",
    )
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="y", alpha=0.2)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_noise(rows: list[dict[str, Any]], out: Path) -> None:
    etas = [0.06, 0.35]
    matrix = np.zeros((len(etas), len(NOISE_VALUES)))
    nonpositive = np.zeros_like(matrix)
    for iy, eta in enumerate(etas):
        for ix, sigma in enumerate(NOISE_VALUES):
            cell = [
                row
                for row in rows
                if float(row["eta"]) == eta and float(row["sigma_F"]) == float(sigma)
            ]
            matrix[iy, ix] = np.mean([bool(row["success"]) for row in cell])
            nonpositive[iy, ix] = np.nanmedian(
                [float(row["nonpositive_fit_fraction"]) for row in cell]
            )
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.3), constrained_layout=True)
    for ax, data, title, cmap in (
        (axes[0], matrix, "Closed-loop success fraction", "RdYlGn"),
        (axes[1], nonpositive, "Fraction of non-positive quadratic fits", "magma"),
    ):
        image = ax.imshow(data, origin="lower", aspect="auto", vmin=0, vmax=1, cmap=cmap)
        ax.set(
            xticks=np.arange(len(NOISE_VALUES)),
            xticklabels=[f"{value:.0e}" for value in NOISE_VALUES],
            yticks=np.arange(len(etas)),
            yticklabels=[f"{value:g}" for value in etas],
            xlabel="fidelity-estimator noise  σ_F",
            ylabel="distortion  η",
            title=title,
        )
        for iy in range(data.shape[0]):
            for ix in range(data.shape[1]):
                value = data[iy, ix]
                if cmap == "magma":
                    text_color = "white" if value < 0.5 else "black"
                else:
                    text_color = "white" if value < 0.25 or value > 0.75 else "black"
                ax.text(
                    ix,
                    iy,
                    f"{value:.1f}",
                    ha="center",
                    va="center",
                    color=text_color,
                )
        fig.colorbar(image, ax=ax)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_pathologies(
    outputs: dict[str, dict[str, Any]], out: Path
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharey=True, constrained_layout=True)
    titles = {
        "pure-null": "Pure null direction\n(higher-order visibility)",
        "zero-crossing": "Amplitude zero crossing\n(coordinate singularity)",
        "symmetry-breaking": "Atom asymmetry\n(new channel)",
        "new-leakage": "Additional leakage state\n(missing channel)",
        "slow-drift": "Slow waveform drift\n(non-stationary objective)",
        "actuator-clipping": "Actuator clipping\n(nonlinear transfer)",
    }
    for ax, name in zip(axes.flat, titles, strict=True):
        trace = outputs[name]["trace"]
        values = [max(row["exact_infidelity"], 1e-14) for row in trace]
        ax.semilogy(range(len(values)), values, "o-", ms=3, color="#4c78a8")
        ax.axhline(SUCCESS_TARGET, color="0.35", ls="--", lw=1)
        ax.set(title=titles[name], xlabel="accepted mode update")
        ax.grid(alpha=0.2)
        status = "success" if outputs[name]["success"] else "residual floor"
        ax.text(
            0.98,
            0.95,
            status,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
        )
    axes[0, 0].set_ylabel("exact gate infidelity  1−F")
    axes[1, 0].set_ylabel("exact gate infidelity  1−F")
    fig.suptitle("Named weird and ill-conditioned controls are not one failure mechanism")
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_hamiltonian_errors(rows: list[dict[str, Any]], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), constrained_layout=True)
    for ax, mechanism, title in (
        (axes[0], "detuning (existing channels)", "Existing channel: detuning"),
        (axes[1], "new leakage channel", "Outside span: new leakage"),
    ):
        cell = [row for row in rows if row["mechanism"] == mechanism]
        strengths = [row["strength"] for row in cell]
        ax.semilogy(
            strengths,
            [max(1.0 - row["before_fidelity"], 1e-8) for row in cell],
            "o-",
            label="before loop",
            color="#4c78a8",
        )
        ax.semilogy(
            strengths,
            [max(1.0 - row["after_fidelity"], 1e-8) for row in cell],
            "s-",
            label="after loop",
            color="#f58518",
        )
        ax.axhline(SUCCESS_TARGET, color="0.35", ls="--", lw=1, label="success target")
        ax.set(
            xlabel="Hamiltonian perturbation strength / Ω",
            ylabel="CZ gate infidelity  1−F",
            title=title,
        )
        ax.grid(alpha=0.2)
        ax.legend(frameon=False)
    fig.suptitle("Correctability is controlled by channel span, not magnitude alone")
    fig.savefig(out, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="New or empty output directory; existing evidence is never overwritten.",
    )
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--max-wall-seconds", type=float, default=600.0)
    args = parser.parse_args()
    if args.seeds <= 0:
        parser.error("--seeds must be a positive integer")
    if args.max_wall_seconds <= 0:
        parser.error("--max-wall-seconds must be positive")

    run_dir = prepare_run_directory(parser, args.run_dir)
    started = time.perf_counter()
    deadline = started + float(args.max_wall_seconds)
    sources = source_record()
    dump_json(
        {
            "status": "running",
            "stage": "baseline",
            "started_local_epoch": time.time(),
            "source": sources,
            "environment": environment_record(),
        },
        run_dir / PROGRESS_PATH,
    )

    model = RydbergCZModel(n_time=256)
    settings = input_settings(model, args)
    baseline = baseline_stage(model, run_dir)
    plot_baseline(model, baseline, run_dir / "figs" / "fig01_baseline_hessian.png")
    dump_json(
        {
            "status": "baseline_complete",
            "stage": "baseline",
            "elapsed_seconds": time.perf_counter() - started,
            "baseline": baseline["payload"],
        },
        run_dir / PROGRESS_PATH,
    )
    if args.baseline_only:
        timing = timing_record(started)
        summary = {
            "status": "baseline_complete",
            "baseline": baseline["payload"],
            "scope": {
                "core_trials": 0,
                "seeds_per_cell": args.seeds,
                "noise_trials": 0,
                "pathology_trials": 0,
                "hamiltonian_error_points": 0,
            },
            "input_settings": settings,
            "provenance": {
                "schema_version": 1,
                "source": sources,
                "artifact_manifest": MANIFEST_PATH,
            },
            "timing": timing,
            "elapsed_seconds": timing["wall_seconds"],
            "figures": ["figs/fig01_baseline_hessian.png"],
        }
        dump_json(summary, run_dir / "summary.json")
        write_artifact_manifest(run_dir)
        dump_json(
            {
                "status": "baseline_complete",
                "stage": "baseline",
                "elapsed_seconds": timing["wall_seconds"],
                "summary": "summary.json",
                "artifact_manifest": MANIFEST_PATH,
                "figures": summary["figures"],
            },
            run_dir / PROGRESS_PATH,
        )
        progress("Baseline-only run complete.")
        return

    progress("Extension scan: starting distortion basin map...")
    core_rows, core_runs = core_scan(
        model,
        baseline["principal"],
        baseline["hessian"],
        run_dir,
        args.seeds,
        deadline,
    )
    dump_json(
        {
            "status": "running",
            "stage": "core_complete",
            "elapsed_seconds": time.perf_counter() - started,
            "completed_core_trials": len(core_rows),
        },
        run_dir / "progress.json",
    )
    oracle = representative_oracle_runs(model, baseline["principal"])
    plot_trajectories(
        core_runs, oracle, run_dir / "figs" / "fig02_trajectories.png"
    )
    plot_failure_map(core_rows, run_dir / "figs" / "fig03_failure_map.png")
    plot_quadratic_breakdown(
        core_rows, run_dir / "figs" / "fig04_quadratic_breakdown.png"
    )

    progress("Extension scan: measuring local Hessian-subspace rotation...")
    rotation_rows = subspace_rotation_scan(
        model, baseline["principal"], run_dir, deadline
    )
    plot_rotation(rotation_rows, run_dir / "figs" / "fig05_subspace_rotation.png")

    channel_data = compute_channel_rows(model, baseline["principal"], core_runs)
    write_csv(channel_data, run_dir / "data" / "channel_decomposition.csv")
    plot_channels(channel_data, run_dir / "figs" / "fig06_channel_decomposition.png")

    progress("Extension scan: testing estimator noise...")
    noise_rows = noise_scan(
        model, baseline["principal"], run_dir, args.seeds, deadline
    )
    plot_noise(noise_rows, run_dir / "figs" / "fig07_noise_conditioning.png")

    progress("Extension scan: running six named pathology probes...")
    pathology, pathology_rows = pathology_runs(model, baseline["principal"], run_dir)
    plot_pathologies(pathology, run_dir / "figs" / "fig08_pathology_gallery.png")

    progress("Extension scan: comparing in-span and missing Hamiltonian channels...")
    hamiltonian_rows = hamiltonian_error_scan(
        model, baseline["principal"], run_dir
    )
    plot_hamiltonian_errors(
        hamiltonian_rows, run_dir / "figs" / "fig09_hamiltonian_channels.png"
    )

    grouped = grouped_core(core_rows)
    boundary_summary = {}
    for p in P_VALUES:
        values = []
        for eta in ETA_VALUES:
            cell = grouped[(float(eta), float(p))]
            successes = int(np.count_nonzero([bool(row["success"]) for row in cell]))
            interval_low, interval_high = wilson_interval(successes, len(cell))
            values.append(
                {
                    "eta": float(eta),
                    "successes": successes,
                    "trials": len(cell),
                    "success_fraction": successes / len(cell),
                    "success_wilson_95_low": interval_low,
                    "success_wilson_95_high": interval_high,
                    "median_initial_infidelity": float(
                        np.median([row["initial_infidelity"] for row in cell])
                    ),
                    "median_final_infidelity": float(
                        np.median([row["final_infidelity"] for row in cell])
                    ),
                    "median_quadratic_relative_residual": float(
                        np.median(
                            [row["quadratic_relative_residual"] for row in cell]
                        )
                    ),
                }
            )
        boundary_summary[f"p_parallel={p:g}"] = values

    timing = timing_record(started)
    summary = {
        "status": "complete",
        "baseline": baseline["payload"],
        "scope": {
            "core_trials": len(core_rows),
            "seeds_per_cell": args.seeds,
            "noise_trials": len(noise_rows),
            "pathology_trials": len(pathology_rows),
            "hamiltonian_error_points": len(hamiltonian_rows),
        },
        "boundary": boundary_summary,
        "pathologies": pathology_rows,
        "input_settings": settings,
        "provenance": {
            "schema_version": 1,
            "source": sources,
            "artifact_manifest": MANIFEST_PATH,
        },
        "timing": timing,
        "elapsed_seconds": timing["wall_seconds"],
        "figures": [
            f"figs/fig{index:02d}_{name}.png"
            for index, name in (
                (1, "baseline_hessian"),
                (2, "trajectories"),
                (3, "failure_map"),
                (4, "quadratic_breakdown"),
                (5, "subspace_rotation"),
                (6, "channel_decomposition"),
                (7, "noise_conditioning"),
                (8, "pathology_gallery"),
                (9, "hamiltonian_channels"),
            )
        ],
    }
    dump_json(summary, run_dir / "summary.json")
    write_artifact_manifest(run_dir)
    dump_json(
        {
            "status": "complete",
            "stage": "all",
            "elapsed_seconds": summary["elapsed_seconds"],
            "summary": "summary.json",
            "artifact_manifest": MANIFEST_PATH,
            "figures": summary["figures"],
        },
        run_dir / PROGRESS_PATH,
    )
    progress(
        f"Run complete: {len(core_rows)} core trials, 9 figures, "
        f"wall={summary['elapsed_seconds']:.1f}s"
    )


if __name__ == "__main__":
    main()
