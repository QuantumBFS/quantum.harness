#!/usr/bin/env python3
"""Close the exact XXX Mori prefix with its KPZ-compatible Freud continuum.

The full long-wave magnetization memory kernel has thirteen exact positive
Lanczos recurrents.  Its low-frequency spectral density is fixed absolutely
by the giant-string KPZ current tail.  To obtain a target-free finite-time
estimate, this script appends the minimal symmetric Freud-class terminator

    rho_T(omega) = c*omega**(1/3)*exp(-(omega/Omega)**2),  omega > 0.

Linear growth of the observed microscopic squared recurrents selects the
Gaussian Freud exponent two.  Unit spectral mass and the exact KPZ boundary
then fix ``c`` and ``Omega``; there is no parameter fitted to a trajectory or
to the desired Burgers pair.  The terminator is inserted behind the complete
mu_26 prefix, the resulting positive full-current spectrum is cosine
transformed, and the exact scalar Mori equation is propagated before applying
the frozen weak estimator.

This is a definite analytic closure estimate.  It is not an identity: the
Freud tail is an asymptotic regularity assumption for the unknown recurrents.
Regulator and closure-family variation must therefore accompany the result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import mpmath as mp
import numpy as np
from scipy.special import gamma


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    xxx_mori_even_moments,
    xxx_mori_long_wave_lanczos,
)
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _exact_even_moments() -> np.ndarray:
    finite = xxx_mori_even_moments(np.asarray(0.0))
    long_wave = xxx_mori_long_wave_lanczos()
    return np.asarray(
        [float(finite[2 * index]) for index in range(9)]
        + [float(long_wave[f"mu{2 * index}"]) for index in range(9, 14)]
    )


def _alternating_low_amplitude(
    terminator_amplitude: float, squared_recurrents: np.ndarray
) -> tuple[float, float]:
    amplitude = float(terminator_amplitude)
    exponent = 1.0 / 3.0
    for recurrent in np.asarray(squared_recurrents, dtype=float)[::-1]:
        amplitude = 1.0 / (recurrent * amplitude)
        exponent = -exponent
    return amplitude, exponent


def _freud_scale(
    normalized_kernel_laplace_amplitude: float,
    squared_recurrents: np.ndarray,
) -> dict[str, float]:
    prefix_factor, final_exponent = _alternating_low_amplitude(
        1.0, squared_recurrents
    )
    if abs(final_exponent + 1.0 / 3.0) > 1.0e-14:
        raise RuntimeError("the recurrent prefix has the wrong parity")
    terminator_resolvent_amplitude = (
        prefix_factor / normalized_kernel_laplace_amplitude
    )
    # Unit mass for c*w^(1/3)*exp[-(w/Omega)^2] gives
    # c=2/(Omega^(4/3)*Gamma(2/3)); its Stieltjes amplitude is c*pi/sqrt(3).
    omega_scale = (
        2.0
        * np.pi
        / (
            np.sqrt(3.0)
            * gamma(2.0 / 3.0)
            * terminator_resolvent_amplitude
        )
    ) ** (3.0 / 4.0)
    density_amplitude = 2.0 / (
        omega_scale ** (4.0 / 3.0) * gamma(2.0 / 3.0)
    )
    return {
        "prefix_alternating_factor": float(prefix_factor),
        "normalized_kernel_laplace_amplitude": float(
            normalized_kernel_laplace_amplitude
        ),
        "terminator_resolvent_amplitude": float(
            terminator_resolvent_amplitude
        ),
        "terminator_density_amplitude": float(density_amplitude),
        "omega_scale": float(omega_scale),
    }


def _terminator_stieltjes(z: complex, omega_scale: float) -> complex:
    """Unit-mass Freud terminator Stieltjes transform at complex ``z``."""

    z_mp = mp.mpc(z)
    scale = mp.mpf(omega_scale)
    b = (z_mp / scale) ** 2
    return complex(
        z_mp
        / scale**2
        * b ** (-mp.mpf(1) / 3)
        * mp.exp(b)
        * mp.gammainc(mp.mpf(1) / 3, b, mp.inf)
    )


def _full_kernel_density(
    omega: np.ndarray,
    *,
    omega_scale: float,
    mu0: float,
    squared_recurrents: np.ndarray,
    boundary_epsilon: float,
) -> np.ndarray:
    density = np.empty_like(omega)
    mp.mp.dps = 30
    for index, frequency in enumerate(omega):
        z = complex(boundary_epsilon, frequency)
        continued = _terminator_stieltjes(z, omega_scale)
        for recurrent in np.asarray(squared_recurrents, dtype=float)[::-1]:
            continued = 1.0 / (z + recurrent * continued)
        density[index] = mu0 * (2.0 / np.pi) * continued.real
    if np.any(~np.isfinite(density)) or np.min(density) < -1.0e-9:
        raise RuntimeError("continued-fraction boundary is not a positive density")
    return np.maximum(density, 0.0)


def _kernel_time_grid(
    omega: np.ndarray,
    spectral_weight: np.ndarray,
    times: np.ndarray,
    *,
    exact_mu0: float,
    chunk_size: int = 512,
) -> np.ndarray:
    kernel = np.zeros_like(times)
    for start in range(0, omega.size, chunk_size):
        stop = min(start + chunk_size, omega.size)
        kernel += np.cos(np.outer(times, omega[start:stop])) @ spectral_weight[
            start:stop
        ]
    # The high-frequency tail has negligible effect for t>0 but carries a
    # visible fraction of K(0).  Enforce the exact contact value only at t=0.
    kernel[0] = exact_mu0
    return kernel


def _solve_mori_volterra(
    kernel: np.ndarray, times: np.ndarray, wave_numbers: np.ndarray
) -> np.ndarray:
    """Second-order trapezoidal solution of F'=-khat^2 K*F."""

    dt = float(times[1] - times[0])
    if np.max(np.abs(np.diff(times) - dt)) > 1.0e-12:
        raise ValueError("Mori time grid must be uniform")
    khat_squared = (2.0 * np.sin(0.5 * wave_numbers)) ** 2
    structure = np.ones((times.size, wave_numbers.size), dtype=float)
    convolution = np.zeros(wave_numbers.size, dtype=float)
    denominator = 1.0 + 0.25 * dt**2 * khat_squared * kernel[0]
    for time_index in range(1, times.size):
        if time_index == 1:
            interior = np.zeros(wave_numbers.size)
        else:
            interior = kernel[1:time_index][::-1] @ structure[1:time_index]
        known_convolution = dt * (
            interior + 0.5 * kernel[time_index] * structure[0]
        )
        current = (
            structure[time_index - 1]
            - 0.5
            * dt
            * khat_squared
            * (known_convolution + convolution)
        ) / denominator
        structure[time_index] = current
        convolution = known_convolution + 0.5 * dt * kernel[0] * current
    return structure


