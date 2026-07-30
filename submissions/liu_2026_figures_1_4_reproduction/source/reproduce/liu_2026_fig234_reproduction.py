#!/usr/bin/env python3
"""Auditable numerical workflows related to Liu et al., arXiv:2606.05060v1.

This is not a claim of complete reproduction of Figures 2--4.  Figure 2 and
the experimental parts of Figures 3--4 require unpublished raw observations.
Figure 3(b,c) can only be *equivalently reoptimized*, because the paper does
not publish its pulse array or complete optimizer settings.  Figure 4(a,b)
has a separately labelled synthetic plant/calibration demonstration, and
Figure 4(f) has a literal transcription of reported values rather than an
independent open-system simulation.

The NumPy/SciPy MWE is usable without JAX.  Optimization and automatic
differentiation stages import JAX lazily and fail with an actionable message
when it is unavailable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Literal

os.environ.setdefault("JAX_ENABLE_X64", "true")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/liu-fig234-mpl")

try:
    if os.environ.get("LIU_DISABLE_JAX") == "1":
        raise ImportError("JAX disabled by LIU_DISABLE_JAX=1")
    import jax

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    from jax import lax
    from jax.scipy.linalg import expm as jax_expm

    JAX_AVAILABLE = True
    JAX_IMPORT_ERROR: Exception | None = None
except Exception as _jax_error:  # exercised by the NumPy-only CLI test
    jax = None
    jnp = None
    lax = None
    jax_expm = None
    JAX_AVAILABLE = False
    JAX_IMPORT_ERROR = _jax_error
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy import optimize
from scipy import signal
from scipy.integrate import solve_ivp
from scipy.interpolate import BSpline
from scipy.linalg import expm


Array = np.ndarray
JaxArray = Any

RUN_DEFAULT = Path("tracks/qcs/results/liu-2026-fig234")

BASIS = (
    "|00>",
    "|W'>",
    "|01>",
    "|0r>",
    "|r'1>",
    "|10>",
    "|r0>",
    "|1r'>",
    "|11>",
    "|W>",
)
INDEX = {state: index for index, state in enumerate(BASIS)}
P_IDX = np.asarray(
    [INDEX["|00>"], INDEX["|01>"], INDEX["|10>"], INDEX["|11>"]],
    dtype=int,
)
Q_IDX = np.asarray(
    [index for index in range(len(BASIS)) if index not in set(P_IDX)],
    dtype=int,
)
TARGET_CZ = np.diag([1.0, 1.0, 1.0, -1.0]).astype(np.complex128)
TARGET_CZ_JAX = jnp.asarray(TARGET_CZ) if JAX_AVAILABLE else None

PROVENANCE = {
    "analytic": "exact analytic/theoretical check",
    "exact": "exact theoretical reproduction from fully specified equations",
    "equivalent": "equivalent numerical reoptimization",
    "digitized": "digitized paper data",
    "synthetic": "synthetic demonstration",
    "experimental": "experimental raw data",
    "reported": "literal transcription of reported paper values",
    "unavailable": "unavailable without raw experimental data",
}

FIDELITY_CONVENTIONS = (
    "fixed_standard_cz",
    "fixed_nominal_virtual_z",
    "pointwise_cz_equivalent",
)


@dataclass(frozen=True)
class ModelConfig:
    omega0_mhz: float = 6.0
    delta_r_mhz: float = 16.1
    duration_us: float = 0.55
    basis_size: int = 10
    detuning_sign: int = 1


@dataclass(frozen=True)
class OptimizerConfig:
    backend: Literal["spline", "time_bin", "source_phase"] = "spline"
    robustness_objective: Literal[
        "channel_root", "common_alpha_s11"
    ] = "channel_root"
    coefficients_per_channel: int = 16
    edge_adiabatic_factor: float = 10.0
    starts: int = 4
    random_seed: int = 260605060
    nominal_maxiter: int = 350
    ar_continuation_maxiter: int = 400
    ar_continuation_nominal_weight: float = 1000.0
    robust_max_nfev: int = 2000
    smooth_maxiter: int = 250
    coarse_nodes: int = 201
    fine_nodes: int = 401
    regularizer_nodes: int = 401
    amplitude_bound: float = 1.0
    phase_bound_turns: float = 2.0
    use_paper_shaped_diagnostic_seed: bool = False
    nominal_infidelity_tolerance: float = 1e-8
    leakage_tolerance: float = 1e-8
    ar_derivative_norm_tolerance: float = 1e-4
    amplitude_curvature_tolerance: float = 1e-8
    smoothness_weight: float = 0.0
    bandwidth_weight: float = 0.0
    rydberg_dwell_weight: float = 0.0
    amplitude_slew_weight: float = 0.0
    phase_slew_weight: float = 0.0


@dataclass(frozen=True)
class HessianConfig:
    convention: Literal[
        "paper_lab_iq", "local_amplitude_phase_frame"
    ] = "paper_lab_iq"
    bin_counts: tuple[int, ...] = (16, 32)
    propagation_nodes: tuple[int, ...] = (201, 401)
    fd_epsilons: tuple[float, ...] = (1e-4, 3e-4, 1e-3, 3e-3)
    rank_relative_tolerances: tuple[float, ...] = (1e-8, 1e-10, 1e-12)
    fd_relative_tolerance: float = 0.01
    propagation_spectrum_tolerance: float = 0.03
    frame_spectrum_tolerance: float = 0.02
    null_curvature_relative_tolerance: float = 1e-5


@dataclass(frozen=True)
class IntensityConfig:
    paper_min_ratio: float = 0.8
    paper_max_ratio: float = 1.2
    diagnostic_min_ratio: float = 0.75
    diagnostic_max_ratio: float = 1.25
    points_per_side: int = 18
    fit_windows: tuple[tuple[float, float], ...] = (
        (0.006, 0.05),
        (0.008, 0.08),
        (0.012, 0.10),
    )


@dataclass(frozen=True)
class AOMConfig:
    case: Literal["small", "paper_scale", "stress"] = "paper_scale"
    bandwidth_mhz: float = 8.0
    damping_ratio: float = 0.65
    delay_us: float = 0.020
    iq_imbalance: float = 0.02
    distortion_strength_small: float = 0.03
    distortion_strength_paper_scale: float = 0.11
    distortion_strength_stress: float = 0.70
    cycles: int = 4
    scan_points: int = 9
    scan_hardware_bound: float = 0.12
    shots: int = 20000
    random_seed: int = 260605060
    irreducible_baseline: float = 0.004
    ridge_projection: float = 1e-8


@dataclass(frozen=True)
class RunConfig:
    profile: Literal["quick", "standard", "convergence"] = "quick"
    model: ModelConfig = field(default_factory=ModelConfig)
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    hessian: HessianConfig = field(default_factory=HessianConfig)
    intensity: IntensityConfig = field(default_factory=IntensityConfig)
    aom: AOMConfig = field(default_factory=AOMConfig)
    adaptive_rtol: float = 1e-11
    adaptive_atol: float = 1e-13
    adaptive_max_step_fraction: float = 0.01
    grid_node_counts: tuple[int, ...] = (101, 201, 401)
    waveform_output_nodes: int = 401
    population_nodes: int = 501
    numerical_roundoff_tolerance: float = 1e-12


def _dataclass_from_dict(cls: type, values: dict[str, Any]) -> Any:
    """Strict recursive dataclass loader with unknown-key rejection."""
    known = {item.name: item for item in fields(cls)}
    unknown = sorted(set(values) - set(known))
    if unknown:
        raise ValueError(f"unknown {cls.__name__} configuration keys: {unknown}")
    nested = {
        "model": ModelConfig,
        "optimizer": OptimizerConfig,
        "hessian": HessianConfig,
        "intensity": IntensityConfig,
        "aom": AOMConfig,
    }
    converted: dict[str, Any] = {}
    for name, value in values.items():
        if name in nested:
            converted[name] = _dataclass_from_dict(nested[name], value)
        elif name in {"grid_node_counts"}:
            converted[name] = tuple(value)
        elif name in {"bin_counts", "propagation_nodes", "fd_epsilons",
                      "rank_relative_tolerances"}:
            converted[name] = tuple(value)
        elif name == "fit_windows":
            converted[name] = tuple(tuple(pair) for pair in value)
        else:
            converted[name] = value
    return cls(**converted)


def profile_config(profile: str) -> RunConfig:
    if profile == "quick":
        return RunConfig()
    if profile == "standard":
        return RunConfig(
            profile="standard",
            optimizer=OptimizerConfig(starts=6, nominal_maxiter=500),
            hessian=HessianConfig(
                bin_counts=(16, 32, 64),
                propagation_nodes=(201, 401),
            ),
            intensity=IntensityConfig(points_per_side=24),
            aom=AOMConfig(shots=50000),
        )
    if profile == "convergence":
        return RunConfig(
            profile="convergence",
            optimizer=OptimizerConfig(
                starts=10,
                nominal_maxiter=700,
                robust_max_nfev=3500,
                coarse_nodes=201,
                fine_nodes=801,
            ),
            hessian=HessianConfig(
                bin_counts=(16, 32, 64),
                propagation_nodes=(201, 401, 801),
            ),
            intensity=IntensityConfig(points_per_side=32),
            aom=AOMConfig(shots=100000),
        )
    raise ValueError(f"unknown profile {profile!r}")


def load_config(path: Path | None, profile: str) -> RunConfig:
    base = profile_config(profile)
    if path is None:
        validate_config(base)
        return base
    with path.open(encoding="utf-8") as handle:
        values = json.load(handle)
    if not isinstance(values, dict):
        raise ValueError("configuration root must be a JSON object")
    if "profile" in values and values["profile"] != profile:
        raise ValueError(
            f"configuration profile {values['profile']!r} conflicts with "
            f"CLI profile {profile!r}"
        )
    merged = asdict(base)
    for key, value in values.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    merged["profile"] = profile
    config = _dataclass_from_dict(RunConfig, merged)
    validate_config(config)
    return config


def validate_config(config: RunConfig) -> None:
    """Reject invalid physical or numerical run choices before any compute."""
    model = config.model
    if (
        model.omega0_mhz <= 0.0
        or model.delta_r_mhz <= 0.0
        or model.duration_us <= 0.0
        or model.basis_size != 10
        or model.detuning_sign not in (-1, 1)
    ):
        raise ValueError("invalid ten-state model configuration")
    optimizer = config.optimizer
    if (
        optimizer.coefficients_per_channel < 6
        or optimizer.starts <= 0
        or optimizer.coarse_nodes < 3
        or optimizer.fine_nodes < optimizer.coarse_nodes
        or optimizer.regularizer_nodes < 3
        or not 0.0 < optimizer.amplitude_bound <= 1.0
        or optimizer.phase_bound_turns <= 0.0
        or optimizer.edge_adiabatic_factor <= 0.0
        or (
            optimizer.backend == "source_phase"
            and optimizer.robustness_objective != "common_alpha_s11"
        )
    ):
        raise ValueError("invalid optimizer configuration")
    if (
        any(value < 3 for value in config.grid_node_counts)
        or tuple(sorted(config.grid_node_counts)) != config.grid_node_counts
        or config.waveform_output_nodes < 3
        or config.population_nodes < 3
        or config.adaptive_rtol <= 0.0
        or config.adaptive_atol <= 0.0
        or not 0.0 < config.adaptive_max_step_fraction <= 1.0
        or config.numerical_roundoff_tolerance <= 0.0
    ):
        raise ValueError("invalid propagation configuration")
    hessian = config.hessian
    if (
        len(hessian.bin_counts) < 2
        or len(hessian.propagation_nodes) < 2
        or any(value < 2 for value in hessian.bin_counts)
        or any(value < 3 for value in hessian.propagation_nodes)
        or any(value <= 0.0 for value in hessian.fd_epsilons)
        or any(value <= 0.0 for value in hessian.rank_relative_tolerances)
    ):
        raise ValueError("Hessian convergence requires valid multi-resolution grids")
    intensity = config.intensity
    if (
        intensity.paper_min_ratio <= 0.0
        or intensity.paper_min_ratio >= 1.0
        or intensity.paper_max_ratio <= 1.0
        or intensity.diagnostic_min_ratio > intensity.paper_min_ratio
        or intensity.diagnostic_max_ratio < intensity.paper_max_ratio
        or intensity.points_per_side < 3
    ):
        raise ValueError("invalid intensity scan configuration")
    aom = config.aom
    if (
        aom.bandwidth_mhz <= 0.0
        or aom.damping_ratio <= 0.0
        or aom.cycles <= 0
        or aom.scan_points < 3
        or aom.scan_hardware_bound <= 0.0
        or aom.shots <= 0
        or not 0.0 <= aom.irreducible_baseline < 1.0
    ):
        raise ValueError("invalid synthetic AOM configuration")


def config_hash(config: RunConfig) -> str:
    encoded = json.dumps(
        asdict(config), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def code_version() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        revision = result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    return f"{revision}+source-{source_hash}"


def require_jax(stage: str) -> None:
    if not JAX_AVAILABLE:
        raise RuntimeError(
            f"{stage} requires JAX with x64 support. Install the pinned "
            "requirements and rerun; the NumPy-only --mwe remains available. "
            f"Original import error: {JAX_IMPORT_ERROR}"
        )


def progress(message: str) -> None:
    print(message, flush=True)


def json_default(item: object) -> object:
    if isinstance(item, np.ndarray):
        return item.tolist()
    if isinstance(item, (complex, np.complexfloating)):
        return {"real": float(np.real(item)), "imag": float(np.imag(item))}
    if isinstance(item, (np.floating, np.integer, np.bool_)):
        return item.item()
    raise TypeError(f"cannot serialize {type(item).__name__}")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=json_default)
        handle.write("\n")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(
            dict.fromkeys(key for row in rows for key in row)
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def wrap_phase(value: float | Array) -> float | Array:
    return np.angle(np.exp(1j * np.asarray(value)))


def trapezoid_weights(times: Array) -> Array:
    times = np.asarray(times, dtype=float)
    if times.ndim != 1 or len(times) < 2:
        raise ValueError("times must be a one-dimensional array of length >= 2")
    intervals = np.diff(times)
    if np.any(intervals <= 0):
        raise ValueError("times must be strictly increasing")
    weights = np.empty_like(times)
    weights[0] = intervals[0] / 2.0
    weights[-1] = intervals[-1] / 2.0
    weights[1:-1] = (intervals[:-1] + intervals[1:]) / 2.0
    return weights


@dataclass(frozen=True)
class Model:
    """Appendix-C 10-state perfect-blockade model.

    Time is measured in μs and every frequency is angular, in rad/μs.  The
    positive detuning convention is H_det = +Δ_r Π_r′.  Double-Rydberg states,
    finite blockade, decay, Doppler shifts, laser noise, and MQDT pair-state
    physics are absent.
    """

    omega0: float = 2.0 * np.pi * 6.0
    delta_r: float = 2.0 * np.pi * 16.1
    duration: float = 0.55
    detuning_sign: int = 1

    def __post_init__(self) -> None:
        if self.omega0 <= 0 or self.delta_r <= 0 or self.duration <= 0:
            raise ValueError("model frequencies and duration must be positive")
        if self.detuning_sign not in (-1, 1):
            raise ValueError("detuning_sign must be +1 or -1")

    @classmethod
    def from_config(cls, config: ModelConfig) -> "Model":
        if config.basis_size != 10:
            raise ValueError(
                "the perfect-blockade reduced model has exactly 10 states"
            )
        return cls(
            omega0=2.0 * np.pi * config.omega0_mhz,
            delta_r=2.0 * np.pi * config.delta_r_mhz,
            duration=config.duration_us,
            detuning_sign=config.detuning_sign,
        )


def raising_operator_numpy() -> Array:
    operator = np.zeros((10, 10), dtype=np.complex128)
    couplings = (
        ("|0r>", "|01>", 1.0),
        ("|r'1>", "|01>", -1.0),
        ("|r0>", "|10>", 1.0),
        ("|1r'>", "|10>", -1.0),
        ("|W'>", "|00>", -np.sqrt(2.0)),
        ("|W>", "|11>", np.sqrt(2.0)),
    )
    for excited, ground, strength in couplings:
        operator[INDEX[excited], INDEX[ground]] = strength
    return operator


SIGMA_PLUS = raising_operator_numpy()
SIGMA_MINUS = SIGMA_PLUS.conj().T
RPRIME_PROJECTOR = np.zeros((10, 10), dtype=np.complex128)
for _state in ("|W'>", "|r'1>", "|1r'>"):
    RPRIME_PROJECTOR[INDEX[_state], INDEX[_state]] = 1.0

SIGMA_PLUS_JAX = jnp.asarray(SIGMA_PLUS) if JAX_AVAILABLE else None
SIGMA_MINUS_JAX = jnp.asarray(SIGMA_MINUS) if JAX_AVAILABLE else None
RPRIME_PROJECTOR_JAX = (
    jnp.asarray(RPRIME_PROJECTOR) if JAX_AVAILABLE else None
)
P_IDX_JAX = jnp.asarray(P_IDX) if JAX_AVAILABLE else None
Q_IDX_JAX = jnp.asarray(Q_IDX) if JAX_AVAILABLE else None


def hamiltonian_numpy(control: complex, model: Model = Model()) -> Array:
    hamiltonian = (
        model.detuning_sign * model.delta_r * RPRIME_PROJECTOR
        + 0.5 * (control * SIGMA_PLUS + np.conj(control) * SIGMA_MINUS)
    )
    return hamiltonian


def hamiltonian_jax(control: JaxArray, model: Model = Model()) -> JaxArray:
    require_jax("JAX Hamiltonian")
    return (
        model.detuning_sign * model.delta_r * RPRIME_PROJECTOR_JAX
        + 0.5
        * (control * SIGMA_PLUS_JAX + jnp.conj(control) * SIGMA_MINUS_JAX)
    )


def clamped_knots(n_coefficients: int, degree: int = 3) -> Array:
    if n_coefficients <= degree:
        raise ValueError("need more coefficients than the spline degree")
    internal_count = n_coefficients - degree - 1
    internal = (
        np.linspace(0.0, 1.0, internal_count + 2)[1:-1]
        if internal_count
        else np.empty(0)
    )
    return np.concatenate(
        [
            np.zeros(degree + 1),
            internal,
            np.ones(degree + 1),
        ]
    )


def bspline_design(
    normalized_times: Array,
    n_coefficients: int = 16,
    degree: int = 3,
    derivative: int = 0,
) -> Array:
    normalized_times = np.asarray(normalized_times, dtype=float)
    knots = clamped_knots(n_coefficients, degree)
    columns = []
    for index in range(n_coefficients):
        coefficient = np.zeros(n_coefficients)
        coefficient[index] = 1.0
        spline = BSpline(knots, coefficient, degree, extrapolate=False)
        columns.append(spline(normalized_times, nu=derivative))
    return np.column_stack(columns)


@dataclass(frozen=True)
class WaveformBasis:
    """Clamped cubic B-spline waveform with explicit physical constraints."""

    model: Model = Model()
    n_coefficients: int = 16
    amplitude_bound: float = 1.0
    phase_bound_rad: float = 4.0 * np.pi

    @property
    def n_amplitude_free(self) -> int:
        # c0=c1=c[-2]=c[-1]=0 gives zero values and slopes.
        return self.n_coefficients - 4

    @property
    def n_phase_free(self) -> int:
        # c0=0 fixes the phase gauge.
        return self.n_coefficients - 1

    @property
    def n_free(self) -> int:
        return self.n_amplitude_free + self.n_phase_free

    def unpack_numpy(self, variables: Array) -> tuple[Array, Array]:
        variables = np.asarray(variables, dtype=float)
        if variables.shape != (self.n_free,):
            raise ValueError(f"expected {self.n_free} variables, got {variables.shape}")
        amplitude = np.zeros(self.n_coefficients)
        amplitude[2:-2] = variables[: self.n_amplitude_free]
        phase = np.zeros(self.n_coefficients)
        phase[1:] = variables[self.n_amplitude_free :]
        return amplitude, phase

    def unpack_jax(self, variables: JaxArray) -> tuple[JaxArray, JaxArray]:
        amplitude = jnp.zeros(self.n_coefficients, dtype=jnp.float64)
        amplitude = amplitude.at[2:-2].set(
            variables[: self.n_amplitude_free]
        )
        phase = jnp.zeros(self.n_coefficients, dtype=jnp.float64)
        phase = phase.at[1:].set(variables[self.n_amplitude_free :])
        return amplitude, phase

    def design(self, times: Array, derivative: int = 0) -> Array:
        return bspline_design(
            np.asarray(times) / self.model.duration,
            self.n_coefficients,
            derivative=derivative,
        ) / self.model.duration**derivative

    def values_numpy(self, variables: Array, times: Array) -> tuple[Array, Array, Array]:
        amplitude_coefficients, phase_coefficients = self.unpack_numpy(variables)
        design = self.design(times)
        amplitude = design @ amplitude_coefficients
        phase = design @ phase_coefficients
        control = self.model.omega0 * amplitude * np.exp(1j * phase)
        return amplitude, phase, control

    def values_jax(
        self, variables: JaxArray, design: JaxArray
    ) -> tuple[JaxArray, JaxArray, JaxArray]:
        amplitude_coefficients, phase_coefficients = self.unpack_jax(variables)
        amplitude = design @ amplitude_coefficients
        phase = design @ phase_coefficients
        control = self.model.omega0 * amplitude * jnp.exp(1j * phase)
        return amplitude, phase, control

    def bounds(self) -> list[tuple[float, float]]:
        amplitude = [(0.0, self.amplitude_bound)] * self.n_amplitude_free
        phase = [
            (-self.phase_bound_rad, self.phase_bound_rad)
        ] * self.n_phase_free
        return amplitude + phase


@dataclass(frozen=True)
class TimeBinBasis(WaveformBasis):
    """Direct amplitude/phase-bin backend with linear interpolation.

    It retains the same zero-value/zero-slope endpoint coefficient constraints
    as the spline backend.  It is GRAPE-style in parameterization only; it is
    not claimed to reproduce the authors' unpublished implementation.
    """

    def design(self, times: Array, derivative: int = 0) -> Array:
        times = np.asarray(times, dtype=float)
        grid = np.linspace(0.0, self.model.duration, self.n_coefficients)
        if derivative not in (0, 1):
            # Piecewise-linear bins have distribution-valued second
            # derivatives.  A finite-difference diagnostic handles this case.
            return np.zeros((len(times), self.n_coefficients))
        matrix = np.zeros((len(times), self.n_coefficients))
        spacing = grid[1] - grid[0]
        for row, value in enumerate(np.clip(times, grid[0], grid[-1])):
            if value == grid[-1]:
                matrix[row, -1] = 1.0
                continue
            left = min(int((value - grid[0]) / spacing), self.n_coefficients - 2)
            fraction = (value - grid[left]) / spacing
            if derivative == 0:
                matrix[row, left] = 1.0 - fraction
                matrix[row, left + 1] = fraction
            else:
                matrix[row, left] = -1.0 / spacing
                matrix[row, left + 1] = 1.0 / spacing
        return matrix


@dataclass(frozen=True)
class SourceConstrainedPhaseBasis(WaveformBasis):
    """Fixed flat-top envelope and piecewise-constant phase backend.

    The cited RobustGRAPE method specifies a constant Ω₀ plateau with
    sinusoidal rise/fall edges and N=400 phase intervals.  The edge duration
    is fixed here by the declared reconstruction choice Δᵣ t_r=10; it is not
    inferred from pixels in the published figure.
    """

    edge_adiabatic_factor: float = 10.0

    @property
    def n_amplitude_free(self) -> int:
        return 0

    @property
    def n_phase_free(self) -> int:
        return self.n_coefficients

    @property
    def n_free(self) -> int:
        return self.n_phase_free

    @property
    def edge_duration(self) -> float:
        return min(
            self.edge_adiabatic_factor / self.model.delta_r,
            0.5 * self.model.duration,
        )

    def envelope_numpy(self, times: Array) -> Array:
        times = np.clip(
            np.asarray(times, dtype=float), 0.0, self.model.duration
        )
        edge = self.edge_duration
        rising = np.sin(0.5 * np.pi * times / edge)
        falling = np.sin(
            0.5 * np.pi * (self.model.duration - times) / edge
        )
        return np.where(
            times < edge,
            rising,
            np.where(times > self.model.duration - edge, falling, 1.0),
        )

    def unpack_numpy(self, variables: Array) -> tuple[Array, Array]:
        variables = np.asarray(variables, dtype=float)
        if variables.shape != (self.n_free,):
            raise ValueError(f"expected {self.n_free} variables, got {variables.shape}")
        centers = (
            np.arange(self.n_coefficients, dtype=float) + 0.5
        ) * self.model.duration / self.n_coefficients
        return self.envelope_numpy(centers), variables.copy()

    def unpack_jax(self, variables: JaxArray) -> tuple[JaxArray, JaxArray]:
        centers = (
            jnp.arange(self.n_coefficients, dtype=jnp.float64) + 0.5
        ) * self.model.duration / self.n_coefficients
        edge = self.edge_duration
        rising = jnp.sin(0.5 * jnp.pi * centers / edge)
        falling = jnp.sin(
            0.5 * jnp.pi * (self.model.duration - centers) / edge
        )
        envelope = jnp.where(
            centers < edge,
            rising,
            jnp.where(
                centers > self.model.duration - edge, falling, 1.0
            ),
        )
        return envelope, variables

    def design(self, times: Array, derivative: int = 0) -> Array:
        times = np.clip(
            np.asarray(times, dtype=float), 0.0, self.model.duration
        )
        matrix = np.zeros((len(times), self.n_coefficients + 1))
        if derivative != 0:
            return matrix
        indices = np.minimum(
            (times / self.model.duration * self.n_coefficients).astype(int),
            self.n_coefficients - 1,
        )
        matrix[np.arange(len(times)), indices] = 1.0
        matrix[:, -1] = self.envelope_numpy(times)
        return matrix

    def values_numpy(self, variables: Array, times: Array) -> tuple[Array, Array, Array]:
        design = self.design(times)
        phase = design[:, :-1] @ np.asarray(variables, dtype=float)
        amplitude = design[:, -1]
        control = self.model.omega0 * amplitude * np.exp(1j * phase)
        return amplitude, phase, control

    def values_jax(
        self, variables: JaxArray, design: JaxArray
    ) -> tuple[JaxArray, JaxArray, JaxArray]:
        phase = design[:, :-1] @ variables
        amplitude = design[:, -1]
        control = self.model.omega0 * amplitude * jnp.exp(1j * phase)
        return amplitude, phase, control

    def bounds(self) -> list[tuple[float, float]]:
        return [
            (-self.phase_bound_rad, self.phase_bound_rad)
        ] * self.n_phase_free


def make_basis(config: RunConfig) -> WaveformBasis:
    model = Model.from_config(config.model)
    if config.optimizer.backend == "spline":
        cls = WaveformBasis
    elif config.optimizer.backend == "time_bin":
        cls = TimeBinBasis
    else:
        cls = SourceConstrainedPhaseBasis
    keyword_arguments: dict[str, Any] = {}
    if cls is SourceConstrainedPhaseBasis:
        keyword_arguments["edge_adiabatic_factor"] = (
            config.optimizer.edge_adiabatic_factor
        )
    return cls(
        model=model,
        n_coefficients=config.optimizer.coefficients_per_channel,
        amplitude_bound=config.optimizer.amplitude_bound,
        phase_bound_rad=(
            2.0 * np.pi * config.optimizer.phase_bound_turns
        ),
        **keyword_arguments,
    )


def generic_seed_waveform(
    basis: WaveformBasis,
    phase_turns: float = 0.5,
    amplitude_plateau: float = 0.85,
) -> Array:
    """Generic smooth seed independent of the published waveform shape."""
    amplitude = np.full(basis.n_amplitude_free, amplitude_plateau)
    # A simple phase sweep avoids imposing any detailed shape from Fig. 3(b).
    phase = np.linspace(
        0.0, 2.0 * np.pi * phase_turns, basis.n_phase_free + 1
    )[1:]
    return np.concatenate([amplitude, phase])


def paper_shaped_diagnostic_seed(basis: WaveformBasis) -> Array:
    """Diagnostic-only seed visually inspired by the paper, never the default."""
    amplitude = np.asarray(
        [0.08, 0.38, 0.86, 1.0, 1.0, 1.0, 1.0, 1.0, 0.92, 0.58, 0.18, 0.04]
    )
    phase_turns = np.asarray(
        [
            0.0,
            0.06,
            0.30,
            0.78,
            0.62,
            0.48,
            0.56,
            0.68,
            0.84,
            0.78,
            0.62,
            0.60,
            0.60,
            0.60,
            0.60,
        ]
    )
    if len(amplitude) != basis.n_amplitude_free:
        raise ValueError("seed waveform assumes 16 amplitude coefficients")
    if len(phase_turns) != basis.n_phase_free:
        raise ValueError("seed waveform assumes 16 phase coefficients")
    return np.concatenate([amplitude, 2.0 * np.pi * phase_turns])


def seed_waveform(basis: WaveformBasis) -> Array:
    """Backward-compatible name for the generic, paper-independent seed."""
    return generic_seed_waveform(basis)


def generic_multistarts(
    basis: WaveformBasis,
    count: int,
    seed: int,
    include_paper_diagnostic: bool = False,
) -> list[tuple[str, Array]]:
    starts: list[tuple[str, Array]] = [
        ("generic_constant_half_turn", generic_seed_waveform(basis)),
        (
            "generic_constant_zero_phase",
            generic_seed_waveform(basis, phase_turns=0.0, amplitude_plateau=0.9),
        ),
    ][:count]
    rng = np.random.default_rng(seed)
    while len(starts) < count:
        base = generic_seed_waveform(
            basis,
            phase_turns=float(rng.uniform(-1.0, 1.0)),
            amplitude_plateau=float(rng.uniform(0.55, 0.95)),
        )
        amplitude_noise = np.zeros(basis.n_amplitude_free)
        if basis.n_amplitude_free:
            amplitude_noise = np.convolve(
                rng.normal(0.0, 0.12, basis.n_amplitude_free),
                np.asarray([0.25, 0.5, 0.25]),
                mode="same",
            )
        phase_noise = np.convolve(
            rng.normal(0.0, 0.5, basis.n_phase_free),
            np.asarray([0.25, 0.5, 0.25]),
            mode="same",
        )
        base[: basis.n_amplitude_free] = np.clip(
            base[: basis.n_amplitude_free] + amplitude_noise,
            0.0,
            basis.amplitude_bound,
        )
        base[basis.n_amplitude_free :] = np.clip(
            base[basis.n_amplitude_free :] + phase_noise,
            -basis.phase_bound_rad,
            basis.phase_bound_rad,
        )
        starts.append((f"generic_random_smooth_{len(starts) - 1}", base))
    if include_paper_diagnostic:
        starts.append(("paper_shaped_diagnostic", paper_shaped_diagnostic_seed(basis)))
    return starts


def propagate_piecewise_numpy(
    times: Array,
    controls_midpoint: Array,
    model: Model = Model(),
) -> Array:
    times = np.asarray(times, dtype=float)
    controls_midpoint = np.asarray(controls_midpoint, dtype=np.complex128)
    if controls_midpoint.shape != (len(times) - 1,):
        raise ValueError("one midpoint control is required per interval")
    unitary = np.eye(10, dtype=np.complex128)
    for interval, control in zip(np.diff(times), controls_midpoint, strict=True):
        unitary = expm(-1j * interval * hamiltonian_numpy(control, model)) @ unitary
    return unitary


def propagate_piecewise_jax(
    controls_midpoint: JaxArray,
    dt: float,
    amplitude_scale: float | JaxArray = 1.0,
    model: Model = Model(),
) -> JaxArray:
    def step(unitary: JaxArray, control: JaxArray) -> tuple[JaxArray, None]:
        hamiltonian = hamiltonian_jax(amplitude_scale * control, model)
        next_unitary = jax_expm(-1j * dt * hamiltonian) @ unitary
        return next_unitary, None

    final, _ = lax.scan(
        step,
        jnp.eye(10, dtype=jnp.complex128),
        controls_midpoint,
    )
    return final


def propagate_adaptive(
    control: Callable[[float], complex],
    model: Model = Model(),
    times: Array | None = None,
    rtol: float = 1e-11,
    atol: float = 1e-13,
    max_step: float | None = None,
) -> Array:
    if times is None:
        times = np.asarray([0.0, model.duration])
    else:
        times = np.asarray(times, dtype=float)

    def rhs(t: float, flat: Array) -> Array:
        unitary = flat.reshape(10, 10)
        return (-1j * hamiltonian_numpy(control(t), model) @ unitary).reshape(-1)

    initial = np.eye(10, dtype=np.complex128).reshape(-1)
    result = solve_ivp(
        rhs,
        (0.0, model.duration),
        initial,
        method="DOP853",
        t_eval=times,
        rtol=rtol,
        atol=atol,
        max_step=(
            model.duration / 100.0 if max_step is None else float(max_step)
        ),
    )
    if not result.success:
        raise RuntimeError(result.message)
    return result.y.T.reshape(len(times), 10, 10)


def symmetric_virtual_z_target(theta: float) -> Array:
    phase = np.exp(1j * theta)
    return np.diag([1.0, phase, phase, -(phase**2)]).astype(np.complex128)


def _validated_probability(
    value: float, name: str, tolerance: float = 1e-12
) -> float:
    if value < -tolerance or value > 1.0 + tolerance:
        raise FloatingPointError(
            f"{name}={value:.17g} is outside [0,1] beyond tolerance "
            f"{tolerance:.1e}"
        )
    return float(value)


def local_z_diagnostics(returns: Array, stability_floor: float = 1e-10) -> dict:
    """Stable symmetric-local-Z diagnostic from the two single-excitation sectors."""
    returns = np.asarray(returns, dtype=np.complex128)
    amplitudes = np.abs(returns)
    stable = bool(np.min(amplitudes[:3]) >= stability_floor)
    if not stable:
        return {
            "phase_01": np.nan,
            "phase_10": np.nan,
            "sector_phase_difference": np.nan,
            "circular_mean": np.nan,
            "circular_resultant": 0.0,
            "stable": False,
            "stability_floor": stability_floor,
        }
    z01 = returns[1] * np.conj(returns[0])
    z10 = returns[2] * np.conj(returns[0])
    p01 = z01 / abs(z01)
    p10 = z10 / abs(z10)
    circular = 0.5 * (p01 + p10)
    resultant = float(abs(circular))
    circular_stable = resultant >= stability_floor
    return {
        "phase_01": float(np.angle(p01)),
        "phase_10": float(np.angle(p10)),
        "sector_phase_difference": float(np.angle(p01 * np.conj(p10))),
        "circular_mean": (
            float(np.angle(circular)) if circular_stable else np.nan
        ),
        "circular_resultant": resultant,
        "stable": bool(circular_stable),
        "stability_floor": stability_floor,
    }


def nonlinear_phase_invariant(returns: Array) -> dict[str, float | bool]:
    """Branch-safe CZ phase invariant; the ideal CZ maps to z=+1."""
    returns = np.asarray(returns, dtype=np.complex128)
    raw = -returns[3] * returns[0] * np.conj(returns[1] * returns[2])
    magnitude = float(abs(raw))
    if magnitude < 1e-14:
        return {
            "sin": np.nan,
            "one_minus_cos": np.nan,
            "angle": np.nan,
            "magnitude": magnitude,
            "stable": False,
        }
    normalized = raw / magnitude
    return {
        "sin": float(np.imag(normalized)),
        "one_minus_cos": float(1.0 - np.real(normalized)),
        "angle": float(np.angle(normalized)),
        "magnitude": magnitude,
        "stable": True,
    }


def average_gate_fidelity_from_target(
    computational: Array, target: Array, tolerance: float = 1e-12
) -> float:
    """Leakage-aware average fidelity, Eq. used in the AR references."""
    interaction = target.conj().T @ computational
    fidelity = float(
        np.real(
            (
                abs(np.trace(interaction)) ** 2
                + np.trace(interaction @ interaction.conj().T).real
            )
            / 20.0
        )
    )
    return _validated_probability(fidelity, "average gate fidelity", tolerance)


def gate_metrics_numpy(
    unitary: Array,
    fidelity_convention: str = "fixed_standard_cz",
    nominal_virtual_z: float | None = None,
    numerical_tolerance: float = 1e-12,
    remove_local_z: bool | None = None,
) -> dict[str, object]:
    if remove_local_z is not None:
        fidelity_convention = (
            "pointwise_cz_equivalent" if remove_local_z else "fixed_standard_cz"
        )
    if fidelity_convention not in FIDELITY_CONVENTIONS:
        raise ValueError(f"unknown fidelity convention {fidelity_convention!r}")
    computational = unitary[np.ix_(P_IDX, P_IDX)]
    returns = np.diag(computational)
    local = local_z_diagnostics(returns)
    if fidelity_convention == "fixed_standard_cz":
        target = TARGET_CZ
        applied_virtual_z = 0.0
    elif fidelity_convention == "fixed_nominal_virtual_z":
        if nominal_virtual_z is None or not np.isfinite(nominal_virtual_z):
            raise ValueError(
                "fixed_nominal_virtual_z requires a finite nominal_virtual_z"
            )
        applied_virtual_z = float(nominal_virtual_z)
        target = symmetric_virtual_z_target(applied_virtual_z)
    else:
        if not local["stable"]:
            raise FloatingPointError(
                "pointwise local-Z phase is undefined because a return "
                "amplitude or circular resultant is near zero"
            )
        applied_virtual_z = float(local["circular_mean"])
        target = symmetric_virtual_z_target(applied_virtual_z)
    fidelity = average_gate_fidelity_from_target(
        computational, target, numerical_tolerance
    )
    leakage = (
        1.0
        - np.sum(abs(unitary[np.ix_(P_IDX, P_IDX)]) ** 2, axis=0)
    ).real
    if float(np.min(leakage)) < -numerical_tolerance:
        raise FloatingPointError(
            f"minimum raw leakage {np.min(leakage):.3e} is below numerical "
            f"tolerance {-numerical_tolerance:.1e}"
        )
    phase = nonlinear_phase_invariant(returns)
    unitarity = np.linalg.norm(unitary.conj().T @ unitary - np.eye(10))
    return {
        "fidelity": fidelity,
        "infidelity": float(1.0 - fidelity),
        "leakage": np.asarray(leakage),
        "max_leakage": float(np.max(leakage)),
        "minimum_raw_leakage": float(np.min(leakage)),
        "cz_phase_error": float(phase["angle"]),
        "cz_phase_sin_residual": float(phase["sin"]),
        "cz_phase_one_minus_cos_residual": float(phase["one_minus_cos"]),
        "cz_phase_invariant_magnitude": float(phase["magnitude"]),
        "local_z_phase": float(local["circular_mean"]),
        "local_z": local,
        "applied_virtual_z": applied_virtual_z,
        "fidelity_convention": fidelity_convention,
        "return_amplitudes": returns,
        "unitarity_residual": float(unitarity),
        "numerical_tolerance": numerical_tolerance,
    }


def gate_metrics_jax(
    unitary: JaxArray,
    fidelity_convention: str = "pointwise_cz_equivalent",
    nominal_virtual_z: float | JaxArray | None = None,
    remove_local_z: bool | None = None,
) -> tuple[JaxArray, JaxArray, JaxArray]:
    require_jax("JAX fidelity")
    if remove_local_z is not None:
        fidelity_convention = (
            "pointwise_cz_equivalent" if remove_local_z else "fixed_standard_cz"
        )
    computational = unitary[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
    returns = jnp.diag(computational)
    if fidelity_convention == "pointwise_cz_equivalent":
        z01 = returns[1] * jnp.conj(returns[0])
        z10 = returns[2] * jnp.conj(returns[0])
        phasor = z01 / jnp.abs(z01) + z10 / jnp.abs(z10)
        local_z_phase = jnp.angle(phasor)
        local_phase_factor = jnp.exp(1j * local_z_phase)
        target = jnp.diag(
            jnp.stack(
                [
                    jnp.asarray(1.0 + 0.0j),
                    local_phase_factor,
                    local_phase_factor,
                    -(local_phase_factor**2),
                ]
            )
        )
    elif fidelity_convention == "fixed_nominal_virtual_z":
        if nominal_virtual_z is None:
            raise ValueError("nominal_virtual_z is required")
        local_phase_factor = jnp.exp(1j * nominal_virtual_z)
        target = jnp.diag(
            jnp.stack(
                [
                    jnp.asarray(1.0 + 0.0j),
                    local_phase_factor,
                    local_phase_factor,
                    -(local_phase_factor**2),
                ]
            )
        )
    elif fidelity_convention == "fixed_standard_cz":
        target = TARGET_CZ_JAX
    else:
        raise ValueError(f"unknown fidelity convention {fidelity_convention!r}")
    interaction = jnp.conj(target.T) @ computational
    fidelity = (
        jnp.abs(jnp.trace(interaction)) ** 2
        + jnp.real(jnp.trace(interaction @ jnp.conj(interaction.T)))
    ) / 20.0
    leakage = 1.0 - jnp.sum(jnp.abs(computational) ** 2, axis=0)
    phase_invariant = (
        -returns[3] * returns[0] * jnp.conj(returns[1] * returns[2])
    )
    phase = jnp.angle(phase_invariant)
    return 1.0 - jnp.real(fidelity), leakage, phase


def normalized_unitary_difference(left: Array, right: Array) -> float:
    return float(np.linalg.norm(left - right) / np.sqrt(left.shape[0]))


def make_control_interpolant(
    basis: WaveformBasis, variables: Array
) -> Callable[[float], complex]:
    if isinstance(basis, SourceConstrainedPhaseBasis):
        phase_values = np.asarray(variables, dtype=float)

        def source_control(t: float) -> complex:
            clipped = float(np.clip(t, 0.0, basis.model.duration))
            index = min(
                int(
                    clipped
                    / basis.model.duration
                    * basis.n_coefficients
                ),
                basis.n_coefficients - 1,
            )
            amplitude = basis.envelope_numpy(np.asarray([clipped]))[0]
            return complex(
                basis.model.omega0
                * amplitude
                * np.exp(1j * phase_values[index])
            )

        return source_control

    amplitude_coefficients, phase_coefficients = basis.unpack_numpy(variables)
    knots = clamped_knots(basis.n_coefficients)
    amplitude_spline = BSpline(knots, amplitude_coefficients, 3)
    phase_spline = BSpline(knots, phase_coefficients, 3)

    def control(t: float) -> complex:
        tau = np.clip(t / basis.model.duration, 0.0, 1.0)
        return complex(
            basis.model.omega0
            * amplitude_spline(tau)
            * np.exp(1j * phase_spline(tau))
        )

    return control


def grid_comparison(
    basis: WaveformBasis,
    variables: Array,
    node_counts: Iterable[int] = (101, 201, 401),
    remove_local_z: bool = False,
    adaptive_rtol: float = 1e-11,
    adaptive_atol: float = 1e-13,
    adaptive_max_step: float | None = None,
    numerical_tolerance: float = 1e-12,
) -> tuple[list[dict], Array]:
    control = make_control_interpolant(basis, variables)
    adaptive = propagate_adaptive(
        control,
        basis.model,
        rtol=adaptive_rtol,
        atol=adaptive_atol,
        max_step=adaptive_max_step,
    )[-1]
    adaptive_metrics = gate_metrics_numpy(
        adaptive,
        remove_local_z=remove_local_z,
        numerical_tolerance=numerical_tolerance,
    )
    rows: list[dict] = []
    for count in node_counts:
        times = np.linspace(0.0, basis.model.duration, count)
        midpoints = 0.5 * (times[:-1] + times[1:])
        _, _, values = basis.values_numpy(variables, midpoints)
        piecewise = propagate_piecewise_numpy(times, values, basis.model)
        metrics = gate_metrics_numpy(
            piecewise,
            remove_local_z=remove_local_z,
            numerical_tolerance=numerical_tolerance,
        )
        rows.append(
            {
                "provenance": PROVENANCE["analytic"],
                "nodes": int(count),
                "normalized_unitary_difference": normalized_unitary_difference(
                    piecewise, adaptive
                ),
                "piecewise_infidelity": metrics["infidelity"],
                "adaptive_infidelity": adaptive_metrics["infidelity"],
                "infidelity_difference": abs(
                    float(metrics["infidelity"])
                    - float(adaptive_metrics["infidelity"])
                ),
                "piecewise_max_leakage": metrics["max_leakage"],
                "adaptive_max_leakage": adaptive_metrics["max_leakage"],
                "max_leakage_difference": abs(
                    float(metrics["max_leakage"])
                    - float(adaptive_metrics["max_leakage"])
                ),
                "unitarity_residual": metrics["unitarity_residual"],
            }
        )
    return rows, adaptive


@dataclass
class JaxControlKernels:
    """Compiled fixed-grid propagation, objective, and derivative kernels."""

    basis: WaveformBasis
    nodes: int = 201
    optimizer_config: OptimizerConfig = field(default_factory=OptimizerConfig)
    numerical_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        require_jax("compiled propagation/objective kernels")
        if self.nodes < 3:
            raise ValueError("at least three nodes are required")
        times = np.linspace(0.0, self.basis.model.duration, self.nodes)
        midpoints = 0.5 * (times[:-1] + times[1:])
        dense_times = np.linspace(
            0.0,
            self.basis.model.duration,
            self.optimizer_config.regularizer_nodes,
        )
        design_midpoint = jnp.asarray(self.basis.design(midpoints))
        design_0 = jnp.asarray(self.basis.design(dense_times, derivative=0))
        design_1 = jnp.asarray(self.basis.design(dense_times, derivative=1))
        design_2 = jnp.asarray(self.basis.design(dense_times, derivative=2))
        dense_weights = jnp.asarray(trapezoid_weights(dense_times))
        dt = self.basis.model.duration / (self.nodes - 1)
        model = self.basis.model
        duration = self.basis.model.duration
        omega0 = self.basis.model.omega0

        def unitary_uncompiled(
            variables: JaxArray, amplitude_scale: JaxArray
        ) -> JaxArray:
            _, _, controls = self.basis.values_jax(
                variables, design_midpoint
            )
            return propagate_piecewise_jax(
                controls,
                dt,
                amplitude_scale=amplitude_scale,
                model=model,
            )

        def regularizers_uncompiled(variables: JaxArray) -> JaxArray:
            if isinstance(self.basis, SourceConstrainedPhaseBasis):
                amplitude = design_0[:, -1]
                phase_steps = variables[1:] - variables[:-1]
                dense_spacing = duration / (len(dense_times) - 1)
                amplitude_d1 = jnp.gradient(amplitude, dense_spacing)
                smoothness = jnp.sum(phase_steps**2)
                dwell_proxy = (
                    jnp.sum(dense_weights * amplitude**2) / duration
                )
                phase_slew = (
                    duration
                    / max(self.basis.n_coefficients - 1, 1)
                    * jnp.sum(phase_steps**2)
                    / (duration / self.basis.n_coefficients) ** 2
                )
                return jnp.asarray(
                    [
                        smoothness,
                        smoothness,
                        dwell_proxy,
                        duration
                        * jnp.sum(dense_weights * amplitude_d1**2),
                        phase_slew,
                    ]
                )
            amplitude_coefficients, phase_coefficients = (
                self.basis.unpack_jax(variables)
            )
            amplitude = design_0 @ amplitude_coefficients
            amplitude_d1 = design_1 @ amplitude_coefficients
            amplitude_d2 = design_2 @ amplitude_coefficients
            phase = design_0 @ phase_coefficients
            phase_d1 = design_1 @ phase_coefficients
            phase_d2 = design_2 @ phase_coefficients
            if isinstance(self.basis, TimeBinBasis):
                dense_spacing = duration / (len(dense_times) - 1)
                amplitude_d1 = jnp.gradient(amplitude, dense_spacing)
                amplitude_d2 = jnp.gradient(amplitude_d1, dense_spacing)
                phase_d1 = jnp.gradient(phase, dense_spacing)
                phase_d2 = jnp.gradient(phase_d1, dense_spacing)
            control_d1 = omega0 * jnp.exp(1j * phase) * (
                amplitude_d1 + 1j * amplitude * phase_d1
            )
            control_d2 = omega0 * jnp.exp(1j * phase) * (
                amplitude_d2
                + 2j * amplitude_d1 * phase_d1
                + 1j * amplitude * phase_d2
                - amplitude * phase_d1**2
            )
            smoothness = (
                duration**3
                / omega0**2
                * jnp.sum(dense_weights * jnp.abs(control_d2) ** 2)
            )
            bandwidth = (
                duration
                / omega0**2
                * jnp.sum(dense_weights * jnp.abs(control_d1) ** 2)
            )
            dwell_proxy = (
                jnp.sum(dense_weights * amplitude**2) / duration
            )
            amplitude_slew = duration * jnp.sum(
                dense_weights * amplitude_d1**2
            )
            phase_slew = duration * jnp.sum(
                dense_weights * amplitude**2 * phase_d1**2
            )
            return jnp.asarray(
                [
                    smoothness,
                    bandwidth,
                    dwell_proxy,
                    amplitude_slew,
                    phase_slew,
                ]
            )

        regularization_weights = jnp.asarray(
            [
                self.optimizer_config.smoothness_weight,
                self.optimizer_config.bandwidth_weight,
                self.optimizer_config.rydberg_dwell_weight,
                self.optimizer_config.amplitude_slew_weight,
                self.optimizer_config.phase_slew_weight,
            ],
            dtype=jnp.float64,
        )

        def nominal_objective_uncompiled(variables: JaxArray) -> JaxArray:
            unitary = unitary_uncompiled(variables, 1.0)
            infidelity, leakage, _ = gate_metrics_jax(
                unitary, fidelity_convention="pointwise_cz_equivalent"
            )
            returns = jnp.diag(
                unitary[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            )
            phase_invariant = (
                -returns[3]
                * returns[0]
                * jnp.conj(returns[1] * returns[2])
            )
            phase_unit = phase_invariant / jnp.abs(phase_invariant)
            phase_penalty = (
                jnp.imag(phase_unit) ** 2
                + (1.0 - jnp.real(phase_unit)) ** 2
            )
            return (
                infidelity
                + 0.25 * jnp.sum(leakage**2)
                + 0.02 * phase_penalty
                + jnp.dot(
                    regularization_weights,
                    regularizers_uncompiled(variables),
                )
            )

        def smoothness_uncompiled(variables: JaxArray) -> JaxArray:
            return regularizers_uncompiled(variables)[0]

        def robustness_uncompiled(
            variables: JaxArray,
        ) -> tuple[JaxArray, JaxArray]:
            unitary, derivative = jax.jvp(
                lambda scale: unitary_uncompiled(variables, scale),
                (jnp.asarray(1.0, dtype=jnp.float64),),
                (jnp.asarray(1.0, dtype=jnp.float64),),
            )
            generator = 1j * jnp.conj(unitary.T) @ derivative
            computational = generator[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            traceless = computational - (
                jnp.trace(computational) / 4.0
            ) * jnp.eye(4, dtype=jnp.complex128)
            # Echoed CZ benchmarking is insensitive to the symmetric
            # single-qubit Z phase.  Remove that direction for the AR
            # objective, but retain it later in the fixed-target Fig. 3
            # Hessian whose rank is ten.
            local_z = jnp.diag(
                jnp.asarray([-1.0, 0.0, 0.0, 1.0], dtype=jnp.complex128)
            )
            local_component = (
                jnp.real(jnp.trace(jnp.conj(local_z.T) @ traceless)) / 2.0
            )
            cz_equivalent = traceless - local_component * local_z
            leakage = generator[jnp.ix_(Q_IDX_JAX, P_IDX_JAX)]
            curvature = (
                2.0
                / 5.0
                * jnp.real(
                    jnp.trace(cz_equivalent @ jnp.conj(cz_equivalent.T))
                )
                + 0.5 * jnp.real(jnp.trace(leakage @ jnp.conj(leakage.T)))
            )
            channel_norm = jnp.sqrt(curvature + 1e-30)
            return curvature, channel_norm

        def robustness_diagnostics_uncompiled(
            variables: JaxArray,
        ) -> JaxArray:
            unitary, derivative = jax.jvp(
                lambda scale: unitary_uncompiled(variables, scale),
                (jnp.asarray(1.0, dtype=jnp.float64),),
                (jnp.asarray(1.0, dtype=jnp.float64),),
            )
            generator = 1j * jnp.conj(unitary.T) @ derivative
            computational = generator[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            traceless = computational - (
                jnp.trace(computational) / 4.0
            ) * jnp.eye(4, dtype=jnp.complex128)
            local_z = jnp.diag(
                jnp.asarray([-1.0, 0.0, 0.0, 1.0], dtype=jnp.complex128)
            )
            local_component = (
                jnp.real(jnp.trace(jnp.conj(local_z.T) @ traceless)) / 2.0
            )
            echoed = traceless - local_component * local_z
            leakage_generator = generator[jnp.ix_(Q_IDX_JAX, P_IDX_JAX)]
            leakage_term = 0.5 * jnp.real(
                jnp.trace(leakage_generator @ jnp.conj(leakage_generator.T))
            )
            fixed_curvature = (
                2.0
                / 5.0
                * jnp.real(jnp.trace(traceless @ jnp.conj(traceless.T)))
                + leakage_term
            )
            echoed_curvature = (
                2.0
                / 5.0
                * jnp.real(jnp.trace(echoed @ jnp.conj(echoed.T)))
                + leakage_term
            )
            returns = jnp.diag(
                unitary[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            )
            derivative_returns = jnp.diag(
                derivative[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            )
            phase_derivatives = jnp.imag(derivative_returns / returns)
            nonlinear_derivative = (
                phase_derivatives[3]
                - phase_derivatives[2]
                - phase_derivatives[1]
                + phase_derivatives[0]
            )
            local_derivative = (
                0.5 * (phase_derivatives[1] + phase_derivatives[2])
                - phase_derivatives[0]
            )
            symmetry_derivative = phase_derivatives[1] - phase_derivatives[2]
            direct_leakage = jnp.asarray(
                [
                    derivative[1, 0],
                    derivative[3, 2],
                    derivative[4, 2],
                    derivative[9, 8],
                ]
            )
            return jnp.asarray(
                [
                    fixed_curvature,
                    echoed_curvature,
                    jnp.linalg.norm(direct_leakage),
                    nonlinear_derivative,
                    local_derivative,
                    symmetry_derivative,
                ]
            )

        def robust_residual_uncompiled(variables: JaxArray) -> JaxArray:
            unitary, derivative = jax.jvp(
                lambda scale: unitary_uncompiled(variables, scale),
                (jnp.asarray(1.0, dtype=jnp.float64),),
                (jnp.asarray(1.0, dtype=jnp.float64),),
            )
            computational = unitary[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            returns = jnp.diag(computational)
            nominal_leakage = jnp.asarray(
                [
                    unitary[1, 0],
                    unitary[3, 2],
                    unitary[4, 2],
                    unitary[9, 8],
                ]
            )
            phase_invariant = (
                -returns[3]
                * returns[0]
                * jnp.conj(returns[1] * returns[2])
            )
            phase_unit = phase_invariant / jnp.abs(phase_invariant)
            if (
                self.optimizer_config.robustness_objective
                == "common_alpha_s11"
            ):
                source_columns = jnp.asarray(
                    [INDEX["|00>"], INDEX["|01>"], INDEX["|11>"]],
                    dtype=jnp.int32,
                )
                psi_zero = unitary[:, source_columns]
                psi_one = derivative[:, source_columns]
                alpha = (
                    jnp.sum(jnp.imag(jnp.conj(psi_zero) * psi_one))
                    / jnp.sum(jnp.abs(psi_zero) ** 2)
                )
                common_alpha_residual = psi_one - 1j * alpha * psi_zero
                return jnp.concatenate(
                    [
                        jnp.real(nominal_leakage),
                        jnp.imag(nominal_leakage),
                        jnp.asarray(
                            [
                                jnp.imag(phase_unit),
                                1.0 - jnp.real(phase_unit),
                            ]
                        ),
                        jnp.ravel(jnp.real(common_alpha_residual)),
                        jnp.ravel(jnp.imag(common_alpha_residual)),
                    ]
                )
            derivative_leakage = jnp.asarray(
                [
                    derivative[1, 0],
                    derivative[3, 2],
                    derivative[4, 2],
                    derivative[9, 8],
                ]
            )
            derivative_returns = jnp.diag(
                derivative[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
            )
            phase_derivatives = jnp.imag(derivative_returns / returns)
            derivative_phase = (
                phase_derivatives[3]
                - phase_derivatives[2]
                - phase_derivatives[1]
                + phase_derivatives[0]
            )
            return jnp.concatenate(
                [
                    jnp.real(nominal_leakage),
                    jnp.imag(nominal_leakage),
                    jnp.asarray(
                        [
                            jnp.imag(phase_unit),
                            1.0 - jnp.real(phase_unit),
                        ]
                    ),
                    jnp.real(derivative_leakage),
                    jnp.imag(derivative_leakage),
                    jnp.asarray([derivative_phase]),
                ]
            )

        def common_alpha_diagnostics_uncompiled(
            variables: JaxArray,
        ) -> JaxArray:
            unitary, derivative = jax.jvp(
                lambda scale: unitary_uncompiled(variables, scale),
                (jnp.asarray(1.0, dtype=jnp.float64),),
                (jnp.asarray(1.0, dtype=jnp.float64),),
            )
            source_columns = jnp.asarray(
                [INDEX["|00>"], INDEX["|01>"], INDEX["|11>"]],
                dtype=jnp.int32,
            )
            psi_zero = unitary[:, source_columns]
            psi_one = derivative[:, source_columns]
            alpha = (
                jnp.sum(jnp.imag(jnp.conj(psi_zero) * psi_one))
                / jnp.sum(jnp.abs(psi_zero) ** 2)
            )
            residual = psi_one - 1j * alpha * psi_zero
            return jnp.asarray([alpha, jnp.linalg.norm(residual)])

        def ar_continuation_objective_uncompiled(
            variables: JaxArray,
        ) -> JaxArray:
            residual = robust_residual_uncompiled(variables)
            # This transparent least-squares merit function provides a broad
            # basin before the high-accuracy trust-region root projection.
            return (
                0.5 * jnp.dot(residual, residual)
                + self.optimizer_config.ar_continuation_nominal_weight
                * nominal_objective_uncompiled(variables)
                + 1e-10 * smoothness_uncompiled(variables)
            )

        self.unitary = jax.jit(unitary_uncompiled)
        self.nominal_objective = jax.jit(nominal_objective_uncompiled)
        self.nominal_value_grad = jax.jit(
            jax.value_and_grad(nominal_objective_uncompiled)
        )
        self.smoothness = jax.jit(smoothness_uncompiled)
        self.regularizers = jax.jit(regularizers_uncompiled)
        self.smoothness_value_grad = jax.jit(
            jax.value_and_grad(smoothness_uncompiled)
        )
        self.robustness = jax.jit(robustness_uncompiled)
        self.robustness_diagnostics = jax.jit(
            robustness_diagnostics_uncompiled
        )
        self.robust_residual = jax.jit(robust_residual_uncompiled)
        self.robust_residual_jacobian = jax.jit(
            jax.jacrev(robust_residual_uncompiled)
        )
        self.common_alpha_diagnostics = jax.jit(
            common_alpha_diagnostics_uncompiled
        )
        self.ar_continuation_objective = jax.jit(
            ar_continuation_objective_uncompiled
        )
        self.ar_continuation_value_grad = jax.jit(
            jax.value_and_grad(ar_continuation_objective_uncompiled)
        )

    def evaluate(self, variables: Array) -> dict:
        variables_jax = jnp.asarray(variables)
        unitary = np.asarray(
            self.unitary(variables_jax, jnp.asarray(1.0)).block_until_ready()
        )
        metrics = gate_metrics_numpy(
            unitary,
            remove_local_z=True,
            numerical_tolerance=self.numerical_tolerance,
        )
        curvature, channel_norm = self.robustness(variables_jax)
        diagnostics = np.asarray(
            self.robustness_diagnostics(variables_jax), dtype=float
        )
        smoothness = self.smoothness(variables_jax)
        regularizers = np.asarray(self.regularizers(variables_jax), dtype=float)
        common_alpha = np.asarray(
            self.common_alpha_diagnostics(variables_jax), dtype=float
        )
        metrics.update(
            {
                "amplitude_curvature": float(curvature),
                "amplitude_channel_norm": float(channel_norm),
                "fixed_z_fidelity_curvature": diagnostics[0],
                "echoed_fidelity_curvature": diagnostics[1],
                "leakage_derivative_norm": diagnostics[2],
                "nonlinear_phase_derivative": diagnostics[3],
                "symmetric_local_z_phase_derivative": diagnostics[4],
                "single_excitation_symmetry_derivative": diagnostics[5],
                "smoothness": float(smoothness),
                "bandwidth_penalty": regularizers[1],
                "rydberg_dwell_proxy": regularizers[2],
                "amplitude_slew_penalty": regularizers[3],
                "phase_slew_penalty": regularizers[4],
                "common_alpha": common_alpha[0],
                "common_alpha_residual_norm": common_alpha[1],
            }
        )
        return metrics


def scipy_value_grad(
    function: Callable[[JaxArray], tuple[JaxArray, JaxArray]]
) -> Callable[[Array], tuple[float, Array]]:
    def wrapped(variables: Array) -> tuple[float, Array]:
        value, gradient = function(jnp.asarray(variables))
        return float(value), np.asarray(gradient, dtype=float)

    return wrapped


def optimize_nominal(
    kernels: JaxControlKernels,
    basis: WaveformBasis,
    starts: list[Array],
    label: str,
    maxiter: int = 350,
    complete_all_starts: bool = True,
    candidate_sink: list[Array] | None = None,
) -> tuple[Array, list[dict], list[dict]]:
    objective = scipy_value_grad(kernels.nominal_value_grad)
    trace: list[dict] = []
    attempts: list[dict] = []
    best_variables = np.asarray(starts[0], dtype=float)
    best_metrics = kernels.evaluate(best_variables)
    best_score = float("inf")
    for attempt, initial in enumerate(starts, 1):
        iteration = 0

        def callback(current: Array) -> None:
            nonlocal iteration
            iteration += 1
            if iteration == 1 or iteration % 10 == 0:
                metrics = kernels.evaluate(current)
                progress(
                    f"  {label} start {attempt}/{len(starts)}, "
                    f"iter {iteration}: 1-F={metrics['infidelity']:.3e}, "
                    f"Lmax={metrics['max_leakage']:.3e}"
                )
                trace.append(
                    {
                        "gate": label,
                        "stage": "nominal",
                        "attempt": attempt,
                        "iteration": iteration,
                        "infidelity": metrics["infidelity"],
                        "max_leakage": metrics["max_leakage"],
                        "cz_phase_error": metrics["cz_phase_error"],
                        "amplitude_curvature": metrics[
                            "amplitude_curvature"
                        ],
                        "smoothness": metrics["smoothness"],
                    }
                )

        started = time.perf_counter()
        result = optimize.minimize(
            objective,
            np.asarray(initial, dtype=float),
            method="L-BFGS-B",
            jac=True,
            bounds=basis.bounds(),
            callback=callback,
            options={
                "maxiter": maxiter,
                "ftol": 1e-15,
                "gtol": 1e-10,
                "maxls": 40,
            },
        )
        elapsed = time.perf_counter() - started
        metrics = kernels.evaluate(result.x)
        if candidate_sink is not None:
            candidate_sink.append(np.asarray(result.x, dtype=float))
        attempts.append(
            {
                "gate": label,
                "attempt": attempt,
                "success": bool(result.success),
                "message": str(result.message),
                "iterations": int(result.nit),
                "objective": float(result.fun),
                "wall_seconds": elapsed,
                "infidelity": metrics["infidelity"],
                "max_leakage": metrics["max_leakage"],
                "cz_phase_error": metrics["cz_phase_error"],
                "amplitude_curvature": metrics["amplitude_curvature"],
                "smoothness": metrics["smoothness"],
                "rydberg_dwell_time": waveform_rydberg_dwell_proxy(
                    basis, result.x
                ),
            }
        )
        progress(
            f"  {label} start {attempt} finished: "
            f"1-F={metrics['infidelity']:.3e}, "
            f"Lmax={metrics['max_leakage']:.3e}, "
            f"wall={elapsed:.1f}s"
        )
        score = (
            1e8 * abs(float(metrics["infidelity"]))
            + 1e8 * abs(float(metrics["max_leakage"]))
            + 1e-8 * float(metrics["smoothness"])
            + 1e-3 * waveform_rydberg_dwell_proxy(basis, result.x)
        )
        attempts[-1]["selection_score"] = score
        if score < best_score:
            best_variables = np.asarray(result.x)
            best_metrics = metrics
            best_score = score
        if not complete_all_starts and (
            best_metrics["infidelity"] <= 5e-9
            and best_metrics["max_leakage"] <= 5e-9
            and abs(best_metrics["cz_phase_error"]) <= 5e-5
        ):
            break
    return best_variables, trace, attempts


def select_ar_multistart(
    kernels: JaxControlKernels,
    basis: WaveformBasis,
    candidates: list[Array],
    iterations_per_candidate: int = 100,
) -> tuple[Array, list[dict[str, Any]]]:
    """Run a bounded AR continuation from every nominal candidate."""
    objective = scipy_value_grad(kernels.ar_continuation_value_grad)
    summaries: list[dict[str, Any]] = []
    best = np.asarray(candidates[0], dtype=float)
    best_score = float("inf")
    for index, candidate in enumerate(candidates, 1):
        started = time.perf_counter()
        result = optimize.minimize(
            objective,
            np.asarray(candidate, dtype=float),
            method="L-BFGS-B",
            jac=True,
            bounds=basis.bounds(),
            options={
                "maxiter": iterations_per_candidate,
                "ftol": 1e-13,
                "gtol": 1e-8,
                "maxls": 40,
            },
        )
        residual = np.asarray(
            kernels.robust_residual(jnp.asarray(result.x)), dtype=float
        )
        metrics = kernels.evaluate(result.x)
        score = (
            float(np.linalg.norm(residual))
            + 1e3 * abs(float(metrics["infidelity"]))
            + 1e3 * abs(float(metrics["max_leakage"]))
            + 1e-8 * float(metrics["smoothness"])
            + 1e-2 * waveform_rydberg_dwell_proxy(basis, result.x)
        )
        summary = {
            "candidate": index,
            "success": bool(result.success),
            "message": str(result.message),
            "iterations": int(result.nit),
            "wall_seconds": time.perf_counter() - started,
            "residual_norm": float(np.linalg.norm(residual)),
            "selection_score": score,
            "selection_terms": {
                "ar_residual_norm": float(np.linalg.norm(residual)),
                "nominal_infidelity": metrics["infidelity"],
                "max_terminal_leakage": metrics["max_leakage"],
                "smoothness": metrics["smoothness"],
                "rydberg_dwell_proxy_us": waveform_rydberg_dwell_proxy(
                    basis, result.x
                ),
            },
            "metrics": metrics,
        }
        summaries.append(summary)
        progress(
            f"  AR multistart {index}/{len(candidates)}: "
            f"||r||={summary['residual_norm']:.3e}, "
            f"1-F={metrics['infidelity']:.3e}"
        )
        if score < best_score:
            best = np.asarray(result.x)
            best_score = score
    return best, summaries


def optimize_robustness(
    kernels: JaxControlKernels,
    basis: WaveformBasis,
    initial: Array,
    maxiter: int = 2000,
) -> tuple[Array, list[dict], dict]:
    trace: list[dict] = []
    common_alpha_objective = (
        kernels.optimizer_config.robustness_objective
        == "common_alpha_s11"
    )
    channel_definition = {
        "nominal": (
            "4 complex leakage amplitudes + branch-safe sin(delta_phi) "
            "and 1-cos(delta_phi)"
        ),
        "amplitude_derivative": (
            "full psi_q^(1) - i alpha psi_q^(0) state-vector residual for "
            "q in {|00>, |01>, |11>}, with one real common alpha"
            if common_alpha_objective
            else "4 complex terminal leakage-amplitude derivatives + "
            "nonlinear CZ-phase derivative"
        ),
        "reported_but_not_zeroed_channel": (
            "none; common alpha is eliminated analytically"
            if common_alpha_objective
            else "the symmetric single-qubit Z derivative is excluded from "
            "the echoed AR root but reported separately"
        ),
    }

    def derivative_is_feasible(metrics: dict[str, Any]) -> bool:
        common_alpha_feasible = (
            not common_alpha_objective
            or metrics["common_alpha_residual_norm"]
            <= kernels.optimizer_config.ar_derivative_norm_tolerance
        )
        return bool(
            common_alpha_feasible
            and metrics["amplitude_curvature"]
            <= kernels.optimizer_config.amplitude_curvature_tolerance
        )

    def residual(variables: Array) -> Array:
        return np.asarray(
            kernels.robust_residual(jnp.asarray(variables)), dtype=float
        )

    def jacobian(variables: Array) -> Array:
        return np.asarray(
            kernels.robust_residual_jacobian(jnp.asarray(variables)),
            dtype=float,
        )

    evaluations = 0
    last_report = 0

    def residual_with_progress(variables: Array) -> Array:
        nonlocal evaluations, last_report
        evaluations += 1
        values = residual(variables)
        if evaluations == 1 or evaluations - last_report >= 25:
            last_report = evaluations
            metrics = kernels.evaluate(variables)
            residual_norm = float(np.linalg.norm(values))
            progress(
                f"  robust channel solve eval {evaluations}: "
                f"||r||={residual_norm:.3e}, "
                f"1-F={metrics['infidelity']:.3e}, "
                f"Lmax={metrics['max_leakage']:.3e}, "
                f"kappa_amp={metrics['amplitude_curvature']:.3e}"
            )
            trace.append(
                {
                    "gate": "robust",
                    "stage": "branch_safe_ar_channel_root",
                    "attempt": 1,
                    "iteration": evaluations,
                    "residual_norm": residual_norm,
                    "infidelity": metrics["infidelity"],
                    "max_leakage": metrics["max_leakage"],
                    "cz_phase_error": metrics["cz_phase_error"],
                    "amplitude_curvature": metrics[
                        "amplitude_curvature"
                    ],
                    "smoothness": metrics["smoothness"],
                }
            )
        return values

    lower, upper = np.asarray(basis.bounds(), dtype=float).T
    continuation_iteration = 0

    def continuation_callback(current: Array) -> None:
        nonlocal continuation_iteration
        continuation_iteration += 1
        if continuation_iteration == 1 or continuation_iteration % 20 == 0:
            residual_norm = float(np.linalg.norm(residual(current)))
            progress(
                f"  AR continuation iter {continuation_iteration}: "
                f"||r||={residual_norm:.3e}"
            )

    started = time.perf_counter()
    continuation = optimize.minimize(
        scipy_value_grad(kernels.ar_continuation_value_grad),
        np.asarray(initial, dtype=float),
        method="L-BFGS-B",
        jac=True,
        bounds=basis.bounds(),
        callback=continuation_callback,
        options={
            "maxiter": kernels.optimizer_config.ar_continuation_maxiter,
            "ftol": 1e-15,
            "gtol": 1e-10,
            "maxls": 50,
        },
    )
    progress(
        "  AR continuation finished: "
        f"||r||={np.linalg.norm(residual(continuation.x)):.3e}"
    )
    continuation_residual = residual(continuation.x)
    continuation_metrics = kernels.evaluate(continuation.x)
    if (
        np.linalg.norm(continuation_residual) <= 1e-4
        and continuation_metrics["infidelity"] <= 1e-8
        and continuation_metrics["max_leakage"] <= 1e-8
        and derivative_is_feasible(continuation_metrics)
    ):
        elapsed = time.perf_counter() - started
        summary = {
            "provenance": PROVENANCE["equivalent"],
            "success": True,
            "message": (
                "AR continuation already met the declared feasible set; "
                "trust-region projection was not needed"
            ),
            "iterations": 0,
            "objective": float(
                0.5 * np.dot(continuation_residual, continuation_residual)
            ),
            "residual_norm": float(np.linalg.norm(continuation_residual)),
            "optimality": np.nan,
            "active_mask": np.zeros_like(continuation.x, dtype=int),
            "wall_seconds": elapsed,
            "metrics": continuation_metrics,
            "continuation": {
                "success": bool(continuation.success),
                "message": str(continuation.message),
                "iterations": int(continuation.nit),
                "objective": float(continuation.fun),
                "residual_norm": float(np.linalg.norm(continuation_residual)),
            },
            "channel_definition": channel_definition,
        }
        progress(
            "  AR continuation is feasible: "
            f"||r||={summary['residual_norm']:.3e}"
        )
        return np.asarray(continuation.x), trace, summary
    result = optimize.least_squares(
        residual_with_progress,
        np.asarray(continuation.x, dtype=float),
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale="jac",
        ftol=1e-14,
        xtol=1e-14,
        gtol=1e-12,
        max_nfev=maxiter,
        verbose=0,
    )
    elapsed = time.perf_counter() - started
    metrics = kernels.evaluate(result.x)
    final_residual = residual(result.x)
    summary = {
        "provenance": PROVENANCE["equivalent"],
        "success": bool(
            np.linalg.norm(final_residual) <= 1e-4
            and metrics["infidelity"] <= 1e-8
            and metrics["max_leakage"] <= 1e-8
            and derivative_is_feasible(metrics)
        ),
        "message": str(result.message),
        "continuation": {
            "success": bool(continuation.success),
            "message": str(continuation.message),
            "iterations": int(continuation.nit),
            "objective": float(continuation.fun),
            "residual_norm": float(np.linalg.norm(residual(continuation.x))),
        },
        "iterations": int(result.nfev),
        "objective": float(0.5 * np.dot(final_residual, final_residual)),
        "residual_norm": float(np.linalg.norm(final_residual)),
        "optimality": float(result.optimality),
        "active_mask": result.active_mask,
        "wall_seconds": elapsed,
        "metrics": metrics,
        "channel_definition": channel_definition,
    }
    progress(
        f"  robust channel solve selected: ||r||="
        f"{summary['residual_norm']:.3e}, "
        f"1-F={metrics['infidelity']:.3e}, "
        f"Lmax={metrics['max_leakage']:.3e}, "
        f"kappa_amp={metrics['amplitude_curvature']:.3e}"
    )
    return np.asarray(result.x), trace, summary



def feasible_manifold_smooth(
    kernels: JaxControlKernels,
    basis: WaveformBasis,
    initial: Array,
    max_root_evaluations: int = 40,
) -> tuple[Array, list[dict], dict]:
    """One bounded null-space smoothing pass on the final fine grid."""
    initial = np.asarray(initial, dtype=float)
    residual0 = np.asarray(
        kernels.robust_residual(jnp.asarray(initial)), dtype=float
    )
    jacobian0 = np.asarray(
        kernels.robust_residual_jacobian(jnp.asarray(initial)), dtype=float
    )
    smoothness0, gradient = kernels.smoothness_value_grad(
        jnp.asarray(initial)
    )
    _, singular_values, right = np.linalg.svd(jacobian0, full_matrices=True)
    threshold = max(singular_values[0] * 1e-9, 1e-11)
    rank = int(np.count_nonzero(singular_values > threshold))
    null_basis = right[rank:].T
    projected = null_basis @ (null_basis.T @ np.asarray(gradient))
    projected_norm = float(np.linalg.norm(projected))
    trace: list[dict[str, Any]] = []
    if projected_norm == 0.0 or null_basis.shape[1] == 0:
        return initial, trace, {
            "success": False,
            "message": "no numerical tangent direction for smoothing",
            "initial_smoothness": float(smoothness0),
            "final_smoothness": float(smoothness0),
            "channel_rank": rank,
            "null_dimension": int(null_basis.shape[1]),
        }
    direction = -projected / projected_norm
    lower, upper = np.asarray(basis.bounds(), dtype=float).T

    def residual(values: Array) -> Array:
        return np.asarray(
            kernels.robust_residual(jnp.asarray(values)), dtype=float
        )

    def jacobian(values: Array) -> Array:
        return np.asarray(
            kernels.robust_residual_jacobian(jnp.asarray(values)), dtype=float
        )

    best = initial
    best_metrics = kernels.evaluate(initial)
    for attempt, step in enumerate((0.01, 0.003, 0.001), 1):
        progress(
            f"  null-space smoothing attempt {attempt}/3, tangent step={step:.3g}"
        )
        trial = np.clip(initial + step * direction, lower, upper)
        root = optimize.least_squares(
            residual,
            trial,
            jac=jacobian,
            bounds=(lower, upper),
            method="trf",
            x_scale="jac",
            ftol=1e-11,
            xtol=1e-11,
            gtol=1e-9,
            max_nfev=max_root_evaluations,
        )
        metrics = kernels.evaluate(root.x)
        residual_norm = float(np.linalg.norm(residual(root.x)))
        accepted = bool(
            residual_norm <= 1e-4
            and metrics["infidelity"] <= 1e-8
            and metrics["max_leakage"] <= 1e-8
            and metrics["echoed_fidelity_curvature"] <= 1e-8
            and metrics["smoothness"] < best_metrics["smoothness"]
        )
        trace.append(
            {
                "attempt": attempt,
                "step": step,
                "root_evaluations": int(root.nfev),
                "residual_norm": residual_norm,
                "smoothness": metrics["smoothness"],
                "accepted": accepted,
            }
        )
        progress(
            f"    residual={residual_norm:.3e}, "
            f"smoothness={metrics['smoothness']:.3e}, accepted={accepted}"
        )
        if accepted:
            best = np.asarray(root.x)
            best_metrics = metrics
            break
    return best, trace, {
        "success": bool(not np.array_equal(best, initial)),
        "message": (
            "accepted a fine-grid tangent/null-space smoothing step"
            if not np.array_equal(best, initial)
            else "no trial improved smoothness while retaining feasibility"
        ),
        "initial_smoothness": float(smoothness0),
        "final_smoothness": best_metrics["smoothness"],
        "channel_rank": rank,
        "null_dimension": int(null_basis.shape[1]),
        "projected_gradient_norm": projected_norm,
        "metrics": best_metrics,
        "trace": trace,
    }


def optimization_starts(
    basis: WaveformBasis, count: int = 4, seed: int = 260605060
) -> list[Array]:
    return [values for _, values in generic_multistarts(basis, count, seed)]


def waveform_rydberg_dwell_proxy(
    basis: WaveformBasis, variables: Array, nodes: int = 101
) -> float:
    """Cheap reconstruction-choice proxy used only for candidate ranking.

    The exact integrated Rydberg population is reported after propagation;
    this envelope-area proxy keeps multistart selection inexpensive.
    """
    times = np.linspace(0.0, basis.model.duration, nodes)
    amplitude, _, _ = basis.values_numpy(variables, times)
    return float(np.trapezoid(amplitude**2, times))


def save_waveform(
    path: Path,
    basis: WaveformBasis,
    variables: Array,
    label: str,
    provenance: str,
    config: RunConfig | None = None,
    stage_metrics: dict[str, Any] | None = None,
) -> None:
    output_nodes = config.waveform_output_nodes if config is not None else 401
    times = np.linspace(0.0, basis.model.duration, output_nodes)
    amplitude, phase, control = basis.values_numpy(variables, times)
    amplitude_coefficients, phase_coefficients = basis.unpack_numpy(variables)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        label=label,
        provenance=provenance,
        variables=np.asarray(variables),
        amplitude_coefficients=amplitude_coefficients,
        phase_coefficients=phase_coefficients,
        times_us=times,
        amplitude=amplitude,
        phase=phase,
        phase_wrapped=wrap_phase(phase),
        phase_unwrapped=np.unwrap(phase),
        control=control,
        config_hash=config_hash(config) if config is not None else "",
        code_version=code_version(),
        model_json=json.dumps(asdict(config.model) if config else asdict(ModelConfig())),
        backend=(
            config.optimizer.backend
            if config is not None
            else basis.__class__.__name__
        ),
        stage_metrics_json=json.dumps(
            stage_metrics or {}, default=json_default
        ),
    )


def optimize_waveforms(
    run_dir: Path, config: RunConfig | None = None
) -> dict:
    """Staged gradient-based spline/time-bin optimal control.

    This is an equivalent physical reoptimization, not the authors'
    unpublished pulse or exact GRAPE implementation.
    """
    require_jax("waveform optimization")
    config = config or RunConfig()
    basis = make_basis(config)
    optimizer_config = config.optimizer
    kernels = JaxControlKernels(
        basis,
        nodes=optimizer_config.coarse_nodes,
        optimizer_config=optimizer_config,
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    progress(
        "Optimization 1/5: compiling the coarse-grid propagation/objective "
        f"kernel ({optimizer_config.coarse_nodes} nodes)..."
    )
    compile_started = time.perf_counter()
    seed = generic_seed_waveform(basis)
    seed_metrics = kernels.evaluate(seed)
    compile_seconds = time.perf_counter() - compile_started
    progress(
        f"  compiled in {compile_seconds:.2f}s; seed 1-F="
        f"{seed_metrics['infidelity']:.3e}"
    )

    named_starts = generic_multistarts(
        basis,
        optimizer_config.starts,
        optimizer_config.random_seed,
        optimizer_config.use_paper_shaped_diagnostic_seed,
    )
    starts = [values for _, values in named_starts]
    progress("Optimization 2/5: finding a nominal non-robust CZ gate...")
    nonrobust_candidates: list[Array] = []
    nonrobust, trace_nonrobust, attempts_nonrobust = optimize_nominal(
        kernels,
        basis,
        starts,
        "same_duration_nonrobust_surrogate",
        maxiter=optimizer_config.nominal_maxiter,
        complete_all_starts=True,
        candidate_sink=nonrobust_candidates,
    )

    progress("Optimization 3/5: finding the nominal seed for the robust gate...")
    nominal_candidates: list[Array] = []
    robust_nominal, trace_nominal, attempts_nominal = optimize_nominal(
        kernels,
        basis,
        [nonrobust] + starts,
        "robust_nominal",
        maxiter=optimizer_config.nominal_maxiter,
        complete_all_starts=True,
        candidate_sink=nominal_candidates,
    )
    nominal_metrics = kernels.evaluate(robust_nominal)
    save_waveform(
        run_dir / "data" / "robust_stage_nominal.npz",
        basis,
        robust_nominal,
        "nominal AR candidate before channel solve",
        PROVENANCE["equivalent"],
        config,
        nominal_metrics,
    )
    progress(
        "Optimization 3b/5: AR continuation from every nominal candidate..."
    )
    robust_start, ar_multistart_summaries = select_ar_multistart(
        kernels,
        basis,
        nominal_candidates,
        iterations_per_candidate=min(
            100, optimizer_config.ar_continuation_maxiter
        ),
    )
    save_waveform(
        run_dir / "data" / "robust_stage_ar_multistart.npz",
        basis,
        robust_start,
        "best generic multistart after AR continuation",
        PROVENANCE["equivalent"],
        config,
        kernels.evaluate(robust_start),
    )
    progress("Optimization 4/5: solving coarse first-order AR channels...")
    robust_coarse, trace_robust, robust_summary = optimize_robustness(
        kernels,
        basis,
        robust_start,
        maxiter=optimizer_config.robust_max_nfev,
    )
    coarse_metrics = kernels.evaluate(robust_coarse)
    save_waveform(
        run_dir / "data" / "robust_stage_coarse_ar.npz",
        basis,
        robust_coarse,
        "coarse-grid AR channel solution",
        PROVENANCE["equivalent"],
        config,
        coarse_metrics,
    )

    progress(
        "Optimization 5/5: fine-grid AR polish followed by feasible-manifold "
        "smoothing..."
    )
    fine_kernels = JaxControlKernels(
        basis,
        nodes=optimizer_config.fine_nodes,
        optimizer_config=optimizer_config,
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    robust_fine, trace_robust_fine, robust_fine_summary = optimize_robustness(
        fine_kernels,
        basis,
        robust_coarse,
        maxiter=optimizer_config.robust_max_nfev,
    )
    fine_metrics_before_smoothing = fine_kernels.evaluate(robust_fine)
    save_waveform(
        run_dir / "data" / "robust_stage_fine_ar.npz",
        basis,
        robust_fine,
        "fine-grid AR channel solution before smoothing",
        PROVENANCE["equivalent"],
        config,
        fine_metrics_before_smoothing,
    )
    robust = robust_fine
    trace_smooth: list[dict] = []
    smooth_summary: dict[str, Any] = {
        "success": False,
        "message": "fine-grid feasibility not reached; smoothing skipped",
        "metrics": fine_metrics_before_smoothing,
    }
    if (
        fine_metrics_before_smoothing["infidelity"]
        <= optimizer_config.nominal_infidelity_tolerance
        and fine_metrics_before_smoothing["max_leakage"]
        <= optimizer_config.leakage_tolerance
        and fine_metrics_before_smoothing["echoed_fidelity_curvature"]
        <= optimizer_config.amplitude_curvature_tolerance
    ):
        smoothed, trace_smooth, smooth_summary = feasible_manifold_smooth(
            fine_kernels,
            basis,
            robust_fine,
            max_root_evaluations=min(
                40, optimizer_config.smooth_maxiter
            ),
        )
        smoothed_metrics = fine_kernels.evaluate(smoothed)
        if (
            smoothed_metrics["infidelity"]
            <= optimizer_config.nominal_infidelity_tolerance
            and smoothed_metrics["max_leakage"]
            <= optimizer_config.leakage_tolerance
            and smoothed_metrics["echoed_fidelity_curvature"]
            <= optimizer_config.amplitude_curvature_tolerance
        ):
            robust = smoothed
    robust_metrics = fine_kernels.evaluate(robust)

    (
        nonrobust,
        trace_nonrobust_fine,
        attempts_nonrobust_fine,
    ) = optimize_nominal(
        fine_kernels,
        basis,
        [nonrobust],
        "same_duration_nonrobust_surrogate_fine",
        maxiter=optimizer_config.nominal_maxiter,
        complete_all_starts=True,
    )
    nonrobust_metrics = fine_kernels.evaluate(nonrobust)

    save_waveform(
        run_dir / "data" / "nonrobust_waveform.npz",
        basis,
        nonrobust,
        "same-duration non-robust CZ surrogate (not a time-optimal gate)",
        PROVENANCE["equivalent"],
        config,
        nonrobust_metrics,
    )
    save_waveform(
        run_dir / "data" / "robust_waveform.npz",
        basis,
        robust,
        "equivalently reoptimized amplitude-robust CZ",
        PROVENANCE["equivalent"],
        config,
        robust_metrics,
    )
    trace = (
        trace_nonrobust
        + trace_nominal
        + trace_robust
        + trace_smooth
        + trace_robust_fine
        + trace_nonrobust_fine
    )
    if trace:
        write_csv(run_dir / "data" / "optimization_trace.csv", trace)

    robust_grid, robust_adaptive = grid_comparison(
        basis,
        robust,
        node_counts=config.grid_node_counts,
        remove_local_z=True,
        adaptive_rtol=config.adaptive_rtol,
        adaptive_atol=config.adaptive_atol,
        adaptive_max_step=(
            basis.model.duration * config.adaptive_max_step_fraction
        ),
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    nonrobust_grid, nonrobust_adaptive = grid_comparison(
        basis,
        nonrobust,
        node_counts=config.grid_node_counts,
        remove_local_z=True,
        adaptive_rtol=config.adaptive_rtol,
        adaptive_atol=config.adaptive_atol,
        adaptive_max_step=(
            basis.model.duration * config.adaptive_max_step_fraction
        ),
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    write_csv(run_dir / "data" / "robust_grid_comparison.csv", robust_grid)
    write_csv(
        run_dir / "data" / "nonrobust_grid_comparison.csv", nonrobust_grid
    )
    robust_adaptive_metrics = gate_metrics_numpy(
        robust_adaptive,
        remove_local_z=True,
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    nonrobust_adaptive_metrics = gate_metrics_numpy(
        nonrobust_adaptive,
        remove_local_z=True,
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )

    def nominal_start_statistics(attempts: list[dict[str, Any]]) -> dict:
        accepted = [
            item
            for item in attempts
            if item["infidelity"]
            <= optimizer_config.nominal_infidelity_tolerance
            and item["max_leakage"]
            <= optimizer_config.leakage_tolerance
        ]
        return {
            "starts_completed": len(attempts),
            "numerically_accepted_starts": len(accepted),
            "success_fraction": (
                len(accepted) / len(attempts) if attempts else 0.0
            ),
            "final_infidelity_range": [
                float(min(item["infidelity"] for item in attempts)),
                float(max(item["infidelity"] for item in attempts)),
            ],
            "final_smoothness_range": [
                float(min(item["smoothness"] for item in attempts)),
                float(max(item["smoothness"] for item in attempts)),
            ],
            "final_dwell_proxy_range_us": [
                float(min(item["rydberg_dwell_time"] for item in attempts)),
                float(max(item["rydberg_dwell_time"] for item in attempts)),
            ],
        }

    summary = {
        "compile_seconds": compile_seconds,
        "provenance": PROVENANCE["equivalent"],
        "method": "gradient-based differentiable optimal control",
        "reproduction_boundary": PROVENANCE["equivalent"],
        "backend": optimizer_config.backend,
        "parameter_count": basis.n_free,
        "control_coefficients_per_channel": basis.n_coefficients,
        "initial_seeds": [name for name, _ in named_starts],
        "seed_statistics": {
            "same_duration_nonrobust_surrogate": (
                nominal_start_statistics(attempts_nonrobust)
            ),
            "robust_nominal_candidates": nominal_start_statistics(
                attempts_nominal
            ),
            "ar_continuation_candidates_completed": len(
                ar_multistart_summaries
            ),
            "ar_continuation_residual_norm_range": [
                float(
                    min(
                        item["residual_norm"]
                        for item in ar_multistart_summaries
                    )
                ),
                float(
                    max(
                        item["residual_norm"]
                        for item in ar_multistart_summaries
                    )
                ),
            ],
        },
        "bounds": {
            "normalized_amplitude": [0.0, optimizer_config.amplitude_bound],
            "phase_rad": [
                -2.0 * np.pi * optimizer_config.phase_bound_turns,
                2.0 * np.pi * optimizer_config.phase_bound_turns,
            ],
            "zero_amplitude_and_slope_endpoints": True,
        },
        "optimizers": {
            "nominal": "SciPy L-BFGS-B with JAX value/gradient",
            "ar_channels": "SciPy trust-region least_squares with JAX Jacobian",
            "smoothing": (
                "fine-grid tangent/null-space descent with trust-region "
                "least-squares re-projection"
            ),
        },
        "stopping_criteria": asdict(optimizer_config),
        "regularization_weights_are_reconstruction_choices": {
            "smoothness": optimizer_config.smoothness_weight,
            "bandwidth": optimizer_config.bandwidth_weight,
            "rydberg_dwell": optimizer_config.rydberg_dwell_weight,
            "amplitude_slew": optimizer_config.amplitude_slew_weight,
            "phase_slew": optimizer_config.phase_slew_weight,
        },
        "seed_metrics": seed_metrics,
        "nonrobust": {
            "fixed_grid_metrics": nonrobust_metrics,
            "adaptive_metrics": nonrobust_adaptive_metrics,
            "attempts": attempts_nonrobust,
            "final_fine_attempts": attempts_nonrobust_fine,
            "grid_comparison": nonrobust_grid,
        },
        "robust": {
            "fixed_grid_metrics": robust_metrics,
            "adaptive_metrics": robust_adaptive_metrics,
            "nominal_attempts": attempts_nominal,
            "ar_multistart": ar_multistart_summaries,
            "robust_stage": robust_summary,
            "coarse_metrics": coarse_metrics,
            "fine_stage": robust_fine_summary,
            "fine_metrics_before_smoothing": fine_metrics_before_smoothing,
            "smooth_stage": smooth_summary,
            "grid_comparison": robust_grid,
        },
    }
    summary["acceptance"] = {
        "nonrobust_nominal": bool(
            nonrobust_adaptive_metrics["infidelity"]
            <= optimizer_config.nominal_infidelity_tolerance
            and nonrobust_adaptive_metrics["max_leakage"]
            <= optimizer_config.leakage_tolerance
        ),
        "robust_nominal": bool(
            robust_adaptive_metrics["infidelity"]
            <= optimizer_config.nominal_infidelity_tolerance
            and robust_adaptive_metrics["max_leakage"]
            <= optimizer_config.leakage_tolerance
        ),
        "robust_derivative": bool(
            (
                robust_metrics["common_alpha_residual_norm"]
                <= optimizer_config.ar_derivative_norm_tolerance
                if optimizer_config.robustness_objective
                == "common_alpha_s11"
                else (
                    robust_metrics["leakage_derivative_norm"]
                    <= optimizer_config.ar_derivative_norm_tolerance
                    and abs(robust_metrics["nonlinear_phase_derivative"])
                    <= optimizer_config.ar_derivative_norm_tolerance
                )
            )
            and robust_metrics["amplitude_curvature"]
            <= optimizer_config.amplitude_curvature_tolerance
        ),
        "robust_cz_phase": bool(
            abs(robust_adaptive_metrics["cz_phase_error"]) <= 1e-4
        ),
    }
    summary["acceptance"]["all"] = bool(all(summary["acceptance"].values()))
    write_json(run_dir / "data" / "optimization_summary.json", summary)
    progress(
        "Optimization checkpoint complete: "
        f"robust adaptive 1-F={robust_adaptive_metrics['infidelity']:.3e}, "
        f"Lmax={robust_adaptive_metrics['max_leakage']:.3e}, "
        f"kappa_echoed={robust_metrics['echoed_fidelity_curvature']:.3e}"
    )
    return summary


def mwe(
    run_dir: Path | None = None, config: RunConfig | None = None
) -> dict:
    config = config or RunConfig()
    model = Model.from_config(config.model)
    basis = make_basis(config)
    variables = seed_waveform(basis)
    progress("MWE 1/3: constructing the ten-state Hamiltonian...")
    sample_hamiltonian = hamiltonian_numpy(model.omega0 * (0.7 + 0.2j), model)
    hermiticity = np.linalg.norm(sample_hamiltonian - sample_hamiltonian.conj().T)
    progress(
        "MWE 2/3: comparing matrix-exponential grids "
        f"{config.grid_node_counts} to DOP853..."
    )
    rows, adaptive = grid_comparison(
        basis,
        variables,
        node_counts=config.grid_node_counts,
        adaptive_rtol=config.adaptive_rtol,
        adaptive_atol=config.adaptive_atol,
        adaptive_max_step=(
            model.duration * config.adaptive_max_step_fraction
        ),
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    errors = np.asarray([row["normalized_unitary_difference"] for row in rows])
    ratios = errors[:-1] / errors[1:]
    if JAX_AVAILABLE:
        progress("MWE 3/3: checking JAX and NumPy matrix-exponential routes...")
        count = int(config.grid_node_counts[0])
        times = np.linspace(0.0, model.duration, count)
        midpoints = 0.5 * (times[:-1] + times[1:])
        design = jnp.asarray(basis.design(midpoints))
        _, _, controls = basis.values_jax(jnp.asarray(variables), design)
        started = time.perf_counter()
        jax_final = np.asarray(
            jax.jit(propagate_piecewise_jax, static_argnames=("model",))(
                controls, model.duration / (count - 1), model=model
            ).block_until_ready()
        )
        compile_seconds = time.perf_counter() - started
        numpy_final = propagate_piecewise_numpy(
            times, np.asarray(controls), model
        )
        jax_numpy_difference: float | None = normalized_unitary_difference(
            jax_final, numpy_final
        )
    else:
        progress(
            "MWE 3/3: JAX unavailable; NumPy/SciPy checks remain valid and "
            "the JAX comparison is explicitly skipped."
        )
        compile_seconds = 0.0
        jax_numpy_difference = None
    summary = {
        "provenance": PROVENANCE["analytic"],
        "basis": list(BASIS),
        "computational_indices": P_IDX.tolist(),
        "leakage_indices": Q_IDX.tolist(),
        "hermiticity_residual": float(hermiticity),
        "adaptive_unitarity_residual": gate_metrics_numpy(adaptive)[
            "unitarity_residual"
        ],
        "grid_rows": rows,
        "grid_error_ratios": ratios.tolist(),
        "jax_numpy_difference_101": jax_numpy_difference,
        "jax_compile_and_first_run_seconds": compile_seconds,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "jax": jax.__version__ if JAX_AVAILABLE else "unavailable",
            "jax_devices": (
                [str(device) for device in jax.devices()]
                if JAX_AVAILABLE
                else []
            ),
            "jax_x64": (
                bool(jax.config.jax_enable_x64) if JAX_AVAILABLE else None
            ),
        },
        "acceptance": {
            "hermitian": bool(hermiticity <= 1e-13),
            "unitary": bool(
                gate_metrics_numpy(adaptive)["unitarity_residual"] <= 1e-10
            ),
            "second_order": bool(np.all((ratios >= 3.0) & (ratios <= 5.0))),
            "jax_matches_numpy": (
                bool(jax_numpy_difference <= 1e-11)
                if jax_numpy_difference is not None
                else "skipped: JAX unavailable"
            ),
        },
    }
    summary["acceptance"]["all"] = bool(
        all(value is True or isinstance(value, str)
            for value in summary["acceptance"].values())
    )
    if run_dir is not None:
        write_json(run_dir / "data" / "mwe_summary.json", summary)
        write_csv(run_dir / "data" / "mwe_grid_comparison.csv", rows)
        figure, axis = plt.subplots(figsize=(5.8, 3.8))
        axis.loglog(
            [row["nodes"] - 1 for row in rows],
            [row["normalized_unitary_difference"] for row in rows],
            "o-",
            label="midpoint/expm vs DOP853",
        )
        reference = errors[0] * (
            (np.asarray([row["nodes"] - 1 for row in rows])
             / (rows[0]["nodes"] - 1)) ** -2
        )
        axis.loglog(
            [row["nodes"] - 1 for row in rows],
            reference,
            "--",
            label="second-order reference",
        )
        axis.set(
            xlabel="Number of propagation intervals",
            ylabel="Normalized unitary difference",
            title="Independent-propagator grid convergence",
        )
        axis.grid(True, which="both", alpha=0.2)
        axis.legend(frameon=False)
        figure.tight_layout()
        plot_path = run_dir / "figs" / "mwe_grid_convergence.png"
        figure.savefig(plot_path, dpi=180)
        plt.close(figure)
        summary["plot"] = str(plot_path)
        write_json(run_dir / "data" / "mwe_summary.json", summary)
    comparison_text = (
        f"{jax_numpy_difference:.3e}"
        if jax_numpy_difference is not None
        else "skipped"
    )
    progress(
        "MWE complete: "
        f"Hermitian={summary['acceptance']['hermitian']}, "
        f"unitary={summary['acceptance']['unitary']}, "
        f"grid ratios={ratios}, "
        f"JAX/NumPy={comparison_text}"
    )
    return summary


def load_waveform_variables(
    path: Path,
    expected_config: RunConfig | None = None,
) -> Array:
    if not path.exists():
        raise FileNotFoundError(
            f"required waveform cache does not exist: {path}. "
            "Run --stage optimize first."
        )
    with np.load(path) as archive:
        if expected_config is not None:
            if "config_hash" not in archive:
                raise RuntimeError(
                    f"{path} is a cache without a configuration hash; "
                    "refusing unsafe reuse"
                )
            else:
                cached = str(archive["config_hash"].item())
                expected = config_hash(expected_config)
                if cached != expected:
                    raise RuntimeError(
                        f"incompatible waveform cache {path}: cached config "
                        f"hash {cached}, expected {expected}"
                    )
                cached_code = (
                    str(archive["code_version"].item())
                    if "code_version" in archive
                    else ""
                )
                if cached_code != code_version():
                    raise RuntimeError(
                        f"incompatible waveform cache {path}: cached code "
                        f"version {cached_code!r}, expected {code_version()!r}"
                    )
        return np.asarray(archive["variables"], dtype=float)


def fixed_target_fidelity(unitary: Array, nominal: Array) -> float:
    interaction = nominal.conj().T @ unitary
    computational = interaction[np.ix_(P_IDX, P_IDX)]
    return average_gate_fidelity_from_target(
        computational, np.eye(4, dtype=np.complex128)
    )


def rydberg_populations_from_trajectory(
    trajectory: Array,
) -> dict[str, Array]:
    """Appendix-C total Rydberg populations used in Figure 3(c).

    The |01> curve is the sum of its two orthogonal Rydberg channels.  The
    |10> curve is identical by atom-exchange symmetry and is not duplicated
    in the main panel.
    """
    trajectory = np.asarray(trajectory, dtype=np.complex128)
    if trajectory.ndim != 3 or trajectory.shape[1:] != (10, 10):
        raise ValueError("trajectory must have shape (time, 10, 10)")
    component_01_0r = (
        abs(trajectory[:, INDEX["|0r>"], INDEX["|01>"]]) ** 2
    )
    component_01_rprime1 = (
        abs(trajectory[:, INDEX["|r'1>"], INDEX["|01>"]]) ** 2
    )
    return {
        "P00_total_rydberg": (
            abs(trajectory[:, INDEX["|W'>"], INDEX["|00>"]]) ** 2
        ),
        "P01_total_rydberg": component_01_0r + component_01_rprime1,
        "P11_total_rydberg": (
            abs(trajectory[:, INDEX["|W>"], INDEX["|11>"]]) ** 2
        ),
        "P01_to_0r_diagnostic": component_01_0r,
        "P01_to_rprime1_diagnostic": component_01_rprime1,
    }


def plot_waveform_and_populations(
    run_dir: Path,
    basis: WaveformBasis,
    variables: Array,
    nodes: int = 501,
    adaptive_max_step: float | None = None,
) -> dict:
    times = np.linspace(0.0, basis.model.duration, nodes)
    amplitude, phase, _ = basis.values_numpy(variables, times)
    control = make_control_interpolant(basis, variables)
    trajectory = propagate_adaptive(
        control,
        basis.model,
        times=times,
        rtol=2e-11,
        atol=2e-13,
        max_step=adaptive_max_step,
    )
    population_data = rydberg_populations_from_trajectory(trajectory)
    populations = {
        key: population_data[key]
        for key in (
            "P00_total_rydberg",
            "P01_total_rydberg",
            "P11_total_rydberg",
        )
    }
    phase_wrapped = wrap_phase(phase)
    phase_unwrapped = np.unwrap(phase)
    rows = []
    for index, time_value in enumerate(times):
        rows.append(
            {
                "provenance": PROVENANCE["equivalent"],
                "time_us": time_value,
                "amplitude_ratio": amplitude[index],
                "intensity_ratio": amplitude[index] ** 2,
                "phase_wrapped_rad": phase_wrapped[index],
                "phase_unwrapped_rad": phase_unwrapped[index],
                "phase_wrapped_turns": phase_wrapped[index] / (2.0 * np.pi),
                "phase_unwrapped_turns": phase_unwrapped[index] / (2.0 * np.pi),
                "P01_to_0r_diagnostic": population_data[
                    "P01_to_0r_diagnostic"
                ][index],
                "P01_to_rprime1_diagnostic": population_data[
                    "P01_to_rprime1_diagnostic"
                ][index],
                **{key: value[index] for key, value in populations.items()},
            }
        )
    write_csv(run_dir / "data" / "fig3_waveform_populations.csv", rows)

    figure, axes = plt.subplots(3, 1, figsize=(7.2, 7.2), sharex=True)
    axes[0].plot(times, amplitude**2, color="#c43b3b", lw=2)
    axes[0].set_ylabel("|Ω/Ω₀|²")
    source_constrained = isinstance(basis, SourceConstrainedPhaseBasis)
    axes[0].set_title(
        "Source-constrained AR CZ waveform"
        if source_constrained
        else "Equivalent reoptimized AR CZ waveform"
    )
    axes[1].plot(
        times, phase_unwrapped / (2.0 * np.pi), color="#315a9a", lw=1.6
    )
    axes[1].set_ylabel("Continuous φ/(2π)", color="#315a9a")
    labels = {
        "P00_total_rydberg": "P₀₀",
        "P01_total_rydberg": "P₀₁ (=P₁₀ by symmetry)",
        "P11_total_rydberg": "P₁₁",
    }
    for label, values in populations.items():
        axes[2].plot(times, values, lw=1.7, label=labels[label])
    axes[2].set(xlabel="Time (μs)", ylabel="Rydberg population")
    axes[2].legend(frameon=False, ncol=2, fontsize=8)
    axes[2].set_ylim(bottom=0)
    figure.tight_layout()
    output = run_dir / "figs" / "fig3_theory_waveform_populations.png"
    figure.savefig(output, dpi=180)
    plt.close(figure)

    waveform_figure, waveform_axes = plt.subplots(
        2, 1, figsize=(5.2, 4.2), sharex=True
    )
    waveform_axes[0].plot(times, amplitude**2, color="#bc3f3c", lw=2.0)
    waveform_axes[0].set(ylabel="|Ω/Ω₀|²")
    waveform_axes[1].plot(
        times,
        phase_unwrapped / (2.0 * np.pi),
        color="#315a9a",
        lw=1.7,
    )
    waveform_axes[1].set(ylabel="φ/(2π)", xlabel="time (μs)")
    for axis in waveform_axes:
        axis.grid(alpha=0.18)
    waveform_figure.tight_layout()
    waveform_output = run_dir / "figs" / (
        "fig3b_source_constrained_waveform.png"
        if source_constrained
        else "fig3b_equivalent_waveform.png"
    )
    waveform_figure.savefig(waveform_output, dpi=220)
    plt.close(waveform_figure)
    summary = {
        "plot": str(output),
        "figure3b_plot": str(waveform_output),
        "provenance": PROVENANCE["equivalent"],
        "max_populations": {
            key: float(np.max(value)) for key, value in populations.items()
        },
        "integrated_rydberg_population_us": {
            key: float(np.trapezoid(value, times))
            for key, value in populations.items()
        },
        "symmetry_statement": (
            "The |10> total Rydberg population equals |01> by atom-exchange "
            "symmetry of the reduced Hamiltonian."
        ),
        "waveform_match_claim": (
            "No pixelwise or array-level match to the unpublished paper pulse "
            "is claimed."
        ),
    }
    write_json(
        run_dir / "data" / "fig3_waveform_population_summary.json",
        summary,
    )
    return summary



def appendix_c_hessian_components(
    channel_jacobian: Array,
) -> dict[str, Array]:
    """Return the four Appendix-C Hessian contributions.

    Channel order is Re(a00, a01→0r, a01→r′1, a11),
    Im(a00, a01→0r, a01→r′1, a11), θ01, θ11.  Appendix C defines

    1−F = ½α00 + α01 + ½α11 + εθ,
    αq = ½ Σl |aql|²,
    εθ = (θ01−θ11/2)²/5 + θ11²/10.

    Since 1−F = ½ sᵀHs, the leakage Gram prefactors in H are ½, 1, ½.
    """
    jacobian = np.asarray(channel_jacobian, dtype=float)
    if jacobian.ndim != 2 or jacobian.shape[0] != 10:
        raise ValueError("channel_jacobian must have shape (10, parameters)")

    def gram(rows: list[int], prefactor: float) -> Array:
        block = jacobian[rows]
        return prefactor * block.T @ block

    h00 = gram([0, 4], 0.5)
    h01 = gram([1, 2, 5, 6], 1.0)
    h11 = gram([3, 7], 0.5)
    phase_jacobian = jacobian[8:10]
    phase_weight = np.asarray([[0.2, -0.1], [-0.1, 0.15]])
    hphase = 2.0 * phase_jacobian.T @ phase_weight @ phase_jacobian
    return {
        "alpha00": h00,
        "alpha01": h01,
        "alpha11": h11,
        "theta": hphase,
    }


def hessian_at_resolution(
    basis: WaveformBasis,
    variables: Array,
    n_bins: int,
    nodes: int,
    convention: str = "paper_lab_iq",
) -> dict[str, Any]:
    """Build Appendix-B/C Hessian at one temporal resolution.

    ``paper_lab_iq`` implements
    Ω_dist(t)=Ω_ideal(t)+|Ω_ideal(t)|[s_x(t)+i s_y(t)].
    ``local_amplitude_phase_frame`` implements the diagnostic coordinates
    Ω_dist=Ω_ideal(1+s_x+i s_y).  Pointwise the frames differ by an
    orthogonal rotation through the ideal phase; finite constant bins do not
    make this transform exact within each bin.
    """
    require_jax("Hessian automatic differentiation")
    if convention not in ("paper_lab_iq", "local_amplitude_phase_frame"):
        raise ValueError(f"unknown distortion convention {convention!r}")
    times = np.linspace(0.0, basis.model.duration, nodes)
    midpoints = 0.5 * (times[:-1] + times[1:])
    _, _, ideal_numpy = basis.values_numpy(variables, midpoints)
    ideal = jnp.asarray(ideal_numpy)
    envelope = jnp.asarray(np.abs(ideal_numpy))
    dt = basis.model.duration / (nodes - 1)
    bin_width = basis.model.duration / n_bins
    bin_index = jnp.asarray(
        np.minimum((midpoints / bin_width).astype(int), n_bins - 1)
    )
    normalization = math.sqrt(bin_width)

    def distorted_unitary_uncompiled(coefficients: JaxArray) -> JaxArray:
        sx = coefficients[:n_bins][bin_index] / normalization
        sy = coefficients[n_bins:][bin_index] / normalization
        if convention == "paper_lab_iq":
            distorted = ideal + envelope * (sx + 1j * sy)
        else:
            distorted = ideal * (1.0 + sx + 1j * sy)
        return propagate_piecewise_jax(distorted, dt, model=basis.model)

    zero = jnp.zeros(2 * n_bins, dtype=jnp.float64)
    distorted_unitary = jax.jit(distorted_unitary_uncompiled)
    nominal = distorted_unitary(zero)

    def channels_uncompiled(coefficients: JaxArray) -> JaxArray:
        unitary = distorted_unitary_uncompiled(coefficients)
        interaction = jnp.conj(nominal.T) @ unitary
        leakage = jnp.asarray(
            [
                interaction[INDEX["|W'>"], INDEX["|00>"]],
                interaction[INDEX["|0r>"], INDEX["|01>"]],
                interaction[INDEX["|r'1>"], INDEX["|01>"]],
                interaction[INDEX["|W>"], INDEX["|11>"]],
            ]
        )
        # These angles are differentiated at interaction=I, safely away from
        # the ±π branch.  Nonlinear optimization residuals use the separate
        # branch-safe complex invariant.
        theta01 = jnp.angle(
            interaction[INDEX["|01>"], INDEX["|01>"]]
            * jnp.conj(interaction[INDEX["|00>"], INDEX["|00>"]])
        )
        theta11 = jnp.angle(
            interaction[INDEX["|11>"], INDEX["|11>"]]
            * jnp.conj(interaction[INDEX["|00>"], INDEX["|00>"]])
        )
        return jnp.concatenate(
            [
                jnp.real(leakage),
                jnp.imag(leakage),
                jnp.asarray([theta01, theta11]),
            ]
        )

    started = time.perf_counter()
    channel_jacobian = np.asarray(
        jax.jit(jax.jacrev(channels_uncompiled))(zero).block_until_ready(),
        dtype=float,
    )
    compile_seconds = time.perf_counter() - started

    components = appendix_c_hessian_components(channel_jacobian)
    raw_hessian = sum(components.values())
    symmetry_residual = float(np.linalg.norm(raw_hessian - raw_hessian.T))
    hessian = 0.5 * (raw_hessian + raw_hessian.T)
    eigenvalues, eigenvectors = np.linalg.eigh(hessian)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    return {
        "hessian": hessian,
        "components": components,
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "channel_jacobian": channel_jacobian,
        "channel_rank": int(np.linalg.matrix_rank(channel_jacobian)),
        "nominal": np.asarray(nominal),
        "distorted_unitary": distorted_unitary,
        "bin_centers_us": (np.arange(n_bins) + 0.5) * bin_width,
        "normalization": normalization,
        "symmetry_residual": symmetry_residual,
        "compile_seconds": compile_seconds,
        "n_bins": n_bins,
        "nodes": nodes,
        "convention": convention,
    }


def hessian_finite_difference_checks(
    result: dict[str, Any],
    epsilons: Iterable[float],
    random_seed: int = 260605060,
) -> list[dict[str, Any]]:
    eigenvalues = result["eigenvalues"]
    eigenvectors = result["eigenvectors"]
    nominal = result["nominal"]
    distorted_unitary = result["distorted_unitary"]
    baseline = 1.0 - fixed_target_fidelity(nominal, nominal)
    directions: list[tuple[str, int, Array, float]] = []
    for index in range(min(14, len(eigenvalues))):
        directions.append(
            (
                "principal" if index < 10 else "null_mode",
                index + 1,
                eigenvectors[:, index],
                eigenvalues[index],
            )
        )
    rng = np.random.default_rng(random_seed)
    null = eigenvectors[:, 10:]
    for index in range(min(4, null.shape[1])):
        weights = rng.normal(size=null.shape[1])
        direction = null @ weights
        direction /= np.linalg.norm(direction)
        directions.append(
            (
                "random_null_combination",
                index + 1,
                direction,
                float(direction @ result["hessian"] @ direction),
            )
        )
    rows: list[dict[str, Any]] = []
    for kind, mode, direction, predicted_curvature in directions:
        for epsilon in epsilons:
            plus_unitary = np.asarray(
                distorted_unitary(jnp.asarray(epsilon * direction))
            )
            minus_unitary = np.asarray(
                distorted_unitary(jnp.asarray(-epsilon * direction))
            )
            plus = 1.0 - fixed_target_fidelity(plus_unitary, nominal)
            minus = 1.0 - fixed_target_fidelity(minus_unitary, nominal)
            central_curvature = (plus + minus - 2.0 * baseline) / epsilon**2
            relative = (
                abs(central_curvature - predicted_curvature)
                / abs(predicted_curvature)
                if abs(predicted_curvature) > 1e-12
                else np.nan
            )
            rows.append(
                {
                    "provenance": PROVENANCE["equivalent"],
                    "kind": kind,
                    "mode": mode,
                    "epsilon": epsilon,
                    "baseline_infidelity_raw": baseline,
                    "plus_infidelity_raw": plus,
                    "minus_infidelity_raw": minus,
                    "central_curvature": central_curvature,
                    "hessian_curvature": predicted_curvature,
                    "relative_error": relative,
                    "evenness_residual": abs(plus - minus),
                }
            )
    return rows


def direct_autodiff_infidelity_hessian(
    result: dict[str, Any],
) -> Array:
    """Independent direct Hessian of 1−F for small-grid validation."""
    require_jax("direct fidelity Hessian validation")
    nominal = jnp.asarray(result["nominal"])
    distorted_unitary = result["distorted_unitary"]
    dimension = len(result["eigenvalues"])

    def infidelity(coefficients: JaxArray) -> JaxArray:
        unitary = distorted_unitary(coefficients)
        interaction = jnp.conj(nominal.T) @ unitary
        computational = interaction[jnp.ix_(P_IDX_JAX, P_IDX_JAX)]
        fidelity = (
            jnp.abs(jnp.trace(computational)) ** 2
            + jnp.real(
                jnp.trace(computational @ jnp.conj(computational.T))
            )
        ) / 20.0
        return 1.0 - fidelity

    zero = jnp.zeros(dimension, dtype=jnp.float64)
    return np.asarray(
        jax.jit(jax.hessian(infidelity))(zero).block_until_ready(),
        dtype=float,
    )


def hessian_analysis(
    run_dir: Path,
    config: RunConfig | None = None,
    n_bins: int | None = None,
    nodes: int | None = None,
) -> dict:
    config = config or RunConfig()
    basis = make_basis(config)
    variables = load_waveform_variables(
        run_dir / "data" / "robust_waveform.npz",
        expected_config=config,
    )
    hconfig = config.hessian
    bin_counts = (n_bins,) if n_bins is not None else hconfig.bin_counts
    node_counts = (nodes,) if nodes is not None else hconfig.propagation_nodes
    resolution_rows: list[dict[str, Any]] = []
    lab_results: dict[tuple[int, int], dict[str, Any]] = {}
    for count in bin_counts:
        for node_count in node_counts:
            progress(
                f"Hessian: paper lab-I/Q, {count} bins, {node_count} nodes..."
            )
            result = hessian_at_resolution(
                basis, variables, count, node_count, "paper_lab_iq"
            )
            lab_results[(count, node_count)] = result
            values = result["eigenvalues"]
            rank_by_threshold = {
                f"{threshold:.0e}": int(
                    np.count_nonzero(values > abs(values[0]) * threshold)
                )
                for threshold in hconfig.rank_relative_tolerances
            }
            resolution_rows.append(
                {
                    "provenance": PROVENANCE["equivalent"],
                    "convention": "paper_lab_iq",
                    "n_bins": count,
                    "nodes": node_count,
                    "channel_rank": result["channel_rank"],
                    "rank_by_relative_threshold": json.dumps(rank_by_threshold),
                    "rank_all_declared_thresholds_10": bool(
                        all(rank == 10 for rank in rank_by_threshold.values())
                    ),
                    "lambda_1": values[0],
                    "lambda_10": values[9],
                    "lambda_11": values[10],
                    "lambda10_over_abs_lambda11": (
                        values[9] / max(abs(values[10]), np.finfo(float).tiny)
                    ),
                    "minimum_eigenvalue": values[-1],
                    "psd_violation": min(values[-1], 0.0),
                    "symmetry_residual": result["symmetry_residual"],
                    "compile_seconds": result["compile_seconds"],
                }
            )
    finest_nodes = max(node_counts)
    finest_bins = max(bin_counts)
    for row in resolution_rows:
        count = int(row["n_bins"])
        node_count = int(row["nodes"])
        values = lab_results[(count, node_count)]["eigenvalues"][:10]
        node_reference = lab_results[(count, finest_nodes)][
            "eigenvalues"
        ][:10]
        bin_reference = lab_results[(finest_bins, node_count)][
            "eigenvalues"
        ][:10]
        row["relative_top10_to_finest_nodes_same_bins"] = float(
            np.linalg.norm(values - node_reference)
            / np.linalg.norm(node_reference)
        )
        row["relative_top10_to_finest_bins_same_nodes"] = float(
            np.linalg.norm(values - bin_reference)
            / np.linalg.norm(bin_reference)
        )
    selected_key = (max(bin_counts), max(node_counts))
    selected = lab_results[selected_key]
    progress(
        f"Hessian diagnostic frame: local amplitude/phase, "
        f"{selected_key[0]} bins, {selected_key[1]} nodes..."
    )
    local = hessian_at_resolution(
        basis,
        variables,
        selected_key[0],
        selected_key[1],
        "local_amplitude_phase_frame",
    )
    local_values = local["eigenvalues"]
    resolution_rows.append(
        {
            "provenance": PROVENANCE["equivalent"],
            "convention": "local_amplitude_phase_frame",
            "n_bins": selected_key[0],
            "nodes": selected_key[1],
            "channel_rank": local["channel_rank"],
            "rank_by_relative_threshold": json.dumps(
                {
                    f"{threshold:.0e}": int(
                        np.count_nonzero(
                            local_values
                            > abs(local_values[0]) * threshold
                        )
                    )
                    for threshold in hconfig.rank_relative_tolerances
                }
            ),
            "rank_all_declared_thresholds_10": bool(
                all(
                    np.count_nonzero(
                        local_values > abs(local_values[0]) * threshold
                    )
                    == 10
                    for threshold in hconfig.rank_relative_tolerances
                )
            ),
            "relative_top10_to_finest_nodes_same_bins": np.nan,
            "relative_top10_to_finest_bins_same_nodes": np.nan,
            "lambda_1": local_values[0],
            "lambda_10": local_values[9],
            "lambda_11": local_values[10],
            "lambda10_over_abs_lambda11": (
                local_values[9]
                / max(abs(local_values[10]), np.finfo(float).tiny)
            ),
            "minimum_eigenvalue": local_values[-1],
            "psd_violation": min(local_values[-1], 0.0),
            "symmetry_residual": local["symmetry_residual"],
            "compile_seconds": local["compile_seconds"],
        }
    )
    write_csv(
        run_dir / "data" / "fig3_hessian_resolution_convergence.csv",
        resolution_rows,
    )

    eigenvalues = selected["eigenvalues"]
    eigenvectors = selected["eigenvectors"]
    components = selected["components"]
    decomposition = {
        name: np.asarray(
            [
                eigenvectors[:, index] @ component @ eigenvectors[:, index]
                for index in range(10)
            ]
        )
        for name, component in components.items()
    }
    spectrum_rows = []
    for index, value in enumerate(eigenvalues[:14]):
        spectrum_rows.append(
            {
                "provenance": PROVENANCE["equivalent"],
                "mode": index + 1,
                "eigenvalue": value,
                "space": (
                    "physical principal space" if index < 10
                    else "numerical null space"
                ),
                **{
                    name: (
                        decomposition[name][index] if index < 10 else np.nan
                    )
                    for name in decomposition
                },
            }
        )
    write_csv(run_dir / "data" / "fig3_hessian_spectrum.csv", spectrum_rows)
    np.savez_compressed(
        run_dir / "data" / "fig3_hessian_modes.npz",
        hessian=selected["hessian"],
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        channel_jacobian=selected["channel_jacobian"],
        bin_centers_us=selected["bin_centers_us"],
        convention="paper_lab_iq",
        local_frame_eigenvalues=local_values,
        config_hash=config_hash(config),
        code_version=code_version(),
        provenance=PROVENANCE["equivalent"],
    )
    fd_rows = hessian_finite_difference_checks(
        selected, hconfig.fd_epsilons, config.optimizer.random_seed
    )
    write_csv(run_dir / "data" / "fig3_hessian_fd_checks.csv", fd_rows)

    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.1))
    mode_axis = np.arange(1, len(eigenvalues) + 1)
    positive = eigenvalues >= 0
    axes[0].plot(
        mode_axis[positive], eigenvalues[positive], "o", color="#315a9a",
        label="non-negative",
    )
    if np.any(~positive):
        axes[0].plot(
            mode_axis[~positive], eigenvalues[~positive], "x",
            color="#c43b3b", label="negative (PSD violation)",
        )
    axes[0].set_yscale("symlog", linthresh=max(abs(eigenvalues[0]) * 1e-14, 1e-15))
    axes[0].axvline(10.5, ls="--", color="0.45")
    axes[0].set(
        xlabel="Mode",
        ylabel="Signed Hessian eigenvalue",
        title="Paper lab-I/Q Hessian spectrum",
    )
    axes[0].legend(frameon=False, fontsize=8)
    bottom = np.zeros(10)
    colors = {
        "alpha00": "#4477aa",
        "alpha01": "#66ccee",
        "alpha11": "#cc6677",
        "theta": "#aa3377",
    }
    for name in ("alpha00", "alpha01", "alpha11", "theta"):
        axes[1].bar(
            np.arange(1, 11),
            decomposition[name],
            bottom=bottom,
            color=colors[name],
            label=name,
        )
        bottom += decomposition[name]
    axes[1].set(
        xlabel="Principal mode",
        ylabel="Eigenvalue contribution",
        title="Appendix-C channel decomposition",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure.tight_layout()
    plot_path = run_dir / "figs" / "fig3_theory_hessian.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)

    centers = selected["bin_centers_us"]
    normalization = selected["normalization"]
    modes_figure, mode_axes = plt.subplots(5, 2, figsize=(10.5, 11.5), sharex=True)
    for index, axis in enumerate(mode_axes.flat):
        axis.plot(
            centers,
            eigenvectors[: selected_key[0], index] / normalization,
            label="x (lab I)",
        )
        axis.plot(
            centers,
            eigenvectors[selected_key[0] :, index] / normalization,
            label="y (lab Q)",
        )
        axis.set_title(f"principal mode {index + 1}")
        axis.axhline(0.0, color="0.7", lw=0.6)
    for axis in mode_axes[-1]:
        axis.set_xlabel("Time (μs)")
    mode_axes[0, 0].legend(frameon=False, fontsize=8)
    modes_figure.tight_layout()
    modes_path = run_dir / "figs" / "fig3_hessian_principal_modes_xy.png"
    modes_figure.savefig(modes_path, dpi=180)
    plt.close(modes_figure)

    principal_best_errors = []
    for mode in range(1, 11):
        candidates = [
            row["relative_error"]
            for row in fd_rows
            if row["kind"] == "principal"
            and row["mode"] == mode
            and np.isfinite(row["relative_error"])
        ]
        principal_best_errors.append(min(candidates, default=np.inf))
    rank_stable = (
        len({row["channel_rank"] for row in resolution_rows
             if row["convention"] == "paper_lab_iq"}) == 1
        and all(
            row["channel_rank"] == 10
            for row in resolution_rows
            if row["convention"] == "paper_lab_iq"
        )
        and len(bin_counts) >= 2
        and len(node_counts) >= 2
        and all(
            row["rank_all_declared_thresholds_10"]
            for row in resolution_rows
            if row["convention"] == "paper_lab_iq"
        )
    )
    psd_tolerance = max(abs(eigenvalues[0]) * 1e-10, 1e-12)
    spectral_gap = eigenvalues[9] / max(
        abs(eigenvalues[10]), np.finfo(float).tiny
    )
    relative_frame_spectrum = float(
        np.linalg.norm(eigenvalues[:10] - local_values[:10])
        / np.linalg.norm(eigenvalues[:10])
    )
    coarser_node_counts = [
        node_count for node_count in node_counts if node_count != finest_nodes
    ]
    propagation_spectrum_differences = [
        float(
            np.linalg.norm(
                lab_results[(count, node_count)]["eigenvalues"][:10]
                - lab_results[(count, finest_nodes)]["eigenvalues"][:10]
            )
            / np.linalg.norm(
                lab_results[(count, finest_nodes)]["eigenvalues"][:10]
            )
        )
        for count in bin_counts
        for node_count in coarser_node_counts
    ]
    propagation_spectrum_max_difference = max(
        propagation_spectrum_differences, default=np.inf
    )
    previous_bins = sorted(bin_counts)[-2] if len(bin_counts) >= 2 else None
    bin_refinement_difference = (
        float(
            np.linalg.norm(
                lab_results[(previous_bins, finest_nodes)][
                    "eigenvalues"
                ][:10]
                - eigenvalues[:10]
            )
            / np.linalg.norm(eigenvalues[:10])
        )
        if previous_bins is not None
        else np.inf
    )
    null_best_curvatures = []
    for kind in ("null_mode", "random_null_combination"):
        mode_numbers = sorted(
            {
                int(row["mode"])
                for row in fd_rows
                if row["kind"] == kind
            }
        )
        for mode in mode_numbers:
            candidates = [
                abs(float(row["central_curvature"]))
                for row in fd_rows
                if row["kind"] == kind and int(row["mode"]) == mode
            ]
            null_best_curvatures.append(min(candidates, default=np.inf))
    null_max_best_relative_curvature = float(
        max(null_best_curvatures, default=np.inf) / abs(eigenvalues[9])
    )
    summary = {
        "provenance": PROVENANCE["equivalent"],
        "default_convention": "paper_lab_iq",
        "diagnostic_convention": "local_amplitude_phase_frame",
        "frame_relation": (
            "The continuous coordinates are related by a time-dependent "
            "orthogonal rotation through the ideal phase. Finite piecewise "
            "constant bins need not have identical spectra."
        ),
        "finite_bin_top10_spectrum_relative_difference": relative_frame_spectrum,
        "propagation_top10_spectrum_relative_differences": (
            propagation_spectrum_differences
        ),
        "propagation_top10_spectrum_max_relative_difference": (
            propagation_spectrum_max_difference
        ),
        "last_bin_refinement_top10_spectrum_relative_difference": (
            bin_refinement_difference
        ),
        "selected_resolution": {
            "n_bins": selected_key[0],
            "nodes": selected_key[1],
        },
        "front_14_eigenvalues": eigenvalues[:14],
        "lambda10_over_lambda11_absolute": spectral_gap,
        "minimum_eigenvalue": float(eigenvalues[-1]),
        "psd_violation": float(min(eigenvalues[-1], 0.0)),
        "symmetry_residual": selected["symmetry_residual"],
        "rank": selected["channel_rank"],
        "rank_stable_across_resolutions": rank_stable,
        "fd_best_relative_error_by_principal_mode": principal_best_errors,
        "fd_max_best_relative_error": float(max(principal_best_errors)),
        "null_fd_best_absolute_curvatures": null_best_curvatures,
        "null_fd_max_best_curvature_over_lambda10": (
            null_max_best_relative_curvature
        ),
        "plots": [str(plot_path), str(modes_path)],
        "acceptance": {
            "symmetric": bool(selected["symmetry_residual"] <= 1e-12),
            "psd_within_numerical_tolerance": bool(
                eigenvalues[-1] >= -psd_tolerance
            ),
            "rank_10_stable": bool(rank_stable),
            "principal_null_spectral_gap": bool(spectral_gap >= 1e6),
            "principal_finite_difference": bool(
                max(principal_best_errors) <= hconfig.fd_relative_tolerance
            ),
            "null_finite_difference": bool(
                null_max_best_relative_curvature
                <= hconfig.null_curvature_relative_tolerance
            ),
            "lab_local_frame_rank_invariance": bool(
                local["channel_rank"] == selected["channel_rank"] == 10
            ),
            "lab_local_frame_spectrum_convergence": bool(
                relative_frame_spectrum <= hconfig.frame_spectrum_tolerance
            ),
            "propagation_grid_convergence": bool(
                propagation_spectrum_max_difference
                <= hconfig.propagation_spectrum_tolerance
            ),
        },
    }
    summary["acceptance"]["all"] = bool(all(summary["acceptance"].values()))
    write_json(run_dir / "data" / "fig3_hessian_summary.json", summary)
    return summary


def intensity_to_amplitude_ratio(intensity_ratio: float | Array) -> float | Array:
    values = np.asarray(intensity_ratio, dtype=float)
    if np.any(values < 0.0):
        raise ValueError("intensity ratio must be non-negative")
    result = np.sqrt(values)
    return float(result) if result.ndim == 0 else result


def intensity_scaling_analysis(run_dir: Path, config: RunConfig | None = None) -> dict:
    require_jax("intensity scaling")
    config = config or RunConfig()
    basis = make_basis(config)
    kernels = JaxControlKernels(
        basis,
        nodes=config.optimizer.fine_nodes,
        optimizer_config=config.optimizer,
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    robust = load_waveform_variables(
        run_dir / "data" / "robust_waveform.npz", expected_config=config
    )
    nonrobust = load_waveform_variables(
        run_dir / "data" / "nonrobust_waveform.npz", expected_config=config
    )
    iconfig = config.intensity
    maximum_offset = max(
        abs(iconfig.diagnostic_min_ratio - 1.0),
        abs(iconfig.diagnostic_max_ratio - 1.0),
    )
    offsets = np.unique(
        np.concatenate(
            [
                -np.geomspace(2e-3, maximum_offset, iconfig.points_per_side),
                np.asarray([0.0]),
                np.geomspace(2e-3, maximum_offset, iconfig.points_per_side),
            ]
        )
    )
    rows: list[dict[str, Any]] = []
    nominal_phases: dict[str, float] = {}
    nominal_floors: dict[str, dict[str, float]] = {}
    gates = (
        ("AR equivalent reoptimization", robust),
        ("same-duration non-robust surrogate", nonrobust),
    )
    for label, variables in gates:
        nominal_unitary = np.asarray(
            kernels.unitary(jnp.asarray(variables), jnp.asarray(1.0))
        )
        nominal_pointwise = gate_metrics_numpy(
            nominal_unitary, "pointwise_cz_equivalent"
        )
        nominal_phase = float(nominal_pointwise["local_z_phase"])
        nominal_phases[label] = nominal_phase
        nominal_floors[label] = {}
        for offset in offsets:
            intensity_ratio = 1.0 + offset
            unitary = np.asarray(
                kernels.unitary(
                    jnp.asarray(variables),
                    jnp.asarray(intensity_to_amplitude_ratio(intensity_ratio)),
                )
            )
            for convention in FIDELITY_CONVENTIONS:
                metrics = gate_metrics_numpy(
                    unitary,
                    convention,
                    nominal_virtual_z=(
                        nominal_phase
                        if convention == "fixed_nominal_virtual_z"
                        else None
                    ),
                )
                if offset == 0.0:
                    nominal_floors[label][convention] = float(
                        metrics["infidelity"]
                    )
                rows.append(
                    {
                        "provenance": PROVENANCE["equivalent"],
                        "gate": label,
                        "intensity_ratio": intensity_ratio,
                        "amplitude_ratio": intensity_to_amplitude_ratio(
                            intensity_ratio
                        ),
                        "delta_intensity": offset,
                        "range": (
                            "paper_range"
                            if iconfig.paper_min_ratio
                            <= intensity_ratio
                            <= iconfig.paper_max_ratio
                            else "extended_diagnostic"
                        ),
                        "fidelity_convention": convention,
                        "infidelity_raw": metrics["infidelity"],
                        "max_leakage_raw": metrics["max_leakage"],
                        "cz_phase_error": metrics["cz_phase_error"],
                        "local_z_phase": metrics["local_z_phase"],
                        "fixed_nominal_virtual_z": nominal_phase,
                    }
                )
    write_csv(run_dir / "data" / "fig4_intensity_scaling.csv", rows)
    fits: list[dict[str, Any]] = []
    for label, _ in gates:
        for convention in FIDELITY_CONVENTIONS:
            floor = nominal_floors[label][convention]
            for direction, sign in (("negative", -1), ("positive", 1)):
                for lower, upper in iconfig.fit_windows:
                    selected = [
                        row
                        for row in rows
                        if row["gate"] == label
                        and row["fidelity_convention"] == convention
                        and np.sign(row["delta_intensity"]) == sign
                        and lower
                        <= abs(row["delta_intensity"])
                        <= upper
                    ]
                    delta = np.asarray(
                        [abs(row["delta_intensity"]) for row in selected]
                    )
                    excess = np.asarray(
                        [row["infidelity_raw"] - floor for row in selected]
                    )
                    valid = excess > max(abs(floor) * 10.0, 1e-15)
                    if np.count_nonzero(valid) >= 3:
                        slope, intercept = np.polyfit(
                            np.log(delta[valid]), np.log(excess[valid]), 1
                        )
                        exponent = float(slope)
                        prefactor = float(np.exp(intercept))
                    else:
                        exponent = np.nan
                        prefactor = np.nan
                    fits.append(
                        {
                            "provenance": PROVENANCE["equivalent"],
                            "gate": label,
                            "fidelity_convention": convention,
                            "direction": direction,
                            "fit_lower": lower,
                            "fit_upper": upper,
                            "nominal_numerical_floor": floor,
                            "model": "excess_infidelity=A*|delta_I|^p",
                            "exponent": exponent,
                            "prefactor": prefactor,
                            "points_used": int(np.count_nonzero(valid)),
                        }
                    )
    write_csv(run_dir / "data" / "fig4_intensity_fit_windows.csv", fits)

    def fit_summary(gate: str, convention: str) -> dict[str, Any]:
        selected = [
            row
            for row in fits
            if row["gate"] == gate
            and row["fidelity_convention"] == convention
            and np.isfinite(row["exponent"])
        ]
        by_direction = {}
        for direction in ("negative", "positive"):
            values = [
                row["exponent"]
                for row in selected
                if row["direction"] == direction
            ]
            by_direction[direction] = {
                "median_exponent": float(np.median(values)) if values else np.nan,
                "window_spread": (
                    float(max(values) - min(values)) if values else np.nan
                ),
                "exponents": values,
            }
        return by_direction

    summaries = {
        label: {
            convention: fit_summary(label, convention)
            for convention in FIDELITY_CONVENTIONS
        }
        for label, _ in gates
    }
    figure, axis = plt.subplots(figsize=(6.5, 4.4))
    for label, color in (
        ("AR equivalent reoptimization", "#c43b3b"),
        ("same-duration non-robust surrogate", "#315a9a"),
    ):
        selected = [
            row
            for row in rows
            if row["gate"] == label
            and row["fidelity_convention"] == "pointwise_cz_equivalent"
            and row["delta_intensity"] != 0.0
            and row["infidelity_raw"] > 0.0
        ]
        axis.loglog(
            [abs(row["delta_intensity"]) for row in selected],
            [row["infidelity_raw"] for row in selected],
            "o",
            ms=3.5,
            color=color,
            label=label,
        )
    axis.set(
        xlabel="|ΔI/I₀|",
        ylabel="Pointwise CZ-equivalent infidelity",
        title="Equivalent AR vs same-duration non-robust surrogate",
    )
    axis.legend(frameon=False)
    axis.grid(True, which="both", alpha=0.2)
    figure.tight_layout()
    plot_path = run_dir / "figs" / "fig4_theory_intensity_scaling.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)
    summary = {
        "provenance": PROVENANCE["equivalent"],
        "intensity_amplitude_relation": "Omega/Omega0=sqrt(I/I0)",
        "paper_range": [
            iconfig.paper_min_ratio,
            iconfig.paper_max_ratio,
        ],
        "extended_diagnostic_range": [
            iconfig.diagnostic_min_ratio,
            iconfig.diagnostic_max_ratio,
        ],
        "gate_label_warning": (
            "The comparator is a same-duration non-robust surrogate, not the "
            "paper's time-optimal gate and not quantitatively identified with it."
        ),
        "fidelity_conventions": {
            "fixed_standard_cz": "fixed diag(1,1,1,-1) target",
            "fixed_nominal_virtual_z": (
                "one symmetric virtual-Z phase determined at I/I0=1 and "
                "held fixed for the entire scan"
            ),
            "pointwise_cz_equivalent": (
                "a separately removed symmetric local-Z at every intensity; "
                "this is an echoed/CZ-equivalent metric, not an ordinary "
                "uncalibrated CZ fidelity"
            ),
        },
        "nominal_virtual_z": nominal_phases,
        "nominal_numerical_floors": nominal_floors,
        "fit_window_summaries": summaries,
        "plot": str(plot_path),
    }
    ar_echoed = summaries["AR equivalent reoptimization"][
        "pointwise_cz_equivalent"
    ]
    nr_echoed = summaries["same-duration non-robust surrogate"][
        "pointwise_cz_equivalent"
    ]
    summary["acceptance"] = {
        "nonrobust_quadratic_both_directions": bool(
            all(
                1.7 <= nr_echoed[direction]["median_exponent"] <= 2.3
                and nr_echoed[direction]["window_spread"] <= 0.5
                for direction in ("negative", "positive")
            )
        ),
        "ar_echoed_quartic_both_directions": bool(
            all(
                3.5 <= ar_echoed[direction]["median_exponent"] <= 4.5
                and ar_echoed[direction]["window_spread"] <= 0.75
                for direction in ("negative", "positive")
            )
        ),
        "fixed_z_reported_without_forced_exponent": True,
    }
    summary["acceptance"]["all"] = bool(all(summary["acceptance"].values()))
    write_json(run_dir / "data" / "fig4_intensity_scaling_summary.json", summary)
    return summary



def aom_plant(
    command: Array,
    bin_width_us: float,
    config: AOMConfig,
) -> Array:
    """Synthetic linear AOM plant; every parameter is an assumed value."""
    cutoff = 2.0 * np.pi * config.bandwidth_mhz
    continuous_a = np.asarray(
        [[0.0, 1.0], [-cutoff**2, -2.0 * config.damping_ratio * cutoff]]
    )
    continuous_b = np.asarray([[0.0], [cutoff**2]])
    continuous_c = np.asarray([[1.0, 0.0]])
    continuous_d = np.asarray([[0.0]])
    ad, bd, cd, dd, _ = signal.cont2discrete(
        (continuous_a, continuous_b, continuous_c, continuous_d),
        bin_width_us,
        method="zoh",
    )

    def filter_quadrature(values: Array) -> Array:
        state = np.zeros(2, dtype=float)
        output = np.empty_like(values, dtype=float)
        for index, value in enumerate(values):
            output[index] = float((cd @ state + dd.ravel() * value).item())
            state = ad @ state + bd.ravel() * value
        return output

    raw = filter_quadrature(command.real) + 1j * filter_quadrature(command.imag)
    centers = (np.arange(len(command)) + 0.5) * bin_width_us
    delayed = np.interp(
        centers - config.delay_us,
        centers,
        raw.real,
        left=0.0,
        right=raw.real[-1],
    ) + 1j * np.interp(
        centers - config.delay_us,
        centers,
        raw.imag,
        left=0.0,
        right=raw.imag[-1],
    )
    imbalanced = (1.0 + config.iq_imbalance) * delayed.real + 1j * (
        1.0 - config.iq_imbalance
    ) * delayed.imag
    strengths = {
        "small": config.distortion_strength_small,
        "paper_scale": config.distortion_strength_paper_scale,
        "stress": config.distortion_strength_stress,
    }
    strength = strengths[config.case]
    # Scaling the declared synthetic plant imperfection changes the actual
    # serialized output as well as its inferred Hessian coordinates.
    return command + strength * (imbalanced - command)


def additive_output_coefficients(
    output: Array,
    ideal: Array,
    envelope: Array,
    bin_width_us: float,
    ridge_fraction: float,
    omega0: float,
) -> tuple[Array, Array]:
    """Ridge-project additive output error into tapered paper lab-I/Q bins.

    This deliberately avoids pointwise division by the ideal command.  Edge
    ringing outside the tapered subspace is retained in ``residual``.
    """
    delta = np.asarray(output) - np.asarray(ideal)
    taper = np.asarray(envelope, dtype=float)
    ridge = ridge_fraction * omega0**2
    denominator = taper**2 + ridge
    sx = taper * delta.real / denominator
    sy = taper * delta.imag / denominator
    represented = taper * (sx + 1j * sy)
    residual = delta - represented
    normalization = math.sqrt(bin_width_us)
    return np.concatenate([sx, sy]) * normalization, residual


def command_from_mode_coefficients(
    ideal: Array,
    envelope: Array,
    coefficients: Array,
    bin_width_us: float,
) -> Array:
    n_bins = len(ideal)
    normalization = math.sqrt(bin_width_us)
    sx = coefficients[:n_bins] / normalization
    sy = coefficients[n_bins:] / normalization
    return ideal + envelope * (sx + 1j * sy)


def validate_synthetic_waveform_archive(
    path: Path,
    model: Model,
    config: AOMConfig,
    tolerance: float = 1e-12,
) -> dict[str, float | bool]:
    """Verify that serialized command/output/distortion arrays agree.

    This is deliberately performed after writing the archive so a stale or
    mismatched representation cannot silently become Figure 4(a) evidence.
    """
    with np.load(path) as archive:
        centers = np.asarray(archive["bin_centers_us"], dtype=float)
        ideal = np.asarray(archive["ideal"], dtype=np.complex128)
        before_command = np.asarray(archive["command"], dtype=np.complex128)
        before_output = np.asarray(
            archive["before_output"], dtype=np.complex128
        )
        after_command = np.asarray(
            archive["after_command"], dtype=np.complex128
        )
        after_output = np.asarray(
            archive["after_output"], dtype=np.complex128
        )
        before_coefficients = np.asarray(
            archive["before_output_distortion_coefficients"], dtype=float
        )
        remaining_coefficients = np.asarray(
            archive["remaining_output_distortion_coefficients"], dtype=float
        )
        before_residual = np.asarray(
            archive["before_unrepresented_additive_residual"],
            dtype=np.complex128,
        )
        after_residual = np.asarray(
            archive["after_unrepresented_additive_residual"],
            dtype=np.complex128,
        )
    if len(centers) < 2:
        raise ValueError("synthetic archive requires at least two time bins")
    bin_width = float(centers[1] - centers[0])
    normalization = math.sqrt(bin_width)
    envelope = np.abs(ideal)

    def reconstruct(coefficients: Array, residual: Array) -> Array:
        count = len(ideal)
        return (
            ideal
            + envelope
            * (
                coefficients[:count] / normalization
                + 1j * coefficients[count:] / normalization
            )
            + residual
        )

    residuals = {
        "before_plant_residual": float(
            np.linalg.norm(
                before_output - aom_plant(before_command, bin_width, config)
            )
        ),
        "after_plant_residual": float(
            np.linalg.norm(
                after_output - aom_plant(after_command, bin_width, config)
            )
        ),
        "before_additive_reconstruction_residual": float(
            np.linalg.norm(
                before_output
                - reconstruct(before_coefficients, before_residual)
            )
        ),
        "after_additive_reconstruction_residual": float(
            np.linalg.norm(
                after_output
                - reconstruct(remaining_coefficients, after_residual)
            )
        ),
    }
    scale = max(
        np.linalg.norm(before_output),
        np.linalg.norm(after_output),
        model.omega0,
    )
    residuals["relative_tolerance"] = tolerance
    residuals["all"] = bool(
        all(
            residuals[name] <= tolerance * scale
            for name in (
                "before_plant_residual",
                "after_plant_residual",
                "before_additive_reconstruction_residual",
                "after_additive_reconstruction_residual",
            )
        )
    )
    if not residuals["all"]:
        raise RuntimeError(
            f"inconsistent synthetic waveform archive {path}: {residuals}"
        )
    return residuals


def synthetic_closed_loop_analysis(
    run_dir: Path, config: RunConfig | None = None
) -> dict:
    """Plant-in-loop synthetic Fig. 4(a,b) demonstration.

    Scan ranges use only theoretical curvature, hardware bounds, prior fit
    uncertainty, and measurement statistics.  The hidden plant distortion is
    never used to center or size a scan.
    """
    config = config or RunConfig()
    basis = make_basis(config)
    variables = load_waveform_variables(
        run_dir / "data" / "robust_waveform.npz", expected_config=config
    )
    hessian_path = run_dir / "data" / "fig3_hessian_modes.npz"
    if not hessian_path.exists():
        raise FileNotFoundError(
            f"{hessian_path} is required; run --stage hessian first"
        )
    with np.load(hessian_path) as archive:
        cached_hash = str(archive["config_hash"].item())
        if cached_hash != config_hash(config):
            raise RuntimeError("Hessian cache/config hash mismatch")
        cached_code = str(archive["code_version"].item())
        if cached_code != code_version():
            raise RuntimeError("Hessian cache/code-version mismatch")
        hessian = np.asarray(archive["hessian"], dtype=float)
        eigenvalues = np.asarray(archive["eigenvalues"], dtype=float)
        eigenvectors = np.asarray(archive["eigenvectors"], dtype=float)
        centers = np.asarray(archive["bin_centers_us"], dtype=float)
    n_bins = len(centers)
    bin_width = basis.model.duration / n_bins
    _, _, ideal = basis.values_numpy(variables, centers)
    envelope = np.abs(ideal)
    ideal_unitary = propagate_piecewise_numpy(
        np.linspace(0.0, basis.model.duration, n_bins + 1),
        ideal,
        basis.model,
    )
    aconfig = config.aom

    def evaluate_command(command_coefficients: Array) -> dict[str, Any]:
        command = command_from_mode_coefficients(
            ideal, envelope, command_coefficients, bin_width
        )
        output = aom_plant(command, bin_width, aconfig)
        output_coefficients, residual = additive_output_coefficients(
            output,
            ideal,
            envelope,
            bin_width,
            aconfig.ridge_projection,
            basis.model.omega0,
        )
        output_unitary = propagate_piecewise_numpy(
            np.linspace(0.0, basis.model.duration, n_bins + 1),
            output,
            basis.model,
        )
        full_error = 1.0 - fixed_target_fidelity(
            output_unitary, ideal_unitary
        )
        quadratic = float(
            0.5 * output_coefficients @ hessian @ output_coefficients
        )
        return {
            "command": command,
            "output": output,
            "output_coefficients": output_coefficients,
            "unrepresented_additive_residual": residual,
            "full_schrodinger_infidelity_raw": full_error,
            "quadratic_hessian_infidelity_raw": quadratic,
        }

    principal = eigenvectors[:, :10]
    correction = np.zeros(2 * n_bins)
    initial = evaluate_command(correction)
    rng = np.random.default_rng(aconfig.random_seed)
    scan_rows: list[dict[str, Any]] = []
    cycle_rows: list[dict[str, Any]] = []
    span_state: dict[int, float] = {}

    def measure(error: float) -> tuple[float, float, int]:
        probability = aconfig.irreducible_baseline + error
        if probability < 0.0 or probability > 1.0:
            raise FloatingPointError(
                f"synthetic measurement probability {probability} is invalid"
            )
        failures = int(rng.binomial(aconfig.shots, probability))
        estimate = (failures + 0.5) / (aconfig.shots + 1.0)
        variance = (
            estimate * (1.0 - estimate) / (aconfig.shots + 2.0)
        )
        return float(estimate), float(math.sqrt(variance)), failures

    def append_cycle(cycle: int, result: dict[str, Any]) -> None:
        observed, sigma, failures = measure(
            result["full_schrodinger_infidelity_raw"]
        )
        cycle_rows.append(
            {
                "provenance": PROVENANCE["synthetic"],
                "cycle": cycle,
                "quadratic_hessian_infidelity_raw": result[
                    "quadratic_hessian_infidelity_raw"
                ],
                "full_schrodinger_infidelity_raw": result[
                    "full_schrodinger_infidelity_raw"
                ],
                "irreducible_baseline": aconfig.irreducible_baseline,
                "synthetic_observed_total_error": observed,
                "synthetic_uncertainty": sigma,
                "failures": failures,
                "shots": aconfig.shots,
            }
        )

    append_cycle(0, initial)
    for cycle in range(1, aconfig.cycles + 1):
        for mode_index in range(10):
            mode = principal[:, mode_index]
            current_coefficient = float(mode @ correction)
            if mode_index not in span_state:
                approximate_sigma = math.sqrt(
                    max(
                        aconfig.irreducible_baseline
                        * (1.0 - aconfig.irreducible_baseline)
                        / aconfig.shots,
                        1e-16,
                    )
                )
                curvature = max(eigenvalues[mode_index], 1e-12)
                span_state[mode_index] = min(
                    aconfig.scan_hardware_bound,
                    max(math.sqrt(12.0 * approximate_sigma / curvature), 0.002),
                )
            span = span_state[mode_index]
            best_fit: tuple[float, Array, float] | None = None
            final_expansion_row_indices: list[int] = []
            for expansion in range(3):
                lower = max(
                    -aconfig.scan_hardware_bound, current_coefficient - span
                )
                upper = min(
                    aconfig.scan_hardware_bound, current_coefficient + span
                )
                trials = np.linspace(lower, upper, aconfig.scan_points)
                observed_values = []
                sigmas = []
                expansion_row_indices = []
                for trial in trials:
                    candidate = correction + (
                        trial - current_coefficient
                    ) * mode
                    result = evaluate_command(candidate)
                    observed, sigma, failures = measure(
                        result["full_schrodinger_infidelity_raw"]
                    )
                    observed_values.append(observed)
                    sigmas.append(sigma)
                    scan_rows.append(
                        {
                            "provenance": PROVENANCE["synthetic"],
                            "cycle": cycle,
                            "mode": mode_index + 1,
                            "expansion": expansion,
                            "scan_coefficient": trial,
                            "quadratic_hessian_infidelity_raw": result[
                                "quadratic_hessian_infidelity_raw"
                            ],
                            "full_schrodinger_infidelity_raw": result[
                                "full_schrodinger_infidelity_raw"
                            ],
                            "synthetic_observed_total_error": observed,
                            "synthetic_uncertainty": sigma,
                            "failures": failures,
                            "shots": aconfig.shots,
                            "selected_optimum": False,
                        }
                    )
                    expansion_row_indices.append(len(scan_rows) - 1)
                try:
                    polynomial, covariance = np.polyfit(
                        trials,
                        observed_values,
                        2,
                        w=1.0 / np.asarray(sigmas),
                        cov=True,
                    )
                except (ValueError, np.linalg.LinAlgError):
                    polynomial = np.polyfit(trials, observed_values, 2)
                    covariance = np.full((3, 3), np.nan)
                if polynomial[0] > 0.0:
                    fitted = float(
                        -polynomial[1] / (2.0 * polynomial[0])
                    )
                else:
                    fitted = float(trials[int(np.argmin(observed_values))])
                fitted_clipped = float(np.clip(fitted, lower, upper))
                at_edge = (
                    int(np.argmin(observed_values)) in (0, len(trials) - 1)
                    or fitted <= lower
                    or fitted >= upper
                )
                fitted_minimum = float(
                    np.polyval(polynomial, fitted_clipped)
                )
                best_fit = (fitted_clipped, covariance, fitted_minimum)
                final_expansion_row_indices = expansion_row_indices
                if (
                    not at_edge
                    or span >= aconfig.scan_hardware_bound
                    or expansion == 2
                ):
                    break
                span = min(2.0 * span, aconfig.scan_hardware_bound)
            assert best_fit is not None
            fitted, covariance, fitted_intercept = best_fit
            correction += (fitted - current_coefficient) * mode
            coefficient_sigma = (
                float(
                    math.sqrt(
                        max(
                            np.asarray(
                                [
                                    polynomial[1]
                                    / (2.0 * polynomial[0] ** 2),
                                    -1.0 / (2.0 * polynomial[0]),
                                    0.0,
                                ]
                            )
                            @ covariance
                            @ np.asarray(
                                [
                                    polynomial[1]
                                    / (2.0 * polynomial[0] ** 2),
                                    -1.0 / (2.0 * polynomial[0]),
                                    0.0,
                                ]
                            ),
                            0.0,
                        )
                    )
                )
                if polynomial[0] > 0.0
                and np.all(np.isfinite(covariance))
                else span / 2.0
            )
            span_state[mode_index] = min(
                aconfig.scan_hardware_bound,
                max(2.5 * coefficient_sigma, span / 3.0, 0.001),
            )
            selected_row_index = min(
                final_expansion_row_indices,
                key=lambda row_index: abs(
                    float(scan_rows[row_index]["scan_coefficient"]) - fitted
                ),
            )
            scan_rows[selected_row_index]["selected_optimum"] = True
            for row_index in final_expansion_row_indices:
                scan_rows[row_index]["fitted_optimum"] = fitted
                scan_rows[row_index][
                    "fitted_optimum_sigma"
                ] = coefficient_sigma
                scan_rows[row_index][
                    "fitted_minimum_raw"
                ] = fitted_intercept
                scan_rows[row_index][
                    "fitted_minimum_is_negative"
                ] = bool(fitted_intercept < 0.0)
        append_cycle(cycle, evaluate_command(correction))

    final = evaluate_command(correction)
    principal_projector = principal @ principal.T
    remaining_principal = (
        principal_projector @ final["output_coefficients"]
    )
    remaining_null = (
        final["output_coefficients"] - remaining_principal
    )
    write_csv(run_dir / "data" / "fig4_synthetic_scans.csv", scan_rows)
    write_csv(run_dir / "data" / "fig4_synthetic_cycles.csv", cycle_rows)
    np.savez_compressed(
        run_dir / "data" / "fig4_synthetic_aom.npz",
        bin_centers_us=centers,
        ideal=ideal,
        command=initial["command"],
        before_output=initial["output"],
        after_command=final["command"],
        after_output=final["output"],
        principal_correction_command_coefficients=correction,
        before_output_distortion_coefficients=initial["output_coefficients"],
        remaining_output_distortion_coefficients=final["output_coefficients"],
        remaining_principal_space_distortion_coefficients=remaining_principal,
        remaining_null_space_distortion_coefficients=remaining_null,
        before_unrepresented_additive_residual=initial[
            "unrepresented_additive_residual"
        ],
        after_unrepresented_additive_residual=final[
            "unrepresented_additive_residual"
        ],
        config_hash=config_hash(config),
        code_version=code_version(),
        provenance=PROVENANCE["synthetic"],
    )
    serialization = validate_synthetic_waveform_archive(
        run_dir / "data" / "fig4_synthetic_aom.npz",
        basis.model,
        aconfig,
    )

    figure, axes = plt.subplots(2, 2, figsize=(11.0, 7.5))
    for values, label, color in (
        (ideal, "Ideal", "#222222"),
        (initial["output"], "Before output", "#c43b3b"),
        (final["output"], "After output", "#315a9a"),
    ):
        axes[0, 0].plot(centers, abs(values) / basis.model.omega0, label=label, color=color)
        axes[1, 0].plot(
            centers,
            np.unwrap(np.angle(values)) / (2.0 * np.pi),
            label=label,
            color=color,
        )
    axes[0, 0].set(
        ylabel="Amplitude / Ω₀",
        title="Synthetic AOM waveforms (not measured data)",
    )
    axes[1, 0].set(xlabel="Time (μs)", ylabel="Unwrapped phase / 2π")
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 1].semilogy(
        [row["cycle"] for row in cycle_rows],
        [row["quadratic_hessian_infidelity_raw"] for row in cycle_rows],
        "o-",
        label="quadratic Hessian prediction",
    )
    axes[0, 1].semilogy(
        [row["cycle"] for row in cycle_rows],
        [row["full_schrodinger_infidelity_raw"] for row in cycle_rows],
        "s-",
        label="full Schrödinger propagation",
    )
    axes[0, 1].set(xlabel="Cycle", ylabel="Closed-system infidelity")
    axes[0, 1].legend(frameon=False, fontsize=8)
    representative = [
        row
        for row in scan_rows
        if row["cycle"] == 1 and row["mode"] in (1, 5, 10)
        and row["expansion"] == 0
    ]
    for mode_index in (1, 5, 10):
        selected_rows = [
            row for row in representative if row["mode"] == mode_index
        ]
        axes[1, 1].errorbar(
            [row["scan_coefficient"] for row in selected_rows],
            [row["synthetic_observed_total_error"] for row in selected_rows],
            yerr=[row["synthetic_uncertainty"] for row in selected_rows],
            fmt="o-",
            ms=3,
            label=f"mode {mode_index}",
        )
    axes[1, 1].set(
        xlabel="Mode coefficient",
        ylabel="Synthetic measured total error",
        title="Synthetic weighted scans",
    )
    axes[1, 1].legend(frameon=False, fontsize=8)
    figure.tight_layout()
    plot_path = run_dir / "figs" / "fig4_synthetic_closed_loop.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)

    relative_disagreement = [
        abs(
            row["full_schrodinger_infidelity_raw"]
            - row["quadratic_hessian_infidelity_raw"]
        )
        / max(abs(row["full_schrodinger_infidelity_raw"]), 1e-15)
        for row in cycle_rows
    ]
    result = {
        "provenance": PROVENANCE["synthetic"],
        "algorithm": "synthetic plant-in-loop Hessian calibration",
        "aom_parameters": {
            **asdict(aconfig),
            "status": "all are assumed synthetic values",
        },
        "initial_quadratic_infidelity_raw": initial[
            "quadratic_hessian_infidelity_raw"
        ],
        "initial_full_schrodinger_infidelity_raw": initial[
            "full_schrodinger_infidelity_raw"
        ],
        "final_quadratic_infidelity_raw": final[
            "quadratic_hessian_infidelity_raw"
        ],
        "final_full_schrodinger_infidelity_raw": final[
            "full_schrodinger_infidelity_raw"
        ],
        "remaining_principal_space_distortion_norm": float(
            np.linalg.norm(remaining_principal)
        ),
        "remaining_null_space_distortion_norm": float(
            np.linalg.norm(remaining_null)
        ),
        "quadratic_full_relative_disagreement_by_cycle": relative_disagreement,
        "measurement_model": (
            "shot-count binomial failures with Jeffreys posterior mean and "
            "heteroskedastic uncertainty; weighted quadratic fits"
        ),
        "scan_range_rule": (
            "theory curvature + shot noise + hardware bounds initially; prior "
            "fit uncertainty thereafter; edge minima trigger bounded expansion"
        ),
        "oracle_information_used": False,
        "serialization_consistency": serialization,
        "irreducible_baseline": aconfig.irreducible_baseline,
        "plot": str(plot_path),
        "warning": (
            "No point is experimental and no synthetic point is overlaid as a "
            "paper measurement."
        ),
    }
    result["acceptance"] = {
        "serialization_consistent": bool(serialization["all"]),
        "oracle_free_scan_rule": True,
        "full_schrodinger_error_reduced": bool(
            final["full_schrodinger_infidelity_raw"]
            < initial["full_schrodinger_infidelity_raw"]
        ),
        "quadratic_and_full_curves_both_saved": True,
    }
    result["acceptance"]["all"] = bool(
        all(result["acceptance"].values())
    )
    write_json(run_dir / "data" / "fig4_synthetic_summary.json", result)
    return result


def write_experimental_contract(run_dir: Path) -> dict:
    analysis_script = Path(__file__).with_name(
        "liu_2026_experimental_analysis.py"
    ).resolve()
    input_manifest = Path(__file__).with_name("input.in").resolve()
    if not analysis_script.exists():
        raise FileNotFoundError(
            f"declared experimental analysis script is missing: {analysis_script}"
        )
    if not input_manifest.exists():
        raise FileNotFoundError(
            f"declared experimental input manifest is missing: {input_manifest}"
        )
    contracts = {
        "Fig2a_two_image_state_assignment": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 2(a)",
            "pipeline_panel": "fig2a_imaging",
            "required_columns": [
                "shot_id",
                "prepared_state",
                "first_image_photon_count",
                "second_image_photon_count",
                "state_assignment",
                "loss_assignment",
            ],
        },
        "Fig2b_single_qubit_rb": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 2(b)",
            "pipeline_panel": "fig2b_single_qubit_rb",
            "required_columns": [
                "rb_depth",
                "sequence_id",
                "shot_id",
                "success",
                "survival",
                "postselection_flag",
            ],
        },
        "Fig3d_mode_sensitivity": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 3(d)",
            "pipeline_panel": "fig3d_mode_sensitivity",
            "required_columns": [
                "mode",
                "coefficient",
                "rb_fidelity_or_error",
                "uncertainty",
                "theory_sensitivity",
            ],
        },
        "Fig3e_channel_decomposition": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 3(e)",
            "pipeline_panel": "fig3e_channel_decomposition",
            "required_columns": [
                "mode",
                "coefficient",
                "initial_computational_state",
                "leakage_channel",
                "measured_leakage",
                "leakage_uncertainty",
                "ramsey_phase",
                "ramsey_phase_uncertainty",
            ],
        },
        "Fig4a_measured_waveforms": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 4(a)",
            "pipeline_panel": "fig4a_waveforms",
            "required_columns": [
                "time_us",
                "ideal_amplitude",
                "before_amplitude",
                "after_amplitude",
                "ideal_intensity",
                "before_intensity",
                "after_intensity",
                "wrapped_phase",
                "unwrapped_phase",
                "measurement_uncertainty",
            ],
        },
        "Fig4b_closed_loop_scans": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 4(b)",
            "pipeline_panel": "fig4b_closed_loop",
            "required_columns": [
                "cycle",
                "mode",
                "scan_coefficient",
                "gate_error",
                "uncertainty",
                "selected_optimum",
            ],
        },
        "Fig4c_echoed_rb": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 4(c)",
            "pipeline_panel": "fig4c_echoed_rb",
            "required_columns": [
                "rb_circuit_depth",
                "sequence_id",
                "shot_id",
                "success",
                "loss",
                "postselection_flag",
            ],
        },
        "Fig4d_intensity": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 4(d)",
            "pipeline_panel": "fig4d_intensity",
            "required_columns": [
                "gate_type",
                "intensity_ratio",
                "gate_error",
                "uncertainty",
                "fidelity_convention",
            ],
        },
        "Fig4e_stability": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 4(e)",
            "pipeline_panel": "fig4e_stability",
            "required_columns": [
                "elapsed_time",
                "gate_error",
                "uncertainty",
                "calibration_or_reoptimization_event",
            ],
        },
        "Fig4f_error_budget": {
            "status": PROVENANCE["unavailable"],
            "panel": "Figure 4(f)",
            "pipeline_panel": "fig4f_error_budget",
            "required_columns": [
                "noise_source",
                "raw_contribution",
                "postselected_contribution",
                "uncertainty",
                "parameter_source",
            ],
        },
    }
    microscopic_input_contracts = {
        "pulse_waveform": [
            "time_us",
            "amplitude_rad_per_us",
            "phase_rad",
        ],
        "zeeman_calibration": [
            "state_label",
            "field_gauss",
            "shift_mhz",
            "uncertainty_mhz",
        ],
        "polarization_calibration": [
            "beam_id",
            "component",
            "relative_amplitude",
            "phase_rad",
            "uncertainty",
        ],
        "mqdt_pair_states": [
            "distance_um",
            "pair_state_id",
            "energy_mhz",
            "product_state",
            "overlap_real",
            "overlap_imag",
        ],
        "distance_samples": [
            "sample_id",
            "distance_um",
            "polar_angle_rad",
            "azimuth_rad",
        ],
        "decay_branching": [
            "initial_state",
            "final_state",
            "rate_per_us",
        ],
        "laser_phase_noise_psd": [
            "frequency_mhz",
            "psd_rad2_per_mhz",
        ],
        "laser_amplitude_noise_psd": [
            "frequency_mhz",
            "psd_fraction2_per_mhz",
        ],
    }
    result = {
        "provenance": PROVENANCE["unavailable"],
        "raw_data_supplied": False,
        "synthetic_points_generated_for_experimental_panels": False,
        "contracts": contracts,
        "microscopic_input_contracts": microscopic_input_contracts,
        "microscopic_input_note": (
            "schema-v2 input.in validates and audits these inputs; the current "
            "ten-state Hessian does not silently consume them"
        ),
        "analysis_script": str(analysis_script),
        "analysis_script_exists": True,
        "input_manifest": str(input_manifest),
        "input_manifest_exists": True,
        "usage": (
            f"{analysis_script} --panel <pipeline_panel> --input <csv> "
            "--output <json>"
        ),
        "input_manifest_usage": (
            f"{analysis_script} --input-in {input_manifest} "
            "--output-dir <run_dir>/data/input_manifest_analysis"
        ),
    }
    write_json(run_dir / "data" / "experimental_data_contract.json", result)
    return result


def run_experimental_input_manifest(
    run_dir: Path,
    manifest_path: Path,
    theory_run_dir: Path | None = None,
) -> dict:
    """Run the separate raw-data pipeline through the user-editable input.in."""
    analysis_script = Path(__file__).with_name(
        "liu_2026_experimental_analysis.py"
    ).resolve()
    manifest_path = manifest_path.resolve()
    if not analysis_script.exists():
        raise FileNotFoundError(
            f"experimental analysis script missing: {analysis_script}"
        )
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"input.in does not exist: {manifest_path}. Supply --input-in."
        )
    output_dir = run_dir / "data" / "input_manifest_analysis"
    plot_dir = run_dir / "figs" / "input_manifest_analysis"
    command = [
        sys.executable,
        str(analysis_script),
        "--input-in",
        str(manifest_path),
        "--output-dir",
        str(output_dir),
        "--plot-dir",
        str(plot_dir),
    ]
    if theory_run_dir is not None:
        theory_run_dir = theory_run_dir.resolve()
        if not theory_run_dir.exists():
            raise FileNotFoundError(
                f"theory run for grouped Figure 3 does not exist: "
                f"{theory_run_dir}"
            )
        command.extend(["--theory-run-dir", str(theory_run_dir)])
    subprocess.run(command, check=True)
    summary_path = output_dir / "manifest_summary.json"
    with summary_path.open(encoding="utf-8") as handle:
        summary = json.load(handle)
    summary["analysis_script"] = str(analysis_script)
    summary["analysis_script_exists"] = True
    summary["plot_dir"] = str(plot_dir.resolve())
    write_json(run_dir / "data" / "input_manifest_summary.json", summary)
    return summary


def reported_error_budget(run_dir: Path) -> dict:
    """Replot only numerical contributions stated explicitly in the paper."""
    noise_module = Path(__file__).with_name(
        "liu_2026_noise_modules.py"
    ).resolve()
    if not noise_module.exists():
        raise FileNotFoundError(
            f"declared optional noise module is missing: {noise_module}"
        )
    contributions = [
        ("Rydberg decay", 3.1e-3, 1.2e-4, "T_r=42(2) μs"),
        ("Doppler", 3.7e-4, 2.8e-4, "T=2.7 μK"),
        (
            "Finite blockade",
            1.6e-4,
            3.0e-5,
            "R=2.0 μm; MQDT inputs unavailable",
        ),
        (
            "Distance variation",
            1.5e-4,
            8.0e-5,
            "T=2.7 μK; trap distribution unavailable",
        ),
        (
            "Laser phase noise",
            1.4e-4,
            1.0e-4,
            "noise spectrum unavailable",
        ),
        (
            "Laser amplitude noise",
            1.0e-5,
            np.nan,
            "postselected value and noise spectrum unavailable",
        ),
    ]
    rows = [
        {
            "source": name,
            "reported_raw_infidelity": raw,
            "reported_postselected_infidelity": postselected,
            "explicit_parameter_or_limitation": note,
            "source_location": "Liu et al. arXiv:2606.05060v1 Appendix E",
            "provenance": PROVENANCE["reported"],
        }
        for name, raw, postselected, note in contributions
    ]
    write_csv(run_dir / "data" / "fig4f_reported_error_budget.csv", rows)
    names = [row[0] for row in contributions]
    raw = np.asarray([row[1] for row in contributions])
    postselected = np.asarray([row[2] for row in contributions])
    positions = np.arange(len(names))
    figure, axis = plt.subplots(figsize=(8.2, 4.5))
    width = 0.38
    axis.bar(
        positions - width / 2,
        raw,
        width,
        label="raw",
        color="#4477aa",
    )
    reported_mask = np.isfinite(postselected)
    axis.bar(
        positions[reported_mask] + width / 2,
        postselected[reported_mask],
        width,
        label="postselected",
        color="#cc6677",
    )
    for position in positions[~reported_mask]:
        axis.plot(
            position + width / 2,
            1.2e-5,
            marker="o",
            markerfacecolor="none",
            markeredgecolor="#cc6677",
        )
        axis.annotate(
            "not reported",
            (position + width / 2, 1.2e-5),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
            rotation=90,
        )
    axis.set_yscale("log")
    axis.set_xticks(positions, names, rotation=28, ha="right")
    axis.set_ylabel("Reported infidelity contribution")
    axis.set_title("Fig. 4(f): reported-value reconstruction only")
    axis.legend(frameon=False)
    figure.tight_layout()
    plot_path = run_dir / "figs" / "fig4f_reported_values.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)
    result = {
        "provenance": PROVENANCE["reported"],
        "classification_detail": (
            "literal transcription/replot, not an independent reproduction"
        ),
        "reported_total_raw": 4.0e-3,
        "reported_total_postselected": 6.6e-4,
        "listed_partial_sum_raw": float(np.sum(raw)),
        "listed_partial_sum_postselected": float(
            np.sum(postselected[reported_mask])
        ),
        "reported_minus_listed_raw": float(4.0e-3 - np.sum(raw)),
        "reported_minus_listed_postselected": float(
            6.6e-4 - np.sum(postselected[reported_mask])
        ),
        "sum_note": (
            "Reported totals and the sum of individually listed rounded "
            "contributions are kept separate; differences reflect rounding "
            "and/or contributions not individually tabulated."
        ),
        "independent_reproduction": PROVENANCE["unavailable"],
        "missing_inputs": [
            "published numerical pulse array",
            "MQDT pair-state Hamiltonians and overlaps versus distance",
            "trap-frequency/position distribution",
            "Rydberg decay branching ratios",
            "laser phase-noise spectrum",
            "laser amplitude-noise spectrum",
        ],
        "implemented_optional_module": str(noise_module),
        "implemented_optional_module_exists": True,
        "plot": str(plot_path),
    }
    write_json(run_dir / "data" / "fig4f_reported_summary.json", result)
    return result


def nullspace_smooth_saved_waveform(
    run_dir: Path,
    outer_iterations: int = 5,
    config: RunConfig | None = None,
) -> dict:
    """Reduce smoothness along the robust-root tangent space, then reproject."""
    config = config or RunConfig()
    basis = make_basis(config)
    kernels = JaxControlKernels(
        basis,
        nodes=config.optimizer.fine_nodes,
        optimizer_config=config.optimizer,
        numerical_tolerance=config.numerical_roundoff_tolerance,
    )
    path = run_dir / "data" / "robust_waveform.npz"
    current = load_waveform_variables(path, expected_config=config)
    lower, upper = np.asarray(basis.bounds(), dtype=float).T

    def residual(variables: Array) -> Array:
        return np.asarray(
            kernels.robust_residual(jnp.asarray(variables)), dtype=float
        )

    def jacobian(variables: Array) -> Array:
        return np.asarray(
            kernels.robust_residual_jacobian(jnp.asarray(variables)),
            dtype=float,
        )

    history = []
    initial_metrics = kernels.evaluate(current)
    for iteration in range(1, outer_iterations + 1):
        value, gradient = kernels.smoothness_value_grad(jnp.asarray(current))
        channel_jacobian = jacobian(current)
        _, singular_values, right = np.linalg.svd(
            channel_jacobian, full_matrices=True
        )
        rank = int(
            np.count_nonzero(
                singular_values
                > max(singular_values[0] * 1e-9, 1e-11)
            )
        )
        null_basis = right[rank:].T
        projected = null_basis @ (null_basis.T @ np.asarray(gradient))
        projected_norm = float(np.linalg.norm(projected))
        accepted = False
        best_candidate = current
        best_metrics = kernels.evaluate(current)
        if projected_norm > 0.0:
            direction = -projected / projected_norm
            for step in (0.10, 0.03, 0.01, 0.003):
                trial = np.clip(current + step * direction, lower, upper)
                root = optimize.least_squares(
                    residual,
                    trial,
                    jac=jacobian,
                    bounds=(lower, upper),
                    method="trf",
                    x_scale="jac",
                    ftol=1e-13,
                    xtol=1e-13,
                    gtol=1e-11,
                    max_nfev=120,
                )
                candidate_metrics = kernels.evaluate(root.x)
                if (
                    np.linalg.norm(residual(root.x)) <= 1e-7
                    and candidate_metrics["infidelity"] <= 1e-8
                    and candidate_metrics["max_leakage"] <= 1e-8
                    and candidate_metrics["amplitude_curvature"] <= 1e-8
                    and candidate_metrics["smoothness"]
                    < best_metrics["smoothness"]
                ):
                    best_candidate = np.asarray(root.x)
                    best_metrics = candidate_metrics
                    accepted = True
        history.append(
            {
                "iteration": iteration,
                "channel_rank": rank,
                "null_dimension": int(null_basis.shape[1]),
                "projected_gradient_norm": projected_norm,
                "smoothness_before": float(value),
                "smoothness_after": best_metrics["smoothness"],
                "accepted": accepted,
            }
        )
        if not accepted:
            break
        current = best_candidate
    final_metrics = kernels.evaluate(current)
    if final_metrics["smoothness"] < initial_metrics["smoothness"]:
        save_waveform(
            path,
            basis,
            current,
            (
                "amplitude-robust CZ, "
                f"{config.optimizer.fine_nodes}-node polished and "
                "null-space smoothed"
            ),
            PROVENANCE["equivalent"],
            config,
            final_metrics,
        )
    summary = {
        "method": (
            "project the smoothness gradient into the null space of the "
            "branch-safe AR-root Jacobian, then reproject to the root"
        ),
        "initial_smoothness": initial_metrics["smoothness"],
        "final_smoothness": final_metrics["smoothness"],
        "improvement_factor": initial_metrics["smoothness"]
        / final_metrics["smoothness"],
        "final_metrics": final_metrics,
        "history": history,
    }
    write_json(run_dir / "data" / "robust_nullspace_smoothing.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=RUN_DEFAULT)
    parser.add_argument(
        "--config",
        type=Path,
        help="optional JSON override; the fully resolved configuration is saved",
    )
    parser.add_argument(
        "--input-in",
        type=Path,
        default=Path(__file__).with_name("input.in"),
        help="manifest for the experimental raw-data analysis stage",
    )
    parser.add_argument(
        "--theory-run-dir",
        type=Path,
        help="completed theory run used to assemble Figure 3(a-e)",
    )
    parser.add_argument("--mwe", action="store_true")
    parser.add_argument(
        "--all",
        action="store_true",
        help="run the complete accessible workflow and stop on any acceptance failure",
    )
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument("--quick", action="store_true")
    profiles.add_argument("--standard", action="store_true")
    profiles.add_argument("--convergence", action="store_true")
    parser.add_argument("--force-reoptimize", action="store_true")
    parser.add_argument(
        "--stage",
        choices=(
            "mwe",
            "optimize",
            "smooth",
            "hessian",
            "synthetic",
            "experimental",
            "reported-error-budget",
            "all",
        ),
        default="mwe",
    )
    return parser.parse_args()


def ensure_run_directories(run_dir: Path) -> None:
    for name in ("data", "figs", "logs"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)


def waveform_cache_matches(path: Path, config: RunConfig) -> bool:
    if not path.exists():
        return False
    try:
        with np.load(path) as archive:
            return (
                "config_hash" in archive
                and str(archive["config_hash"].item()) == config_hash(config)
                and "code_version" in archive
                and str(archive["code_version"].item()) == code_version()
            )
    except (OSError, ValueError, KeyError):
        return False


def require_stage_files(run_dir: Path, stage: str, names: Iterable[str]) -> None:
    missing = [
        str(run_dir / "data" / name)
        for name in names
        if not (run_dir / "data" / name).exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"stage {stage!r} is missing required inputs: {missing}"
        )


def main() -> None:
    args = parse_args()
    profile = (
        "convergence"
        if args.convergence
        else "standard"
        if args.standard
        else "quick"
    )
    config = load_config(args.config, profile)
    ensure_run_directories(args.run_dir)
    write_json(args.run_dir / "resolved_config.json", asdict(config))
    write_json(
        args.run_dir / "run_metadata.json",
        {
            "config_hash": config_hash(config),
            "code_version": code_version(),
            "profile": config.profile,
            "jax_available": JAX_AVAILABLE,
            "provenance_vocabulary": PROVENANCE,
        },
    )
    stage = "all" if args.all else args.stage
    if args.mwe or stage == "mwe":
        summary = mwe(args.run_dir, config)
        if not summary["acceptance"]["all"]:
            raise SystemExit("MWE acceptance failed")
        return
    if stage == "all":
        summary = mwe(args.run_dir, config)
        if not summary["acceptance"]["all"]:
            raise SystemExit("MWE acceptance failed")
        robust_path = args.run_dir / "data" / "robust_waveform.npz"
        nonrobust_path = args.run_dir / "data" / "nonrobust_waveform.npz"
        if (
            args.force_reoptimize
            or not waveform_cache_matches(robust_path, config)
            or not waveform_cache_matches(nonrobust_path, config)
        ):
            optimization = optimize_waveforms(args.run_dir, config)
        else:
            summary_path = args.run_dir / "data" / "optimization_summary.json"
            if not summary_path.exists():
                raise RuntimeError(
                    "compatible waveform caches exist but their acceptance "
                    "summary is missing"
                )
            with summary_path.open(encoding="utf-8") as handle:
                optimization = json.load(handle)
        if not optimization["acceptance"]["all"]:
            raise SystemExit(
                "Optimization acceptance failed; --all stops before figures"
            )
        basis = make_basis(config)
        variables = load_waveform_variables(
            robust_path, expected_config=config
        )
        plot_waveform_and_populations(
            args.run_dir,
            basis,
            variables,
            nodes=config.population_nodes,
            adaptive_max_step=(
                basis.model.duration * config.adaptive_max_step_fraction
            ),
        )
        hessian_summary = hessian_analysis(args.run_dir, config)
        if not hessian_summary["acceptance"]["all"]:
            raise SystemExit(
                "Hessian acceptance failed; --all stops before later panels"
            )
        scaling_summary = intensity_scaling_analysis(args.run_dir, config)
        if not scaling_summary["acceptance"]["all"]:
            raise SystemExit(
                "Intensity acceptance failed; --all stops before synthetic panels"
            )
        synthetic_summary = synthetic_closed_loop_analysis(
            args.run_dir, config
        )
        if not synthetic_summary["acceptance"]["all"]:
            raise SystemExit(
                "Synthetic calibration acceptance failed; --all stops"
            )
        write_experimental_contract(args.run_dir)
        reported_error_budget(args.run_dir)
        return
    if stage == "optimize":
        summary = optimize_waveforms(args.run_dir, config)
        if not summary["acceptance"]["all"]:
            raise SystemExit("Optimization acceptance failed")
        return
    if stage == "smooth":
        require_stage_files(
            args.run_dir, stage, ["robust_waveform.npz"]
        )
        nullspace_smooth_saved_waveform(args.run_dir, config=config)
        return
    if stage == "hessian":
        require_stage_files(
            args.run_dir,
            stage,
            ["robust_waveform.npz", "nonrobust_waveform.npz"],
        )
        basis = make_basis(config)
        variables = load_waveform_variables(
            args.run_dir / "data" / "robust_waveform.npz",
            expected_config=config,
        )
        plot_waveform_and_populations(
            args.run_dir,
            basis,
            variables,
            nodes=config.population_nodes,
            adaptive_max_step=(
                basis.model.duration * config.adaptive_max_step_fraction
            ),
        )
        hessian_summary = hessian_analysis(args.run_dir, config)
        scaling_summary = intensity_scaling_analysis(args.run_dir, config)
        if not hessian_summary["acceptance"]["all"]:
            raise SystemExit("Hessian acceptance failed")
        if not scaling_summary["acceptance"]["all"]:
            raise SystemExit("Intensity-scaling acceptance failed")
        return
    if stage == "synthetic":
        require_stage_files(
            args.run_dir,
            stage,
            ["robust_waveform.npz", "fig3_hessian_modes.npz"],
        )
        synthetic_summary = synthetic_closed_loop_analysis(
            args.run_dir, config
        )
        if not synthetic_summary["acceptance"]["all"]:
            raise SystemExit("Synthetic calibration acceptance failed")
        return
    if stage == "experimental":
        write_experimental_contract(args.run_dir)
        run_experimental_input_manifest(
            args.run_dir, args.input_in, args.theory_run_dir
        )
        return
    if stage == "reported-error-budget":
        reported_error_budget(args.run_dir)
        return
    raise SystemExit(
        f"Stage {stage!r} is not implemented."
    )


if __name__ == "__main__":
    main()
