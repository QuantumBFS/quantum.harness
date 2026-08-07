from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from scripts.hard_goal import build_parser
import spinglass3d.workflow as workflow_module
from spinglass3d.workflow import (
    StageManifest,
    _json_safe,
    _run_stage5_exact,
    _run_stage5_pt,
    _run_stage5_rg,
    _run_stage5_resources,
    _run_stage5_vmcrg,
    classify_stage5,
    load_stage5_config,
    run_stage5,
    validate_stage5_manifest,
)
from vmcrg_ref.artifacts import sha256_file


CONFIG = Path("config/hard_goal/stage5_validation_v1.toml")


def test_stage5_config_freezes_the_required_small_system_matrix() -> None:
    config = load_stage5_config(CONFIG)
    assert config.l2_betas == (0.4, 0.8, 0.9, 1.2)
    assert len(config.l2_seeds) == 4
    assert len(config.l3_seeds) == 2
    assert config.pt_lengths == (6, 9)
    assert config.chain_pairs == 4
    assert config.templates == ("cube", "cross")
    assert config.routes == ("C", "B")
    assert config.chis == (2, 4, 8)
    assert config.backends == ("reference", "available_accelerator")
    assert config.second_rg is False


def test_stage5_config_rejects_a_relaxed_correctness_gate(tmp_path: Path) -> None:
    relaxed = tmp_path / "relaxed-stage5.toml"
    relaxed.write_text(
        CONFIG.read_text(encoding="ascii").replace(
            "l2_absolute = 2e-3",
            "l2_absolute = 2e-2",
        ),
        encoding="ascii",
    )
    with pytest.raises(ValueError, match=r"tolerances\.l2_absolute"):
        load_stage5_config(relaxed)


