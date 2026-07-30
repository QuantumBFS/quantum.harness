"""Resumable batch execution for the first odd-cycle local-H search."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp

from oracle.oddcycle_local_hs_exact import exact_local_hs_certificate
from oracle.oddcycle_local_hs_scan import (
    NumericalConeResult,
    TargetConeResult,
    locality_specs,
    scan_positive_local_kernel,
    scan_target_cone,
)
from oracle.oddcycle_local_targets import first_target_library
from oracle.oddcycle_transfer_portfolio import rank_transfer_portfolio
from oracle.oddcycle_word_operator import build_word_dictionary


SETTINGS_SCHEMA = "oddcycle-local-hs-settings-v1"
CELL_SCHEMA = "oddcycle-local-hs-cell-v1"
MANIFEST_SCHEMA = "oddcycle-local-hs-manifest-v1"
PROMOTION_SCHEMA = "oddcycle-local-hs-promotion-v1"
PROMOTION_MANIFEST_SCHEMA = "oddcycle-local-hs-promotion-manifest-v1"
DEFAULT_ACTIVE_TOLERANCE = 1.0e-10
DEFAULT_RESIDUAL_TOLERANCE = 1.0e-9
DEFAULT_PROMOTION_ACTIVE_RAY_LIMIT = 32
TARGET_FAMILIES = (
    "path-t-v",
    "ring-frustrated-t-v",
    "path-correlated-hop",
    "path-pair-hop",
)
_SAFE_CELL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


@dataclass(frozen=True)
class BatchCell:
    """One independent dictionary, free, target, or transfer search cell."""

    id: str
    mode: str
    max_word_length: int
    seed: int = 20260730
    locality: str | None = None
    target_family: str | None = None
    sample_count: int = 0
    promotion_active_ray_limit: int = DEFAULT_PROMOTION_ACTIVE_RAY_LIMIT
    numerical_active_tolerance: float = DEFAULT_ACTIVE_TOLERANCE
    numerical_residual_tolerance: float = DEFAULT_RESIDUAL_TOLERANCE
    python_hash_seed: int = 0


@dataclass(frozen=True)
class BatchSummary:
    """Compact outcome of one resumable invocation."""

    selected: int
    completed: int
    skipped: int
    survivors: int
    infeasible: int
    inconclusive: int
    elapsed_seconds: float
    output_dir: str


@dataclass(frozen=True)
class PromotionSummary:
    """Compact outcome of one resumable exact-promotion invocation."""

    selected: int
    completed: int
    skipped: int
    exact_survivors: int
    inconclusive: int
    elapsed_seconds: float
    output_dir: str


def _positive_integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _finite_positive_float(value: object, name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def _validated_cell_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not _SAFE_CELL_ID.fullmatch(value)
        or ".." in value
    ):
        raise ValueError("cell id must be one safe path component")
    return value


def _cell_from_mapping(
    raw: Mapping[str, object],
    *,
    seed: int,
    promotion_active_ray_limit: int,
    numerical_active_tolerance: float,
    numerical_residual_tolerance: float,
    default_sample_count: int,
    python_hash_seed: int,
) -> BatchCell:
    cell_id = _validated_cell_id(raw.get("id"))
    mode = raw.get("mode")
    if mode not in {"free", "target", "portfolio"}:
        raise ValueError(f"cell {cell_id!r} has an unsupported mode")
    max_word_length = _positive_integer(
        raw.get("max_word_length"),
        f"cell {cell_id!r} max_word_length",
    )
    cell_seed = raw.get("seed", seed)
    if not isinstance(cell_seed, int) or isinstance(cell_seed, bool):
        raise ValueError(f"cell {cell_id!r} seed must be an integer")

    locality = raw.get("locality")
    target_family = raw.get("target_family", raw.get("family"))
    sample_count = raw.get("sample_count", default_sample_count)
    if mode == "free":
        if locality not in locality_specs():
            raise ValueError(f"cell {cell_id!r} has an unknown locality")
        target_family = None
        sample_count = 0
    elif mode == "target":
        if target_family not in TARGET_FAMILIES:
            raise ValueError(f"cell {cell_id!r} has an unknown target family")
        locality = None
        sample_count = 0
    else:
        locality = None
        target_family = None
        sample_count = _nonnegative_integer(
            sample_count,
            f"cell {cell_id!r} sample_count",
        )

    return BatchCell(
        id=cell_id,
        mode=mode,
        max_word_length=max_word_length,
        seed=cell_seed,
        locality=locality if isinstance(locality, str) else None,
        target_family=(
            target_family if isinstance(target_family, str) else None
        ),
        sample_count=sample_count,
        promotion_active_ray_limit=_positive_integer(
            raw.get(
                "promotion_active_ray_limit",
                promotion_active_ray_limit,
            ),
            f"cell {cell_id!r} promotion_active_ray_limit",
        ),
        numerical_active_tolerance=_finite_positive_float(
            raw.get(
                "numerical_active_tolerance",
                numerical_active_tolerance,
            ),
            f"cell {cell_id!r} numerical_active_tolerance",
        ),
        numerical_residual_tolerance=_finite_positive_float(
            raw.get(
                "numerical_residual_tolerance",
                numerical_residual_tolerance,
            ),
            f"cell {cell_id!r} numerical_residual_tolerance",
        ),
        python_hash_seed=_nonnegative_integer(
            raw.get("python_hash_seed", python_hash_seed),
            f"cell {cell_id!r} python_hash_seed",
        ),
    )


def expand_settings(settings: Mapping[str, object]) -> tuple[BatchCell, ...]:
    """Expand explicit or frozen-axis settings into unique ID-sorted cells."""

    if not isinstance(settings, Mapping):
        raise TypeError("settings must be a mapping")
    if settings.get("schema") != SETTINGS_SCHEMA:
        raise ValueError(f"settings schema must be {SETTINGS_SCHEMA!r}")
    seed = settings.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    promotion_limit = _positive_integer(
        settings.get(
            "promotion_active_ray_limit",
            DEFAULT_PROMOTION_ACTIVE_RAY_LIMIT,
        ),
        "promotion_active_ray_limit",
    )
    active_tolerance = _finite_positive_float(
        settings.get(
            "numerical_active_tolerance",
            DEFAULT_ACTIVE_TOLERANCE,
        ),
        "numerical_active_tolerance",
    )
    residual_tolerance = _finite_positive_float(
        settings.get(
            "numerical_residual_tolerance",
            DEFAULT_RESIDUAL_TOLERANCE,
        ),
        "numerical_residual_tolerance",
    )
    sample_count = _nonnegative_integer(
        settings.get("portfolio_sample_count", 0),
        "portfolio_sample_count",
    )
    python_hash_seed = settings.get("python_hash_seed", 0)
    if (
        not isinstance(python_hash_seed, int)
        or isinstance(python_hash_seed, bool)
        or python_hash_seed < 0
    ):
        raise ValueError("python_hash_seed must be a nonnegative integer")

    declared_cells = settings.get("cells")
    if declared_cells is not None:
        if (
            not isinstance(declared_cells, Sequence)
            or isinstance(declared_cells, (str, bytes))
        ):
            raise TypeError("cells must be a sequence of mappings")
        cells = []
        for raw in declared_cells:
            if not isinstance(raw, Mapping):
                raise TypeError("each cell must be a mapping")
            cells.append(
                _cell_from_mapping(
                    raw,
                    seed=seed,
                    promotion_active_ray_limit=promotion_limit,
                    numerical_active_tolerance=active_tolerance,
                    numerical_residual_tolerance=residual_tolerance,
                    default_sample_count=sample_count,
                    python_hash_seed=python_hash_seed,
                )
            )
    else:
        raw_lengths = settings.get("dictionary_lengths")
        if (
            not isinstance(raw_lengths, Sequence)
            or isinstance(raw_lengths, (str, bytes))
            or not raw_lengths
        ):
            raise ValueError("dictionary_lengths must be a nonempty sequence")
        lengths = tuple(
            _positive_integer(value, "dictionary length")
            for value in raw_lengths
        )
        if len(set(lengths)) != len(lengths):
            raise ValueError("dictionary_lengths must be unique")

        raw_localities = settings.get("free_localities")
        if (
            not isinstance(raw_localities, Sequence)
            or isinstance(raw_localities, (str, bytes))
            or not raw_localities
        ):
            raise ValueError("free_localities must be a nonempty sequence")
        localities = tuple(raw_localities)
        known_localities = locality_specs()
        if (
            any(
                not isinstance(name, str) or name not in known_localities
                for name in localities
            )
            or len(set(localities)) != len(localities)
        ):
            raise ValueError("free_localities must name unique locality specs")
        if settings.get("target_library") != "first":
            raise ValueError("target_library must be 'first'")

        cells = []
        for max_word_length in lengths:
            for locality in localities:
                cells.append(
                    BatchCell(
                        id=f"free-l{max_word_length}-{locality}",
                        mode="free",
                        max_word_length=max_word_length,
                        seed=seed,
                        locality=locality,
                        promotion_active_ray_limit=promotion_limit,
                        numerical_active_tolerance=active_tolerance,
                        numerical_residual_tolerance=residual_tolerance,
                        python_hash_seed=python_hash_seed,
                    )
                )
            for family in TARGET_FAMILIES:
                cells.append(
                    BatchCell(
                        id=f"target-l{max_word_length}-{family}",
                        mode="target",
                        max_word_length=max_word_length,
                        seed=seed,
                        target_family=family,
                        promotion_active_ray_limit=promotion_limit,
                        numerical_active_tolerance=active_tolerance,
                        numerical_residual_tolerance=residual_tolerance,
                        python_hash_seed=python_hash_seed,
                    )
                )
            cells.append(
                BatchCell(
                    id=f"portfolio-l{max_word_length}",
                    mode="portfolio",
                    max_word_length=max_word_length,
                    seed=seed,
                    sample_count=sample_count,
                    promotion_active_ray_limit=promotion_limit,
                    numerical_active_tolerance=active_tolerance,
                    numerical_residual_tolerance=residual_tolerance,
                    python_hash_seed=python_hash_seed,
                )
            )

    ordered = tuple(sorted(cells, key=lambda cell: cell.id))
    ids = tuple(cell.id for cell in ordered)
    if len(set(ids)) != len(ids):
        raise ValueError("cell ids must be unique")
    return ordered


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, sp.Rational):
        return {
            "numerator": int(value.p),
            "denominator": int(value.q),
        }
    if isinstance(value, sp.Basic):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_jsonable(item) for item in value]
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _canonical_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _payload_sha256(payload: Mapping[str, object]) -> str:
    unhashed = dict(payload)
    unhashed.pop("payload_sha256", None)
    return hashlib.sha256(_canonical_json(unhashed).encode("utf-8")).hexdigest()


def _active_weights(
    weights: np.ndarray | None,
    active_indices: Sequence[int],
) -> list[float] | None:
    if weights is None:
        return None
    return [float(weights[index]) for index in active_indices]


def _numerical_record(result: NumericalConeResult) -> dict[str, object]:
    return {
        "status": result.status,
        "residual": result.residual,
        "minimum_retained_weight": result.minimum_retained_weight,
        "active_indices": list(result.active_indices),
        "active_weights": _active_weights(
            result.weights,
            result.active_indices,
        ),
        "objective": result.objective,
        "objective_index": result.objective_index,
        "objective_sign": result.objective_sign,
        "solver_message": result.solver_message,
        "iteration_count": result.iteration_count,
    }


def _target_record(result: TargetConeResult) -> dict[str, object]:
    return {
        "status": result.status,
        "target_id": result.target_id,
        "target_parameters": _jsonable(result.target_parameters),
        "residual": result.residual,
        "minimum_retained_weight": result.minimum_retained_weight,
        "active_indices": list(result.active_indices),
        "active_weights": _active_weights(
            result.weights,
            result.active_indices,
        ),
        "target_diagonal_gauge_frustrated": (
            result.target_diagonal_gauge_frustrated
        ),
        "solver_message": result.solver_message,
        "iteration_count": result.iteration_count,
    }


def _promotion_inconclusive(
    reason: str,
    active_ray_count: int,
    *,
    error_type: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema": "oddcycle-local-hs-exact-v1",
        "status": "exact-promotion-inconclusive",
        "reason": reason,
        "active_ray_count": active_ray_count,
    }
    if error_type is not None:
        record["error_type"] = error_type
    return record


def _run_free(
    cell: BatchCell,
    columns: Sequence[object],
) -> tuple[str, dict[str, object]]:
    if cell.locality is None:
        raise ValueError("free cell has no locality")
    spec = locality_specs()[cell.locality]
    scans = scan_positive_local_kernel(columns, spec)
    records = []
    has_inconclusive = False
    numerical_survivor_count = 0
    for scan_index, numerical in enumerate(scans):
        record = _numerical_record(numerical)
        record["scan_index"] = scan_index
        if numerical.status == "numerical-survivor":
            numerical_survivor_count += 1
        elif numerical.status == "solver-inconclusive":
            has_inconclusive = True
        records.append(record)

    if numerical_survivor_count:
        status = "survivor"
    elif has_inconclusive:
        status = "inconclusive"
    else:
        status = "infeasible"
    return status, {
        "locality": cell.locality,
        "scan_count": len(records),
        "numerical_survivor_count": numerical_survivor_count,
        "scans": records,
        "promotion_boundary": (
            "immutable numerical evidence; exact promotion runs separately "
            "with promote_from_payloads"
        ),
    }


def _run_target(
    cell: BatchCell,
    columns: Sequence[object],
) -> tuple[str, dict[str, object]]:
    if cell.target_family is None:
        raise ValueError("target cell has no target family")
    targets = tuple(
        target
        for target in first_target_library()
        if target.family == cell.target_family
    )
    if not targets:
        raise ValueError(f"target family {cell.target_family!r} is empty")
    records = tuple(
        _target_record(scan_target_cone(columns, target))
        for target in targets
    )
    statuses = {record["status"] for record in records}
    if "numerical-survivor" in statuses:
        status = "survivor"
    elif "solver-inconclusive" in statuses:
        status = "inconclusive"
    else:
        status = "infeasible"
    return status, {
        "target_family": cell.target_family,
        "target_count": len(records),
        "numerical_survivor_count": sum(
            record["status"] == "numerical-survivor"
            for record in records
        ),
        "targets": records,
        "promotion_boundary": (
            "target cells are numerical Route-B screens; exact target equality "
            "requires a target-specific rational replay"
        ),
    }


def _run_portfolio(
    cell: BatchCell,
    columns: Sequence[object],
) -> tuple[str, dict[str, object]]:
    records = rank_transfer_portfolio(
        columns,
        seed=cell.seed,
        sample_count=cell.sample_count,
    )
    conclusive = sum(
        record.status == "numerical-log-conclusive"
        for record in records
    )
    status = "survivor" if conclusive else "inconclusive"
    return status, {
        "sample_count": cell.sample_count,
        "conclusive_count": conclusive,
        "records": _jsonable(records),
        "route": "D",
        "exact_locality_claimed": False,
    }


def _compute_cell_payload(cell: BatchCell) -> dict[str, object]:
    columns = build_word_dictionary(cell.max_word_length)
    if cell.mode == "free":
        status, result = _run_free(cell, columns)
    elif cell.mode == "target":
        status, result = _run_target(cell, columns)
    elif cell.mode == "portfolio":
        status, result = _run_portfolio(cell, columns)
    else:
        raise ValueError(f"unsupported cell mode {cell.mode!r}")
    return {
        "schema": CELL_SCHEMA,
        "cell_id": cell.id,
        "cell": _jsonable(cell),
        "status": status,
        "dictionary": {
            "max_word_length": cell.max_word_length,
            "column_count": len(columns),
        },
        "result": _jsonable(result),
    }


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_cell_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid completed cell file {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"completed cell file {path} is not an object")
    if payload.get("schema") != CELL_SCHEMA:
        raise ValueError(f"completed cell file {path} has the wrong schema")
    cell_id = _validated_cell_id(payload.get("cell_id"))
    if path.stem != cell_id:
        raise ValueError(f"cell id does not match file name for {path}")
    if (
        not isinstance(payload.get("cell"), Mapping)
        or payload.get("status")
        not in {"survivor", "infeasible", "inconclusive"}
    ):
        raise ValueError(f"completed cell file {path} lacks terminal fields")
    stored_hash = payload.get("payload_sha256")
    if (
        not isinstance(stored_hash, str)
        or stored_hash != _payload_sha256(payload)
    ):
        raise ValueError(f"payload hash mismatch for cell {cell_id!r}")
    return payload


def _atomic_write_payload(
    payload: dict[str, object],
    final_path: Path,
) -> dict[str, object]:
    payload["payload_sha256"] = _payload_sha256(payload)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(f"{final_path}.tmp")
    encoded = _canonical_json(payload) + "\n"
    with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_path, final_path)
    _fsync_directory(final_path.parent)
    return payload


def run_cell(
    cell: BatchCell,
    output_dir: str | os.PathLike[str],
) -> dict[str, object]:
    """Compute and atomically publish one cell without touching the manifest."""

    if not isinstance(cell, BatchCell):
        raise TypeError("cell must be a BatchCell")
    _validated_cell_id(cell.id)
    root = Path(output_dir)
    cells_dir = root / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    final_path = cells_dir / f"{cell.id}.json"
    if final_path.exists():
        existing = _read_cell_payload(final_path)
        if existing.get("cell") != _jsonable(cell):
            raise ValueError(f"completed cell {cell.id!r} has different settings")
        return existing

    try:
        payload = _compute_cell_payload(cell)
    except Exception as error:
        payload = {
            "schema": CELL_SCHEMA,
            "cell_id": cell.id,
            "cell": _jsonable(cell),
            "status": "inconclusive",
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
    return _atomic_write_payload(payload, final_path)


def _batch_cell_from_json(value: object) -> BatchCell:
    if not isinstance(value, Mapping):
        raise ValueError("cell settings must be an object")
    expected_fields = {field.name for field in fields(BatchCell)}
    if set(value) != expected_fields:
        raise ValueError("cell settings do not match the BatchCell schema")
    try:
        cell = BatchCell(**value)
    except TypeError as error:
        raise ValueError("invalid BatchCell settings") from error
    _validated_cell_id(cell.id)
    return cell


def _cell_settings_sha256(cell: BatchCell) -> str:
    return hashlib.sha256(
        _canonical_json(cell).encode("utf-8")
    ).hexdigest()


def _manifest_record_for_cell(
    cell: BatchCell,
    *,
    payload_sha256: str,
    status: str,
) -> dict[str, object]:
    if status not in {"survivor", "infeasible", "inconclusive"}:
        raise ValueError(f"cell {cell.id!r} has an invalid terminal status")
    if not isinstance(payload_sha256, str):
        raise ValueError(f"cell {cell.id!r} lacks a payload hash")
    return {
        "schema": MANIFEST_SCHEMA,
        "cell_id": cell.id,
        "mode": cell.mode,
        "max_word_length": cell.max_word_length,
        "status": status,
        "cell_settings_sha256": _cell_settings_sha256(cell),
        "payload_sha256": payload_sha256,
        "path": f"cells/{cell.id}.json",
    }


def _manifest_record(payload: Mapping[str, object]) -> dict[str, object]:
    cell_id = _validated_cell_id(payload.get("cell_id"))
    payload_hash = payload.get("payload_sha256")
    status = payload.get("status")
    cell = _batch_cell_from_json(payload.get("cell"))
    if cell.id != cell_id:
        raise ValueError("payload cell settings have a different id")
    if (
        not isinstance(payload_hash, str)
        or status not in {"survivor", "infeasible", "inconclusive"}
    ):
        raise ValueError(f"cell {cell_id!r} lacks manifest fields")
    return _manifest_record_for_cell(
        cell,
        payload_sha256=payload_hash,
        status=status,
    )


def _append_manifest(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(_canonical_json(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _repair_torn_manifest(path: Path, valid_prefix: str) -> None:
    temporary_path = Path(f"{path}.repair.tmp")
    with temporary_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        handle.write(valid_prefix)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_path, path)
    _fsync_directory(path.parent)


def _read_jsonl_records(
    path: Path,
    *,
    schema: str,
    id_field: str,
) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    if not path.exists():
        return records
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"cannot read manifest {path}") from error
    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            if line_number == len(lines) and not text.endswith("\n"):
                prefix_end = text.rfind("\n")
                valid_prefix = (
                    text[: prefix_end + 1] if prefix_end >= 0 else ""
                )
                _repair_torn_manifest(path, valid_prefix)
                break
            raise ValueError(
                f"invalid manifest JSON on line {line_number}"
            ) from error
        if (
            not isinstance(record, dict)
            or record.get("schema") != schema
        ):
            raise ValueError(f"invalid manifest record on line {line_number}")
        record_id = _validated_cell_id(record.get(id_field))
        payload_hash = record.get("payload_sha256")
        if not isinstance(payload_hash, str):
            raise ValueError(
                f"manifest record for {record_id!r} lacks a payload hash"
            )
        prior = records.get(record_id)
        if (
            prior is not None
            and prior.get("payload_sha256") != payload_hash
        ):
            raise ValueError(
                f"conflicting payload hashes for {record_id!r}"
            )
        if (
            prior is not None
            and _canonical_json(prior) != _canonical_json(record)
        ):
            raise ValueError(
                f"conflicting duplicate manifest records for {record_id!r}"
            )
        records[record_id] = record
    return records


def _read_manifest(path: Path) -> dict[str, dict[str, object]]:
    return _read_jsonl_records(
        path,
        schema=MANIFEST_SCHEMA,
        id_field="cell_id",
    )


def _resume_records(
    cells: Sequence[BatchCell],
    output_dir: Path,
    *,
    resume: bool,
) -> dict[str, dict[str, object]]:
    expected = {cell.id: cell for cell in cells}
    manifest_path = output_dir / "manifest.jsonl"
    manifest_records = _read_manifest(manifest_path)
    unknown_manifest = set(manifest_records) - set(expected)
    if unknown_manifest:
        raise ValueError(
            "manifest contains cells outside the requested settings: "
            + ", ".join(sorted(unknown_manifest))
        )
    for cell_id, record in manifest_records.items():
        cell = expected[cell_id]
        if (
            record.get("mode") != cell.mode
            or record.get("max_word_length") != cell.max_word_length
            or record.get("path") != f"cells/{cell_id}.json"
            or record.get("cell_settings_sha256")
            != _cell_settings_sha256(cell)
        ):
            raise ValueError(
                f"manifest record for {cell_id!r} has different settings"
            )

    file_records: dict[str, dict[str, object]] = {}
    cells_dir = output_dir / "cells"
    if cells_dir.exists():
        for path in sorted(cells_dir.glob("*.json")):
            payload = _read_cell_payload(path)
            cell_id = str(payload["cell_id"])
            if cell_id not in expected:
                raise ValueError(
                    f"cell file {cell_id!r} is outside the requested settings"
                )
            if payload.get("cell") != _jsonable(expected[cell_id]):
                raise ValueError(
                    f"completed cell {cell_id!r} has different settings"
                )
            record = _manifest_record(payload)
            prior = manifest_records.get(cell_id)
            if (
                prior is not None
                and prior.get("payload_sha256")
                != record.get("payload_sha256")
            ):
                raise ValueError(
                    f"conflicting payload hashes for cell {cell_id!r}"
                )
            if (
                prior is not None
                and _canonical_json(prior) != _canonical_json(record)
            ):
                raise ValueError(
                    f"manifest metadata conflicts for cell {cell_id!r}"
                )
            file_records[cell_id] = record

    orphan_manifest = set(manifest_records) - set(file_records)
    if orphan_manifest:
        raise ValueError(
            "orphan manifest records lack verified final payloads: "
            + ", ".join(sorted(orphan_manifest))
        )

    if not resume and (manifest_records or file_records):
        raise FileExistsError(
            "output already contains completed cells; use resume=True "
            "or choose a new output directory"
        )

    for cell_id, record in file_records.items():
        if cell_id not in manifest_records:
            _append_manifest(manifest_path, record)
            manifest_records[cell_id] = record
    return file_records


def _promotion_candidates(
    payload_paths: Sequence[str | os.PathLike[str]],
) -> tuple[dict[str, object], ...]:
    candidates = []
    seen_ids = set()
    for raw_path in payload_paths:
        path = Path(raw_path)
        payload = _read_cell_payload(path)
        cell = _batch_cell_from_json(payload["cell"])
        if cell.mode != "free" or cell.locality is None:
            raise ValueError(
                f"promotion source {cell.id!r} is not a free-search cell"
            )
        result = payload.get("result")
        scans = result.get("scans") if isinstance(result, Mapping) else None
        if not isinstance(scans, list):
            raise ValueError(f"promotion source {cell.id!r} lacks scans")
        for fallback_index, scan in enumerate(scans):
            if not isinstance(scan, Mapping):
                raise ValueError(f"promotion source {cell.id!r} has a bad scan")
            if scan.get("status") != "numerical-survivor":
                continue
            scan_index = scan.get("scan_index", fallback_index)
            if (
                not isinstance(scan_index, int)
                or isinstance(scan_index, bool)
                or scan_index < 0
            ):
                raise ValueError(
                    f"promotion source {cell.id!r} has a bad scan index"
                )
            promotion_id = (
                f"{cell.id}--scan-{scan_index:04d}"
            )
            _validated_cell_id(promotion_id)
            if promotion_id in seen_ids:
                raise ValueError(
                    f"duplicate promotion id {promotion_id!r}"
                )
            seen_ids.add(promotion_id)
            candidates.append(
                {
                    "promotion_id": promotion_id,
                    "source_path": str(path),
                    "cell": cell,
                    "source_cell_payload_sha256": payload["payload_sha256"],
                    "scan_index": scan_index,
                    "scan": dict(scan),
                }
            )
    return tuple(
        sorted(candidates, key=lambda candidate: str(candidate["promotion_id"]))
    )


def _promotion_certificate(
    candidate: Mapping[str, object],
    columns: Sequence[object],
) -> dict[str, object]:
    cell = candidate["cell"]
    scan = candidate["scan"]
    if not isinstance(cell, BatchCell) or not isinstance(scan, Mapping):
        raise TypeError("invalid promotion candidate")
    if cell.locality is None:
        raise ValueError("free promotion cell has no locality")
    raw_indices = scan.get("active_indices")
    raw_weights = scan.get("active_weights")
    if (
        not isinstance(raw_indices, list)
        or not isinstance(raw_weights, list)
        or len(raw_indices) != len(raw_weights)
    ):
        return _promotion_inconclusive(
            "numerical survivor lacks matched active indices and weights",
            0,
        )
    active_pairs = []
    for index, weight in zip(raw_indices, raw_weights, strict=True):
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= len(columns)
            or not isinstance(weight, (int, float))
            or isinstance(weight, bool)
            or not math.isfinite(float(weight))
        ):
            return _promotion_inconclusive(
                "numerical survivor has invalid active data",
                len(raw_indices),
            )
        if float(weight) > cell.numerical_active_tolerance:
            active_pairs.append((index, float(weight)))
    residual = scan.get("residual")
    if (
        not isinstance(residual, (int, float))
        or isinstance(residual, bool)
        or not math.isfinite(float(residual))
        or float(residual) > cell.numerical_residual_tolerance
    ):
        return _promotion_inconclusive(
            "numerical residual exceeds the promotion tolerance",
            len(active_pairs),
        )
    if len(active_pairs) > cell.promotion_active_ray_limit:
        return _promotion_inconclusive(
            "active ray count exceeds the promotion limit",
            len(active_pairs),
        )
    if not active_pairs:
        return _promotion_inconclusive(
            "numerical survivor has no retained active rays",
            0,
        )
    active_columns = tuple(columns[index] for index, _weight in active_pairs)
    approximate = np.asarray(
        [weight for _index, weight in active_pairs],
        dtype=float,
    )
    try:
        return exact_local_hs_certificate(
            active_columns,
            approximate,
            locality_specs()[cell.locality],
        )
    except Exception as error:
        return _promotion_inconclusive(
            str(error),
            len(active_pairs),
            error_type=type(error).__name__,
        )


def _promote_source_candidates(
    candidates: Sequence[Mapping[str, object]],
    output_dir: str | os.PathLike[str],
) -> tuple[dict[str, object], ...]:
    if not candidates:
        return ()
    first = candidates[0]
    cell = first["cell"]
    if not isinstance(cell, BatchCell):
        raise TypeError("invalid promotion cell")
    try:
        columns = build_word_dictionary(cell.max_word_length)
        build_error = None
    except Exception as error:
        columns = ()
        build_error = error

    payloads = []
    promotions_dir = Path(output_dir) / "promotions"
    for candidate in candidates:
        promotion_id = str(candidate["promotion_id"])
        if build_error is None:
            certificate = _promotion_certificate(candidate, columns)
        else:
            certificate = _promotion_inconclusive(
                str(build_error),
                0,
                error_type=type(build_error).__name__,
            )
        status = (
            "exact-survivor"
            if certificate.get("status")
            == "exact-local-interacting-hs-survivor"
            else "inconclusive"
        )
        payload = {
            "schema": PROMOTION_SCHEMA,
            "promotion_id": promotion_id,
            "cell_id": cell.id,
            "cell_settings_sha256": _cell_settings_sha256(cell),
            "source_cell_payload_sha256": candidate[
                "source_cell_payload_sha256"
            ],
            "scan_index": candidate["scan_index"],
            "status": status,
            "certificate": _jsonable(certificate),
        }
        final_path = promotions_dir / f"{promotion_id}.json"
        if final_path.exists():
            existing = _read_promotion_payload(final_path)
            if (
                existing.get("source_cell_payload_sha256")
                != payload["source_cell_payload_sha256"]
                or existing.get("cell_settings_sha256")
                != payload["cell_settings_sha256"]
            ):
                raise ValueError(
                    f"promotion {promotion_id!r} has conflicting source data"
                )
            payloads.append(existing)
        else:
            payloads.append(_atomic_write_payload(payload, final_path))
    return tuple(payloads)


def _read_promotion_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid promotion payload {path}") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != PROMOTION_SCHEMA
    ):
        raise ValueError(f"promotion payload {path} has the wrong schema")
    promotion_id = _validated_cell_id(payload.get("promotion_id"))
    if path.stem != promotion_id:
        raise ValueError(f"promotion id does not match file name for {path}")
    stored_hash = payload.get("payload_sha256")
    if (
        not isinstance(stored_hash, str)
        or stored_hash != _payload_sha256(payload)
    ):
        raise ValueError(f"payload hash mismatch for promotion {promotion_id!r}")
    if payload.get("status") not in {"exact-survivor", "inconclusive"}:
        raise ValueError(f"promotion {promotion_id!r} lacks terminal status")
    return payload


def _promotion_manifest_record(
    payload: Mapping[str, object],
) -> dict[str, object]:
    promotion_id = _validated_cell_id(payload.get("promotion_id"))
    return {
        "schema": PROMOTION_MANIFEST_SCHEMA,
        "promotion_id": promotion_id,
        "cell_id": payload.get("cell_id"),
        "scan_index": payload.get("scan_index"),
        "status": payload.get("status"),
        "cell_settings_sha256": payload.get("cell_settings_sha256"),
        "source_cell_payload_sha256": payload.get(
            "source_cell_payload_sha256"
        ),
        "payload_sha256": payload.get("payload_sha256"),
        "path": f"promotions/{promotion_id}.json",
    }


def _promotion_resume_records(
    candidates: Sequence[Mapping[str, object]],
    output_dir: Path,
    *,
    resume: bool,
) -> dict[str, dict[str, object]]:
    expected = {
        str(candidate["promotion_id"]): candidate
        for candidate in candidates
    }
    manifest_path = output_dir / "promotion-manifest.jsonl"
    manifest_records = _read_jsonl_records(
        manifest_path,
        schema=PROMOTION_MANIFEST_SCHEMA,
        id_field="promotion_id",
    )
    unknown = set(manifest_records) - set(expected)
    if unknown:
        raise ValueError(
            "promotion manifest contains unexpected records: "
            + ", ".join(sorted(unknown))
        )
    for promotion_id, record in manifest_records.items():
        candidate = expected[promotion_id]
        cell = candidate["cell"]
        if (
            not isinstance(cell, BatchCell)
            or record.get("cell_id") != cell.id
            or record.get("scan_index") != candidate["scan_index"]
            or record.get("cell_settings_sha256")
            != _cell_settings_sha256(cell)
            or record.get("source_cell_payload_sha256")
            != candidate["source_cell_payload_sha256"]
            or record.get("path")
            != f"promotions/{promotion_id}.json"
        ):
            raise ValueError(
                f"promotion manifest {promotion_id!r} has different settings"
            )

    file_records = {}
    promotions_dir = output_dir / "promotions"
    if promotions_dir.exists():
        for path in sorted(promotions_dir.glob("*.json")):
            payload = _read_promotion_payload(path)
            promotion_id = str(payload["promotion_id"])
            if promotion_id not in expected:
                raise ValueError(
                    f"promotion {promotion_id!r} is outside requested sources"
                )
            record = _promotion_manifest_record(payload)
            candidate = expected[promotion_id]
            cell = candidate["cell"]
            if (
                not isinstance(cell, BatchCell)
                or record["cell_settings_sha256"]
                != _cell_settings_sha256(cell)
                or record["source_cell_payload_sha256"]
                != candidate["source_cell_payload_sha256"]
            ):
                raise ValueError(
                    f"promotion {promotion_id!r} has different source data"
                )
            prior = manifest_records.get(promotion_id)
            if prior is not None and _canonical_json(prior) != _canonical_json(
                record
            ):
                raise ValueError(
                    f"promotion {promotion_id!r} conflicts with its manifest"
                )
            file_records[promotion_id] = record

    orphan = set(manifest_records) - set(file_records)
    if orphan:
        raise ValueError(
            "orphan promotion manifest records lack verified payloads: "
            + ", ".join(sorted(orphan))
        )
    if not resume and (manifest_records or file_records):
        raise FileExistsError(
            "promotion output already contains completed records"
        )
    for promotion_id, record in file_records.items():
        if promotion_id not in manifest_records:
            _append_manifest(manifest_path, record)
    return file_records


def promote_from_payloads(
    payload_paths: Sequence[str | os.PathLike[str]],
    output_dir: str | os.PathLike[str],
    workers: int,
    resume: bool = True,
) -> PromotionSummary:
    """Exactly promote numerical free-cell survivors without mutating sources."""

    worker_count = _positive_integer(workers, "workers")
    if not isinstance(resume, bool):
        raise TypeError("resume must be a boolean")
    candidates = _promotion_candidates(payload_paths)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "promotions").mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    completed_records = _promotion_resume_records(
        candidates,
        root,
        resume=resume,
    )
    skipped = len(completed_records)
    pending = tuple(
        candidate
        for candidate in candidates
        if candidate["promotion_id"] not in completed_records
    )
    by_source: dict[str, list[Mapping[str, object]]] = {}
    for candidate in pending:
        by_source.setdefault(str(candidate["source_path"]), []).append(candidate)
    manifest_path = root / "promotion-manifest.jsonl"
    newly_completed = 0

    def record_payloads(payloads: Sequence[Mapping[str, object]]) -> None:
        nonlocal newly_completed
        for payload in payloads:
            record = _promotion_manifest_record(payload)
            _append_manifest(manifest_path, record)
            completed_records[str(record["promotion_id"])] = record
            newly_completed += 1
            counts = _promotion_status_counts(completed_records)
            print(
                "promotion-progress "
                f"completed={len(completed_records)}/{len(candidates)} "
                f"exact-survivor={counts['exact-survivor']} "
                f"inconclusive={counts['inconclusive']} "
                f"elapsed={time.monotonic() - started:.3f}s "
                f"output={root}",
                flush=True,
            )

    groups = tuple(by_source.values())
    if worker_count == 1:
        for group in groups:
            record_payloads(_promote_source_candidates(group, root))
    elif groups:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_promote_source_candidates, group, root): group
                for group in groups
            }
            for future in as_completed(futures):
                record_payloads(future.result())
    if not groups:
        counts = _promotion_status_counts(completed_records)
        print(
            "promotion-progress "
            f"completed={len(completed_records)}/{len(candidates)} "
            f"exact-survivor={counts['exact-survivor']} "
            f"inconclusive={counts['inconclusive']} "
            f"elapsed={time.monotonic() - started:.3f}s "
            f"output={root}",
            flush=True,
        )

    counts = _promotion_status_counts(completed_records)
    return PromotionSummary(
        selected=len(candidates),
        completed=newly_completed,
        skipped=skipped,
        exact_survivors=counts["exact-survivor"],
        inconclusive=counts["inconclusive"],
        elapsed_seconds=time.monotonic() - started,
        output_dir=str(root),
    )


def _promotion_status_counts(
    records: Mapping[str, Mapping[str, object]],
) -> dict[str, int]:
    counts = {"exact-survivor": 0, "inconclusive": 0}
    for record in records.values():
        status = record.get("status")
        if status not in counts:
            raise ValueError("promotion record has an unknown status")
        counts[str(status)] += 1
    return counts


def _status_counts(
    records: Mapping[str, Mapping[str, object]],
) -> dict[str, int]:
    counts = {"survivor": 0, "infeasible": 0, "inconclusive": 0}
    for record in records.values():
        status = record.get("status")
        if status not in counts:
            raise ValueError("completed record has an unknown status")
        counts[str(status)] += 1
    return counts


def _print_progress(
    *,
    processed: int,
    total: int,
    counts: Mapping[str, int],
    started: float,
    output_dir: Path,
) -> None:
    print(
        "progress "
        f"completed={processed}/{total} "
        f"survivor={counts['survivor']} "
        f"infeasible={counts['infeasible']} "
        f"inconclusive={counts['inconclusive']} "
        f"elapsed={time.monotonic() - started:.3f}s "
        f"output={output_dir}",
        flush=True,
    )


def run_batch(
    settings: Mapping[str, object],
    output_dir: str | os.PathLike[str],
    workers: int,
    resume: bool = True,
) -> BatchSummary:
    """Run independent cells and append parent-owned progress durably."""

    worker_count = _positive_integer(workers, "workers")
    if not isinstance(resume, bool):
        raise TypeError("resume must be a boolean")
    cells = expand_settings(settings)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "cells").mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    completed_records = _resume_records(cells, root, resume=resume)
    skipped = len(completed_records)
    pending = tuple(
        cell for cell in cells if cell.id not in completed_records
    )
    counts = _status_counts(completed_records)
    manifest_path = root / "manifest.jsonl"
    newly_completed = 0

    if pending:
        if worker_count == 1:
            for cell in pending:
                payload = run_cell(cell, root)
                record = _manifest_record(payload)
                _append_manifest(manifest_path, record)
                completed_records[cell.id] = record
                counts[str(record["status"])] += 1
                newly_completed += 1
                _print_progress(
                    processed=len(completed_records),
                    total=len(cells),
                    counts=counts,
                    started=started,
                    output_dir=root,
                )
        else:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(run_cell, cell, root): cell
                    for cell in pending
                }
                for future in as_completed(futures):
                    cell = futures[future]
                    payload = future.result()
                    record = _manifest_record(payload)
                    _append_manifest(manifest_path, record)
                    completed_records[cell.id] = record
                    counts[str(record["status"])] += 1
                    newly_completed += 1
                    _print_progress(
                        processed=len(completed_records),
                        total=len(cells),
                        counts=counts,
                        started=started,
                        output_dir=root,
                    )
    else:
        _print_progress(
            processed=len(completed_records),
            total=len(cells),
            counts=counts,
            started=started,
            output_dir=root,
        )

    elapsed = time.monotonic() - started
    return BatchSummary(
        selected=len(cells),
        completed=newly_completed,
        skipped=skipped,
        survivors=counts["survivor"],
        infeasible=counts["infeasible"],
        inconclusive=counts["inconclusive"],
        elapsed_seconds=elapsed,
        output_dir=str(root),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the resumable odd-cycle local-H first batch.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--settings", type=Path)
    source.add_argument(
        "--promote-from",
        type=Path,
        help="cell payload file or directory copied to the WSL promotion host",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--workers",
        type=int,
        default=max((os.cpu_count() or 1) - 2, 1),
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = _build_parser().parse_args(argv)
    if args.promote_from is not None:
        if args.promote_from.is_dir():
            payload_paths = tuple(sorted(args.promote_from.glob("*.json")))
        else:
            payload_paths = (args.promote_from,)
        summary = promote_from_payloads(
            payload_paths,
            args.output,
            workers=args.workers,
            resume=args.resume,
        )
    else:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
        summary = run_batch(
            settings,
            args.output,
            workers=args.workers,
            resume=args.resume,
        )
    print(_canonical_json(asdict(summary)), flush=True)
    return 0


__all__ = [
    "BatchCell",
    "BatchSummary",
    "PromotionSummary",
    "expand_settings",
    "main",
    "promote_from_payloads",
    "run_batch",
    "run_cell",
]


if __name__ == "__main__":
    raise SystemExit(main())
