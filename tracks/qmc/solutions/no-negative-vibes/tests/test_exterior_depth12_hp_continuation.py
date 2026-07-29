from __future__ import annotations

import hashlib
import json
from pathlib import Path

from oracle import exterior_deep_high_precision_replay as stage3hp
from oracle import exterior_deep_survivor as stage3
from oracle import exterior_depth12_hp_continuation as continuation
from oracle import weights
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    stage2_root = tmp_path / "stage2"
    stage3_root = tmp_path / "stage3"
    hp_root = tmp_path / "stage3hp"
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
    stage2_plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "source_commit": "a" * 40,
        "plan_hash": "b" * 64,
        "protocol_hash": "c" * 64,
        "candidates": [entry],
    }
    _write(stage2_root / "plan-summary.json", stage2_plan)
    _write(
        stage2_root / "candidates" / identity / "manifest.json",
        {
            "run_id": stage2_plan["run_id"],
            "protocol_hash": stage2_plan["protocol_hash"],
            "candidate_id": identity,
            "card_sha256": identity,
            "status": stage3.PARENT_SURVIVOR_STATUS,
        },
    )

    confirmed_word = [0, 1, 0, 1, 0, 1, 0, 1, 0]
    protocol_hash = stage3._protocol_hash(stage2_plan, stage3.RUN_ID)
    failure = {
        "classification": "uncertain",
        "word_indices": confirmed_word,
        "depth": len(confirmed_word),
        "exact_card_sha256": identity,
        "sigma_min_I_plus_D": 0.0,
    }
    stage3_manifest = {
        "schema_version": stage3.SCHEMA_VERSION,
        "run_id": stage3.RUN_ID,
        "protocol_hash": protocol_hash,
        "parent_run_id": stage2_plan["run_id"],
        "parent_protocol_hash": stage2_plan["protocol_hash"],
        "candidate_id": identity,
        "card_sha256": identity,
        "depths": list(stage3.DEEP_DEPTHS),
        "planned_words": len(stage3.DEEP_WORDS),
        "tested_words": 1,
        "status": "uncertain-high-precision",
        "first_failure": failure,
    }
    stage3_path = stage3_root / "candidates" / identity / "manifest.json"
    _write(stage3_path, stage3_manifest)

    hp_entry = {
        **entry,
        "stage2_shard": entry["shard"],
        "word_indices": confirmed_word,
        "first_failure_sha256": stage3hp._sha256(failure),
        "stage3_manifest_sha256": hashlib.sha256(stage3_path.read_bytes()).hexdigest(),
    }
    hp_plan = {
        "schema_version": stage3hp.SCHEMA_VERSION,
        "run_id": stage3hp.RUN_ID,
        "stage2_run_id": stage2_plan["run_id"],
        "stage2_source_commit": stage2_plan["source_commit"],
        "stage2_plan_hash": stage2_plan["plan_hash"],
        "stage2_protocol_hash": stage2_plan["protocol_hash"],
        "stage3_run_id": stage3.RUN_ID,
        "stage3_protocol_hash": protocol_hash,
        "stage3_depths": list(stage3.DEEP_DEPTHS),
        "dps_ladder": list(stage3hp.DEFAULT_DPS),
        "candidate_count": 1,
        "candidates": [hp_entry],
    }
    hp_plan["replay_plan_hash"] = stage3hp._sha256(hp_plan)
    _write(hp_root / "replay-plan.json", hp_plan)
    _write(
        hp_root / "candidates" / identity / "manifest.json",
        {
            "schema_version": stage3hp.SCHEMA_VERSION,
            "run_id": stage3hp.RUN_ID,
            "replay_plan_hash": hp_plan["replay_plan_hash"],
            "candidate_id": identity,
            "card_sha256": identity,
            "word_indices": confirmed_word,
            "first_failure_sha256": hp_entry["first_failure_sha256"],
            "status": "confirmed-nonnegative",
            "ladder": [{"dps": 180, "sign": "positive"}],
            "exact_determinant": {
                "numerator": "1",
                "denominator": "1",
                "sign": 1,
            },
        },
    )
    return stage2_root, stage3_root, hp_root, identity


def _result(classification: str) -> weights.WeightResult:
    return weights.WeightResult(
        classification=classification,
        value=1 + 0j,
        phase=1 + 0j,
        log_abs=0.0,
        sigma_min=0.0 if classification == "uncertain" else 1.0,
        condition_number=1.0,
    )


def test_reuses_confirmed_word_completes_tranche_and_resumes(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, parent, hp_root, identity = _fixture(tmp_path)
    output = tmp_path / "output"
    plan = continuation.plan_continuation(
        stage2, parent, hp_root, output, expected_count=1
    )
    calls = 0

    def positive(_):
        nonlocal calls
        calls += 1
        return _result("positive")

    monkeypatch.setattr(continuation.weights, "classify_product", positive)
    owner = int(identity[:16], 16) % continuation.WORKERS
    first = continuation.run_worker(
        stage2, parent, hp_root, output, worker_index=owner
    )
    second = continuation.run_worker(
        stage2, parent, hp_root, output, worker_index=owner
    )
    summary = continuation.collect_run(output, markdown=output / "summary.md")
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )
    assert plan["candidate_count"] == 1
    assert plan["word_count_per_candidate"] == 7672
    assert calls == 7671
    assert first == {"completed": 1, "reused": 0, "operational_errors": 0}
    assert second == {"completed": 0, "reused": 1, "operational_errors": 0}
    assert manifest["status"] == continuation.SURVIVOR_STATUS
    assert manifest["tested_words"] == 7672
    assert manifest["reused_hp_count"] == 1
    assert summary["reused_hp_proofs"] == 1


def test_new_uncertain_word_exact_negative_early_stops(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, parent, hp_root, identity = _fixture(tmp_path)
    output = tmp_path / "output"
    continuation.plan_continuation(
        stage2, parent, hp_root, output, expected_count=1
    )
    monkeypatch.setattr(
        continuation.weights, "classify_product", lambda _: _result("uncertain")
    )
    monkeypatch.setattr(
        continuation.exact_fallback,
        "_adjudicate_word",
        lambda _: (
            "negative",
            {
                "source": "test-exact",
                "ladder": [],
                "exact_determinant": {
                    "numerator": "-1",
                    "denominator": "1",
                    "sign": -1,
                },
            },
        ),
    )
    owner = int(identity[:16], 16) % continuation.WORKERS
    continuation.run_worker(
        stage2, parent, hp_root, output, worker_index=owner
    )
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )
    assert manifest["status"] == "rejected-negative-exact-fallback"
    assert manifest["tested_words"] == 1
    assert manifest["exact_fallback_count"] == 1
