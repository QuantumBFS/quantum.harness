#!/usr/bin/env python3
"""Audit an acyclic, functional-boundary ranked SAT window array."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} does not contain a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ranking", type=Path, required=True)
    parser.add_argument("--expected", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    ranking = load_json(args.ranking)
    safety = ranking["safety"]
    assert isinstance(safety, dict)
    assert safety["acyclic_boundary"] is True
    assert safety["boundary_excludes_root_descendants"] is True
    assert safety["roots_functional_of_boundary"] is True
    records = ranking["records"]
    assert isinstance(records, list)
    records = records[: args.expected]
    if len(records) != args.expected:
        raise RuntimeError(
            f"ranking has {len(records)} records, expected {args.expected}"
        )

    candidate_filename = Path(str(ranking["netlist"])).stem + ".candidate.txt"
    cells: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    missing: list[int] = []
    malformed: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []

    for index, ranked_untyped in enumerate(records):
        assert isinstance(ranked_untyped, dict)
        ranked = ranked_untyped
        roots = [str(root) for root in ranked["roots"]]
        gates = int(ranked["candidate_gates"])
        expected_name = f"{index:03d}_{roots[0]}_{roots[1]}_k{gates}"
        cell = args.root / expected_name
        report_path = cell / "report.json"
        if not report_path.is_file():
            missing.append(index)
            continue
        try:
            report = load_json(report_path)
            if list(report["roots"]) != roots:
                raise ValueError("roots disagree with frozen ranking")
            if int(report["requested_gate_count"]) != gates:
                raise ValueError("gate count disagrees with frozen ranking")
            if int(report["removed_gate_count"]) != int(ranked["removed_count"]):
                raise ValueError("removed count disagrees with frozen ranking")
            status = str(report["status"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            malformed.append({"index": index, "error": str(exc)})
            continue

        status_counts[status] += 1
        entry: dict[str, object] = {
            "index": index,
            "cell": expected_name,
            "roots": roots,
            "removed_gate_count": int(report["removed_gate_count"]),
            "requested_gate_count": gates,
            "boundary": list(report["boundary"]),
            "reachable_patterns": int(report["reachable_patterns"]),
            "status": status,
            "solve_seconds": float(report["solve_seconds"]),
            "conflicts": int(report["solver_stats"]["conflicts"]),
            "report_sha256": sha256(report_path),
        }

        candidate_path = cell / candidate_filename
        audit_path = cell / "independent-full-domain-audit.json"
        formula_path = cell / "direct-formula-audit.json"
        if candidate_path.is_file():
            entry["candidate_sha256"] = sha256(candidate_path)
            if not audit_path.is_file():
                entry["audit_error"] = "candidate exists without independent audit"
            else:
                entry["audit_sha256"] = sha256(audit_path)
                entry["audit"] = load_json(audit_path)
            if formula_path.is_file():
                entry["formula_audit_sha256"] = sha256(formula_path)
                entry["formula_audit"] = load_json(formula_path)
            candidates.append(entry)
        cells.append(entry)

    payload = {
        "ranking": str(args.ranking),
        "ranking_sha256": sha256(args.ranking),
        "candidate_filename": candidate_filename,
        "expected_cells": args.expected,
        "completed_reports": len(cells),
        "missing_indices": missing,
        "malformed": malformed,
        "status_counts": dict(sorted(status_counts.items())),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "cells": cells,
        "complete": (
            len(cells) == args.expected
            and not missing
            and not malformed
            and sum(status_counts.values()) == args.expected
        ),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "complete": payload["complete"],
                "status_counts": payload["status_counts"],
                "candidate_count": payload["candidate_count"],
                "output": str(args.output),
                "output_sha256": sha256(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
