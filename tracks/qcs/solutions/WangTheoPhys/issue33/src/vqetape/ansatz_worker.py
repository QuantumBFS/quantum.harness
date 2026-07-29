"""Fresh-process worker for one ansatz-growth experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from vqetape.ansatz_training import (
    AnsatzGrowthRequest,
    run_ansatz_growth,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    request = AnsatzGrowthRequest.from_dict(
        json.loads(args.request.read_text(encoding="utf-8"))
    )
    payload = run_ansatz_growth(request).to_dict()
    payload["worker_pid"] = os.getpid()
    payload["parent_pid"] = os.getppid()
    temporary = args.output.with_suffix(
        args.output.suffix + ".tmp"
    )
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
