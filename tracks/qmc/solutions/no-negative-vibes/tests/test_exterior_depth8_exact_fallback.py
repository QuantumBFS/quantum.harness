from __future__ import annotations

import json
from pathlib import Path

from oracle import exterior_depth8_exact_fallback as depth8
from oracle import exterior_high_precision_replay as hp
from oracle import weights
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


def _fixture_runs(tmp_path: Path) -> tuple[Path, Path, str]:
    parent = tmp_path / "parent"
    hp_root = tmp_path / "hp"
    cards = [
        candidate_card(template=TEMPLATES[0], seed=seed)
        for seed in (0, 1)
    ]
    entries = []
    failures = {}
    first_word = [0, 0, 0, 0, 1]
    parent_plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "source_commit": "a" * 40,
        "plan_hash": "b" * 64,
        "protocol_hash": "c" * 64,
    }
    for shard, card in enumerate(cards):
        identity = candidate_id(card)
        entry = {
            "candidate_id": identity,
            "card_sha256": identity,
            "template": card["template"],
            "seed": card["seed"],
            "dimension": card["dimension"],
            "shard": shard,
        }
        entries.append(entry)
        failure = {
            "classification": "uncertain",
            "word_indices": first_word,
            "depth": 5,
            "exact_card_sha256": identity,
        }
        failures[identity] = failure
        manifest = {
            **entry,
            "run_id": parent_plan["run_id"],
            "source_commit": parent_plan["source_commit"],
            "protocol_hash": parent_plan["protocol_hash"],
            "status": "uncertain-high-precision",
            "first_failure": failure,
        }
        path = parent / "candidates" / identity / "manifest.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
    parent_plan["candidates"] = entries
    (parent / "plan-summary.json").parent.mkdir(parents=True, exist_ok=True)
    (parent / "plan-summary.json").write_text(
        json.dumps(parent_plan), encoding="utf-8",
    )

    hp_entries = [
        {
            **entry,
            "parent_shard": entry["shard"],
            "word_indices": first_word,
            "first_failure_sha256": hp._sha256(failures[entry["candidate_id"]]),
        }
        for entry in entries
    ]
    hp_plan = {
        "schema_version": hp.SCHEMA_VERSION,
        "run_id": hp.RUN_ID,
        "parent_run_id": parent_plan["run_id"],
        "parent_source_commit": parent_plan["source_commit"],
        "parent_plan_hash": parent_plan["plan_hash"],
        "parent_protocol_hash": parent_plan["protocol_hash"],
        "dps_ladder": list(hp.DEFAULT_DPS),
        "candidate_count": 2,
        "candidates": hp_entries,
    }
    hp_plan["replay_plan_hash"] = hp._sha256(hp_plan)
    (hp_root / "replay-plan.json").parent.mkdir(parents=True)
    (hp_root / "replay-plan.json").write_text(json.dumps(hp_plan), encoding="utf-8")
    for index, entry in enumerate(hp_entries):
        identity = entry["candidate_id"]
        status = "confirmed-nonnegative" if index == 0 else "confirmed-negative"
        manifest = {
            "candidate_id": identity,
            "replay_plan_hash": hp_plan["replay_plan_hash"],
            "word_indices": first_word,
            "first_failure_sha256": entry["first_failure_sha256"],
            "status": status,
            "ladder": [{"dps": 180, "sign": "positive" if index == 0 else "negative"}],
            "exact_determinant": {
                "numerator": "1" if index == 0 else "-1",
                "denominator": "1",
                "sign": 1 if index == 0 else -1,
            },
        }
        path = hp_root / "candidates" / identity / "manifest.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
    return parent, hp_root, entries[0]["candidate_id"]


def _result(classification: str) -> weights.WeightResult:
    return weights.WeightResult(
        classification=classification,
        value=1 + 0j,
        phase=1 + 0j,
        log_abs=0.0,
        sigma_min=0.0 if classification == "uncertain" else 1.0,
        condition_number=1.0,
    )


def test_selects_only_hp_nonnegative_and_completes_all_472(
    tmp_path: Path, monkeypatch,
) -> None:
    parent, hp_root, identity = _fixture_runs(tmp_path)
    output = tmp_path / "output"
    plan = depth8.plan_continuation(
        parent, hp_root, output, expected_count=1,
    )
    calls = 0

    def classify(_):
        nonlocal calls
        calls += 1
        return _result("uncertain" if calls == 1 else "positive")

    monkeypatch.setattr(depth8.weights, "classify_product", classify)
    owner = int(identity[:16], 16) % 76
    assert depth8.run_worker(
        parent, hp_root, output, worker_index=owner,
    ) == {"completed": 1, "reused": 0, "operational_errors": 0}
    summary = depth8.collect_run(output, markdown=output / "summary.md")
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )
    assert plan["candidate_count"] == 1
    assert calls == 472
    assert manifest["status"] == depth8.SURVIVOR_STATUS
    assert manifest["tested_words"] == 472
    assert manifest["exact_fallback_count"] == 1
    assert summary["status_counts"] == {depth8.SURVIVOR_STATUS: 1}


def test_new_uncertain_word_uses_exact_fallback_and_stops_on_negative(
    tmp_path: Path, monkeypatch,
) -> None:
    parent, hp_root, identity = _fixture_runs(tmp_path)
    output = tmp_path / "output"
    depth8.plan_continuation(parent, hp_root, output, expected_count=1)
    classifications = iter(("uncertain", "uncertain"))
    monkeypatch.setattr(
        depth8.weights, "classify_product", lambda _: _result(next(classifications)),
    )
    monkeypatch.setattr(
        depth8,
        "_adjudicate_word",
        lambda _: (
            "negative",
            {
                "source": "test-exact",
                "ladder": [],
                "exact_determinant": {
                    "numerator": "-1", "denominator": "1", "sign": -1,
                },
            },
        ),
    )
    owner = int(identity[:16], 16) % 76
    depth8.run_worker(parent, hp_root, output, worker_index=owner)
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )
    assert manifest["status"] == "rejected-negative-exact-fallback"
    assert manifest["tested_words"] == 2
    assert manifest["exact_fallback_count"] == 2
