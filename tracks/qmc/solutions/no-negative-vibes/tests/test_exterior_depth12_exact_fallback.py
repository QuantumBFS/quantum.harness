from __future__ import annotations

import json
from pathlib import Path

from oracle import exterior_depth12_exact_fallback as depth12
from oracle import exterior_depth8_exact_fallback as depth8
from oracle import weights
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    stage2_root = tmp_path / "stage2"
    depth8_root = tmp_path / "depth8"
    cards = [candidate_card(template=TEMPLATES[0], seed=seed) for seed in (0, 1)]
    entries = [
        {
            "candidate_id": candidate_id(card),
            "card_sha256": candidate_id(card),
            "template": card["template"],
            "seed": card["seed"],
            "dimension": card["dimension"],
            "shard": index,
        }
        for index, card in enumerate(cards)
    ]
    stage2_plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "source_commit": "a" * 40,
        "plan_hash": "b" * 64,
        "protocol_hash": "c" * 64,
        "candidates": entries,
    }
    _write(stage2_root / "plan-summary.json", stage2_plan)

    parent_plan = {
        "schema_version": depth8.SCHEMA_VERSION,
        "run_id": depth8.RUN_ID,
        "parent_run_id": stage2_plan["run_id"],
        "parent_source_commit": stage2_plan["source_commit"],
        "parent_plan_hash": stage2_plan["plan_hash"],
        "parent_protocol_hash": stage2_plan["protocol_hash"],
        "hp_replay_plan_hash": "d" * 64,
        "depths": list(depth8.DEPTHS),
        "word_count_per_candidate": 472,
        "candidate_count": len(entries),
        "candidates": entries,
    }
    parent_plan["continuation_plan_hash"] = depth8._sha256(parent_plan)
    _write(depth8_root / "continuation-plan.json", parent_plan)
    for index, entry in enumerate(entries):
        survivor = index == 0
        manifest = {
            "schema_version": depth8.SCHEMA_VERSION,
            "run_id": depth8.RUN_ID,
            "continuation_plan_hash": parent_plan["continuation_plan_hash"],
            **entry,
            "depths": list(depth8.DEPTHS),
            "planned_words": 472,
            "tested_words": 472 if survivor else 1,
            "exact_fallback_count": 0,
            "status": (
                depth8.SURVIVOR_STATUS
                if survivor
                else "rejected-negative-stable"
            ),
            "first_failure": (
                None
                if survivor
                else {"classification": "negative", "word_indices": [0, 1]}
            ),
        }
        _write(
            depth8_root
            / "candidates"
            / str(entry["candidate_id"])
            / "manifest.json",
            manifest,
        )
    return stage2_root, depth8_root, str(entries[0]["candidate_id"])


def _result(classification: str) -> weights.WeightResult:
    return weights.WeightResult(
        classification=classification,
        value=1 + 0j,
        phase=1 + 0j,
        log_abs=0.0,
        sigma_min=0.0 if classification == "uncertain" else 1.0,
        condition_number=1.0,
    )


def test_selects_survivor_scans_all_words_and_resumes(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, parent, identity = _fixture(tmp_path)
    output = tmp_path / "output"
    plan = depth12.plan_continuation(
        stage2, parent, output, expected_count=1
    )
    calls = 0

    def positive(_):
        nonlocal calls
        calls += 1
        return _result("positive")

    monkeypatch.setattr(depth12.weights, "classify_product", positive)
    owner = int(identity[:16], 16) % depth12.WORKERS
    assert depth12.run_worker(
        stage2, parent, output, worker_index=owner
    ) == {"completed": 1, "reused": 0, "operational_errors": 0}
    assert depth12.run_worker(
        stage2, parent, output, worker_index=owner
    ) == {"completed": 0, "reused": 1, "operational_errors": 0}
    summary = depth12.collect_run(output, markdown=output / "summary.md")
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )
    assert plan["candidate_count"] == 1
    assert plan["word_count_per_candidate"] == 7672
    assert calls == 7672
    assert manifest["status"] == depth12.SURVIVOR_STATUS
    assert manifest["tested_words"] == 7672
    assert summary["status_counts"] == {depth12.SURVIVOR_STATUS: 1}


def test_uncertain_uses_exact_fallback_and_stops_on_negative(
    tmp_path: Path, monkeypatch,
) -> None:
    stage2, parent, identity = _fixture(tmp_path)
    output = tmp_path / "output"
    depth12.plan_continuation(stage2, parent, output, expected_count=1)
    monkeypatch.setattr(
        depth12.weights, "classify_product", lambda _: _result("uncertain")
    )
    monkeypatch.setattr(
        depth12.depth8,
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
    owner = int(identity[:16], 16) % depth12.WORKERS
    depth12.run_worker(stage2, parent, output, worker_index=owner)
    manifest = json.loads(
        (output / "candidates" / identity / "manifest.json").read_text()
    )
    assert manifest["status"] == "rejected-negative-exact-fallback"
    assert manifest["tested_words"] == 1
    assert manifest["exact_fallback_count"] == 1
