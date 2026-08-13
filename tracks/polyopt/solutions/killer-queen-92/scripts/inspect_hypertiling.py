#!/usr/bin/env python3
"""Generate genuine hyperbolic rooted balls and print combinatorial summaries."""

from __future__ import annotations

import argparse
import json

from issue92.graphs import GEOMETRIES, graph_summary, hyperbolic_rooted_ball


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", choices=tuple(GEOMETRIES), default="83")
    parser.add_argument("--radius", type=int, default=2)
    args = parser.parse_args()
    graph = hyperbolic_rooted_ball(args.geometry, args.radius)
    print(json.dumps(graph_summary(graph), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
