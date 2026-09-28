#!/usr/bin/env python3
r"""Propagate a finite-cutoff approximation to infinite-mode fluctuating GHD.

The retained variables are all string/rapidity occupations ``delta n_i``.
No scalar or two-pole closure is made.  Around a homogeneous TBA state the
implemented stochastic equation is

  d_t u_i + v_i d_x u_i + V_ij u_j d_x u_i
      = (1/2) D_ij d_x^2 u_j + d_x eta_i,

where ``D`` is the complete non-diagonal diffusion operator,
``<eta eta^T>=Q delta(x-x')delta(t-t')`` with the FDT matrix ``Q``, and
``V_ij=delta v_i^eff/delta n_j`` is obtained by differentiating dressing.

The linear Ornstein--Uhlenbeck part is stepped exactly in Fourier space.  A
dealiased Heun step treats the quadratic velocity vertex.  This is a
controlled finite-cutoff nonlinear tier, not a claim that the zero-field,
infinite-string limit or its finite-time ``F1_perp`` has converged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import expm


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_noise_frechet_derivatives,
    full_diffusion_operator_field,
)


def _psd_square_root(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    hermitian = 0.5 * (matrix + matrix.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    clipped_weight = float(np.sum(np.maximum(-eigenvalues, 0.0)) / scale)
    return (
        (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0)))
        @ eigenvectors.conj().T,
        clipped_weight,
    )


def _hermitian_gaussian(
    roots: np.ndarray,
    ensembles: int,
    rng: np.random.Generator,
    *,
    antithetic: bool = False,
) -> np.ndarray:
    """Draw Fourier fields with covariance ``roots[k] roots[k]^dagger``."""

    if antithetic:
        if ensembles % 2:
            raise ValueError("antithetic sampling requires an even ensemble count")
        half = _hermitian_gaussian(roots, ensembles // 2, rng)
        return np.concatenate((half, -half), axis=0)

    wave_count, mode_count, _ = roots.shape
    sample = np.zeros((ensembles, mode_count, wave_count), dtype=complex)
    sample[:, :, 0] = rng.normal(size=(ensembles, mode_count)) @ roots[0].T
    nyquist = wave_count // 2 if wave_count % 2 == 0 else None
    upper = (wave_count + 1) // 2
    for index in range(1, upper):
        standard = (
            rng.normal(size=(ensembles, mode_count))
            + 1j * rng.normal(size=(ensembles, mode_count))
        ) / np.sqrt(2.0)
        draw = standard @ roots[index].T
        sample[:, :, index] = draw
        sample[:, :, -index] = draw.conj()
    if nyquist is not None:
        # A pseudospectral first derivative does not have a real-valued
        # Nyquist representative.  The 2/3 rule removes this mode, so keep it
        # exactly zero rather than letting advection break Hermitian symmetry.
        sample[:, :, nyquist] = 0.0
    return sample


def _nonlinear_rhs(
    fourier_field: np.ndarray,
    wave_numbers: np.ndarray,
    velocity_vertex: np.ndarray,
    dealias_mask: np.ndarray,
    diffusion_vertex: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    filtered = fourier_field * dealias_mask[None, None, :]
    field = np.fft.ifft(filtered, axis=-1, norm="ortho").real
    gradient = np.fft.ifft(
        1j * wave_numbers[None, None, :] * filtered,
        axis=-1,
        norm="ortho",
    ).real
    velocity_shift = np.einsum("ij,ejx->eix", velocity_vertex, field)
    rhs_real = -velocity_shift * gradient
    if diffusion_vertex is not None:
        left_factors, matrix_factors = diffusion_vertex
        laplacian = np.fft.ifft(
            -(wave_numbers[None, None, :] ** 2) * filtered,
            axis=-1,
            norm="ortho",
        ).real
        amplitudes = np.einsum("lr,elx->erx", left_factors, field)
        responses = np.einsum(
            "rij,ejx->erix", matrix_factors, laplacian
        )
        rhs_real += 0.5 * np.einsum(
            "erx,erix->eix", amplitudes, responses
        )
    rhs = np.fft.fft(rhs_real, axis=-1, norm="ortho")
    return rhs * dealias_mask[None, None, :]


def _heun_nonlinear_step(
    field: np.ndarray,
    step: float,
    wave_numbers: np.ndarray,
    velocity_vertex: np.ndarray,
    dealias_mask: np.ndarray,
    diffusion_vertex: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    first = _nonlinear_rhs(
        field,
        wave_numbers,
        velocity_vertex,
        dealias_mask,
        diffusion_vertex,
    )
    predictor = field + step * first
    second = _nonlinear_rhs(
        predictor,
        wave_numbers,
        velocity_vertex,
        dealias_mask,
        diffusion_vertex,
    )
    return field + 0.5 * step * (first + second)


def _compress_frechet_tensor(
    tensor: np.ndarray,
    retained_fraction: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | int]]:
    """SVD-compress ``tensor[l,i,j]`` with a declared Frobenius error."""

    if not 0.0 < retained_fraction <= 1.0:
        raise ValueError("retained_fraction must lie in (0,1]")
    tensor = np.asarray(tensor)
    node_count = tensor.shape[0]
    flattened = tensor.reshape(node_count, -1)
    left, singular_values, right = np.linalg.svd(flattened, full_matrices=False)
    weights = singular_values**2
    cumulative = np.cumsum(weights) / np.sum(weights)
    rank = int(np.searchsorted(cumulative, retained_fraction) + 1)
    left_factors = left[:, :rank] * singular_values[:rank]
    matrix_factors = right[:rank].reshape(rank, *tensor.shape[1:])
    discarded = float(np.sqrt(max(1.0 - cumulative[rank - 1], 0.0)))
    return left_factors, matrix_factors, {
        "rank": rank,
        "retained_frobenius_fraction": float(cumulative[rank - 1]),
        "relative_discarded_frobenius_norm": discarded,
    }


def _spin_observable_fourier(
    occupation_fourier: np.ndarray,
    spin_projection: np.ndarray,
    spin_hessian: np.ndarray | None = None,
) -> np.ndarray:
    linear = np.einsum("i,eik->ek", spin_projection, occupation_fourier)
    if spin_hessian is None:
        return linear
    occupation = np.fft.ifft(
        occupation_fourier, axis=-1, norm="ortho"
    ).real
    quadratic = 0.5 * np.einsum(
        "ij,eix,ejx->ex", spin_hessian, occupation, occupation
    )
    return linear + np.fft.fft(quadratic, axis=-1, norm="ortho")


def _linear_ou_data(
    velocity: np.ndarray,
    diffusion: np.ndarray,
    covariance: np.ndarray,
    wave_numbers: np.ndarray,
    time_step: float,
    cell_length: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    transitions = []
    innovation_roots = []
    clipped = 0.0
    equilibrium = covariance / cell_length
    for wave_number in wave_numbers:
        generator = (
            -1j * wave_number * np.diag(velocity)
            - 0.5 * wave_number**2 * diffusion
        )
        transition = expm(time_step * generator)
        innovation = equilibrium - transition @ equilibrium @ transition.conj().T
        root, weight = _psd_square_root(innovation)
        transitions.append(transition)
        innovation_roots.append(root)
        clipped += weight
    return (
        np.asarray(transitions),
        np.asarray(innovation_roots),
        clipped,
    )


def propagate(
    *,
    field: float,
    xi_cutoff: float,
    xi_buffer: float,
    u_extent: float,
    rapidity_points: int,
    spatial_points: int,
    cell_length: float,
    time_step: float,
    output_times: np.ndarray,
    ensembles: int,
    seed: int,
    nonlinear_strength: float = 1.0,
    paired_linear_control: bool = False,
    antithetic: bool = False,
    diffusion_vertex_retained_fraction: float = 0.0,
) -> dict[str, object]:
    if spatial_points < 8 or spatial_points % 2:
        raise ValueError("spatial_points must be an even integer >= 8")
    if cell_length <= 0.0 or time_step <= 0.0:
        raise ValueError("cell_length and time_step must be positive")
    output_times = np.asarray(output_times, dtype=float)
    if output_times[0] != 0.0 or np.any(np.diff(output_times) <= 0.0):
        raise ValueError("output_times must start at zero and increase")
    output_steps_float = output_times / time_step
    output_steps = np.rint(output_steps_float).astype(int)
    if not np.allclose(output_steps_float, output_steps, atol=1.0e-10):
        raise ValueError("every output time must be an integer time_step multiple")

    modes = full_diffusion_operator_field(
        field,
        string_xi_cutoff=xi_cutoff,
        string_xi_buffer=xi_buffer,
        rapidity_u_extent=u_extent,
        rapidity_points=rapidity_points,
        string_boundary="robin",
    )
    velocity = np.asarray(modes["velocity"])
    diffusion = np.asarray(modes["diffusion_operator"])
    covariance = np.asarray(modes["static_covariance"])
    noise = np.asarray(modes["noise_covariance"])
    vertex = nonlinear_strength * np.asarray(modes["velocity_vertex"])
    spin = np.asarray(modes["spin_projection"])
    spin_hessian = np.asarray(modes["spin_hessian"])
    diffusion_vertex = None
    diffusion_vertex_report: dict[str, float | int] | None = None
    if diffusion_vertex_retained_fraction > 0.0:
        derivatives = full_diffusion_noise_frechet_derivatives(modes)
        left, matrices, diffusion_vertex_report = _compress_frechet_tensor(
            derivatives["diffusion_derivative"],
            diffusion_vertex_retained_fraction,
        )
        diffusion_vertex = (left, matrices)
    wave_numbers = 2.0 * np.pi * np.fft.fftfreq(
        spatial_points, d=cell_length
    )
    mode_indices = np.fft.fftfreq(spatial_points) * spatial_points
    dealias_mask = np.abs(mode_indices) <= spatial_points / 3.0

    transitions, innovation_roots, clipped = _linear_ou_data(
        velocity,
        diffusion,
        covariance,
        wave_numbers,
        time_step,
        cell_length,
    )
    equilibrium_root, equilibrium_clip = _psd_square_root(
        covariance / cell_length
    )
    equilibrium_roots = np.repeat(
        equilibrium_root[None, :, :], spatial_points, axis=0
    )
    rng = np.random.default_rng(seed)
    state = _hermitian_gaussian(
        equilibrium_roots, ensembles, rng, antithetic=antithetic
    )
    initial = state.copy()
    linear_control = state.copy() if paired_linear_control else None
    susceptibility = float(spin @ covariance @ spin / cell_length)
    initial_spin_linear = _spin_observable_fourier(initial, spin)
    initial_spin_physical = _spin_observable_fourier(
        initial, spin, spin_hessian
    )

    positive_indices = np.arange(1, spatial_points // 3 + 1)
    records: list[dict[str, object]] = []

    def record(time: float) -> None:
        initial_spin = initial_spin_physical
        current_spin = _spin_observable_fourier(state, spin, spin_hessian)
        correlation = np.mean(
            current_spin[:, positive_indices]
            * initial_spin[:, positive_indices].conj(),
            axis=0,
        ).real / susceptibility
        initial_variance = np.mean(
            np.abs(initial_spin[:, positive_indices]) ** 2, axis=0
        ).real / susceptibility
        current_variance = np.mean(
            np.abs(current_spin[:, positive_indices]) ** 2, axis=0
        ).real / susceptibility
        records.append(
            {
                "time": float(time),
                "positive_wave_numbers": wave_numbers[positive_indices].tolist(),
                "structure_factor_over_chi": correlation.tolist(),
                "structure_factor_normalized_by_empirical_t0": (
                    correlation / initial_variance
                ).tolist(),
                "equal_time_variance_over_chi": current_variance.tolist(),
            }
        )
        if linear_control is not None:
            control_spin = _spin_observable_fourier(
                linear_control, spin, spin_hessian
            )
            leading_control_spin = _spin_observable_fourier(
                linear_control, spin
            )
            control_samples = (
                control_spin[:, positive_indices]
                * initial_spin[:, positive_indices].conj()
            ).real / susceptibility
            leading_control_samples = (
                leading_control_spin[:, positive_indices]
                * initial_spin_linear[:, positive_indices].conj()
            ).real / susceptibility
            nonlinear_samples = (
                current_spin[:, positive_indices]
                * initial_spin[:, positive_indices].conj()
            ).real / susceptibility
            differences = nonlinear_samples - control_samples
            independent_differences = differences
            if antithetic:
                half = ensembles // 2
                independent_differences = 0.5 * (
                    differences[:half] + differences[half:]
                )
            control_correlation = np.mean(control_samples, axis=0)
            standard_error = (
                np.std(independent_differences, axis=0, ddof=1)
                / np.sqrt(independent_differences.shape[0])
                if independent_differences.shape[0] > 1
                else np.full(differences.shape[1], np.nan)
            )
            records[-1]["paired_linear_structure_factor_over_chi"] = (
                control_correlation.tolist()
            )
            records[-1]["leading_linear_structure_factor_over_chi"] = (
                np.mean(leading_control_samples, axis=0).tolist()
            )
            records[-1]["quadratic_observable_correction_over_chi"] = (
                np.mean(control_samples - leading_control_samples, axis=0).tolist()
            )
            records[-1]["nonlinear_minus_linear_over_chi"] = (
                np.mean(differences, axis=0).tolist()
            )
            records[-1]["total_physical_minus_leading_over_chi"] = (
                np.mean(nonlinear_samples - leading_control_samples, axis=0).tolist()
            )
            records[-1]["nonlinear_minus_linear_standard_error"] = (
                standard_error.tolist()
            )
            records[-1]["nonlinear_minus_linear_normalized_by_empirical_t0"] = (
                np.mean(differences, axis=0) / initial_variance
            ).tolist()

    record(0.0)
    requested = {int(step): float(time) for step, time in zip(output_steps, output_times)}
    half_step = 0.5 * time_step
    maximum_rms_occupation = 0.0
    for step_index in range(1, int(output_steps[-1]) + 1):
        state = _heun_nonlinear_step(
            state,
            half_step,
            wave_numbers,
            vertex,
            dealias_mask,
            diffusion_vertex,
        )
        state = np.einsum("kmn,enk->emk", transitions, state)
        innovation = _hermitian_gaussian(
            innovation_roots, ensembles, rng, antithetic=antithetic
        )
        state += innovation
        if linear_control is not None:
            linear_control = np.einsum(
                "kmn,enk->emk", transitions, linear_control
            )
            linear_control += innovation
        state = _heun_nonlinear_step(
            state,
            half_step,
            wave_numbers,
            vertex,
            dealias_mask,
            diffusion_vertex,
        )
        real_state = np.fft.ifft(state, axis=-1, norm="ortho").real
        maximum_rms_occupation = max(
            maximum_rms_occupation, float(np.sqrt(np.mean(real_state**2)))
        )
        if not np.all(np.isfinite(state)):
            raise FloatingPointError(
                f"non-finite state at step {step_index}; increase cell_length "
                "or reduce time_step"
            )
        if step_index in requested:
            record(requested[step_index])

    fdt_residual = np.linalg.norm(
        noise - 0.5 * (diffusion @ covariance + covariance @ diffusion.T)
    ) / max(np.linalg.norm(noise), np.finfo(float).tiny)
    variance_values = np.concatenate(
        [np.asarray(row["equal_time_variance_over_chi"]) for row in records]
    )
    return {
        "schema_version": 1,
        "inputs": {
            "field": field,
            "string_xi_cutoff": xi_cutoff,
            "string_xi_buffer": xi_buffer,
            "rapidity_u_extent": u_extent,
            "rapidity_points": rapidity_points,
            "spatial_points": spatial_points,
            "cell_length": cell_length,
            "time_step": time_step,
            "output_times": output_times.tolist(),
            "ensembles": ensembles,
            "seed": seed,
            "nonlinear_strength": nonlinear_strength,
            "paired_linear_control": paired_linear_control,
            "antithetic_sampling": antithetic,
            "diffusion_vertex_retained_fraction": (
                diffusion_vertex_retained_fraction
            ),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "operator": {
            "dimension": int(velocity.size),
            "active_strings": int(modes["active_strings"]),
            "full_off_diagonal_diffusion_retained": True,
            "full_fdt_noise_covariance_retained": True,
            "full_velocity_vertex_retained": True,
            "quadratic_dressed_spin_observable_retained": True,
            "diffusion_vertex": diffusion_vertex_report,
            "linear_noise_step": (
                "exact stationary OU innovation; algebraically identical to "
                "integrating k^2 Q because Q=(D C+C D^T)/2"
            ),
            "relative_fdt_identity_residual": float(fdt_residual),
            "ou_negative_spectral_weight_clipped": float(
                clipped + equilibrium_clip
            ),
        },
        "stability": {
            "maximum_rms_occupation_fluctuation": maximum_rms_occupation,
            "minimum_equal_time_variance_over_chi": float(
                np.min(variance_values)
            ),
            "maximum_equal_time_variance_over_chi": float(
                np.max(variance_values)
            ),
        },
        "structure_factor": records,
        "scope": {
            "finite_cutoff_nonlinear_fluctuating_ghd": True,
            "infinite_mode_limit_converged": False,
            "physical_F1_perp_claimed": False,
            "required_next_check": (
                "joint h->0, string-cutoff, rapidity-grid, spatial-grid, "
                "time-step, cell-volume and ensemble convergence"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", type=float, default=0.25)
    parser.add_argument("--xi-cutoff", type=float, default=0.75)
    parser.add_argument("--xi-buffer", type=float, default=0.75)
    parser.add_argument("--u-extent", type=float, default=1.5)
    parser.add_argument("--rapidity-points", type=int, default=16)
    parser.add_argument("--spatial-points", type=int, default=32)
    parser.add_argument("--cell-length", type=float, default=256.0)
    parser.add_argument("--time-step", type=float, default=0.02)
    parser.add_argument("--output-times", nargs="+", type=float, default=[0, 0.1, 0.2])
    parser.add_argument("--ensembles", type=int, default=16)
    parser.add_argument("--seed", type=int, default=265)
    parser.add_argument("--nonlinear-strength", type=float, default=1.0)
    parser.add_argument("--paired-linear-control", action="store_true")
    parser.add_argument("--antithetic", action="store_true")
    parser.add_argument(
        "--diffusion-vertex-retained-fraction", type=float, default=0.0
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = propagate(
        field=args.field,
        xi_cutoff=args.xi_cutoff,
        xi_buffer=args.xi_buffer,
        u_extent=args.u_extent,
        rapidity_points=args.rapidity_points,
        spatial_points=args.spatial_points,
        cell_length=args.cell_length,
        time_step=args.time_step,
        output_times=np.asarray(args.output_times),
        ensembles=args.ensembles,
        seed=args.seed,
        nonlinear_strength=args.nonlinear_strength,
        paired_linear_control=args.paired_linear_control,
        antithetic=args.antithetic,
        diffusion_vertex_retained_fraction=(
            args.diffusion_vertex_retained_fraction
        ),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
