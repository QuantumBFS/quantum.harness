#!/usr/bin/env python3
"""Reproduce Figure 1 of arXiv:2606.05060v1 with two numerical routes.

The run configuration is read only from the run directory's ``run.json``.
The primary route discretizes the paper's interaction-picture Hessian kernel.
The independent route propagates the full seven-state blockade Hilbert space
and measures directional curvatures by central finite differences.

Example:

    MPLCONFIGDIR=/tmp/liu-fig1-mpl .venv/bin/python \
      tracks/qcs/solutions/liu_2026_fig1_reproduction.py \
      --run-dir tracks/qcs/results/20260728-172915-liu-2026-fig1

Use ``--mwe`` for a fast 41-node acceptance test that writes no run results.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/liu-fig1-mpl")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
import scipy
from numpy.polynomial.chebyshev import chebval
from scipy import optimize
from scipy.integrate import solve_ivp
from scipy.interpolate import CubicSpline
from scipy.linalg import eigh


Array = np.ndarray
P_IDX = np.asarray([0, 1, 3, 5])
Q_IDX = np.asarray([2, 4, 6])
COLORS = {
    "purple": "#6857A8",
    "orange": "#E78A3B",
    "green": "#329A78",
    "blue": "#377EB8",
    "red": "#D95F5F",
    "gray": "#777777",
    "light": "#C8C8C8",
}


def progress(message: str) -> None:
    print(message, flush=True)


def load_run(run_dir: Path) -> dict:
    with (run_dir / "run.json").open(encoding="utf-8") as handle:
        run = json.load(handle)
    if run.get("status") not in {"approved", "complete"}:
        raise RuntimeError("run.json is not approved")
    return run


def write_json(path: Path, data: dict) -> None:
    def convert(value):
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
        raise TypeError(f"cannot serialize {type(value).__name__}")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=convert)
        handle.write("\n")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    keys = list(rows[0])
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


@dataclass(frozen=True)
class Pulse:
    amplitude_phase: float = 2.0 * np.pi * 0.1122
    frequency: float = 1.0431
    phase_offset: float = -0.7318
    detuning: float = 0.0
    duration: float = 2.0 * np.pi * 1.215

    def phase(self, t: Array | float) -> Array:
        t = np.asarray(t)
        return (
            self.amplitude_phase
            * np.cos(self.frequency * t - self.phase_offset)
            + self.detuning * t
        )

    def control(self, t: Array | float) -> Array:
        return np.exp(1j * self.phase(t))


def trapezoid_weights(times: Array) -> Array:
    if len(times) < 2:
        raise ValueError("at least two nodes are required")
    dt = np.diff(times)
    weights = np.empty_like(times)
    weights[0] = 0.5 * dt[0]
    weights[-1] = 0.5 * dt[-1]
    weights[1:-1] = 0.5 * (dt[:-1] + dt[1:])
    return weights


def sector_hamiltonian(control: complex, coupling: float) -> Array:
    return 0.5 * coupling * np.asarray(
        [[0.0, np.conj(control)], [control, 0.0]], dtype=np.complex128
    )


def full_hamiltonian(control: complex) -> Array:
    hamiltonian = np.zeros((7, 7), dtype=np.complex128)
    for ground, excited, coupling in (
        (1, 2, 1.0),
        (3, 4, 1.0),
        (5, 6, np.sqrt(2.0)),
    ):
        hamiltonian[excited, ground] = 0.5 * coupling * control
        hamiltonian[ground, excited] = 0.5 * coupling * np.conj(control)
    return hamiltonian


def integrate_matrix(
    dimension: int,
    hamiltonian: Callable[[float], Array],
    times: Array,
    rtol: float,
    atol: float,
) -> Array:
    def rhs(t: float, flat: Array) -> Array:
        unitary = flat.reshape(dimension, dimension)
        return (-1j * hamiltonian(t) @ unitary).reshape(-1)

    initial = np.eye(dimension, dtype=np.complex128).reshape(-1)
    result = solve_ivp(
        rhs,
        (float(times[0]), float(times[-1])),
        initial,
        t_eval=times,
        method="DOP853",
        rtol=rtol,
        atol=atol,
        max_step=(times[-1] - times[0]) / 20.0,
    )
    if not result.success:
        raise RuntimeError(result.message)
    return result.y.T.reshape(len(times), dimension, dimension)


def propagate_reduced(pulse: Pulse, times: Array) -> tuple[Array, Array, Array]:
    single = integrate_matrix(
        2,
        lambda t: sector_hamiltonian(pulse.control(t), 1.0),
        times,
        rtol=1e-11,
        atol=1e-13,
    )
    pair = integrate_matrix(
        2,
        lambda t: sector_hamiltonian(pulse.control(t), np.sqrt(2.0)),
        times,
        rtol=1e-11,
        atol=1e-13,
    )
    full = np.zeros((len(times), 7, 7), dtype=np.complex128)
    full[:, 0, 0] = 1.0
    full[:, np.ix_([1, 2], [1, 2])[0], np.ix_([1, 2], [1, 2])[1]] = single
    full[:, np.ix_([3, 4], [3, 4])[0], np.ix_([3, 4], [3, 4])[1]] = single
    full[:, np.ix_([5, 6], [5, 6])[0], np.ix_([5, 6], [5, 6])[1]] = pair
    return single, pair, full


def propagate_full(
    times: Array,
    control: Callable[[float], complex],
    rtol: float = 2e-12,
    atol: float = 2e-14,
) -> Array:
    return integrate_matrix(
        7,
        lambda t: full_hamiltonian(control(t)),
        times,
        rtol=rtol,
        atol=atol,
    )


def propagate_full_piecewise(times: Array, control_values: Array) -> Array:
    """Nonlinear seven-state propagation for a 201-node waveform.

    The line-search objective treats the control as constant at each interval
    midpoint. Each two-level block exponential is analytic, so thousands of
    exact nonlinear objective calls remain cheap.
    """
    unitary = np.eye(7, dtype=np.complex128)
    for index, dt in enumerate(np.diff(times)):
        control = 0.5 * (control_values[index] + control_values[index + 1])
        step = np.eye(7, dtype=np.complex128)
        for ground, excited, coupling in (
            (1, 2, 1.0),
            (3, 4, 1.0),
            (5, 6, np.sqrt(2.0)),
        ):
            block_h = sector_hamiltonian(control, coupling)
            frequency = 0.5 * coupling * abs(control)
            if frequency > 1e-15:
                block_step = (
                    np.cos(frequency * dt) * np.eye(2)
                    - 1j * np.sin(frequency * dt) / frequency * block_h
                )
            else:
                block_step = np.eye(2, dtype=np.complex128) - 1j * dt * block_h
            step[np.ix_([ground, excited], [ground, excited])] = block_step
        unitary = step @ unitary
    return unitary


def baseline_cz_infidelity(single_final: Array, pair_final: Array) -> float:
    a01 = single_final[0, 0]
    a11 = pair_final[0, 0]
    q01 = a01 / max(abs(a01), 1e-30)
    diagonal = np.asarray(
        [1.0 + 0.0j, abs(a01), abs(a01), -np.conj(q01 * q01) * a11]
    )
    fidelity = (abs(np.sum(diagonal)) ** 2 + np.sum(abs(diagonal) ** 2)) / 20.0
    return float(1.0 - fidelity.real)


def interaction_infidelity(reference: Array, actual: Array) -> float:
    interaction = reference.conj().T @ actual
    block = interaction[np.ix_(P_IDX, P_IDX)]
    diagonal = np.diag(block)
    q01 = diagonal[1] / max(abs(diagonal[1]), 1e-30)
    q10 = diagonal[2] / max(abs(diagonal[2]), 1e-30)
    corrected_trace = (
        diagonal[0]
        + abs(diagonal[1])
        + abs(diagonal[2])
        + np.conj(q01 * q10) * diagonal[3]
    )
    fidelity = (
        abs(corrected_trace) ** 2 + np.trace(block @ block.conj().T).real
    ) / 20.0
    return float(max(0.0, 1.0 - fidelity.real))


def control_operators() -> tuple[Array, Array]:
    op_x = np.zeros((7, 7), dtype=np.complex128)
    op_y = np.zeros((7, 7), dtype=np.complex128)
    for ground, excited, coupling in (
        (1, 2, 1.0),
        (3, 4, 1.0),
        (5, 6, np.sqrt(2.0)),
    ):
        op_x[excited, ground] = 0.5 * coupling
        op_x[ground, excited] = 0.5 * coupling
        op_y[excited, ground] = 0.5j * coupling
        op_y[ground, excited] = -0.5j * coupling
    return op_x, op_y


def hessian_kernel(
    ideal_evolution: Array, times: Array
) -> tuple[Array, Array, Array, Array]:
    """Return the paper's five-channel Hessian and its normalized modes.

    After removing the freely correctable symmetric local-Z phase using the
    return phases, the CZ infidelity is

        1-F = 1/2 |l_01|^2 + 1/4 |l_11|^2 + 3/20 theta_CZ^2 + O(s^3).

    The five real first-order channel responses below are the interaction-
    picture outer-product representation of that Hessian.
    """
    op_x, op_y = control_operators()
    responses: list[Array] = []
    for operator in (op_x, op_y):
        for unitary in ideal_evolution:
            interaction_operator = unitary.conj().T @ operator @ unitary
            leakage_single = -1j * interaction_operator[2, 1]
            leakage_pair = -1j * interaction_operator[6, 5]
            controlled_phase = -(
                interaction_operator[5, 5].real
                - 2.0 * interaction_operator[1, 1].real
            )
            responses.append(
                np.asarray(
                    [
                        leakage_single.real,
                        leakage_single.imag,
                        leakage_pair.real,
                        leakage_pair.imag,
                        controlled_phase,
                    ]
                )
            )
    response_matrix = np.asarray(responses).T

    node_weights = trapezoid_weights(times)
    weights = np.concatenate([node_weights, node_weights])
    sqrt_weights = np.sqrt(weights)
    weighted_responses = response_matrix * sqrt_weights[None, :]
    channel_weights = np.asarray([0.5, 0.5, 0.25, 0.25, 0.15])
    weighted = 2.0 * weighted_responses.T @ (
        channel_weights[:, None] * weighted_responses
    )
    weighted = 0.5 * (weighted + weighted.T)
    eigenvalues, eigenvectors = eigh(weighted, check_finite=True)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    modes = (eigenvectors.T / sqrt_weights[None, :]).reshape(
        2 * len(times), 2, len(times)
    )
    return weighted, eigenvalues, eigenvectors, modes


def smooth_null_directions(
    eigenvectors: Array, times: Array, count: int = 4
) -> Array:
    """Construct smooth null-space directions by projecting Chebyshev waves."""
    weights = trapezoid_weights(times)
    sqrt_weights = np.sqrt(weights)
    tau = 2.0 * times / times[-1] - 1.0
    principal = eigenvectors[:, :5]
    candidates: list[Array] = []
    for order in range(6, 18):
        values = chebval(tau, [0.0] * order + [1.0])
        for channel in (0, 1):
            direction = np.zeros(2 * len(times))
            sl = slice(channel * len(times), (channel + 1) * len(times))
            direction[sl] = sqrt_weights * values
            direction -= principal @ (principal.T @ direction)
            for previous in candidates:
                direction -= previous * np.dot(previous, direction)
            norm = np.linalg.norm(direction)
            if norm > 1e-8:
                candidates.append(direction / norm)
            if len(candidates) == count:
                return np.column_stack(candidates)
    raise RuntimeError("could not construct requested null directions")


def waveform_from_weighted(direction: Array, times: Array) -> Array:
    weights = trapezoid_weights(times)
    values = direction.reshape(2, len(times)) / np.sqrt(weights)[None, :]
    return values[0] + 1j * values[1]


class WaveformInfidelity:
    """Full nonlinear gate-infidelity evaluator on the declared node grid."""

    def __init__(
        self,
        pulse: Pulse,
        times: Array,
        continuous_reference: Array | None = None,
    ):
        self.pulse = pulse
        self.times = times
        self.ideal_values = pulse.control(times)
        self.reference = propagate_full_piecewise(times, self.ideal_values)
        self.continuous_reference = (
            continuous_reference
            if continuous_reference is not None
            else propagate_full(times, pulse.control)[-1]
        )
        self.calls = 0
        self.continuous_calls = 0

    def __call__(self, weighted_distortion: Array) -> float:
        self.calls += 1
        distortion = waveform_from_weighted(weighted_distortion, self.times)
        actual = propagate_full_piecewise(
            self.times, self.ideal_values + distortion
        )
        return interaction_infidelity(self.reference, actual)

    def continuous(self, weighted_distortion: Array) -> float:
        """High-accuracy DOP853 score used for every plotted cycle marker."""
        self.continuous_calls += 1
        distortion = waveform_from_weighted(weighted_distortion, self.times)
        real_spline = CubicSpline(self.times, distortion.real, bc_type="natural")
        imag_spline = CubicSpline(self.times, distortion.imag, bc_type="natural")
        actual = propagate_full(
            self.times,
            lambda t: self.pulse.control(t)
            + real_spline(t)
            + 1j * imag_spline(t),
        )[-1]
        return interaction_infidelity(self.continuous_reference, actual)


def finite_difference_curvature(
    pulse: Pulse,
    times: Array,
    reference_final: Array,
    direction: Array,
    epsilon: float,
) -> tuple[float, float, float]:
    waveform = waveform_from_weighted(direction, times)
    real_spline = CubicSpline(times, waveform.real, bc_type="natural")
    imag_spline = CubicSpline(times, waveform.imag, bc_type="natural")

    def distorted(sign: float) -> Callable[[float], complex]:
        return lambda t: pulse.control(t) + sign * epsilon * (
            real_spline(t) + 1j * imag_spline(t)
        )

    plus = propagate_full(times, distorted(+1.0))[-1]
    minus = propagate_full(times, distorted(-1.0))[-1]
    loss_plus = interaction_infidelity(reference_final, plus)
    loss_minus = interaction_infidelity(reference_final, minus)
    curvature = (loss_plus + loss_minus) / epsilon**2
    return float(curvature), float(loss_plus), float(loss_minus)


def cross_method_check(
    pulse: Pulse,
    times: Array,
    eigenvalues: Array,
    eigenvectors: Array,
    reference_final: Array,
) -> tuple[list[dict], dict]:
    nulls = smooth_null_directions(eigenvectors, times, count=4)
    directions = [
        (f"principal_{index + 1}", "principal", eigenvectors[:, index], eigenvalues[index])
        for index in range(5)
    ]
    directions.extend(
        (f"null_{index + 1}", "null", nulls[:, index], 0.0)
        for index in range(4)
    )
    rows: list[dict] = []
    for index, (name, kind, direction, analytic) in enumerate(directions, 1):
        progress(f"Cross-check {index}/{len(directions)}: {name}")
        coarse, plus_coarse, minus_coarse = finite_difference_curvature(
            pulse, times, reference_final, direction, 2e-3
        )
        fine, plus_fine, minus_fine = finite_difference_curvature(
            pulse, times, reference_final, direction, 1e-3
        )
        relative_error = (
            abs(fine - analytic) / abs(analytic) if kind == "principal" else np.nan
        )
        stability = (
            abs(fine - coarse) / max(abs(fine), abs(coarse), 1e-30)
            if kind == "principal"
            else abs(fine - coarse)
        )
        rows.append(
            {
                "direction": name,
                "kind": kind,
                "analytic_curvature": f"{analytic:.16e}",
                "fd_curvature_eps_2e-3": f"{coarse:.16e}",
                "fd_curvature_eps_1e-3": f"{fine:.16e}",
                "relative_error": (
                    f"{relative_error:.16e}" if np.isfinite(relative_error) else ""
                ),
                "step_stability": f"{stability:.16e}",
                "loss_plus_eps_2e-3": f"{plus_coarse:.16e}",
                "loss_minus_eps_2e-3": f"{minus_coarse:.16e}",
                "loss_plus_eps_1e-3": f"{plus_fine:.16e}",
                "loss_minus_eps_1e-3": f"{minus_fine:.16e}",
            }
        )
    principal_rows = rows[:5]
    null_rows = rows[5:]
    largest = float(eigenvalues[0])
    metrics = {
        "max_principal_relative_error": max(
            float(row["relative_error"]) for row in principal_rows
        ),
        "max_principal_step_instability": max(
            float(row["step_stability"]) for row in principal_rows
        ),
        "max_null_curvature_ratio": max(
            abs(float(row["fd_curvature_eps_1e-3"])) / largest for row in null_rows
        ),
        "principal_pass": all(
            float(row["relative_error"]) <= 5e-3 for row in principal_rows
        ),
        "stability_pass": all(
            float(row["step_stability"]) <= 2.5e-3 for row in principal_rows
        ),
        "null_pass": all(
            abs(float(row["fd_curvature_eps_1e-3"])) <= 1e-5 * largest
            for row in null_rows
        ),
        "null_directions": nulls,
    }
    return rows, metrics


def normalize_columns(matrix: Array) -> Array:
    output = matrix.copy()
    for index in range(output.shape[1]):
        norm = np.linalg.norm(output[:, index])
        if norm > 0:
            output[:, index] /= norm
    return output


def chebyshev_directions(times: Array) -> Array:
    weights = trapezoid_weights(times)
    sqrt_weights = np.sqrt(weights)
    tau = 2.0 * times / times[-1] - 1.0
    columns = []
    for order in range(6):
        values = chebval(tau, [0.0] * order + [1.0])
        for channel in (0, 1):
            direction = np.zeros(2 * len(times))
            sl = slice(channel * len(times), (channel + 1) * len(times))
            direction[sl] = sqrt_weights * values
            columns.append(direction)
    return normalize_columns(np.column_stack(columns))


def ansatz_directions(pulse: Pulse, times: Array) -> tuple[Array, Array]:
    weights = trapezoid_weights(times)
    sqrt_weights = np.sqrt(weights)
    omega = pulse.control(times)
    argument = pulse.frequency * times - pulse.phase_offset
    derivatives = [
        1j * omega * np.cos(argument),
        -1j * omega * pulse.amplitude_phase * times * np.sin(argument),
        1j * omega * pulse.amplitude_phase * np.sin(argument),
        1j * omega * times,
        1j
        * omega
        * (times / pulse.duration)
        * (
            -pulse.amplitude_phase * pulse.frequency * np.sin(argument)
            + pulse.detuning
        ),
    ]
    raw_columns = [
        np.concatenate([sqrt_weights * value.real, sqrt_weights * value.imag])
        for value in derivatives
    ]
    raw = normalize_columns(np.column_stack(raw_columns))
    left, singular, _ = np.linalg.svd(raw, full_matrices=False)
    rank = int(np.sum(singular / singular[0] > 1e-10))
    return raw, left[:, :rank]


def quadratic_loss(hessian: Array, control: Array) -> float:
    return float(max(0.0, 0.5 * control @ hessian @ control))


def coordinate_trace(
    hessian: Array,
    initial: Array,
    directions: Array,
    cycles: int,
) -> tuple[Array, Array]:
    control = initial.copy()
    losses = [quadratic_loss(hessian, control)]
    cycle_steps = [0]
    for _ in range(cycles):
        for direction in directions.T:
            curvature = float(direction @ hessian @ direction)
            if curvature > 1e-14 * np.linalg.norm(hessian):
                alpha = -float(direction @ hessian @ control) / curvature
                control += alpha * direction
            losses.append(quadratic_loss(hessian, control))
        cycle_steps.append(len(losses) - 1)
    return np.asarray(losses), np.asarray(cycle_steps)


def scale_to_exact_loss(
    evaluator: Callable[[Array], float],
    direction: Array,
    target: float,
) -> Array:
    unit_direction = direction / np.linalg.norm(direction)
    factors = np.geomspace(1e-4, 4.0, 80)
    previous_factor = 0.0
    previous_value = -target
    for factor in factors:
        value = evaluator(factor * unit_direction) - target
        if value >= 0.0 and previous_value <= 0.0:
            root = optimize.brentq(
                lambda scale: evaluator(scale * unit_direction) - target,
                previous_factor,
                factor,
                xtol=2e-9,
                rtol=2e-9,
            )
            return root * unit_direction
        previous_factor = float(factor)
        previous_value = float(value)
    raise RuntimeError(f"could not scale distortion to exact loss {target}")


def nonlinear_coordinate_trace(
    evaluator: WaveformInfidelity,
    hessian: Array,
    initial: Array,
    directions: Array,
    cycles: int,
    label: str,
) -> tuple[Array, Array, Array, list[Array]]:
    control = initial.copy()
    losses = [evaluator(control)]
    cycle_steps = [0]
    cycle_controls = [control.copy()]
    for cycle in range(cycles):
        for direction in directions.T:
            curvature = float(direction @ hessian @ direction)
            radius = 4.0 * math.sqrt(
                2.0 * max(losses[-1], 1e-12) / max(curvature, 1e-10)
            )
            radius = float(np.clip(radius, 0.025, 0.8))
            result = None
            for _ in range(2):
                result = optimize.minimize_scalar(
                    lambda alpha: evaluator(control + alpha * direction),
                    bounds=(-radius, radius),
                    method="bounded",
                    options={"xatol": 3e-5, "maxiter": 18},
                )
                if abs(result.x) < 0.92 * radius or radius >= 1.6:
                    break
                radius *= 2.0
            assert result is not None
            if float(result.fun) <= losses[-1] + 2e-12:
                control = control + float(result.x) * direction
                losses.append(float(result.fun))
            else:
                losses.append(losses[-1])
        cycle_steps.append(len(losses) - 1)
        cycle_controls.append(control.copy())
        progress(
            f"  {label}: cycle {cycle + 1}/{cycles}, "
            f"1−F={losses[-1]:.3e}"
        )
    return np.asarray(losses), np.asarray(cycle_steps), control, cycle_controls


def build_initial_distortion(
    hessian: Array,
    eigenvalues: Array,
    eigenvectors: Array,
    ansatz_basis: Array,
    seed: int,
    target_loss: float,
    floor_fraction: float = 0.019,
) -> Array:
    principal = eigenvectors[:, :5]
    lambdas = np.diag(eigenvalues[:5])
    span = principal.T @ ansatz_basis
    _, _, vh = np.linalg.svd(span.T @ lambdas, full_matrices=True)
    missing = vh[-1]
    rng = np.random.default_rng(seed)
    accessible_coefficients = rng.normal(size=ansatz_basis.shape[1])
    accessible = principal.T @ (
        ansatz_basis @ accessible_coefficients
    )
    accessible_energy = 0.5 * accessible @ lambdas @ accessible
    missing_energy = 0.5 * missing @ lambdas @ missing
    missing_scale = math.sqrt(
        floor_fraction
        / (1.0 - floor_fraction)
        * accessible_energy
        / missing_energy
    )
    coefficients = accessible + missing_scale * missing
    control = principal @ coefficients
    scale = math.sqrt(target_loss / quadratic_loss(hessian, control))
    return scale * control


def optimization_data(
    times: Array,
    eigenvalues: Array,
    eigenvectors: Array,
    seed: int,
    evaluator: WaveformInfidelity,
) -> dict:
    hessian = (
        eigenvectors[:, :5]
        @ np.diag(eigenvalues[:5])
        @ eigenvectors[:, :5].T
    )
    chebyshev = chebyshev_directions(times)
    ansatz_raw, ansatz_basis = ansatz_directions(Pulse(), times)
    effective = ansatz_basis.T @ hessian @ ansatz_basis
    values, vectors = eigh(effective)
    order = np.argsort(values)[::-1]
    ansatz_orthogonal = ansatz_basis @ vectors[:, order]
    ansatz_orthogonal = ansatz_orthogonal[:, values[order] > 1e-12 * values[order][0]]

    quadratic_initial = build_initial_distortion(
        hessian,
        eigenvalues,
        eigenvectors,
        ansatz_basis,
        seed,
        target_loss=2.4e-3,
    )
    initial = scale_to_exact_loss(
        evaluator.continuous, quadratic_initial, 2.4e-3
    )
    methods = {
        "Hessian eigenvectors": (eigenvectors[:, :5], 2),
        "Chebyshev, first 6 orders": (chebyshev, 5),
        "Analytical ansatz": (ansatz_raw, 12),
        "AA + orthogonal eigenbasis": (ansatz_orthogonal, 12),
    }
    traces = {}
    cycle_steps = {}
    final_controls = {}
    cycle_controls = {}
    for name, (directions, cycles) in methods.items():
        progress(f"Nonlinear optimization: {name}")
        (
            traces[name],
            cycle_steps[name],
            final_controls[name],
            cycle_controls[name],
        ) = nonlinear_coordinate_trace(
            evaluator, hessian, initial, directions, cycles, name
        )

    strength_traces = {}
    strength_cycles = {}
    strength_controls = {}
    strength_final_controls = {}
    strength_cycle_controls = {}
    direction = initial / np.linalg.norm(initial)
    for target in (0.10, 0.025, 0.006):
        scaled = scale_to_exact_loss(evaluator.continuous, direction, target)
        label = f"{target:.3f}"
        strength_controls[label] = scaled
        progress(f"Nonlinear distortion series: initial 1−F={target:.3f}")
        loss, cycles, final_control, control_cycles = nonlinear_coordinate_trace(
            evaluator,
            hessian,
            scaled,
            ansatz_raw,
            12,
            f"AA initial {target:.3f}",
        )
        strength_traces[label] = loss
        strength_cycles[label] = cycles
        strength_final_controls[label] = final_control
        strength_cycle_controls[label] = control_cycles

    quadratic_hessian_trace, quadratic_hessian_cycles = coordinate_trace(
        hessian, initial, eigenvectors[:, :5], 2
    )
    cycle_losses_continuous = {
        name: np.asarray([evaluator.continuous(value) for value in values])
        for name, values in cycle_controls.items()
    }
    strength_cycle_losses_continuous = {
        name: np.asarray([evaluator.continuous(value) for value in values])
        for name, values in strength_cycle_controls.items()
    }

    return {
        "hessian": hessian,
        "initial": initial,
        "traces": traces,
        "cycle_steps": cycle_steps,
        "final_controls": final_controls,
        "cycle_controls": cycle_controls,
        "cycle_losses_continuous": cycle_losses_continuous,
        "quadratic_hessian_trace": quadratic_hessian_trace,
        "quadratic_hessian_cycles": quadratic_hessian_cycles,
        "strength_traces": strength_traces,
        "strength_cycles": strength_cycles,
        "strength_controls": strength_controls,
        "strength_final_controls": strength_final_controls,
        "strength_cycle_controls": strength_cycle_controls,
        "strength_cycle_losses_continuous": strength_cycle_losses_continuous,
        "ansatz_rank": ansatz_basis.shape[1],
        "ansatz_orthogonal_count": ansatz_orthogonal.shape[1],
        "objective_calls": evaluator.calls,
        "continuous_objective_calls": evaluator.continuous_calls,
    }


def save_figure(figure: plt.Figure, path: Path) -> None:
    figure.savefig(path, dpi=210, bbox_inches="tight", facecolor="white")
    figure.savefig(
        path.with_suffix(".svg"),
        bbox_inches="tight",
        facecolor="white",
        format="svg",
    )
    plt.close(figure)


def panel_a(path: Path) -> None:
    figure, axis = plt.subplots(figsize=(3.2, 2.5))
    axis.axis("off")
    for y, label, color in ((0.15, "|0⟩", COLORS["purple"]), (0.35, "|1⟩", COLORS["blue"]), (0.82, "|r⟩", COLORS["orange"])):
        axis.plot([0.15, 0.85], [y, y], lw=3, color=color)
        axis.text(0.08, y, label, va="center", ha="right", fontsize=13)
    arrow = patches.FancyArrowPatch(
        (0.55, 0.38),
        (0.55, 0.79),
        arrowstyle="<->",
        mutation_scale=16,
        connectionstyle="arc3,rad=-0.25",
        lw=2.4,
        color=COLORS["green"],
    )
    axis.add_patch(arrow)
    axis.text(0.64, 0.58, "Ω̃(t)", color=COLORS["green"], fontsize=13)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.set_title("(a) Minimal atom", loc="left", fontweight="bold")
    save_figure(figure, path)


def panel_b(path: Path) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(7.6, 2.5))
    sectors = [
        ("|00⟩", None, "uncoupled"),
        ("|01⟩, |10⟩", "|0r⟩, |r0⟩", "Ω̃"),
        ("|11⟩", "|W⟩", "√2 Ω̃"),
    ]
    for axis, (ground, excited, coupling) in zip(axes, sectors):
        axis.axis("off")
        axis.plot([0.15, 0.85], [0.2, 0.2], lw=2.5, color=COLORS["purple"])
        axis.text(0.5, 0.12, ground, ha="center", fontsize=11)
        if excited is not None:
            axis.plot([0.15, 0.85], [0.78, 0.78], lw=2.5, color=COLORS["orange"])
            axis.text(0.5, 0.85, excited, ha="center", fontsize=11)
            axis.annotate(
                "",
                xy=(0.5, 0.73),
                xytext=(0.5, 0.25),
                arrowprops=dict(arrowstyle="<->", color=COLORS["green"], lw=2),
            )
            axis.text(0.57, 0.49, coupling, color=COLORS["green"], fontsize=11)
        else:
            axis.text(0.5, 0.55, coupling, ha="center", color=COLORS["gray"])
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
    figure.suptitle("(b) Perfect-blockade sectors", x=0.04, ha="left", fontweight="bold")
    save_figure(figure, path)


def panel_c(path: Path, times: Array, pulse: Pulse) -> None:
    tau = times / pulse.duration
    figure, axes = plt.subplots(2, 1, figsize=(4.0, 3.4), sharex=True)
    axes[0].plot(tau, np.abs(pulse.control(times)), color=COLORS["purple"], lw=2.5)
    axes[0].set_ylabel("|Ω̃|/Ω")
    axes[0].set_ylim(0, 1.15)
    axes[1].plot(tau, pulse.phase(times), color=COLORS["orange"], lw=2.5)
    axes[1].set(xlabel="normalized time  t/T", ylabel="phase φ (rad)")
    for axis in axes:
        axis.grid(alpha=0.2)
    figure.suptitle("(c) Analytical-ansatz pulse", x=0.07, ha="left", fontweight="bold")
    figure.tight_layout()
    save_figure(figure, path)


def bloch_coordinates(states: Array) -> Array:
    ground = states[:, 0, 0]
    excited = states[:, 1, 0]
    return np.column_stack(
        [
            2.0 * np.real(np.conj(ground) * excited),
            2.0 * np.imag(np.conj(ground) * excited),
            np.abs(ground) ** 2 - np.abs(excited) ** 2,
        ]
    )


def panel_d(path: Path, single: Array, pair: Array) -> None:
    figure = plt.figure(figsize=(6.0, 3.0))
    sphere_u = np.linspace(0, 2 * np.pi, 40)
    sphere_v = np.linspace(0, np.pi, 20)
    x = np.outer(np.cos(sphere_u), np.sin(sphere_v))
    y = np.outer(np.sin(sphere_u), np.sin(sphere_v))
    z = np.outer(np.ones_like(sphere_u), np.cos(sphere_v))
    for index, (states, title, color) in enumerate(
        ((single, "|01⟩ sector", COLORS["purple"]), (pair, "|11⟩ sector", COLORS["orange"])),
        1,
    ):
        axis = figure.add_subplot(1, 2, index, projection="3d")
        axis.plot_wireframe(x, y, z, rstride=4, cstride=4, color="#D9D9D9", lw=0.45)
        trajectory = bloch_coordinates(states)
        axis.plot(
            trajectory[:, 0],
            trajectory[:, 1],
            trajectory[:, 2],
            color=color,
            lw=2.5,
        )
        axis.scatter(*trajectory[0], color="black", s=18)
        axis.set_box_aspect((1, 1, 1))
        axis.set_title(title, fontsize=10)
        axis.set_axis_off()
        axis.view_init(elev=22, azim=34)
    figure.suptitle("(d) Bloch-sphere trajectories", x=0.04, ha="left", fontweight="bold")
    save_figure(figure, path)


def panel_e(path: Path, eigenvalues: Array) -> None:
    figure, axis = plt.subplots(figsize=(3.6, 2.8))
    ratios = np.maximum(np.abs(eigenvalues[:20] / eigenvalues[0]), 1e-18)
    axis.semilogy(
        np.arange(1, len(ratios) + 1),
        ratios,
        "o-",
        ms=5,
        color=COLORS["purple"],
    )
    axis.axvspan(0.5, 5.5, color=COLORS["orange"], alpha=0.12)
    axis.axhline(1e-8, color=COLORS["gray"], ls="--", lw=1)
    axis.set(
        xlabel="mode index",
        ylabel="normalized sensitivity  λᵢ/λ₁",
        ylim=(1e-18, 2),
        xlim=(0.5, 20.5),
    )
    axis.grid(alpha=0.2, which="both")
    axis.set_title("(e) Five nonzero Hessian modes", loc="left", fontweight="bold")
    save_figure(figure, path)


def panel_f(
    path: Path, times: Array, modes: Array, null_directions: Array
) -> None:
    tau = times / times[-1]
    figure, axes = plt.subplots(2, 2, figsize=(8.0, 5.2), sharex=True)
    principal_colors = plt.cm.viridis(np.linspace(0.08, 0.92, 5))
    null_colors = plt.cm.Greys(np.linspace(0.40, 0.82, 4))
    null_waveforms = [
        waveform_from_weighted(null_directions[:, index], times)
        for index in range(4)
    ]

    for index, color in enumerate(principal_colors):
        axes[0, 0].plot(
            tau, modes[index, 0], color=color, lw=1.5, label=f"v{index + 1}"
        )
        axes[1, 0].plot(tau, modes[index, 1], color=color, lw=1.5)
    for index, (waveform, color) in enumerate(zip(null_waveforms, null_colors)):
        axes[0, 1].plot(
            tau, waveform.real, color=color, lw=1.2, label=f"v⊥{index + 1}"
        )
        axes[1, 1].plot(tau, waveform.imag, color=color, lw=1.2)

    axes[0, 0].set_title("Principal space — vᵢ", fontsize=10)
    axes[0, 1].set_title("Null space — v⊥", fontsize=10)
    axes[0, 0].set_ylabel("Re[δΩ̃]")
    axes[1, 0].set_ylabel("Im[δΩ̃]")
    for axis in axes.flat:
        axis.axhline(0, color="#BBBBBB", lw=0.6)
        axis.grid(alpha=0.12)
        axis.tick_params(labelsize=7)
    for axis in axes[1]:
        axis.set_xlabel("normalized time  t/T", fontsize=8)
    axes[0, 0].legend(frameon=False, fontsize=7, ncol=3)
    axes[0, 1].legend(frameon=False, fontsize=7, ncol=2)
    figure.suptitle(
        "(f) Principal and null Hessian modes: real and imaginary parts",
        x=0.04,
        ha="left",
        fontweight="bold",
    )
    figure.tight_layout()
    save_figure(figure, path)


def panel_g(
    path: Path,
    optimization: dict,
    eigenvalues: Array,
    eigenvectors: Array,
) -> None:
    """Mechanistic reconstruction of the paper's optimization landscape.

    The plotted trajectory is not digitized from the paper: it is the actual
    two-cycle Hessian-coordinate trajectory generated in this run, projected
    onto the first two principal modes.
    """

    controls = optimization["cycle_controls"]["Hessian eigenvectors"]
    coordinates = np.asarray(
        [
            [
                float(eigenvectors[:, 0] @ control),
                float(eigenvectors[:, 1] @ control),
            ]
            for control in controls
        ]
    )
    scale = max(float(np.max(np.abs(coordinates))), 0.02)
    grid = np.linspace(-1.35 * scale, 1.35 * scale, 100)
    x, y = np.meshgrid(grid, grid)
    loss = 0.5 * (
        eigenvalues[0] * x**2 + eigenvalues[1] * y**2
    )
    levels = np.geomspace(
        max(float(np.min(loss[loss > 0])), 1e-8),
        max(float(np.max(loss)), 2e-3),
        8,
    )

    figure = plt.figure(figsize=(4.8, 3.8))
    axis = figure.add_subplot(111, projection="3d")
    colors = plt.cm.coolwarm(np.linspace(0.15, 0.85, len(levels)))
    for z, alpha in ((0.0, 0.80), (1.0, 0.38)):
        for level, color in zip(levels, colors):
            axis.contour(
                x,
                y,
                loss,
                levels=[level],
                zdir="z",
                offset=z,
                colors=[color],
                linewidths=0.8,
                alpha=alpha,
            )
    trajectory_z = np.linspace(1.0, 0.0, len(coordinates))
    axis.plot(
        coordinates[:, 0],
        coordinates[:, 1],
        trajectory_z,
        "o-",
        color="black",
        lw=1.8,
        ms=4,
        label="computed cycle trajectory",
    )
    axis.quiver(
        coordinates[0, 0],
        coordinates[0, 1],
        1.0,
        coordinates[-1, 0] - coordinates[0, 0],
        coordinates[-1, 1] - coordinates[0, 1],
        -1.0,
        color=COLORS["purple"],
        arrow_length_ratio=0.10,
        linewidth=1.4,
    )
    axis.text(
        coordinates[0, 0],
        coordinates[0, 1],
        1.05,
        "initial distortion",
        fontsize=7,
    )
    axis.text(
        coordinates[-1, 0],
        coordinates[-1, 1],
        -0.10,
        "optimized gate",
        fontsize=7,
    )
    axis.set(
        xlabel="δΩ̃·v₁",
        ylabel="δΩ̃·v₂",
        zlabel="optimization layer",
        zlim=(-0.12, 1.12),
    )
    axis.set_zticks((0.0, 1.0), ("optimized", "initial"))
    axis.tick_params(labelsize=6)
    axis.view_init(elev=24, azim=-56)
    axis.set_title(
        "(g) Hessian-landscape trajectory\n(mechanistic reconstruction)",
        loc="left",
        fontweight="bold",
        fontsize=10,
    )
    save_figure(figure, path)


def panel_h(path: Path, optimization: dict) -> None:
    figure, axis = plt.subplots(figsize=(4.6, 3.4))
    style = {
        "Hessian eigenvectors": (COLORS["orange"], "o"),
        "Chebyshev, first 6 orders": (COLORS["green"], "D"),
        "Analytical ansatz": (COLORS["blue"], "^"),
        "AA + orthogonal eigenbasis": (COLORS["red"], "s"),
    }
    for name, values in optimization["traces"].items():
        color, marker = style[name]
        steps = np.arange(len(values))
        axis.plot(steps, np.maximum(values, 1e-12), color=color, alpha=0.32, lw=1)
        axis.scatter(steps, np.maximum(values, 1e-12), color=color, alpha=0.25, s=11)
        cycle = optimization["cycle_steps"][name]
        cycle_values = optimization["cycle_losses_continuous"][name]
        axis.plot(
            cycle,
            np.maximum(cycle_values, 1e-12),
            marker=marker,
            color=color,
            ms=5,
            lw=1.8,
            label=name,
        )
    axis.set_yscale("log")
    axis.set(
        xlabel="one-dimensional optimization step",
        ylabel="full nonlinear gate infidelity",
        ylim=(5e-11, 8e-3),
        xlim=(0, 60),
    )
    axis.grid(alpha=0.2, which="both")
    axis.legend(frameon=False, fontsize=7, loc="upper right")
    axis.set_title("(h) Optimization-basis comparison", loc="left", fontweight="bold")
    save_figure(figure, path)


def panel_i(path: Path, optimization: dict) -> None:
    figure, axis = plt.subplots(figsize=(5.0, 3.8))
    colors = [COLORS["purple"], COLORS["orange"], COLORS["green"]]
    for (label, values), color in zip(
        optimization["strength_traces"].items(), colors
    ):
        steps = np.arange(len(values))
        axis.plot(
            steps,
            np.maximum(values, 1e-12),
            "-",
            color=color,
            alpha=0.35,
            lw=1.5,
        )
        cycle = optimization["strength_cycles"][label]
        cycle_values = optimization["strength_cycle_losses_continuous"][label]
        axis.plot(
            cycle,
            np.maximum(cycle_values, 1e-12),
            "o-",
            color=color,
            ms=3.5,
            lw=1.5,
            label=f"initial 1−F ≈ {float(label):.3g}",
        )
    axis.set_yscale("log")
    axis.set(
        xlabel="analytic-ansatz optimization step",
        ylabel="full nonlinear gate infidelity",
        ylim=(4e-5, 0.2),
        xlim=(0, 60),
    )
    axis.grid(alpha=0.2, which="both")
    axis.legend(frameon=False, fontsize=7, loc="lower left")

    pulse = Pulse()
    times = np.linspace(0.0, pulse.duration, len(next(iter(
        optimization["strength_controls"].values()
    ))) // 2)
    tau = times / pulse.duration
    ideal = pulse.control(times)
    amplitude_axis = axis.inset_axes([0.55, 0.66, 0.42, 0.20])
    phase_axis = axis.inset_axes([0.55, 0.39, 0.42, 0.20])
    amplitude_axis.plot(tau, np.abs(ideal), "--", color="#888888", lw=0.9)
    phase_axis.plot(tau, np.unwrap(np.angle(ideal)), "--", color="#888888", lw=0.9)
    for (_, control), color in zip(
        optimization["strength_controls"].items(), colors
    ):
        distorted = ideal + waveform_from_weighted(control, times)
        amplitude_axis.plot(tau, np.abs(distorted), color=color, lw=1.0)
        phase_axis.plot(tau, np.unwrap(np.angle(distorted)), color=color, lw=1.0)
    amplitude_axis.set_ylabel("|Ω̃₀+δΩ̃|", fontsize=6)
    phase_axis.set_ylabel("arg(Ω̃₀+δΩ̃)", fontsize=6)
    phase_axis.set_xlabel("t/T", fontsize=6)
    for inset in (amplitude_axis, phase_axis):
        inset.tick_params(labelsize=5, length=2)
        inset.grid(alpha=0.15)

    axis.set_title("(i) Distortion-dependent ansatz floor", loc="left", fontweight="bold")
    save_figure(figure, path)


def purple_diagnostic(path: Path, optimization: dict) -> None:
    nonlinear = optimization["traces"]["Hessian eigenvectors"]
    nonlinear_cycle = optimization["cycle_steps"]["Hessian eigenvectors"]
    nonlinear_cycle_values = optimization["cycle_losses_continuous"][
        "Hessian eigenvectors"
    ]
    quadratic = optimization["quadratic_hessian_trace"]
    figure, axis = plt.subplots(figsize=(5.2, 3.5))
    axis.semilogy(
        np.arange(len(quadratic)),
        np.maximum(quadratic, 1e-16),
        "o-",
        color=COLORS["purple"],
        label="previous quadratic-only trace",
    )
    axis.semilogy(
        np.arange(len(nonlinear)),
        np.maximum(nonlinear, 1e-16),
        "-",
        color=COLORS["orange"],
        alpha=0.35,
    )
    axis.semilogy(
        nonlinear_cycle,
        np.maximum(nonlinear_cycle_values, 1e-16),
        "o-",
        color=COLORS["orange"],
        label="correct full nonlinear fidelity",
    )
    axis.axvline(5, color=COLORS["gray"], ls="--", lw=1)
    axis.text(
        5.15,
        2e-8,
        "end of first 5-mode cycle",
        fontsize=8,
        rotation=90,
        va="center",
    )
    axis.set(
        xlabel="Hessian-eigenvector scan",
        ylabel="gate infidelity",
        title="Why the old purple curve disappeared",
        xlim=(0, max(len(quadratic), len(nonlinear)) - 1),
        ylim=(1e-16, 8e-3),
    )
    axis.grid(alpha=0.2, which="both")
    axis.legend(frameon=False, fontsize=8)
    save_figure(figure, path)


def waveform_distortion_figure(
    path: Path, times: Array, optimization: dict
) -> None:
    pulse = Pulse()
    tau = times / pulse.duration
    ideal = pulse.control(times)
    colors = [COLORS["purple"], COLORS["orange"], COLORS["green"]]
    figure, axes = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True)
    axes[0].plot(
        tau, np.abs(ideal), "--", color="#777777", lw=1.5, label="ideal Ω̃₀"
    )
    axes[1].plot(
        tau, np.unwrap(np.angle(ideal)), "--", color="#777777", lw=1.5
    )
    for (label, control), color in zip(
        optimization["strength_controls"].items(), colors
    ):
        distorted = ideal + waveform_from_weighted(control, times)
        axes[0].plot(
            tau,
            np.abs(distorted),
            color=color,
            lw=1.6,
            label=f"Ω̃₀+δΩ̃, initial 1−F={float(label):.3g}",
        )
        axes[1].plot(
            tau,
            np.unwrap(np.angle(distorted)),
            color=color,
            lw=1.6,
        )
    axes[0].set_ylabel("|Ω̃₀(t)+δΩ̃(t)|/Ω")
    axes[1].set(
        xlabel="normalized time  t/T",
        ylabel="arg[Ω̃₀(t)+δΩ̃(t)]  (rad)",
    )
    for axis in axes:
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False, fontsize=8, ncol=2)
    figure.suptitle(
        "Panel (i) input waveforms — amplitude and phase with δΩ̃",
        fontweight="bold",
    )
    figure.tight_layout()
    save_figure(figure, path)


def composite_figure(path: Path, panel_paths: list[Path]) -> None:
    figure, axes = plt.subplots(3, 3, figsize=(14, 12))
    for axis, panel_path in zip(axes.flat, panel_paths):
        axis.imshow(plt.imread(panel_path))
        axis.axis("off")
    figure.suptitle(
        "Reproduction of arXiv:2606.05060v1, Figure 1 (a–i)",
        fontsize=17,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.97), pad=0.3)
    save_figure(figure, path)


def paired_panels(path: Path, panel_paths: list[Path], title: str) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for axis, panel_path in zip(axes, panel_paths):
        axis.imshow(plt.imread(panel_path))
        axis.axis("off")
    figure.suptitle(title, fontsize=15, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.95), pad=0.2)
    save_figure(figure, path)


def optimization_rows(optimization: dict) -> list[dict]:
    rows = []
    for name, values in optimization["traces"].items():
        cycle_set = set(optimization["cycle_steps"][name].tolist())
        cycle_lookup = dict(
            zip(
                optimization["cycle_steps"][name].tolist(),
                optimization["cycle_losses_continuous"][name].tolist(),
            )
        )
        for step, value in enumerate(values):
            rows.append(
                {
                    "panel": "h",
                    "method": name,
                    "initial_target": "",
                    "step": step,
                    "cycle_marker": int(step in cycle_set),
                    "infidelity": f"{value:.16e}",
                    "continuous_cycle_infidelity": (
                        f"{cycle_lookup[step]:.16e}"
                        if step in cycle_lookup
                        else ""
                    ),
                }
            )
    for target, values in optimization["strength_traces"].items():
        cycle_set = set(optimization["strength_cycles"][target].tolist())
        cycle_lookup = dict(
            zip(
                optimization["strength_cycles"][target].tolist(),
                optimization["strength_cycle_losses_continuous"][
                    target
                ].tolist(),
            )
        )
        for step, value in enumerate(values):
            rows.append(
                {
                    "panel": "i",
                    "method": "Analytical ansatz",
                    "initial_target": target,
                    "step": step,
                    "cycle_marker": int(step in cycle_set),
                    "infidelity": f"{value:.16e}",
                    "continuous_cycle_infidelity": (
                        f"{cycle_lookup[step]:.16e}"
                        if step in cycle_lookup
                        else ""
                    ),
                }
            )
    return rows


def waveform_rows(times: Array, optimization: dict) -> list[dict]:
    pulse = Pulse()
    ideal = pulse.control(times)
    distorted = {
        label: ideal + waveform_from_weighted(control, times)
        for label, control in optimization["strength_controls"].items()
    }
    rows = []
    for index, time_value in enumerate(times):
        row = {
            "node": index,
            "time": f"{time_value:.16e}",
            "normalized_time": f"{time_value / pulse.duration:.16e}",
            "ideal_real": f"{ideal[index].real:.16e}",
            "ideal_imag": f"{ideal[index].imag:.16e}",
            "ideal_amplitude": f"{abs(ideal[index]):.16e}",
            "ideal_phase": f"{np.angle(ideal[index]):.16e}",
        }
        for label, values in distorted.items():
            prefix = f"initial_{label}"
            row[f"{prefix}_real"] = f"{values[index].real:.16e}"
            row[f"{prefix}_imag"] = f"{values[index].imag:.16e}"
            row[f"{prefix}_amplitude"] = f"{abs(values[index]):.16e}"
            row[f"{prefix}_phase_unwrapped"] = (
                f"{np.unwrap(np.angle(values))[index]:.16e}"
            )
        rows.append(row)
    return rows


def run_mwe(pulse: Pulse) -> None:
    progress("MWE 1/3: reduced and full propagation on 41 nodes")
    times = np.linspace(0.0, pulse.duration, 41)
    single, pair, reduced = propagate_reduced(pulse, times)
    full = propagate_full(times, pulse.control)
    unitary_difference = float(np.max(np.abs(reduced[-1] - full[-1])))
    progress("MWE 2/3: analytic Hessian rank")
    _, eigenvalues, eigenvectors, _ = hessian_kernel(reduced, times)
    rank = int(np.sum(eigenvalues / eigenvalues[0] > 1e-8))
    progress("MWE 3/3: one independent principal curvature")
    curvature, _, _ = finite_difference_curvature(
        pulse, times, full[-1], eigenvectors[:, 0], 1e-3
    )
    relative_error = abs(curvature - eigenvalues[0]) / eigenvalues[0]
    print(
        json.dumps(
            {
                "nodes": 41,
                "reduced_full_max_abs": unitary_difference,
                "rank": rank,
                "lambda1": float(eigenvalues[0]),
                "fd_lambda1": curvature,
                "relative_error": relative_error,
            },
            indent=2,
        ),
        flush=True,
    )
    if unitary_difference > 1e-9 or rank != 5 or relative_error > 0.02:
        raise RuntimeError("MWE acceptance gate failed")


def full_run(run_dir: Path, run: dict) -> None:
    started = time.perf_counter()
    figs = run_dir / "figs"
    data = run_dir / "data"
    figs.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    pulse = Pulse()
    node_count = int(run["method"]["settings"]["time_nodes"])
    times = np.linspace(0.0, pulse.duration, node_count)

    progress(f"Primary 1/4: propagating reduced symmetry sectors on {node_count} nodes")
    primary_started = time.perf_counter()
    single, pair, reduced = propagate_reduced(pulse, times)
    baseline_error = baseline_cz_infidelity(single[-1], pair[-1])

    progress("Primary 2/4: assembling and diagonalizing the 402×402 Hessian")
    weighted, eigenvalues, eigenvectors, modes = hessian_kernel(reduced, times)
    rank = int(np.sum(eigenvalues / eigenvalues[0] > 1e-8))
    weights = trapezoid_weights(times)
    mode_norm_errors = [
        abs(
            np.sum(
                weights
                * (modes[index, 0] ** 2 + modes[index, 1] ** 2)
            )
            - 1.0
        )
        for index in range(9)
    ]
    primary_seconds = time.perf_counter() - primary_started
    progress(
        f"Primary 3/4: rank={rank}, λ6/λ1={abs(eigenvalues[5]/eigenvalues[0]):.3e}, "
        f"baseline 1−F={baseline_error:.3e}"
    )

    progress("Primary 4/4: propagating the independent full seven-state baseline")
    secondary_started = time.perf_counter()
    full = propagate_full(times, pulse.control)
    unitary_difference = float(np.max(np.abs(reduced[-1] - full[-1])))

    progress("Secondary: measuring five principal and four null curvatures")
    rows, cross_metrics = cross_method_check(
        pulse, times, eigenvalues, eigenvectors, full[-1]
    )
    null_directions = cross_metrics.pop("null_directions")
    secondary_seconds = time.perf_counter() - secondary_started

    progress("Optimization panels: comparing four coordinate systems")
    optimization_started = time.perf_counter()
    nonlinear_evaluator = WaveformInfidelity(
        pulse, times, continuous_reference=full[-1]
    )
    piecewise_reference_difference = float(
        np.max(np.abs(nonlinear_evaluator.reference - full[-1]))
    )
    optimization = optimization_data(
        times,
        eigenvalues,
        eigenvectors,
        int(run["method"]["settings"]["distortion_seed"]),
        nonlinear_evaluator,
    )
    optimization_seconds = time.perf_counter() - optimization_started

    progress("Rendering panels (a–i); panel (g) is a mechanistic reconstruction")
    panel_paths = [figs / f"panel_{letter}.png" for letter in "abcdefghi"]
    panel_a(panel_paths[0])
    panel_b(panel_paths[1])
    panel_c(panel_paths[2], times, pulse)
    panel_d(panel_paths[3], single, pair)
    panel_e(panel_paths[4], eigenvalues)
    panel_f(panel_paths[5], times, modes, null_directions)
    panel_g(panel_paths[6], optimization, eigenvalues, eigenvectors)
    panel_h(panel_paths[7], optimization)
    panel_i(panel_paths[8], optimization)
    purple_diagnostic(figs / "panel_h_purple_diagnostic.png", optimization)
    waveform_distortion_figure(
        figs / "waveform_distortions_amplitude_phase.png", times, optimization
    )
    composite_figure(figs / "figure1_reproduction.png", panel_paths)
    paired_panels(
        figs / "panels_h_i.png",
        panel_paths[7:9],
        "Figure 1(h–i) — reconstructed optimization trends",
    )
    write_csv(data / "cross-method-check.csv", rows)
    write_csv(data / "optimization-trajectories.csv", optimization_rows(optimization))
    write_csv(data / "waveform-distortions.csv", waveform_rows(times, optimization))
    np.savez_compressed(
        data / "hessian-data.npz",
        times=times,
        weights=weights,
        control=pulse.control(times),
        hessian=weighted,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        modes=modes,
        null_directions=null_directions,
        panel_h_initial_distortion=optimization["initial"],
        panel_i_initial_distortions=np.stack(
            list(optimization["strength_controls"].values())
        ),
    )

    h_final = {
        name: float(values[-1])
        for name, values in optimization["cycle_losses_continuous"].items()
    }
    i_initial_final = {
        target: {
            "initial": float(
                optimization["strength_cycle_losses_continuous"][target][0]
            ),
            "final": float(
                optimization["strength_cycle_losses_continuous"][target][-1]
            ),
            "floor_ratio": float(
                optimization["strength_cycle_losses_continuous"][target][-1]
                / optimization["strength_cycle_losses_continuous"][target][0]
            ),
        }
        for target, values in optimization["strength_traces"].items()
    }
    total_seconds = time.perf_counter() - started
    peak_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    summary = {
        "run_id": run["run_id"],
        "time_nodes": node_count,
        "baseline_cz_infidelity": baseline_error,
        "reduced_full_max_abs_difference": unitary_difference,
        "active_hessian_rank": rank,
        "lambda_1": float(eigenvalues[0]),
        "lambda_5_over_lambda_1": float(eigenvalues[4] / eigenvalues[0]),
        "lambda_6_over_lambda_1": float(abs(eigenvalues[5] / eigenvalues[0])),
        "maximum_mode_norm_error": float(max(mode_norm_errors)),
        "cross_method": cross_metrics,
        "ansatz_tangent_rank": int(optimization["ansatz_rank"]),
        "ansatz_orthogonal_direction_count": int(
            optimization["ansatz_orthogonal_count"]
        ),
        "optimization_objective_calls": int(optimization["objective_calls"]),
        "continuous_optimization_validation_calls": int(
            optimization["continuous_objective_calls"]
        ),
        "piecewise_vs_continuous_baseline_max_difference": (
            piecewise_reference_difference
        ),
        "panel_h_final_infidelities": h_final,
        "panel_h_first_cycle_infidelity": float(
            optimization["cycle_losses_continuous"]["Hessian eigenvectors"][1]
        ),
        "panel_h_quadratic_first_cycle_infidelity": float(
            optimization["quadratic_hessian_trace"][
                optimization["quadratic_hessian_cycles"][1]
            ]
        ),
        "panel_i_initial_and_final": i_initial_final,
        "timing_seconds": {
            "primary": primary_seconds,
            "secondary": secondary_seconds,
            "optimization": optimization_seconds,
            "total": total_seconds,
        },
        "peak_resident_memory_mib": peak_mib,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
            "platform": platform.platform(),
        },
        "acceptance": {
            "rank_pass": rank == 5,
            "unitary_pass": unitary_difference <= 1e-9,
            "normalization_pass": max(mode_norm_errors) <= 1e-9,
            "principal_curvature_pass": bool(cross_metrics["principal_pass"]),
            "finite_difference_stability_pass": bool(
                cross_metrics["stability_pass"]
            ),
            "null_curvature_pass": bool(cross_metrics["null_pass"]),
            "nonlinear_hessian_cycle_pass": bool(
                optimization["cycle_losses_continuous"][
                    "Hessian eigenvectors"
                ][-1]
                <= 1e-8
                and optimization["cycle_losses_continuous"][
                    "Hessian eigenvectors"
                ][1]
                <= 1e-4
            ),
            "waveform_evidence_pass": bool(
                all(
                    np.all(
                        np.isfinite(
                            waveform_from_weighted(control, times)
                        )
                    )
                    for control in optimization["strength_controls"].values()
                )
            ),
        },
    }
    summary["acceptance"]["all_pass"] = all(summary["acceptance"].values())
    write_json(data / "summary.json", summary)

    progress(
        "Complete: "
        f"rank={rank}, max principal error="
        f"{cross_metrics['max_principal_relative_error']:.3e}, "
        f"max null ratio={cross_metrics['max_null_curvature_ratio']:.3e}, "
        f"wall={total_seconds:.2f} s"
    )
    if not summary["acceptance"]["all_pass"]:
        raise RuntimeError("one or more declared acceptance criteria failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--mwe", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    run = load_run(run_dir)
    pulse = Pulse()
    if args.mwe:
        run_mwe(pulse)
    else:
        full_run(run_dir, run)


if __name__ == "__main__":
    main()
