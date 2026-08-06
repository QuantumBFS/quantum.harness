#!/usr/bin/env python3
"""Unified local and cluster entry point for Hubbard-pump ED workflows."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.io_utils import load_yaml, save_chern_grid, save_scan_summary  # noqa: E402
from src.workflows import (  # noqa: E402
    BenchmarkConfig,
    ScanConfig,
    benchmark_config_from_mapping,
    run_benchmark,
    scan_config_from_mapping,
    scan_u,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    benchmark = subparsers.add_parser("benchmark", help="Compute all four observables")
    benchmark.add_argument("--config", type=Path, required=True)
    benchmark.add_argument("--L", type=int)
    benchmark.add_argument("--U", type=float)
    benchmark.add_argument("--period", type=float)
    benchmark.add_argument("--time-steps", type=int)
    benchmark.add_argument("--save", type=Path)

    scan = subparsers.add_parser("scan-u", help="Scan C_MB over interaction values")
    scan.add_argument("--config", type=Path, required=True)
    scan.add_argument("--values", type=float, nargs="+")
    scan.add_argument("--L", type=int)
    scan.add_argument("--grid-sizes", type=int, nargs="+")
    scan.add_argument("--output-dir", type=Path)
    return parser


def _benchmark(args: argparse.Namespace, mapping: dict) -> dict[str, object]:
    config = benchmark_config_from_mapping(mapping)
    model = config.model
    if args.L is not None:
        model = replace(
            model,
            L=args.L,
            N_up=args.L // 2,
            N_down=args.L // 2,
        )
    if args.U is not None:
        model = replace(model, U=args.U)
    config = replace(
        config,
        model=model,
        period=config.period if args.period is None else args.period,
        time_steps=config.time_steps if args.time_steps is None else args.time_steps,
    )
    result = run_benchmark(config)
    if args.save is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def _scan(args: argparse.Namespace, mapping: dict) -> list[dict]:
    config = scan_config_from_mapping(mapping)
    if args.L is not None:
        config = replace(
            config,
            model=replace(
                config.model,
                L=args.L,
                N_up=args.L // 2,
                N_down=args.L // 2,
            ),
        )
    if args.grid_sizes is not None:
        config = ScanConfig(model=config.model, grid_sizes=tuple(args.grid_sizes))
    values = args.values
    if values is None:
        scan_mapping = mapping.get("scan", {})
        values = scan_mapping.get("U_values")
    if not values:
        raise ValueError("scan-u requires U values in YAML or --values")
    records = scan_u(values, config)
    configured_output = Path(mapping.get("output_dir", "results"))
    output_dir = args.output_dir or configured_output
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    for record in records:
        save_chern_grid(record, output_dir / "grid_data")
    save_scan_summary(records, output_dir)
    return [record.as_dict() for record in records]


def main() -> None:
    args = _parser().parse_args()
    mapping = load_yaml(args.config)
    if args.command == "benchmark":
        payload = _benchmark(args, mapping)
    else:
        payload = _scan(args, mapping)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
