#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


EXPECTED_METHODS = {
    "full_space_nelder_mead",
    "random_subspace_nelder_mead",
    "hessian_subspace_nelder_mead",
    "adaptive_hessian_subspace_nelder_mead",
    "device_informed_adaptive_hessian_nelder_mead",
}


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() and (candidate / "tracks").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root above {start}")


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def validate_fast_output(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    summary = json.loads((out_dir / "summary.json").read_text())
    if summary.get("records") != 10:
        raise RuntimeError(
            f"expected 10 records in summary.json, found {summary.get('records')}"
        )
    if summary.get("groups") != 10:
        raise RuntimeError(
            f"expected 10 groups in summary.json, found {summary.get('groups')}"
        )

    rows = _read_jsonl(out_dir / "runs.jsonl")
    if len(rows) != 10:
        raise RuntimeError(f"expected 10 rows in runs.jsonl, found {len(rows)}")
    splits = sorted({row["split"] for row in rows})
    if splits != ["dev", "holdout"]:
        raise RuntimeError(f"expected dev and holdout splits, found {splits}")
    variants = sorted({row["true_device_variant"] for row in rows})
    if variants != ["pulse_distortion"]:
        raise RuntimeError(f"expected pulse_distortion variant, found {variants}")
    methods = {row["method"] for row in rows}
    if methods != EXPECTED_METHODS:
        raise RuntimeError(
            "unexpected method set: "
            f"missing={sorted(EXPECTED_METHODS - methods)}, "
            f"extra={sorted(methods - EXPECTED_METHODS)}"
        )

    summary_path = (
        out_dir / "summary_tables" / "black_box_holdout_summary.csv"
    )
    with summary_path.open() as handle:
        summary_rows = list(csv.DictReader(handle))
    if len(summary_rows) != 10:
        raise RuntimeError(
            f"expected 10 summary-table rows, found {len(summary_rows)}"
        )

    figure = out_dir / "figures" / "black_box_holdout_success.png"
    skipped = out_dir / "figures" / "black_box_holdout_success.skipped.txt"
    if not figure.exists() and not skipped.exists():
        raise RuntimeError("expected success figure or plotting skip marker")

    return {
        "records": 10,
        "groups": 10,
        "splits": splits,
        "true_device_variants": variants,
    }


def _run_checked(command: list[str], repo_root: Path) -> None:
    try:
        subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            sys.stderr.write(exc.stdout)
        if exc.stderr:
            sys.stderr.write(exc.stderr)
        raise


def main() -> int:
    attempt_dir = Path(__file__).resolve().parent
    repo_root = _find_repo_root(attempt_dir)
    default_out = (
        repo_root
        / "tracks/qcs/results/YueYuan/attempt-004/submission_quick"
    )
    parser = argparse.ArgumentParser(
        description="Run the fast YueYuan challenge-submission verification."
    )
    parser.add_argument("--out", type=Path, default=default_out)
    args = parser.parse_args()
    out_dir = args.out if args.out.is_absolute() else repo_root / args.out

    black_box_tests = (
        repo_root
        / "tracks/qcs/solutions/YueYuan/research/attempt_tests/"
        "test_attempt_004_black_box_rigor.py"
    )
    validator = (
        repo_root
        / "tracks/qcs/solutions/YueYuan/research/validator/self_test.py"
    )
    holdout_runner = attempt_dir / "run_black_box_holdout.py"
    _run_checked(
        [sys.executable, "-m", "pytest", str(black_box_tests), "-q"],
        repo_root,
    )
    _run_checked([sys.executable, str(validator)], repo_root)
    _run_checked(
        [
            sys.executable,
            str(holdout_runner),
            "--out",
            str(out_dir),
            "--fast",
        ],
        repo_root,
    )
    print(json.dumps(validate_fast_output(out_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
