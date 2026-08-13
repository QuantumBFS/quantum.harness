from __future__ import annotations

import json
from pathlib import Path

import oracle.exterior_deep_survivor as deep
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id


SOURCE_COMMIT = "3" * 40


def test_partition_entries_is_deterministic_disjoint_and_exhaustive() -> None:
    entries = [{"candidate_id": character * 64} for character in "fedcba9870"]

    first = [
        deep.partition_entries(entries, worker_index=index, workers=3)
        for index in range(3)
    ]
    second = [
        deep.partition_entries(list(reversed(entries)), worker_index=index, workers=3)
        for index in range(3)
    ]

    assert first == second
    ids_by_worker = [
        {entry["candidate_id"] for entry in partition} for partition in first
    ]
    assert set.union(*ids_by_worker) == {
        entry["candidate_id"] for entry in entries
    }
    assert not any(
        ids_by_worker[left] & ids_by_worker[right]
        for left in range(3)
        for right in range(left + 1, 3)
    )


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
        "shard": 0,
    }
    stage2 = tmp_path / "stage2"
    output = tmp_path / "stage3"
    (stage2 / "candidates" / identity).mkdir(parents=True)
    (stage2 / "plan-summary.json").write_text(
        json.dumps(
            {
                "run_id": "exterior-survivor-pressure-v1",
                "protocol_hash": "a" * 64,
                "source_commit": SOURCE_COMMIT,
                "candidates": [entry],
            }
        ),
        encoding="utf-8",
    )
    (stage2 / "candidates" / identity / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "exterior-survivor-pressure-v1",
                "protocol_hash": "a" * 64,
                "candidate_id": identity,
                "card_sha256": identity,
                "status": "survivor-pressure-zero-failure",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(deep, "DEEP_WORDS", ((0, 1, 0, 1, 0, 1, 0, 1, 0),))
    monkeypatch.setattr(deep, "candidate_card", lambda *, template, seed: card)

    first = deep.run_worker(
        stage2_run_dir=stage2,
        output_dir=output,
        worker_index=0,
        workers=1,
    )
    manifest_path = output / "candidates" / identity / "manifest.json"
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    second = deep.run_worker(
        stage2_run_dir=stage2,
        output_dir=output,
        worker_index=0,
        workers=1,
    )
    collected = deep.collect_run(stage2_run_dir=stage2, output_dir=output)

    assert first == {"selected": 1, "assigned": 1, "completed": 1, "reused": 0}
    assert second == {"selected": 1, "assigned": 1, "completed": 0, "reused": 1}
    assert manifest_path.read_bytes() == original
    assert manifest["status"] in deep.TERMINAL_STATUSES
    assert manifest["depths"] == [9]
    assert collected["terminal"] == 1
    assert collected["missing"] == 0
