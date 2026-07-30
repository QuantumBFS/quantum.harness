"""Register the Phase 7 parallel dispatch from a passed Phase 6 v2 gate."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

from route_d_plus.finalize_phase6_v2 import (
    artifact,
    load_json,
    validate,
    write_json,
)
from route_d_plus.future.verify import validate_dispatch, validate_payload

MODULE_ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "challenge-15-route-d-plus-future-dependency-v1"
DISPATCH_VERSION = "challenge-15-route-d-plus-future-dispatch-v1"
REGISTRATION_VERSION = "challenge-15-route-d-plus-phase7-registration-v1"


def git_output(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def phase7_tasks() -> list[dict[str, Any]]:
    def label(m_sector: int) -> str:
        if m_sector < 0:
            return f"m-minus-{abs(m_sector)}"
        if m_sector > 0:
            return f"m-plus-{m_sector}"
        return "m-zero"

    tasks = [
        {
            "task_id": label(m),
            "kind": "ed-sector",
            "run_dir": f"tasks/{label(m)}",
            "required_gates": [
                "sector_energy",
                "sector_normalization",
                "symmetry_readback",
                "slurm_evidence",
            ],
            "n_electrons": 6,
            "m_sector": m,
        }
        for m in range(-2, 3)
    ]
    tasks.extend(
        [
            {
                "task_id": "overlap",
                "kind": "overlap",
                "run_dir": "tasks/overlap",
                "required_gates": [
                    "ground_overlap",
                    "tower_overlap",
                    "gap_comparison",
                    "slurm_evidence",
                ],
                "n_electrons": 6,
                "m_sector": None,
            },
            {
                "task_id": "span-ceiling",
                "kind": "span-ceiling",
                "run_dir": "tasks/span-ceiling",
                "required_gates": [
                    "ground_span_ceiling",
                    "tower_span_ceiling",
                    "slurm_evidence",
                ],
                "n_electrons": 6,
                "m_sector": None,
            },
        ]
    )
    return tasks


def register(
    *,
    repo_root: Path,
    final_path: Path,
    run_id: str,
    run_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    revision = git_output(repo_root, "rev-parse", "HEAD")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("Phase 7 registration requires a clean worktree")
    final = load_json(final_path)
    validate(final, MODULE_ROOT / "phase6-final-v2.schema.json")
    if (
        not final["passed"]
        or final["ed_accessed"]
        or not final["architecture_frozen"]
        or not final["checkpoints_frozen"]
        or final["source_revisions"]["finalizer"] != revision
    ):
        raise RuntimeError("Phase 6 v2 certificate is not a Phase 7 gate")

    output_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    dependency_path = output_dir / "phase6-frozen-dependency.json"
    dependency = {
        "schema_version": SCHEMA_VERSION,
        "kind": "phase6-frozen-checkpoint-gate",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "phase6_certificate": artifact(final_path),
        "checkpoints": [
            {
                "path": seed["checkpoint"]["path"],
                "sha256": seed["checkpoint"]["sha256"],
            }
            for seed in final["seed_artifacts"]
        ],
        "architecture_protocol": {
            "path": final["architecture_protocol"]["path"],
            "sha256": final["architecture_protocol"]["sha256"],
        },
        "capacity_protocol": {
            "path": final["capacity_protocol"]["path"],
            "sha256": final["capacity_protocol"]["sha256"],
        },
        "architecture_status": "D+0-frozen-for-Phase7",
        "ed_accessed": False,
        "heldout_accessed": False,
        "beyond_ed_accessed": False,
        "passed": True,
    }
    validate_payload(dependency, "dependency.schema.json")
    write_json(dependency_path, dependency)

    dispatch_path = output_dir / "phase7-dispatch.json"
    dispatch = {
        "schema_version": DISPATCH_VERSION,
        "stage": "phase7",
        "run_id": run_id,
        "run_root": str(run_root.resolve()),
        "source_revision": revision,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prerequisites": [
            {
                "kind": "phase6-frozen-checkpoint-gate",
                **artifact(dependency_path),
            }
        ],
        "tasks": phase7_tasks(),
    }
    validate_dispatch(dispatch)
    write_json(dispatch_path, dispatch)
    return {
        "schema_version": REGISTRATION_VERSION,
        "phase6_dependency": artifact(dependency_path),
        "phase7_dispatch": artifact(dispatch_path),
        "source_revision": revision,
        "exact_task_count": len(dispatch["tasks"]),
        "ed_accessed": False,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--phase6-final", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = register(
        repo_root=args.repo_root.resolve(),
        final_path=args.phase6_final.resolve(),
        run_id=args.run_id,
        run_root=args.run_root.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    validate(payload, MODULE_ROOT / "phase7-registration.schema.json")
    write_json(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
