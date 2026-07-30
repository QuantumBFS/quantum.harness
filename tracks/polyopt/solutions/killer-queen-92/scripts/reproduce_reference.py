#!/usr/bin/env python3
"""Reproduce the pinned SpectralGap.jl Table-S1 Ising cell with Mosek."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

COMMIT = "a1171c906ff2cc2901e58c2426397a2f68c32bb7"


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def has_mosek_license() -> bool:
    configured = os.environ.get("MOSEKLM_LICENSE_FILE")
    # MOSEKLM_LICENSE_FILE may be a local file or a FlexNet server expression
    # such as ``port@host``.  A nonempty environment value is therefore enough
    # to attempt the solve; Mosek itself remains the authority on validity.
    return bool(configured) or (Path.home() / "mosek/mosek.lic").exists()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/reference/ising-L2-d2-g0.5-a1171c9.json"),
    )
    args = parser.parse_args()
    record: dict[str, object] = {
        "project": "wangjie212/SpectralGap",
        "commit": COMMIT,
        "model": "transverse-field Ising chain",
        "paper_cell": {"g": 0.5, "L": 2, "N": 5, "d": 2},
        "paper_table_S1_endpoint": 0.52,
        "expected_upstream_blocks": {
            "moment_Z2_even": 67,
            "moment_Z2_odd": 26,
            "gap_Z2_even": 5,
            "gap_Z2_odd": 6,
        },
        "solver_required": "Mosek",
    }
    if not has_mosek_license():
        record.update(
            status="BLOCKED",
            blocker="No MOSEKLM_LICENSE_FILE or ~/mosek/mosek.lic is available on this host",
            mosek_version=None,
            endpoint=None,
            discrepancy=None,
        )
        atomic_json(args.output, record)
        print(f"wrote blocked reference record to {args.output}", flush=True)
        raise SystemExit(2)

    environment = os.environ.copy()
    depot = Path(".raw/julia-depot").resolve()
    environment["JULIA_DEPOT_PATH"] = f"{depot}:"
    environment["SPECTRALGAP_COMMIT"] = COMMIT
    environment["REFERENCE_OUTPUT"] = str(args.output.resolve())
    command = ["julia", "scripts/reproduce_reference_upstream.jl"]
    completed = subprocess.run(command, text=True, capture_output=True, env=environment)
    record["stdout"] = completed.stdout
    record["stderr"] = completed.stderr
    record["exit_code"] = completed.returncode
    if completed.returncode != 0:
        record.update(status="BLOCKED", blocker="upstream Mosek reproduction failed; inspect stderr")
        atomic_json(args.output, record)
        raise SystemExit(completed.returncode)
    upstream = json.loads(completed.stdout.split("REFERENCE_JSON:", 1)[1].strip().splitlines()[0])
    record.update(upstream)
    record["status"] = "DONE"
    record["discrepancy"] = float(record["endpoint"]) - 0.52
    atomic_json(args.output, record)
    print(f"reproduced endpoint {record['endpoint']} at blocks {record['actual_blocks']}", flush=True)


if __name__ == "__main__":
    main()
