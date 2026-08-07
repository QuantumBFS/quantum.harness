"""Fresh-process worker for one measured VQE training request."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from vqetape.training import train_vqe
from vqetape.training_spec import VQETrainingRequest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    request = VQETrainingRequest.from_dict(
        json.loads(args.request.read_text(encoding="utf-8"))
    )
    result = train_vqe(request)
    payload = result.to_dict()
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
