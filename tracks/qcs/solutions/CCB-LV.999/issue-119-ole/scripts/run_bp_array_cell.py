#!/usr/bin/env python3
"""Run one OLE seed/χ cell selected from a harness run specification."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import tomllib
from pathlib import Path


def parse_confirmation_token(output: str) -> str:
    matches = re.findall(r"^confirmation_token=([0-9a-f]{16})$", output, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"expected one confirmation token, found {len(matches)}")
    return matches[0]


def parse_result_path(output: str, ole_root: Path) -> Path:
    matches = re.findall(r"^result_path=(.+)$", output, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"expected one result path, found {len(matches)}")
    path = Path(matches[0]).resolve()
    runs_root = (ole_root / "runs").resolve()
    if not path.is_relative_to(runs_root):
        raise ValueError(f"runner result path is outside {runs_root}: {path}")
    return path


def result_path(root: Path, params: dict) -> Path:
    delta_directory = {"0.15": "delta-0p15", "0": "delta-0"}[str(params["delta"])]
    return (
        root
        / "runs"
        / "baseline-49x648"
        / delta_directory
        / f"chi-{int(params['chi'])}"
        / f"seed-{int(params['seed']):04d}.toml"
    )


def success_manifest(payload: dict, document: dict, source_result: Path) -> dict:
    run = document["run"]
    result = document["result"]
    if run.get("status") != "complete":
        raise ValueError(f"result is not complete: {source_result}")
    if int(result["seed_id"]) != int(payload["params"]["seed"]):
        raise ValueError("result seed does not match the declared cell")
    if int(result["maxdim"]) != int(payload["params"]["chi"]):
        raise ValueError("result chi does not match the declared cell")
    layers = result["layers"]
    layer_wall_seconds = [
        float(layer["wall_seconds"])
        for layer in layers
        if "wall_seconds" in layer
    ]
    virtual_bond_dimensions = [
        int(layer["max_bond_dimension"])
        for layer in layers
        if "max_bond_dimension" in layer
    ]
    norm_defects = [
        float(layer["norm_defect"])
        for layer in layers
        if layer.get("norm_defect_available", False)
        and math.isfinite(float(layer["norm_defect"]))
    ]
    return {
        "status": "success",
        "cell_id": payload["cell_id"],
        "params": payload["params"],
        "settings": payload["settings"],
        "provenance": payload["provenance"],
        "source_result": str(source_result),
        "result": {
            "sample_value": result["sample_value"],
            "wall_seconds": result["wall_seconds"],
            "peak_rss_bytes": result["peak_rss_bytes"],
            "max_truncation_error": result["max_truncation_error"],
            "sum_truncation_error": result["sum_truncation_error"],
            "max_bp_residual": max(layer["bp_residual"] for layer in layers),
            "bp_nonconverged_layers": sum(
                not layer["bp_converged"] for layer in layers
            ),
            "max_layer_wall_seconds": (
                max(layer_wall_seconds) if layer_wall_seconds else None
            ),
            "mean_layer_wall_seconds": (
                sum(layer_wall_seconds) / len(layer_wall_seconds)
                if layer_wall_seconds
                else None
            ),
            "max_virtual_bond_dimension": (
                max(virtual_bond_dimensions) if virtual_bond_dimensions else None
            ),
            "norm_defect_available_layers": len(norm_defects),
            "max_norm_defect": max(norm_defects) if norm_defects else None,
        },
    }


def run_cell(
    payload: dict,
    ole_root: Path,
    workspace_root: Path,
    julia_bin: Path,
) -> Path:
    params = payload["params"]
    runner = ole_root / "scripts" / "run_bp.jl"
    config_path = (
        ole_root
        / payload.get("settings", {}).get(
            "config_path",
            "configs/baseline-49x648.toml",
        )
    ).resolve()
    configs_root = (ole_root / "configs").resolve()
    if not config_path.is_relative_to(configs_root) or not config_path.is_file():
        raise ValueError(f"invalid BP-TN config path: {config_path}")
    command = [
        str(julia_bin),
        f"--project={ole_root}",
        str(runner),
        "--config",
        str(config_path),
        "--seed",
        str(params["seed"]),
        "--chi",
        str(params["chi"]),
        "--delta",
        str(params["delta"]),
    ]
    dry_run = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=True,
    )
    print(dry_run.stdout, end="", flush=True)
    token = parse_confirmation_token(dry_run.stdout)
    source_result = parse_result_path(dry_run.stdout, ole_root)
    subprocess.run(
        [*command, "--execute", "--confirm", token],
        check=True,
    )

    with source_result.open("rb") as handle:
        document = tomllib.load(handle)
    manifest = success_manifest(payload, document, source_result)
    manifest_path = (
        workspace_root
        / payload["run_dir"]
        / "cells"
        / payload["cell_id"]
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(manifest_path)
    return manifest_path


def selected_payload(run_spec: dict, selector: int) -> dict:
    cells = run_spec["cells"]
    if selector < 1 or selector > len(cells):
        raise ValueError(f"selector {selector} is outside 1:{len(cells)}")
    cell = cells[selector - 1]
    return {
        "cell_id": cell["cell_id"],
        "params": cell["params"],
        "settings": run_spec.get("settings", {}),
        "provenance": run_spec.get("provenance", {}),
        "run_dir": run_spec["run_dir"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", default=os.environ.get("HARNESS_RUN_SPEC"))
    parser.add_argument(
        "--selector",
        type=int,
        default=os.environ.get("SLURM_ARRAY_TASK_ID"),
    )
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    if not args.run_spec:
        parser.error("--run-spec or HARNESS_RUN_SPEC is required")
    if args.selector is None:
        parser.error("--selector or SLURM_ARRAY_TASK_ID is required")

    run_spec_path = Path(args.run_spec).resolve()
    run_spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    payload = selected_payload(run_spec, args.selector)
    if args.inspect_only:
        print(json.dumps(payload, sort_keys=True))
        return
    ole_root = Path(__file__).resolve().parents[1]
    julia_bin = Path(
        os.environ.get(
            "HARNESS_JULIA_BIN",
            str(Path.home() / ".juliaup" / "bin" / "julia"),
        )
    )
    manifest_path = run_cell(payload, ole_root, Path.cwd(), julia_bin)
    print(f"manifest={manifest_path}", flush=True)


if __name__ == "__main__":
    main()
