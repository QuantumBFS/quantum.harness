"""Research dataset schema, initial conditions, and simulation manifests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.special import erf

from .research_protocol import ConditionSpec, ResearchMatrix


Array = np.ndarray
RESEARCH_DATASET_SCHEMA = 1
REQUIRED_METADATA_KEYS = (
    "schema_version",
    "hamiltonian",
    "delta",
    "J",
    "J2",
    "temperature",
    "mu",
    "orientation",
    "profile",
    "width",
    "background_m",
    "L",
    "boundary_condition",
    "algorithm",
    "time_step",
    "chi_max",
    "truncation_cutoff",
    "discarded_weight_max",
    "source_commit",
    "raw_sha256",
    "preprocessing",
)


@dataclass(frozen=True)
class ResearchDataset:
    """Versioned profile data with optional current, correlation, and FCS data."""

    condition_id: str
    x: Array
    t: Array
    u: Array
    metadata: dict[str, Any]
    m: Array | None = None
    current: Array | None = None
    czz: Array | None = None
    fcs_gamma: Array | None = None
    fcs_logZ: Array | None = None


def initial_profile(
    x: Array,
    *,
    profile: str,
    mu: float,
    orientation: int,
    width: float,
    background_m: float = 0.0,
    center: float = 0.0,
    separation: float = 32.0,
    wavelength: float = 64.0,
) -> Array:
    """Return physical magnetization for a preregistered weak initial state."""

    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or np.any(~np.isfinite(x)):
        raise ValueError("x must be a finite one-dimensional array")
    if float(mu) <= 0 or float(width) <= 0:
        raise ValueError("mu and width must be positive")
    if int(orientation) not in (-1, 1):
        raise ValueError("orientation must be -1 or +1")
    amplitude = 0.5 * np.tanh(float(mu)) * int(orientation)
    coordinate = (x - float(center)) / float(width)
    if profile == "tanh":
        shape = np.tanh(coordinate)
    elif profile == "erf":
        shape = erf(coordinate)
    elif profile == "double_wall":
        if separation <= 0:
            raise ValueError("separation must be positive")
        left = np.tanh((x + 0.5 * separation - center) / width)
        right = np.tanh((x - 0.5 * separation - center) / width)
        shape = left - right - 1.0
    elif profile == "gaussian":
        shape = np.exp(-0.5 * coordinate**2)
    elif profile == "sinusoid":
        if wavelength <= 0:
            raise ValueError("wavelength must be positive")
        shape = np.sin(2.0 * np.pi * (x - center) / float(wavelength))
    else:
        raise ValueError(f"Unknown profile: {profile}")
    return float(background_m) + amplitude * shape


def initial_superposition(components: Iterable[Array]) -> Array:
    """Add registered weak components without hidden normalization."""

    arrays = [np.asarray(component, dtype=float) for component in components]
    if not arrays:
        raise ValueError("At least one component is required")
    if any(array.shape != arrays[0].shape for array in arrays):
        raise ValueError("All components must have the same shape")
    return np.sum(np.stack(arrays, axis=0), axis=0)


def normalized_field(m: Array, *, mu: float, background_m: float = 0.0) -> Array:
    """Convert physical magnetization to the article-normalized field."""

    if float(mu) <= 0:
        raise ValueError("mu must be positive")
    return (np.asarray(m, dtype=float) - float(background_m)) / float(mu)


def validate_research_dataset(dataset: ResearchDataset) -> dict[str, Any]:
    """Validate arrays and provenance without modifying the dataset."""

    x = np.asarray(dataset.x, dtype=float)
    t = np.asarray(dataset.t, dtype=float)
    u = np.asarray(dataset.u, dtype=float)
    if not dataset.condition_id:
        raise ValueError("condition_id must not be empty")
    if x.ndim != 1 or t.ndim != 1 or u.shape != (t.size, x.size):
        raise ValueError("Expected x:(Nx,), t:(Nt,), u:(Nt,Nx)")
    if x.size < 5 or t.size < 2:
        raise ValueError("Dataset grid is too small")
    if np.any(np.diff(x) <= 0) or np.any(np.diff(t) <= 0):
        raise ValueError("x and t must be strictly increasing")
    if np.any(~np.isfinite(u)):
        raise ValueError("u contains non-finite values")
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in dataset.metadata]
    if missing:
        raise ValueError("Missing metadata keys: " + ", ".join(missing))
    if int(dataset.metadata["schema_version"]) != RESEARCH_DATASET_SCHEMA:
        raise ValueError("Unsupported research dataset schema")
    if int(dataset.metadata["orientation"]) not in (-1, 1):
        raise ValueError("metadata orientation must be -1 or +1")
    if float(dataset.metadata["mu"]) <= 0:
        raise ValueError("metadata mu must be positive")

    optional_shapes: dict[str, tuple[int, ...]] = {}
    if dataset.m is not None:
        m = np.asarray(dataset.m, dtype=float)
        if m.shape != u.shape:
            raise ValueError("m must have the same shape as u")
        optional_shapes["m"] = m.shape
    if dataset.current is not None:
        current = np.asarray(dataset.current, dtype=float)
        if current.ndim != 2 or current.shape[0] != t.size or current.shape[1] not in (
            x.size,
            x.size - 1,
        ):
            raise ValueError("current must have shape (Nt,Nx) or (Nt,Nx-1)")
        optional_shapes["current"] = current.shape
    if dataset.czz is not None:
        czz = np.asarray(dataset.czz, dtype=float)
        if czz.shape != u.shape:
            raise ValueError("czz must have the same shape as u")
        optional_shapes["czz"] = czz.shape
    if (dataset.fcs_gamma is None) != (dataset.fcs_logZ is None):
        raise ValueError("fcs_gamma and fcs_logZ must be supplied together")
    if dataset.fcs_gamma is not None:
        gamma = np.asarray(dataset.fcs_gamma, dtype=float)
        logZ = np.asarray(dataset.fcs_logZ)
        if gamma.ndim != 1 or logZ.shape[-1] != gamma.size:
            raise ValueError("Last fcs_logZ axis must match fcs_gamma")
        optional_shapes["fcs_logZ"] = logZ.shape

    edge_n = min(10, max(2, x.size // 20))
    plateau_left = np.mean(u[:, :edge_n], axis=1)
    plateau_right = np.mean(u[:, -edge_n:], axis=1)
    return {
        "condition_id": dataset.condition_id,
        "shape": {"Nt": int(t.size), "Nx": int(x.size)},
        "time_range": [float(t[0]), float(t[-1])],
        "space_range": [float(x[0]), float(x[-1])],
        "left_plateau_range": [
            float(np.min(plateau_left)),
            float(np.max(plateau_left)),
        ],
        "right_plateau_range": [
            float(np.min(plateau_right)),
            float(np.max(plateau_right)),
        ],
        "optional_shapes": {
            key: [int(value) for value in shape]
            for key, shape in optional_shapes.items()
        },
        "valid": True,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot JSON serialize {type(value).__name__}")


def save_research_dataset(dataset: ResearchDataset, path: str | Path) -> None:
    """Validate and save a compressed dataset with JSON metadata."""

    validate_research_dataset(dataset)
    arrays: dict[str, Any] = {
        "condition_id": np.asarray(dataset.condition_id),
        "x": np.asarray(dataset.x, dtype=float),
        "t": np.asarray(dataset.t, dtype=float),
        "u": np.asarray(dataset.u, dtype=float),
        "metadata_json": np.asarray(
            json.dumps(
                dataset.metadata,
                sort_keys=True,
                ensure_ascii=False,
                default=_json_default,
            )
        ),
    }
    for name in ("m", "current", "czz", "fcs_gamma", "fcs_logZ"):
        value = getattr(dataset, name)
        if value is not None:
            arrays[name] = np.asarray(value)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, **arrays)


def load_research_dataset(path: str | Path) -> ResearchDataset:
    """Load and validate a research NPZ without allowing pickle objects."""

    with np.load(Path(path), allow_pickle=False) as raw:
        metadata = json.loads(str(raw["metadata_json"].item()))
        dataset = ResearchDataset(
            condition_id=str(raw["condition_id"].item()),
            x=np.asarray(raw["x"], dtype=float),
            t=np.asarray(raw["t"], dtype=float),
            u=np.asarray(raw["u"], dtype=float),
            metadata=metadata,
            **{
                name: np.asarray(raw[name]) if name in raw.files else None
                for name in ("m", "current", "czz", "fcs_gamma", "fcs_logZ")
            },
        )
    validate_research_dataset(dataset)
    return dataset


def file_sha256(path: str | Path) -> str:
    """Return SHA-256 for provenance manifests."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _observables_for(condition: ConditionSpec, convergence_ids: set[str]) -> list[str]:
    observables = ["magnetization"]
    if condition.condition_id in convergence_ids:
        observables.append("local_spin_current")
    if condition.condition_id in {"amp_mu005_up", "amp_mu005_down"}:
        observables.extend(["czz", "fcs_logZ"])
    return observables


