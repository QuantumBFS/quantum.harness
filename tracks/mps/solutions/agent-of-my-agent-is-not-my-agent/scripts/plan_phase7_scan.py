#!/usr/bin/env python3
"""Plan and audit Phase 7 crossover work without running TeNPy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lrtfim.phase7_protocol import (
    SIGMAS,
    build_broad_spec,
    build_gap_spec,
    decide_refinement,
    estimate_scan_cost,
    finalize_crossing,
)


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
        stream.flush()
    temporary.replace(path)


def load_manifests(root: Path) -> dict[str, dict]:
    manifests = {}
    for path in sorted(root.rglob("summary.json")):
        manifests[str(path)] = json.loads(path.read_text())
    for path in sorted(root.rglob("manifest.json")):
        manifests[str(path)] = json.loads(path.read_text())
    return manifests


def cell_command(cell: dict, fit_path: str, run_dir: str) -> list[str]:
    return [
        "python",
        "-u",
        "scripts/benchmark_phase6_optimizations.py",
        "--fit-summary",
        fit_path,
        "--length",
        str(cell["L"]),
        "--gamma",
        str(cell["Gamma"]),
        "--num-exponentials",
        "24",
        "--alpha",
        "0.5",
        "--r-fit",
        "2048",
        "--chi-schedule",
        "64",
        "--direct-only",
        "--sectors",
        cell["sector"],
        "--output-dir",
        str(Path(run_dir) / "cells" / cell["cell_id"]),
    ]


def command_broad(args: argparse.Namespace) -> None:
    fits = json.loads(args.fit_map.read_text())
    spec = build_broad_spec(fits, args.output.parent)
    for cell in spec["cells"]:
        fit = fits[f"{cell['sigma']:.2f}"]
        cell["command"] = cell_command(
            cell,
            str(fit["path"]),
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(f"planned {len(spec['cells'])} broad cells", flush=True)


def _input_hash(spec: dict, manifests: dict) -> str:
    payload = json.dumps(
        {"spec": spec, "manifests": manifests},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def command_decide(args: argparse.Namespace) -> None:
    spec = json.loads(args.run_spec.read_text())
    manifests = load_manifests(args.manifest_root)
    input_hash = _input_hash(spec, manifests)
    for sigma in SIGMAS:
        decision = decide_refinement(sigma, spec, manifests)
        if decision["status"] == "ready":
            resolved = finalize_crossing(decision, manifests)
            if resolved["status"] != "incomplete":
                decision = resolved
        decision["input_hash"] = input_hash
        destination = args.output_dir / f"sigma-{sigma:.2f}.json"
        if destination.is_file():
            existing = json.loads(destination.read_text())
            if existing.get("input_hash") != input_hash:
                raise ValueError(
                    f"refusing to overwrite changed decision {destination}"
                )
        atomic_json(destination, decision)
        print(f"sigma={sigma:.2f}: {decision['status']}", flush=True)


def command_gaps(args: argparse.Namespace) -> None:
    decisions = [
        json.loads(path.read_text())
        for path in sorted(args.decisions_dir.glob("sigma-*.json"))
    ]
    spec = build_gap_spec(decisions, args.output.parent)
    for cell in spec["cells"]:
        fit_path = args.fit_root / f"sigma-{cell['sigma']:.2f}.json"
        cell["command"] = cell_command(
            cell,
            str(fit_path),
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(f"planned {len(spec['cells'])} gap cells", flush=True)


def command_estimate(args: argparse.Namespace) -> None:
    spec = json.loads(args.run_spec.read_text())
    records = json.loads(args.timing_records.read_text())
    estimate = estimate_scan_cost(records, spec)
    atomic_json(args.output, estimate)
    print(
        "estimated "
        f"{estimate['combined']['central_wall_seconds'] / 3600:.2f} "
        "central wall-hours",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    broad = subparsers.add_parser("broad")
    broad.add_argument("--fit-map", type=Path, required=True)
    broad.add_argument("--output", type=Path, required=True)
    broad.set_defaults(handler=command_broad)

    decide = subparsers.add_parser("decide")
    decide.add_argument("--run-spec", type=Path, required=True)
    decide.add_argument("--manifest-root", type=Path, required=True)
    decide.add_argument("--output-dir", type=Path, required=True)
    decide.set_defaults(handler=command_decide)

    gaps = subparsers.add_parser("gaps")
    gaps.add_argument("--decisions-dir", type=Path, required=True)
    gaps.add_argument("--fit-root", type=Path, required=True)
    gaps.add_argument("--output", type=Path, required=True)
    gaps.set_defaults(handler=command_gaps)

    estimate = subparsers.add_parser("estimate")
    estimate.add_argument("--run-spec", type=Path, required=True)
    estimate.add_argument("--timing-records", type=Path, required=True)
    estimate.add_argument("--output", type=Path, required=True)
    estimate.set_defaults(handler=command_estimate)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
