from __future__ import annotations

import json
from pathlib import Path

import oracle.exterior_deep_survivor as stage3
import oracle.exterior_depth16_survivor as stage4
from oracle.exterior_candidates import candidate_card, candidate_id
from oracle.exterior_structural_rank import rank_survivor_cards, sector_trace_gate


def _write_chain(
    root: Path,
    cards: list[dict[str, object]],
) -> tuple[Path, Path, Path]:
    stage2_root = root / "stage2"
    stage3_root = root / "stage3"
    stage4_root = root / "stage4"
    entries = [
        {
            "candidate_id": candidate_id(card),
            "card_sha256": candidate_id(card),
            "template": card["template"],
            "seed": card["seed"],
            "dimension": card["dimension"],
        }
        for card in cards
    ]
    plan = {
        "run_id": "exterior-survivor-pressure-v1",
        "protocol_hash": "a" * 64,
        "source_commit": "4" * 40,
        "planned": len(entries),
        "candidates": entries,
    }
    (stage2_root / "plan-summary.json").parent.mkdir(parents=True)
    (stage2_root / "plan-summary.json").write_text(
        json.dumps(plan), encoding="utf-8"
    )
    stage3_protocol = stage3._protocol_hash(plan, stage3.RUN_ID)
    stage4_protocol = stage4._protocol_hash(
        plan, stage3_protocol, stage4.RUN_ID
    )
    for entry in entries:
        identity = str(entry["candidate_id"])
        stage2_manifest = stage2_root / "candidates" / identity / "manifest.json"
        stage2_manifest.parent.mkdir(parents=True)
        stage2_manifest.write_text(
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
        stage3_manifest = stage3_root / "candidates" / identity / "manifest.json"
        stage3_manifest.parent.mkdir(parents=True)
        stage3_manifest.write_text(
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
        stage4_manifest = stage4_root / "candidates" / identity / "manifest.json"
        stage4_manifest.parent.mkdir(parents=True)
        stage4_manifest.write_text(
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
                    "tested_words": len(stage4.WORDS),
                    "status": stage4.SURVIVOR_STATUS,
                    "first_failure": None,
                }
            ),
            encoding="utf-8",
        )
    return stage2_root, stage3_root, stage4_root


def test_sector_trace_gate_separates_known_exact5_residue() -> None:
    trace_clean = sector_trace_gate(
        candidate_card(template="exact5-oddcycle-block-pair", seed=13)
    )
    obstructed = sector_trace_gate(
        candidate_card(template="exact5-oddcycle-block-pair", seed=14)
    )

    assert trace_clean["status"] == "trace-clean-depth4"
    assert obstructed["status"] == "sector-trace-obstructed"
    assert obstructed["witness"]["numerator"] < 0
    assert obstructed["witness"]["depth"] <= 4


def test_manifest_rank_puts_trace_clean_exact5_before_induced_control(
    tmp_path: Path,
) -> None:
    exact5 = candidate_card(template="exact5-oddcycle-block-pair", seed=13)
    control = candidate_card(template="exact4-graded-shear-pair", seed=37)
    stage2_root, stage3_root, stage4_root = _write_chain(
        tmp_path, [control, exact5]
    )

    result = rank_survivor_cards(
        stage2_run_dir=stage2_root,
        stage3_run_dir=stage3_root,
        stage4_run_dir=stage4_root,
    )

    assert result["selected"] == 2
    assert [item["template"] for item in result["ranking"]] == [
        "exact5-oddcycle-block-pair",
        "exact4-graded-shear-pair",
    ]
    assert result["ranking"][0]["priority_class"] == "exact5-trace-clean-non-control"
    assert (
        result["ranking"][1]["control_reduction"]["kind"]
        == "known-induced-tn-signed-gauge"
    )