def _wall_profiles(
    x: np.ndarray, wave_numbers: np.ndarray, structure: np.ndarray
) -> np.ndarray:
    basis = np.empty((x.size, wave_numbers.size), dtype=float)
    basis[:, 0] = x
    basis[:, 1:] = (
        np.sin(np.outer(x, wave_numbers[1:])) / wave_numbers[None, 1:]
    )
    return np.trapezoid(
        structure[:, None, :] * basis[None, :, :], wave_numbers, axis=2
    ) / np.pi


def derive(args: argparse.Namespace) -> dict[str, object]:
    boundary = json.loads(args.boundary.read_text(encoding="utf-8"))
    current_tail_laplace = float(
        boundary["kpz"]["current_tail"]["laplace_amplitude"]
    )
    susceptibility = float(boundary["inputs"]["susceptibility"])
    lanczos = xxx_mori_long_wave_lanczos()
    mu0 = float(lanczos["mu0"])
    squared_recurrents = np.asarray(
        lanczos["squared_recurrents"], dtype=float
    )
    normalized_amplitude = current_tail_laplace / susceptibility / mu0
    freud = _freud_scale(normalized_amplitude, squared_recurrents)

    # Midpoint cells integrate the omega^(-1/3) endpoint without evaluating
    # the integrable singularity at zero.
    omega = (
        np.arange(int(np.ceil(args.omega_maximum / args.omega_step))) + 0.5
    ) * args.omega_step
    density = _full_kernel_density(
        omega,
        omega_scale=freud["omega_scale"],
        mu0=mu0,
        squared_recurrents=squared_recurrents,
        boundary_epsilon=args.boundary_epsilon,
    )
    spectral_weight = density * args.omega_step
    exact_moments = _exact_even_moments()
    reconstructed_moments = np.asarray(
        [
            np.dot(spectral_weight, omega ** (2 * order))
            for order in range(exact_moments.size)
        ]
    )

    all_times = np.arange(0.0, args.profile_stop + 0.5 * args.dt, args.dt)
    kernel = _kernel_time_grid(
        omega, spectral_weight, all_times, exact_mu0=mu0
    )
    wave_numbers = np.arange(
        0.0, args.k_maximum + 0.5 * args.k_step, args.k_step
    )
    structure = _solve_mori_volterra(kernel, all_times, wave_numbers)
    select = all_times >= args.profile_start - 1.0e-12
    profile_times = all_times[select]
    x = (
        np.arange(args.length, dtype=float) - 0.5 * (args.length - 1)
    ) * args.dx
    profiles = _wall_profiles(x, wave_numbers, structure[select])
    fit = fit_profiled_weak(
        x,
        profile_times,
        profiles,
        t_window=(args.fit_start, args.fit_stop),
        x_crop=(args.x_crop[0], args.x_crop[1]),
        gamma=0.0,
    )
    positive_moment_mask = reconstructed_moments > 1.0e-300
    moment_relative_error = np.full_like(exact_moments, np.nan)
    moment_relative_error[positive_moment_mask] = (
        reconstructed_moments[positive_moment_mask]
        / exact_moments[positive_moment_mask]
        - 1.0
    )
    return {
        "schema_version": 1,
        "method": "mu26_exact_prefix_with_KPZ_matched_Freud_terminator",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "inputs": {
            "boundary": str(args.boundary),
            "length": args.length,
            "profile_window": [args.profile_start, args.profile_stop],
            "fit_window": [args.fit_start, args.fit_stop],
            "dt": args.dt,
            "k_maximum": args.k_maximum,
            "k_step": args.k_step,
            "omega_maximum": args.omega_maximum,
            "omega_step": args.omega_step,
            "boundary_epsilon": args.boundary_epsilon,
        },
        "exact_microscopic_constraints": {
            "mu0": mu0,
            "maximum_even_moment": 26,
            "even_moments": exact_moments.tolist(),
            "squared_recurrents": squared_recurrents.tolist(),
            "KPZ_kernel_laplace_amplitude": current_tail_laplace
            / susceptibility,
        },
        "freud_terminator": {
            **freud,
            "density": "c*omega^(1/3)*exp[-(omega/Omega)^2]",
            "exponent_selected_from": (
                "asymptotically linear growth of squared Lanczos recurrents"
            ),
            "free_fitted_parameters": 0,
        },
        "spectral_diagnostics": {
            "minimum_density": float(np.min(density)),
            "resolved_mass": float(np.sum(spectral_weight)),
            "reconstructed_even_moments": reconstructed_moments.tolist(),
            "relative_even_moment_error": moment_relative_error.tolist(),
            "kernel_at_first_positive_time": float(kernel[1]),
            "kernel_minimum": float(np.min(kernel)),
            "kernel_maximum": float(np.max(kernel)),
        },
        "structure_factor_diagnostics": {
            "minimum": float(np.min(structure)),
            "maximum": float(np.max(structure)),
            "k_zero_conservation_error": float(
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
            "exact": (
                "mu0..mu26 prefix, positivity, continuity/KPZ low-frequency "
                "amplitude, and exact scalar Mori propagation"
            ),
            "closure_assumption": (
                "the unknown recurrent tail belongs to the p=2 Freud class"
            ),
            "physical_F1_uniquely_proved": False,
            "result_is_target_free_closure_estimate": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--boundary",
        type=Path,
        default=ROOT / "docs/qlq_kpz_low_frequency_boundary.json",
    )
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=[-120.0, 120.0])
    parser.add_argument("--k-maximum", type=float, default=1.2)
    parser.add_argument("--k-step", type=float, default=0.01)
    parser.add_argument("--omega-maximum", type=float, default=16.0)
    parser.add_argument("--omega-step", type=float, default=0.004)
    parser.add_argument("--boundary-epsilon", type=float, default=1.0e-10)
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
