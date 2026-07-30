#!/usr/bin/env python3
"""Export exact rooted graph balls for the Julia hierarchy engine."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from issue92.graphs import GEOMETRIES, hyperbolic_rooted_ball


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-radius", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("results/graphs"))
    args = parser.parse_args()
    if args.max_radius < 1:
        parser.error("--max-radius must be positive")

    for geometry in GEOMETRIES:
        for radius in range(1, args.max_radius + 1):
            graph = hyperbolic_rooted_ball(geometry, radius)
            payload = {
                "geometry": geometry,
                "label": graph.graph["label"],
                "source": graph.graph["source"],
                "root": int(graph.graph["root"]),
                "radius": radius,
                "vertices": sorted(int(vertex) for vertex in graph.nodes),
                "edges": sorted(
                    [min(int(u), int(v)), max(int(u), int(v))] for u, v in graph.edges
                ),
            }
            destination = args.output / f"{geometry}-L{radius}.json"
            atomic_json(destination, payload)
            print(
                f"wrote {destination}: {graph.number_of_nodes()} sites, "
                f"{graph.number_of_edges()} edges",
                flush=True,
            )


if __name__ == "__main__":
    main()
