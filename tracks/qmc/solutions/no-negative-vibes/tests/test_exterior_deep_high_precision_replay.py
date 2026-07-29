from __future__ import annotations

import json
from pathlib import Path

import sympy as sp

from oracle import exterior_deep_high_precision_replay as replay
from oracle import exterior_deep_survivor as deep
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


def _fixture(tmp_path: Path, *, tamper: bool = False) -> tuple[Path, Path, str]:
    stage2 = tmp_path / "stage2"
    stage3 = tmp_path / "stage3"
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
                "status": deep.PARENT_SURVIVOR_STATUS,
            }
        ),
        encoding="utf-8",
    )
    protocol_hash = deep._protocol_hash(plan, deep.RUN_ID)
    failure = {
        "classification": "uncertain",
        "word_indices": [0, 1, 0, 1, 0, 1, 0, 1, 0],
        "depth": 9,
        "exact_card_sha256": "d" * 64 if tamper else identity,
        "sigma_min_I_plus_D": 0.0,
    }
    stage3_path = stage3 / "candidates" / identity / "manifest.json"
    stage3_path.parent.mkdir(parents=True)
    stage3_path.write_text(
        json.dumps(
            {
                "schema_version": deep.SCHEMA_VERSION,
                "run_id": deep.RUN_ID,
                "protocol_hash": protocol_hash,
                "parent_run_id": plan["run_id"],
                "parent_protocol_hash": plan["protocol_hash"],
                "candidate_id": identity,
                "card_sha256": identity,
                "depths": list(deep.DEEP_DEPTHS),
                "planned_words": len(deep.DEEP_WORDS),
                "tested_words": 1,
                "status": "uncertain-high-precision",
                "first_failure": failure,
            }
        ),
        encoding="utf-8",
    )
    return stage2, stage3, identity


def test_plan_run_resume_and_collect_one_deep_uncertainty(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, stage3, identity = _fixture(tmp_path)
    output = tmp_path / "replay"
    plan = replay.plan_replay(stage2, stage3, output, expected_count=1)
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
    first = replay.run_worker(stage2, stage3, output, worker_index=owner)
    second = replay.run_worker(stage2, stage3, output, worker_index=owner)
    summary = replay.collect_replay(output, markdown=output / "summary.md")

    assert plan["candidate_count"] == 1
    assert first == {"completed": 1, "reused": 0, "unresolved": 0}
    assert second == {"completed": 0, "reused": 1, "unresolved": 0}
    assert summary["status_counts"] == {"confirmed-nonnegative": 1}
    assert (output / "summary.md").is_file()


def test_plan_rejects_tampered_deep_exact_card_binding(tmp_path: Path) -> None:
    stage2, stage3, _ = _fixture(tmp_path, tamper=True)

    try:
        replay.plan_replay(stage2, stage3, tmp_path / "replay", expected_count=1)
    except RuntimeError as error:
        assert "uncertain failure" in str(error)
    else:
        raise AssertionError("tampered Stage-3 failure was accepted")
