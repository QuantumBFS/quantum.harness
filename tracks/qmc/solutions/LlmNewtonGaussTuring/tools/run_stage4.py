#!/usr/bin/env python3
"""Plan, execute, and collect resumable Challenge 148 SSE cells."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_SCHEMA = "challenge148-raw-v1"
MANIFEST_SCHEMA = "challenge148-cell-v1"
PROTOCOL_ID = "c148-prereg-v1+rev1+rev2+rev3"
SOLUTION_REL = Path("tracks/qmc/solutions/LlmNewtonGaussTuring")
SOURCE_PATHS = (SOLUTION_REL, Path("scripts/parameter_scan.py"))
REQUIRED_RAW_COLUMNS = {
    "raw_schema", "lattice", "geometry_version", "L", "N", "Nb", "h",
    "beta", "c_tau", "seed", "initial_state", "bin", "n_thermal",
    "n_bins", "sweeps_per_bin", "update_algorithm", "sign_avg",
    "config_checked", "consistency_failures", "E", "equal_m2", "equal_m4",
    "spacetime_m2", "spacetime_m4", "S0", "Sq", "q_norm", "q_count",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=repo_root(), check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def source_provenance() -> dict[str, Any]:
    scoped = git_output(
        "status", "--porcelain", "--untracked-files=all", "--",
        *(str(path) for path in SOURCE_PATHS),
    )
    repository = git_output("status", "--porcelain", "--untracked-files=all")
    return {
        "source_commit": git_output("rev-parse", "HEAD"),
        "source_dirty": bool(scoped),
        "source_dirty_paths": scoped.splitlines(),
        "repository_dirty": bool(repository),
    }


def parse_csv_values(value: str, converter):
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("list must not be empty")
    try:
        return [converter(item) for item in items]
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def stable_seed(run_id: str, params: dict[str, Any]) -> int:
    material = json.dumps(
        {"run_id": run_id, **params}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    value = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return value or 1


def geometry_metadata(lattice: str, L: int) -> dict[str, Any]:
    sqrt3 = math.sqrt(3.0)
    if lattice == "square":
        return {
            "version": "square-v1", "boundary": "periodic", "N": L * L,
            "Nb": 2 * L * L, "coordination": 4,
            "primitive_vectors": [[1.0, 0.0], [0.0, 1.0]],
            "basis": [[0.0, 0.0]],
            "reciprocal_vectors": [[2.0 * math.pi, 0.0], [0.0, 2.0 * math.pi]],
        }
    if lattice == "triangular":
        return {
            "version": "triangular-v1", "boundary": "periodic", "N": L * L,
            "Nb": 3 * L * L, "coordination": 6,
            "primitive_vectors": [[1.0, 0.0], [0.5, sqrt3 / 2.0]],
            "basis": [[0.0, 0.0]],
            "reciprocal_vectors": [
                [2.0 * math.pi, -2.0 * math.pi / sqrt3],
                [0.0, 4.0 * math.pi / sqrt3],
            ],
        }
    if lattice == "honeycomb":
        return {
            "version": "honeycomb-v2", "boundary": "periodic", "N": 2 * L * L,
            "Nb": 3 * L * L, "coordination": 3,
            "primitive_vectors": [[0.5, sqrt3 / 2.0], [-0.5, sqrt3 / 2.0]],
            "basis": [[0.0, 0.0], [0.0, 1.0 / sqrt3]],
            "reciprocal_vectors": [
                [2.0 * math.pi, 2.0 * math.pi / sqrt3],
                [-2.0 * math.pi, 2.0 * math.pi / sqrt3],
            ],
        }
    raise ValueError(f"unsupported lattice {lattice!r}")


def resolve_run_dir(run_spec: dict[str, Any], spec_path: Path) -> Path:
    configured = Path(run_spec.get("run_dir", spec_path.parent))
    if configured.is_absolute():
        return configured
    return repo_root() / configured


def load_spec(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec.get("cells"), list) or not spec["cells"]:
        raise ValueError("run spec has no cells")
    return spec


def select_cell(spec: dict[str, Any], selector: str | None) -> dict[str, Any]:
    selector = selector or os.environ.get("HARNESS_CELL_ID") or os.environ.get("SLURM_ARRAY_TASK_ID")
    if not selector:
        raise ValueError("cell selector required via --cell, HARNESS_CELL_ID, or SLURM_ARRAY_TASK_ID")
    if selector.isdigit():
        index = int(selector) - 1
        if index < 0 or index >= len(spec["cells"]):
            raise ValueError(f"cell index {selector} is outside 1..{len(spec['cells'])}")
        return spec["cells"][index]
    matches = [cell for cell in spec["cells"] if cell.get("cell_id") == selector]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate cell id {selector!r}")
    return matches[0]


def build_info(sampler: Path) -> dict[str, str]:
    completed = subprocess.run(
        [str(sampler), "--build-info"], check=True, text=True,
        stdout=subprocess.PIPE,
    )
    result = {}
    for line in completed.stdout.splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError(f"malformed sampler build-info line: {line!r}")
        result[key] = value
    required = {"raw_schema", "compiler_id", "compiler_version", "build_type"}
    if required - result.keys():
        raise ValueError("sampler build-info is incomplete")
    if result["raw_schema"] != RAW_SCHEMA:
        raise ValueError("sampler raw schema does not match runner")
    return result


def validate_raw(path: Path, params: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_RAW_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"raw file is missing columns: {sorted(missing)}")
        rows = list(reader)
    expected_bins = int(settings["n_bins"])
    if len(rows) != expected_bins:
        raise ValueError(f"raw file has {len(rows)} bins, expected {expected_bins}")

    geometry = geometry_metadata(str(params["lattice"]), int(params["L"]))
    numeric_columns = (
        "h", "beta", "c_tau", "sign_avg", "E", "equal_m2", "equal_m4",
        "spacetime_m2", "spacetime_m4", "S0", "Sq", "q_norm",
    )
    for index, row in enumerate(rows):
        numeric = [float(row[name]) for name in numeric_columns]
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError(f"non-finite raw value in bin {index}")
        expected = {
            "raw_schema": RAW_SCHEMA,
            "lattice": str(params["lattice"]),
            "geometry_version": geometry["version"],
            "L": str(params["L"]),
            "N": str(geometry["N"]),
            "Nb": str(geometry["Nb"]),
            "seed": str(params["seed"]),
            "initial_state": str(params["initial_state"]),
            "bin": str(index),
            "n_thermal": str(settings["n_thermal"]),
            "n_bins": str(settings["n_bins"]),
            "sweeps_per_bin": str(settings["sweeps_per_bin"]),
            "update_algorithm": "sandvik-tfim-cluster-v1",
            "config_checked": "0",
            "consistency_failures": "-1",
        }
        for key, value in expected.items():
            if row[key] != value:
                raise ValueError(f"raw bin {index} has {key}={row[key]!r}, expected {value!r}")
        if not math.isclose(float(row["h"]), float(params["h"]), rel_tol=1e-14):
            raise ValueError(f"raw bin {index} has the wrong field")
        if not math.isclose(float(row["c_tau"]), float(settings["c_tau"]), rel_tol=1e-14):
            raise ValueError(f"raw bin {index} has the wrong c_tau")
        expected_beta = float(settings["c_tau"]) * int(params["L"]) / float(params["h"])
        if not math.isclose(float(row["beta"]), expected_beta, rel_tol=1e-13):
            raise ValueError(f"raw bin {index} violates beta*h/L=c_tau")
        if float(row["sign_avg"]) != 1.0:
            raise ValueError(f"raw bin {index} is not sign-free")
        expected_q_norm = (
            2.0 * math.pi / int(params["L"])
            if params["lattice"] == "square"
            else 4.0 * math.pi / (math.sqrt(3.0) * int(params["L"]))
        )
        expected_q_count = 4 if params["lattice"] == "square" else 6
        if not math.isclose(float(row["q_norm"]), expected_q_norm, rel_tol=1e-13):
            raise ValueError(f"raw bin {index} has incompatible q_norm")
        if int(row["q_count"]) != expected_q_count:
            raise ValueError(f"raw bin {index} has incompatible q_count")

    def mean(name: str) -> float:
        return sum(float(row[name]) for row in rows) / len(rows)

    m2, m4, s0, sq = (mean(name) for name in ("spacetime_m2", "spacetime_m4", "S0", "Sq"))
    q_norm = float(rows[0]["q_norm"])
    denominator = 4.0 * math.sin(q_norm / 2.0) ** 2
    xi2 = (s0 / sq - 1.0) / denominator if sq > 0.0 and denominator > 0.0 else math.nan
    return {
        "rows": rows,
        "geometry": geometry,
        "results": {
            "Q_spacetime": m2 * m2 / m4 if m4 > 0.0 else math.nan,
            "xi_over_L": math.sqrt(xi2) / int(params["L"]) if xi2 > 0.0 else None,
            "energy": mean("E"),
        },
        "diagnostics": {
            "sign_avg": mean("sign_avg"),
            "config_checked": False,
            "consistency_failures": -1,
            "q_norm": q_norm,
            "q_count": int(rows[0]["q_count"]),
        },
    }


def cmd_plan(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id):
        raise ValueError("run id may contain only letters, digits, dot, underscore, and dash")
    sizes = parse_csv_values(args.sizes, int)
    fields = parse_csv_values(args.fields, float)
    replicas = parse_csv_values(args.replicas, int)
    starts = parse_csv_values(args.starts, str)
    if (min(sizes) < 2 or min(replicas) < 0
            or any(not math.isfinite(field) or field <= 0.0 for field in fields)):
        raise ValueError("require L >= 2, h > 0, and replica >= 0")
    for label, values in (("sizes", sizes), ("fields", fields), ("replicas", replicas)):
        if len(set(values)) != len(values):
            raise ValueError(f"{label} must not contain duplicates")
    if sorted(set(starts)) != sorted(starts) or not set(starts) <= {"hot", "cold"}:
        raise ValueError("starts must be unique values chosen from hot,cold")
    if not args.allow_single_start and set(starts) != {"hot", "cold"}:
        raise ValueError("production plans require both hot and cold starts")

    source = source_provenance()
    if source["source_dirty"] and not args.allow_dirty:
        raise ValueError(
            "Challenge 148 source is dirty; commit it before making a production plan "
            "or use --allow-dirty only for a smoke"
        )
    run_dir = repo_root() / "results" / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    axes = {"L": sizes, "h": fields, "initial_state": starts, "replica": replicas}
    settings = {
        "J": 1.0,
        "c_tau": args.c_tau,
        "n_thermal": args.thermal,
        "n_bins": args.bins,
        "sweeps_per_bin": args.sweeps_per_bin,
        "sampler": args.sampler,
        "raw_schema": RAW_SCHEMA,
        "update_algorithm": "sandvik-tfim-cluster-v1",
        "primary_estimator": "Q=<mbar^2>^2/<mbar^4>",
        "secondary_estimator": "xi/L from equal-time S(0)/S(q_min)",
        "required_initial_states": starts,
        "allow_dirty_source": bool(args.allow_dirty),
    }
    provenance = {
        **source,
        "protocol_id": PROTOCOL_ID,
        "challenge_issue": "https://github.com/QuantumBFS/quantum.harness/issues/148",
        "lattice": args.lattice,
        "planned_at": utc_now(),
    }
    inputs = run_dir / ".plan-inputs"
    inputs.mkdir()
    atomic_json(inputs / "axes.json", axes)
    atomic_json(inputs / "settings.json", settings)
    atomic_json(inputs / "provenance.json", provenance)
    command = [
        sys.executable, str(repo_root() / "scripts" / "parameter_scan.py"), "plan",
        "--axes", str(inputs / "axes.json"), "--run-id", args.run_id,
        "--run-dir", str(Path("results") / args.run_id),
        "--settings", str(inputs / "settings.json"),
        "--provenance", str(inputs / "provenance.json"),
    ]
    subprocess.run(command, cwd=repo_root(), check=True)

    spec_path = run_dir / "run_spec.json"
    spec = load_spec(spec_path)
    for cell in spec["cells"]:
        cell["params"]["lattice"] = args.lattice
        cell["params"]["seed"] = stable_seed(args.run_id, cell["params"])
    seeds = [cell["params"]["seed"] for cell in spec["cells"]]
    if len(set(seeds)) != len(seeds):
        raise RuntimeError("deterministic seed collision in run plan")
    spec["assemble"] = {
        "manifest_contract": {
            "schema_version": {"type": "equality", "value": MANIFEST_SCHEMA},
            "status": {"type": "equality", "value": "success"},
            "artifacts.bins.sha256": {"type": "nonempty"},
            "diagnostics.sign_avg": {"type": "equality", "value": 1.0},
        },
        "consensus_fields": [
            "physics.hamiltonian", "settings.update_algorithm", "provenance.protocol_id",
            "provenance.sampler_sha256", "provenance.build.compiler_id",
            "provenance.build.compiler_version", "provenance.build.build_type",
        ],
        "provenance_fields": ["provenance.protocol_id", "provenance.source_commit"],
    }
    atomic_json(spec_path, spec)
    print(f"Challenge 148 plan: {len(spec['cells'])} cells -> {spec_path}")
    print(f"source_commit={source['source_commit']} source_dirty={source['source_dirty']}")


def cmd_run_cell(args: argparse.Namespace) -> None:
    spec_path = args.run_spec.resolve()
    spec = load_spec(spec_path)
    cell = select_cell(spec, args.cell)
    cell_id = cell["cell_id"]
    params = cell["params"]
    settings = {**spec.get("settings", {}), **cell.get("settings", {})}
    run_dir = resolve_run_dir(spec, spec_path)
    cell_dir = run_dir / "cells" / cell_id
    manifest_path = cell_dir / "manifest.json"
    cell_dir.mkdir(parents=True, exist_ok=True)

    if manifest_path.is_file():
        with manifest_path.open(encoding="utf-8") as handle:
            previous = json.load(handle)
        if previous.get("status") == "success":
            raw = cell_dir / previous.get("artifacts", {}).get("bins", {}).get("path", "bins.csv")
            expected_hash = previous.get("artifacts", {}).get("bins", {}).get("sha256")
            if raw.is_file() and expected_hash == sha256_file(raw):
                print(f"{cell_id}: existing success manifest and raw hash verified; skipping")
                return
            raise ValueError(f"{cell_id}: success manifest exists but its raw artifact is invalid")
        if not args.retry_failed:
            raise ValueError(f"{cell_id}: failed manifest exists; pass --retry-failed only after review")

    source = source_provenance()
    planned = spec.get("provenance", {})
    if source["source_commit"] != planned.get("source_commit"):
        raise ValueError("current source commit differs from the run plan")
    if source["source_dirty"] and not settings.get("allow_dirty_source", False):
        raise ValueError("Challenge 148 source became dirty after planning")

    sampler = Path(settings["sampler"])
    if not sampler.is_absolute():
        sampler = repo_root() / sampler
    if not sampler.is_file() or not os.access(sampler, os.X_OK):
        raise ValueError(f"missing executable sampler: {sampler}")
    build = build_info(sampler)
    started_at = utc_now()
    start_clock = time.monotonic()
    temporary_raw = cell_dir / f".bins.csv.{os.getpid()}.tmp"
    final_raw = cell_dir / "bins.csv"

    base_manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "cell_id": cell_id,
        "params": params,
        "settings": settings,
        "provenance": {
            **planned,
            "observed_source_commit": source["source_commit"],
            "observed_source_dirty": source["source_dirty"],
            "sampler_sha256": sha256_file(sampler),
            "build": build,
            "host": socket.gethostname(),
            "platform": platform.platform(),
        },
        "physics": {
            "hamiltonian": "H=-J sum_<ij> sigma_z_i sigma_z_j-h sum_i sigma_x_i",
            "pauli_normalization": True,
            "J": 1.0,
            "h": params["h"],
            "beta": settings["c_tau"] * params["L"] / params["h"],
            "c_tau": settings["c_tau"],
        },
        "started_at": started_at,
    }
    try:
        command = [
            str(sampler), str(params["lattice"]), str(params["L"]),
            format(float(params["h"]), ".17g"), format(float(settings["c_tau"]), ".17g"),
            str(params["seed"]), str(params["initial_state"]),
            str(settings["n_thermal"]), str(settings["n_bins"]),
            str(settings["sweeps_per_bin"]), str(temporary_raw),
        ]
        print(f"{cell_id}: L={params['L']} h={params['h']} start={params['initial_state']} "
              f"replica={params['replica']} seed={params['seed']}", flush=True)
        subprocess.run(command, cwd=repo_root(), check=True)
        validated = validate_raw(temporary_raw, params, settings)
        os.replace(temporary_raw, final_raw)
        raw_hash = sha256_file(final_raw)
        manifest = {
            **base_manifest,
            "status": "success",
            "completed_at": utc_now(),
            "wall_seconds": time.monotonic() - start_clock,
            "geometry": validated["geometry"],
            "sampling": {
                "seed": params["seed"], "replica": params["replica"],
                "initial_state": params["initial_state"],
                "n_thermal": settings["n_thermal"], "n_bins": settings["n_bins"],
                "sweeps_per_bin": settings["sweeps_per_bin"],
            },
            "diagnostics": validated["diagnostics"],
            "results": validated["results"],
            "artifacts": {
                "bins": {"path": "bins.csv", "sha256": raw_hash, "bytes": final_raw.stat().st_size}
            },
        }
        atomic_json(manifest_path, manifest)
        print(f"{cell_id}: success raw_sha256={raw_hash} wall={manifest['wall_seconds']:.3f}s")
    except BaseException as error:
        if temporary_raw.exists():
            temporary_raw.unlink()
        failed = {
            **base_manifest,
            "status": "failed",
            "completed_at": utc_now(),
            "wall_seconds": time.monotonic() - start_clock,
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        atomic_json(manifest_path, failed)
        raise


def validate_manifest(
    spec: dict[str, Any], cell: dict[str, Any], run_dir: Path
) -> tuple[dict[str, Any], Path]:
    path = run_dir / "cells" / cell["cell_id"] / "manifest.json"
    if not path.is_file():
        raise ValueError(f"{cell['cell_id']}: missing manifest")
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("status") != "success":
        raise ValueError(f"{cell['cell_id']}: manifest is not a {MANIFEST_SCHEMA} success")
    if manifest.get("params") != cell.get("params"):
        raise ValueError(f"{cell['cell_id']}: manifest params differ from run spec")
    expected_settings = {**spec.get("settings", {}), **cell.get("settings", {})}
    if manifest.get("settings") != expected_settings:
        raise ValueError(f"{cell['cell_id']}: manifest settings differ from run spec")
    for key in ("protocol_id", "source_commit"):
        if manifest.get("provenance", {}).get(key) != spec.get("provenance", {}).get(key):
            raise ValueError(f"{cell['cell_id']}: provenance {key} mismatch")
    artifact = manifest.get("artifacts", {}).get("bins", {})
    raw = path.parent / artifact.get("path", "")
    if not raw.is_file() or artifact.get("sha256") != sha256_file(raw):
        raise ValueError(f"{cell['cell_id']}: raw artifact hash mismatch")
    validate_raw(raw, cell["params"], expected_settings)
    return manifest, raw


def cmd_collect(args: argparse.Namespace) -> None:
    spec_path = args.run_spec.resolve()
    spec = load_spec(spec_path)
    run_dir = resolve_run_dir(spec, spec_path)
    successes = []
    failures = []
    for cell in spec["cells"]:
        try:
            successes.append((cell, *validate_manifest(spec, cell, run_dir)))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"{cell['cell_id']}: {error}")
    if failures and not args.allow_incomplete:
        raise ValueError("collection refused:\n" + "\n".join(failures))
    if not successes:
        raise ValueError("collection has no valid successful cells")
    sampler_hashes = {manifest["provenance"]["sampler_sha256"] for _, manifest, _ in successes}
    build_contracts = {
        json.dumps(manifest["provenance"]["build"], sort_keys=True)
        for _, manifest, _ in successes
    }
    if len(sampler_hashes) != 1 or len(build_contracts) != 1:
        raise ValueError("successful cells do not share one sampler binary and build contract")

    output = run_dir / f"{spec['run_id']}_bins.csv"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=run_dir)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as destination:
            expected_header = None
            for _, _, raw in successes:
                with raw.open(encoding="utf-8", newline="") as source:
                    header = source.readline()
                    if expected_header is None:
                        expected_header = header
                        destination.write(header)
                    elif header != expected_header:
                        raise ValueError(f"raw header mismatch in {raw}")
                    for line in source:
                        destination.write(line)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, output)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise

    report = {
        "schema_version": "challenge148-collection-v1",
        "run_id": spec["run_id"],
        "completed_at": utc_now(),
        "planned_cells": len(spec["cells"]),
        "successful_cells": len(successes),
        "invalid_or_missing_cells": failures,
        "merged_bins": {
            "path": output.name, "sha256": sha256_file(output), "bytes": output.stat().st_size,
        },
    }
    atomic_json(run_dir / "collection.json", report)

    generic = [
        sys.executable, str(repo_root() / "scripts" / "parameter_scan.py"), "collect",
        "--run-spec", str(spec_path), "--success-field", "status", "--success-value", "success",
        "--value-field", "results.Q_spacetime", "--value-field", "results.xi_over_L",
        "--value-field", "results.energy",
    ]
    subprocess.run(generic, cwd=repo_root(), check=True)
    print(f"merged {len(successes)}/{len(spec['cells'])} cells -> {output}")
    print(f"merged_sha256={report['merged_bins']['sha256']}")
    if failures:
        print(f"WARNING: {len(failures)} cells were invalid or missing", file=sys.stderr)


def cmd_run_local(args: argparse.Namespace) -> None:
    spec_path = args.run_spec.resolve()
    spec = load_spec(spec_path)
    workers = max(1, args.workers)

    def run(cell_id: str) -> None:
        cmd_run_cell(
            argparse.Namespace(
                run_spec=spec_path,
                cell=cell_id,
                retry_failed=args.retry_failed,
            )
        )

    failures = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(run, cell["cell_id"]): cell["cell_id"]
            for cell in spec["cells"]
        }
        for future in as_completed(futures):
            cell_id = futures[future]
            try:
                future.result()
            except Exception as error:
                failures.append(f"{cell_id}: {error}")
    if failures:
        raise RuntimeError("local run failed:\n" + "\n".join(sorted(failures)))
    if args.collect:
        cmd_collect(argparse.Namespace(run_spec=spec_path, allow_incomplete=False))


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--lattice", required=True, choices=("square", "triangular", "honeycomb"))
    plan.add_argument("--sizes", required=True)
    plan.add_argument("--fields", required=True)
    plan.add_argument("--replicas", default="0,1")
    plan.add_argument("--starts", default="hot,cold")
    plan.add_argument("--c-tau", type=float, default=1.0)
    plan.add_argument("--thermal", type=int, required=True)
    plan.add_argument("--bins", type=int, required=True)
    plan.add_argument("--sweeps-per-bin", type=int, required=True)
    plan.add_argument(
        "--sampler",
        default=str(SOLUTION_REL / "build-production" / "sample_stage4_cell"),
    )
    plan.add_argument("--allow-dirty", action="store_true")
    plan.add_argument("--allow-single-start", action="store_true")
    plan.set_defaults(function=cmd_plan)

    run_cell = subparsers.add_parser("run-cell")
    run_cell.add_argument("--run-spec", type=Path, required=True)
    run_cell.add_argument("--cell")
    run_cell.add_argument("--retry-failed", action="store_true")
    run_cell.set_defaults(function=cmd_run_cell)

    run_local = subparsers.add_parser("run-local")
    run_local.add_argument("--run-spec", type=Path, required=True)
    run_local.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    run_local.add_argument("--retry-failed", action="store_true")
    run_local.add_argument("--collect", action="store_true")
    run_local.set_defaults(function=cmd_run_local)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--run-spec", type=Path, required=True)
    collect.add_argument("--allow-incomplete", action="store_true")
    collect.set_defaults(function=cmd_collect)
    return parser


def main() -> None:
    args = make_parser().parse_args()
    if args.command == "plan":
        if (not math.isfinite(args.c_tau) or args.c_tau <= 0.0
                or args.thermal < 0 or args.bins <= 0 or args.sweeps_per_bin <= 0):
            raise ValueError("require c_tau > 0, thermal >= 0, bins > 0, sweeps_per_bin > 0")
    args.function(args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"run_stage4: {error}", file=sys.stderr)
        raise SystemExit(1) from error
