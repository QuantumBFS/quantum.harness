"""Fixed-frequency coherent-destruction scans for the Floquet heat valve."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
from scipy.integrate import trapezoid
from scipy.optimize import linear_sum_assignment
from scipy.special import jn_zeros, jv

from .backends.uniform_tempo import (
    UNIFORM_TEMPO_REVISION,
    UniformTempoBackend,
    UniformTempoControls,
)
from .config import BathConfig, ModelConfig
from .convergence import ConvergenceCache, fingerprint
from .dark_channels import floquet_matrix_elements
from .floquet import FloquetSolution, solve_floquet
from .heat_current import heat_current_spectrum
from .models import coupling_operator, drive_operator, ising_hamiltonian
from .operators import ComplexMatrix
from .poles import fit_pole_residues, transfer_poles
from .symmetry import Sector, n2_sectors, n3_reflection_sectors, project

BESSEL_ROOT = float(jn_zeros(0, 1)[0])


@dataclass(frozen=True)
class HeatValvePoint:
    n: Literal[1, 2, 3]
    xi: float
    j: float = 1.0
    omega: float = 1.0
    drive_frequency: float = 3.0
    alpha: float = 0.05
    cutoff: float = 2.5
    temperature: float = 0.0
    floquet_steps: int = 360

    def __post_init__(self) -> None:
        if self.n not in (1, 2, 3):
            raise ValueError("n must be one of 1, 2, 3")
        if self.xi < 0:
            raise ValueError("xi must be nonnegative")
        if self.floquet_steps < 8:
            raise ValueError("floquet_steps must be at least eight")

    @property
    def drive_amplitude(self) -> float:
        return self.xi * self.drive_frequency / 2


@dataclass(frozen=True)
class PreparedHeatValve:
    point: HeatValvePoint
    model: ModelConfig
    bath: BathConfig
    sector: Sector
    h0: ComplexMatrix
    coupling: ComplexMatrix
    drive: ComplexMatrix
    cat_plus: np.ndarray[Any, np.dtype[np.complex128]]
    cat_minus: np.ndarray[Any, np.dtype[np.complex128]]


@dataclass(frozen=True)
class ValveNumerics:
    steps_per_period: int = 60
    tolerance: float = 1e-6
    phase_samples: int = 3
    delay_periods: int = 12
    pole_count: int = 8
    pole_tolerance: float = 1e-10
    pole_maxiter: int = 2_000
    frequency_max: float = 6.0
    frequency_points: int = 601
    auto_nc: bool = True
    memory_cutoff: int = 100_000
    low_rank_svd: bool = False
    truncation: Literal["rel", "abs"] = "rel"
    cap_rank: int = 100_000
    max_rank: int = 100_000

    def __post_init__(self) -> None:
        if self.steps_per_period < 2:
            raise ValueError("steps_per_period must be at least two")
        if (
            self.phase_samples < 2
            or self.phase_samples > self.steps_per_period
            or self.steps_per_period % self.phase_samples != 0
        ):
            raise ValueError("phase_samples must divide steps_per_period")
        if not 0 < self.tolerance < 1:
            raise ValueError("tolerance must lie between zero and one")
        if self.delay_periods < 1:
            raise ValueError("delay_periods must be positive")
        if self.pole_count < 2:
            raise ValueError("pole_count must include steady and decaying poles")
        if self.delay_periods + 1 <= self.pole_count - 1:
            raise ValueError("delay window must overdetermine the pole fit")
        if self.pole_tolerance <= 0 or self.pole_maxiter < 1:
            raise ValueError("invalid pole solver controls")
        if self.frequency_max <= 0 or self.frequency_points < 2:
            raise ValueError("invalid heat-current frequency grid")
        if self.memory_cutoff < 1:
            raise ValueError("memory_cutoff must be positive")
        if self.truncation not in ("rel", "abs"):
            raise ValueError("truncation must be 'rel' or 'abs'")
        if self.cap_rank < 1 or self.max_rank < self.cap_rank:
            raise ValueError("invalid rank limits")


def _active_sector(n: int) -> Sector:
    if n == 1:
        return Sector("full", np.eye(2, dtype=np.complex128))
    if n == 2:
        _, triplet = n2_sectors()
        return triplet
    _, even = n3_reflection_sectors()
    return even


def _projected_cat(
    n: int,
    sector: Sector,
    sign: Literal[-1, 1],
) -> np.ndarray[Any, np.dtype[np.complex128]]:
    up = np.zeros(2**n, dtype=np.complex128)
    down = np.zeros(2**n, dtype=np.complex128)
    up[0] = 1
    down[-1] = 1
    value = sector.isometry.conj().T @ ((up + sign * down) / np.sqrt(2))
    norm = float(np.linalg.norm(value))
    if norm <= 1e-13:
        raise ValueError("selected sector does not contain the cat state")
    return np.asarray(value / norm, dtype=np.complex128)


def prepare_heat_valve_point(point: HeatValvePoint) -> PreparedHeatValve:
    """Project a size point while keeping bath and drive normalizations separate."""
    model = ModelConfig(
        n=point.n,
        j=point.j,
        omega=point.omega,
        drive_amplitude=point.drive_amplitude,
        drive_frequency=point.drive_frequency,
        normalization="bounded",
        drive_normalization="per_spin",
    )
    bath = BathConfig(point.alpha, point.cutoff, point.temperature)
    sector = _active_sector(point.n)
    return PreparedHeatValve(
        point=point,
        model=model,
        bath=bath,
        sector=sector,
        h0=project(ising_hamiltonian(model), sector),
        coupling=project(coupling_operator(model), sector),
        drive=project(drive_operator(model), sector),
        cat_plus=_projected_cat(point.n, sector, +1),
        cat_minus=_projected_cat(point.n, sector, -1),
    )


def _cat_modes(
    prepared: PreparedHeatValve,
    solution: FloquetSolution,
) -> tuple[tuple[int, int], tuple[float, float], float]:
    cat_basis = np.column_stack((prepared.cat_plus, prepared.cat_minus))
    subspace_weights = np.sum(
        abs(cat_basis.conj().T @ solution.modes) ** 2,
        axis=0,
    )
    selected = np.argsort(subspace_weights)[-2:]
    overlaps = abs(cat_basis.conj().T @ solution.modes[:, selected]) ** 2
    rows, columns = linear_sum_assignment(-overlaps)
    assigned = {
        int(row): (int(selected[column]), float(overlaps[row, column]))
        for row, column in zip(rows, columns, strict=True)
    }
    modes = (assigned[0][0], assigned[1][0])
    direct_overlaps = (assigned[0][1], assigned[1][1])
    cat_overlap = float(np.min(subspace_weights[selected]))
    return modes, direct_overlaps, cat_overlap


def _isolated_point(point: HeatValvePoint) -> dict[str, Any]:
    prepared = prepare_heat_valve_point(point)
    model = prepared.model

    def hamiltonian(time: float) -> ComplexMatrix:
        return np.asarray(
            prepared.h0
            + model.drive_amplitude
            * np.cos(model.drive_frequency * time)
            * prepared.drive,
            dtype=np.complex128,
        )

    solution = solve_floquet(
        hamiltonian,
        model.period,
        point.floquet_steps,
    )
    modes, direct_overlaps, cat_overlap = _cat_modes(prepared, solution)
    raw_gap = float(abs(solution.quasienergies[modes[0]] - solution.quasienergies[modes[1]]))
    cat_gap = min(raw_gap, model.drive_frequency - raw_gap)
    transitions = floquet_matrix_elements(
        solution,
        prepared.coupling,
        harmonic_cutoff=3,
    )
    selected_modes = set(modes)
    cat_brightness = float(
        sum(
            record.weight
            for record in transitions
            if record.source in selected_modes
            and record.target in selected_modes
            and record.source != record.target
        )
    )
    return {
        **asdict(point),
        "drive_amplitude": model.drive_amplitude,
        "bessel_j0": float(jv(0, point.xi)),
        "bessel_root": BESSEL_ROOT,
        "sector": prepared.sector.name,
        "dimension": prepared.sector.dimension,
        "cat_mode_indices": list(modes),
        "cat_plus_overlap": direct_overlaps[0],
        "cat_minus_overlap": direct_overlaps[1],
        "cat_overlap": cat_overlap,
        "cat_gap": float(cat_gap),
        "cat_brightness": cat_brightness,
        "unitarity_residual": solution.unitarity_residual,
        "floquet_eigen_residual": solution.eigen_residual,
    }


def isolated_valve_scan(
    points: Iterable[HeatValvePoint],
) -> dict[str, Any]:
    """Run a deterministic exact scan before selecting open-system points."""
    selected = tuple(points)
    if not selected:
        raise ValueError("the isolated valve scan requires at least one point")
    records = [_isolated_point(point) for point in selected]
    return {
        "complete": True,
        "method": "isolated_floquet_coherent_destruction",
        "schema_version": 1,
        "bessel_root": BESSEL_ROOT,
        "points": records,
    }


def _complex_values(values: np.ndarray[Any, np.dtype[np.complex128]]) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.complex128)
    return {
        "real": np.real(array).astype(float).tolist(),
        "imag": np.imag(array).astype(float).tolist(),
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_uniform_valve_point(
    point: HeatValvePoint,
    numerics: ValveNumerics,
    cache: ConvergenceCache,
    *,
    source_revision: str | None = None,
) -> dict[str, Any]:
    """Run or restore one pole-resolved UniformTEMPO heat-valve point."""
    prepared = prepare_heat_valve_point(point)
    revision = _git_commit() if source_revision is None else source_revision
    cache_payload = {
        "experiment": "uniform-floquet-pole-heat-valve-v1",
        "point": asdict(point),
        "numerics": asdict(numerics),
        "h0": _complex_values(prepared.h0),
        "coupling": _complex_values(prepared.coupling),
        "drive": _complex_values(prepared.drive),
        "bath": asdict(prepared.bath),
        "uniform_tempo_revision": UNIFORM_TEMPO_REVISION,
    }
    key = fingerprint(cache_payload, revision)
    if cache.contains(key):
        return cache.load(key)

    controls = UniformTempoControls(
        steps_per_period=numerics.steps_per_period,
        tolerance=numerics.tolerance,
        phase_samples=numerics.phase_samples,
        delay_periods=numerics.delay_periods,
        auto_nc=numerics.auto_nc,
        memory_cutoff=numerics.memory_cutoff,
        low_rank_svd=numerics.low_rank_svd,
        truncation=numerics.truncation,
        cap_rank=numerics.cap_rank,
        max_rank=numerics.max_rank,
        pole_count=numerics.pole_count,
        pole_tolerance=numerics.pole_tolerance,
        pole_maxiter=numerics.pole_maxiter,
    )
    run = UniformTempoBackend(
        tensor_cache_directory=cache.directory / "process_tensors"
    ).run_periodic(
        prepared.h0,
        prepared.coupling,
        prepared.model,
        prepared.bath,
        controls,
        drive_operator=prepared.drive,
    )
    poles = transfer_poles(
        run.transfer_eigenvalues,
        run.transfer_eigenpair_residuals,
        prepared.model.period,
    )
    fit = fit_pole_residues(
        poles,
        run.correlation.delays,
        run.correlation.connected,
        prepared.model.period,
        max_modes=len(poles),
    )
    frequencies = np.linspace(
        0,
        numerics.frequency_max,
        numerics.frequency_points,
    )
    heat = heat_current_spectrum(
        run.correlation,
        prepared.bath,
        frequencies,
    )
    connected_tail = float(abs(run.correlation.connected[-1]))
    maximum_eigenpair_residual = float(
        np.max(run.transfer_eigenpair_residuals)
    )
    maximum_pole_modulus = float(
        max(abs(item.eigenvalue) for item in poles)
    )
    converged = bool(
        run.diagnostics["trace_error"] <= 5e-3
        and run.diagnostics["hermiticity_error"] <= 5e-3
        and run.diagnostics["minimum_density_eigenvalue"] >= -5e-3
        and run.diagnostics["fixed_point_residual"] <= 1e-3
        and connected_tail <= 5e-2
        and maximum_eigenpair_residual <= 1e-8
        and maximum_pole_modulus <= 1 + 1e-6
        and fit.reconstruction_residual <= 5e-2
    )
    residue_records = [
        {
            "eigenvalue": {
                "real": float(item.pole.eigenvalue.real),
                "imag": float(item.pole.eigenvalue.imag),
                "abs": float(abs(item.pole.eigenvalue)),
            },
            "decay_rate": item.pole.decay_rate,
            "quasifrequency": item.pole.quasifrequency,
            "eigenpair_residual": item.pole.eigenpair_residual,
            "residue": {
                "real": float(item.residue.real),
                "imag": float(item.residue.imag),
                "abs": float(abs(item.residue)),
            },
        }
        for item in fit.residues
    ]
    dominant = max(fit.residues, key=lambda item: abs(item.residue))
    payload: dict[str, Any] = {
        "method": run.method,
        "source_commit": revision,
        "point": asdict(point),
        "model": asdict(prepared.model),
        "bath": asdict(prepared.bath),
        "numerics": asdict(numerics),
        "sector": prepared.sector.name,
        "dimension": prepared.sector.dimension,
        "converged": converged,
        "diagnostics": {
            **run.diagnostics,
            **run.metadata,
            "connected_tail": connected_tail,
            "maximum_eigenpair_residual": maximum_eigenpair_residual,
            "maximum_pole_modulus": maximum_pole_modulus,
        },
        "phase_state": _complex_values(run.floquet_state),
        "phase_states": _complex_values(run.phase_states),
        "correlation": {
            "delay": run.correlation.delays.tolist(),
            "total": _complex_values(run.correlation.total),
            "connected": _complex_values(run.correlation.connected),
            "coherent": run.correlation.coherent.tolist(),
        },
        "frequency": heat.frequencies.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(item) for item in heat.delta_peaks],
        "integrated_absolute_heat": float(
            trapezoid(abs(heat.continuous), heat.frequencies)
        ),
        "poles": residue_records,
        "dominant_residue": {
            "real": float(dominant.residue.real),
            "imag": float(dominant.residue.imag),
            "abs": float(abs(dominant.residue)),
        },
        "visible_residue_weight": float(
            sum(abs(item.residue) for item in fit.residues)
        ),
        "pole_fit": {
            "reconstruction": _complex_values(fit.reconstruction),
            "stroboscopic_delays": fit.stroboscopic_delays.tolist(),
            "reconstruction_residual": fit.reconstruction_residual,
            "condition_number": fit.condition_number,
        },
    }
    cache.store(key, payload)
    return cache.load(key)


def _point_from_scan(record: dict[str, Any]) -> HeatValvePoint:
    return HeatValvePoint(
        n=int(record["n"]),  # type: ignore[arg-type]
        xi=float(record["xi"]),
        j=float(record["j"]),
        omega=float(record["omega"]),
        drive_frequency=float(record["drive_frequency"]),
        alpha=float(record["alpha"]),
        cutoff=float(record["cutoff"]),
        temperature=float(record["temperature"]),
        floquet_steps=int(record["floquet_steps"]),
    )


def build_heat_valve_manifest(
    isolated_scan: dict[str, Any],
    uniform_results: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Select two-sided valve points and combine any completed exact results."""
    scan_records = tuple(isolated_scan.get("points", ()))
    selected: list[HeatValvePoint] = []
    for n in (1, 2, 3):
        candidates = [
            record
            for record in scan_records
            if int(record["n"]) == n and float(record["cat_overlap"]) >= 0.5
        ]
        if not candidates:
            raise ValueError(f"isolated scan has no resolved N={n} cat points")
        minimum = min(candidates, key=lambda item: float(item["cat_gap"]))
        minimum_xi = float(minimum["xi"])
        lower = [
            record
            for record in candidates
            if float(record["xi"]) <= minimum_xi - 0.15
        ]
        upper = [
            record
            for record in candidates
            if float(record["xi"]) >= minimum_xi + 0.15
        ]
        if not lower or not upper:
            raise ValueError(f"isolated N={n} minimum lacks two resolved flanks")
        selected.extend(
            (
                _point_from_scan(max(lower, key=lambda item: float(item["xi"]))),
                _point_from_scan(minimum),
                _point_from_scan(min(upper, key=lambda item: float(item["xi"]))),
            )
        )

    results = tuple(uniform_results)
    result_keys = {
        (int(item["point"]["n"]), float(item["point"]["xi"])) for item in results
    }
    selected_keys = {(item.n, item.xi) for item in selected}
    return {
        "complete": result_keys == selected_keys,
        "method": "uniform-floquet-pole-heat-valve-v1",
        "isolated_scan_complete": bool(isolated_scan.get("complete", False)),
        "selected_points": [asdict(item) for item in selected],
        "points": list(results),
    }
