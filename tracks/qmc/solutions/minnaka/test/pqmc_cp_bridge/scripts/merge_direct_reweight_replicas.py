#!/usr/bin/env python3
"""Strictly merge completed direct-reweighting production replicas."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from archive_runs import write_archive_index
from direct_reweight_statistics import write_products
from prepare_alf_chain import atomic_json
from run_direct_reweight_replica import validate_archive_entries


def merge_replica_rows(
    replica_rows: Sequence[Sequence[Mapping[str, str]]],
    *,
    replicas: int,
    chains_per_replica: int,
    paths_per_chain: int,
) -> list[dict[str, str]]:
    if len(replica_rows) != replicas:
        raise RuntimeError("replica summary count differs from request")
    merged: list[dict[str, str]] = []
    sample_ids: set[int] = set()
    for replica, rows in enumerate(replica_rows):
        expected_rows = chains_per_replica * paths_per_chain
        if len(rows) != expected_rows:
            raise RuntimeError(
                f"replica {replica} replay row count differs from "
                f"{expected_rows}"
            )
        first = replica * chains_per_replica
        expected_chains = set(range(first, first + chains_per_replica))
        found_chains = {int(row["chain"]) for row in rows}
        if found_chains != expected_chains:
            raise RuntimeError(f"replica {replica} chain range is incomplete")
        for chain in sorted(found_chains):
            chain_rows = [row for row in rows if int(row["chain"]) == chain]
            sweeps = [int(row["sweep"]) for row in chain_rows]
            if (
                len(chain_rows) != paths_per_chain
                or len(sweeps) != len(set(sweeps))
            ):
                raise RuntimeError(
                    f"replica {replica} chain {chain} path count is incomplete"
                )
        for row in rows:
            sample_id = int(row["sample_id"])
            if sample_id in sample_ids:
                raise RuntimeError("duplicate sample ID across replicas")
            sample_ids.add(sample_id)
            merged.append(dict(row))
    merged.sort(key=lambda row: int(row["sample_id"]))
    return merged


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


def merge_green_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_chains: int,
) -> dict[str, object]:
    chains = sorted(int(row["chain"]) for row in rows)
    if chains != list(range(expected_chains)):
        raise RuntimeError("Green diagnostics do not cover all global chains")
    values = [float(row["max_delta_g"]) for row in rows]
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError("Green diagnostics contain non-finite values")
    failed = [
        int(row["chain"])
        for row in rows
        if float(row["max_delta_g"]) > 1.0e-8
    ]
    return {
        "chains": expected_chains,
        "maximum_delta_g": max(values),
        "median_delta_g": _percentile(values, 0.5),
        "p95_delta_g": _percentile(values, 0.95),
        "failed_chains": failed,
        "alf_green_stability_pass": not failed,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"cannot write empty merged file: {path.name}")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_chinese_report(path: Path, summary: Mapping[str, object]) -> None:
    statistical = summary["direct_reweight_statistical_precision_pass"]
    green = summary["green_stability_pass"]
    path.write_text(
        "# 4×4 半满 Hubbard 模型直接路径重加权结果\n\n"
        f"- 路径数：{summary['paths']}（"
        f"{summary['chains']} 条独立链 × "
        f"{summary['paths_per_chain']} 条/链）\n"
        f"- 直接重加权能量："
        f"{float(summary['energy_cross_chain_bin_mean']):.10f} ± "
        f"{float(summary['energy_error_cross_chain_bins']):.10f}\n"
        f"- 全局分子/分母比值："
        f"{float(summary['energy_global_ratio']):.10f}\n"
        f"- 有效样本量：{float(summary['effective_sample_size']):.3f}\n"
        f"- statistical_precision_pass：{str(statistical).lower()}\n"
        f"- green_stability_pass：{str(green).lower()}\n\n"
        "主结果为直接重加权，不包含控制变量修正。误差棒来自 50 个"
        "跨链同编号汇总 bin；留一链 jackknife 仅作链间一致性诊断。\n"
    )


def merge_production(
    production_root: Path,
    *,
    replicas: int = 10,
    chains_per_replica: int = 192,
    paths_per_chain: int = 50,
    target_error: float = 0.01,
) -> dict[str, object]:
    all_entries: list[dict[str, object]] = []
    summaries: list[list[dict[str, str]]] = []
    green_rows: list[dict[str, str]] = []
    replica_replay_pass = True
    for replica in range(replicas):
        root = production_root / "replicas" / f"replica_{replica:03d}"
        status_path = root / "replica_status.json"
        if not status_path.is_file():
            raise RuntimeError(f"replica {replica} has no completion status")
        status = json.loads(status_path.read_text())
        if status.get("status") != "complete":
            raise RuntimeError(f"replica {replica} is not complete")
        offset = replica * chains_per_replica
        if (
            int(status.get("chain_offset", -1)) != offset
            or int(status.get("chains", -1)) != chains_per_replica
            or int(status.get("paths_per_chain", -1)) != paths_per_chain
        ):
            raise RuntimeError(f"replica {replica} contract mismatch")
        index = json.loads(Path(status["archive_index"]).read_text())
        entries = index.get("entries", [])
        validate_archive_entries(
            entries,
            chain_offset=offset,
            chains=chains_per_replica,
            paths_per_chain=paths_per_chain,
        )
        all_entries.extend(entries)
        summaries.append(_read_csv(Path(status["replay_summary"])))
        green_rows.extend(_read_csv(Path(status["green_stability_csv"])))
        replica_replay_pass = (
            replica_replay_pass
            and bool(status.get("replay_stability_pass", False))
        )

    merged_rows = merge_replica_rows(
        summaries,
        replicas=replicas,
        chains_per_replica=chains_per_replica,
        paths_per_chain=paths_per_chain,
    )
    expected_chains = replicas * chains_per_replica
    if expected_chains > 2048:
        raise RuntimeError("merged global chain range exceeds archive contract")
    results = production_root / "results"
    results.mkdir(parents=True, exist_ok=True)
    merged_summary_path = results / "replay_summary_s5.csv"
    _write_csv(merged_summary_path, merged_rows)
    green_rows.sort(key=lambda row: int(row["chain"]))
    _write_csv(results / "green_stability.csv", green_rows)
    green = merge_green_rows(green_rows, expected_chains=expected_chains)
    green["replay_stability_pass"] = replica_replay_pass
    green["green_stability_pass"] = (
        bool(green["alf_green_stability_pass"]) and replica_replay_pass
    )
    atomic_json(results / "green_stability.json", green)

    archive_index = production_root / "archive_index.json"
    write_archive_index(
        archive_index,
        all_entries,
        phase="direct_reweight",
        replicas=replicas,
        chains=expected_chains,
        paths_per_chain=paths_per_chain,
        records=expected_chains * paths_per_chain,
        sample_id_layout="chain11_sequence49",
    )
    summary = write_products(
        merged_rows,
        results,
        expected_chains=expected_chains,
        paths_per_chain=paths_per_chain,
        target_error=target_error,
        green_stability_pass=bool(green["green_stability_pass"]),
    )
    summary["archive_index"] = str(archive_index.resolve())
    summary["replay_summary"] = str(merged_summary_path.resolve())
    atomic_json(results / "direct_reweight_summary.json", summary)
    _write_chinese_report(results / "DIRECT_REWEIGHT_RESULTS_CN.md", summary)
    atomic_json(production_root / "merge_status.json", {
        "schema_version": 1,
        "status": "complete",
        "paths": expected_chains * paths_per_chain,
        "direct_reweight_statistical_precision_pass": summary[
            "direct_reweight_statistical_precision_pass"
        ],
        "green_stability_pass": summary["green_stability_pass"],
        "summary": str(
            (results / "direct_reweight_summary.json").resolve()
        ),
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-root", type=Path, required=True)
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument("--chains-per-replica", type=int, default=192)
    parser.add_argument("--paths-per-chain", type=int, default=50)
    parser.add_argument("--target-error", type=float, default=0.01)
    args = parser.parse_args()
    result = merge_production(
        args.production_root,
        replicas=args.replicas,
        chains_per_replica=args.chains_per_replica,
        paths_per_chain=args.paths_per_chain,
        target_error=args.target_error,
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
