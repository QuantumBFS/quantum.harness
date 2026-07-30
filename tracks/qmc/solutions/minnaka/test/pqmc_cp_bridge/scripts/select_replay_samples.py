#!/usr/bin/env python3
"""Uniform-by-chain archive sampling independent of replay outcomes."""

from __future__ import annotations

import hashlib
import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable, Mapping

from path_archive import ArchiveReader


def _tie_key(seed: int, sample_id: int) -> bytes:
    return hashlib.sha256(f"{seed}:{sample_id}".encode()).digest()


def stratified_sample(
    index: Iterable[Mapping[str, int]],
    per_chain: int,
    seed: int,
) -> list[int]:
    if per_chain <= 0:
        raise ValueError("per_chain must be positive")
    groups: dict[tuple[int, int], list[Mapping[str, int]]] = {}
    for row in index:
        key = (int(row["ensemble"]), int(row["chain"]))
        groups.setdefault(key, []).append(row)
    chains_by_ensemble = {
        ensemble: sorted(chain for code, chain in groups if code == ensemble)
        for ensemble in (1, 2)
    }
    chains = chains_by_ensemble[1]
    if (
        not chains
        or chains_by_ensemble[2] != chains
        or chains != list(range(len(chains)))
        or set(groups) != {
            (ensemble, chain)
            for ensemble in (1, 2)
            for chain in chains
        }
    ):
        raise ValueError(
            "archive index must contain matching contiguous chains "
            "for both ensembles"
        )
    selected: list[int] = []
    for key in sorted(groups):
        rows = sorted(
            groups[key],
            key=lambda row: (
                int(row["bin"]),
                int(row["sweep"]),
                _tie_key(seed, int(row["sample_id"])),
            ),
        )
        if len(rows) < per_chain:
            raise ValueError(f"not enough records in ensemble/chain {key}")
        positions = [
            min(
                len(rows) - 1,
                math.floor((slot + 0.5) * len(rows) / per_chain),
            )
            for slot in range(per_chain)
        ]
        if len(set(positions)) != per_chain:
            raise RuntimeError("uniform quantile selection produced duplicates")
        selected.extend(int(rows[position]["sample_id"]) for position in positions)
    return sorted(selected)


def archive_rows(index_path: Path) -> list[dict[str, int]]:
    index = json.loads(index_path.read_text())
    rows: list[dict[str, int]] = []
    seen: set[int] = set()
    for entry in index.get("entries", []):
        path = Path(entry["path"])
        if not path.is_absolute():
            path = (index_path.parent / path).resolve()
        reader = ArchiveReader(path)
        ensemble = int(reader.header.ensemble_code)
        chain = int(entry["chain"])
        for record in reader.records():
            if record.sample_id in seen:
                raise ValueError("duplicate sample ID across archives")
            seen.add(record.sample_id)
            rows.append({
                "sample_id": record.sample_id,
                "ensemble": ensemble,
                "chain": chain,
                "bin": record.bin_id,
                "sweep": record.sweep_id,
            })
    return rows


def write_sample_manifest(
    path: Path, rows: Iterable[Mapping[str, int]], sample_ids: Iterable[int]
) -> None:
    by_id = {int(row["sample_id"]): row for row in rows}
    selected = sorted(int(value) for value in sample_ids)
    if len(selected) != len(set(selected)) or not set(selected) <= set(by_id):
        raise ValueError("selected sample IDs are duplicate or unavailable")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("sample_id", "ensemble", "chain"))
        for sample_id in selected:
            row = by_id[sample_id]
            writer.writerow((
                sample_id,
                "II" if int(row["ensemble"]) == 1 else "TI",
                int(row["chain"]),
            ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--per-chain", type=int)
    group.add_argument("--all", action="store_true")
    parser.add_argument("--seed", type=int, default=7721)
    args = parser.parse_args()
    rows = archive_rows(args.archive_index)
    selected = (
        sorted(int(row["sample_id"]) for row in rows)
        if args.all
        else stratified_sample(rows, args.per_chain, args.seed)
    )
    write_sample_manifest(args.output, rows, selected)
    print(f"wrote {len(selected)} sample IDs to {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
