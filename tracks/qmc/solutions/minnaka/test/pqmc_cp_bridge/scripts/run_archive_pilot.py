#!/usr/bin/env python3
"""Run the approved six-chain II/TI archive pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archive_runs import run_archive_phase, write_archive_index


def _partial_index(archive_root: Path, ensemble: str) -> Path:
    return archive_root / f"pilot/archive_index.{ensemble}.json"


def _merge_if_complete(
    archive_root: Path, *, theta: int
) -> Path | None:
    partials = [_partial_index(archive_root, item) for item in ("II", "TI")]
    if not all(path.is_file() for path in partials):
        return None
    entries = []
    for path in partials:
        entries.extend(json.loads(path.read_text())["entries"])
    index = archive_root / "pilot/archive_index.json"
    write_archive_index(
        index, entries, phase="pilot", theta=theta,
        stride=5, after_sweep=2000,
        records=sum(int(row["records"]) for row in entries),
    )
    return index


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-projection", type=Path, required=True)
    parser.add_argument(
        "--executable", type=Path,
        default=root / "test/alf_hirsch_binary/run/binary/bin/ALF.binary.out",
    )
    parser.add_argument(
        "--run-root", type=Path, default=bridge / "runs/archive_pilot",
    )
    parser.add_argument(
        "--archive-root", type=Path, default=bridge / "archives",
    )
    parser.add_argument(
        "--ensemble", choices=("II", "TI", "both"), default="both",
    )
    parser.add_argument(
        "--direct", action="store_true",
        help="run the serial/noMPI ALF executable without mpirun",
    )
    args = parser.parse_args()
    selected = json.loads(args.selected_projection.read_text())
    theta = int(selected["theta_star"])
    ensembles = ("II", "TI") if args.ensemble == "both" \
        else (args.ensemble,)
    entries = run_archive_phase(
        run_root=args.run_root,
        archive_root=args.archive_root,
        phase="pilot",
        theta=theta,
        nsweep=4000,
        stride=5,
        after_sweep=2000,
        executable=args.executable,
        selected_projection=args.selected_projection,
        master_seed=1_700_090,
        ensembles=ensembles,
        direct=args.direct,
    )
    expected = len(ensembles) * 6 * 400
    actual = sum(entry["records"] for entry in entries)
    if actual != expected:
        raise RuntimeError(f"pilot expected {expected} records, found {actual}")
    for ensemble in ensembles:
        ensemble_entries = [
            row for row in entries if row["ensemble"] == ensemble
        ]
        write_archive_index(
            _partial_index(args.archive_root, ensemble),
            ensemble_entries, phase="pilot", theta=theta,
            ensemble=ensemble,
            stride=5, after_sweep=2000,
            records=sum(row["records"] for row in ensemble_entries),
        )
    index = _merge_if_complete(args.archive_root, theta=theta)
    if index is None:
        print(
            f"pilot {','.join(ensembles)} complete; waiting for other ensemble",
            flush=True,
        )
        return 0
    print(f"pilot archive index: {index}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
