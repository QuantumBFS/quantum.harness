"""Physical projected-contact zero-mode bundles over the closed twist torus."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .bundle_geometry import BundleGeometry, analyze_frame_bundle
from .lattice import BosonBasis, build_kapit_laughlin_parent


MODULE_ROOT = Path(__file__).resolve().parent
SCRIPT_ROOT = MODULE_ROOT.parent
DEFAULT_CHECKPOINT_ROOT = SCRIPT_ROOT / "output" / "topology_v3_checkpoints"


@dataclass(frozen=True)
class TwistBundle:
    """One exact quasihole bundle sampled over a periodic twist mesh."""

    N: int
    n_flux: int
    rank: int
    mesh: int
    energies: np.ndarray
    kernel_bandwidth: np.ndarray
    external_gap: np.ndarray
    coefficient_frames: np.ndarray
    orbital_frames: np.ndarray
    geometry: BundleGeometry
    observed_rank_min: int
    observed_rank_max: int
    runtime_seconds: float
    identity: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(
    N: int,
    n_flux: int,
    rank: int,
    mesh: int,
) -> dict[str, Any]:
    sources = (
        MODULE_ROOT / "twist_bundle.py",
        MODULE_ROOT / "bundle_geometry.py",
        MODULE_ROOT / "lattice.py",
    )
    return {
        "version": "v3",
        "N": int(N),
        "n_flux": int(n_flux),
        "rank": int(rank),
        "mesh": int(mesh),
        "sources": {
            path.name: _sha256(path)
            for path in sources
        },
        "numpy": np.__version__,
    }


def _identity_hash(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_twist_bundle(
    N: int,
    n_flux: int,
    rank: int,
    mesh: int,
    progress: Callable[[str], None] | None = None,
) -> TwistBundle:
    """Diagonalize an exact projected-contact bundle on a periodic mesh."""

    particles = int(N)
    flux = int(n_flux)
    target_rank = int(rank)
    grid = int(mesh)
    if particles < 2 or flux < 2 * particles or target_rank < 1:
        raise ValueError("invalid quasihole bundle parameters")
    if grid < 3:
        raise ValueError("twist mesh must be at least three")
    seed_system = build_kapit_laughlin_parent(
        particles,
        flux,
        0.0,
        0.0,
    )
    basis_dimension = seed_system.basis.dimension
    physical_sites = seed_system.orbitals.shape[0]
    energies = np.empty((grid, grid, target_rank + 1), dtype=float)
    bandwidth = np.empty((grid, grid), dtype=float)
    gap = np.empty_like(bandwidth)
    coefficient_frames = np.empty(
        (grid, grid, basis_dimension, target_rank),
        dtype=complex,
    )
    orbital_frames = np.empty(
        (grid, grid, physical_sites, flux),
        dtype=complex,
    )
    observed_ranks: list[int] = []
    twists = 2.0 * np.pi * np.arange(grid) / grid
    started = time.perf_counter()
    for ix, theta_x in enumerate(twists):
        for iy, theta_y in enumerate(twists):
            system = build_kapit_laughlin_parent(
                particles,
                flux,
                float(theta_x),
                float(theta_y),
            )
            parent = system.parent.toarray()
            parent = 0.5 * (parent + parent.conj().T)
            values, vectors = np.linalg.eigh(parent)
            tolerance = 1e-9 * max(float(np.max(np.abs(values))), 1.0)
            observed = int(
                np.count_nonzero(np.abs(values) < tolerance)
            )
            observed_ranks.append(observed)
            if observed != target_rank:
                raise RuntimeError(
                    f"twist ({ix},{iy}) has {observed} zero modes, "
                    f"expected {target_rank}"
                )
            energies[ix, iy] = values[: target_rank + 1]
            bandwidth[ix, iy] = float(np.ptp(values[:target_rank]))
            gap[ix, iy] = float(
                values[target_rank] - values[target_rank - 1]
            )
            coefficient_frames[ix, iy] = vectors[:, :target_rank]
            orbital_frames[ix, iy] = system.orbitals
        if progress is not None:
            progress(f"N={particles}, mesh={grid}: row {ix + 1}/{grid}")
    basis = BosonBasis(flux, particles)
    geometry = analyze_frame_bundle(
        coefficient_frames,
        orbital_frames,
        basis,
    )
    return TwistBundle(
        N=particles,
        n_flux=flux,
        rank=target_rank,
        mesh=grid,
        energies=energies,
        kernel_bandwidth=bandwidth,
        external_gap=gap,
        coefficient_frames=coefficient_frames,
        orbital_frames=orbital_frames,
        geometry=geometry,
        observed_rank_min=min(observed_ranks),
        observed_rank_max=max(observed_ranks),
        runtime_seconds=time.perf_counter() - started,
        identity=_identity(particles, flux, target_rank, grid),
    )


def save_twist_bundle(
    bundle: TwistBundle,
    metadata_path: Path,
) -> None:
    """Save a bundle and its hash-locked array checkpoint."""

    metadata = Path(metadata_path)
    arrays_path = metadata.with_suffix(".npz")
    metadata.parent.mkdir(parents=True, exist_ok=True)
    temporary_arrays = arrays_path.with_suffix(".npz.tmp")
    with temporary_arrays.open("wb") as handle:
        np.savez_compressed(
            handle,
            energies=bundle.energies,
            kernel_bandwidth=bundle.kernel_bandwidth,
            external_gap=bundle.external_gap,
            coefficient_frames=bundle.coefficient_frames,
            orbital_frames=bundle.orbital_frames,
        )
    temporary_arrays.replace(arrays_path)
    payload = {
        "identity": bundle.identity,
        "identity_hash": _identity_hash(bundle.identity),
        "arrays": arrays_path.name,
        "arrays_sha256": _sha256(arrays_path),
        "observed_rank_min": bundle.observed_rank_min,
        "observed_rank_max": bundle.observed_rank_max,
        "runtime_seconds": bundle.runtime_seconds,
        "geometry": {
            "chern_determinant": bundle.geometry.chern_determinant,
            "chern_trace_log": bundle.geometry.chern_trace_log,
            "determinant_branch_margin": (
                bundle.geometry.determinant_branch_margin
            ),
            "minimum_overlap_singular_value": (
                bundle.geometry.minimum_overlap_singular_value
            ),
            "maximum_link_unitarity_error": (
                bundle.geometry.maximum_link_unitarity_error
            ),
            "maximum_plaquette_unitarity_error": (
                bundle.geometry.maximum_plaquette_unitarity_error
            ),
        },
    }
    temporary_metadata = metadata.with_suffix(".json.tmp")
    temporary_metadata.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary_metadata.replace(metadata)


def load_twist_bundle(
    metadata_path: Path,
    expected_N: int,
    expected_n_flux: int,
    expected_rank: int,
    expected_mesh: int,
) -> TwistBundle:
    """Load a checkpoint only if its identity and array hash match."""

    metadata = Path(metadata_path)
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    expected_identity = _identity(
        expected_N,
        expected_n_flux,
        expected_rank,
        expected_mesh,
    )
    if (
        payload.get("identity") != expected_identity
        or payload.get("identity_hash") != _identity_hash(expected_identity)
    ):
        raise ValueError("checkpoint identity mismatch")
    arrays_path = metadata.with_name(payload["arrays"])
    if payload.get("arrays_sha256") != _sha256(arrays_path):
        raise ValueError("checkpoint array hash mismatch")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        energies = np.asarray(arrays["energies"], dtype=float)
        bandwidth = np.asarray(arrays["kernel_bandwidth"], dtype=float)
        gap = np.asarray(arrays["external_gap"], dtype=float)
        coefficient_frames = np.asarray(
            arrays["coefficient_frames"],
            dtype=complex,
        )
        orbital_frames = np.asarray(
            arrays["orbital_frames"],
            dtype=complex,
        )
    basis = BosonBasis(expected_n_flux, expected_N)
    geometry = analyze_frame_bundle(
        coefficient_frames,
        orbital_frames,
        basis,
    )
    return TwistBundle(
        N=int(expected_N),
        n_flux=int(expected_n_flux),
        rank=int(expected_rank),
        mesh=int(expected_mesh),
        energies=energies,
        kernel_bandwidth=bandwidth,
        external_gap=gap,
        coefficient_frames=coefficient_frames,
        orbital_frames=orbital_frames,
        geometry=geometry,
        observed_rank_min=int(payload["observed_rank_min"]),
        observed_rank_max=int(payload["observed_rank_max"]),
        runtime_seconds=float(payload["runtime_seconds"]),
        identity=expected_identity,
    )


def default_checkpoint_path(
    N: int,
    mesh: int,
) -> Path:
    return DEFAULT_CHECKPOINT_ROOT / f"N{int(N)}_mesh{int(mesh)}_twist_bundle_v3.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--n-flux", type=int, required=True)
    parser.add_argument("--rank", type=int, required=True)
    parser.add_argument("--mesh", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    bundle = build_twist_bundle(
        arguments.N,
        arguments.n_flux,
        arguments.rank,
        arguments.mesh,
        progress=print,
    )
    output = arguments.output or default_checkpoint_path(
        arguments.N,
        arguments.mesh,
    )
    save_twist_bundle(bundle, output)
    print(json.dumps(
        {
            "output": str(output),
            "chern_determinant": bundle.geometry.chern_determinant,
            "chern_trace_log": bundle.geometry.chern_trace_log,
            "minimum_gap": float(np.min(bundle.external_gap)),
            "minimum_overlap_singular_value": (
                bundle.geometry.minimum_overlap_singular_value
            ),
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
