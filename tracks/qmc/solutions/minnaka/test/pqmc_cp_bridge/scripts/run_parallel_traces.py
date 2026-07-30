#!/usr/bin/env python3
"""Run detailed C++ path traces in independent shards and merge CSV output."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import os
from pathlib import Path
import shutil
import subprocess

MANIFEST_COLUMNS = [
    "path_id", "role", "case_id", "config_id", "fields_file",
    "score", "log_d_over_mean", "weight_bin",
]


def split_trace_rows(
    rows: list[dict[str, str]], workers: int
) -> list[list[dict[str, str]]]:
    if workers <= 0 or not rows:
        raise ValueError("trace sharding needs rows and positive workers")
    shards = [[] for _ in range(min(workers, len(rows)))]
    for index, row in enumerate(rows):
        shards[index % len(shards)].append(row)
    identifiers = [
        row["path_id"] for shard in shards for row in shard
    ]
    if (
        len(identifiers) != len(rows)
        or len(set(identifiers)) != len(rows)
        or set(identifiers) != {row["path_id"] for row in rows}
    ):
        raise RuntimeError("trace shard partition is not lossless")
    return shards


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MANIFEST_COLUMNS:
            raise ValueError("unexpected detailed-trace manifest columns")
        rows = list(reader)
    identifiers = [row["path_id"] for row in rows]
    if not rows or len(identifiers) != len(set(identifiers)):
        raise ValueError("trace manifest is empty or has duplicate paths")
    return rows


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def merge_csv_outputs(paths: list[Path], output: Path) -> int:
    if not paths:
        raise ValueError("no trace outputs to merge")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    header: str | None = None
    rows = 0
    with temporary.open("w", newline="") as target:
        for path in paths:
            with path.open(newline="") as source:
                current = source.readline()
                if not current:
                    raise ValueError(f"empty trace shard: {path}")
                if header is None:
                    header = current
                    target.write(header)
                elif current != header:
                    raise ValueError("trace shard CSV headers differ")
                for line in source:
                    if not line.strip():
                        continue
                    target.write(line)
                    rows += 1
    temporary.replace(output)
    return rows


def trace_command(
    executable: Path,
    manifest: Path,
    trial_manifest: Path,
    steps_output: Path,
    masks_output: Path,
    *,
    stabilize_every: int,
) -> list[str]:
    return [
        str(executable), "batch-replay",
        "--lx", "4", "--ly", "4", "--t", "1", "--u", "4",
        "--dt", "0.05", "--n-up", "8", "--n-down", "8",
        "--slices", "420", "--trial", "uhf",
        "--trial-manifest", str(trial_manifest),
        "--proposal", "site",
        "--stabilize-every", str(stabilize_every),
        "--manifest", str(manifest),
        "--steps-output", str(steps_output),
        "--masks-output", str(masks_output),
        "--progress-updates", "1",
    ]


def run_parallel_traces(
    *,
    executable: Path,
    manifest: Path,
    trial_manifest: Path,
    output_dir: Path,
    workers: int,
    stabilize_every: int = 5,
) -> tuple[Path, Path]:
    rows = read_manifest(manifest)
    shards = split_trace_rows(rows, workers)
    work = output_dir / ".parallel_traces"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    commands: list[tuple[list[str], Path, Path]] = []
    for index, shard in enumerate(shards):
        root = work / f"shard_{index:03d}"
        shard_manifest = root / "manifest.csv"
        steps = root / "steps.csv"
        masks = root / "masks.csv"
        write_manifest(shard_manifest, shard)
        commands.append((
            trace_command(
                executable, shard_manifest, trial_manifest, steps, masks,
                stabilize_every=stabilize_every,
            ),
            steps,
            masks,
        ))

    completed = 0
    update_every = max(1, len(commands) // 20)

    def execute(item: tuple[list[str], Path, Path]) -> None:
        subprocess.run(
            item[0], check=True, stdout=subprocess.DEVNULL,
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(commands)
    ) as pool:
        futures = [pool.submit(execute, item) for item in commands]
        for future in concurrent.futures.as_completed(futures):
            future.result()
            completed += 1
            if completed % update_every == 0 or completed == len(commands):
                print(
                    f"parallel trace shards {completed}/{len(commands)}",
                    flush=True,
                )

    steps_output = output_dir / "full_trace_steps.csv"
    masks_output = output_dir / "full_trace_masks.csv"
    step_rows = merge_csv_outputs(
        [item[1] for item in commands], steps_output
    )
    mask_rows = merge_csv_outputs(
        [item[2] for item in commands], masks_output
    )
    expected_masks = len(rows) * 420
    expected_steps = expected_masks * 18
    if mask_rows != expected_masks or step_rows != expected_steps:
        raise RuntimeError(
            "detailed trace merge count mismatch: "
            f"steps={step_rows}/{expected_steps}, "
            f"masks={mask_rows}/{expected_masks}"
        )
    shutil.rmtree(work)
    print(
        f"parallel traces complete: paths={len(rows)}, "
        f"steps={step_rows}, masks={mask_rows}",
        flush=True,
    )
    return steps_output, masks_output


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--trial-manifest", type=Path,
        default=bridge / "assets/trials/trial_manifest.json",
    )
    parser.add_argument(
        "--executable", type=Path,
        default=root / "test/cpmc_path_audit/build/cpmc_audit",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--workers", type=int,
        default=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")),
    )
    parser.add_argument("--stabilize-every", type=int, default=5)
    args = parser.parse_args()
    if args.workers <= 0 or args.stabilize_every <= 0:
        parser.error("workers and stabilization interval must be positive")
    run_parallel_traces(
        executable=args.executable,
        manifest=args.manifest,
        trial_manifest=args.trial_manifest,
        output_dir=args.output_dir,
        workers=args.workers,
        stabilize_every=args.stabilize_every,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
