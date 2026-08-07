#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SOLUTION_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = SOLUTION_DIR / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from challenge148.acceptance import run_acceptance  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Challenge 148 ED-QMC_SSE-QMC_LTFIM acceptance gate."
    )
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    arguments = parser.parse_args()

    os.environ["PATH"] = f"{Path.home() / '.cargo' / 'bin'}:{os.environ.get('PATH', '')}"
    request_path = arguments.request.resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    print(f"acceptance request: {request_path}", flush=True)
    print(f"acceptance mode: {request.get('mode', '<invalid>')}", flush=True)
    result = run_acceptance(request, arguments.output_root.resolve())
    summary = json.loads((result / "summary.json").read_text(encoding="utf-8"))
    print(f"acceptance evidence: {result}", flush=True)
    print(
        f"acceptance passed={summary['passed']} "
        f"scientific_acceptance={summary['scientific_acceptance']}",
        flush=True,
    )
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
