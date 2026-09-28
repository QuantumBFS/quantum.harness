from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.unblind_research_test as unblind
from src.production_b_gate import ProductionBGatePaths


def _paths(tmp_path: Path) -> ProductionBGatePaths:
    placeholder = tmp_path / "unused.json"
    return ProductionBGatePaths(
        team_root=tmp_path,
        source_root=tmp_path,
        manifest=placeholder,
        rules=placeholder,
        convergence_audit=placeholder,
        source_preflight=placeholder,
        j2_validation=placeholder,
        production_a_record=placeholder,
        reuse_attestations=placeholder,
        analysis_record=placeholder,
        selection_record=placeholder,
        unblinding_record=tmp_path / "jobs" / "unblinding.json",
    )


def test_explicit_confirmation_is_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        unblind,
        "build_unblinding_record",
        lambda *args, **kwargs: calls.append("called"),
    )
    with pytest.raises(ValueError, match="--confirm-unblind"):
        unblind.create_unblinding_record(
            _paths(tmp_path),
            confirm=False,
            command="test",
            now="2026-07-30T12:00:00+00:00",
        )
    assert calls == []
    assert not (tmp_path / "jobs" / "unblinding.json").exists()


def test_record_is_schema_v2_and_exclusively_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema_version": 2,
        "status": "opened",
        "protocol_version": "1.2",
    }
    monkeypatch.setattr(
        unblind,
        "build_unblinding_record",
        lambda *args, **kwargs: dict(payload),
    )
    paths = _paths(tmp_path)
    first = unblind.create_unblinding_record(
        paths,
        confirm=True,
        command="test --confirm-unblind",
        now="2026-07-30T12:00:00+00:00",
    )
    assert first == payload
    assert json.loads(paths.unblinding_record.read_text()) == payload

    with pytest.raises(FileExistsError, match="already exists"):
        unblind.create_unblinding_record(
            paths,
            confirm=True,
            command="test --confirm-unblind",
            now="2026-07-30T12:01:00+00:00",
        )
    assert json.loads(paths.unblinding_record.read_text()) == payload


def test_gate_failure_creates_no_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(*args, **kwargs):
        raise ValueError("validation status is not eligible")

    monkeypatch.setattr(unblind, "build_unblinding_record", reject)
    paths = _paths(tmp_path)
    with pytest.raises(ValueError, match="not eligible"):
        unblind.create_unblinding_record(
            paths,
            confirm=True,
            command="test --confirm-unblind",
            now="2026-07-30T12:00:00+00:00",
        )
    assert not paths.unblinding_record.exists()
