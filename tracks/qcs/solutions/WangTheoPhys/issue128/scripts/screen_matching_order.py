#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from trottercert.matching_screen import screen_matching_order


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank the 24 matching-color orders")
    parser.add_argument("--permutation-index", type=int, required=True)
    parser.add_argument("--order", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    running = {
        "schema_version": 1,
        "kind": "issue128_matching_order_screen_manifest",
        "status": "running",
        "trusted": False,
        "purpose": "discovery-ranking",
        "permutation_index": args.permutation_index,
        "order": args.order,
        "source_commit": os.environ.get("ISSUE128_SOURCE_COMMIT", "unrecorded"),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _write(args.manifest, running)
    try:
        payload = screen_matching_order(args.permutation_index, args.order)
        _write(args.output, payload)
        _write(
            args.manifest,
            {
                **running,
                "status": "complete",
                "wall_seconds": time.perf_counter() - started,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except BaseException as error:
        _write(
            args.manifest,
            {
                **running,
                "status": "failed",
                "wall_seconds": time.perf_counter() - started,
                "error_type": type(error).__name__,
                "error": str(error),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise


if __name__ == "__main__":
    main()
