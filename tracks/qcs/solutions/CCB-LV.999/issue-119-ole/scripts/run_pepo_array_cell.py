#!/usr/bin/env python3
"""Run one deterministic PEPO cell selected from a harness run specification."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from ole_pepo.records import atomic_write_json


OLE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
DEFAULT_EVOLUTION_CUTOFF = 1.0e-10
DEFAULT_CONTRACTION_CUTOFF = 1.0e-10
RUN_ROOT_PATTERN = re.compile(r"^issue119-pepo-.+$")
CELL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def parse_confirmation_token(output: str) -> str:
    matches = re.findall(r"^confirmation_token=([0-9a-f]{16})$", output, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"expected one confirmation token, found {len(matches)}")
    return matches[0]


def confined_run_root(run_dir: object, workspace_root: Path) -> Path:
    if not isinstance(run_dir, str):
        raise ValueError("run_dir must be a relative string")
    requested = Path(run_dir)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("run_dir must be relative and must not contain '..'")
    if (
        len(requested.parts) != 2
        or requested.parts[0] != "results"
        or RUN_ROOT_PATTERN.fullmatch(requested.parts[1]) is None
    ):
        raise ValueError("run_dir must match results/issue119-pepo-*")
    workspace = workspace_root.resolve()
    declared_results_root = workspace / "results"
    results_root = declared_results_root.resolve()
    if results_root != declared_results_root:
        raise ValueError("run_dir results root must not be a symlink")
    lexical_run_root = workspace / requested
    resolved = lexical_run_root.resolve()
    if resolved != lexical_run_root:
        raise ValueError("run_dir selected root must not redirect through a symlink")
    try:
        resolved.relative_to(results_root)
    except ValueError as error:
        raise ValueError("run_dir must remain under repo-root results/") from error
    if (
        resolved.parent != results_root
        or RUN_ROOT_PATTERN.fullmatch(resolved.name) is None
    ):
        raise ValueError(
            "run_dir resolved root must match results/issue119-pepo-*"
        )
    return resolved


def safe_cell_id(cell_id: object) -> str:
    if not isinstance(cell_id, str) or CELL_ID_PATTERN.fullmatch(cell_id) is None:
        raise ValueError("cell_id must be one safe relative path component")
    return cell_id


def confined_cell_dir(run_root: Path, cell_id: str, workspace_root: Path) -> Path:
    results_root = (workspace_root.resolve() / "results").resolve()
    resolved = (run_root / "cells" / cell_id).resolve()
    try:
        relative_to_run = resolved.relative_to(run_root)
        resolved.relative_to(results_root)
    except ValueError as error:
        raise ValueError(
            "cell path must remain under the selected resolved run root"
        ) from error
    if relative_to_run == Path("."):
        raise ValueError(
            "cell path must remain below the selected resolved run root"
        )
    return resolved


def selected_payload(run_spec: dict, selector: int) -> dict:
    cells = run_spec["cells"]
    if selector < 1 or selector > len(cells):
        raise ValueError(f"selector {selector} is outside 1:{len(cells)}")
    cell = cells[selector - 1]
    settings = {**run_spec.get("settings", {}), **cell.get("settings", {})}
    params = cell["params"]
    confined_run_root(run_spec["run_dir"], WORKSPACE_ROOT)
    cell_id = safe_cell_id(cell["cell_id"])
    return {
        "cell_id": cell_id,
        "params": params,
        "settings": settings,
        "provenance": run_spec.get("provenance", {}),
        "run_dir": run_spec["run_dir"],
    }


def _declared_values(payload: dict) -> dict[str, object]:
    settings = payload["settings"]
    params = payload["params"]
    delta = params.get("delta", settings["delta"])
    return {
        "circuit": str(settings.get("circuit", "baseline")),
        "dop": int(params["dop"]),
        "chi_env": int(params["chi_env"]),
        "delta": float(delta),
        "evolution_cutoff": float(
            settings.get("evolution_cutoff", DEFAULT_EVOLUTION_CUTOFF)
        ),
        "contraction_cutoff": float(
            settings.get("contraction_cutoff", DEFAULT_CONTRACTION_CUTOFF)
        ),
    }


def success_manifest(payload: dict, document: dict, source_result: Path) -> dict:
    if document.get("status") != "success":
        raise ValueError(f"direct PEPO result is not successful: {source_result}")
    expected = _declared_values(payload)
    protocol = document.get("protocol")
    if not isinstance(protocol, dict):
        raise ValueError("direct PEPO result has no protocol")
    for field, expected_value in expected.items():
        actual = protocol.get(field)
        if actual != expected_value:
            raise ValueError(
                f"direct PEPO {field} does not match selected cell: "
                f"expected {expected_value}, got {actual}"
            )

    result = document.get("result")
    diagnostics = document.get("diagnostics")
    if not isinstance(result, dict):
        raise ValueError("direct PEPO result fields are missing")
    if not isinstance(diagnostics, dict):
        raise ValueError("direct PEPO diagnostics are missing")
    for field in (
        "value_real",
        "value_imag",
        "wall_seconds",
        "peak_rss_bytes",
    ):
        if field not in result:
            raise ValueError(f"direct PEPO result is missing {field}")
    for field in (
        "causal_gates",
        "final_support_size",
        "max_realized_bond",
        "max_retained_tail_ratio",
    ):
        if field not in diagnostics:
            raise ValueError(f"direct PEPO diagnostics are missing {field}")

    return {
        "status": "success",
        "cell_id": payload["cell_id"],
        "params": payload["params"],
        "settings": payload["settings"],
        "provenance": payload["provenance"],
        "source_result": str(source_result),
        "direct_provenance": document.get("provenance", {}),
        "result": result,
        "diagnostics": diagnostics,
    }


def run_cell(
    payload: dict,
    *,
    workspace_root: Path,
    python_bin: Path = Path(sys.executable),
    runner: Path | None = None,
) -> Path:
    selected = _declared_values(payload)
    direct_runner = runner or OLE_ROOT / "scripts" / "run_pepo.py"
    run_root = confined_run_root(payload["run_dir"], workspace_root)
    cell_id = safe_cell_id(payload["cell_id"])
    cell_dir = confined_cell_dir(run_root, cell_id, workspace_root)
    source_result = cell_dir / "pepo-result.json"
    oracle_setting = payload["settings"].get("oracle_manifest")
    if oracle_setting is None:
        oracle_run = (
            "issue119-pepo-active-small-oracle"
            if selected["circuit"] == "active"
            else "issue119-pepo-small-oracle"
        )
        oracle_path = workspace_root / "results" / oracle_run / "manifest.json"
    else:
        oracle_path = Path(str(oracle_setting))
        if not oracle_path.is_absolute():
            oracle_path = workspace_root / oracle_path
    command = [
        str(python_bin),
        str(direct_runner),
        "--dop",
        str(selected["dop"]),
        "--chi-env",
        str(selected["chi_env"]),
        "--delta",
        str(selected["delta"]),
        "--evolution-cutoff",
        str(selected["evolution_cutoff"]),
        "--contraction-cutoff",
        str(selected["contraction_cutoff"]),
        "--circuit",
        str(selected["circuit"]),
        "--oracle-manifest",
        str(oracle_path),
        "--output",
        str(source_result),
    ]
    dry_run = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=True,
    )
    print(dry_run.stdout, end="", flush=True)
    token = parse_confirmation_token(dry_run.stdout)
    subprocess.run(
        [*command, "--execute", "--confirm", token],
        check=True,
    )

    document = json.loads(source_result.read_text(encoding="utf-8"))
    manifest = success_manifest(payload, document, source_result)
    manifest_path = cell_dir / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-spec", default=os.environ.get("HARNESS_RUN_SPEC"))
    parser.add_argument(
        "--selector",
        type=int,
        default=os.environ.get("SLURM_ARRAY_TASK_ID"),
    )
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.run_spec:
        parser.error("--run-spec or HARNESS_RUN_SPEC is required")
    if args.selector is None:
        parser.error("--selector or SLURM_ARRAY_TASK_ID is required")

    run_spec_path = Path(args.run_spec).resolve()
    run_spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    try:
        payload = selected_payload(run_spec, args.selector)
    except ValueError as error:
        parser.error(str(error))
    if args.inspect_only:
        print(json.dumps(payload, sort_keys=True))
        return 0

    manifest_path = run_cell(payload, workspace_root=WORKSPACE_ROOT)
    print(f"manifest={manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