def build_simulation_manifest(
    matrix: ResearchMatrix,
    *,
    matrix_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Expand the frozen matrix into convergence and blinded production jobs."""

    output_root = Path(output_root).resolve()
    convergence_ids = set(matrix.convergence_condition_ids)
    condition_by_id = {
        condition.condition_id: condition for condition in matrix.conditions
    }
    jobs: list[dict[str, Any]] = []

    for condition_id in matrix.convergence_condition_ids:
        condition = condition_by_id[condition_id]
        for level in matrix.convergence_levels:
            level_name = str(level["level"])
            job_id = f"{condition_id}__convergence__{level_name}"
            jobs.append(
                {
                    "job_id": job_id,
                    "condition_id": condition_id,
                    "stage": "convergence",
                    "resolution_level": level_name,
                    "blinded": False,
                    "t_max": 200.0,
                    "output_path": str(
                        output_root / "raw" / "convergence" / f"{job_id}.npz"
                    ),
                    "condition": asdict(condition),
                    "numerics": dict(level),
                    "observables": _observables_for(condition, convergence_ids),
                    "depends_on": [],
                }
            )

    fine = dict(matrix.convergence_levels[-1])
    for condition in matrix.conditions:
        observables = _observables_for(condition, convergence_ids)
        stage_a_id = f"{condition.condition_id}__production_a"
        jobs.append(
            {
                "job_id": stage_a_id,
                "condition_id": condition.condition_id,
                "stage": "production_a",
                "resolution_level": "selected_after_convergence",
                "blinded": False,
                "t_max": matrix.validation_window[1],
                "output_path": str(
                    output_root / "raw" / "production_a" / f"{stage_a_id}.npz"
                ),
                "condition": asdict(condition),
                "numerics": fine,
                "observables": observables,
                "depends_on": (
                    [
                        f"{condition.condition_id}__convergence__fine"
                    ]
                    if condition.condition_id in convergence_ids
                    else list(
                        f"{registered}__convergence__fine"
                        for registered in matrix.convergence_condition_ids
                    )
                ),
            }
        )
        stage_b_id = f"{condition.condition_id}__production_b"
        jobs.append(
            {
                "job_id": stage_b_id,
                "condition_id": condition.condition_id,
                "stage": "production_b",
                "resolution_level": "selected_after_convergence",
                "blinded": True,
                "t_max": matrix.test_window[1],
                "output_path": str(
                    output_root / "raw" / "production_b" / f"{stage_b_id}.npz"
                ),
                "condition": asdict(condition),
                "numerics": fine,
                "observables": observables,
                "depends_on": [stage_a_id],
            }
        )

    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "matrix_path": str(Path(matrix_path).resolve()),
        "matrix_sha256": file_sha256(matrix_path),
        "output_root": str(output_root),
        "job_count": len(jobs),
        "jobs": jobs,
    }
