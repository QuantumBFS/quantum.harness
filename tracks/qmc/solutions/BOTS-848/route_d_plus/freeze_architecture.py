"""Freeze D+0 only after Phase 6 and remediated Phase 7 both pass."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

from route_d_plus.future.verify import (
    load_json,
    require_artifact,
    sha256_file,
    validate_dependency,
    validate_dispatch,
    validate_payload,
)


def artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def freeze(
    *,
    repo_root: Path,
    phase6_final_path: Path,
    phase6_readback_path: Path,
    phase7_dispatch_path: Path,
    phase7_stage_gate_path: Path,
    phase7_aggregate_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    revision = git_output(repo_root, "rev-parse", "HEAD")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("architecture freeze requires a clean checkout")
    phase6_final = load_json(phase6_final_path)
    validate_payload(phase6_final, "../phase6-final-v2.schema.json")
    phase6_readback = load_json(phase6_readback_path)
    validate_payload(
        phase6_readback, "../phase6-final-v2-readback.schema.json"
    )
    if (
        not phase6_final["passed"]
        or not phase6_readback["passed"]
        or phase6_readback["final_certificate"]["sha256"]
        != sha256_file(phase6_final_path)
    ):
        raise RuntimeError("Phase 6 final/readback gate did not pass")

    dispatch = load_json(phase7_dispatch_path)
    validate_dispatch(dispatch)
    if dispatch["source_revision"] != revision:
        raise RuntimeError("Phase 7 reevaluation revision mismatch")
    dependency = validate_dependency(dispatch["prerequisites"][0])
    if dependency["kind"] != "dplus0-remediation-gate":
        raise RuntimeError("freeze requires remediated D+0 reevaluation")
    stage_gate = load_json(phase7_stage_gate_path)
    validate_payload(stage_gate, "stage-gate.schema.json")
    decision = stage_gate["decision"]
    if (
        decision["benchmark_classification"] != "dplus0-sufficient"
        or decision["capacity_action"] != "keep-D+0"
        or decision["capacity_protocol_modified"]
        or decision["checkpoint_modified"]
    ):
        raise RuntimeError("remediated D+0 did not pass Phase 7")
    aggregate = load_json(phase7_aggregate_path)
    validate_payload(aggregate, "aggregate-certificate.schema.json")
    if (
        not aggregate["passed"]
        or aggregate["stage_gate"]["sha256"]
        != sha256_file(phase7_stage_gate_path)
        or aggregate["dispatch"]["sha256"]
        != sha256_file(phase7_dispatch_path)
    ):
        raise RuntimeError("Phase 7 aggregate provenance mismatch")

    remediation = load_json(
        require_artifact(dependency["remediation_certificate"])
    )
    validate_payload(
        remediation, "../optimization-remediation.schema.json"
    )
    remediation_readback = load_json(
        require_artifact(dependency["remediation_readback"])
    )
    validate_payload(
        remediation_readback,
        "../optimization-remediation-readback.schema.json",
    )
    payload = {
        "schema_version": (
            "challenge-15-route-d-plus-future-dependency-v1"
        ),
        "kind": "architecture-freeze",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "selection_aggregate": artifact(phase7_aggregate_path),
        "phase6_final": artifact(phase6_final_path),
        "phase6_readback": artifact(phase6_readback_path),
        "phase7_stage_gate": artifact(phase7_stage_gate_path),
        "remediation_certificate": dependency["remediation_certificate"],
        "remediation_readback": dependency["remediation_readback"],
        "selection_stage": "phase7",
        "selection_protocol": dependency["capacity_protocol"],
        "selected_capacity": "D+0",
        "architecture": dependency["architecture"],
        "checkpoints": dependency["checkpoints"],
        "heldout_accessed": False,
        "beyond_ed_accessed": False,
        "passed": True,
    }
    validate_payload(payload, "dependency.schema.json")
    write_json(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--phase6-final", required=True, type=Path)
    parser.add_argument("--phase6-readback", required=True, type=Path)
    parser.add_argument("--phase7-dispatch", required=True, type=Path)
    parser.add_argument("--phase7-stage-gate", required=True, type=Path)
    parser.add_argument("--phase7-aggregate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    payload = freeze(
        repo_root=arguments.repo_root.resolve(),
        phase6_final_path=arguments.phase6_final.resolve(),
        phase6_readback_path=arguments.phase6_readback.resolve(),
        phase7_dispatch_path=arguments.phase7_dispatch.resolve(),
        phase7_stage_gate_path=arguments.phase7_stage_gate.resolve(),
        phase7_aggregate_path=arguments.phase7_aggregate.resolve(),
        output_path=arguments.output.resolve(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
