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
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="unit",
    )
    path = tmp_path / "specs" / "shard-00.json"
    spec = json.loads(path.read_text())
    spec["candidates"] = spec["candidates"][:1]
    path.write_text(json.dumps(spec), encoding="utf-8")
    entry = spec["candidates"][0]
    card = candidate_card(template=entry["template"], seed=entry["seed"])
    identity = candidate_id(card)
    manifest_path = tmp_path / "candidates" / identity / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    terminal = thin.screen_card(
        card,
        source_commit=SOURCE_COMMIT,
        run_id="unit",
        protocol_hash=spec["protocol_hash"],
        machine_role="wsl",
        shard=0,
    )
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
            "machine_role": "wsl" if first["shard"] < 14 else "cpu",
            "shard": first["shard"],
            "oracle": "oracle.weights.classify_product",
            "oracle_version": thin.ORACLE_VERSION,
            "word_order": thin.WORD_ORDER,
            "depths": [2, 3, 4],
            "minimum_sigma_min_I_plus_D": 0.5,
            "minimum_sigma_word_indices": [0, 1],
            "runtime_seconds": 0.1,
            "first_failure": None,
        }),
        encoding="utf-8",
    )

    result = thin.collect_run(tmp_path)

    assert result["planned"] == 2304
    assert result["terminal"] == 1
    assert result["missing"] == 2303
    assert result["scientific_counts"]["survivor-shallow-zero-failure"] == 1


