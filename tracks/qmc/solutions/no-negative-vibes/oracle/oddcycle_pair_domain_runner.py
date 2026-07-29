"""Resumable high-throughput runner for two-point oddcycle alphabets."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

from .oddcycle_contraction_sdp import common_metric_sdp, common_metric_sdp_for_points
from .oddcycle_joint_words import exhaustive_joint_short_words, joint_alphabet
from .oddcycle_path_metric import last_letter_path_metric_sdp


JointWordsFunction = Callable[..., dict[str, object]]
MetricFunction = Callable[..., dict[str, object]]
PathMetricFunction = Callable[..., dict[str, object]]
OrientationFunction = Callable[..., dict[str, object]]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.floating, float)) and not math.isfinite(float(value)):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """Publish one complete manifest without exposing a partial JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(
                json.dumps(
                    _json_safe(payload),
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        temporary.replace(path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _successful_manifest(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("compute_success") is True


def _error_record(error: Exception) -> dict[str, object]:
    return {
        "status": "compute-error",
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _finish(
    manifest: dict[str, object],
    started: float,
    *,
    classification: str,
    compute_success: bool,
    first_failure: str | None,
) -> dict[str, object]:
    manifest["classification"] = classification
    manifest["compute_success"] = compute_success
    manifest["first_failure"] = first_failure
    manifest["elapsed_seconds"] = time.perf_counter() - started
    return manifest


def _finite_float(params: Mapping[str, object], key: str) -> float:
    value = float(params[key])
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def _points_from_params(
    params: Mapping[str, object],
) -> tuple[tuple[float, float, float], ...]:
    p_low = _finite_float(params, "p_low")
    p_high = _finite_float(params, "p_high")
    q = _finite_float(params, "q")
    r = _finite_float(params, "r")
    if not p_low < p_high:
        raise ValueError("p_low must be strictly below p_high")
    return ((p_low, q, r), (p_high, q, r))


def _sdp_options(settings: Mapping[str, object]) -> dict[str, object]:
    options: dict[str, object] = {}
    if "sdp_solver" in settings:
        options["solver"] = settings["sdp_solver"]
    if "sdp_validation_tolerance" in settings:
        options["validation_tolerance"] = settings["sdp_validation_tolerance"]
    if "sdp_solver_options" in settings:
        options["solver_options"] = settings["sdp_solver_options"]
    return options


def _path_metric_options(settings: Mapping[str, object]) -> dict[str, object]:
    """Return only options accepted by ``last_letter_path_metric_sdp``."""

    return {
        key: value
        for key, value in _sdp_options(settings).items()
        if key in {"solver", "validation_tolerance"}
    }


def _short_word_options(settings: Mapping[str, object]) -> dict[str, object]:
    depth = settings.get("short_word_depth", 6)
    if isinstance(depth, bool) or depth != 6:
        raise ValueError("short_word_depth must be exactly 6 for this protocol")
    options: dict[str, object] = {
        "max_depth": 6
    }
    if "max_level_matrices" in settings:
        options["max_level_matrices"] = settings["max_level_matrices"]
    if "determinant_tolerance" in settings:
        options["determinant_tolerance"] = settings["determinant_tolerance"]
    return options


def numerical_time_orientation(
    points: Sequence[Sequence[float]],
    metrics: Sequence[Sequence[Sequence[float]]],
    *,
    tolerance: float = 1.0e-7,
) -> dict[str, object]:
    """Synchronize future-sheet signs for a numerical path-metric solution.

    The supplied metrics must have one positive and four negative directions.
    Their positive eigenvectors are oriented from state zero, then every
    inverse transition is checked with the selected sheet signs.
    """

    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and nonnegative")
    atoms = tuple(joint_alphabet(points))
    values = tuple(
        0.5 * (np.asarray(metric, dtype=float) + np.asarray(metric, dtype=float).T)
        for metric in metrics
    )
    if len(values) != len(atoms):
        raise ValueError("one path metric is required per alphabet atom")
    if not values or any(value.shape != (5, 5) for value in values):
        raise ValueError("path metrics must be finite five-by-five matrices")
    if any(not np.all(np.isfinite(value)) for value in values):
        raise ValueError("path metrics must be finite")
    eigenpairs = tuple(np.linalg.eigh(value) for value in values)
    time_vectors = tuple(vectors[:, -1] for _, vectors in eigenpairs)
    norms = tuple(
        float(vector @ metric @ vector)
        for vector, metric in zip(time_vectors, values, strict=True)
    )
    inertias = tuple(
        {
            "positive": int(np.count_nonzero(eigenvalues > tolerance)),
            "negative": int(np.count_nonzero(eigenvalues < -tolerance)),
            "zero": int(np.count_nonzero(np.abs(eigenvalues) <= tolerance)),
        }
        for eigenvalues, _ in eigenpairs
    )
    valid_inertia = all(
        inertia == {"positive": 1, "negative": 4, "zero": 0}
        for inertia in inertias
    )
    raw_scalars = np.asarray(
        [
            [
                float(
                    time_vectors[previous]
                    @ values[previous]
                    @ np.linalg.solve(atom, time_vectors[current])
                )
                for current, atom in enumerate(atoms)
            ]
            for previous in range(len(atoms))
        ],
        dtype=float,
    )
    signs = np.ones(len(atoms), dtype=float)
    if np.all(np.isfinite(raw_scalars)) and np.all(
        np.abs(raw_scalars[1:, 0]) > tolerance
    ):
        signs[1:] = np.sign(raw_scalars[1:, 0])
    oriented_scalars = signs[:, None] * signs[None, :] * raw_scalars
    finite_scalars = bool(np.all(np.isfinite(oriented_scalars)))
    minimum_scalar = (
        float(np.min(oriented_scalars)) if finite_scalars else float("nan")
    )
    determinant_values = tuple(float(np.linalg.det(atom)) for atom in atoms)
    time_like = all(norm > tolerance for norm in norms)
    future_preserving = (
        valid_inertia
        and time_like
        and finite_scalars
        and minimum_scalar > tolerance
        and all(determinant > tolerance for determinant in determinant_values)
    )
    return {
        "status": (
            "time-orientation-passed"
            if future_preserving
            else "time-orientation-failed"
        ),
        "points": [list(point) for point in points],
        "metric_inertias": list(inertias),
        "time_vectors": [vector.tolist() for vector in time_vectors],
        "orientation_signs": [int(sign) for sign in signs],
        "time_like_norms": list(norms),
        "minimum_oriented_scalar": minimum_scalar,
        "all_inverse_transitions_future_preserving": future_preserving,
        "atom_determinants": list(determinant_values),
    }


def _candidate_score(manifest: Mapping[str, object]) -> dict[str, float | None]:
    endpoint_metrics = manifest["endpoint_metrics"]
    assert isinstance(endpoint_metrics, Mapping)
    endpoint_margins = [
        endpoint_metrics[key].get("verified_margin")
        for key in ("p_low", "p_high")
        if isinstance(endpoint_metrics[key], Mapping)
    ]

    def value(record: object, key: str) -> float | None:
        if not isinstance(record, Mapping):
            return None
        candidate = record.get(key)
        return float(candidate) if isinstance(candidate, (int, float)) else None

    finite_endpoints = [
        float(margin)
        for margin in endpoint_margins
        if isinstance(margin, (int, float)) and math.isfinite(float(margin))
    ]
    return {
        "minimum_determinant": value(manifest["short_words"], "minimum_determinant"),
        "endpoint_minimum_margin": min(finite_endpoints) if finite_endpoints else None,
        "joint_metric_margin": value(manifest["joint_metric"], "verified_margin"),
        "path_metric_margin": value(manifest["path_metric"], "verified_margin"),
        "time_orientation_minimum": value(
            manifest["time_orientation"], "minimum_oriented_scalar"
        ),
    }


def run_cell(
    cell_id: str,
    params: Mapping[str, object],
    settings: Mapping[str, object],
    provenance: Mapping[str, object],
    *,
    joint_words_fn: JointWordsFunction = exhaustive_joint_short_words,
    endpoint_metric_fn: MetricFunction = common_metric_sdp,
    joint_metric_fn: MetricFunction = common_metric_sdp_for_points,
    path_metric_fn: PathMetricFunction = last_letter_path_metric_sdp,
    orientation_fn: OrientationFunction = numerical_time_orientation,
) -> dict[str, object]:
    """Run one pair cell, stopping at its first scientific failed gate."""

    started = time.perf_counter()
    manifest: dict[str, object] = {
        "cell_id": str(cell_id),
        "params": dict(params),
        "settings": dict(settings),
        "provenance": dict(provenance),
        "points": None,
        "short_words": {"status": "not-run"},
        "endpoint_metrics": {
            "p_low": {"status": "not-run"},
            "p_high": {"status": "not-run"},
        },
        "joint_metric": {"status": "not-run"},
        "path_metric": {"status": "not-run"},
        "time_orientation": {"status": "not-run"},
    }
    try:
        points = _points_from_params(params)
    except Exception as error:
        manifest["short_words"] = _error_record(error)
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="parameter-error",
        )
    manifest["points"] = [list(point) for point in points]

    try:
        short_words = joint_words_fn(points, **_short_word_options(settings))
    except Exception as error:
        manifest["short_words"] = _error_record(error)
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="short-word-error",
        )
    manifest["short_words"] = short_words
    if short_words.get("status") != "all-tested-words-positive":
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="short-word-failed",
            compute_success=True,
            first_failure="short-word-gate",
        )

    sdp_options = _sdp_options(settings)
    for label, point in zip(("p_low", "p_high"), points, strict=True):
        try:
            endpoint = endpoint_metric_fn(*point, **sdp_options)
        except Exception as error:
            manifest["endpoint_metrics"][label] = _error_record(error)
            manifest["candidate_score"] = _candidate_score(manifest)
            return _finish(
                manifest,
                started,
                classification="compute-error",
                compute_success=False,
                first_failure="endpoint-metric-error",
            )
        manifest["endpoint_metrics"][label] = endpoint
        if endpoint.get("status") != "strict-common-metric-found":
            manifest["candidate_score"] = _candidate_score(manifest)
            return _finish(
                manifest,
                started,
                classification="endpoint-metric-failed",
                compute_success=True,
                first_failure="endpoint-metric-gate",
            )

    try:
        joint_metric = joint_metric_fn(points, **sdp_options)
    except Exception as error:
        manifest["joint_metric"] = _error_record(error)
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest, started, classification="compute-error", compute_success=False,
            first_failure="joint-metric-error",
        )
    manifest["joint_metric"] = joint_metric
    if joint_metric.get("status") == "strict-common-metric-found":
        manifest["path_metric"] = {"status": "not-run", "reason": "joint-common-metric"}
        manifest["time_orientation"] = {
            "status": "not-run",
            "reason": "joint-common-metric",
        }
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="joint-common-metric",
            compute_success=True,
            first_failure="joint-common-metric",
        )
    if joint_metric.get("status") != "no-strict-common-metric-numerically":
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="joint-metric-inconclusive",
            compute_success=True,
            first_failure="joint-metric-gate",
        )

    try:
        path_metric = path_metric_fn(points, **_path_metric_options(settings))
    except Exception as error:
        manifest["path_metric"] = _error_record(error)
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest, started, classification="compute-error", compute_success=False,
            first_failure="path-metric-error",
        )
    manifest["path_metric"] = path_metric
    if (
        path_metric.get("status") != "strict-last-letter-path-metric-found"
        or path_metric.get("correct_split_inertia") is not True
    ):
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="path-metric-failed",
            compute_success=True,
            first_failure="path-metric-gate",
        )

    try:
        orientation_options: dict[str, object] = {}
        if "time_orientation_tolerance" in settings:
            orientation_options["tolerance"] = settings["time_orientation_tolerance"]
        orientation = orientation_fn(
            points,
            path_metric["metrics"],
            **orientation_options,
        )
    except Exception as error:
        manifest["time_orientation"] = _error_record(error)
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest, started, classification="compute-error", compute_success=False,
            first_failure="time-orientation-error",
        )
    manifest["time_orientation"] = orientation
    if (
        orientation.get("status") != "time-orientation-passed"
        or orientation.get("all_inverse_transitions_future_preserving") is not True
    ):
        manifest["candidate_score"] = _candidate_score(manifest)
        return _finish(
            manifest,
            started,
            classification="time-orientation-failed",
            compute_success=True,
            first_failure="time-orientation-gate",
        )

    manifest["candidate_score"] = _candidate_score(manifest)
    return _finish(
        manifest, started, classification="candidate-survivor", compute_success=True,
        first_failure=None,
    )


