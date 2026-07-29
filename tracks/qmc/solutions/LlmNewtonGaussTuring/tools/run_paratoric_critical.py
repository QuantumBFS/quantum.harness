#!/usr/bin/env python3
"""Plan, execute, collect, and cost ParaToric critical-observable scans."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


PROTOCOL_ID = "c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6+rev7"
RAW_SCHEMA = "challenge148-paratoric-critical-v1"
MANIFEST_SCHEMA = "challenge148-paratoric-critical-cell-v1"
PARATORIC_COMMIT = "e7bc78446ba083aeeae1ada9c883fa03bf205890"
PARATORIC_PATCH_SHA256 = (
    "3bd7a5231c38f048035f13f23bb20162b6f6e1f2264270dbeb61e2ce35073d30"
)
MAX_PARATORIC_SEED = 2**31 - 1
SOLUTION_REL = Path("tracks/qmc/solutions/LlmNewtonGaussTuring")
SOURCE_PATHS = (SOLUTION_REL, Path("scripts/parameter_scan.py"))
PRODUCTION = {
    "triangular": {
        "gauge_lattice": "honeycomb",
        "sizes": [8, 12, 16, 20, 24, 32],
        "fields": [
            4.740, 4.745, 4.750, 4.755, 4.760, 4.765, 4.770,
            4.775, 4.780, 4.785, 4.790, 4.795, 4.800,
        ],
    },
    "honeycomb": {
        "gauge_lattice": "triangular",
        "sizes": [10, 12, 16, 20, 24, 32],
        "fields": [2.110, 2.115, 2.120, 2.125, 2.130, 2.135, 2.140, 2.145, 2.150],
    },
}
PILOT = {
    "triangular": {"sizes": [8, 16], "fields": [4.770]},
    "honeycomb": {"sizes": [10, 16], "fields": [2.130]},
}
REQUIRED_RAW_COLUMNS = {
    "raw_schema", "target_lattice", "gauge_lattice", "L", "beta", "field",
    "mu", "seed", "sample", "n_thermal", "n_samples", "updates_between",
    "percolation_probability", "staggered_imaginary_times", "star_x",
    "package_tau_percolation", "package_tau_sit", "package_tau_star",
}
HEARTBEAT_SECONDS = 30.0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


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


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(repo_root()))
    except ValueError:
        return str(resolved)


def resolve_setting_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


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
    return {
        "source_commit": git_output("rev-parse", "HEAD"),
        "source_dirty": bool(scoped),
        "source_dirty_paths": scoped.splitlines(),
    }


def validate_source_provenance(
    planned: dict[str, Any], observed: dict[str, Any]
) -> None:
    planned_commit = planned.get("source_commit")
    if not isinstance(planned_commit, str) or not planned_commit:
        raise ValueError("run spec has no planned source commit")
    if planned.get("source_dirty") is not False:
        raise ValueError("run spec was not planned from a clean scoped source tree")
    if observed.get("source_dirty"):
        raise ValueError("execution requires a clean scoped source tree")
    if observed.get("source_commit") != planned_commit:
        raise ValueError("current source commit differs from the planned commit")


def stable_seed(run_id: str, params: dict[str, Any]) -> int:
    material = json.dumps(
        {"protocol_id": PROTOCOL_ID, "run_id": run_id, **params},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    value = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return value % MAX_PARATORIC_SEED + 1


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_run_dir(spec: dict[str, Any], spec_path: Path) -> Path:
    configured = Path(spec.get("run_dir", spec_path.parent))
    return configured if configured.is_absolute() else repo_root() / configured


def load_spec(path: Path) -> dict[str, Any]:
    spec = load_json(path)
    if spec.get("provenance", {}).get("protocol_id") != PROTOCOL_ID:
        raise ValueError("run spec uses the wrong protocol identifier")
    if not spec.get("cells"):
        raise ValueError("run spec has no cells")
    return spec


def plan_axes(target: str, purpose: str) -> dict[str, list[Any]]:
    definition = PRODUCTION[target] if purpose == "production" else PILOT[target]
    return {
        "target_lattice": [target],
        "L": definition["sizes"],
        "field": definition["fields"],
        "chain": [0, 1, 2, 3],
    }


def cmd_plan(args: argparse.Namespace) -> None:
    sampler = args.sampler.resolve()
    if not sampler.is_file():
        raise ValueError(f"sampler does not exist: {sampler}")
    run_dir = args.output.resolve()
    if (run_dir / "run_spec.json").exists():
        raise ValueError("run_spec.json already exists; use it to resume")
    run_dir.mkdir(parents=True, exist_ok=True)
    inputs = run_dir / ".plan-inputs"
    inputs.mkdir(exist_ok=True)
    source = source_provenance()
    if source["source_dirty"]:
        raise ValueError("planning requires a clean scoped source tree")

    axes = plan_axes(args.target, args.purpose)
    settings = {
        "purpose": args.purpose,
        "sampler": portable_path(sampler),
        "sampler_sha256": sha256_file(sampler),
        "boost_lib": portable_path(args.boost_lib) if args.boost_lib else None,
        "mu": 64.0,
        "samples_per_chain": 30000 if args.purpose == "production" else args.samples,
        "thermalization_rule": "500*L^3",
        "between_samples_rule": "8*L^3",
        "observable_order": [
            "percolation_probability", "staggered_imaginary_times", "star_x"
        ],
    }
    provenance = {
        **source,
        "protocol_id": PROTOCOL_ID,
        "paratoric_commit": PARATORIC_COMMIT,
        "paratoric_external_patch_sha256": PARATORIC_PATCH_SHA256,
        "target_lattice": args.target,
        "planned_at": utc_now(),
    }
    for name, payload in (("axes.json", axes), ("settings.json", settings),
                          ("provenance.json", provenance)):
        atomic_json(inputs / name, payload)
    command = [
        sys.executable, str(repo_root() / "scripts" / "parameter_scan.py"), "plan",
        "--axes", str(inputs / "axes.json"), "--run-id", args.run_id,
        "--run-dir", str(run_dir), "--settings", str(inputs / "settings.json"),
        "--provenance", str(inputs / "provenance.json"),
    ]
    subprocess.run(command, cwd=repo_root(), check=True)
    spec_path = run_dir / "run_spec.json"
    spec = load_json(spec_path)
    spec["assemble"] = {
        "manifest_contract": {
            "schema_version": {"type": "equality", "value": MANIFEST_SCHEMA},
            "status": {"type": "equality", "value": "success"},
            "diagnostics.max_star_defect": {"type": "bounds", "max": 1e-12},
            "artifacts.raw.sha256": {"type": "nonempty"},
            "provenance.source_commit": {
                "type": "equality", "value": source["source_commit"],
            },
            "provenance.source_dirty": {"type": "equality", "value": False},
            "provenance.observed_source_commit": {
                "type": "equality", "value": source["source_commit"],
            },
            "provenance.observed_source_dirty": {
                "type": "equality", "value": False,
            },
            "provenance.sampler_sha256": {
                "type": "equality", "value": settings["sampler_sha256"],
            },
            "provenance.paratoric_commit": {
                "type": "equality", "value": PARATORIC_COMMIT,
            },
            "provenance.paratoric_external_patch_sha256": {
                "type": "equality", "value": PARATORIC_PATCH_SHA256,
            },
            "provenance.target_lattice": {
                "type": "equality", "value": args.target,
            },
        },
        "consensus_fields": [
            "schema_version", "provenance.protocol_id",
            "provenance.source_commit", "provenance.source_dirty",
            "provenance.observed_source_commit", "provenance.observed_source_dirty",
            "provenance.sampler_sha256", "provenance.paratoric_commit",
            "provenance.paratoric_external_patch_sha256",
            "provenance.target_lattice",
        ],
        "provenance_fields": [
            "provenance.protocol_id", "provenance.source_commit",
            "provenance.source_dirty", "provenance.paratoric_commit",
            "provenance.paratoric_external_patch_sha256",
            "provenance.target_lattice",
        ],
    }
    for cell in spec["cells"]:
        params = cell["params"]
        params["seed"] = stable_seed(args.run_id, params)
        size = int(params["L"])
        cell["settings"] = {
            "n_thermal": 500 * size**3,
            "updates_between": 8 * size**3,
        }
    seeds = [cell["params"]["seed"] for cell in spec["cells"]]
    if len(seeds) != len(set(seeds)) or 0 in seeds:
        raise RuntimeError("planned seeds are not unique nonzero values")
    atomic_json(spec_path, spec)
    plan = load_json(run_dir / "parameter-scan.plan.json")
    plan["cells"] = spec["cells"]
    atomic_json(run_dir / "parameter-scan.plan.json", plan)
    print(f"planned {len(spec['cells'])} {args.purpose} chains -> {spec_path}")


def validate_rows(
    rows: list[dict[str, str]], params: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    missing = REQUIRED_RAW_COLUMNS - set(rows[0] if rows else ())
    if missing:
        raise ValueError(f"raw output is missing columns: {sorted(missing)}")
    samples = int(settings["samples_per_chain"])
    if len(rows) != samples:
        raise ValueError(f"raw output has {len(rows)} samples, expected {samples}")
    target = str(params["target_lattice"])
    gauge = str(PRODUCTION[target]["gauge_lattice"])
    size = int(params["L"])
    field = float(params["field"])
    beta = size / field
    mu = float(settings["mu"])
    star_defect = 0.0
    tau_names = (
        "package_tau_percolation", "package_tau_sit", "package_tau_star"
    )
    package_tau = {name: float(rows[0][name]) for name in tau_names}
    if any(value < 0.0 for value in package_tau.values()):
        raise ValueError("raw output contains a negative package autocorrelation time")
    for index, row in enumerate(rows):
        expected = {
            "raw_schema": RAW_SCHEMA,
            "target_lattice": target,
            "gauge_lattice": gauge,
            "L": str(size),
            "seed": str(params["seed"]),
            "sample": str(index),
            "n_thermal": str(settings["n_thermal"]),
            "n_samples": str(samples),
            "updates_between": str(settings["updates_between"]),
        }
        for key, value in expected.items():
            if row[key] != value:
                raise ValueError(f"sample {index} has {key}={row[key]!r}, expected {value!r}")
        numeric = [float(row[name]) for name in REQUIRED_RAW_COLUMNS - {
            "raw_schema", "target_lattice", "gauge_lattice"
        }]
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError(f"sample {index} contains a non-finite value")
        if not math.isclose(float(row["beta"]), beta, rel_tol=1e-14):
            raise ValueError(f"sample {index} violates beta*field=L")
        if not math.isclose(float(row["field"]), field, rel_tol=1e-14):
            raise ValueError(f"sample {index} has the wrong target field")
        if not math.isclose(float(row["mu"]), mu, rel_tol=1e-14):
            raise ValueError(f"sample {index} has the wrong charge penalty")
        for name in tau_names:
            value = float(row[name])
            if value < 0.0:
                raise ValueError(
                    f"sample {index} has a negative package autocorrelation time"
                )
            if not math.isclose(value, package_tau[name], rel_tol=1e-14):
                raise ValueError(f"sample {index} has inconsistent {name}")
        if float(row["percolation_probability"]) not in (0.0, 1.0):
            raise ValueError(f"sample {index} has a nonbinary winding projector")
        if abs(float(row["staggered_imaginary_times"])) > 1.0 + 1e-12:
            raise ValueError(f"sample {index} has an invalid SIT value")
        star_defect = max(star_defect, abs(1.0 - float(row["star_x"])))
    if star_defect > 1e-12:
        raise ValueError(f"star-sector gate failed with defect {star_defect}")

    def mean(name: str) -> float:
        return sum(float(row[name]) for row in rows) / len(rows)

    tau = {
        "percolation": package_tau["package_tau_percolation"],
        "sit": package_tau["package_tau_sit"],
        "star": package_tau["package_tau_star"],
    }
    effective = {
        key: samples / (2.0 * max(0.5, value)) for key, value in tau.items()
    }
    if settings.get("purpose") == "production" and (
        effective["percolation"] < 1000.0 or effective["sit"] < 1000.0
    ):
        raise ValueError("production chain has fewer than 1000 effective critical samples")
    return {
        "percolation_mean": mean("percolation_probability"),
        "sit_mean": mean("staggered_imaginary_times"),
        "max_star_defect": star_defect,
        "package_tau_int": tau,
        "package_effective_samples": effective,
        "charge_pair_acceptance_bound": math.exp(-beta * (4.0 * float(settings["mu"]) - 2.0)),
    }


def select_cell(spec: dict[str, Any], selector: str) -> dict[str, Any]:
    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(spec["cells"]):
            return spec["cells"][index]
    matches = [cell for cell in spec["cells"] if cell["cell_id"] == selector]
    if len(matches) != 1:
        raise ValueError(f"unknown cell selector {selector!r}")
    return matches[0]


def run_cell(spec_path: Path, selector: str, retry_failed: bool) -> None:
    spec = load_spec(spec_path)
    cell = select_cell(spec, selector)
    cell_id = cell["cell_id"]
    run_dir = resolve_run_dir(spec, spec_path)
    cell_dir = run_dir / "cells" / cell_id
    cell_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cell_dir / "manifest.json"
    if manifest_path.exists() and not retry_failed:
        manifest = load_json(manifest_path)
        if manifest.get("status") == "success":
            validate_manifest(spec, cell, run_dir)
            print(f"{cell_id}: already successful")
            return
    settings = {**spec["settings"], **cell.get("settings", {})}
    sampler = resolve_setting_path(settings["sampler"])
    if sha256_file(sampler) != settings["sampler_sha256"]:
        raise ValueError("sampler hash differs from the planned executable")
    source = source_provenance()
    validate_source_provenance(spec.get("provenance", {}), source)
    params = cell["params"]
    raw_path = cell_dir / "raw.csv"
    started_at, start_clock = utc_now(), time.monotonic()
    command = [
        str(sampler), str(params["target_lattice"]), str(params["L"]),
        format(float(params["field"]), ".17g"), format(float(settings["mu"]), ".17g"),
        str(params["seed"]), str(settings["n_thermal"]),
        str(settings["samples_per_chain"]), str(settings["updates_between"]),
    ]
    environment = os.environ.copy()
    if settings.get("boost_lib"):
        previous = environment.get("LD_LIBRARY_PATH", "")
        boost_lib = str(resolve_setting_path(settings["boost_lib"]))
        environment["LD_LIBRARY_PATH"] = (
            boost_lib if not previous else f"{boost_lib}:{previous}"
        )
    base = {
        "schema_version": MANIFEST_SCHEMA,
        "cell_id": cell_id,
        "params": params,
        "settings": settings,
        "provenance": {
            **spec["provenance"],
            "observed_source_commit": source["source_commit"],
            "observed_source_dirty": source["source_dirty"],
            "sampler_sha256": sha256_file(sampler),
            "host": socket.gethostname(),
            "platform": platform.platform(),
        },
        "started_at": started_at,
    }
    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file, \
                tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
            process = subprocess.Popen(
                command, cwd=repo_root(), env=environment, text=True,
                stdout=stdout_file, stderr=stderr_file,
            )
            while True:
                try:
                    process.wait(timeout=HEARTBEAT_SECONDS)
                    break
                except subprocess.TimeoutExpired:
                    print(
                        f"{cell_id}: running wall={time.monotonic() - start_clock:.1f}s",
                        flush=True,
                    )
            stdout_file.seek(0)
            stderr_file.seek(0)
            completed_stdout = stdout_file.read()
            completed_stderr = stderr_file.read()
        if process.returncode != 0:
            detail = completed_stderr.strip() or completed_stdout.strip()
            raise RuntimeError(
                f"sampler exited {process.returncode}: {detail or 'no diagnostic output'}"
            )
        lines = completed_stdout.splitlines()
        header_index = next(
            index for index, line in enumerate(lines) if line.startswith("raw_schema,")
        )
        warnings = [line for line in lines[:header_index] if line.strip()]
        warnings.extend(line for line in completed_stderr.splitlines() if line.strip())
        if warnings:
            raise ValueError(f"ParaToric warning gate failed: {warnings}")
        rows = list(csv.DictReader(lines[header_index:]))
        diagnostics = validate_rows(rows, params, settings)
        with raw_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        raw_hash = sha256_file(raw_path)
        total_updates = int(settings["n_thermal"]) + int(
            settings["samples_per_chain"]
        ) * int(settings["updates_between"])
        manifest = {
            **base,
            "status": "success",
            "completed_at": utc_now(),
            "wall_seconds": time.monotonic() - start_clock,
            "total_updates": total_updates,
            "diagnostics": diagnostics,
            "results": {
                "percolation_mean": diagnostics["percolation_mean"],
                "sit_mean": diagnostics["sit_mean"],
            },
            "artifacts": {"raw": {
                "path": raw_path.name, "sha256": raw_hash,
                "bytes": raw_path.stat().st_size,
            }},
        }
        atomic_json(manifest_path, manifest)
        print(f"{cell_id}: success wall={manifest['wall_seconds']:.3f}s")
    except BaseException as error:
        if raw_path.exists():
            raw_path.unlink()
        atomic_json(manifest_path, {
            **base, "status": "failed", "completed_at": utc_now(),
            "wall_seconds": time.monotonic() - start_clock,
            "error": {"type": type(error).__name__, "message": str(error)},
        })
        raise


def validate_manifest(
    spec: dict[str, Any], cell: dict[str, Any], run_dir: Path
) -> tuple[dict[str, Any], Path]:
    manifest_path = run_dir / "cells" / cell["cell_id"] / "manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("status") != "success":
        raise ValueError(f"{cell['cell_id']}: manifest is not a successful critical cell")
    if manifest.get("params") != cell.get("params"):
        raise ValueError(f"{cell['cell_id']}: manifest params differ from the plan")
    settings = {**spec["settings"], **cell.get("settings", {})}
    if manifest.get("settings") != settings:
        raise ValueError(f"{cell['cell_id']}: manifest settings differ from the plan")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError(f"{cell['cell_id']}: manifest provenance is missing")
    for key, expected in spec.get("provenance", {}).items():
        if provenance.get(key) != expected:
            raise ValueError(
                f"{cell['cell_id']}: manifest provenance {key} differs from the plan"
            )
    planned_provenance = spec["provenance"]
    if (provenance.get("observed_source_commit")
            != planned_provenance.get("source_commit")
            or provenance.get("observed_source_dirty")
            is not planned_provenance.get("source_dirty")):
        raise ValueError(f"{cell['cell_id']}: observed source provenance is invalid")
    if provenance.get("sampler_sha256") != settings.get("sampler_sha256"):
        raise ValueError(f"{cell['cell_id']}: manifest sampler hash differs from the plan")
    artifact = manifest.get("artifacts", {}).get("raw", {})
    artifact_path = artifact.get("path")
    if (not isinstance(artifact_path, str) or not artifact_path
            or Path(artifact_path).is_absolute()
            or Path(artifact_path).name != artifact_path):
        raise ValueError(f"{cell['cell_id']}: raw artifact path is invalid")
    raw = manifest_path.parent / artifact_path
    if raw.resolve().parent != manifest_path.parent.resolve() or not raw.is_file():
        raise ValueError(f"{cell['cell_id']}: raw artifact path is invalid")
    if artifact.get("bytes") != raw.stat().st_size:
        raise ValueError(f"{cell['cell_id']}: raw artifact size mismatch")
    if artifact.get("sha256") != sha256_file(raw):
        raise ValueError(f"{cell['cell_id']}: raw hash mismatch")
    with raw.open(encoding="utf-8", newline="") as handle:
        diagnostics = validate_rows(
            list(csv.DictReader(handle)), cell["params"], settings
        )
    if manifest.get("diagnostics") != diagnostics:
        raise ValueError(f"{cell['cell_id']}: manifest diagnostics differ from raw data")
    expected_results = {
        "percolation_mean": diagnostics["percolation_mean"],
        "sit_mean": diagnostics["sit_mean"],
    }
    if manifest.get("results") != expected_results:
        raise ValueError(f"{cell['cell_id']}: manifest results differ from raw data")
    return manifest, raw


def cmd_collect(args: argparse.Namespace) -> None:
    spec_path = args.run_spec.resolve()
    spec = load_spec(spec_path)
    run_dir = resolve_run_dir(spec, spec_path)
    valid, failures = [], []
    for cell in spec["cells"]:
        try:
            valid.append((cell, *validate_manifest(spec, cell, run_dir)))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append(str(error))
    if failures and not args.allow_incomplete:
        raise ValueError("collection refused:\n" + "\n".join(failures))
    if not valid:
        raise ValueError("collection has no valid cells")
    output = run_dir / f"{spec['run_id']}_raw.csv"
    with output.open("w", encoding="utf-8", newline="") as destination:
        writer = None
        for cell, _, raw in valid:
            with raw.open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
            if writer is None:
                writer = csv.DictWriter(
                    destination, fieldnames=["cell_id", "chain", *list(rows[0])]
                )
                writer.writeheader()
            for row in rows:
                writer.writerow({"cell_id": cell["cell_id"], "chain": cell["params"]["chain"], **row})
    report = {
        "schema_version": "challenge148-paratoric-critical-collection-v1",
        "run_id": spec["run_id"], "completed_at": utc_now(),
        "planned_cells": len(spec["cells"]), "successful_cells": len(valid),
        "invalid_or_missing_cells": failures,
        "merged_raw": {"path": output.name, "sha256": sha256_file(output),
                       "bytes": output.stat().st_size},
    }
    atomic_json(run_dir / "collection.json", report)
    generic = [
        sys.executable, str(repo_root() / "scripts" / "parameter_scan.py"), "collect",
        "--run-spec", str(spec_path), "--success-field", "status",
        "--success-value", "success", "--value-field", "results.percolation_mean",
        "--value-field", "results.sit_mean",
    ]
    subprocess.run(generic, cwd=repo_root(), check=True)
    print(f"merged {len(valid)}/{len(spec['cells'])} cells -> {output}")


def cmd_run_local(args: argparse.Namespace) -> None:
    spec_path = args.run_spec.resolve()
    spec = load_spec(spec_path)
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(run_cell, spec_path, cell["cell_id"], args.retry_failed):
            cell["cell_id"] for cell in spec["cells"]
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as error:
                failures.append(f"{futures[future]}: {error}")
    if failures:
        raise RuntimeError("local run failed:\n" + "\n".join(sorted(failures)))
    if args.collect:
        cmd_collect(argparse.Namespace(run_spec=spec_path, allow_incomplete=False))


def cost_projection(manifests: list[dict[str, Any]], target: str, workers: int) -> dict[str, Any]:
    grouped: dict[int, list[float]] = {}
    for manifest in manifests:
        size = int(manifest["params"]["L"])
        grouped.setdefault(size, []).append(
            float(manifest["wall_seconds"]) / int(manifest["total_updates"])
        )
    if len(grouped) < 2:
        raise ValueError("cost projection requires at least two pilot sizes")
    sizes = sorted(grouped)
    rates = [median(grouped[size]) for size in sizes]
    log_sizes = [math.log(size) for size in sizes]
    log_rates = [math.log(rate) for rate in rates]
    x_mean, y_mean = sum(log_sizes) / len(sizes), sum(log_rates) / len(rates)
    denominator = sum((value - x_mean) ** 2 for value in log_sizes)
    exponent = sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(log_sizes, log_rates)
    ) / denominator
    coefficient = math.exp(y_mean - exponent * x_mean)
    definition = PRODUCTION[target]
    field_count = len(definition["fields"])
    projected = []
    aggregate = 0.0
    for size in definition["sizes"]:
        updates = 500 * size**3 + 30000 * 8 * size**3
        chain_seconds = coefficient * size**exponent * updates
        size_seconds = chain_seconds * 4 * field_count
        projected.append({
            "L": size, "updates_per_chain": updates,
            "seconds_per_chain": chain_seconds, "aggregate_seconds": size_seconds,
        })
        aggregate += size_seconds
    return {
        "target_lattice": target,
        "pilot_seconds_per_update": [
            {"L": size, "median": rate} for size, rate in zip(sizes, rates)
        ],
        "seconds_per_update_model": {"coefficient": coefficient, "L_exponent": exponent},
        "production_field_count": field_count, "production_chains_per_point": 4,
        "production_projection": projected, "aggregate_cpu_seconds": aggregate,
        "ideal_workers": workers, "ideal_wall_seconds": aggregate / workers,
        "caveat": (
            "Two-size cost-only extrapolation; excludes queueing, I/O, load variation, "
            "and any retry required by sampling or fit gates."
        ),
    }


def cmd_cost(args: argparse.Namespace) -> None:
    spec_path = args.run_spec.resolve()
    spec = load_spec(spec_path)
    if spec["settings"]["purpose"] != "pilot":
        raise ValueError("cost projection must consume a cost-only pilot")
    run_dir = resolve_run_dir(spec, spec_path)
    manifests = [validate_manifest(spec, cell, run_dir)[0] for cell in spec["cells"]]
    target = spec["provenance"]["target_lattice"]
    projection = cost_projection(manifests, target, args.workers)
    projection["protocol_id"] = PROTOCOL_ID
    projection["run_id"] = spec["run_id"]
    projection["created_at"] = utc_now()
    output = args.output.resolve() if args.output else run_dir / "cost-model.json"
    atomic_json(output, projection)
    print(f"cost projection -> {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--target", choices=sorted(PRODUCTION), required=True)
    plan.add_argument("--purpose", choices=("pilot", "production"), required=True)
    plan.add_argument("--sampler", type=Path, required=True)
    plan.add_argument("--boost-lib", type=Path)
    plan.add_argument("--samples", type=int, default=200)
    plan.set_defaults(function=cmd_plan)

    run_cell_parser = subparsers.add_parser("run-cell")
    run_cell_parser.add_argument("--run-spec", type=Path, required=True)
    run_cell_parser.add_argument("--cell", required=True)
    run_cell_parser.add_argument("--retry-failed", action="store_true")
    run_cell_parser.set_defaults(
        function=lambda args: run_cell(args.run_spec.resolve(), args.cell, args.retry_failed)
    )

    local = subparsers.add_parser("run-local")
    local.add_argument("--run-spec", type=Path, required=True)
    local.add_argument("--workers", type=int, default=1)
    local.add_argument("--retry-failed", action="store_true")
    local.add_argument("--collect", action="store_true")
    local.set_defaults(function=cmd_run_local)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--run-spec", type=Path, required=True)
    collect.add_argument("--allow-incomplete", action="store_true")
    collect.set_defaults(function=cmd_collect)

    cost = subparsers.add_parser("cost")
    cost.add_argument("--run-spec", type=Path, required=True)
    cost.add_argument("--workers", type=int, default=16)
    cost.add_argument("--output", type=Path)
    cost.set_defaults(function=cmd_cost)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if getattr(args, "samples", 2) < 2:
        raise ValueError("pilot sample count must be at least two")
    args.function(args)


if __name__ == "__main__":
    main()
