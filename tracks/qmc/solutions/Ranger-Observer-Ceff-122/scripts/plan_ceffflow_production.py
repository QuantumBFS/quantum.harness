#!/usr/bin/env python3
"""Expand conditional ceffflow axes without creating invalid channel cells."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_run_spec(
    axes: dict[str, Any],
    *,
    run_id: str,
    run_dir: Path,
    axes_source: Path,
) -> dict[str, Any]:
    """Expand optional model axes into deterministic, valid run-spec cells."""
    lengths = axes["lengths"]
    seeds = axes["seeds"]
    cells: list[dict[str, object]] = []

    def append(settings: dict[str, object]) -> None:
        cells.append(
            {
                "cell_id": f"cell-{len(cells) + 1:04d}",
                "settings": settings,
            }
        )

    if axes.get("clean_ising", False):
        append(
            {
                "model": "clean_ising",
                "lengths": lengths,
                "channel": {"kind": "identity", "parameter": 0.0},
                "steps": 20,
                "burn_in": 0,
                "block_size": 10,
                "seed": 0,
                "particles": 1,
            }
        )

    nishimori = axes.get("nishimori")
    if nishimori is not None:
        for seed in seeds:
            append(
                {
                    "model": "nishimori",
                    "lengths": lengths,
                    "channel": {"kind": "identity", "parameter": 0.0},
                    **nishimori,
                    "seed": seed,
                    "particles": 1,
                }
            )

    self_dual = axes.get("self_dual")
    if self_dual is not None:
        channels = self_dual["channels"]
        common = {
            "steps": self_dual["steps"],
            "burn_in": self_dual["burn_in"],
            "block_size": self_dual["block_size"],
        }

        # Identity has no latent-history approximation, so it is emitted once
        # per seed and always uses a single exact particle.
        for parameter in channels.get("identity", []):
            for seed in seeds:
                append(
                    {
                        "model": "self_dual",
                        "lengths": lengths,
                        "channel": {
                            "kind": "identity",
                            "parameter": parameter,
                        },
                        **common,
                        "seed": seed,
                        "particles": 1,
                    }
                )

        particle_counts = self_dual.get("particle_counts")
        if particle_counts is None:
            particle_counts = [self_dual["particles"]]
        if not particle_counts or len(set(particle_counts)) != len(particle_counts):
            raise ValueError("particle_counts must be nonempty and unique")

        # Particle count is outermost so a contiguous array range represents
        # one complete convergence level over every degraded resolution.
        for particles in particle_counts:
            for channel, parameters in channels.items():
                if channel == "identity":
                    continue
                for parameter in parameters:
                    for seed in seeds:
                        append(
                            {
                                "model": "self_dual",
                                "lengths": lengths,
                                "channel": {
                                    "kind": channel,
                                    "parameter": parameter,
                                },
                                **common,
                                "seed": seed,
                                "particles": particles,
                            }
                        )

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "result_root": "cells",
        "axes_source": str(axes_source),
        "cells": cells,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", default="ceffflow-production")
    args = parser.parse_args()
    axes = json.loads(args.axes.read_text())
    payload = build_run_spec(
        axes,
        run_id=args.run_id,
        run_dir=args.output.parent,
        axes_source=args.axes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"planned {len(payload['cells'])} valid cells -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
