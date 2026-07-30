#!/usr/bin/env python3
"""Replay disjoint sample-manifest shards concurrently and merge outputs."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess

from prefix_file import HEADER, RECORD, records as prefix_records
from run_bulk_replay import (
    initial_mixed_energy,
    replay_command,
    validate_inputs,
)


MANIFEST_COLUMNS = ["sample_id", "ensemble", "chain"]


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MANIFEST_COLUMNS:
            raise ValueError("unexpected sample manifest columns")
        rows = list(reader)
    sample_ids = [int(row["sample_id"]) for row in rows]
    if not rows or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("sample manifest is empty or has duplicate IDs")
    return rows


def split_rows(
    rows: list[dict[str, str]], workers: int
) -> list[list[dict[str, str]]]:
    if workers <= 0:
        raise ValueError("worker count must be positive")
    shards = [[] for _ in range(min(workers, len(rows)))]
    for index, row in enumerate(rows):
        shards[index % len(shards)].append(row)
    if sorted(int(row["sample_id"]) for shard in shards for row in shard) != \
            sorted(int(row["sample_id"]) for row in rows):
        raise RuntimeError("replay shard partition is not lossless")
    return shards


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def merge_summaries(paths: list[Path], output: Path) -> int:
    fieldnames: list[str] | None = None
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if fieldnames is None:
                fieldnames = reader.fieldnames
            elif reader.fieldnames != fieldnames:
                raise ValueError("replay shard summary columns differ")
            rows.extend(reader)
    if not fieldnames:
        raise ValueError("replay shards contain no summary header")
    sample_ids = [int(row["sample_id"]) for row in rows]
    if not rows or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("merged replay summary has duplicate/missing rows")
    rows.sort(key=lambda row: int(row["sample_id"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    return len(rows)


def merge_prefixes(paths: list[Path], output: Path) -> int:
    payloads: list[bytes] = []
    total = 0
    for path in paths:
        validated = sum(1 for _ in prefix_records(path))
        raw = path.read_bytes()
        header = HEADER.unpack(raw[:HEADER.size])
        count = int(header[5])
        if validated != count or len(raw) != HEADER.size + count * RECORD.size:
            raise ValueError("prefix shard count/size mismatch")
        total += count
        payloads.append(raw[HEADER.size:])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(HEADER.pack(
            b"QHPFX01\0", 1, 0x01020304,
            HEADER.size, RECORD.size, total,
        ))
        for payload in payloads:
            handle.write(payload)
    if sum(1 for _ in prefix_records(temporary)) != total:
        raise RuntimeError("merged prefix validation failed")
    temporary.replace(output)
    return total


def run_parallel_replay(
    *,
    executable: Path,
    archive_index: Path,
    sample_manifest: Path,
    selected_projection: Path,
    trial_manifest: Path,
    field_order: Path,
    output_dir: Path,
    stabilize_every: int,
    workers: int,
    summary_only: bool = False,
) -> tuple[Path, Path | None]:
    validate_inputs(
        archive_index, sample_manifest,
        selected_projection, trial_manifest,
    )
    rows = read_manifest(sample_manifest)
    shards = split_rows(rows, workers)
    work = output_dir / f".parallel_s{stabilize_every}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    reference_energy = initial_mixed_energy(trial_manifest.parent)
    commands: list[tuple[list[str], Path, Path | None]] = []
    for index, shard in enumerate(shards):
        root = work / f"shard_{index:03d}"
        manifest = root / "samples.csv"
        summary = root / "summary.csv"
        prefix = None if summary_only else root / "prefix.qhpfx"
        write_manifest(manifest, shard)
        commands.append((
            replay_command(
                executable, archive_index, manifest,
                selected_projection, trial_manifest, field_order,
                summary, prefix, reference_energy, stabilize_every,
                summary_only=summary_only,
            ),
            summary,
            prefix,
        ))

    completed = 0
    update_every = max(1, len(commands) // 20)

    def execute(command: tuple[list[str], Path, Path | None]) -> None:
        subprocess.run(
            command[0], check=True,
            stdout=subprocess.DEVNULL,
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(commands)
    ) as pool:
        futures = [pool.submit(execute, command) for command in commands]
        for future in concurrent.futures.as_completed(futures):
            future.result()
            completed += 1
            if completed % update_every == 0 or completed == len(commands):
                print(
                    f"parallel replay shards {completed}/{len(commands)}",
                    flush=True,
                )

    summary_output = output_dir / f"replay_summary_s{stabilize_every}.csv"
    summary_count = merge_summaries(
        [command[1] for command in commands], summary_output
    )
    prefix_output: Path | None = None
    if summary_only:
        if summary_count != len(rows):
            raise RuntimeError("parallel replay summary count mismatch")
        print(
            f"parallel replay complete: paths={summary_count}, "
            "prefixes=disabled",
            flush=True,
        )
    else:
        prefix_output = (
            output_dir / f"replay_prefix_s{stabilize_every}.qhpfx"
        )
        prefix_paths = [command[2] for command in commands]
        if any(path is None for path in prefix_paths):
            raise RuntimeError("parallel replay prefix shard is missing")
        prefix_count = merge_prefixes(
            [path for path in prefix_paths if path is not None],
            prefix_output,
        )
        expected_prefixes = summary_count * int(
            json.loads(selected_projection.read_text())["ltrot_star"]
        )
        if summary_count != len(rows) or prefix_count != expected_prefixes:
            raise RuntimeError("parallel replay merge count mismatch")
        print(
            f"parallel replay complete: paths={summary_count}, "
            f"prefixes={prefix_count}",
            flush=True,
        )
    return summary_output, prefix_output


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument(
        "--selected-projection", type=Path,
        default=bridge / "results/selected_projection.json",
    )
    parser.add_argument(
        "--trial-manifest", type=Path,
        default=bridge / "assets/trials/trial_manifest.json",
    )
    parser.add_argument(
        "--field-order", type=Path,
        default=bridge / "contracts/field_order.json",
    )
    parser.add_argument(
        "--executable", type=Path,
        default=root / "test/cpmc_path_audit/build/cpmc_audit",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=bridge / "replay/bulk",
    )
    parser.add_argument("--stabilize-every", type=int, default=5)
    parser.add_argument(
        "--workers", type=int,
        default=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")),
    )
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.stabilize_every <= 0 or args.workers <= 0:
        parser.error("stabilization interval and workers must be positive")
    run_parallel_replay(
        executable=args.executable,
        archive_index=args.archive_index,
        sample_manifest=args.sample_manifest,
        selected_projection=args.selected_projection,
        trial_manifest=args.trial_manifest,
        field_order=args.field_order,
        output_dir=args.output_dir,
        stabilize_every=args.stabilize_every,
        workers=args.workers,
        summary_only=args.summary_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
