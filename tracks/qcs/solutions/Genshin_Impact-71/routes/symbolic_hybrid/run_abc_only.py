#!/usr/bin/env python3
"""Run native ABC EXDC and exact semantic/ROBDD hybrid flows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import routes
from run_experiments import abc_map, abc_map_incomplete, convert_and_audit


def run_one(name: str, work: Path, abc: Path) -> dict[str, object]:
    directory = work / name
    discovery = directory / "discovery.json"

    incomplete_blif = directory / "abc-incomplete-k2.blif"
    abc_map_incomplete(
        abc,
        directory / "train-incomplete-exdc.blif",
        incomplete_blif,
        directory / "abc-incomplete.log",
    )
    incomplete_audit = convert_and_audit(
        discovery,
        incomplete_blif,
        directory / "abc-incomplete.txt",
        directory / "abc-incomplete-audit.json",
        require_exact=False,
    )

    bdd_metrics = json.loads(
        (directory / "bdd-metrics.json").read_text(encoding="utf-8")
    )
    candidates: list[dict[str, object]] = []
    for order_name, order_data in sorted(bdd_metrics["orders"].items()):
        mapped = directory / f"hybrid-bdd-{order_name}-k2.blif"
        challenge = directory / f"hybrid-bdd-{order_name}.txt"
        audit_path = directory / f"hybrid-bdd-{order_name}-audit.json"
        abc_map(
            abc,
            Path(order_data["blif_path"]),
            mapped,
            directory / f"abc-bdd-{order_name}.log",
        )
        audit = convert_and_audit(
            discovery, mapped, challenge, audit_path, require_exact=True
        )
        candidates.append(
            {
                "route": f"bdd-{order_name}",
                "source_nodes": order_data["nonterminal_nodes"],
                "mapped_blif": str(mapped),
                "challenge": str(challenge),
                "audit": str(audit_path),
                "gates": audit["gates"],
            }
        )

    semantic_mapped = directory / "hybrid-semantic-full-k2.blif"
    semantic_challenge = directory / "hybrid-semantic-full.txt"
    semantic_audit_path = directory / "hybrid-semantic-full-audit.json"
    abc_map(
        abc,
        directory / "semantic-full.pla",
        semantic_mapped,
        directory / "abc-semantic-full.log",
    )
    semantic_audit = convert_and_audit(
        discovery,
        semantic_mapped,
        semantic_challenge,
        semantic_audit_path,
        require_exact=True,
    )
    candidates.append(
        {
            "route": "semantic-full",
            "source_nodes": None,
            "mapped_blif": str(semantic_mapped),
            "challenge": str(semantic_challenge),
            "audit": str(semantic_audit_path),
            "gates": semantic_audit["gates"],
        }
    )

    best = min(candidates, key=lambda item: (item["gates"], item["route"]))
    best_path = directory / "hybrid-best.txt"
    shutil.copyfile(str(best["challenge"]), best_path)
    result = {
        "instance": name,
        "abc_incomplete": incomplete_audit,
        "exact_candidates": candidates,
        "best": {**best, "copied_challenge": str(best_path)},
    }
    routes.atomic_json(directory / "abc-flow-summary.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--abc", required=True)
    args = parser.parse_args()
    work = Path(args.work).resolve()
    abc = Path(args.abc).resolve()
    if not os.access(abc, os.X_OK):
        raise ValueError(f"ABC executable missing: {abc}")
    version = subprocess.run(
        (str(abc), "-c", "version; quit"),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    ).stdout
    summary: dict[str, object] = {
        "schema": "occam71-native-abc-and-hybrid-v1",
        "root_seed": routes.ROOT_SEED,
        "abc": str(abc),
        "abc_sha256": routes.sha256_file(abc),
        "abc_version_output": version,
        "instances": {},
    }
    for name in routes.INSTANCE_NAMES:
        summary["instances"][name] = run_one(name, work, abc)
    routes.atomic_json(work / "abc-flow-summary.json", summary)
    (work / "ABC_FLOW_COMPLETE").write_text(
        "success\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
