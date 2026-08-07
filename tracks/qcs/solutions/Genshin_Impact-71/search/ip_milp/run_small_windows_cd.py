"""Second MILP batch: deliberately easy, distinct C/D MFFCs only.

The primary run ranks large MFFCs first.  This complementary batch ranks
2- and 3-gate cones first so that the independent IP arm also obtains completed
proof statuses on C and D rather than spending every slot on a 4→3 timeout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import run_experiments as experiment


def choose_small_cd(
    circuit: experiment.Circuit, limit: int
) -> list[tuple[str, set[str]]]:
    if len(circuit.gates) not in {113, 156}:
        return []
    candidates = []
    for gate_index, gate in enumerate(circuit.gates):
        removed = experiment.mffc(circuit, gate.output)
        if 2 <= len(removed) <= 3:
            candidates.append(((len(removed), gate_index), gate.output, removed))
    candidates.sort(key=lambda item: item[0])
    return [(root, removed) for _, root, removed in candidates[:limit]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=180)
    parser.add_argument("--witness-count", type=int, default=64)
    parser.add_argument("--windows-per-circuit", type=int, default=3)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    experiment.choose_windows = choose_small_cd
    started = time.time()
    records = experiment.local_experiments(
        args.reference_dir,
        args.output_dir,
        args.time_limit,
        args.witness_count,
        args.windows_per_circuit,
    )
    result = {
        "schema": "issue71-ip-milp-small-cd-v1",
        "root_seed": 42,
        "selection": "C/D only; MFFC size ascending then root index",
        "parameters": {
            "time_limit": args.time_limit,
            "witness_count": args.witness_count,
            "windows_per_circuit": args.windows_per_circuit,
        },
        "records": records,
        "wall_seconds": time.time() - started,
    }
    (args.output_dir / "results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (args.output_dir / "COMPLETE").write_text("IP_MILP_SMALL_CD_COMPLETE\n")
    print(
        f"COMPLETE output={args.output_dir} records={len(records)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
