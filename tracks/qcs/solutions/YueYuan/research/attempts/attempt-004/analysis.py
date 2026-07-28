from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def aggregate(results_dir: Path) -> dict:
    rows = read_jsonl(Path(results_dir) / "runs.jsonl")
    groups = defaultdict(list)
    for row in rows:
        key = (
            row["system"],
            row["method"],
            row["mismatch"],
            row["shots_per_query"],
            row["k"],
        )
        groups[key].append(row)
    summaries = []
    for (system, method, mismatch, shots, k), items in sorted(groups.items()):
        queries = [item["queries_to_target"] for item in items if item["queries_to_target"] is not None]
        shots_to_target = [
            item["total_shots_to_target"] for item in items if item["total_shots_to_target"] is not None
        ]
        success_rate = sum(1 for item in items if item["success"]) / len(items)
        summaries.append(
            {
                "system": system,
                "method": method,
                "mismatch": mismatch,
                "shots_per_query": shots,
                "k": k,
                "n": len(items),
                "success_rate": success_rate,
                "median_queries_to_target": statistics.median(queries) if queries else None,
                "median_shots_to_target": statistics.median(shots_to_target) if shots_to_target else None,
                "median_final_infidelity": statistics.median(
                    [item["final_infidelity"] for item in items]
                ),
            }
        )
    return {"rows": len(rows), "groups": summaries}


def write_summary(results_dir: Path) -> dict:
    summary = aggregate(results_dir)
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    (Path(results_dir) / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary
