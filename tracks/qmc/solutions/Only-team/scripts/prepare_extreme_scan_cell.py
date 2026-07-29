#!/usr/bin/env python3
"""Prepare and finalize one challenge extreme-size scan cell."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tomllib
from pathlib import Path
from typing import Any


EXPECTED_SETTINGS = {
    "J1": -1.0,
    "J2": 0.0,
    "IfSetDltau": True,
    "FixedDltau": 0.013,
    "nLocal": 1,
    "nWolff": 5,
    "nWarm": 10000,
    "NmBin": 32,
    "NSwep": 2000,
    "NmMeaConfg": 10,
    "discard_initial_bins": 1,
    "trim_extrema": True,
    "statistics_mode": "bin_sem",
    "initial_state": "random",
    "nprocs": 32,
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_run_dir(repo_root: Path, declared: str) -> Path:
    run_dir = (repo_root / declared).resolve()
    allowed = (
        repo_root / "tracks" / "qmc" / "results" / "Only-team"
    ).resolve()
    run_dir.relative_to(allowed)
    return run_dir


def validate_settings(settings: dict[str, Any]) -> None:
    for key, expected in EXPECTED_SETTINGS.items():
        actual = settings.get(key)
        if actual != expected:
            raise ValueError(
                f"run setting {key}={actual!r}, expected {expected!r}"
            )


def select_cell(
    spec: dict[str, Any],
    index: int,
    role: str,
) -> dict[str, Any]:
    if role not in ("min", "max", "scan"):
        raise ValueError("role must be min, max, or scan")
    cells = spec.get("cells")
    if not isinstance(cells, list) or not 1 <= index <= len(cells):
        raise ValueError(f"cell index {index} is outside the run specification")
    cell = cells[index - 1]
    params = cell["params"]
    lattice = params["lattice"]
    if lattice not in ("triangular", "honeycomb"):
        raise ValueError(f"unsupported lattice {lattice!r}")

    settings = spec["settings"]
    validate_settings(settings)
    if role == "scan":
        required = ("L", "hTrfd", "FixedDltau", "scan_kind", "seed")
        missing = [name for name in required if name not in params]
        if missing:
            raise ValueError(f"scan cell is missing parameters {missing}")
        size = int(params["L"])
        field = float(params["hTrfd"])
        requested_step = float(params["FixedDltau"])
        seed = int(params["seed"])
        if size < 3:
            raise ValueError("scan size must be at least 3")
        if field <= 0 or requested_step <= 0 or seed < 0:
            raise ValueError("scan field, time step, and seed must be valid")
        if params["scan_kind"] not in ("main", "dtau"):
            raise ValueError("scan_kind must be main or dtau")
        return {
            "cell_id": cell["cell_id"],
            "lattice": lattice,
            "L": size,
            "hTrfd": field,
            "FixedDltau": requested_step,
            "scan_kind": params["scan_kind"],
            "seed": seed,
        }

    field_index = params["field_index"]
    if not isinstance(field_index, int):
        raise ValueError("field_index must be an integer")
    fields = settings["fields"][lattice]
    if not 1 <= field_index <= len(fields):
        raise ValueError(f"field index {field_index} is invalid for {lattice}")
    size = settings["sizes"][role][lattice]
    field = fields[field_index - 1]
    base_seed = int(settings["base_seed"])
    role_code = 1 if role == "min" else 2
    lattice_code = 1 if lattice == "triangular" else 2
    seed = (
        base_seed * 10000
        + role_code * 1000
        + lattice_code * 100
        + field_index
    )
    return {
        "cell_id": cell["cell_id"],
        "lattice": lattice,
        "field_index": field_index,
        "L": size,
        "hTrfd": field,
        "FixedDltau": settings["FixedDltau"],
        "scan_kind": "extreme",
        "seed": seed,
    }


def config_text(
    selected: dict[str, Any],
    settings: dict[str, Any],
    output_dir: str,
) -> tuple[str, float, int]:
    size = int(selected["L"])
    field = float(selected["hTrfd"])
    beta = size / field
    requested_step = float(selected["FixedDltau"])
    ltrot = math.ceil(beta / requested_step)
    if ltrot % 2:
        ltrot += 1
    text = f"""lattice = "{selected['lattice']}"

NumL1 = {size}
NumL2 = {size}

J1 = -1.0
J2 = 0.0
hTrfd = {field!r}

BetaT = {beta!r}
IfSetDltau = true
FixedDltau = {requested_step!r}
LTrot = {ltrot}

nLocal = 1
nWolff = 5

nWarm = 10000
NmBin = 32
NSwep = 2000
NmMeaConfg = 10

discard_initial_bins = 1
trim_extrema = true
statistics_mode = "bin_sem"

seed = {selected['seed']}
initial_state = "random"

