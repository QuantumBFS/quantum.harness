#!/usr/bin/env python3
"""Create the evidence-bound, one-time Production-B unblinding record."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.production_b_gate import (
    ProductionBGatePaths,
    build_unblinding_record,
    remote_gate_paths,
)

DEFAULT_TEAM_ROOT = Path(
    "/work/share/giggleliu/cfys01/kharkov_burgers_20260729"
)


def create_unblinding_record(
    paths: ProductionBGatePaths,
    *,
    confirm: bool,
    command: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Validate all evidence, then exclusively create the one-time record."""

    if not confirm:
        raise ValueError(
            "Refusing to unblind without --confirm-unblind. This command "
            "is intentionally one-time."
        )
    destination = paths.unblinding_record
    if destination.exists():
        raise FileExistsError(
            f"Unblinding record already exists: {destination}"
        )
    timestamp = now or datetime.now(timezone.utc).isoformat()
    record = build_unblinding_record(
        paths,
        command=command,
        now=timestamp,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation closes the race between the read-only gate and write.
    with destination.open("x") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return record


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--team-root",
        type=Path,
        default=DEFAULT_TEAM_ROOT,
    )
    parser.add_argument(
        "--confirm-unblind",
        action="store_true",
        help=(
            "Required human acknowledgement that the eligible registered "
            "Production-B forecast opens exactly once."
        ),
    )
    args = parser.parse_args(argv)
    command = (
        "scripts/unblind_research_test.py "
        f"--team-root {args.team_root} --confirm-unblind"
    )
    try:
        record = create_unblinding_record(
            remote_gate_paths(args.team_root),
            confirm=args.confirm_unblind,
            command=command,
        )
    except (OSError, TypeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": str(error),
                    "unblinding_performed": False,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from error
    print(
        json.dumps(
            {
                "status": record["status"],
                "protocol_version": record["protocol_version"],
                "validation_status": record["validation_status"],
                "record": str(
                    remote_gate_paths(args.team_root).unblinding_record
                ),
                "unblinding_performed": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
