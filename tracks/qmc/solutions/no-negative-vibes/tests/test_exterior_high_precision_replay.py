from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id
from oracle import exterior_high_precision_replay as replay


def _parent_run(root: Path, *, tamper_hash: bool = False) -> str:
    card = candidate_card(template=TEMPLATES[0], seed=0)
    identity = candidate_id(card)
    entry = {
        "candidate_id": identity,
        "card_sha256": identity,
        "template": card["template"],
        "seed": card["seed"],
        "dimension": card["dimension"],
        "shard": 7,
    }
    plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "source_commit": "a" * 40,
        "plan_hash": "b" * 64,
        "protocol_hash": "c" * 64,
        "candidates": [entry],
    }
    (root / "plan-summary.json").parent.mkdir(parents=True)
    (root / "plan-summary.json").write_text(json.dumps(plan), encoding="utf-8")
    failure = {
        "classification": "uncertain",
        "word_indices": [0, 1, 0, 1, 0],
        "depth": 5,
        "exact_card_sha256": "d" * 64 if tamper_hash else identity,
    }
    manifest = {
        "run_id": plan["run_id"],
        "source_commit": plan["source_commit"],
        "protocol_hash": plan["protocol_hash"],
        **entry,
        "status": "uncertain-high-precision",
        "first_failure": failure,
    }
    path = root / "candidates" / identity / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return identity


def test_plan_run_resume_and_collect_one_uncertain_candidate(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    identity = _parent_run(parent)
    output = tmp_path / "replay"

    planned = replay.plan_replay(parent, output, expected_count=1)
    owner = int(identity[:16], 16) % 3
    first = replay.run_worker(parent, output, worker_index=owner, workers=3)
    second = replay.run_worker(parent, output, worker_index=owner, workers=3)
    summary = replay.collect_replay(output, markdown=output / "summary.md")

    assert planned["candidate_count"] == 1
    assert first == {"completed": 1, "reused": 0, "unresolved": 0}
    assert second == {"completed": 0, "reused": 1, "unresolved": 0}
    assert summary["terminal"] == 1
    assert summary["missing"] == 0
    assert sum(summary["status_counts"].values()) == 1
    assert (output / "summary.md").is_file()


def test_plan_rejects_tampered_exact_card_binding(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    _parent_run(parent, tamper_hash=True)

    with pytest.raises(RuntimeError, match="first_failure"):
        replay.plan_replay(parent, tmp_path / "replay", expected_count=1)
