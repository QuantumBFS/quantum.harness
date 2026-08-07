#!/usr/bin/env python3
"""Run or resume one independent-chain ALF batch."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence

from prepare_alf_chain import (
    DEFAULT_TRIAL_ASSETS,
    atomic_json,
    prepare_batch,
    sha256_file,
)


def _completed_bins(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip())


def _available_cpus(count: int) -> list[int]:
    available = sorted(os.sched_getaffinity(0))
    preferred = [0, 2, 4, 6, 8, 10]
    selected = [cpu for cpu in preferred if cpu in available]
    for cpu in available:
        if len(selected) >= count:
            break
        if cpu not in selected:
            selected.append(cpu)
    if len(selected) < count:
        raise RuntimeError(f"need {count} distinct CPUs, found {len(available)}")
    return selected[:count]


def _environment(cpu: int | None) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "I_MPI_PIN": "1",
        "I_MPI_PIN_DOMAIN": "core",
    })
    if cpu is not None:
        env["I_MPI_PIN_PROCESSOR_LIST"] = str(cpu)
    return env


def run_batch(
    batch_dir: Path,
    *,
    launcher: Sequence[str] = ("mpirun", "-np", "1"),
    resume: bool = True,
    progress_seconds: float = 20.0,
    bind_cpus: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(
        (batch_dir / "batch_manifest.json").read_text(encoding="utf-8")
    )
    state_path = batch_dir / "batch_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") == "complete":
        return state
    previous = state.get("chains", {}) if resume else {}
    active: dict[int, tuple[subprocess.Popen[str], Any, float]] = {}
    records: dict[str, dict[str, Any]] = dict(previous)
    executable = manifest["executable"]
    expected_bins = int(manifest["nbin"])
    chain_records = manifest["chains"]
    chain_ids = [int(record["chain"]) for record in chain_records]
    if chain_ids != list(
        range(chain_ids[0], chain_ids[0] + len(chain_records))
    ):
        raise RuntimeError("batch chain identifiers must be contiguous")
    chain_count = len(chain_records)
    if chain_count < 6:
        raise RuntimeError("batch requires at least six independent chains")
    cpus = _available_cpus(chain_count) if bind_cpus else [None] * chain_count
    for chain_record, cpu in zip(chain_records, cpus):
        chain = int(chain_record["chain"])
        old = records.get(str(chain), {})
        if resume and old.get("returncode") == 0 \
                and old.get("complete_bins") == expected_bins:
            continue
        run_dir = batch_dir / f"chain_{chain}"
        log_handle = (run_dir / "run.log").open("w", encoding="utf-8")
        command = [*launcher, executable]
        process = subprocess.Popen(
            command,
            cwd=run_dir,
            env=_environment(cpu),
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        active[chain] = (process, log_handle, time.monotonic())
        records[str(chain)] = {
            "chain": chain,
            "seed": chain_record["seed"],
            "cpu": cpu,
            "status": "running",
        }
    atomic_json(
        state_path,
        {
            "schema_version": 1,
            "status": "running",
            "statistics_eligible": False,
            "chains": records,
        },
    )
    started = time.monotonic()
    last_progress = 0.0
    while active:
        now = time.monotonic()
        for chain, (process, log_handle, chain_started) in list(active.items()):
            returncode = process.poll()
            if returncode is None:
                continue
            log_handle.close()
            run_dir = batch_dir / f"chain_{chain}"
            records[str(chain)] = {
                **records[str(chain)],
                "status": "complete" if returncode == 0 else "failed",
                "returncode": returncode,
                "wall_seconds": time.monotonic() - chain_started,
                "complete_bins": _completed_bins(run_dir / "Ener_scal"),
                "parameter_sha256": sha256_file(run_dir / "parameters"),
            }
            del active[chain]
            atomic_json(
                state_path,
                {
                    "schema_version": 1,
                    "status": "running",
                    "statistics_eligible": False,
                    "chains": records,
                },
            )
        if now - last_progress >= progress_seconds:
            complete_bins = sum(
                _completed_bins(
                    batch_dir / f"chain_{chain}" / "Ener_scal"
                )
                for chain in chain_ids
            )
            print(
                f"theta={manifest['theta']} batch={manifest['batch']} "
                f"complete_bins={complete_bins}/{chain_count * expected_bins} "
                f"live_chains={len(active)} wall={now - started:.1f}s",
                flush=True,
            )
            last_progress = now
        if active:
            time.sleep(min(0.1, max(0.01, progress_seconds)))
    success = all(
        records.get(str(chain), {}).get("returncode") == 0
        and records[str(chain)].get("complete_bins") == expected_bins
        for chain in chain_ids
    )
    final = {
        "schema_version": 1,
        "status": "complete" if success else "failed",
        "statistics_eligible": success,
        "chains": records,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_json(state_path, final)
    return final


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensemble", choices=("TI", "II"), required=True)
    parser.add_argument("--theta", type=int, required=True)
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--nbin", type=int, required=True)
    parser.add_argument("--nsweep", type=int, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--master-seed", type=int, default=900090)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--trial-assets", type=Path, default=DEFAULT_TRIAL_ASSETS)
    parser.add_argument("--chains", type=int, default=6)
    parser.add_argument("--nwrap", type=int, default=5)
    parser.add_argument(
        "--direct",
        action="store_true",
        help="run a serial/noMPI ALF executable without mpirun",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_dir = (
        args.run_root / args.ensemble / f"theta_{args.theta:03d}"
        / f"batch_{args.batch:03d}"
    )
    if not (batch_dir / "batch_manifest.json").exists():
        prepare_batch(
            args.run_root,
            ensemble=args.ensemble,
            theta=args.theta,
            batch=args.batch,
            nbin=args.nbin,
            nsweep=args.nsweep,
            master_seed=args.master_seed,
            executable=args.executable,
            trial_assets=args.trial_assets,
            chains=args.chains,
            nwrap=args.nwrap,
        )
    launcher: Sequence[str] = () if args.direct else ("mpirun", "-np", "1")
    state = run_batch(batch_dir, launcher=launcher, bind_cpus=True)
    if state["status"] != "complete":
        raise SystemExit("ALF batch failed; inspect batch_state.json and run.log")


if __name__ == "__main__":
    main()
