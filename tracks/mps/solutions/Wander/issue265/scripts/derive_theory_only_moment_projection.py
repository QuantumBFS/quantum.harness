#!/usr/bin/env python3
"""Evaluate the analytic finite-window KPZ-to-Burgers moment projection.

Only exact/TBA KPZ constants, the universal stationary KPZ shape factor, the
wall height, and the declared time window enter.  No Heisenberg trajectory,
measured width, or reported Burgers coefficient is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    KPZ_BURGERS_MOMENT_SHAPE_FACTOR,
    theory_only_width_rate_projection,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--wall-height", type=float, default=0.5)
    parser.add_argument(
        "--shape-factor",
        type=float,
        default=KPZ_BURGERS_MOMENT_SHAPE_FACTOR,
    )
    args = parser.parse_args()
    result = theory_only_width_rate_projection(
        args.t_start,
        args.t_stop,
        wall_height=args.wall_height,
        shape_factor=args.shape_factor,
    )
    result["gram"] = result["gram"].tolist()
    result["rhs"] = result["rhs"].tolist()
    result.update(
        {
            "time_window": [args.t_start, args.t_stop],
            "wall_height": args.wall_height,
            "shape_factor": args.shape_factor,
            "loss": "continuum_width_rate_L2",
            "uses_heisenberg_trajectory": False,
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