def run_spec(
    path: str | Path,
    *,
    workers: int = 1,
    worker_index: int = 0,
    worker_count: int = 1,
    joint_words_fn: JointWordsFunction = exhaustive_joint_short_words,
    endpoint_metric_fn: MetricFunction = common_metric_sdp,
    joint_metric_fn: MetricFunction = common_metric_sdp_for_points,
    path_metric_fn: PathMetricFunction = last_letter_path_metric_sdp,
    orientation_fn: OrientationFunction = numerical_time_orientation,
) -> dict[str, int]:
    """Execute the deterministic virtual-worker shard declared by a spec."""

    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise ValueError("workers must be a positive integer")
    if (
        not isinstance(worker_count, int)
        or isinstance(worker_count, bool)
        or worker_count < 1
        or not isinstance(worker_index, int)
        or isinstance(worker_index, bool)
        or not 0 <= worker_index < worker_count
    ):
        raise ValueError("require 0 <= worker_index < worker_count")
    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cells = spec.get("cells")
    if not isinstance(cells, list):
        raise ValueError("run_spec.json requires a cells list")
    shared_settings = dict(spec.get("settings", {}))
    shared_provenance = dict(spec.get("provenance", {}))
    cell_ids: set[str] = set()
    for cell in cells:
        if (
            not isinstance(cell, Mapping)
            or "cell_id" not in cell
            or "params" not in cell
        ):
            raise ValueError("each cell requires cell_id and params")
        cell_id = str(cell["cell_id"])
        if cell_id in cell_ids:
            raise ValueError(f"duplicate cell_id: {cell_id}")
        cell_ids.add(cell_id)
        cell_settings = cell.get("settings", {})
        if not isinstance(cell_settings, Mapping):
            raise ValueError("cell settings must be an object")
        _short_word_options({**shared_settings, **dict(cell_settings)})
    declared_run_dir = Path(spec.get("run_dir", spec_path.parent))
    run_dir = (
        declared_run_dir
        if declared_run_dir.is_absolute()
        else spec_path.parent / declared_run_dir
    )
    selected = [
        cell for position, cell in enumerate(cells)
        if position % worker_count == worker_index
    ]
    pending: list[Mapping[str, object]] = []
    reused = 0
    for cell in selected:
        manifest_path = run_dir / "cells" / str(cell["cell_id"]) / "manifest.json"
        if _successful_manifest(manifest_path):
            reused += 1
        else:
            pending.append(cell)

    def execute(cell: Mapping[str, object]) -> dict[str, object]:
        manifest = run_cell(
            str(cell["cell_id"]),
            dict(cell["params"]),
            {**shared_settings, **dict(cell.get("settings", {}))},
            {**shared_provenance, **dict(cell.get("provenance", {}))},
            joint_words_fn=joint_words_fn,
            endpoint_metric_fn=endpoint_metric_fn,
            joint_metric_fn=joint_metric_fn,
            path_metric_fn=path_metric_fn,
            orientation_fn=orientation_fn,
        )
        _write_json_atomic(
            run_dir / "cells" / str(cell["cell_id"]) / "manifest.json",
            manifest,
        )
        return manifest

    completed = 0
    compute_errors = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(execute, cell) for cell in pending]
        for future in as_completed(futures):
            manifest = future.result()
            completed += 1
            if manifest["compute_success"] is not True:
                compute_errors += 1
    return {
        "selected": len(selected),
        "completed": completed,
        "reused": reused,
        "compute_errors": compute_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_spec", help="path to generic run_spec.json")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker-index", type=int, default=0)
    parser.add_argument("--worker-count", type=int, default=1)
    arguments = parser.parse_args()
    print(
        json.dumps(
            run_spec(
                arguments.run_spec,
                workers=arguments.workers,
                worker_index=arguments.worker_index,
                worker_count=arguments.worker_count,
            ),
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()


__all__ = ["main", "numerical_time_orientation", "run_cell", "run_spec"]
