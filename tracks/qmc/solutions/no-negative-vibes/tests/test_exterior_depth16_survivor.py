from __future__ import annotations

import json
from pathlib import Path

import oracle.exterior_deep_survivor as stage3
import oracle.exterior_depth16_survivor as stage4
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


SOURCE_COMMIT = "4" * 40


def _write_parent(
    root: Path,
    entries: list[dict[str, object]],
    *,
    stage3_statuses: list[str],
) -> tuple[Path, Path]:
    stage2 = root / "stage2"
    stage3_root = root / "stage3"
    plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "protocol_hash": "a" * 64,
        "source_commit": SOURCE_COMMIT,
        "planned": len(entries),
        "candidates": entries,
    }
    (stage2 / "plan-summary.json").parent.mkdir(parents=True)
    (stage2 / "plan-summary.json").write_text(json.dumps(plan), encoding="utf-8")
    stage3_protocol = stage3._protocol_hash(plan, stage3.RUN_ID)
    for entry, status in zip(entries, stage3_statuses, strict=True):
        identity = str(entry["candidate_id"])
        stage2_path = stage2 / "candidates" / identity / "manifest.json"
        stage2_path.parent.mkdir(parents=True)
        stage2_path.write_text(
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
        stage3_path = stage3_root / "candidates" / identity / "manifest.json"
        stage3_path.parent.mkdir(parents=True)
        survivor = status == stage3.SURVIVOR_STATUS
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
                    "tested_words": len(stage3.DEEP_WORDS) if survivor else 1,
                    "status": status,
                    "first_failure": (
                        None if survivor else {"classification": "negative"}
                    ),
                }
            ),
            encoding="utf-8",
        )
    return stage2, stage3_root


def test_selects_exactly_depth12_survivor_manifests(tmp_path: Path) -> None:
    entries = [
        {
            "candidate_id": character * 64,
            "card_sha256": character * 64,
            "template": "fixture",
            "seed": index,
            "dimension": 3,
        }
        for index, character in enumerate("ab")
    ]
    stage2, stage3_root = _write_parent(
        tmp_path,
        entries,
        stage3_statuses=[stage3.SURVIVOR_STATUS, "rejected-negative"],
    )

    _, selected, _ = stage4.load_stage3_survivors(stage2, stage3_root)

    assert [entry["candidate_id"] for entry in selected] == ["a" * 64]


def test_run_writes_terminal_manifest_and_resumes_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    card = candidate_card(template=TEMPLATES[0], seed=0)
    identity = candidate_id(card)
    entry = {
        "candidate_id": identity,
        "card_sha256": identity,
        "template": card["template"],
        "seed": card["seed"],
        "dimension": card["dimension"],
    }
    stage2, stage3_root = _write_parent(
        tmp_path, [entry], stage3_statuses=[stage3.SURVIVOR_STATUS]
    )
    output = tmp_path / "stage4"
    monkeypatch.setattr(
        stage4, "WORDS", ((0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0),)
    )
    monkeypatch.setattr(stage4.stage3, "_entry_card", lambda _: card)

    first = stage4.run_worker(
        stage2_run_dir=stage2,
        stage3_run_dir=stage3_root,
        output_dir=output,
        worker_index=0,
        workers=1,
    )
    path = output / "candidates" / identity / "manifest.json"
    original = path.read_bytes()
    second = stage4.run_worker(
        stage2_run_dir=stage2,
        stage3_run_dir=stage3_root,
        output_dir=output,
        worker_index=0,
        workers=1,
    )
    collected = stage4.collect_run(
        stage2_run_dir=stage2,
        stage3_run_dir=stage3_root,
        output_dir=output,
    )

    assert first == {"selected": 1, "assigned": 1, "completed": 1, "reused": 0}
    assert second == {"selected": 1, "assigned": 1, "completed": 0, "reused": 1}
    assert path.read_bytes() == original
    assert json.loads(original)["status"] in stage4.TERMINAL_STATUSES
    assert collected["terminal"] == 1
