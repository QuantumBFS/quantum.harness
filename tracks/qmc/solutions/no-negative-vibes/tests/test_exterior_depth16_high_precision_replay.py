from __future__ import annotations

import json
from pathlib import Path

import sympy as sp

from oracle import exterior_depth16_high_precision_replay as replay
from oracle import exterior_deep_survivor as stage3
from oracle import exterior_depth16_survivor as stage4
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


def _fixture(tmp_path: Path, *, tamper: bool = False) -> tuple[Path, Path, Path, str]:
    stage2 = tmp_path / "stage2"
    stage3_root = tmp_path / "stage3"
    stage4_root = tmp_path / "stage4"
    card = candidate_card(template=TEMPLATES[0], seed=0)
    identity = candidate_id(card)
    entry = {
        "candidate_id": identity,
        "card_sha256": identity,
        "template": card["template"],
        "seed": card["seed"],
        "dimension": card["dimension"],
        "shard": 4,
    }
    plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "source_commit": "a" * 40,
        "plan_hash": "b" * 64,
        "protocol_hash": "c" * 64,
        "candidates": [entry],
    }
    (stage2 / "plan-summary.json").parent.mkdir(parents=True)
    (stage2 / "plan-summary.json").write_text(json.dumps(plan), encoding="utf-8")
    parent_path = stage2 / "candidates" / identity / "manifest.json"
    parent_path.parent.mkdir(parents=True)
    parent_path.write_text(
        json.dumps(
            {
                "run_id": plan["run_id"],
                "protocol_hash": plan["protocol_hash"],
                "candidate_id": identity,
                "card_sha256": identity,
                "status": stage3.PARENT_SURVIVOR_STATUS,
            }
        ),
        encoding="utf-8",
    )
    stage3_protocol = stage3._protocol_hash(plan, stage3.RUN_ID)
    stage3_path = stage3_root / "candidates" / identity / "manifest.json"
    stage3_path.parent.mkdir(parents=True)
    stage3_path.write_text(
        json.dumps(
            {
                "schema_version": stage3.SCHEMA_VERSION,
                "run_id": stage3.RUN_ID,
                "protocol_hash": stage3_protocol,
                "parent_run_id": plan["run_id"],
                "parent_protocol_hash": plan["protocol_hash"],
                "candidate_id": identity,
                "card_sha256": identity,
                "depths": list(stage3.DEEP_DEPTHS),
                "planned_words": len(stage3.DEEP_WORDS),
                "tested_words": len(stage3.DEEP_WORDS),
                "status": stage3.SURVIVOR_STATUS,
                "first_failure": None,
            }
        ),
        encoding="utf-8",
    )
    stage4_protocol = stage4._protocol_hash(plan, stage3_protocol, stage4.RUN_ID)
    failure = {
        "classification": "uncertain",
        "word_indices": [0, 1] * 7,
        "depth": 14,
        "exact_card_sha256": "d" * 64 if tamper else identity,
        "sigma_min_I_plus_D": 0.0,
    }
    stage4_path = stage4_root / "candidates" / identity / "manifest.json"
    stage4_path.parent.mkdir(parents=True)
    stage4_path.write_text(
        json.dumps(
            {
                "schema_version": stage4.SCHEMA_VERSION,
                "run_id": stage4.RUN_ID,
                "protocol_hash": stage4_protocol,
                "parent_run_id": stage3.RUN_ID,
                "parent_protocol_hash": stage3_protocol,
                "stage2_protocol_hash": plan["protocol_hash"],
                "candidate_id": identity,
                "card_sha256": identity,
                "depths": list(stage4.DEPTHS),
                "planned_words": len(stage4.WORDS),
                "tested_words": 1,
                "status": "uncertain-high-precision",
                "first_failure": failure,
            }
        ),
        encoding="utf-8",
    )
    return stage2, stage3_root, stage4_root, identity


def test_plan_run_resume_and_collect_one_depth16_uncertainty(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, stage3_root, stage4_root, identity = _fixture(tmp_path)
    output = tmp_path / "replay"
    plan = replay.plan_replay(
        stage2, stage3_root, stage4_root, output, expected_count=1
    )
    monkeypatch.setattr(
        replay,
        "_adjudicate",
        lambda _: (
            "confirmed-nonnegative",
            [{"dps": 180, "sign": "positive"}],
            sp.Rational(1),
            "test exact agreement",
        ),
    )
    owner = int(identity[:16], 16) % 76
    first = replay.run_worker(
        stage2, stage3_root, stage4_root, output, worker_index=owner
    )
    second = replay.run_worker(
        stage2, stage3_root, stage4_root, output, worker_index=owner
    )
    summary = replay.collect_replay(output, markdown=output / "summary.md")

    assert plan["candidate_count"] == 1
    assert first == {"completed": 1, "reused": 0, "unresolved": 0}
    assert second == {"completed": 0, "reused": 1, "unresolved": 0}
    assert summary["status_counts"] == {"confirmed-nonnegative": 1}
    assert (output / "summary.md").is_file()


def test_plan_rejects_tampered_depth16_exact_card_binding(tmp_path: Path) -> None:
    stage2, stage3_root, stage4_root, _ = _fixture(tmp_path, tamper=True)

    try:
        replay.plan_replay(
            stage2, stage3_root, stage4_root, tmp_path / "replay", expected_count=1
        )
    except RuntimeError as error:
        assert "uncertain failure" in str(error)
    else:
        raise AssertionError("tampered Stage-4 failure was accepted")
