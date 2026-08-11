"""Many-body Chern number and polarization winding."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import time

import numpy as np
from quspin.operators import hamiltonian

from .diagonalization import EDEngine


@dataclass(frozen=True)
class FHSDiagnostics:
    chern_raw: float
    chern_integer: int
    integer_deviation: float
    minimum_overlap: float
    maximum_link_modulus_error: float
    maximum_absolute_flux: float
    flux: np.ndarray


def compute_fhs(
    states: np.ndarray,
    overlap_threshold: float = 1e-12,
    admissibility_margin: float = 1e-8,
) -> FHSDiagnostics:
    """Compute oriented FHS fluxes for `(theta, phi, basis)` states."""
    state_array = np.asarray(states, dtype=np.complex128)
    if state_array.ndim != 3 or min(state_array.shape[:2]) < 2:
        raise ValueError(
            "states must have shape (N_theta, N_phi, basis_dimension)"
        )

    theta_neighbor = np.roll(state_array, -1, axis=0)
    phi_neighbor = np.roll(state_array, -1, axis=1)
    theta_overlap = np.einsum(
        "mni,mni->mn",
        state_array.conj(),
        theta_neighbor,
    )
    phi_overlap = np.einsum(
        "mni,mni->mn",
        state_array.conj(),
        phi_neighbor,
    )
    magnitudes = np.concatenate(
        (np.abs(theta_overlap).ravel(), np.abs(phi_overlap).ravel())
    )
    if not np.all(np.isfinite(magnitudes)) or np.min(magnitudes) <= overlap_threshold:
        raise ValueError("neighbor overlap is non-finite or below threshold")

    u_theta = theta_overlap / np.abs(theta_overlap)
    u_phi = phi_overlap / np.abs(phi_overlap)
    plaquette = (
        u_theta
        * np.roll(u_phi, -1, axis=0)
        * np.conj(np.roll(u_theta, -1, axis=1))
        * np.conj(u_phi)
    )
    flux = np.angle(plaquette)
    maximum_absolute_flux = float(np.max(np.abs(flux)))
    if maximum_absolute_flux >= np.pi - admissibility_margin:
        raise ValueError("plaquette flux reaches the principal-branch boundary")

    chern_raw = float(np.sum(flux) / (2.0 * np.pi))
    chern_integer = round(chern_raw)
    maximum_link_modulus_error = float(
        max(
            np.max(np.abs(np.abs(u_phi) - 1.0)),
            np.max(np.abs(np.abs(u_theta) - 1.0)),
        )
    )
    return FHSDiagnostics(
        chern_raw=chern_raw,
        chern_integer=chern_integer,
        integer_deviation=abs(chern_raw - chern_integer),
        minimum_overlap=float(np.min(magnitudes)),
        maximum_link_modulus_error=maximum_link_modulus_error,
        maximum_absolute_flux=maximum_absolute_flux,
        flux=flux,
    )


@dataclass(frozen=True)
class ChernGridResult:
    N_theta: int
    N_phi: int
    states: np.ndarray
    ground_state_energies: np.ndarray
    first_excited_energies: np.ndarray
    gaps: np.ndarray
    hermiticity_errors: np.ndarray
    residuals: np.ndarray
    basis_fingerprint: str
    fhs: FHSDiagnostics
    minimum_gap: float
    theta_at_minimum_gap: float
    phi_at_minimum_gap: float
    maximum_hermiticity_error: float
    maximum_residual: float
    new_diagonalizations: int
    total_diagonalizations: int
    wall_time_s: float

    def as_dict(self) -> dict[str, float | int | bool]:
        return {
            "N_theta": self.N_theta,
            "N_phi": self.N_phi,
            "C_raw": self.fhs.chern_raw,
            "C_rounded": self.fhs.chern_integer,
            "chern_error": self.fhs.integer_deviation,
            "gap_min": self.minimum_gap,
            "theta_gap_min": self.theta_at_minimum_gap,
            "phi_gap_min": self.phi_at_minimum_gap,
            "min_link_overlap": self.fhs.minimum_overlap,
            "max_abs_berry_curvature": self.fhs.maximum_absolute_flux,
            "maximum_link_modulus_error": self.fhs.maximum_link_modulus_error,
            "solver_residual": self.maximum_residual,
            "converged": self.fhs.integer_deviation < 1e-3,
            "diagonalization_count": self.new_diagonalizations,
            "total_diagonalizations": self.total_diagonalizations,
            "wall_time_s": self.wall_time_s,
        }


def scan_chern(
    engine: EDEngine,
    *,
    n_theta: int,
    n_phi: int,
    overlap_threshold: float = 1e-12,
) -> ChernGridResult:
    """Compute a many-body Chern number on a periodic torus grid."""
    if n_theta < 2 or n_phi < 2:
        raise ValueError("grid dimensions must be at least 2")
    start = time.perf_counter()
    before = engine.diagonalization_count
    states = np.empty((n_theta, n_phi, engine.basis.Ns), dtype=np.complex128)
    e0 = np.empty((n_theta, n_phi), dtype=np.float64)
    e1 = np.empty_like(e0)
    hermiticity = np.empty_like(e0)
    residuals = np.empty_like(e0)

    for theta_index in range(n_theta):
        for phi_index in range(n_phi):
            vertex = engine.vertex(
                Fraction(theta_index, n_theta),
                Fraction(phi_index, n_phi),
            )
            states[theta_index, phi_index] = vertex.state
            e0[theta_index, phi_index] = vertex.energies[0]
            e1[theta_index, phi_index] = vertex.energies[1]
            hermiticity[theta_index, phi_index] = vertex.hermiticity_error
            residuals[theta_index, phi_index] = vertex.residual

    gaps = e1 - e0
    minimum_index = np.unravel_index(np.argmin(gaps), gaps.shape)
    return ChernGridResult(
        N_theta=n_theta,
        N_phi=n_phi,
        states=states,
        ground_state_energies=e0,
        first_excited_energies=e1,
        gaps=gaps,
        hermiticity_errors=hermiticity,
        residuals=residuals,
        basis_fingerprint=hashlib.sha256(engine.basis.states.tobytes()).hexdigest(),
        fhs=compute_fhs(states, overlap_threshold=overlap_threshold),
        minimum_gap=float(gaps[minimum_index]),
        theta_at_minimum_gap=2.0 * np.pi * minimum_index[0] / n_theta,
        phi_at_minimum_gap=2.0 * np.pi * minimum_index[1] / n_phi,
        maximum_hermiticity_error=float(np.max(hermiticity)),
        maximum_residual=float(np.max(residuals)),
        new_diagonalizations=engine.diagonalization_count - before,
        total_diagonalizations=engine.diagonalization_count,
        wall_time_s=time.perf_counter() - start,
    )


def verify_gauge_invariance(
    result: ChernGridResult,
    seed: int = 20260728,
) -> float:
    """Return the largest FHS change under independent grid-point phases."""
    rng = np.random.default_rng(seed)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=result.states.shape[:2])
    transformed = compute_fhs(result.states * np.exp(1j * phases)[:, :, None])
    return float(
        max(
            np.max(np.abs(transformed.flux - result.fhs.flux)),
            abs(transformed.chern_raw - result.fhs.chern_raw),
        )
    )


@dataclass(frozen=True)
class PolarizationResult:
    resta_values: np.ndarray
    polarization: np.ndarray
    charge: float
    minimum_resta_modulus: float


@dataclass(frozen=True)
class WilsonLoopPolarizationResult:
    wilson_loops: np.ndarray
    polarization: np.ndarray
    charge: float
    minimum_overlap: float


@dataclass(frozen=True)
class FixedTwistChargeResult:
    cumulative_charge: np.ndarray
    charge: float
    strip_flux: np.ndarray
    theta_width: float
    minimum_overlap: float
    maximum_absolute_flux: float


@dataclass(frozen=True)
class FixedTwistAdiabaticChargeResult(FixedTwistChargeResult):
    phi: np.ndarray
    states: np.ndarray
    maximum_residual: float
    new_diagonalizations: int
    n_phi: int
    theta_fraction: Fraction


@dataclass(frozen=True)
class FixedTwistConvergenceResult:
    result: FixedTwistAdiabaticChargeResult
    phi_charge_error: float
    phi_curve_max_error: float
    theta_curve_error: float
    refinement_count: int


def fixed_twist_charge_from_states(
    states: np.ndarray,
    *,
    theta_width: float,
    overlap_threshold: float = 1e-12,
) -> FixedTwistChargeResult:
    """Integrate Berry flux across a narrow twist strip.

    ``states`` has shape ``(2, N_phi, basis_dimension)``. The first axis
    contains the lower and upper twist boundaries in that order.
    """
    state_array = np.asarray(states, dtype=np.complex128)
    if state_array.ndim != 3 or state_array.shape[0] != 2 or state_array.shape[1] < 2:
        raise ValueError("states must have shape (2, N_phi, basis_dimension)")
    if not np.isfinite(theta_width) or theta_width <= 0.0:
        raise ValueError("theta_width must be positive and finite")

    lower, upper = state_array
    lower_next = np.roll(lower, -1, axis=0)
    upper_next = np.roll(upper, -1, axis=0)
    theta_overlap = np.einsum("ni,ni->n", lower.conj(), upper)
    lower_phi_overlap = np.einsum("ni,ni->n", lower.conj(), lower_next)
    upper_phi_overlap = np.einsum("ni,ni->n", upper.conj(), upper_next)
    theta_next_overlap = np.roll(theta_overlap, -1)
    overlaps = np.concatenate(
        (
            np.abs(theta_overlap),
            np.abs(lower_phi_overlap),
            np.abs(upper_phi_overlap),
        )
    )
    if not np.all(np.isfinite(overlaps)) or np.min(overlaps) <= overlap_threshold:
        raise ValueError("strip neighbor overlap is non-finite or below threshold")

    plaquette = (
        theta_overlap / np.abs(theta_overlap)
        * upper_phi_overlap / np.abs(upper_phi_overlap)
        * np.conj(theta_next_overlap / np.abs(theta_next_overlap))
        * np.conj(lower_phi_overlap / np.abs(lower_phi_overlap))
    )
    flux = np.angle(plaquette)
    cumulative = np.concatenate(([0.0], np.cumsum(flux / theta_width)))
    return FixedTwistChargeResult(
        cumulative_charge=cumulative,
        charge=float(cumulative[-1]),
        strip_flux=flux,
        theta_width=float(theta_width),
        minimum_overlap=float(np.min(overlaps)),
        maximum_absolute_flux=float(np.max(np.abs(flux))),
    )


def compute_fixed_twist_adiabatic_charge(
    engine: EDEngine,
    *,
    n_phi: int,
    theta_fraction: Fraction = Fraction(1, 256),
    direction: int = 1,
    overlap_threshold: float = 1e-12,
) -> FixedTwistAdiabaticChargeResult:
    """Compute the adiabatic boundary charge at twist ``theta=0``."""
    if not isinstance(n_phi, int) or isinstance(n_phi, bool) or n_phi < 2:
        raise ValueError("n_phi must be an integer of at least 2")
    if not isinstance(theta_fraction, Fraction):
        raise TypeError("theta_fraction must be a Fraction")
    if theta_fraction <= 0 or theta_fraction >= Fraction(1, 2):
        raise ValueError("theta_fraction must lie between zero and one half")
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")

    before = engine.diagonalization_count
    states = np.empty((2, n_phi, engine.basis.Ns), dtype=np.complex128)
    residuals = np.empty((2, n_phi), dtype=np.float64)
    theta_coordinates = (-theta_fraction / 2, theta_fraction / 2)
    for theta_index, theta in enumerate(theta_coordinates):
        for phi_index in range(n_phi):
            vertex = engine.vertex(theta, direction * Fraction(phi_index, n_phi))
            states[theta_index, phi_index] = vertex.state
            residuals[theta_index, phi_index] = vertex.residual

    theta_width = 2.0 * np.pi * float(theta_fraction)
    charge = fixed_twist_charge_from_states(
        states,
        theta_width=theta_width,
        overlap_threshold=overlap_threshold,
    )
    return FixedTwistAdiabaticChargeResult(
        cumulative_charge=charge.cumulative_charge,
        charge=charge.charge,
        strip_flux=charge.strip_flux,
        theta_width=charge.theta_width,
        minimum_overlap=charge.minimum_overlap,
        maximum_absolute_flux=charge.maximum_absolute_flux,
        phi=direction * np.linspace(0.0, 2.0 * np.pi, n_phi + 1),
        states=states,
        maximum_residual=float(np.max(residuals)),
        new_diagonalizations=engine.diagonalization_count - before,
        n_phi=n_phi,
        theta_fraction=theta_fraction,
    )


def converge_fixed_twist_adiabatic_charge(
    engine: EDEngine,
    *,
    n_phi: int = 20,
    theta_fraction: Fraction = Fraction(1, 64),
    curve_tolerance: float = 2e-2,
    max_refinements: int = 3,
    direction: int = 1,
    overlap_threshold: float = 1e-12,
) -> FixedTwistConvergenceResult:
    """Refine both the path grid and the centered twist-strip width."""
    if not np.isfinite(curve_tolerance) or curve_tolerance <= 0.0:
        raise ValueError("curve_tolerance must be positive and finite")
    if not isinstance(max_refinements, int) or max_refinements < 1:
        raise ValueError("max_refinements must be a positive integer")

    coarse = compute_fixed_twist_adiabatic_charge(
        engine,
        n_phi=n_phi,
        theta_fraction=theta_fraction,
        direction=direction,
        overlap_threshold=overlap_threshold,
    )
    for refinement in range(1, max_refinements + 1):
        fine_phi = compute_fixed_twist_adiabatic_charge(
            engine,
            n_phi=coarse.n_phi * 2,
            theta_fraction=coarse.theta_fraction,
            direction=direction,
            overlap_threshold=overlap_threshold,
        )
        fine = compute_fixed_twist_adiabatic_charge(
            engine,
            n_phi=fine_phi.n_phi,
            theta_fraction=coarse.theta_fraction / 2,
            direction=direction,
            overlap_threshold=overlap_threshold,
        )
        coarse_coordinate = np.linspace(0.0, 1.0, coarse.n_phi + 1)
        fine_coordinate = np.linspace(0.0, 1.0, fine.n_phi + 1)
        coarse_on_fine = np.interp(
            fine_coordinate,
            coarse_coordinate,
            coarse.cumulative_charge,
        )
        phi_curve_max_error = float(
            np.max(np.abs(fine_phi.cumulative_charge - coarse_on_fine))
        )
        phi_charge_error = abs(fine_phi.charge - coarse.charge)
        theta_error = float(
            np.max(
                np.abs(fine.cumulative_charge - fine_phi.cumulative_charge)
            )
        )
        if max(phi_charge_error, theta_error) <= curve_tolerance:
            return FixedTwistConvergenceResult(
                result=fine,
                phi_charge_error=phi_charge_error,
                phi_curve_max_error=phi_curve_max_error,
                theta_curve_error=theta_error,
                refinement_count=refinement,
            )
        coarse = fine
    raise RuntimeError(
        "fixed-twist adiabatic charge did not converge after "
        f"{max_refinements} refinements: phi_charge_error="
        f"{phi_charge_error:.6g}, theta_curve_error={theta_error:.6g}"
    )


def wilson_loop_polarization(
    states: np.ndarray,
    *,
    overlap_threshold: float = 1e-12,
) -> WilsonLoopPolarizationResult:
    """Return twist Wilson-loop polarization for `(theta, phi, basis)` states."""
    state_array = np.asarray(states, dtype=np.complex128)
    if state_array.ndim != 3 or min(state_array.shape[:2]) < 2:
        raise ValueError(
            "states must have shape (N_theta, N_phi, basis_dimension)"
        )
    overlaps = np.einsum(
        "mni,mni->mn",
        state_array.conj(),
        np.roll(state_array, -1, axis=0),
    )
    magnitudes = np.abs(overlaps)
    if not np.all(np.isfinite(magnitudes)) or np.min(magnitudes) <= overlap_threshold:
        raise ValueError("theta-neighbor overlap is non-finite or below threshold")
    wilson_loops = np.prod(overlaps / magnitudes, axis=0)
    fhs = compute_fhs(state_array, overlap_threshold=overlap_threshold)
    increments = np.sum(fhs.flux, axis=0) / (2.0 * np.pi)
    polarization = np.empty(wilson_loops.size + 1, dtype=np.float64)
    polarization[0] = -np.angle(wilson_loops[0]) / (2.0 * np.pi)
    polarization[1:] = polarization[0] + np.cumsum(increments)
    return WilsonLoopPolarizationResult(
        wilson_loops=wilson_loops,
        polarization=polarization,
        charge=float(polarization[-1] - polarization[0]),
        minimum_overlap=float(np.min(magnitudes)),
    )


@dataclass(frozen=True)
class AdiabaticChargeResult(PolarizationResult):
    phi: np.ndarray
    states: np.ndarray
    maximum_residual: float
    new_diagonalizations: int
    n_phi: int
    refinement_count: int
    charge_convergence_error: float


def _position_phase(basis, L: int) -> np.ndarray:
    position_terms = [[float(site), site] for site in range(L)]
    position = hamiltonian(
        [["n|", position_terms], ["|n", position_terms]],
        [],
        basis=basis,
        dtype=np.float64,
        check_herm=False,
        check_symm=False,
        check_pcon=False,
    )
    diagonal = np.asarray(position.diagonal(), dtype=np.float64)
    return np.exp(2j * np.pi * diagonal / L)


def polarization_from_states(
    basis,
    L: int,
    states: np.ndarray,
    *,
    overlap_threshold: float = 1e-10,
) -> PolarizationResult:
    """Return the continuous Resta polarization and its winding."""
    state_array = np.asarray(states, dtype=np.complex128)
    if state_array.ndim != 2 or state_array.shape[1] != basis.Ns:
        raise ValueError("states must have shape (samples, basis_dimension)")
    norms = np.linalg.norm(state_array, axis=1)
    if not np.all(np.isfinite(state_array)) or not np.allclose(
        norms,
        1.0,
        atol=1e-10,
    ):
        raise ValueError("states must be finite and normalized")

    phase = _position_phase(basis, L)
    resta_values = np.einsum("ij,j,ij->i", state_array.conj(), phase, state_array)
    minimum_modulus = float(np.min(np.abs(resta_values)))
    if not np.isfinite(minimum_modulus) or minimum_modulus <= overlap_threshold:
        raise ValueError("Resta polarization is ill-defined: overlap is too small")

    phase_steps = np.angle(resta_values[1:] * resta_values[:-1].conj())
    first_phase = np.angle(resta_values[0])
    unwrapped_phase = np.concatenate(
        ([first_phase], first_phase + np.cumsum(phase_steps))
    )
    polarization = unwrapped_phase / (2.0 * np.pi)
    return PolarizationResult(
        resta_values=resta_values,
        polarization=polarization,
        charge=float(polarization[-1] - polarization[0]),
        minimum_resta_modulus=minimum_modulus,
    )


def _adiabatic_fixed_grid(
    engine: EDEngine,
    *,
    n_phi: int,
    direction: int,
    overlap_threshold: float,
) -> AdiabaticChargeResult:
    before = engine.diagonalization_count
    states = np.empty((n_phi + 1, engine.basis.Ns), dtype=np.complex128)
    residuals = np.empty(n_phi + 1, dtype=np.float64)
    for index in range(n_phi + 1):
        vertex = engine.vertex(Fraction(0), direction * Fraction(index, n_phi))
        states[index] = vertex.state
        residuals[index] = vertex.residual

    result = polarization_from_states(
        engine.basis,
        engine.model.L,
        states,
        overlap_threshold=overlap_threshold,
    )
    return AdiabaticChargeResult(
        resta_values=result.resta_values,
        polarization=result.polarization,
        charge=result.charge,
        minimum_resta_modulus=result.minimum_resta_modulus,
        phi=direction * np.linspace(0.0, 2.0 * np.pi, n_phi + 1),
        states=states,
        maximum_residual=float(np.max(residuals)),
        new_diagonalizations=engine.diagonalization_count - before,
        n_phi=n_phi,
        refinement_count=0,
        charge_convergence_error=float("inf"),
    )


def compute_adiabatic_charge(
    engine: EDEngine,
    *,
    n_phi: int = 40,
    direction: int = 1,
    overlap_threshold: float = 1e-10,
    charge_tolerance: float = 1e-8,
    max_refinements: int = 4,
    minimum_converged_points: int = 16,
) -> AdiabaticChargeResult:
    """Refine endpoint-inclusive ground-state paths until winding is stable."""
    if n_phi < 2:
        raise ValueError("n_phi must be at least 2")
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    if charge_tolerance <= 0.0 or max_refinements < 1:
        raise ValueError("charge_tolerance and max_refinements must be positive")
    if minimum_converged_points < 2:
        raise ValueError("minimum_converged_points must be at least 2")

    before = engine.diagonalization_count
    coarse = _adiabatic_fixed_grid(
        engine,
        n_phi=n_phi,
        direction=direction,
        overlap_threshold=overlap_threshold,
    )
    current_size = n_phi
    for refinement in range(1, max_refinements + 1):
        current_size *= 2
        fine = _adiabatic_fixed_grid(
            engine,
            n_phi=current_size,
            direction=direction,
            overlap_threshold=overlap_threshold,
        )
        error = abs(fine.charge - coarse.charge)
        if error <= charge_tolerance and current_size >= minimum_converged_points:
            return replace(
                fine,
                new_diagonalizations=engine.diagonalization_count - before,
                refinement_count=refinement,
                charge_convergence_error=error,
            )
        coarse = fine
    raise RuntimeError(
        f"adiabatic charge did not converge after {max_refinements} refinements"
    )
