#!/usr/bin/env python3
"""Exact-diagonalization oracle for the issue-121 large-lattice runner.

This module deliberately constructs the complete 2**N Fock space and is
therefore hard-limited to N<=9. It is only a small-system ED oracle for checking
large_lattice_ctqmc.py; it is not a production lattice algorithm.

For a one-particle matrix B and ordered occupation sets I,J, the convention is

    <I|Gamma(B)|J> = det(B[I,J]).

Thus the one-particle block of Gamma(B) is B, with the destination occupation
set selecting matrix rows and the source occupation set selecting columns. The
Hamiltonian matching the continuous-time expansion is

    H = G0 I - sum_(triangle,vertex) activity * Gamma(B_emb),

where the catalog activity already includes the factor 1/6 from the S3 twirl.
Individual Gamma(B_emb) need not be Hermitian; the completed sum must pass an
explicit Hermiticity-residual gate before diagonalization.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

import numpy as np

import large_lattice_ctqmc as ctqmc


ALGORITHM_ID = "triangular-ab-full-fock-ed-oracle-v1"
SCHEMA_VERSION = 1
MAX_SITES = 9
DEFAULT_HERMITIAN_TOLERANCE = 1.0e-10
ORIENTATION_TOLERANCE = 1.0e-14


class EDOracleError(RuntimeError):
    """Raised when an ED-only size or numerical invariant is violated."""


@dataclass(frozen=True)
class SectorLayout:
    particles: int
    occupations: Tuple[Tuple[int, ...], ...]
    masks: Tuple[int, ...]


@dataclass(frozen=True)
class FockLayout:
    n_sites: int
    dimension: int
    sectors: Tuple[SectorLayout, ...]


@dataclass(frozen=True)
class OracleInput:
    manifest_sha256: str
    geometry: ctqmc.TriangularGeometry
    catalog: Tuple[ctqmc.LocalVertex, ...]
    model: Mapping[str, float]
    momenta: Tuple[Tuple[int, int], ...]
    hermitian_tolerance: float


def _as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ctqmc.ManifestError(f"{name} must be an object")
    return value


def _integer(value: Any, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ctqmc.ManifestError(f"{name} must be an integer >= {minimum}")
    return value


def _signed_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ctqmc.ManifestError(f"{name} must be an integer")
    return value


def _real(value: Any, name: str) -> float:
    try:
        parsed = float(Fraction(value)) if isinstance(value, str) else float(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ctqmc.ManifestError(f"invalid {name}") from exc
    if not math.isfinite(parsed):
        raise ctqmc.ManifestError(f"{name} must be finite")
    return parsed


def load_runner_input(path: Path) -> OracleInput:
    """Load one CTQMC runner manifest without constructing a sampler."""
    manifest, digest = ctqmc.load_manifest(path)
    if int(manifest.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ctqmc.ManifestError("schema_version must be 1")

    lattice = _as_mapping(manifest.get("lattice"), "lattice")
    lx = _integer(lattice.get("Lx"), "lattice.Lx", 2)
    ly = _integer(lattice.get("Ly"), "lattice.Ly", 2)
    geometry = ctqmc.build_triangular_geometry(lx, ly)
    if geometry.n_sites > MAX_SITES:
        raise EDOracleError(
            f"ED oracle forbids N={geometry.n_sites}; maximum is {MAX_SITES}"
        )

    raw_model = _as_mapping(manifest.get("model"), "model")
    model = {
        name: _real(raw_model.get(name), f"model.{name}")
        for name in (
            "epsilon",
            "kappa",
            "vertex_strength",
            "g_A",
            "g_B",
            "beta",
        )
    }
    if model["beta"] <= 0.0:
        raise ctqmc.ManifestError("model.beta must be positive")
    catalog = tuple(
        ctqmc.build_vertex_catalog(
            model["epsilon"],
            model["kappa"],
            model["vertex_strength"],
            model["g_A"],
            model["g_B"],
        )
    )

    measurements = _as_mapping(manifest.get("measurements", {}), "measurements")
    raw_momenta = measurements.get("momenta", [[0, 0]])
    if (
        not isinstance(raw_momenta, Sequence)
        or isinstance(raw_momenta, (str, bytes))
    ):
        raise ctqmc.ManifestError("measurements.momenta must be a sequence")
    momenta = []
    for index, raw in enumerate(raw_momenta):
        if (
            not isinstance(raw, Sequence)
            or isinstance(raw, (str, bytes))
            or len(raw) != 2
        ):
            raise ctqmc.ManifestError(
                f"measurements.momenta[{index}] must be [kx,ky]"
            )
        kx = _signed_integer(raw[0], f"measurements.momenta[{index}][0]")
        ky = _signed_integer(raw[1], f"measurements.momenta[{index}][1]")
        momenta.append((kx, ky))
    if len(set(momenta)) != len(momenta):
        raise ctqmc.ManifestError("measurements.momenta contains duplicates")

    ed_config = _as_mapping(
        manifest.get("exact_diagonalization", {}),
        "exact_diagonalization",
    )
    hermitian_tolerance = _real(
        ed_config.get("hermitian_tolerance", DEFAULT_HERMITIAN_TOLERANCE),
        "exact_diagonalization.hermitian_tolerance",
    )
    if hermitian_tolerance <= 0.0:
        raise ctqmc.ManifestError("hermitian_tolerance must be positive")

    return OracleInput(
        digest,
        geometry,
        catalog,
        model,
        tuple(momenta),
        hermitian_tolerance,
    )


def build_fock_layout(n_sites: int) -> FockLayout:
    if n_sites < 1 or n_sites > MAX_SITES:
        raise EDOracleError(f"Fock layout requires 1<=N<={MAX_SITES}")
    sectors = []
    for particles in range(n_sites + 1):
        occupations = tuple(combinations(range(n_sites), particles))
        masks = tuple(
            sum(1 << site for site in occupation)
            for occupation in occupations
        )
        sectors.append(SectorLayout(particles, occupations, masks))
    return FockLayout(n_sites, 1 << n_sites, tuple(sectors))


def exterior_representation(
    matrix: np.ndarray,
    occupations: Sequence[Tuple[int, ...]],
) -> np.ndarray:
    """Return the exterior-power block with row=destination, column=source."""
    square = np.asarray(matrix)
    if square.ndim != 2 or square.shape[0] != square.shape[1]:
        raise ValueError("matrix must be square")
    result = np.zeros(
        (len(occupations), len(occupations)),
        dtype=np.result_type(square.dtype, np.float64),
    )
    if len(occupations) == 1 and not occupations[0]:
        result[0, 0] = 1.0
        return result
    for row, destination in enumerate(occupations):
        for column, source in enumerate(occupations):
            result[row, column] = np.linalg.det(
                square[np.ix_(destination, source)]
            )
    return result


def fock_gamma(
    matrix: np.ndarray,
    layout: FockLayout,
) -> Tuple[np.ndarray, float]:
    """Build full Gamma(matrix) in bitmask order and check its 1-body block."""
    square = np.asarray(matrix)
    if square.shape != (layout.n_sites, layout.n_sites):
        raise ValueError("one-particle matrix has wrong shape")
    gamma = np.zeros(
        (layout.dimension, layout.dimension),
        dtype=np.result_type(square.dtype, np.float64),
    )
    for sector in layout.sectors:
        block = exterior_representation(square, sector.occupations)
        indices = list(sector.masks)
        gamma[np.ix_(indices, indices)] = block

    one_particle_masks = list(layout.sectors[1].masks)
    one_particle_block = gamma[
        np.ix_(one_particle_masks, one_particle_masks)
    ]
    orientation_residual = float(
        np.linalg.norm(one_particle_block - square, ord=np.inf)
        / max(1.0, float(np.linalg.norm(square, ord=np.inf)))
    )
    return gamma, orientation_residual


def embed_block(
    n_sites: int,
    sites: Sequence[int],
    block: np.ndarray,
) -> np.ndarray:
    embedded = np.eye(n_sites)
    indices = list(sites)
    if len(indices) != 3 or len(set(indices)) != 3:
        raise EDOracleError("each ED vertex must occupy three distinct sites")
    embedded[np.ix_(indices, indices)] = np.asarray(block)
    return embedded


def build_hamiltonian(
    oracle: OracleInput,
    layout: FockLayout,
) -> Tuple[np.ndarray, Mapping[str, Any]]:
    """Construct H from the exact catalog used by the determinant sampler."""
    activity_sum = float(sum(vertex.activity for vertex in oracle.catalog))
    g0 = float(oracle.geometry.n_triangles * activity_sum)
    hamiltonian = g0 * np.eye(layout.dimension)
    max_orientation_residual = 0.0
    terms = 0

    for triangle in oracle.geometry.triangles:
        for vertex in oracle.catalog:
            embedded = embed_block(
                oracle.geometry.n_sites,
                triangle.sites,
                vertex.block,
            )
            lifted, orientation_residual = fock_gamma(embedded, layout)
            max_orientation_residual = max(
                max_orientation_residual,
                orientation_residual,
            )
            hamiltonian -= float(vertex.activity) * lifted
            terms += 1

    if max_orientation_residual > ORIENTATION_TOLERANCE:
        raise EDOracleError(
            "Gamma(B) one-particle block has the wrong row/column orientation: "
            f"residual={max_orientation_residual:.3e}"
        )

    norm_h = float(np.linalg.norm(hamiltonian, ord=np.inf))
    hermitian_residual = float(
        np.linalg.norm(
            hamiltonian - hamiltonian.conj().T,
            ord=np.inf,
        )
        / max(1.0, norm_h)
    )
    if (
        not math.isfinite(hermitian_residual)
        or hermitian_residual > oracle.hermitian_tolerance
    ):
        raise EDOracleError(
            "completed S3-twirled Hamiltonian is not Hermitian: "
            f"relative_inf_residual={hermitian_residual:.3e}, "
            f"tolerance={oracle.hermitian_tolerance:.3e}"
        )

    diagnostics = {
        "G0": g0,
        "resolved_term_count": terms,
        "max_gamma_one_body_orientation_residual_inf": (
            max_orientation_residual
        ),
        "hermitian_residual_relative_inf": hermitian_residual,
        "hermitian_tolerance": oracle.hermitian_tolerance,
    }
    hermitian = 0.5 * (hamiltonian + hamiltonian.conj().T)
    return hermitian, diagnostics


def thermal_density_matrix(
    hamiltonian: np.ndarray,
    beta: float,
) -> Tuple[np.ndarray, np.ndarray, float, Optional[float], float]:
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    minimum = float(eigenvalues[0])
    scaled_weights = np.exp(-beta * (eigenvalues - minimum))
    scaled_partition = float(np.sum(scaled_weights))
    probabilities = scaled_weights / scaled_partition
    log_z = float(-beta * minimum + math.log(scaled_partition))
    log_float_max = math.log(np.finfo(float).max)
    z_value = math.exp(log_z) if log_z < log_float_max else None
    density_matrix = (
        eigenvectors * probabilities[np.newaxis, :]
    ) @ eigenvectors.conj().T
    energy = float(np.dot(probabilities, eigenvalues))
    return density_matrix, eigenvalues, log_z, z_value, energy


def _fermion_sign(mask: int, site: int) -> float:
    lower = mask & ((1 << site) - 1)
    return -1.0 if lower.bit_count() % 2 else 1.0


def hop_action(mask: int, create_site: int, annihilate_site: int) -> Optional[Tuple[int, float]]:
    """Apply c_create^dagger c_annihilate to a bitmask ket."""
    if not (mask & (1 << annihilate_site)):
        return None
    amplitude = _fermion_sign(mask, annihilate_site)
    intermediate = mask ^ (1 << annihilate_site)
    if intermediate & (1 << create_site):
        return None
    amplitude *= _fermion_sign(intermediate, create_site)
    destination = intermediate | (1 << create_site)
    return destination, amplitude


def one_body_green(
    density_matrix: np.ndarray,
    n_sites: int,
) -> np.ndarray:
    """Return G[i,j]=Tr(rho c_i^dagger c_j), matching the sampler."""
    dimension = 1 << n_sites
    green = np.zeros((n_sites, n_sites), dtype=complex)
    for create_site in range(n_sites):
        for annihilate_site in range(n_sites):
            value = 0.0j
            for source in range(dimension):
                action = hop_action(source, create_site, annihilate_site)
                if action is None:
                    continue
                destination, amplitude = action
                # Tr(rho O) uses rho[source,destination] when
                # O|source> = amplitude|destination>.
                value += amplitude * density_matrix[source, destination]
            green[create_site, annihilate_site] = value
    return green


def density_moments(
    density_matrix: np.ndarray,
    n_sites: int,
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    dimension = 1 << n_sites
    basis_probabilities = np.real(np.diag(density_matrix))
    occupations = np.empty((dimension, n_sites), dtype=float)
    for mask in range(dimension):
        for site in range(n_sites):
            occupations[mask, site] = float((mask >> site) & 1)
    density = basis_probabilities @ occupations
    density_pair = occupations.T @ (
        basis_probabilities[:, np.newaxis] * occupations
    )
    particle_number = float(np.sum(density))
    particle_number_squared = float(np.sum(density_pair))
    return density, density_pair, particle_number, particle_number_squared


def _complex_pair(value: complex) -> Sequence[float]:
    number = complex(value)
    return [float(number.real), float(number.imag)]


def _complex_matrix(matrix: np.ndarray) -> Mapping[str, Any]:
    array = np.asarray(matrix)
    return {
        "real": np.real(array).tolist(),
        "imag": np.imag(array).tolist(),
    }


def momentum_observables(
    geometry: ctqmc.TriangularGeometry,
    green: np.ndarray,
    density: np.ndarray,
    density_pair: np.ndarray,
    momenta: Sequence[Tuple[int, int]],
) -> Mapping[str, Any]:
    """Use exactly the phase and normalization convention of the sampler."""
    n_sites = geometry.n_sites
    x = geometry.coordinates[:, 0]
    y = geometry.coordinates[:, 1]
    result = {}
    for kx, ky in momenta:
        phase = np.exp(
            2.0j
            * math.pi
            * (kx * x / geometry.Lx + ky * y / geometry.Ly)
        )
        one_body = complex(np.vdot(phase, green @ phase) / n_sites)
        density_raw = complex(
            np.vdot(phase, density_pair @ phase) / n_sites
        )
        density_mode = complex(
            np.vdot(phase, density) / math.sqrt(n_sites)
        )
        density_connected = (
            density_raw - density_mode.conjugate() * density_mode
        )
        result[f"{kx},{ky}"] = {
            "one_body": _complex_pair(one_body),
            "density_raw": _complex_pair(density_raw),
            "density_mode": _complex_pair(density_mode),
            "density_connected_from_means": _complex_pair(
                density_connected
            ),
        }
    return result


def run_oracle(manifest_path: Path) -> Mapping[str, Any]:
    oracle = load_runner_input(manifest_path)
    layout = build_fock_layout(oracle.geometry.n_sites)
    hamiltonian, hamiltonian_diagnostics = build_hamiltonian(oracle, layout)
    (
        density_matrix,
        eigenvalues,
        log_z,
        z_value,
        energy,
    ) = thermal_density_matrix(hamiltonian, oracle.model["beta"])

    green = one_body_green(density_matrix, oracle.geometry.n_sites)
    (
        density,
        density_pair,
        particle_number,
        particle_number_squared,
    ) = density_moments(density_matrix, oracle.geometry.n_sites)
    raw_number_variance = (
        particle_number_squared - particle_number * particle_number
    )
    variance_roundoff_tolerance = (
        128.0
        * np.finfo(float).eps
        * max(1.0, float(oracle.geometry.n_sites**2))
    )
    if raw_number_variance < -variance_roundoff_tolerance:
        raise EDOracleError("thermal particle-number variance is negative")
    number_variance = max(0.0, raw_number_variance)
    compressibility = (
        oracle.model["beta"]
        * number_variance
        / oracle.geometry.n_sites
    )

    trace_residual = abs(complex(np.trace(density_matrix)) - 1.0)
    green_hermitian_residual = float(
        np.linalg.norm(green - green.conj().T, ord=np.inf)
    )
    green_number_residual = abs(
        float(np.real(np.trace(green))) - particle_number
    )
    density_pair_diagonal_residual = float(
        np.linalg.norm(np.diag(density_pair) - density, ord=np.inf)
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "algorithm_id": ALGORITHM_ID,
        "runner_manifest_sha256": oracle.manifest_sha256,
        "oracle_boundary": {
            "maximum_sites": MAX_SITES,
            "fock_dimension": layout.dimension,
            "purpose": "N<=9 exact-diagonalization cross-check only",
            "production_use_forbidden": True,
            "geometry_note": (
                "The imported runner geometry permits Lx,Ly>=2. The "
                "preregistered periodic triangular-lattice tori with "
                "Lx=Ly are L=2,N=4 and L=3,N=9."
            ),
        },
        "geometry": {
            "Lx": oracle.geometry.Lx,
            "Ly": oracle.geometry.Ly,
            "n_sites": oracle.geometry.n_sites,
            "n_triangles": oracle.geometry.n_triangles,
        },
        "model": dict(oracle.model),
        "hamiltonian": {
            **hamiltonian_diagnostics,
            "dimension": layout.dimension,
            "minimum_eigenvalue": float(eigenvalues[0]),
            "maximum_eigenvalue": float(eigenvalues[-1]),
        },
        "observables": {
            "Z": z_value,
            "logZ": log_z,
            "scalar": {
                "energy": energy,
                "energy_density": energy / oracle.geometry.n_sites,
                "particle_number": particle_number,
                "particle_number_squared": particle_number_squared,
                "particle_density": (
                    particle_number / oracle.geometry.n_sites
                ),
                "particle_density_squared": (
                    particle_number_squared
                    / (oracle.geometry.n_sites * oracle.geometry.n_sites)
                ),
                "compressibility": compressibility,
            },
            "one_body_green": {
                "definition": "G[i,j]=Tr(rho c_i^dagger c_j)",
                **_complex_matrix(green),
            },
            "momentum": momentum_observables(
                oracle.geometry,
                green,
                density,
                density_pair,
                oracle.momenta,
            ),
            "momentum_definition": {
                "one_body": "phase^dagger G phase / N",
                "density_raw": "phase^dagger <n_i n_j> phase / N",
                "density_mode": "phase^dagger <n_i> / sqrt(N)",
                "density_connected_from_means": (
                    "density_raw-abs(density_mode)^2"
                ),
            },
        },
        "diagnostics": {
            "density_matrix_trace_residual": float(trace_residual),
            "green_hermitian_residual_inf": green_hermitian_residual,
            "green_trace_minus_particle_number_abs": (
                green_number_residual
            ),
            "density_pair_diagonal_residual_inf": (
                density_pair_diagonal_residual
            ),
            "raw_particle_number_variance": raw_number_variance,
            "variance_roundoff_tolerance": variance_roundoff_tolerance,
            "partition_function_note": (
                "Z is null only if exp(logZ) exceeds float range"
                if z_value is None
                else "Z represented as float"
            ),
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="single-run large_lattice_ctqmc manifest",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new JSON output file",
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        raise EDOracleError(
            f"refusing to overwrite existing output: {args.output}"
        )
    payload = run_oracle(args.manifest)
    ctqmc.atomic_write_json(args.output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "algorithm_id": ALGORITHM_ID,
                "output": str(args.output),
                "n_sites": payload["geometry"]["n_sites"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
