"""Resumable batch manifests and checkpoint handling for cluster scans."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import uuid
from typing import Mapping, Sequence

import numpy as np

from .diagonalization import EDEngine
from .topology import ChernGridResult, compute_fhs


BASE_U_VALUES = (
    -32.0,
    -24.0,
    -16.0,
    -12.0,
    -8.0,
    -6.0,
    -4.0,
    -2.0,
    0.0,
    2.0,
    4.0,
    5.0,
    5.5,
    5.8,
    6.0,
    6.2,
    6.5,
    7.0,
    8.0,
    10.0,
    12.0,
    16.0,
    24.0,
    32.0,
)
DENSE_U_VALUES = tuple(round(4.0 + 0.25 * index, 2) for index in range(25))
U_VALUES = tuple(sorted(set(BASE_U_VALUES + DENSE_U_VALUES)))
T_VALUES = tuple(round(0.5 + 0.1 * index, 1) for index in range(11))
PERIODS = (2.0, 10.0, 50.0)


def _number_token(value: float) -> str:
    return (
        f"{float(value):+.6f}"
        .replace("+", "p")
        .replace("-", "neg")
        .replace(".", "d")
    )


@dataclass(frozen=True)
class ParameterPoint:
    index: int
    U: float
    t: float

    @property
    def key(self) -> str:
        return f"pair:{self.index}:U={self.U}:t={self.t}"


@dataclass(frozen=True)
class RealtimePoint:
    index: int
    pair: ParameterPoint
    period: float

    @property
    def key(self) -> str:
        return f"{self.pair.key}:T={self.period}"


@dataclass(frozen=True)
class LoadedChernCheckpoint:
    path: Path
    grid_size: int
    vertex_count: int
    states: np.ndarray
    energies: np.ndarray
    gaps: np.ndarray
    hermiticity_errors: np.ndarray
    residuals: np.ndarray
    flux: np.ndarray
    metadata: dict


def parameter_points() -> tuple[ParameterPoint, ...]:
    return tuple(
        ParameterPoint(index=index, U=float(U), t=float(t))
        for index, (t, U) in enumerate(
            (t, U) for t in T_VALUES for U in U_VALUES
        )
    )


def realtime_points() -> tuple[RealtimePoint, ...]:
    return tuple(
        RealtimePoint(index=index, pair=pair, period=float(period))
        for index, (pair, period) in enumerate(
            (pair, period) for pair in parameter_points() for period in PERIODS
        )
    )


def pair_checkpoint_name(point: ParameterPoint, grid_size: int) -> str:
    return (
        f"pair_{point.index:04d}_U_{_number_token(point.U)}_"
        f"t_{_number_token(point.t)}_N{int(grid_size)}.npz"
    )


def realtime_result_name(point: RealtimePoint) -> str:
    pair = point.pair
    return (
        f"realtime_{point.index:04d}_pair_{pair.index:04d}_"
        f"U_{_number_token(pair.U)}_t_{_number_token(pair.t)}_"
        f"T_{_number_token(point.period)}.npz"
    )


def static_result_name(point: ParameterPoint) -> str:
    return (
        f"static_{point.index:04d}_U_{_number_token(point.U)}_"
        f"t_{_number_token(point.t)}.npz"
    )


def _expected_parameters(engine: EDEngine, point: ParameterPoint) -> dict:
    parameters = engine.model.parameters
    expected = {
        "L": parameters.L,
        "U": point.U,
        "t": point.t,
        "delta0": parameters.delta0,
        "Delta0": parameters.Delta0,
        "N_up": parameters.N_up,
        "N_down": parameters.N_down,
    }
    if parameters.delta_center != 0.0 or parameters.Delta_center != 0.0:
        expected.update(
            delta_center=parameters.delta_center,
            Delta_center=parameters.Delta_center,
        )
    return expected


def atomic_savez_exclusive(
    path: Path | str,
    arrays: Mapping[str, np.ndarray | str],
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"result already exists: {output}")
    partial = output.with_name(f".{output.name}.partial.{os.getpid()}.{uuid.uuid4().hex}")
    published = False
    try:
        with partial.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(partial, output)
        published = True
        return output
    finally:
        if partial.exists():
            partial.unlink()
        if not published and output.exists() and output.stat().st_nlink > 1:
            raise RuntimeError("atomic result publication failed after linking")


def save_chern_checkpoint(
    path: Path | str,
    engine: EDEngine,
    *,
    point: ParameterPoint,
    results: Sequence[ChernGridResult],
) -> Path:
    """Atomically write nested Chern grids in the reusable schema-v2 format."""
    if not results:
        raise ValueError("at least one Chern grid is required")
    sizes = [int(result.N_theta) for result in results]
    if any(result.N_theta != result.N_phi for result in results):
        raise ValueError("cluster Chern checkpoints require square grids")
    if sizes != sorted(set(sizes)):
        raise ValueError("Chern grid sizes must be unique and increasing")
    parameters = _expected_parameters(engine, point)
    if parameters["U"] != engine.model.parameters.U or parameters["t"] != engine.model.parameters.t:
        raise ValueError("point does not match the engine model")

    final = results[-1]
    size = final.N_theta
    coordinates = [(theta, phi) for theta in range(size) for phi in range(size)]
    summary = {
        **final.as_dict(),
        "index": point.index,
        **parameters,
        "checkpoint": Path(path).name,
    }
    fingerprint = hashlib.sha256(engine.basis.states.tobytes()).hexdigest()
    metadata = {
        "schema_version": 2,
        "complete": True,
        "parameters": parameters,
        "basis_fingerprint": fingerprint,
        "basis_dimension": engine.basis.Ns,
        "grid_sizes": sizes,
        "vertex_count": size * size,
        "summary": summary,
        "grid_summaries": [result.as_dict() for result in results],
    }
    arrays: dict[str, np.ndarray | str] = {
        "schema_version": np.asarray(2),
        "metadata_json": json.dumps(metadata, sort_keys=True),
        "theta_numerators": np.asarray([theta for theta, _ in coordinates]),
        "theta_denominators": np.full(size * size, size),
        "phi_numerators": np.asarray([phi for _, phi in coordinates]),
        "phi_denominators": np.full(size * size, size),
        "states": final.states.reshape(size * size, engine.basis.Ns),
        "energies": np.column_stack(
            (
                final.ground_state_energies.ravel(),
                final.first_excited_energies.ravel(),
            )
        ),
        "gaps": final.gaps.ravel(),
        "hermiticity_errors": final.hermiticity_errors.ravel(),
        "residuals": final.residuals.ravel(),
    }
    for result in results:
        suffix = f"N{result.N_theta}"
        arrays[f"flux_{suffix}"] = result.fhs.flux
        arrays[f"e0_{suffix}"] = result.ground_state_energies
        arrays[f"e1_{suffix}"] = result.first_excited_energies
    return atomic_savez_exclusive(path, arrays)


def load_chern_checkpoint(
    path: Path | str,
    engine: EDEngine,
    *,
    point: ParameterPoint,
    grid_size: int,
) -> LoadedChernCheckpoint:
    """Validate a schema-v2 grid checkpoint and seed its exact vertices."""
    checkpoint = Path(path)
    grid_size = int(grid_size)
    with np.load(checkpoint, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"]))
        if int(data["schema_version"]) != 2:
            raise ValueError("checkpoint array schema version is unsupported")
        if metadata.get("schema_version") != 2 or not metadata.get("complete"):
            raise ValueError("checkpoint metadata is incomplete or unsupported")
        expected_parameters = _expected_parameters(engine, point)
        if metadata.get("parameters") != expected_parameters:
            raise ValueError("checkpoint parameters do not match the requested point")
        fingerprint = hashlib.sha256(engine.basis.states.tobytes()).hexdigest()
        if metadata.get("basis_fingerprint") != fingerprint:
            raise ValueError("checkpoint basis fingerprint does not match")
        if metadata.get("basis_dimension") != engine.basis.Ns:
            raise ValueError("checkpoint basis dimension does not match")
        if grid_size not in [int(value) for value in metadata.get("grid_sizes", [])]:
            raise ValueError("checkpoint does not contain the requested grid")

        names = (
            "states",
            "energies",
            "gaps",
            "hermiticity_errors",
            "residuals",
            "theta_numerators",
            "theta_denominators",
            "phi_numerators",
            "phi_denominators",
            f"flux_N{grid_size}",
            f"e0_N{grid_size}",
            f"e1_N{grid_size}",
        )
        missing = [name for name in names if name not in data]
        if missing:
            raise ValueError(f"checkpoint arrays are missing: {missing}")
        states_flat = np.asarray(data["states"], dtype=np.complex128)
        energies_flat = np.asarray(data["energies"], dtype=np.float64)
        gaps_flat = np.asarray(data["gaps"], dtype=np.float64)
        hermiticity_flat = np.asarray(data["hermiticity_errors"], dtype=np.float64)
        residuals_flat = np.asarray(data["residuals"], dtype=np.float64)
        coordinate_arrays = [np.asarray(data[name]) for name in names[5:9]]
        flux = np.asarray(data[f"flux_N{grid_size}"], dtype=np.float64)
        saved_e0 = np.asarray(data[f"e0_N{grid_size}"], dtype=np.float64)
        saved_e1 = np.asarray(data[f"e1_N{grid_size}"], dtype=np.float64)

    count = grid_size * grid_size
    if metadata.get("vertex_count") != count:
        raise ValueError("checkpoint vertex count does not match the grid")
    if states_flat.shape != (count, engine.basis.Ns):
        raise ValueError("checkpoint state array shape is invalid")
    if energies_flat.shape != (count, 2):
        raise ValueError("checkpoint energy array shape is invalid")
    for name, array in (
        ("gaps", gaps_flat),
        ("Hermiticity errors", hermiticity_flat),
        ("residuals", residuals_flat),
    ):
        if array.shape != (count,):
            raise ValueError(f"checkpoint {name} shape is invalid")
    if any(array.shape != (count,) for array in coordinate_arrays):
        raise ValueError("checkpoint coordinate array shape is invalid")
    numerical_arrays = (
        states_flat,
        energies_flat,
        gaps_flat,
        hermiticity_flat,
        residuals_flat,
        flux,
        saved_e0,
        saved_e1,
    )
    if not all(np.all(np.isfinite(array)) for array in numerical_arrays):
        raise ValueError("checkpoint contains non-finite numerical data")
    if not np.allclose(np.linalg.norm(states_flat, axis=1), 1.0, atol=1e-10):
        raise ValueError("checkpoint contains non-normalized states")
    if not np.allclose(gaps_flat, energies_flat[:, 1] - energies_flat[:, 0], atol=1e-10):
        raise ValueError("checkpoint gaps do not match its energies")

    theta_num, theta_den, phi_num, phi_den = coordinate_arrays
    positions: dict[tuple[Fraction, Fraction], int] = {}
    for index in range(count):
        key = (
            Fraction(int(theta_num[index]), int(theta_den[index])) % 1,
            Fraction(int(phi_num[index]), int(phi_den[index])) % 1,
        )
        if key in positions:
            raise ValueError("checkpoint has duplicate coordinates")
        positions[key] = index
    expected_coordinates = {
        (Fraction(theta, grid_size), Fraction(phi, grid_size))
        for theta in range(grid_size)
        for phi in range(grid_size)
    }
    if set(positions) != expected_coordinates:
        raise ValueError("checkpoint coordinates do not form the requested grid")

    states = np.empty((grid_size, grid_size, engine.basis.Ns), dtype=np.complex128)
    energies = np.empty((grid_size, grid_size, 2), dtype=np.float64)
    gaps = np.empty((grid_size, grid_size), dtype=np.float64)
    hermiticity = np.empty_like(gaps)
    residuals = np.empty_like(gaps)
    for theta_index in range(grid_size):
        for phi_index in range(grid_size):
            coordinate = (
                Fraction(theta_index, grid_size),
                Fraction(phi_index, grid_size),
            )
            position = positions[coordinate]
            states[theta_index, phi_index] = states_flat[position]
            energies[theta_index, phi_index] = energies_flat[position]
            gaps[theta_index, phi_index] = gaps_flat[position]
            hermiticity[theta_index, phi_index] = hermiticity_flat[position]
            residuals[theta_index, phi_index] = residuals_flat[position]

    if flux.shape != (grid_size, grid_size):
        raise ValueError("checkpoint flux shape is invalid")
    if not np.allclose(saved_e0, energies[:, :, 0], atol=1e-10) or not np.allclose(
        saved_e1,
        energies[:, :, 1],
        atol=1e-10,
    ):
        raise ValueError("checkpoint grid energies are inconsistent")
    recomputed = compute_fhs(states)
    if not np.allclose(recomputed.flux, flux, atol=1e-10):
        raise ValueError("checkpoint FHS flux is inconsistent with its states")
    summary = metadata.get("summary", {})
    if not np.isclose(recomputed.chern_raw, float(summary.get("C_raw", np.nan)), atol=1e-10):
        raise ValueError("checkpoint Chern summary is inconsistent")

    for theta_index in range(grid_size):
        for phi_index in range(grid_size):
            engine.seed_vertex(
                Fraction(theta_index, grid_size),
                Fraction(phi_index, grid_size),
                state=states[theta_index, phi_index],
                energies=tuple(energies[theta_index, phi_index]),
                hermiticity_error=hermiticity[theta_index, phi_index],
                residual=residuals[theta_index, phi_index],
            )
    return LoadedChernCheckpoint(
        path=checkpoint,
        grid_size=grid_size,
        vertex_count=count,
        states=states,
        energies=energies,
        gaps=gaps,
        hermiticity_errors=hermiticity,
        residuals=residuals,
        flux=flux,
        metadata=metadata,
    )
