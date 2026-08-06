"""Workflow composition for the four observables and parameter scans."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .diagonalization import EDEngine
from .dynamics import evolve_pump_cycle
from .io_utils import parameters_dict, require_mapping
from .model import ModelParameters, RiceMeleHubbardModel
from .topology import ChernGridResult, compute_adiabatic_charge, scan_chern


def _nested_sizes(values: Sequence[int], *, minimum: int) -> tuple[int, ...]:
    sizes = tuple(int(value) for value in values)
    if not sizes or any(size < minimum for size in sizes):
        raise ValueError(f"grid sizes must be at least {minimum}")
    for coarse, fine in zip(sizes, sizes[1:]):
        if fine <= coarse or fine % coarse:
            raise ValueError("each nested grid must be an increasing integer multiple")
    return sizes


@dataclass(frozen=True)
class BenchmarkConfig:
    model: ModelParameters
    chern_grid: int = 5
    gap_grids: tuple[int, ...] = (3, 6)
    polarization_points: int = 40
    period: float = 10.0
    time_steps: int = 400

    def __post_init__(self) -> None:
        if self.chern_grid < 5:
            raise ValueError("Chern grid size must be at least 5")
        object.__setattr__(self, "gap_grids", _nested_sizes(self.gap_grids, minimum=2))
        if self.polarization_points < 2:
            raise ValueError("polarization_points must be at least 2")
        if self.period <= 0.0 or self.time_steps < 2:
            raise ValueError("period must be positive and time_steps at least 2")


@dataclass(frozen=True)
class ScanConfig:
    model: ModelParameters
    grid_sizes: tuple[int, ...] = (5,)

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid_sizes", _nested_sizes(self.grid_sizes, minimum=5))


@dataclass(frozen=True)
class UScanRecord:
    parameters: ModelParameters
    result: ChernGridResult

    def as_dict(self) -> dict[str, float | int | bool]:
        return {**parameters_dict(self.parameters), **self.result.as_dict()}


def run_benchmark(config: BenchmarkConfig) -> dict[str, object]:
    """Compute C_MB, minimum gap, adiabatic Q, and finite-time Q."""
    engine = EDEngine(RiceMeleHubbardModel(config.model))
    chern = scan_chern(
        engine,
        n_theta=config.chern_grid,
        n_phi=config.chern_grid,
    )
    gap_levels = engine.scan_nested_gaps(config.gap_grids)
    adiabatic = compute_adiabatic_charge(
        engine,
        n_phi=config.polarization_points,
    )

    realtime_engine = EDEngine(RiceMeleHubbardModel(config.model))
    realtime = evolve_pump_cycle(
        realtime_engine,
        period=config.period,
        n_steps=config.time_steps,
    )
    return {
        "parameters": parameters_dict(config.model),
        "conventions": {
            "site_staggering": "(-1)^j with zero-based j",
            "boundary_forward_phase": "exp(+i*theta)",
            "torus_order": "theta,phi",
            "current": "dH/dtheta at theta=0",
            "polarization": "continuous arg(<exp(i*2*pi*X/L)>)/(2*pi)",
        },
        "C_MB": chern.fhs.chern_raw,
        "C_MB_integer": chern.fhs.chern_integer,
        "Delta_min": gap_levels[-1].minimum_gap,
        "Q_adiabatic": adiabatic.charge,
        "Q_real_time": realtime.charge,
        "period": realtime.period,
        "time_steps": realtime.n_steps,
        "norm_error": realtime.maximum_norm_error,
        "final_ground_state_fidelity": realtime.final_ground_state_fidelity,
        "minimum_resta_modulus": adiabatic.minimum_resta_modulus,
        "polarization_points_used": adiabatic.n_phi,
        "adiabatic_refinements": adiabatic.refinement_count,
        "adiabatic_convergence_error": adiabatic.charge_convergence_error,
        "minimum_link_overlap": chern.fhs.minimum_overlap,
        "maximum_link_modulus_error": chern.fhs.maximum_link_modulus_error,
        "maximum_solver_residual": max(
            chern.maximum_residual,
            gap_levels[-1].maximum_residual,
            adiabatic.maximum_residual,
        ),
        "gap_levels": [
            {
                "N_theta": level.N_theta,
                "N_phi": level.N_phi,
                "minimum_gap": level.minimum_gap,
                "theta_at_minimum": level.theta_at_minimum,
                "phi_at_minimum": level.phi_at_minimum,
                "new_diagonalizations": level.new_diagonalizations,
                "maximum_residual": level.maximum_residual,
            }
            for level in gap_levels
        ],
    }


def scan_u(values: Sequence[float], config: ScanConfig) -> list[UScanRecord]:
    """Scan U with nested-grid reuse within each interaction value."""
    if not values:
        raise ValueError("at least one U value is required")
    records: list[UScanRecord] = []
    for value in values:
        parameters = replace(config.model, U=float(value))
        engine = EDEngine(RiceMeleHubbardModel(parameters))
        for size in config.grid_sizes:
            records.append(
                UScanRecord(
                    parameters=parameters,
                    result=scan_chern(engine, n_theta=size, n_phi=size),
                )
            )
    return records


def model_from_mapping(mapping: Mapping[str, Any]) -> ModelParameters:
    allowed = {"L", "t", "delta0", "Delta0", "U", "N_up", "N_down"}
    unknown = set(mapping) - allowed
    if unknown:
        raise ValueError(f"unknown model parameters: {sorted(unknown)}")
    return ModelParameters(**mapping)


def benchmark_config_from_mapping(config: Mapping[str, Any]) -> BenchmarkConfig:
    model = model_from_mapping(require_mapping(config, "model"))
    values = dict(require_mapping(config, "benchmark"))
    if "gap_grids" in values:
        values["gap_grids"] = tuple(values["gap_grids"])
    return BenchmarkConfig(model=model, **values)


def scan_config_from_mapping(config: Mapping[str, Any]) -> ScanConfig:
    model = model_from_mapping(require_mapping(config, "model"))
    values = dict(require_mapping(config, "scan"))
    values.pop("U_values", None)
    if "grid_sizes" in values:
        values["grid_sizes"] = tuple(values["grid_sizes"])
    return ScanConfig(model=model, **values)
