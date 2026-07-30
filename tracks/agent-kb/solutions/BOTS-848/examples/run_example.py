#!/usr/bin/env python3
"""Run the two minimal channel-classification examples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
if str(SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLUTION_ROOT))

from src.channel_decomposition import channel_weights, decompose_operator
from src.decision_gate import select_correction_level


DEFAULT_CASES = (
    SOLUTION_ROOT / "examples" / "toy_common_shift.yaml",
    SOLUTION_ROOT / "examples" / "toy_orbital_splitting.yaml",
)


def run_case(path: Path) -> dict[str, object]:
    case = json.loads(path.read_text(encoding="utf-8"))
    channels = decompose_operator(case["operator"], case["site_blocks"])
    weights = channel_weights(channels)
    result = select_correction_level(weights, case["evidence"])
    dominant = max(weights, key=weights.get)
    passed = (
        dominant == case["expected_dominant_channel"]
        and result["decision"] == case["expected_decision"]
    )
    return {
        "name": case["name"],
        "weights": weights,
        "decision": result["decision"],
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="*", type=Path, help="JSON-compatible YAML case files")
    args = parser.parse_args()
    paths = args.cases or DEFAULT_CASES
    results = [run_case(path) for path in paths]
    for result in results:
        weights = ", ".join(f"{name}={value:.3f}" for name, value in result["weights"].items())
        print(f"{result['name']}: {weights}; decision={result['decision']}; passed={result['passed']}")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
