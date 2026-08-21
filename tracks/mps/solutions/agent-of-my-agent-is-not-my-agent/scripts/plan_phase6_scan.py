#!/usr/bin/env python3
"""Write the locked Phase 6 production specification without running it."""

import argparse
import json
from pathlib import Path

from lrtfim.phase6_protocol import build_run_spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sigma", type=float, default=1.75)
    parser.add_argument("--fit-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = build_run_spec(
        sigma=args.sigma,
        fit_id=args.fit_id,
        output_dir=args.output.parent,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {len(spec['cells'])} pending cells to {args.output}", flush=True)


if __name__ == "__main__":
    main()
