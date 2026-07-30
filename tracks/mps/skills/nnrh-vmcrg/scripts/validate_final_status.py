#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REQUIRED = {
    "project_name", "acronym", "slug", "challenge_issue", "pull_request",
    "track", "team", "git_branch", "git_head", "generated_at",
    "reproduction_status", "easy_goal_status", "mps_tt_support_status",
    "hard_goal_status", "completed_gates", "failed_gates",
    "not_executed_gates", "primary_evidence", "supporting_evidence",
    "missing_work", "random_seeds", "configs", "result_paths",
    "scientific_claims_allowed", "scientific_claims_forbidden",
    "engineering_tests", "cleanup_summary", "resource_summary",
    "submission_status",
}
EASY = {"EASY_GOAL_SUCCESS", "PROTOCOL_INCOMPLETE", "OPTIMIZATION_NOT_CONVERGED", "VALIDATION_FAILED", "RESOURCE_LIMITED_INCOMPLETE", "SCIENTIFIC_NEGATIVE"}

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    missing = sorted(REQUIRED - data.keys())
    if missing:
        fail(f"missing required fields: {', '.join(missing)}")
    if data["easy_goal_status"] not in EASY:
        fail(f"invalid easy_goal_status: {data['easy_goal_status']}")
    if data["easy_goal_status"] == "EASY_GOAL_SUCCESS" and (data["failed_gates"] or data["not_executed_gates"]):
        fail("EASY_GOAL_SUCCESS is incompatible with failed or unexecuted gates")
    if data["hard_goal_status"] == "HARD_GOAL_SUCCESS" and (data["failed_gates"] or data["not_executed_gates"]):
        fail("HARD_GOAL_SUCCESS is incompatible with failed or unexecuted gates")
    if len(data["git_head"]) != 40:
        fail("git_head must be a full 40-character SHA")
    print("final_status validation PASS")

if __name__ == "__main__":
    main()
