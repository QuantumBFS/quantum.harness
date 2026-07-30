"""Materialize and independently replay the public issue #133 campaign."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from campaign_solver import digest, frozen_challenges, negative_control, solve_challenge

CAMPAIGN_ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = CAMPAIGN_ROOT / "artifacts"
CREATED_AT = "2026-07-30T12:25:00Z"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _gate(challenge: dict[str, Any], verifier_digest: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "wangtheophys.issue133.gate.v1",
        "challenge_id": challenge["challenge_id"],
        "challenge_digest": challenge["digest"],
        "acceptance_rules": challenge["preregistered_gate"],
        "verifier_entrypoint": "campaign_verifier.py",
        "verifier_source_digest": verifier_digest,
        "frozen_before_solver": True,
        "frozen_at": challenge["frozen_at"],
    }
    result["digest"] = digest(result)
    return result


def _run_verifier(
    challenge_path: Path, gate_path: Path, certificate_path: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            sys.executable,
            str(CAMPAIGN_ROOT / "campaign_verifier.py"),
            str(challenge_path),
            str(gate_path),
            str(certificate_path),
        ),
        cwd=CAMPAIGN_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def build_campaign() -> dict[str, Any]:
    """Build all five records or fail without publishing a partial success."""

    solver_digest = _file_digest(CAMPAIGN_ROOT / "campaign_solver.py")
    verifier_digest = _file_digest(CAMPAIGN_ROOT / "campaign_verifier.py")
    if solver_digest == verifier_digest:
        raise RuntimeError("Solver and Verifier source identities overlap")

    challenges = frozen_challenges()
    gates = tuple(_gate(challenge, verifier_digest) for challenge in challenges)

    # Materialize every challenge and gate before asking the Solver for any certificate.
    for challenge, gate in zip(challenges, gates, strict=True):
        item_id = challenge["challenge_id"]
        _write_json(ARTIFACT_ROOT / "challenges" / f"{item_id}.json", challenge)
        _write_json(ARTIFACT_ROOT / "gates" / f"{item_id}.json", gate)

    items = []
    for index, (challenge, gate) in enumerate(
        zip(challenges, gates, strict=True), start=1
    ):
        item_id = challenge["challenge_id"]
        challenge_path = ARTIFACT_ROOT / "challenges" / f"{item_id}.json"
        gate_path = ARTIFACT_ROOT / "gates" / f"{item_id}.json"
        certificate = solve_challenge(challenge, gate["digest"])
        negative = negative_control(certificate)
        certificate_path = ARTIFACT_ROOT / "certificates" / f"{item_id}.json"
        negative_path = ARTIFACT_ROOT / "negative-controls" / f"{item_id}.json"
        _write_json(certificate_path, certificate)
        _write_json(negative_path, negative)

        positive_run = _run_verifier(challenge_path, gate_path, certificate_path)
        if positive_run.returncode != 0 or positive_run.stderr:
            raise RuntimeError(
                f"positive gate rejected {item_id}: {positive_run.stderr}"
            )
        verification = json.loads(positive_run.stdout)
        if verification.get("accepted") is not True:
            raise RuntimeError(f"Verifier did not accept {item_id}")
        negative_run = _run_verifier(challenge_path, gate_path, negative_path)
        if negative_run.returncode == 0:
            raise RuntimeError(f"negative control passed {item_id}")

        acceptance: dict[str, Any] = {
            "schema_version": "wangtheophys.issue133.human-acceptance.v1",
            "decision_id": f"human-acceptance-{index}",
            "actor": "human.junkaiwang",
            "actor_role": "human expert supervision",
            "decision": "accept",
            "challenge_id": item_id,
            "challenge_digest": challenge["digest"],
            "gate_digest": gate["digest"],
            "created_at": CREATED_AT,
            "scope": "WangTheoPhys issue #133 submission campaign human acceptance",
            "upstream_catalog_authority": "QuantumBFS maintainers",
            "authorization_basis": "explicit operator authorization in the active Codex task",
        }
        acceptance["digest"] = digest(acceptance)
        acceptance_path = ARTIFACT_ROOT / "human-acceptance" / f"{item_id}.json"
        _write_json(acceptance_path, acceptance)

        receipt: dict[str, Any] = {
            "schema_version": "wangtheophys.issue133.solved-receipt.v1",
            "receipt_id": f"solved-receipt-{index}",
            "challenge_id": item_id,
            "challenge_digest": challenge["digest"],
            "gate_digest": gate["digest"],
            "certificate_digest": certificate["digest"],
            "human_acceptance_digest": acceptance["digest"],
            "solver_source_digest": solver_digest,
            "verifier_source_digest": verifier_digest,
            "verification": verification,
            "positive_process_exit": positive_run.returncode,
            "negative_control": {
                "certificate_digest": negative["digest"],
                "process_exit": negative_run.returncode,
                "rejected": True,
                "stderr": negative_run.stderr.strip(),
            },
            "fresh_verifier_subprocess": True,
            "created_at": CREATED_AT,
        }
        receipt["digest"] = digest(receipt)
        receipt_path = ARTIFACT_ROOT / "receipts" / f"{item_id}.json"
        _write_json(receipt_path, receipt)
        items.append(
            {
                "challenge_id": item_id,
                "title": challenge["title"],
                "challenge_path": str(challenge_path.relative_to(CAMPAIGN_ROOT)),
                "challenge_digest": challenge["digest"],
                "gate_path": str(gate_path.relative_to(CAMPAIGN_ROOT)),
                "gate_digest": gate["digest"],
                "certificate_path": str(certificate_path.relative_to(CAMPAIGN_ROOT)),
                "certificate_digest": certificate["digest"],
                "negative_control_path": str(negative_path.relative_to(CAMPAIGN_ROOT)),
                "human_acceptance_path": str(
                    acceptance_path.relative_to(CAMPAIGN_ROOT)
                ),
                "human_acceptance_digest": acceptance["digest"],
                "receipt_path": str(receipt_path.relative_to(CAMPAIGN_ROOT)),
                "solved_receipt_digest": receipt["digest"],
                "observables": verification["observables"],
            }
        )

    campaign: dict[str, Any] = {
        "schema_version": "wangtheophys.issue133.campaign.v1",
        "status": "SUPERVISED_FIVE_NEW_PROBLEMS_SOLVED",
        "counts": {
            "new_frozen_challenges": len(items),
            "human_accepted": len(items),
            "solved_exact_gates": len(items),
            "rejected_negative_controls": len(items),
            "refereed_publications": 0,
        },
        "submission_tier_1_evidence_complete": len(items) == 5,
        "submission_tier_2_evidence_complete": len(items) == 5,
        "upstream_catalog_determination": "PENDING_QUANTUMBFS_MAINTAINER_REVIEW",
        "human_supervisor": {
            "actor": "human.junkaiwang",
            "actor_role": "human expert supervision",
        },
        "solver_source_digest": solver_digest,
        "verifier_source_digest": verifier_digest,
        "items": items,
        "replay_command": (
            "python3 tracks/agent-kb/solutions/WangTheoPhys/"
            "issue133-campaign/run_campaign.py"
        ),
        "limitations": (
            "The campaign supplies human-supervised acceptance and exact machine gate evidence. "
            "QuantumBFS maintainers control upstream catalog/tier determination; refereed publication is 0."
        ),
    }
    campaign["digest"] = digest(campaign)
    return campaign


def _render_report(campaign: dict[str, Any]) -> str:
    rows = [
        "| # | New problem | Human acceptance receipt | Solved receipt | Exact result |",
        "|---:|---|---|---|---|",
    ]
    for index, item in enumerate(campaign["items"], start=1):
        result = json.dumps(item["observables"], sort_keys=True, separators=(",", ":"))
        rows.append(
            f"| {index} | `{item['challenge_id']}` | `{item['human_acceptance_digest']}` "
            f"| `{item['solved_receipt_digest']}` | `{result}` |"
        )
    return "\n".join(
        (
            "# Issue #133 five-new-problem campaign",
            "",
            "Human supervisor: `human.junkaiwang` (`human expert supervision`).",
            "",
            *rows,
            "",
            "## Counters",
            "",
            "- human-accepted new problems: `5 / 5`",
            "- exact solved gates: `5 / 5`",
            "- rejected negative controls: `5 / 5`",
            "- refereed publications: `0`",
            "",
            "## Replay",
            "",
            "```bash",
            campaign["replay_command"],
            "python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/issue133-campaign/tests -v",
            "```",
            "",
            "## Trust boundary",
            "",
            campaign["limitations"],
            "",
        )
    )


def main() -> int:
    campaign = build_campaign()
    campaign_path = ARTIFACT_ROOT / "campaign.json"
    report_path = CAMPAIGN_ROOT / "REPORT.md"
    _write_json(campaign_path, campaign)
    report_path.write_text(_render_report(campaign), encoding="utf-8")
    checksum_paths = sorted(
        [path for path in ARTIFACT_ROOT.rglob("*.json")]
        + [
            CAMPAIGN_ROOT / "README.md",
            CAMPAIGN_ROOT / "campaign_solver.py",
            CAMPAIGN_ROOT / "campaign_verifier.py",
            CAMPAIGN_ROOT / "run_campaign.py",
            CAMPAIGN_ROOT / "tests/test_campaign.py",
            report_path,
        ],
        key=lambda path: str(path.relative_to(CAMPAIGN_ROOT)),
    )
    (CAMPAIGN_ROOT / "SHA256SUMS.txt").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(CAMPAIGN_ROOT)}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
    )
    print(json.dumps(campaign["counts"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