def test_smoke_namespace_cannot_poison_production_manifest(
    tmp_path: Path,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    smoke_path = tmp_path / "specs" / "smoke-wsl.json"
    smoke = json.loads(smoke_path.read_text())
    smoke["candidates"] = smoke["candidates"][:1]
    smoke_path.write_text(json.dumps(smoke), encoding="utf-8")
    entry = smoke["candidates"][0]
    production_path = tmp_path / "specs" / f"shard-{entry['shard']:02d}.json"
    production = json.loads(production_path.read_text())
    production["candidates"] = [entry]
    production_path.write_text(json.dumps(production), encoding="utf-8")

    assert thin.run_spec(smoke_path)["completed"] == 1
    assert thin.run_spec(production_path)["completed"] == 1
    assert (
        tmp_path / "smoke" / "candidates" / entry["candidate_id"] / "manifest.json"
    ).is_file()
    assert (
        tmp_path / "candidates" / entry["candidate_id"] / "manifest.json"
    ).is_file()


def test_run_cli_returns_nonzero_when_any_operational_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        thin,
        "run_spec",
        lambda _: {"completed": 0, "reused": 0, "errors": 1},
    )
    assert thin.main(["run", "ignored.json"]) != 0
    assert json.loads(capsys.readouterr().out)["errors"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_commit", "2" * 40),
        ("run_id", "edited-run"),
        ("oracle_version", "edited-oracle"),
        ("word_order", "edited-order"),
        ("depths", [2, 3]),
    ),
)
def test_run_spec_recomputes_protocol_hash_and_rejects_tampering(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    path = tmp_path / "specs" / "shard-00.json"
    spec = json.loads(path.read_text())
    spec[field] = value
    path.write_text(json.dumps(spec), encoding="utf-8")

    with pytest.raises(RuntimeError, match="protocol"):
        thin.run_spec(path)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("shard", 75),
        ("machine_role", "cpu"),
        ("dimension", 99),
        ("card_sha256", "f" * 64),
    ),
)
def test_run_spec_rejects_wrong_owner_role_or_reconstructed_card(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    path = tmp_path / "specs" / "shard-00.json"
    spec = json.loads(path.read_text())
    assert spec["candidates"]
    spec["candidates"] = spec["candidates"][:1]
    if field in {"shard", "machine_role"}:
        spec[field] = value
    else:
        spec["candidates"][0][field] = value
    path.write_text(json.dumps(spec), encoding="utf-8")

    with pytest.raises(RuntimeError, match="owner|role|card|dimension|protocol"):
        thin.run_spec(path)


def test_survivor_manifest_and_collection_preserve_promotion_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    plan = json.loads((tmp_path / "plan-summary.json").read_text())
    entry = plan["candidates"][0]
    card = candidate_card(template=entry["template"], seed=entry["seed"])
    sigma = iter([0.9, 0.3, 0.7, 0.6])
    monkeypatch.setattr(
        thin.weights,
        "classify_product",
        lambda _: WeightResult(
            classification="positive",
            value=1.0,
            phase=1.0,
            log_abs=0.0,
            sigma_min=next(sigma),
            condition_number=2.0,
        ),
    )
    manifest = thin.screen_card(
        card,
        source_commit=SOURCE_COMMIT,
        run_id="full",
        protocol_hash=plan["protocol_hash"],
        machine_role="wsl" if entry["shard"] < 14 else "cpu",
        shard=entry["shard"],
        words=((0, 1), (1, 0), (0, 1, 0), (0, 1, 0, 1)),
    )
    assert manifest["minimum_sigma_min_I_plus_D"] == pytest.approx(0.3)
    assert manifest["minimum_sigma_word_indices"] == [1, 0]
    path = tmp_path / "candidates" / entry["candidate_id"] / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    markdown = tmp_path / "ROUND_SUMMARY.md"

    result = thin.collect_run(tmp_path, markdown=markdown)

    assert result["survivors"] == [{
        "candidate_id": entry["candidate_id"],
        "template": entry["template"],
        "dimension": entry["dimension"],
        "tested_words": 4,
        "minimum_sigma_min_I_plus_D": pytest.approx(0.3),
        "minimum_sigma_word_indices": [1, 0],
    }]
    assert str(entry["dimension"]) in result["by_dimension"]
    assert entry["template"] in result["by_template"]
    assert result["first_failures"] == []
    assert result["machine_execution"][0]["candidates"] == 1
    rendered = markdown.read_text(encoding="utf-8")
    for heading in (
        "## By dimension",
        "## By template",
        "## First failures",
        "## Shallow survivors",
        "## Machine execution",
    ):
        assert heading in rendered
    assert entry["candidate_id"] in rendered


def test_collection_validates_ownership_detects_duplicates_and_clears_retries(
    tmp_path: Path,
) -> None:
    thin.plan_run(
        run_dir=tmp_path,
        source_commit=SOURCE_COMMIT,
        run_id="full",
    )
    plan = json.loads((tmp_path / "plan-summary.json").read_text())
    entry = plan["candidates"][0]
    role = "wsl" if entry["shard"] < 14 else "cpu"
    manifest = {
        "schema_version": thin.SCHEMA_VERSION,
        "run_id": "full",
        "protocol_hash": plan["protocol_hash"],
        "source_commit": SOURCE_COMMIT,
        "candidate_id": entry["candidate_id"],
        "card_sha256": entry["card_sha256"],
        "status": "rejected-negative",
        "tested_words": 1,
        "template": entry["template"],
        "dimension": entry["dimension"],
        "machine_role": role,
        "shard": entry["shard"],
        "runtime_seconds": 0.1,
        "oracle": "oracle.weights.classify_product",
        "oracle_version": thin.ORACLE_VERSION,
        "word_order": thin.WORD_ORDER,
        "depths": [2, 3, 4],
        "minimum_sigma_min_I_plus_D": 0.5,
        "minimum_sigma_word_indices": [0, 1],
        "first_failure": {
            "classification": "negative",
            "word_indices": [0, 1],
            "depth": 2,
            "sigma_min_I_plus_D": 0.5,
            "condition_number_I_plus_D": 2.0,
        },
    }
    directory = tmp_path / "candidates" / entry["candidate_id"]
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "manifest-returned.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.json").write_text(
        json.dumps({"errors": [{"candidate_id": entry["candidate_id"]}]}),
        encoding="utf-8",
    )

    result = thin.collect_run(tmp_path)

    assert result["operational_error"] == 0
    assert result["unresolved_operational_candidate_ids"] == []
    assert result["historical_operational_attempts"] == 1
    assert result["duplicate"] == 1

    manifest["machine_role"] = "cpu" if role == "wsl" else "wsl"
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    stale = thin.collect_run(tmp_path)
    assert stale["terminal"] == 0
    assert stale["stale"] >= 1


def _write_parent_terminal_manifests(
    parent: Path,
    *,
    survivors: set[int],
) -> dict[str, object]:
    """Hand-build a complete Stage-1 terminal fixture for survivor planning."""

    thin.plan_run(run_dir=parent, source_commit=SOURCE_COMMIT, run_id="parent")
    plan = json.loads((parent / "plan-summary.json").read_text(encoding="utf-8"))
    for index, entry in enumerate(plan["candidates"]):
        role = "wsl" if entry["shard"] < 14 else "cpu"
        status = (
            "survivor-shallow-zero-failure"
            if index in survivors
            else "rejected-negative"
        )
        manifest = {
            "schema_version": thin.SCHEMA_VERSION,
            "run_id": "parent",
            "protocol_hash": plan["protocol_hash"],
            "source_commit": SOURCE_COMMIT,
            "candidate_id": entry["candidate_id"],
            "card_sha256": entry["card_sha256"],
            "status": status,
            "tested_words": 22 if status.startswith("survivor") else 1,
            "template": entry["template"],
            "dimension": entry["dimension"],
            "machine_role": role,
            "shard": entry["shard"],
            "runtime_seconds": 0.1,
            "oracle": "oracle.weights.classify_product",
            "oracle_version": thin.ORACLE_VERSION,
            "word_order": thin.WORD_ORDER,
            "depths": [2, 3, 4],
            "minimum_sigma_min_I_plus_D": 0.5,
            "minimum_sigma_word_indices": [0, 1],
            "first_failure": None if status.startswith("survivor") else {
                "classification": "negative",
                "word_indices": [0, 1],
                "depth": 2,
                "sigma_min_I_plus_D": 0.5,
                "condition_number_I_plus_D": 2.0,
            },
        }
        path = parent / "candidates" / entry["candidate_id"] / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
    return plan


def test_pressure_words_are_complete_and_ordered() -> None:
    # A missing mixed word, or an added pure repeat, would weaken the pressure run.
    words = thin.mixed_words(2, depths=thin.PRESSURE_DEPTHS)
    assert len(words) == len(set(words)) == 472
    assert words == tuple(sorted(words, key=lambda word: (len(word), word)))
    for depth in thin.PRESSURE_DEPTHS:
        at_depth = [word for word in words if len(word) == depth]
        assert len(at_depth) == 2**depth - 2
        assert (0,) * depth not in at_depth
        assert (1,) * depth not in at_depth


def test_survivor_plan_selects_only_validated_parent_survivors(tmp_path: Path) -> None:
    # Accepting rejected cards here would change a Stage-2 scientific claim.
    parent = tmp_path / "stage-1"
    parent_plan = _write_parent_terminal_manifests(parent, survivors={0, 37})

    summary = thin.plan_survivor_run(
        parent_run_dir=parent,
        run_dir=tmp_path / "stage-2",
        source_commit=SOURCE_COMMIT,
        run_id="pressure",
    )

    stage2 = json.loads(
        (tmp_path / "stage-2" / "plan-summary.json").read_text(encoding="utf-8")
    )
    selected = [parent_plan["candidates"][index] for index in (0, 37)]
    assert summary["planned"] == 2
    assert stage2["candidates"] == selected
    assert stage2["depths"] == [5, 6, 7, 8]
    assert stage2["survivor_status"] == "survivor-pressure-zero-failure"
    assert stage2["parent_run_id"] == "parent"
    assert stage2["parent_protocol_hash"] == parent_plan["protocol_hash"]


@pytest.mark.parametrize("breakage", ("missing", "stale", "duplicate", "unresolved"))
def test_survivor_planning_fails_closed_on_incomplete_parent_collection(
    tmp_path: Path,
    breakage: str,
) -> None:
    # Treating operational uncertainty as a survivor would promote an unvalidated card.
    parent = tmp_path / "stage-1"
    plan = _write_parent_terminal_manifests(parent, survivors={0})
    entry = plan["candidates"][1]
    manifest_path = parent / "candidates" / entry["candidate_id"] / "manifest.json"
    if breakage == "missing":
        manifest_path.unlink()
    elif breakage == "stale":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["machine_role"] = "cpu" if manifest["machine_role"] == "wsl" else "wsl"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif breakage == "duplicate":
        (manifest_path.parent / "manifest-returned.json").write_text(
            manifest_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        logs = parent / "logs"
        logs.mkdir()
        (logs / "retry.json").write_text(
            json.dumps({"errors": [{"candidate_id": entry["candidate_id"]}]}),
            encoding="utf-8",
        )

    with pytest.raises(RuntimeError, match="missing|stale|duplicate|unresolved|parent"):
        thin.plan_survivor_run(
            parent_run_dir=parent,
            run_dir=tmp_path / "stage-2",
            source_commit=SOURCE_COMMIT,
        )


@pytest.mark.parametrize(
    "field",
    ("run_id", "protocol_hash", "source_commit", "card_sha256", "status"),
)
def test_survivor_planning_rejects_tampered_parent_provenance(
    tmp_path: Path,
    field: str,
) -> None:
    # Parent identity tampering must not be able to manufacture a pressure candidate.
    parent = tmp_path / "stage-1"
    plan = _write_parent_terminal_manifests(parent, survivors={0})
    if field in {"run_id", "protocol_hash", "source_commit"}:
        path = parent / "plan-summary.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[field] = "2" * 40 if field == "source_commit" else "tampered"
    else:
        entry = plan["candidates"][0]
        path = parent / "candidates" / entry["candidate_id"] / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[field] = "f" * 64 if field == "card_sha256" else "rejected-negative"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="hash|protocol|stale|parent|card"):
        thin.plan_survivor_run(
            parent_run_dir=parent,
            run_dir=tmp_path / "stage-2",
            source_commit=SOURCE_COMMIT,
        )


