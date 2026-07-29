from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

import oracle.exterior_thin_scan as thin
from oracle.exterior_candidates import TEMPLATES, candidate_card, candidate_id
from oracle.weights import WeightResult


SOURCE_COMMIT = "1" * 40


def _result(classification: str) -> WeightResult:
    phase = -1.0 if classification == "negative" else 1.0
    if classification == "complex":
        phase = 1.0j
    if classification == "zero":
        phase = 0.0
    return WeightResult(
        classification=classification,
        value=complex(phase),
        phase=complex(phase),
        log_abs=0.25,
        sigma_min=0.5,
        condition_number=4.0,
    )


def test_mixed_words_are_depth_then_lexicographic_and_exclude_pure_repeats() -> None:
    words = thin.mixed_words(2)
    assert len(words) == 22
    assert words == tuple(
        sorted(words, key=lambda word: (len(word), word))
    )
    assert all(len(set(word)) >= 2 for word in words)
    assert thin.mixed_words(3) == tuple(
        word
        for depth in (2, 3, 4)
        for word in __import__("itertools").product(range(3), repeat=depth)
        if len(set(word)) >= 2
    )
    assert len(thin.mixed_words(3)) == 108


def test_screen_card_uses_right_append_order_and_frozen_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = candidate_card(template=TEMPLATES[0], seed=0)
    seen: list[np.ndarray] = []

    def classify(product: np.ndarray) -> WeightResult:
        seen.append(product.copy())
        return _result("negative")

    atoms = (
        np.asarray([[1.0, 2.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        np.asarray([[3.0, 0.0, 0.0], [4.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
    )
    monkeypatch.setattr(thin, "float_atoms_from_card", lambda _: atoms)
    monkeypatch.setattr(thin.weights, "classify_product", classify)
    manifest = thin.screen_card(
        card,
        source_commit=SOURCE_COMMIT,
        run_id="unit",
        words=((0, 1, 0),),
    )

    np.testing.assert_array_equal(seen[0], atoms[0] @ atoms[1] @ atoms[0])
    assert manifest["status"] == "rejected-negative"
    assert manifest["tested_words"] == 1
    assert manifest["first_failure"]["word_indices"] == [0, 1, 0]


@pytest.mark.parametrize(
    ("classifications", "status", "tested"),
    (
        (["negative", "positive"], "rejected-negative", 1),
        (["positive", "complex", "positive"], "rejected-complex", 2),
        (["zero", "uncertain", "positive"], "uncertain-high-precision", 2),
        (
            ["zero", "positive", "positive"],
            "survivor-shallow-zero-failure",
            3,
        ),
    ),
)
def test_screen_card_early_stop_state_machine(
    monkeypatch: pytest.MonkeyPatch,
    classifications: list[str],
    status: str,
    tested: int,
) -> None:
    iterator = iter(classifications)
    calls = 0

    def classify(_: np.ndarray) -> WeightResult:
        nonlocal calls
        calls += 1
        return _result(next(iterator))

    monkeypatch.setattr(thin.weights, "classify_product", classify)
    card = candidate_card(template=TEMPLATES[0], seed=1)
    manifest = thin.screen_card(
        card,
        source_commit=SOURCE_COMMIT,
        run_id="unit",
        words=((0, 1), (1, 0), (0, 1, 0)),
    )

    assert manifest["status"] == status
    assert manifest["tested_words"] == tested == calls
    assert manifest["oracle"] == "oracle.weights.classify_product"
    assert manifest["candidate_id"] == candidate_id(card)
    assert manifest["card_sha256"] == candidate_id(card)
    if status == "survivor-shallow-zero-failure":
        assert manifest["first_failure"] is None
    else:
        failure = manifest["first_failure"]
        assert failure["classification"] == classifications[tested - 1]
        assert failure["exact_card_sha256"] == candidate_id(card)
        assert {
            "phase_real",
            "phase_imag",
            "log_abs_weight",
            "sigma_min_I_plus_D",
            "condition_number_I_plus_D",
            "atoms_float_projection",
        } <= set(failure)


def test_shard_owner_uses_first_sixteen_hex_digits() -> None:
    identity = "0123456789abcdef" + "f" * 48
    assert thin.shard_owner(identity) == int(identity[:16], 16) % 76


def test_plan_has_exact_first_tranche_and_disjoint_owners(tmp_path: Path) -> None:
    summary = thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    planned = json.loads((tmp_path / "plan-summary.json").read_text())
    ids = [entry["candidate_id"] for entry in planned["candidates"]]
    owners = [entry["shard"] for entry in planned["candidates"]]

    assert summary["planned"] == 9 * 256 == 2304
    assert len(ids) == len(set(ids)) == 2304
    assert all(owner == thin.shard_owner(identity) for identity, owner in zip(ids, owners))
    assert set(owners) <= set(range(76))
    assert not ({owner for owner in owners if owner < 14} & {owner for owner in owners if owner >= 14})
    assert len(list((tmp_path / "specs").glob("shard-*.json"))) == 76
    assert not list(tmp_path.rglob("*.tmp"))


def test_smoke_plan_has_one_candidate_per_dimension_and_both_roles(
    tmp_path: Path,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
        smoke_count=4,
    )
    wsl = json.loads((tmp_path / "specs" / "smoke-wsl.json").read_text())
    cpu = json.loads((tmp_path / "specs" / "smoke-cpu.json").read_text())
    entries = wsl["candidates"] + cpu["candidates"]

    assert Counter(entry["dimension"] for entry in entries) == {
        3: 1,
        4: 1,
        5: 1,
        6: 1,
    }
    assert len(wsl["candidates"]) == len(cpu["candidates"]) == 2
    assert all(entry["shard"] < 14 for entry in wsl["candidates"])
    assert all(entry["shard"] >= 14 for entry in cpu["candidates"])
    assert wsl["run_id"] == cpu["run_id"] == "exterior-thin-first-v1-smoke"


def test_run_spec_resumes_matching_manifest_and_rejects_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = candidate_card(template=TEMPLATES[0], seed=3)
    identity = candidate_id(card)
    spec = {
        "schema_version": thin.SCHEMA_VERSION,
        "run_id": "unit",
        "protocol_hash": "a" * 64,
        "source_commit": SOURCE_COMMIT,
        "machine_role": "wsl",
        "shard": thin.shard_owner(identity),
        "artifact_root": "..",
        "candidates": [{
            "template": card["template"],
            "seed": card["seed"],
            "dimension": card["dimension"],
            "candidate_id": identity,
            "card_sha256": identity,
            "shard": thin.shard_owner(identity),
        }],
    }
    specs = tmp_path / "specs"
    specs.mkdir()
    path = specs / "unit.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    manifest_path = tmp_path / "candidates" / identity / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    terminal = {
        "schema_version": thin.SCHEMA_VERSION,
        "run_id": "unit",
        "protocol_hash": "a" * 64,
        "source_commit": SOURCE_COMMIT,
        "candidate_id": identity,
        "card_sha256": identity,
        "status": "rejected-negative",
    }
    manifest_path.write_text(json.dumps(terminal), encoding="utf-8")
    monkeypatch.setattr(
        thin,
        "screen_card",
        lambda *args, **kwargs: pytest.fail("matching manifest must be reused"),
    )

    assert thin.run_spec(path) == {"completed": 0, "reused": 1, "errors": 0}

    terminal["source_commit"] = "2" * 40
    manifest_path.write_text(json.dumps(terminal), encoding="utf-8")
    with pytest.raises(RuntimeError, match="stale|mismatch"):
        thin.run_spec(path)
    assert json.loads(manifest_path.read_text())["source_commit"] == "2" * 40


def test_run_spec_records_operational_error_without_scientific_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    spec_path = tmp_path / "specs" / "shard-00.json"
    spec = json.loads(spec_path.read_text())
    spec["candidates"] = spec["candidates"][:1]
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    identity = spec["candidates"][0]["candidate_id"]
    monkeypatch.setattr(
        thin,
        "screen_card",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )

    result = thin.run_spec(spec_path)

    assert result == {"completed": 0, "reused": 0, "errors": 1}
    assert not (tmp_path / "candidates" / identity / "manifest.json").exists()
    logs = list((tmp_path / "logs").glob("*.json"))
    assert len(logs) == 1
    assert json.loads(logs[0].read_text())["errors"][0]["error"] == "boom"


def test_collect_reports_missing_and_status_counts(tmp_path: Path) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    plan = json.loads((tmp_path / "plan-summary.json").read_text())
    first = plan["candidates"][0]
    path = tmp_path / "candidates" / first["candidate_id"] / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "schema_version": thin.SCHEMA_VERSION,
            "run_id": "full",
            "protocol_hash": plan["protocol_hash"],
            "source_commit": SOURCE_COMMIT,
            "candidate_id": first["candidate_id"],
            "card_sha256": first["card_sha256"],
            "status": "survivor-shallow-zero-failure",
            "tested_words": 22,
            "template": first["template"],
            "dimension": first["dimension"],
            "first_failure": None,
        }),
        encoding="utf-8",
    )

    result = thin.collect_run(tmp_path)

    assert result["planned"] == 2304
    assert result["terminal"] == 1
    assert result["missing"] == 2303
    assert result["scientific_counts"]["survivor-shallow-zero-failure"] == 1
