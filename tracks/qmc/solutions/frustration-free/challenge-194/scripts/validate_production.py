#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from long_range_percolation.validation import (
    ValidationProtocol,
    run_production_validation,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed Challenge 194 production correctness gate."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--protocol",
        choices=("production-v1",),
        required=True,
    )
    parser.add_argument("--jobs", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.jobs < 1:
        _parser().error("--jobs must be a positive integer")
    protocol = ValidationProtocol.production_v1()
    protocol = ValidationProtocol(
        lengths=protocol.lengths,
        sigmas=protocol.sigmas,
        kappas=protocol.kappas,
        samples_by_length=protocol.samples_by_length,
        master_seeds=protocol.master_seeds,
        familywise_alpha=protocol.familywise_alpha,
        permutation_replicates=protocol.permutation_replicates,
        multinomial_replicates=protocol.multinomial_replicates,
        jobs=arguments.jobs,
        name=protocol.name,
    )
    protocol.require_production()
    try:
        report = run_production_validation(protocol, arguments.output)
    except Exception as error:
        print(
            f"validation infrastructure failure: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        f"validation passed={report['passed']} "
        f"families={report['family_count']} "
        f"minimum_margin={report['minimum_margin']} "
        f"output={arguments.output}",
        flush=True,
    )
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
