#!/usr/bin/env python3
"""Independent full-domain audit for issue-71 candidate netlists."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from circuit import Circuit, compare_truth_tables, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    reference = Circuit.parse(args.reference)
    candidate = Circuit.parse(args.candidate)
    audit = compare_truth_tables(reference, candidate)
    report = {
        "reference": str(args.reference),
        "candidate": str(args.candidate),
        "reference_sha256": sha256_file(args.reference),
        "candidate_sha256": sha256_file(args.candidate),
        "reference_gates": len(reference.gates),
        "candidate_gates": len(candidate.gates),
        "saved_gates": len(reference.gates) - len(candidate.gates),
        "truth_table": audit,
    }
    if not audit["equivalent"]:
        raise SystemExit(f"candidate is not equivalent: {report}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
