"""Command-line interface for generation, verification, and reporting."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

from .audit import audit_directory
from .certify import make_level_certificate
from .lti import solve_lti
from .schema import LevelCertificate
from .upper import optimize_block_state
from .verify import verify_level


def _csv(value: str, cast):
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def generate(args: argparse.Namespace) -> int:
    output = Path(args.output)
    deltas = _csv(args.delta, str)
    levels = _csv(args.lti_levels, int)
    blocks = _csv(args.block_sizes, int)
    if len(blocks) == 1:
        blocks *= len(levels)
    if len(levels) != len(blocks):
        raise ValueError("block-sizes must have one value or match lti-levels")
    for delta_text in deltas:
        delta = float(delta_text)
        for level, block in zip(levels, blocks, strict=True):
            raw_level = min(level, args.raw_lti_cap)
            lower = solve_lti(delta, raw_level, args.solver)
            upper = optimize_block_state(delta, block)
            certificate = make_level_certificate(
                delta_text, lower, upper, proof_level=level
            )
            destination = (
                output
                / f"delta_{delta_text.replace('-', 'm').replace('.', 'p')}"
                / f"level_{level}_block_{block}.json"
            )
            certificate.write(destination)
            print(f"WROTE {destination}")
    return 0


def _paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.glob("**/*.json"))


def verify(args: argparse.Namespace) -> int:
    failures = 0
    paths = _paths(Path(args.path))
    if not paths:
        print("FAIL no certificate files found")
        return 2
    for path in paths:
        report = verify_level(path)
        if report.ok:
            print(f"PASS {path}")
        else:
            failures += 1
            print(f"FAIL {path}: {'; '.join(report.errors)}")
    return 1 if failures else 0


def report(args: argparse.Namespace) -> int:
    paths = _paths(Path(args.path))
    print("delta level block certified_lower bethe_lower bethe_upper certified_upper width")
    for path in paths:
        certificate = LevelCertificate.read(path)
        width = certificate.certified_upper - certificate.certified_lower
        print(
            certificate.delta,
            certificate.level,
            certificate.block_size,
            certificate.certified_lower,
            certificate.bethe.lower,
            certificate.bethe.upper,
            certificate.certified_upper,
            width,
        )
    return 0


def audit(args: argparse.Namespace) -> int:
    result = audit_directory(Path(args.path))
    print(
        "delta level block certified_lower bethe_lower bethe_upper "
        "certified_upper lower_error upper_error width"
    )
    for row in result.rows:
        print(
            row.delta,
            row.level,
            row.block_size,
            row.certified_lower,
            row.bethe_lower,
            row.bethe_upper,
            row.certified_upper,
            row.lower_error,
            row.upper_error,
            row.width,
        )
    print(
        f"MONOTONE lower={result.lower_monotone} "
        f"upper={result.upper_monotone}"
    )
    if args.json_output:
        destination = Path(args.json_output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xxzcert")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--delta", required=True)
    generate_parser.add_argument("--lti-levels", required=True)
    generate_parser.add_argument("--block-sizes", required=True)
    generate_parser.add_argument("--solver", default="CLARABEL")
    generate_parser.add_argument("--raw-lti-cap", type=int, default=5)
    generate_parser.add_argument("--output", required=True)
    generate_parser.set_defaults(func=generate)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("path")
    verify_parser.set_defaults(func=verify)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("path")
    report_parser.set_defaults(func=report)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("path")
    audit_parser.add_argument("--json", dest="json_output")
    audit_parser.set_defaults(func=audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
