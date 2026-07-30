from __future__ import annotations

import hashlib
import json
from pathlib import Path

from oracle import exterior_deep_survivor as stage3
from oracle import exterior_depth16_high_precision_replay as stage4hp
from oracle import exterior_depth16_hp_continuation as continuation
from oracle import exterior_depth16_survivor as stage4
from oracle import weights
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, str, list[int]]:
    stage2 = tmp_path / "stage2"
    stage3_root = tmp_path / "stage3"
    stage4_root = tmp_path / "stage4"
    hp_root = tmp_path / "stage4hp"
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
    _write(stage2 / "plan-summary.json", stage2_plan)
    _write(
        stage2 / "candidates" / identity / "manifest.json",
        {
            "run_id": stage2_plan["run_id"],
            "protocol_hash": stage2_plan["protocol_hash"],
            "candidate_id": identity,
            "card_sha256": identity,
            "status": stage3.PARENT_SURVIVOR_STATUS,
        },
    )
    stage3_protocol = stage3._protocol_hash(stage2_plan, stage3.RUN_ID)
    _write(
        stage3_root / "candidates" / identity / "manifest.json",
        {
            "schema_version": stage3.SCHEMA_VERSION,
            "run_id": stage3.RUN_ID,
            "protocol_hash": stage3_protocol,
            "parent_run_id": stage2_plan["run_id"],
            "parent_protocol_hash": stage2_plan["protocol_hash"],
            "candidate_id": identity,
            "card_sha256": identity,
            "depths": list(stage3.DEEP_DEPTHS),
            "planned_words": len(stage3.DEEP_WORDS),
            "tested_words": len(stage3.DEEP_WORDS),
            "status": stage3.SURVIVOR_STATUS,
            "first_failure": None,
        },
    )
    stage4_protocol = stage4._protocol_hash(
        stage2_plan, stage3_protocol, stage4.RUN_ID
    )
    confirmed_word = [0, 1] * 7
    failure = {
        "classification": "uncertain",
        "word_indices": confirmed_word,
        "depth": len(confirmed_word),
        "exact_card_sha256": identity,
        "sigma_min_I_plus_D": 0.0,
    }
    stage4_path = stage4_root / "candidates" / identity / "manifest.json"
    _write(
        stage4_path,
        {
            "schema_version": stage4.SCHEMA_VERSION,
            "run_id": stage4.RUN_ID,
            "protocol_hash": stage4_protocol,
            "parent_run_id": stage3.RUN_ID,
            "parent_protocol_hash": stage3_protocol,
            "stage2_protocol_hash": stage2_plan["protocol_hash"],
            "candidate_id": identity,
            "card_sha256": identity,
            "depths": list(stage4.DEPTHS),
            "planned_words": len(stage4.WORDS),
            "tested_words": 1,
            "status": "uncertain-high-precision",
            "first_failure": failure,
        },
    )
    hp_entry = {
        **entry,
        "stage2_shard": entry["shard"],
        "word_indices": confirmed_word,
        "first_failure_sha256": stage4hp.hp._sha256(failure),
        "stage4_manifest_sha256": hashlib.sha256(stage4_path.read_bytes()).hexdigest(),
    }
    hp_plan = {
        "schema_version": stage4hp.SCHEMA_VERSION,
        "run_id": stage4hp.RUN_ID,
        "stage2_run_id": stage2_plan["run_id"],
        "stage2_source_commit": stage2_plan["source_commit"],
        "stage2_plan_hash": stage2_plan["plan_hash"],
        "stage2_protocol_hash": stage2_plan["protocol_hash"],
        "stage3_run_id": stage3.RUN_ID,
        "stage3_protocol_hash": stage3_protocol,
        "stage4_run_id": stage4.RUN_ID,
        "stage4_protocol_hash": stage4_protocol,
        "stage4_depths": list(stage4.DEPTHS),
        "dps_ladder": list(stage4hp.DEFAULT_DPS),
        "candidate_count": 1,
        "candidates": [hp_entry],
    }
    hp_plan["replay_plan_hash"] = stage4hp.hp._sha256(hp_plan)
    _write(hp_root / "replay-plan.json", hp_plan)
    _write(
        hp_root / "candidates" / identity / "manifest.json",
        {
            "schema_version": stage4hp.SCHEMA_VERSION,
            "run_id": stage4hp.RUN_ID,
            "replay_plan_hash": hp_plan["replay_plan_hash"],
            "candidate_id": identity,
            "card_sha256": identity,
            "word_indices": confirmed_word,
            "first_failure_sha256": hp_entry["first_failure_sha256"],
            "stage4_manifest_sha256": hp_entry["stage4_manifest_sha256"],
            "status": "confirmed-nonnegative",
            "ladder": [{"dps": 180, "sign": "positive"}],
            "exact_determinant": {
                "numerator": "1",
                "denominator": "1",
                "sign": 1,
            },
        },
    )
    return stage2, stage3_root, stage4_root, hp_root, identity, confirmed_word


def _result(classification: str) -> weights.WeightResult:
    return weights.WeightResult(
        classification=classification,
        value=1 + 0j,
        phase=1 + 0j,
        log_abs=0.0,
        sigma_min=0.0 if classification == "uncertain" else 1.0,
        condition_number=1.0,
    )


def test_reuses_confirmed_word_scans_suffix_and_resumes(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, stage3_root, stage4_root, hp_root, identity, confirmed = _fixture(
        tmp_path
    )
    new_word = [0, 1] + [0] * 11
    monkeypatch.setattr(
        continuation, "WORDS", (tuple(new_word), tuple(confirmed))
    )
    output = tmp_path / "continuation"
    plan = continuation.plan_continuation(
        stage2, stage3_root, stage4_root, hp_root, output, expected_count=1
    )
    calls = 0

    def positive(_):
        nonlocal calls
        calls += 1
        return _result("positive")

    monkeypatch.setattr(continuation.weights, "classify_product", positive)
    owner = int(identity[:16], 16) % continuation.WORKERS
    first = continuation.run_worker(
        stage2,
        stage3_root,
        stage4_root,
        hp_root,
        output,
        worker_index=owner,
    )
    second = continuation.run_worker(
        stage2,
        stage3_root,
        stage4_root,
        hp_root,
        output,
        worker_index=owner,
    )
    summary = continuation.collect_run(output)
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )

    assert plan["candidate_count"] == 1
    assert plan["word_count_per_candidate"] == 2
    assert calls == 1
    assert first == {"completed": 1, "reused": 0, "operational_errors": 0}
    assert second == {"completed": 0, "reused": 1, "operational_errors": 0}
    assert manifest["status"] == continuation.SURVIVOR_STATUS
    assert manifest["reused_hp_count"] == 1
    assert summary["reused_hp_proofs"] == 1


def test_new_uncertain_word_exact_negative_early_stops(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, stage3_root, stage4_root, hp_root, identity, confirmed = _fixture(
        tmp_path
    )
    new_word = [0, 1] + [0] * 11
    monkeypatch.setattr(
        continuation, "WORDS", (tuple(new_word), tuple(confirmed))
    )
    output = tmp_path / "continuation"
    continuation.plan_continuation(
        stage2, stage3_root, stage4_root, hp_root, output, expected_count=1
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
        stage2,
        stage3_root,
        stage4_root,
        hp_root,
        output,
        worker_index=owner,
    )
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )

    assert manifest["status"] == "rejected-negative-exact-fallback"
    assert manifest["tested_words"] == 1
    assert manifest["exact_fallback_count"] == 1
