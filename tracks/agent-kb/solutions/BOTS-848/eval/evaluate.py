#!/usr/bin/env python3
"""Deterministic evaluation for the BOTS:848 research-agent contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
if str(SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLUTION_ROOT))

from src.decision_gate import select_correction_level


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _bibliography_keys() -> set[str]:
    text = (SOLUTION_ROOT / "knowledge" / "references.bib").read_text(encoding="utf-8")
    return set(re.findall(r"@[A-Za-z]+\{([^,]+),", text))


def run_evaluation() -> dict[str, object]:
    cases = _load_json(SOLUTION_ROOT / "eval" / "cases.yaml")["cases"]
    bibliography = _bibliography_keys()
    details = []
    decision_total = decision_correct = 0
    claim_total = claim_correct = 0
    citation_required = citation_grounded = 0
    unsupported_assertions = 0

    for case in cases:
        if case["kind"] == "decision":
            decision_total += 1
            actual = select_correction_level(case["weights"], case["evidence"])["decision"]
            passed = actual == case["expected_decision"]
            decision_correct += int(passed)
            details.append({"case_id": case["case_id"], "passed": passed, "actual": actual})
            continue

        if case["kind"] != "claim":
            raise ValueError(f"unknown evaluation kind: {case['kind']}")
        claim_total += 1
        status_ok = case["candidate_status"] == case["expected_status"]
        citation_ok = True
        if case["citation_required"]:
            citation_required += 1
            source_ids = set(case["candidate_source_ids"])
            citation_ok = bool(source_ids) and source_ids.issubset(bibliography)
            citation_grounded += int(citation_ok)
        unsupported = case["asserted_as_fact"] and not case["supported"]
        unsupported_assertions += int(unsupported)
        passed = status_ok and citation_ok and not unsupported
        claim_correct += int(passed)
        details.append(
            {
                "case_id": case["case_id"],
                "passed": passed,
                "actual": case["candidate_status"],
            }
        )

    passed = sum(int(item["passed"]) for item in details)
    return {
        "passed": passed,
        "total": len(details),
        "metrics": {
            "decision_accuracy": decision_correct / decision_total,
            "claim_status_accuracy": claim_correct / claim_total,
            "citation_coverage": citation_grounded / citation_required,
            "unsupported_claim_rate": unsupported_assertions / claim_total,
        },
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the complete JSON result")
    args = parser.parse_args()
    result = run_evaluation()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"BOTS:848 evaluation: {result['passed']}/{result['total']} cases passed")
        for name, value in result["metrics"].items():
            print(f"{name}: {value:.3f}")
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
