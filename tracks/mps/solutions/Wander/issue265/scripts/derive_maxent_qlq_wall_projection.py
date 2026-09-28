#!/usr/bin/env python3
"""Target-free finite-window wall from a maximum-entropy QLQ continuum.

The exact band-projected microscopic current fixes the current norm, its
coupling to ``QLQ``, and five QLQ Lanczos recurrents.  Stationary KPZ plus
continuity fixes the absolute ``rho_Q(omega) ~ c*omega**(1/3)`` boundary.
These data do not uniquely determine the remaining continuum.  This script
therefore makes one explicit closure choice: maximum relative entropy with
respect to Lebesgue measure on the unresolved positive-frequency interval.

The resulting positive continuum is compressed by Gaussian quadrature and
propagated as an exactly conservative Mori star.  The density structure
factor is then integrated to a sharp-wall profile and passed through the
already frozen weak estimator.  No spin-chain trajectory and no target
Burgers coefficient are accepted as inputs.  The output is a closure estimate,
not a proof that maximum entropy is the physical QLQ terminator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.special import logsumexp
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import expm_multiply


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _maximum_entropy_measure(
    even_moments: np.ndarray,
    low_density_amplitude: float,
    *,
    low_density_exponent: float = 1.0 / 3.0,
    omega_match: float,
    omega_maximum: float,
    integration_order: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Return a positive discretization of the fixed-tail/maxent measure."""

    moments = np.asarray(even_moments, dtype=float)
    if moments.ndim != 1 or moments.size < 2 or moments[0] <= 0.0:
        raise ValueError("even_moments must start with a positive mass")
    if not 0.0 < omega_match < omega_maximum:
        raise ValueError("require 0 < omega_match < omega_maximum")
    if integration_order < 256:
        raise ValueError("integration_order must be at least 256")

    low_density_exponent = float(low_density_exponent)
    if low_density_exponent <= -1.0:
        raise ValueError("low_density_exponent must define an integrable tail")
    orders = np.arange(moments.size, dtype=float)
    low_moments = (
        low_density_amplitude
        * omega_match ** (2.0 * orders + low_density_exponent + 1.0)
        / (2.0 * orders + low_density_exponent + 1.0)
    )
    unresolved = moments - low_moments
    if np.any(unresolved <= 0.0):
        raise ValueError("fixed low-frequency tail exceeds a supplied moment")
    unresolved_mass = unresolved[0]

    # A scale of four keeps the five moment constraints numerically balanced;
    # it is only a basis change and does not alter the entropy solution.
    feature_scale = 4.0
    target = np.asarray(
        [
            unresolved[index]
            / unresolved_mass
            / feature_scale ** (2 * index)
            for index in range(1, moments.size)
        ]
    )
    nodes, base_weights = np.polynomial.legendre.leggauss(integration_order)
    omega = (
        0.5 * (omega_maximum - omega_match) * nodes
        + 0.5 * (omega_maximum + omega_match)
    )
    base_weights = 0.5 * (omega_maximum - omega_match) * base_weights
    features = np.column_stack(
        [
            (omega / feature_scale) ** (2 * index)
            for index in range(1, moments.size)
        ]
    )
    log_base = np.log(base_weights)

    def statistics(multiplier: np.ndarray):
        log_weight = log_base - features @ multiplier
        log_weight -= logsumexp(log_weight)
        probability = np.exp(log_weight)
        mean = probability @ features
        centered = features - mean
        covariance = centered.T @ (probability[:, None] * centered)
        return probability, mean, covariance

    # Damped Newton on the strictly convex entropy dual.  The relative-moment
    # line search avoids the precision loss seen in a generic BFGS solve.
    multiplier = np.zeros(target.size)
    relative_error = np.inf
    iterations = 0
    for iterations in range(1, 101):
        probability, mean, covariance = statistics(multiplier)
        residual = mean - target
        relative_error = float(np.max(np.abs(residual) / target))
        if relative_error < 1.0e-10:
            break
        step = np.linalg.solve(
            covariance + 1.0e-14 * np.eye(target.size), residual
        )
        old_loss = float(np.dot(residual / target, residual / target))
        damping = 1.0
        for _ in range(40):
            _, trial_mean, _ = statistics(multiplier + damping * step)
            trial_residual = trial_mean - target
            trial_loss = float(
                np.dot(trial_residual / target, trial_residual / target)
            )
            if trial_loss < old_loss:
                break
            damping *= 0.5
        multiplier += damping * step
    else:
        raise RuntimeError("maximum-entropy Newton solve did not converge")

    probability, mean, _ = statistics(multiplier)
    high_weights = unresolved_mass * probability

    # Resolve the analytically fixed low tail independently.  Its small mass
    # is essential for the nonanalytic z^(1/3) boundary and must not disappear
    # in the high-frequency entropy discretization.
    low_nodes, low_quadrature = np.polynomial.legendre.leggauss(
        max(64, integration_order // 8)
    )
    low_omega = 0.5 * omega_match * (low_nodes + 1.0)
    low_quadrature = 0.5 * omega_match * low_quadrature
    low_weights = (
        low_density_amplitude
        * low_omega**low_density_exponent
        * low_quadrature
    )
    all_omega = np.concatenate((low_omega, omega))
    all_weights = np.concatenate((low_weights, high_weights))
    all_weights *= moments[0] / np.sum(all_weights)

    reconstructed = np.asarray(
        [np.dot(all_weights, all_omega ** (2 * index)) for index in range(moments.size)]
    )
    return all_omega, all_weights, {
        "omega_match": float(omega_match),
        "low_density_exponent": low_density_exponent,
        "omega_maximum": float(omega_maximum),
        "integration_order": int(integration_order),
        "feature_scale": feature_scale,
        "dual_multiplier": multiplier.tolist(),
        "newton_iterations": int(iterations),
        "maximum_relative_constraint_error": relative_error,
        "target_even_moments": moments.tolist(),
        "fixed_low_tail_even_moments": low_moments.tolist(),
        "reconstructed_even_moments": reconstructed.tolist(),
        "maximum_relative_reconstructed_moment_error": float(
            np.max(np.abs(reconstructed / moments - 1.0))
        ),
    }


def _gaussian_compress(
    omega: np.ndarray, weights: np.ndarray, order: int
) -> tuple[np.ndarray, np.ndarray, float]:
    """Compress a positive discrete measure by a reorthogonalized Lanczos rule."""

    omega = np.asarray(omega, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if order < 8 or order >= omega.size:
        raise ValueError("invalid compression order")
    mass = float(np.sum(weights))
    vector = np.sqrt(weights / mass)
    previous = np.zeros_like(vector)
    beta_previous = 0.0
    basis = []
    alpha = []
    beta = []
    for level in range(order):
        basis.append(vector.copy())
        candidate = omega * vector - beta_previous * previous
        diagonal = float(np.dot(vector, candidate))
        candidate -= diagonal * vector
        # Full reorthogonalization is cheap here and preserves positivity of
        # the subsequent Jacobi quadrature at high order.
        for direction in basis:
            candidate -= np.dot(direction, candidate) * direction
        alpha.append(diagonal)
        if level == order - 1:
            break
        next_beta = float(np.linalg.norm(candidate))
        if next_beta <= 1.0e-14:
            raise RuntimeError("spectral quadrature Lanczos terminated early")
        beta.append(next_beta)
        previous, vector = vector, candidate / next_beta
        beta_previous = next_beta
    jacobi = np.diag(alpha)
    jacobi += np.diag(beta, 1) + np.diag(beta, -1)
    nodes, eigenvectors = np.linalg.eigh(jacobi)
    compressed_weights = mass * eigenvectors[0] ** 2
    return nodes, compressed_weights, float(
        np.max(np.abs(eigenvectors.T @ eigenvectors - np.eye(order)))
    )


def _mori_star_structure(
    wave_numbers: np.ndarray,
    times: np.ndarray,
    bath_omega: np.ndarray,
    bath_weights: np.ndarray,
    *,
    current_norm: float,
    susceptibility: float,
    beta_zero_squared: float,
    regular_diffusion: float,
) -> np.ndarray:
    """Propagate the density component of a conservative Mori star."""

    wave_numbers = np.asarray(wave_numbers, dtype=float)
    times = np.asarray(times, dtype=float)
    bath_omega = np.asarray(bath_omega, dtype=float)
    bath_weights = np.asarray(bath_weights, dtype=float)
    beta_zero = np.sqrt(beta_zero_squared)
    size = 2 + 2 * bath_omega.size
    result = np.empty((times.size, wave_numbers.size), dtype=float)
    result[:, 0] = 1.0
    bath_coupling = beta_zero * np.sqrt(bath_weights)
    initial = np.zeros(size, dtype=float)
    initial[0] = 1.0
    equally_spaced_times = bool(
        times.size < 3
        or np.max(np.abs(np.diff(times) - np.diff(times)[0])) < 1.0e-12
    )
    if not equally_spaced_times:
        raise ValueError("sparse Mori-star propagation requires equally spaced times")
    for wave_index, wave_number in enumerate(wave_numbers[1:], start=1):
        lattice_wave_number = 2.0 * np.sin(0.5 * wave_number)
        density_current = (
            lattice_wave_number * np.sqrt(current_norm / susceptibility)
        )
        rows = [0, 1]
        columns = [1, 0]
        data = [-density_current, density_current]
        for bath_index, (frequency, coupling) in enumerate(
            zip(bath_omega, bath_coupling)
        ):
            x_index = 2 + 2 * bath_index
            y_index = x_index + 1
            rows.extend((1, x_index, x_index, y_index))
            columns.extend((x_index, 1, y_index, x_index))
            data.extend((-coupling, coupling, -frequency, frequency))
        generator = coo_matrix(
            (data, (rows, columns)), shape=(size, size), dtype=float
        ).tocsr()
        propagated = expm_multiply(
            generator,
            initial,
            start=float(times[0]),
            stop=float(times[-1]),
            num=int(times.size),
            endpoint=True,
            traceA=0.0,
        )
        conservative = np.asarray(propagated[:, 0], dtype=float)
        result[:, wave_index] = conservative * np.exp(
            -regular_diffusion * lattice_wave_number**2 * times
        )
    return result


def _wall_profiles(
    x: np.ndarray,
    wave_numbers: np.ndarray,
    structure: np.ndarray,
) -> np.ndarray:
    integrand = np.empty((x.size, wave_numbers.size), dtype=float)
    integrand[:, 0] = x
    integrand[:, 1:] = (
        np.sin(np.outer(x, wave_numbers[1:])) / wave_numbers[None, 1:]
    )
    profiles = np.trapezoid(
        integrand[None, :, :] * structure[:, None, :],
        wave_numbers,
        axis=2,
    ) / np.pi
    return profiles


def derive(args: argparse.Namespace) -> dict[str, object]:
    constraints = json.loads(args.constraints.read_text(encoding="utf-8"))
    boundary = json.loads(args.boundary.read_text(encoding="utf-8"))
    microscopic = constraints["microscopic_constraints"]
    even_moments = np.asarray(microscopic["even_moments"], dtype=float)
    low_amplitude = float(microscopic["low_density_amplitude"])
    omega, weights, entropy_diagnostics = _maximum_entropy_measure(
        even_moments,
        low_amplitude,
        omega_match=args.omega_match,
        omega_maximum=args.omega_maximum,
        integration_order=args.integration_order,
    )
    bath_omega, bath_weights, orthogonality_error = _gaussian_compress(
        omega, weights, args.bath_order
    )
    compressed_moments = np.asarray(
        [
            np.dot(bath_weights, bath_omega ** (2 * index))
            for index in range(even_moments.size)
        ]
    )

    times = np.arange(
        args.profile_start, args.profile_stop + 0.5 * args.dt, args.dt
    )
    wave_numbers = np.arange(
        0.0, args.k_maximum + 0.5 * args.k_step, args.k_step
    )
    slow = boundary["microscopic_slow_current"]
    if args.propagation_measure == "full":
        propagation_omega = omega
        propagation_weights = weights
    else:
        propagation_omega = bath_omega
        propagation_weights = bath_weights
    structure = _mori_star_structure(
        wave_numbers,
        times,
        propagation_omega,
        propagation_weights,
        current_norm=float(slow["norm"]),
        susceptibility=float(boundary["inputs"]["susceptibility"]),
        beta_zero_squared=float(slow["beta_zero_squared"]),
        regular_diffusion=args.regular_diffusion,
    )
    x = (
        np.arange(args.length, dtype=float) - 0.5 * (args.length - 1)
    ) * args.dx
    profiles = _wall_profiles(x, wave_numbers, structure)
    fit = fit_profiled_weak(
        x,
        times,
        profiles,
        t_window=(args.fit_start, args.fit_stop),
        x_crop=(args.x_crop[0], args.x_crop[1]),
        gamma=0.0,
    )
    return {
        "schema_version": 1,
        "method": "maximum_entropy_positive_QLQ_continuum_Mori_star_wall",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "inputs": {
            "constraints": str(args.constraints),
            "boundary": str(args.boundary),
            "length": args.length,
            "profile_window": [args.profile_start, args.profile_stop],
            "fit_window": [args.fit_start, args.fit_stop],
            "k_maximum": args.k_maximum,
            "k_step": args.k_step,
            "regular_diffusion": args.regular_diffusion,
            "propagation_measure": args.propagation_measure,
            "propagation_bath_size": int(propagation_omega.size),
        },
        "maximum_entropy_continuum": entropy_diagnostics,
        "gaussian_quadrature": {
            "order": args.bath_order,
            "nodes": bath_omega.tolist(),
            "weights": bath_weights.tolist(),
            "orthogonality_error": orthogonality_error,
            "compressed_even_moments": compressed_moments.tolist(),
            "maximum_relative_compressed_moment_error": float(
                np.max(np.abs(compressed_moments / even_moments - 1.0))
            ),
        },
        "structure_factor_diagnostics": {
            "minimum": float(np.min(structure)),
            "maximum": float(np.max(structure)),
            "k_zero_maximum_conservation_error": float(
                np.max(np.abs(structure[:, 0] - 1.0))
            ),
            "last_time_at_kmax": float(structure[-1, -1]),
        },
        "frozen_weak_projection": {
            "a": float(fit.a),
            "D": float(fit.D0),
            "mse": float(fit.mse),
            "n_obs": int(fit.n_obs),
        },
        "scope": {
            "exact_inputs": (
                "microscopic slow-current norm, beta0, five QLQ recurrents, "
                "and the absolute KPZ low-frequency spectral boundary"
            ),
            "closure_assumption": (
                "maximum relative entropy with Lebesgue reference measure "
                "on the unresolved positive-frequency continuum"
            ),
            "physical_F1_uniquely_proved": False,
            "constant_burgers_pair_is_projection_not_microscopic_constant": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--constraints",
        type=Path,
        default=ROOT / "docs/qlq_positive_spectral_interval_steps5.json",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=ROOT / "docs/qlq_kpz_low_frequency_boundary.json",
    )
    parser.add_argument("--omega-match", type=float, default=0.05)
    parser.add_argument("--omega-maximum", type=float, default=20.0)
    parser.add_argument("--integration-order", type=int, default=1200)
    parser.add_argument("--bath-order", type=int, default=48)
    parser.add_argument(
        "--propagation-measure",
        choices=("full", "gaussian"),
        default="full",
        help="Use the resolved maxent continuum or its finite Gaussian moment rule.",
    )
    parser.add_argument("--regular-diffusion", type=float, default=0.0)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=[-120.0, 120.0])
    parser.add_argument("--k-maximum", type=float, default=np.pi / 4.0)
    parser.add_argument("--k-step", type=float, default=0.01)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
