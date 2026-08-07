#!/usr/bin/env python3
"""Validate CPMC proposal probabilities with short fixed-prefix hit counts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Iterable, Mapping

from path_archive import ArchiveReader


CATEGORIES = ("regular", "low_final_q", "deep_prefix", "near_node")


def _truth(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _tie(sample_id: int) -> bytes:
    return hashlib.sha256(f"proposal-check:{sample_id}".encode()).digest()


def select_targets(
    source: Iterable[Mapping[str, object]],
    *,
    per_category: int = 5,
) -> list[dict[str, object]]:
    if per_category <= 0:
        raise ValueError("per-category target count must be positive")
    eligible = [
        dict(row) for row in source
        if str(row["ensemble"]) == "TI"
        and int(row["chain"]) in (0, 1, 2)
        and _truth(row["alive"])
        and not _truth(row.get("numerically_ambiguous", False))
    ]
    chosen: set[int] = set()
    selected: list[dict[str, object]] = []
    definitions = (
        (
            "low_final_q",
            lambda row: row["proposal_risk"] == "lowest_1pct",
            lambda row: (float(row["log_q_prop"]), int(row["sample_id"])),
        ),
        (
            "deep_prefix",
            lambda row: row["prefix_risk"] == "highest_1pct",
            lambda row: (-float(row["prefix_barrier"]), int(row["sample_id"])),
        ),
        (
            "near_node",
            lambda row: row["near_node_risk"] == "highest_1pct",
            lambda row: (-float(row["near_node_count"]), int(row["sample_id"])),
        ),
        (
            "regular",
            lambda row: (
                row["proposal_risk"] == "regular"
                and row["prefix_risk"] == "regular"
                and row["near_node_risk"] == "regular"
            ),
            lambda row: (_tie(int(row["sample_id"])),),
        ),
    )
    for category, predicate, order in definitions:
        candidates = sorted(
            (
                row for row in eligible
                if predicate(row) and int(row["sample_id"]) not in chosen
            ),
            key=order,
        )
        if len(candidates) < per_category:
            raise ValueError(
                f"insufficient {category} TI training targets: "
                f"{len(candidates)} < {per_category}"
            )
        for row in candidates[:per_category]:
            sample_id = int(row["sample_id"])
            chosen.add(sample_id)
            selected.append({
                **row,
                "sample_id": sample_id,
                "chain": int(row["chain"]),
                "target_category": category,
            })
    return sorted(
        selected,
        key=lambda row: (
            CATEGORIES.index(str(row["target_category"])),
            int(row["sample_id"]),
        ),
    )


def load_target_fields(
    selected: list[dict[str, object]],
    archive_index: Path,
    site_map_path: Path,
) -> list[dict[str, object]]:
    site_map = [
        [int(value) for value in line.split()]
        for line in site_map_path.read_text().splitlines() if line.strip()
    ]
    sites = len(site_map)
    cpp_by_alf = [-1] * sites
    for alf_one, cpp, _x, _y in site_map:
        cpp_by_alf[alf_one - 1] = cpp
    if sorted(cpp_by_alf) != list(range(sites)):
        raise ValueError("site map is not a bijection")
    wanted = {int(row["sample_id"]): row for row in selected}
    found: dict[int, tuple[int, ...]] = {}
    index = json.loads(archive_index.read_text())
    for entry in index.get("entries", []):
        if entry["ensemble"] != "TI":
            continue
        path = Path(entry["path"])
        if not path.is_absolute():
            path = (archive_index.parent / path).resolve()
        for record in ArchiveReader(path).records():
            if record.sample_id not in wanted:
                continue
            mapped = [-1] * len(record.fields)
            for event, field in enumerate(record.fields):
                slice_index, alf = divmod(event, sites)
                mapped[slice_index * sites + cpp_by_alf[alf]] = field
            found[record.sample_id] = tuple(mapped)
    if set(found) != set(wanted):
        raise ValueError("proposal targets are absent from TI archives")
    return [{
        "sample_id": str(row["sample_id"]),
        "stratum": row["target_category"],
        "fields": found[int(row["sample_id"])],
    } for row in selected]


def validate_output(path: Path, expected_ids: set[int]) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if {int(row["sample_id"]) for row in rows} != expected_ids:
        raise ValueError("proposal output sample IDs differ from targets")
    for row in rows:
        expected = float(row["expected_hits"])
        z_score = float(row["z_score"])
        if (
            not math.isfinite(expected) or expected < 20.0 - 1.0e-10
            or not math.isfinite(z_score) or abs(z_score) > 4.0
            or not _truth(row["within_4sigma"])
        ):
            raise RuntimeError(
                f"proposal binomial gate failed for {row['sample_id']}"
            )
    return rows


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--strata", type=Path, required=True)
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument(
        "--site-map", type=Path,
        default=bridge / "assets/trials/site_map.dat",
    )
    parser.add_argument("--independent-walkers", type=int, default=100_000)
    parser.add_argument("--minimum-expected-hits", type=float, default=20.0)
    parser.add_argument("--per-category", type=int, default=5)
    parser.add_argument("--seed", type=int, default=8_130_077)
    parser.add_argument(
        "--matlab", type=Path,
        default=Path("/home/minnaka/.local/bin/matlab"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=bridge / "results/proposal_check.csv",
    )
    args = parser.parse_args()
    if (
        args.independent_walkers <= 0
        or args.minimum_expected_hits <= 0.0
    ):
        parser.error("proposal workload must be positive")

    with args.strata.open(newline="") as handle:
        selected = select_targets(
            list(csv.DictReader(handle)),
            per_category=args.per_category,
        )
    targets = load_target_fields(
        selected, args.archive_index, args.site_map
    )
    run_root = bridge / "runs/matlab_cp/proposal_check"
    run_root.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    config_path = run_root / "proposal_check.json"
    mat_path = run_root / "proposal_check.mat"
    config = {
        "schema_version": 1,
        "package_dir": str(
            (bridge / "runs/matlab_cp/package").resolve()
        ),
        "trial_dir": str((bridge / "assets/trials").resolve()),
        "output_file": str(mat_path.resolve()),
        "output_csv": str(args.output.resolve()),
        "seed": args.seed,
        "independent_walkers": args.independent_walkers,
        "minimum_expected_hits": args.minimum_expected_hits,
        "targets": targets,
    }
    config_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    expression = (
        f"addpath('{bridge / 'matlab'}'); "
        f"run_proposal_prefix('{config_path.resolve()}')"
    )
    subprocess.run([str(args.matlab), "-batch", expression], check=True)
    rows = validate_output(
        args.output, {int(row["sample_id"]) for row in selected}
    )
    print(
        f"proposal check: {len(rows)} targets, all within 4 sigma",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
