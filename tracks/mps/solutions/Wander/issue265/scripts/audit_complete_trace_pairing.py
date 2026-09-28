#!/usr/bin/env python3
"""Freeze the all-pairs trace estimator against an independent P=1 control.

For a frame of S independent x probes and S independent y probes, the S
cyclic shifts enumerate every ordered pair (x_i,y_j) exactly once.  Averaging
all S^2 force products is therefore the conditional average over the pairing
index.  It is target-free and unbiased by the x/y product measure.  This audit
still compares independent replicas against P=1 to catch implementation or
finite-sample failures before production.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.audit_trace_pairing_variance_reduction import audit


def complete_pairing_audit(
    paths: list[Path],
    *,
    required_replicates: int = 8,
    target_complex_sem: float = 5.0e-4,
) -> dict[str, object]:
    payloads = [(path, json.loads(path.read_text())) for path in paths]
    sample_counts = {
        int(payload["regulator"]["samples_per_internal_wave"])
        for _, payload in payloads
    }
    if len(sample_counts) != 1:
        raise ValueError("all inputs must use one trace frame size")
    samples = sample_counts.pop()
    pairing_counts = {
        int(payload["regulator"].get("trace_pairings_per_frame", 1))
        for _, payload in payloads
    }
    if pairing_counts != {1, samples}:
        raise ValueError("inputs must contain exactly P=1 and P=S complete pairing")
    for path, payload in payloads:
        regulator = payload["regulator"]
        count = int(regulator.get("trace_pairings_per_frame", 1))
        if count == samples:
            if regulator.get("trace_pairing_strategy") != "cyclic_bipartite":
                raise ValueError(f"wrong pairing strategy in {path}")
            if not regulator.get("complete_cartesian_trace_pairing"):
                raise ValueError(f"complete pairing not certified in {path}")
            if not payload.get("scope", {}).get(
                "complete_cartesian_trace_pairing_is_conditional_pairing_average"
            ):
                raise ValueError(f"conditional pairing average absent in {path}")

    result = audit(
        paths,
        required_replicates=required_replicates,
        target_complex_sem=target_complex_sem,
    )
    candidate = next(
        row for row in result["rows"]
        if row["trace_pairings_per_frame"] == samples
    )
    result.update(
        {
            "schema": 1,
            "method": "complete_cartesian_trace_pairing_preregistered_audit",
            "all_pairs_identity": (
                "S cyclic shifts enumerate each ordered (x_i,y_j) once"
            ),
            "candidate_pairings_per_frame": samples,
            "candidate_selected_before_candidate_outputs": True,
            "fallback_if_rejected": (
                "use P=1 with the plugin independent-replicate count; "
                "do not select another partial pairing count"
            ),
            "complete_pairing_accepted": bool(candidate["accepted"]),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--required-replicates", type=int, default=8)
    parser.add_argument("--target-complex-sem", type=float, default=5.0e-4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = complete_pairing_audit(
        args.inputs,
        required_replicates=args.required_replicates,
        target_complex_sem=args.target_complex_sem,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
