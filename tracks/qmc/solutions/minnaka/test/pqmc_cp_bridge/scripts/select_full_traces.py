#!/usr/bin/env python3
"""Deterministically select risky long paths and matched regular controls."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping

from analyze_prefix_risk import chain_partitions
from path_archive import ArchiveReader


def _tie(seed: int, case_id: int, sample_id: int) -> bytes:
    return hashlib.sha256(
        f"{seed}:{case_id}:{sample_id}".encode()
    ).digest()


def _deciles(rows: list[dict[str, object]]) -> None:
    for ensemble in ("II", "TI"):
        group = [row for row in rows if row["ensemble"] == ensemble]
        ordered = sorted(
            group, key=lambda row: (
                float(row["alf_frozen_etot"]), int(row["sample_id"])
            )
        )
        for rank, row in enumerate(ordered):
            row["energy_decile"] = min(9, 10 * rank // len(ordered))


def select_cases_and_controls(
    source: Iterable[Mapping[str, object]],
    *,
    seed: int = 9137,
    dead_cap: int = 500,
    category_cap: int = 5,
) -> list[dict[str, object]]:
    rows = [dict(row) for row in source]
    if not rows:
        raise ValueError("trace selection source is empty")
    training_chains, _held_out_chains = chain_partitions(rows)
    training_set = set(training_chains)
    for row in rows:
        row["sample_id"] = int(row["sample_id"])
        row["chain"] = int(row["chain"])
        row["alive"] = str(row["alive"]).lower() in {"1", "true"}
        row["numerically_ambiguous"] = str(
            row.get("numerically_ambiguous", False)
        ).lower() in {"1", "true"}
        row["chain_split"] = (
            "training" if row["chain"] in training_set else "held_out"
        )
    _deciles(rows)
    ambiguous = [
        row for row in rows if row["numerically_ambiguous"]
    ]
    dead = [
        row for row in rows
        if not row["alive"] and not row["numerically_ambiguous"]
    ]
    if len(dead) > dead_cap:
        ordered = sorted(
            dead, key=lambda row: _tie(seed, 0, row["sample_id"])
        )
        dead = ordered[:dead_cap]
    alive = [row for row in rows if row["alive"]]
    top_count = max(1, math.ceil(0.001 * len(alive))) if alive else 0
    extreme_q = sorted(
        alive, key=lambda row: (
            float(row["log_q_prop"]), row["sample_id"]
        )
    )[:top_count]
    extreme_prefix = sorted(
        alive, key=lambda row: (
            -float(row["prefix_barrier"]), row["sample_id"]
        )
    )[:top_count]
    categories: list[tuple[str, list[dict[str, object]]]] = [
        ("ambiguous", ambiguous),
        ("dead", dead),
        ("proposal_low_1pct", [
            row for row in alive
            if row["proposal_risk"] == "lowest_1pct"
        ]),
        ("prefix_high_1pct", [
            row for row in alive
            if row["prefix_risk"] == "highest_1pct"
        ]),
        ("proposal_low_0p1pct", extreme_q),
        ("prefix_high_0p1pct", extreme_prefix),
    ]
    if category_cap <= 0:
        raise ValueError("trace category cap must be positive")
    case_by_id: dict[int, dict[str, object]] = {}
    labels: dict[int, list[str]] = {}
    for label, group in categories:
        for ensemble in ("II", "TI"):
            ensemble_group = [
                row for row in group if row["ensemble"] == ensemble
            ]
            if label.startswith("proposal_"):
                ordered = sorted(
                    ensemble_group,
                    key=lambda row: (
                        float(row["log_q_prop"]), row["sample_id"]
                    ),
                )
            elif label.startswith("prefix_"):
                ordered = sorted(
                    ensemble_group,
                    key=lambda row: (
                        -float(row["prefix_barrier"]), row["sample_id"]
                    ),
                )
            else:
                ordered = sorted(
                    ensemble_group,
                    key=lambda row: _tie(seed, 0, row["sample_id"]),
                )
            for row in ordered[:category_cap]:
                case_by_id[row["sample_id"]] = row
                labels.setdefault(row["sample_id"], []).append(label)
    regular = [
        row for row in rows
        if row["primary_static_stratum"] == "alive_regular_static"
        and row["sample_id"] not in case_by_id
        and not row["numerically_ambiguous"]
    ]
    used_controls: set[int] = set()
    selected: list[dict[str, object]] = []
    for case_id in sorted(case_by_id):
        case = case_by_id[case_id]
        selected.append({
            **case,
            "role": "case",
            "case_id": case_id,
            "selection_labels": ";".join(sorted(labels[case_id])),
        })
        candidates = [
            row for row in regular
            if row["ensemble"] == case["ensemble"]
            and row["chain_split"] == case["chain_split"]
            and row["energy_decile"] == case["energy_decile"]
            and row["sample_id"] not in used_controls
        ]
        if not candidates:
            candidates = [
                row for row in regular
                if row["ensemble"] == case["ensemble"]
                and row["chain_split"] == case["chain_split"]
                and row["energy_decile"] == case["energy_decile"]
            ]
        if not candidates:
            candidates = [
                row for row in regular
                if row["ensemble"] == case["ensemble"]
                and row["chain_split"] == case["chain_split"]
                and row["sample_id"] not in used_controls
            ]
        if not candidates:
            continue
        control = min(
            candidates,
            key=lambda row: (
                abs(float(row["alf_frozen_etot"]) -
                    float(case["alf_frozen_etot"])),
                _tie(seed, case_id, row["sample_id"]),
            ),
        )
        used_controls.add(control["sample_id"])
        selected.append({
            **control,
            "role": "control",
            "case_id": case_id,
            "selection_labels": "matched_regular_control",
        })
    return selected


def _log_mean(values: list[float]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(
        math.exp(value - maximum) for value in values
    )) - math.log(len(values))


def write_trace_inputs(
    selected: list[dict[str, object]],
    archive_index: Path,
    site_map_path: Path,
    fields_dir: Path,
    manifest_path: Path,
) -> None:
    site_rows = [
        [int(value) for value in line.split()]
        for line in site_map_path.read_text().splitlines() if line.strip()
    ]
    sites = len(site_rows)
    cpp_by_alf = [0] * sites
    for alf_one, cpp, _x, _y in site_rows:
        cpp_by_alf[alf_one - 1] = cpp
    wanted = {int(row["sample_id"]) for row in selected}
    records = {}
    index = json.loads(archive_index.read_text())
    for entry in index["entries"]:
        path = Path(entry["path"])
        if not path.is_absolute():
            path = (archive_index.parent / path).resolve()
        for record in ArchiveReader(path).records():
            if record.sample_id in wanted:
                records[record.sample_id] = record
    if set(records) != wanted:
        raise ValueError("selected trace samples are absent from archives")
    fields_dir.mkdir(parents=True, exist_ok=True)
    field_paths: dict[int, Path] = {}
    for sample_id, record in records.items():
        mapped = [-1] * len(record.fields)
        for index, field in enumerate(record.fields):
            slice_index, alf = divmod(index, sites)
            mapped[slice_index * sites + cpp_by_alf[alf]] = field
        path = fields_dir / f"{sample_id}.fields"
        path.write_text("\n".join(str(value) for value in mapped) + "\n")
        field_paths[sample_id] = path.resolve()
    log_means = {
        ensemble: _log_mean([
            float(row[
                "logabs_d_ii" if ensemble == "II" else "logabs_d_ti"
            ])
            for row in selected if row["ensemble"] == ensemble
        ])
        for ensemble in {row["ensemble"] for row in selected}
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow((
            "path_id", "role", "case_id", "config_id", "fields_file",
            "score", "log_d_over_mean", "weight_bin",
        ))
        for row in selected:
            sample_id = int(row["sample_id"])
            log_d = float(row[
                "logabs_d_ii" if row["ensemble"] == "II"
                else "logabs_d_ti"
            ])
            score = (
                float(row["prefix_barrier"]) if row["alive"]
                else float(row["first_rejection_slice"] or 0)
            )
            writer.writerow((
                f"{row['role']}_{row['case_id']}_{sample_id}",
                row["role"], row["case_id"], "",
                field_paths[sample_id], score,
                log_d - log_means[row["ensemble"]],
                f"E{row['energy_decile']}",
            ))


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
    parser.add_argument(
        "--fields-dir", type=Path, default=bridge / "replay/traces/fields",
    )
    parser.add_argument(
        "--manifest-output", type=Path,
        default=bridge / "replay/manifests/full_traces.csv",
    )
    parser.add_argument(
        "--selection-output", type=Path,
        default=bridge / "replay/manifests/full_trace_selection.json",
    )
    parser.add_argument("--seed", type=int, default=9137)
    parser.add_argument("--category-cap", type=int, default=5)
    args = parser.parse_args()
    with args.strata.open(newline="") as handle:
        source = list(csv.DictReader(handle))
    selected = select_cases_and_controls(
        source, seed=args.seed, category_cap=args.category_cap
    )
    write_trace_inputs(
        selected, args.archive_index, args.site_map,
        args.fields_dir, args.manifest_output,
    )
    args.selection_output.parent.mkdir(parents=True, exist_ok=True)
    args.selection_output.write_text(json.dumps({
        "schema_version": 1,
        "seed": args.seed,
        "category_cap": args.category_cap,
        "selected": [{
            "sample_id": row["sample_id"],
            "role": row["role"],
            "case_id": row["case_id"],
            "labels": row["selection_labels"],
            "ensemble": row["ensemble"],
            "chain": row["chain"],
            "chain_split": row["chain_split"],
            "energy_decile": row["energy_decile"],
        } for row in selected],
    }, indent=2, sort_keys=True) + "\n")
    print(
        f"selected {len(selected)} case/control trace paths",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