def test_pressure_protocol_binds_parent_and_stage_one_plan_remains_thin(
    tmp_path: Path,
) -> None:
    # Omitting provenance or changing thin defaults would permit cross-run substitution.
    parent = tmp_path / "stage-1"
    _write_parent_terminal_manifests(parent, survivors={0})
    thin.plan_survivor_run(
        parent_run_dir=parent,
        run_dir=tmp_path / "stage-2",
        source_commit=SOURCE_COMMIT,
    )
    pressure = json.loads(
        (tmp_path / "stage-2" / "plan-summary.json").read_text(encoding="utf-8")
    )
    spec = json.loads((tmp_path / "stage-2" / "specs" / "shard-00.json").read_text())
    assert pressure["plan_hash"] != pressure["parent_plan_hash"]
    assert pressure["parent_plan_hash"] in thin._canonical_json(pressure)
    assert spec["depths"] == [5, 6, 7, 8]
    assert spec["parent_protocol_hash"] == pressure["parent_protocol_hash"]

    thin.plan_run(run_dir=tmp_path / "thin", source_commit=SOURCE_COMMIT, run_id="full")
    thin_plan = json.loads((tmp_path / "thin" / "plan-summary.json").read_text())
    thin_spec = json.loads((tmp_path / "thin" / "specs" / "shard-00.json").read_text())
    assert thin_plan["depths"] == [2, 3, 4]
    assert thin_spec["depths"] == [2, 3, 4]
    assert "parent_plan_hash" not in thin_plan
    assert "parent_protocol_hash" not in thin_spec


@pytest.mark.parametrize(
    ("classifications", "status", "tested"),
    (
        (["positive"] * 472, "survivor-pressure-zero-failure", 472),
        (["positive", "negative"], "rejected-negative", 2),
        (["complex"], "rejected-complex", 1),
        (["uncertain"], "uncertain-high-precision", 1),
    ),
)
def test_pressure_run_uses_hash_bound_words_and_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    classifications: list[str],
    status: str,
    tested: int,
) -> None:
    # Falling back to shallow words or status would mislabel the Stage-2 result.
    parent = tmp_path / "stage-1"
    _write_parent_terminal_manifests(parent, survivors={0})
    thin.plan_survivor_run(
        parent_run_dir=parent,
        run_dir=tmp_path / "stage-2",
        source_commit=SOURCE_COMMIT,
    )
    spec_path = tmp_path / "stage-2" / "specs" / "shard-00.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not spec["candidates"]:
        spec_path = next((tmp_path / "stage-2" / "specs").glob("shard-*.json"))
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["candidates"] = spec["candidates"][:1]
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    iterator = iter(classifications)
    monkeypatch.setattr(thin.weights, "classify_product", lambda _: _result(next(iterator)))

    assert thin.run_spec(spec_path) == {"completed": 1, "reused": 0, "errors": 0}
    entry = spec["candidates"][0]
    manifest = json.loads(
        (tmp_path / "stage-2" / "candidates" / entry["candidate_id"] / "manifest.json").read_text()
    )
    assert manifest["status"] == status
    assert manifest["planned_words"] == 472
    assert manifest["tested_words"] == tested
