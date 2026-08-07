#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sandbox import run_candidate_if_needed
from schema import (
    environment_report,
    error,
    extract_runs,
    load_json,
    make_report,
    scan_forbidden_sources,
    validate_run_shape,
    write_report,
)
from scoring import evaluate_submission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate YueYuan challenge #113 candidates.")
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--precheck", action="store_true", help="run free structural checks only")
    parser.add_argument("--instances", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)

    out = args.out or args.candidate_dir / "report.json"
    env = environment_report(args.instances, args.timeout_seconds)

    try:
        instance_payload, infra_errors = _load_instances(args.instances)
        if infra_errors:
            return _finish(out, "infra_error", None, {}, infra_errors, env, 2)

        source_errors = scan_forbidden_sources(args.candidate_dir)
        if source_errors:
            return _finish(out, "rejected", None, {}, source_errors, env, 1)

        if args.precheck:
            return _precheck(args.candidate_dir, out, env)

        runner_errors = run_candidate_if_needed(args.candidate_dir, args.timeout_seconds)
        if runner_errors:
            return _finish(out, "rejected", None, {}, runner_errors, env, 1)

        payload, load_errors = load_json(args.candidate_dir / "submission.json")
        if load_errors or payload is None:
            return _finish(out, "rejected", None, {}, load_errors, env, 1)

        if args.instances == "holdout":
            budget_errors = _record_holdout_query()
            if budget_errors:
                return _finish(out, "rejected", None, {}, budget_errors, env, 1)

        score, per_instance, errors = evaluate_submission(payload, instance_payload)
        status = "accepted" if not errors else "rejected"
        code = 0 if not errors else 1
        return _finish(out, status, score, per_instance, errors, env, code)
    except Exception as exc:  # pragma: no cover - last-resort contract guard
        return _finish(
            out,
            "infra_error",
            None,
            {},
            [error("validator_exception", "validator crashed", detail=repr(exc))],
            env,
            2,
        )


def _precheck(candidate_dir: Path, out: Path, env: dict) -> int:
    submission = candidate_dir / "submission.json"
    runner = candidate_dir / "run_candidate.py"
    if not submission.exists() and not runner.exists():
        return _finish(
            out,
            "rejected",
            None,
            {},
            [error("missing_submission", "candidate must provide submission.json or run_candidate.py")],
            env,
            1,
        )
    if submission.exists():
        payload, load_errors = load_json(submission)
        if load_errors or payload is None:
            return _finish(out, "rejected", None, {}, load_errors, env, 1)
        runs, schema_errors = extract_runs(payload)
        schema_errors.extend(validate_run_shape(runs))
        if schema_errors:
            return _finish(out, "rejected", None, {}, schema_errors, env, 1)
    return _finish(out, "precheck_passed", None, {}, [], env, 0)


def _load_instances(instances: str) -> tuple[dict | None, list[dict]]:
    split = "private" if instances == "holdout" else "dev"
    path = ROOT.parent / "benchmark" / split / "instances.json"
    payload, errors = load_json(path)
    return payload, errors


def _record_holdout_query() -> list[dict]:
    manifest = ROOT / "MANIFEST.json"
    if not manifest.exists():
        return [error("missing_manifest", "holdout budget manifest is missing")]
    try:
        payload = json.loads(manifest.read_text())
    except json.JSONDecodeError as exc:
        return [error("invalid_manifest", "holdout budget manifest is invalid", detail=str(exc))]
    budget = int(payload.get("holdout_query_budget", 0))
    used = int(payload.get("holdout_queries_used", 0))
    if used >= budget:
        return [
            error(
                "holdout_budget_exhausted",
                "holdout query budget is exhausted",
                holdout_query_budget=budget,
                holdout_queries_used=used,
            )
        ]
    payload["holdout_queries_used"] = used + 1
    payload.setdefault("holdout_query_log", []).append(
        {"query_index": used + 1, "note": "aggregate validator invocation"}
    )
    manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return []


def _finish(
    out: Path,
    status: str,
    score: float | None,
    per_instance: dict,
    errors: list[dict],
    env: dict,
    exit_code: int,
) -> int:
    write_report(out, make_report(status, score, per_instance, errors, env))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
