from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess two independent Jacobian batches at one frozen coupling point"
    )
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-standardized-difference", type=float, default=1.96)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    reports = [
        json.loads(path.resolve().read_text(encoding="utf-8"))
        for path in (args.left, args.right)
    ]
    if any(report.get("status") != "NUMERICALLY_STABLE" for report in reports):
        raise ValueError("both Jacobian reports must be NUMERICALLY_STABLE")
    if reports[0]["input"] != reports[1]["input"]:
        raise ValueError("pilot batches were not measured at the same frozen input")

    blocks: dict[str, object] = {}
    all_pass = True
    for parity in ("even", "odd"):
        left = reports[0][parity]
        right = reports[1][parity]
        difference = abs(
            float(left["leading_eigenvalue"])
            - float(right["leading_eigenvalue"])
        )
        combined_standard_error = math.sqrt(
            float(left["bootstrap"]["standard_error"]) ** 2
            + float(right["bootstrap"]["standard_error"]) ** 2
        )
        standardized = difference / combined_standard_error
        ci_low = max(
            float(left["bootstrap"]["ci95_low"]),
            float(right["bootstrap"]["ci95_low"]),
        )
        ci_high = min(
            float(left["bootstrap"]["ci95_high"]),
            float(right["bootstrap"]["ci95_high"]),
        )
        passed = (
            standardized <= args.maximum_standardized_difference
            and ci_low <= ci_high
        )
        all_pass = all_pass and passed
        blocks[parity] = {
            "left_eigenvalue": left["leading_eigenvalue"],
            "right_eigenvalue": right["leading_eigenvalue"],
            "absolute_difference": difference,
            "combined_bootstrap_standard_error": combined_standard_error,
            "standardized_difference": standardized,
            "maximum_standardized_difference": args.maximum_standardized_difference,
            "ci95_intersection": {
                "low": ci_low,
                "high": ci_high,
                "exists": ci_low <= ci_high,
            },
            "status": "PASS" if passed else "FAIL",
        }
    result = {
        "status": "PASS" if all_pass else "FAIL",
        "method": "two_independent_batches_same_frozen_coupling_and_bias",
        "scope": "diagnostic_pilot_not_formal_Table_I_result",
        "left": str(args.left.resolve()),
        "right": str(args.right.resolve()),
        "input": reports[0]["input"],
        "blocks": blocks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
