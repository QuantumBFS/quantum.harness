"""Strict readers for Rust-generated clean-Ising data."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


class DataContractError(ValueError):
    """Raised when raw records do not match the run manifest."""


EXACT_FIELDS = {
    "schema_version",
    "l",
    "k",
    "boundary_conditions",
    "lambda0",
    "g_exact",
    "iterations",
    "relative_change",
    "residual",
    "elapsed_s",
}

MC_FIELDS = {
    "schema_version",
    "l",
    "m",
    "k_index",
    "k",
    "replica",
    "seed",
    "thermal_sweeps",
    "measurement_sweeps",
    "block_index",
    "block_sweeps",
    "cluster_updates_per_sweep",
    "energy_sum",
    "energy_squared_sum",
    "measurement_count",
    "mean_cluster_size",
    "max_cluster_size",
    "cumulative_elapsed_s",
}


def load_manifest(path: Path) -> Dict[str, Any]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataContractError(f"cannot read manifest {path}: {error}") from error
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("config"), dict):
        raise DataContractError("manifest must use schema_version 1 and contain config")
    return manifest


def load_exact(path: Path, manifest: Mapping[str, Any]) -> List[Dict[str, Any]]:
    records, complete = _read_jsonl_prefix(Path(path))
    if not complete:
        raise DataContractError(f"{path} has an incomplete final JSONL record")
    config = _config(manifest)
    expected_widths = list(config["widths"])
    seen = set()
    for record in records:
        _require_fields(record, EXACT_FIELDS, "exact")
        _require_finite_numbers(record, "exact")
        if record["schema_version"] != manifest["schema_version"]:
            raise DataContractError("mixed schema versions in exact records")
        l_value = record["l"]
        if l_value in seen:
            raise DataContractError(f"duplicate exact width {l_value}")
        seen.add(l_value)
        if l_value not in expected_widths:
            raise DataContractError(f"unexpected exact width {l_value}")
        if abs(record["k"] - config["critical_k"]) > 1.0e-15:
            raise DataContractError(f"exact K mismatch at L={l_value}")
        if record["boundary_conditions"] != "periodic-cylinder":
            raise DataContractError(f"unexpected exact boundary at L={l_value}")
    if seen != set(expected_widths):
        missing = sorted(set(expected_widths) - seen)
        raise DataContractError(f"missing exact widths {missing}")
    return sorted(records, key=lambda record: record["l"])


def load_mc_blocks(path: Path, manifest: Mapping[str, Any]) -> List[Dict[str, Any]]:
    records, complete = _read_jsonl_prefix(Path(path))
    if not complete:
        raise DataContractError(f"{path} has an incomplete final JSONL record")
    config = _config(manifest)
    mc = config["mc"]
    expected_blocks = mc["measurement_sweeps"] // mc["block_sweeps"]
    expected_seeds = {
        (item["l"], item["k_index"], item["replica"]): item["seed"]
        for item in manifest.get("seeds", [])
    }
    seen = set()
    for record in records:
        _require_fields(record, MC_FIELDS, "Monte Carlo")
        _require_finite_numbers(record, "Monte Carlo")
        key = (
            record["l"],
            record["k_index"],
            record["replica"],
            record["block_index"],
        )
        if key in seen:
            raise DataContractError(f"duplicate Monte Carlo block key {key}")
        seen.add(key)
        _validate_mc_record(record, manifest, expected_seeds)

    expected = {
        (l_value, k_index, replica, block_index)
        for l_value in config["widths"]
        for k_index in range(mc["grid_intervals"] + 1)
        for replica in range(mc["replicas"])
        for block_index in range(expected_blocks)
    }
    if seen != expected:
        missing = len(expected - seen)
        unexpected = len(seen - expected)
        raise DataContractError(
            f"incomplete Monte Carlo grid: missing={missing}, unexpected={unexpected}"
        )
    return sorted(
        records,
        key=lambda record: (
            record["l"],
            record["k_index"],
            record["replica"],
            record["block_index"],
        ),
    )


def _read_jsonl_prefix(path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise DataContractError(f"cannot read JSONL {path}: {error}") from error
    lines = raw.splitlines(keepends=True)
    records = []
    for index, raw_line in enumerate(lines):
        text = raw_line.decode("utf-8").strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            is_final = index == len(lines) - 1
            if is_final and not raw.endswith(b"\n"):
                return records, False
            raise DataContractError(
                f"invalid complete JSONL record {index + 1} in {path}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise DataContractError(f"JSONL record {index + 1} in {path} is not an object")
        records.append(value)
    return records, True


def _config(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    if manifest.get("schema_version") != 1:
        raise DataContractError("manifest schema_version must be 1")
    config = manifest.get("config")
    if not isinstance(config, Mapping) or not isinstance(config.get("mc"), Mapping):
        raise DataContractError("manifest is missing config.mc")
    return config


def _validate_mc_record(
    record: Mapping[str, Any],
    manifest: Mapping[str, Any],
    expected_seeds: Mapping[Tuple[int, int, int], int],
) -> None:
    config = _config(manifest)
    mc = config["mc"]
    l_value = record["l"]
    k_index = record["k_index"]
    replica = record["replica"]
    if record["schema_version"] != manifest["schema_version"]:
        raise DataContractError("mixed schema versions in Monte Carlo records")
    if l_value not in config["widths"]:
        raise DataContractError(f"unexpected Monte Carlo width {l_value}")
    if record["m"] != l_value * config["aspect_ratio"]:
        raise DataContractError(f"geometry mismatch at L={l_value}")
    if not 0 <= k_index <= mc["grid_intervals"]:
        raise DataContractError(f"K_index out of range: {k_index}")
    expected_k = config["critical_k"] * k_index / mc["grid_intervals"]
    if abs(record["k"] - expected_k) > 1.0e-15:
        raise DataContractError(f"K mismatch at L={l_value}, K_index={k_index}")
    if not 0 <= replica < mc["replicas"]:
        raise DataContractError(f"replica out of range: {replica}")
    for field in ("thermal_sweeps", "measurement_sweeps", "block_sweeps"):
        expected_value = (
            mc["thermal_sweeps"] if field == "thermal_sweeps" else mc[field]
        )
        if record[field] != expected_value:
            raise DataContractError(f"{field} mismatch for {(l_value, k_index, replica)}")
    if record["measurement_count"] != mc["block_sweeps"]:
        raise DataContractError("measurement_count must equal block_sweeps")
    seed_key = (l_value, k_index, replica)
    if expected_seeds and expected_seeds.get(seed_key) != record["seed"]:
        raise DataContractError(f"seed mismatch for {seed_key}")


def _require_fields(record: Mapping[str, Any], required: Sequence[str], label: str) -> None:
    missing = sorted(set(required) - set(record))
    if missing:
        raise DataContractError(f"{label} record is missing fields {missing}")


def _require_finite_numbers(record: Mapping[str, Any], label: str) -> None:
    for key, value in record.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise DataContractError(f"{label} record field {key} is non-finite")
