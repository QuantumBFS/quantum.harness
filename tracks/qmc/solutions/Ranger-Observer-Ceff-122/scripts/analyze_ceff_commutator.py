#!/usr/bin/env python3
"""Evaluate the declared self-dual 2-to-1 block commutator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ceffflow.commutator import (
    self_dual_block_deficiency,
    self_dual_trajectory_block_deficiency,
)
from ceffflow.self_dual import SELF_DUAL_BETA


def _result_payload(result) -> dict:
    payload = {
        "record_range": result.record_range,
        "tv_deficiency": result.tv.deficiency,
        "kl_deficiency_nats": result.kl.deficiency,
        "tv_stochastic_map": result.tv.stochastic_map.tolist(),
        "kl_stochastic_map": result.kl.stochastic_map.tolist(),
        "tv_optimizer_status": result.tv.optimizer_status,
        "kl_optimizer_status": result.kl.optimizer_status,
    }
    if hasattr(result, "diamond_distance"):
        payload["half_diamond_distance"] = result.diamond_distance
        payload["diamond_norm"] = result.diamond_norm
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lengths", default="3,4,5")
    parser.add_argument("--trajectories", type=int, default=12)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--seed", type=int, default=122)
    args = parser.parse_args()

    lengths = [int(value) for value in args.lengths.split(",")]
    channel_level = [
        _result_payload(self_dual_block_deficiency(record_range=record_range))
        for record_range in (1, 2)
    ]
    trajectory_results = []
    for length in lengths:
        for record_range in (1, 2):
            result = self_dual_trajectory_block_deficiency(
                length,
                record_range=record_range,
                trajectories=args.trajectories,
                rows=args.rows,
                seed=args.seed,
            )
            row = _result_payload(result)
            row.update(
                {
                    "length": result.length,
                    "state_count": result.state_count,
                    "trajectories": result.trajectories,
                    "rows": result.rows,
                }
            )
            trajectory_results.append(row)

    payload = {
        "status": (
            "exact local channel witness and finite critical-trajectory "
            "evidence; not a thermodynamic central-charge result"
        ),
        "model": "self-dual weak monitored Ising circuit",
        "beta": SELF_DUAL_BETA,
        "tanh_beta": 2.0**-0.5,
        "block_channel": (
            "CNOT on each two-site block followed by tracing the syndrome; "
            "logical X pulls back to X1 X2"
        ),
        "quantum_first": "weak logical-X measurement after block RG",
        "record_first": (
            "one or two physical weak-X outcomes followed by an optimized "
            "row-stochastic classical map"
        ),
        "channel_level_x_eigenstate_family": channel_level,
        "critical_conditional_trajectory_family": trajectory_results,
        "seed": args.seed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
