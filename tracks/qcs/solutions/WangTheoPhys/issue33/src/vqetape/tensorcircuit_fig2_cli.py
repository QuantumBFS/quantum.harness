"""CLI for the TensorCircuit-NG paper Fig. 2 protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vqetape.tensorcircuit_baseline_cli import _write_json_atomic
from vqetape.tensorcircuit_fig2 import (
    Fig2Spec,
    build_fig2_protocol,
    protocol_sha256,
    run_fig2_path,
    search_fig2_path,
    validate_path_payload,
)


def _add_protocol_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--nqubits", type=int, default=32)
    parser.add_argument("--depth", type=int, default=16)
    parser.add_argument("--coupling", type=float, default=1.0)
    parser.add_argument("--field", type=float, default=1.0)
    parser.add_argument(
        "--dtype",
        choices=("complex64", "complex128"),
        default="complex64",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--parameter-scale", type=float, default=0.1)
    parser.add_argument("--max-repeats", type=int, default=640)
    parser.add_argument("--target-size-log2", type=int, default=29)
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help=(
            "path-search workers; 1 avoids forking after JAX starts "
            "threads"
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Declare, search, and execute the TensorCircuit-NG paper "
            "Fig. 2 SU(4) ladder protocol."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    manifest = commands.add_parser(
        "manifest",
        help="write the protocol without importing optional dependencies",
    )
    _add_protocol_arguments(manifest)
    manifest.add_argument("--output", required=True, type=Path)

    path = commands.add_parser(
        "path",
        help="search and write a safe JSON contraction path",
    )
    _add_protocol_arguments(path)
    path.add_argument("--output", required=True, type=Path)

    run = commands.add_parser(
        "run",
        help="execute value-and-gradient calls from a JSON path",
    )
    run.add_argument("--path", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--warm-repeats", type=int, default=3)
    run.add_argument("--verify-direct", action="store_true")
    return parser


def _spec(args: argparse.Namespace) -> Fig2Spec:
    return Fig2Spec(
        nqubits=args.nqubits,
        depth=args.depth,
        coupling=args.coupling,
        field=args.field,
        dtype=args.dtype,
        seed=args.seed,
        parameter_scale=args.parameter_scale,
    )


def _target_size(args: argparse.Namespace) -> int:
    if not 1 <= args.target_size_log2 <= 60:
        raise ValueError("target_size_log2 must be between 1 and 60")
    return 2**args.target_size_log2


def _read_path(path: Path) -> dict:
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("path artifact exceeds the 100 MiB safety limit")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("path artifact must be a JSON object")
    validate_path_payload(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "manifest":
        spec = _spec(args)
        protocol = build_fig2_protocol(
            spec,
            max_repeats=args.max_repeats,
            target_size=_target_size(args),
            parallel=args.parallel,
        )
        payload = {
            "schema_version": 1,
            "artifact_type": "tensorcircuit_ng_fig2_manifest",
            "protocol": protocol,
            "protocol_sha256": protocol_sha256(protocol),
        }
        _write_json_atomic(args.output, payload)
        print(
            f"manifest={args.output} "
            f"parameters={spec.parameter_count}",
            flush=True,
        )
        return 0

    if args.command == "path":
        payload = search_fig2_path(
            _spec(args),
            max_repeats=args.max_repeats,
            target_size=_target_size(args),
            parallel=args.parallel,
        )
        _write_json_atomic(args.output, payload)
        stats = payload["path_search"]["tree_stats"]
        print(
            f"path={args.output} slices={stats['slices']} "
            f"search={payload['path_search']['seconds']:.6f}s",
            flush=True,
        )
        return 0

    payload = _read_path(args.path)
    report = run_fig2_path(
        payload,
        warm_repeats=args.warm_repeats,
        verify_direct=args.verify_direct,
    )
    _write_json_atomic(args.output, report)
    correctness = report["correctness"]
    label = (
        "not-checked"
        if correctness is None
        else "pass" if correctness["tolerance_passed"] else "fail"
    )
    print(
        f"run={args.output} "
        f"warm={report['timings']['warm_value_and_grad_seconds_median']:.6f}s "
        f"correctness={label}",
        flush=True,
    )
    if correctness is not None and not correctness["tolerance_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
