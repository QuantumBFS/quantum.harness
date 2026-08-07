#!/usr/bin/env python3
"""Compare two robustness runs at the scientific-data level.

Generated artifacts are not expected to be byte-identical across JAX/XLA
hosts. This standard-library comparator checks table schemas, categorical
fields, row counts, and every numerical field within declared tolerances.
Host environment, compilation timing, and rendering metadata are excluded.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


CSV_PATHS = [
    "data/channel_decomposition.csv",
    "data/core_scan.csv",
    "data/hamiltonian_error_scan.csv",
    "data/noise_scan.csv",
    "data/pathology_scan.csv",
    "data/subspace_rotation.csv",
]

BASELINE_KEYS = [
    "accepted",
    "baseline_infidelity",
    "leakage_01",
    "leakage_11",
    "controlled_phase",
    "phase_error_to_pi",
    "active_rank",
    "largest_eigenvalue",
    "sixth_to_first_eigenvalue",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def finite_float(value: str) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


class Comparison:
    def __init__(self, relative_tolerance: float, absolute_tolerance: float):
        self.rtol = relative_tolerance
        self.atol = absolute_tolerance
        self.mismatches: list[str] = []
        self.numeric_comparisons = 0
        self.categorical_comparisons = 0
        self.maximum_absolute_difference = 0.0
        self.maximum_relative_difference = 0.0
        self.maximum_tolerance_ratio = 0.0

    def mismatch(self, message: str) -> None:
        if len(self.mismatches) < 100:
            self.mismatches.append(message)

    def compare_scalar(self, label: str, reference: Any, candidate: Any) -> None:
        if (
            isinstance(reference, (int, float))
            and not isinstance(reference, bool)
            and isinstance(candidate, (int, float))
            and not isinstance(candidate, bool)
        ):
            self.compare_number(label, float(reference), float(candidate))
            return
        self.categorical_comparisons += 1
        if reference != candidate:
            self.mismatch(
                f"{label}: categorical mismatch "
                f"{reference!r} != {candidate!r}"
            )

    def compare_number(
        self, label: str, reference: float, candidate: float
    ) -> None:
        self.numeric_comparisons += 1
        if not (math.isfinite(reference) and math.isfinite(candidate)):
            self.mismatch(f"{label}: non-finite numerical value")
            return
        absolute = abs(candidate - reference)
        scale = max(abs(reference), abs(candidate))
        relative = absolute / scale if scale > 0.0 else 0.0
        allowed = self.atol + self.rtol * scale
        tolerance_ratio = absolute / allowed if allowed > 0.0 else 0.0
        self.maximum_absolute_difference = max(
            self.maximum_absolute_difference, absolute
        )
        self.maximum_relative_difference = max(
            self.maximum_relative_difference, relative
        )
        self.maximum_tolerance_ratio = max(
            self.maximum_tolerance_ratio, tolerance_ratio
        )
        if not math.isclose(
            reference,
            candidate,
            rel_tol=self.rtol,
            abs_tol=self.atol,
        ):
            self.mismatch(
                f"{label}: {reference:.17g} != {candidate:.17g}; "
                f"abs={absolute:.3e}, rel={relative:.3e}"
            )

    def compare_tree(self, label: str, reference: Any, candidate: Any) -> None:
        if isinstance(reference, dict):
            if not isinstance(candidate, dict):
                self.mismatch(f"{label}: candidate is not an object")
                return
            missing = sorted(set(reference) - set(candidate))
            if missing:
                self.mismatch(f"{label}: missing keys {missing}")
            for key in sorted(set(reference) & set(candidate)):
                self.compare_tree(
                    f"{label}.{key}", reference[key], candidate[key]
                )
            return
        if isinstance(reference, list):
            if not isinstance(candidate, list):
                self.mismatch(f"{label}: candidate is not a list")
                return
            if len(reference) != len(candidate):
                self.mismatch(
                    f"{label}: list length {len(reference)} != "
                    f"{len(candidate)}"
                )
            for index, (left, right) in enumerate(
                zip(reference, candidate, strict=False)
            ):
                self.compare_tree(f"{label}[{index}]", left, right)
            return
        self.compare_scalar(label, reference, candidate)

    def compare_csv(
        self,
        relative_path: str,
        reference_root: Path,
        candidate_root: Path,
    ) -> None:
        reference_header, reference_rows = load_csv(
            reference_root / relative_path
        )
        candidate_header, candidate_rows = load_csv(
            candidate_root / relative_path
        )
        if reference_header != candidate_header:
            self.mismatch(
                f"{relative_path}: headers differ "
                f"{reference_header!r} != {candidate_header!r}"
            )
            return
        if len(reference_rows) != len(candidate_rows):
            self.mismatch(
                f"{relative_path}: row count {len(reference_rows)} != "
                f"{len(candidate_rows)}"
            )
        for row_index, (reference_row, candidate_row) in enumerate(
            zip(reference_rows, candidate_rows, strict=False), start=1
        ):
            for column in reference_header:
                left = reference_row[column]
                right = candidate_row[column]
                left_number = finite_float(left)
                right_number = finite_float(right)
                label = f"{relative_path}:row={row_index}:{column}"
                if left_number is not None and right_number is not None:
                    self.compare_number(label, left_number, right_number)
                else:
                    self.compare_scalar(label, left, right)


def scientific_summary(summary: dict[str, Any]) -> dict[str, Any]:
    baseline = summary.get("baseline", {})
    return {
        "status": summary.get("status"),
        "baseline": {key: baseline.get(key) for key in BASELINE_KEYS},
        "scope": summary.get("scope"),
        "boundary": summary.get("boundary"),
        "pathologies": summary.get("pathologies"),
        "figures": summary.get("figures"),
    }


def compare_runs(
    reference_root: Path,
    candidate_root: Path,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    comparison = Comparison(relative_tolerance, absolute_tolerance)
    comparison.compare_tree(
        "summary",
        scientific_summary(load_json(reference_root / "summary.json")),
        scientific_summary(load_json(candidate_root / "summary.json")),
    )
    comparison.compare_tree(
        "baseline",
        {key: load_json(reference_root / "data/baseline.json").get(key)
         for key in BASELINE_KEYS},
        {key: load_json(candidate_root / "data/baseline.json").get(key)
         for key in BASELINE_KEYS},
    )
    for relative_path in CSV_PATHS:
        comparison.compare_csv(
            relative_path, reference_root, candidate_root
        )
    return {
        "status": "pass" if not comparison.mismatches else "fail",
        "relative_tolerance": relative_tolerance,
        "absolute_tolerance": absolute_tolerance,
        "numeric_comparisons": comparison.numeric_comparisons,
        "categorical_comparisons": comparison.categorical_comparisons,
        "maximum_absolute_difference": (
            comparison.maximum_absolute_difference
        ),
        "maximum_relative_difference": (
            comparison.maximum_relative_difference
        ),
        "maximum_tolerance_ratio": comparison.maximum_tolerance_ratio,
        "mismatch_count": len(comparison.mismatches),
        "mismatches": comparison.mismatches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--relative-tolerance", type=float, default=1e-8)
    parser.add_argument("--absolute-tolerance", type=float, default=1e-10)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.relative_tolerance < 0 or args.absolute_tolerance < 0:
        parser.error("tolerances must be non-negative")
    reference_root = args.reference_dir.expanduser().resolve()
    candidate_root = args.candidate_dir.expanduser().resolve()
    if not reference_root.is_dir():
        parser.error(f"reference directory does not exist: {reference_root}")
    if not candidate_root.is_dir():
        parser.error(f"candidate directory does not exist: {candidate_root}")

    result = compare_runs(
        reference_root,
        candidate_root,
        args.relative_tolerance,
        args.absolute_tolerance,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(payload, end="")
    if args.json_out is not None:
        output = args.json_out.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8", newline="\n")
    raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