def test_stage5_exact_section_executes_a_fixed_l2_sample(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = replace(
        load_stage5_config(CONFIG),
        l2_betas=(0.4,),
        l2_seeds=(2026073001,),
        l2_samples=32,
        l3_betas=(),
        l3_seeds=(),
    )
    result = _run_stage5_exact(config)
    assert len(result["l2"]) == 1
    assert result["l2"][0]["beta"] == 0.4
    assert set(result["l2"][0]["metrics"]) == {"energy_per_site", "q2", "q4"}
    serialized = _json_safe(result)
    assert isinstance(serialized, dict)
    assert type(serialized["l2"][0]["passed"]) is bool
    progress = capsys.readouterr().out
    assert "energy_per_site=" in progress
    assert "q2=" in progress
    assert "q4=" in progress


def test_stage5_vmcrg_runs_matched_cube_c_and_b_with_cross_b_fallback() -> None:
    config = replace(
        load_stage5_config(CONFIG),
        chis=(2,),
        vmcrg_disorder_samples=1,
        vmcrg_pool_size=4,
    )
    result = _run_stage5_vmcrg(config)
    assert [
        (cell["template"], cell["route"], cell["chi"])
        for cell in result["cells"]
    ] == [("cube", "C", 2), ("cube", "B", 2), ("cross", "B", 2)]
    cube_c, cube_b, cross_b = result["cells"]
    assert cube_c["tt_initialization_seed"] == cube_b["tt_initialization_seed"]
    assert cube_c["linear_feature_names"] == [
        "q_pair_nn",
        "q_pair_face",
        "q_plaquette",
        "flux_q_pair_nn",
        "flux_q_plaquette",
    ]
    assert cube_b["linear_feature_names"] == []
    assert cross_b["linear_feature_names"] == []


def test_stage5_pt_reports_energy_overlap_swaps_and_round_trips(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = replace(
        load_stage5_config(CONFIG),
        pt_lengths=(3,),
        pt_betas=(0.4, 0.8),
        chain_pairs=1,
        pt_sweeps=1,
    )
    result = _run_stage5_pt(config)
    case = result["unbiased_cases"][0]
    assert isinstance(case["energy_per_site_mean"], float)
    progress = capsys.readouterr().out
    assert "energy_per_site=" in progress
    assert "q2=" in progress
    assert "swap_acceptance=" in progress
    assert "round_trips=" in progress


def test_stage5_rg_reports_cache_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _run_stage5_rg(load_stage5_config(CONFIG))
    assert result["passed"] is True
    progress = capsys.readouterr().out
    assert "incremental_cache_error=" in progress
    assert "bias_cache_error=" in progress


def test_stage5_available_accelerator_runs_the_resource_smoke() -> None:
    result = _run_stage5_resources(load_stage5_config(CONFIG))
    accelerator = result["available_accelerator"]
    if accelerator["status"] == "AVAILABLE":
        assert accelerator["proposals"] > 0
        assert accelerator["maximum_accept_decision_mismatches"] == 0
        assert accelerator["energies_finite"] is True
    else:
        assert accelerator["status"] == "UNAVAILABLE_OPTIONAL"


def _write_stage5_fixture(root: Path, *, omit: str | None = None) -> Path:
    names = ("exact.json", "pt.json", "rg.json", "vmcrg.json", "resources.json")
    artifacts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for name in names:
        artifacts[name.removesuffix(".json")] = name
        if name == omit:
            continue
        path = root / name
        path.write_text(json.dumps({"name": name}) + "\n", encoding="ascii")
        hashes[f"artifact:{name}"] = sha256_file(path)
    manifest = {
        "schema_version": 1,
        "stage": "stage5",
        "classification": "PASS",
        "failed_gates": [],
        "artifacts": artifacts,
        "hashes": hashes,
        "second_rg_enabled": False,
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest) + "\n", encoding="ascii")
    return path


def test_stage5_manifest_requires_every_evidence_file(tmp_path: Path) -> None:
    manifest = _write_stage5_fixture(tmp_path, omit="pt.json")
    with pytest.raises(FileNotFoundError, match="pt.json"):
        validate_stage5_manifest(manifest)


def test_stage5_manifest_rejects_tampering_and_second_rg(tmp_path: Path) -> None:
    manifest = _write_stage5_fixture(tmp_path)
    (tmp_path / "rg.json").write_text("{}\n", encoding="ascii")
    with pytest.raises(ValueError, match="hash"):
        validate_stage5_manifest(manifest)

    second = tmp_path / "second"
    second.mkdir()
    manifest = _write_stage5_fixture(second)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["second_rg_enabled"] = True
    manifest.write_text(json.dumps(payload) + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="second RG"):
        validate_stage5_manifest(manifest)


def test_stage5_classifier_distinguishes_correctness_and_scientific_negative() -> None:
    failed = classify_stage5(
        exact_passed=False,
        pt_passed=True,
        rg_passed=True,
        vmcrg_finite=True,
        tt_improved=True,
        resources_passed=True,
    )
    assert failed["classification"] == "CORRECTNESS_FAILURE"
    assert "exact" in failed["failed_gates"]

    negative = classify_stage5(
        exact_passed=True,
        pt_passed=True,
        rg_passed=True,
        vmcrg_finite=True,
        tt_improved=False,
        resources_passed=True,
    )
    assert negative["classification"] == "SCIENTIFIC_NEGATIVE"
    assert negative["failed_gates"] == ["tt_improvement"]


def test_stage5_refuses_overwrite_before_compute(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        run_stage5(CONFIG, output)


def test_stage5_stops_after_the_first_correctness_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def failed_exact(config: object) -> dict[str, object]:
        calls.append("exact")
        return {"passed": False}

    def unexpected_pt(config: object) -> dict[str, object]:
        calls.append("pt")
        raise AssertionError("PT ran after the exact gate failed")

    monkeypatch.setattr(workflow_module, "_run_stage5_exact", failed_exact)
    monkeypatch.setattr(workflow_module, "_run_stage5_pt", unexpected_pt)
    output = tmp_path / "failed-stage5"
    with pytest.raises(RuntimeError, match="exact correctness gate failed"):
        run_stage5(CONFIG, output)
    assert calls == ["exact"]
    assert not output.exists()


def test_validate_cli_is_registered() -> None:
    args = build_parser().parse_args(
        ["validate", "--config", str(CONFIG), "--output", "/tmp/stage5-test"]
    )
    assert args.stage == "validate"


def test_stage5_manifest_public_projection_accepts_scientific_negative() -> None:
    manifest = StageManifest(
        stage="stage5",
        classification="SCIENTIFIC_NEGATIVE",
        failed_gates=("tt_improvement",),
        artifacts={"exact": "exact.json"},
        hashes={"artifact:exact.json": "a" * 64},
    )
    assert manifest.stage == "stage5"
