#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from closed_loop import build_submission, summarize_submission


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate YueYuan attempt-002 submission.")
    parser.add_argument("--out", type=Path, default=Path("submission.json"))
    args = parser.parse_args()

    payload = build_submission()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summarize_submission(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
