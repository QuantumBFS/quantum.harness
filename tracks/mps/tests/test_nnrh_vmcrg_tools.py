import json
import subprocess
import sys
from pathlib import Path


TRACK_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = TRACK_ROOT / "skills" / "nnrh-vmcrg"


def run_script(name: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKILL_ROOT / "scripts" / name), *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_final_status_validator_rejects_false_easy_goal_success(tmp_path: Path) -> None:
    status = {
        "project_name": "Neural-Network Renormalized Hamiltonians for VMCRG",
        "acronym": "NNRH-VMCRG",
        "slug": "nnrh-vmcrg",
        "challenge_issue": 28,
        "pull_request": 154,
        "track": "mps",
        "team": "LULU",
        "reproduction_status": "REPRODUCTION_COMPLETE",
        "easy_goal_status": "EASY_GOAL_SUCCESS",
        "mps_tt_support_status": "SUPPORTING_EVIDENCE",
        "hard_goal_status": "STAGE_6_NO_GO",
        "completed_gates": [],
        "failed_gates": ["easy_goal.validation"],
        "not_executed_gates": [],
        "primary_evidence": [],
        "supporting_evidence": [],
        "missing_work": [],
        "random_seeds": [],
        "configs": [],
        "result_paths": [],
        "scientific_claims_allowed": [],
        "scientific_claims_forbidden": [],
        "engineering_tests": {},
        "cleanup_summary": {},
        "resource_summary": {},
        "submission_status": "PREPARED",
        "git_branch": "branch",
        "git_head": "0" * 40,
        "generated_at": "2026-07-30T00:00:00+08:00",
    }
    path = tmp_path / "final_status.json"
    path.write_text(json.dumps(status), encoding="utf-8")

    result = run_script("validate_final_status.py", path)

    assert result.returncode != 0
    assert "EASY_GOAL_SUCCESS" in result.stderr


def test_track_local_skill_and_references_validate() -> None:
    skill = run_script("validate_skill.py", SKILL_ROOT)
    references = run_script(
        "check_references.py",
        TRACK_ROOT,
        TRACK_ROOT / "NNRH-VMCRG.md",
    )

    assert skill.returncode == 0, skill.stdout + skill.stderr
    assert references.returncode == 0, references.stdout + references.stderr