output_dir = "{output_dir}"
"""
    return text, beta, ltrot


def prepare(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve()
    run_spec = Path(args.run_spec)
    if not run_spec.is_absolute():
        run_spec = repo_root / run_spec
    spec = load_json(run_spec.resolve())
    selected = select_cell(spec, args.index, args.role)
    run_dir = checked_run_dir(repo_root, spec["run_dir"])
    cell_dir = run_dir / "cells" / selected["cell_id"]
    if cell_dir.exists():
        raise FileExistsError(f"refusing to overwrite cell directory {cell_dir}")
    cell_dir.mkdir(parents=True)
    qmc_dir = cell_dir / "qmc"
    output_dir = qmc_dir.relative_to(repo_root).as_posix()
    config, beta, input_ltrot = config_text(
        selected,
        spec["settings"],
        output_dir,
    )
    config_path = cell_dir / "config.toml"
    atomic_text(config_path, config)
    context = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "run_spec": str(run_spec.resolve()),
        "run_dir": str(run_dir),
        "cell_id": selected["cell_id"],
        "role": args.role,
        "params": {
            "lattice": selected["lattice"],
            "L": selected["L"],
            "hTrfd": selected["hTrfd"],
            "FixedDltau": selected["FixedDltau"],
            "scan_kind": selected["scan_kind"],
        },
        "settings": spec["settings"],
        "derived_input": {
            "BetaT": beta,
            "input_LTrot": input_ltrot,
            "seed": selected["seed"],
        },
        "repo_root": str(repo_root),
        "config_path": str(config_path),
        "qmc_dir": str(qmc_dir),
    }
    context_path = cell_dir / "cell_context.json"
    atomic_text(context_path, json.dumps(context, indent=2, sort_keys=True) + "\n")
    print(context_path, flush=True)


def require_equal(actual: Any, expected: Any, name: str) -> None:
    if actual != expected:
        raise ValueError(f"{name}={actual!r}, expected {expected!r}")


def finalize(args: argparse.Namespace) -> None:
    context_path = Path(args.context).resolve()
    context = load_json(context_path)
    qmc_dir = Path(context["qmc_dir"])
    expected_files = ["bins.csv", "metadata.toml", "results.csv"]
    actual_files = sorted(path.name for path in qmc_dir.iterdir() if path.is_file())
    require_equal(actual_files, expected_files, "QMC output files")

    with (qmc_dir / "bins.csv").open(
        newline="",
        encoding="utf-8",
    ) as stream:
        bins = list(csv.DictReader(stream))
    require_equal(len(bins), 32, "bin count")
    require_equal([int(row["bin"]) for row in bins], list(range(1, 33)), "bins")
    for row in bins:
        values = [float(row[key]) for key in ("m2_bin", "m4_bin", "Q_bin")]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("nonfinite bin value")

    with (qmc_dir / "metadata.toml").open("rb") as stream:
        metadata = tomllib.load(stream)
    actual = metadata["actual_parameters"]
    params = context["params"]
    settings = context["settings"]
    for key, expected in {
        "lattice": params["lattice"],
        "NumL1": params["L"],
        "NumL2": params["L"],
        "J1": settings["J1"],
        "J2": settings["J2"],
        "hTrfd": params["hTrfd"],
        "FixedDltau": params["FixedDltau"],
        "nLocal": settings["nLocal"],
        "nWolff": settings["nWolff"],
    }.items():
        require_equal(actual[key], expected, f"metadata {key}")
    beta = params["L"] / params["hTrfd"]
    if not math.isclose(actual["BetaT"], beta, rel_tol=0, abs_tol=1e-14):
        raise ValueError("metadata BetaT does not equal L/hTrfd")
    if not math.isclose(
        actual["Dltau"],
        actual["BetaT"] / actual["LTrot"],
        rel_tol=0,
        abs_tol=1e-15,
    ):
        raise ValueError("metadata Dltau is inconsistent")
    seeds = metadata["runtime"]["rank_seeds"]
    require_equal(len(seeds), settings["nprocs"], "rank seed count")
    require_equal(len(set(seeds)), settings["nprocs"], "distinct rank seed count")

    with (qmc_dir / "results.csv").open(
        newline="",
        encoding="utf-8",
    ) as stream:
        result_rows = list(csv.DictReader(stream))
    require_equal(len(result_rows), 1, "results row count")
    result = result_rows[0]
    require_equal(int(result["nprocs"]), settings["nprocs"], "result nprocs")
    expected_measurements = (
        settings["nprocs"] * settings["NmBin"] * settings["NSwep"]
    )
    require_equal(
        int(result["total_measurements"]),
        expected_measurements,
        "total measurements",
    )

    manifest = {
        "schema_version": 1,
        "state": "success",
        "run_id": context["run_id"],
        "cell_id": context["cell_id"],
        "role": context["role"],
        "params": params,
        "settings": settings,
        "actual_parameters": actual,
        "observables": {
            "m2": float(result["m2"]),
            "m2_error": float(result["m2_error"]),
            "binder_Q": float(result["binder_Q"]),
            "binder_Q_error": float(result["binder_Q_error"]),
        },
        "diagnostics": metadata["diagnostics"],
        "runtime": {
            "job_id": args.job_id,
            "array_task_id": args.array_task_id,
            "wall_time_seconds": metadata["runtime"]["wall_time_seconds"],
            "mpi_size": metadata["runtime"]["mpi_size"],
            "rank_seed_count": len(seeds),
        },
        "hashes": {
            name: file_digest(qmc_dir / name) for name in expected_files
        }
        | {
            "config.toml": file_digest(context_path.parent / "config.toml"),
            "cell_context.json": file_digest(context_path),
        },
    }
    manifest_path = context_path.parent / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite manifest {manifest_path}")
    atomic_text(
        manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    print(manifest_path, flush=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subparsers = root.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--run-spec", required=True)
    prepare_parser.add_argument("--index", required=True, type=int)
    prepare_parser.add_argument(
        "--role",
        required=True,
        choices=("min", "max", "scan"),
    )
    prepare_parser.add_argument("--repo-root", required=True)
    prepare_parser.set_defaults(function=prepare)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--context", required=True)
    finalize_parser.add_argument("--job-id", required=True)
    finalize_parser.add_argument("--array-task-id", required=True)
    finalize_parser.set_defaults(function=finalize)
    return root


def main() -> None:
    args = parser().parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
