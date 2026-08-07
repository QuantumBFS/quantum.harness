from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.production_v2_manifest import (
    build_production_manifest_v2,
    load_production_amendment,
)


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "configs" / "two_mode_fcs_amendment_20260730.json"
MATRIX = ROOT / "configs" / "burgers_research_matrix.json"
BASE_MANIFEST = ROOT / "results_research_program" / "manifest.json"


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload))
    return path


def test_amendment_rejects_wrong_base_hash(tmp_path: Path) -> None:
    raw = json.loads(AMENDMENT.read_text())
    raw["base"]["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="base manifest hash"):
        load_production_amendment(_write(tmp_path / "amendment.json", raw))


def test_amendment_requires_symmetric_fcs_grid(tmp_path: Path) -> None:
    raw = json.loads(AMENDMENT.read_text())
    raw["fcs_gamma"] = [-0.6, -0.2, 0.0, 0.4, 0.6]
    with pytest.raises(ValueError, match="symmetric"):
        load_production_amendment(_write(tmp_path / "amendment.json", raw))


def test_amendment_is_strict_and_explicit() -> None:
    amendment = load_production_amendment(AMENDMENT)
    assert len(amendment.new_conditions) == 3
    assert amendment.fcs_gamma == (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6)
    assert amendment.reuse == {
        "amp_mu005_up": "amp_mu005_up__convergence__fine",
        "amp_mu005_down": "amp_mu005_down__convergence__fine",
    }
    assert "equilibrium_m0" in amendment.current_condition_ids


def test_v2_manifest_has_frozen_tier_counts(tmp_path: Path) -> None:
    manifest = build_production_manifest_v2(
        base_matrix_path=MATRIX,
        base_manifest_path=BASE_MANIFEST,
        amendment_path=AMENDMENT,
        data_root=tmp_path / "data",
    )
    a = [j for j in manifest["jobs"] if j["stage"] == "production_a"]
    b = [j for j in manifest["jobs"] if j["stage"] == "production_b"]
    assert len(a) == len(b) == 34
    assert sum(j["execution_mode"] == "reuse" for j in a) == 2
    assert sum(j["execution_mode"] == "execute" for j in a) == 32
    assert sum("fcs_logZ" in j["observables"] for j in a) == 7
    assert sum(
        "fcs_logZ" in j["observables"] and j["execution_mode"] == "execute"
        for j in a
    ) == 5
    assert sum("fcs_logZ" in j["observables"] for j in b) == 3
    assert manifest["summary"]["submission_performed"] is False


def test_v2_manifest_does_not_mutate_base_inputs(tmp_path: Path) -> None:
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (MATRIX, BASE_MANIFEST)
    }
    manifest = build_production_manifest_v2(
        base_matrix_path=MATRIX,
        base_manifest_path=BASE_MANIFEST,
        amendment_path=AMENDMENT,
        data_root=tmp_path / "data",
    )
    after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (MATRIX, BASE_MANIFEST)
    }
    assert after == before
    assert manifest["base"]["matrix_sha256"] == before[MATRIX]
    assert manifest["base"]["manifest_sha256"] == before[BASE_MANIFEST]


def test_observable_policy_is_not_inferred_from_prefix(tmp_path: Path) -> None:
    raw = json.loads(AMENDMENT.read_text())
    raw["observable_policy"]["current_condition_ids"].remove("amp_mu020_up")
    custom = _write(tmp_path / "amendment.json", raw)
    with pytest.raises(ValueError, match="current condition IDs"):
        load_production_amendment(custom)


def test_production_b_depends_on_matching_a_row(tmp_path: Path) -> None:
    manifest = build_production_manifest_v2(
        base_matrix_path=MATRIX,
        base_manifest_path=BASE_MANIFEST,
        amendment_path=AMENDMENT,
        data_root=tmp_path / "data",
    )
    for job in manifest["jobs"]:
        if job["stage"] == "production_b":
            assert job["depends_on"] == [
                f"{job['condition_id']}__production_a__v2"
            ]
