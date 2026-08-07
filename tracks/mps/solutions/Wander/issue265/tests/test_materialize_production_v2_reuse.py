from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import scripts.materialize_production_v2_reuse as materializer
from src.production_reuse_gate import ALLOWED_REUSE


@dataclass(frozen=True)
class _FakeAttestation:
    target_job_id: str
    source_job_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "target_job_id": self.target_job_id,
            "source_job_id": self.source_job_id,
            "status": "accepted",
        }


def _manifest() -> dict:
    return {
        "jobs": [
            {
                "job_id": target,
                "execution_mode": "reuse",
                "reuse_from_job_id": source,
            }
            for target, source in ALLOWED_REUSE.items()
        ]
    }


def _inputs(tmp_path: Path) -> dict[str, object]:
    data_root = tmp_path / "convergence"
    data_root.mkdir(exist_ok=True)
    validation = {"records": []}
    audit = {"accepted": True, "records": []}
    for source in ALLOWED_REUSE.values():
        (data_root / f"{source}.npz").write_bytes(b"npz")
        (data_root / f"{source}.run.json").write_text(
            json.dumps({"status": "complete", "job_id": source})
        )
    return {
        "v2_manifest": _manifest(),
        "base_manifest": {"jobs": []},
        "data_root": data_root,
        "dataset_validation": validation,
        "convergence_audit": audit,
    }


def test_materializer_accepts_exactly_the_two_registered_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Path, str]] = []

    def fake_validate(target, **kwargs):
        source = str(target["reuse_from_job_id"])
        calls.append(
            (
                str(target["job_id"]),
                Path(kwargs["dataset_path"]),
                str(kwargs["run_summary"]["job_id"]),
            )
        )
        return _FakeAttestation(str(target["job_id"]), source)

    monkeypatch.setattr(materializer, "validate_reuse", fake_validate)
    payload = materializer.materialize_reuse_attestations(
        **_inputs(tmp_path)
    )
    assert set(payload) == {"_provenance", *ALLOWED_REUSE}
    assert set(ALLOWED_REUSE) == {
        target for target, _, _ in calls
    }
    assert {
        path.name for _, path, _ in calls
    } == {f"{source}.npz" for source in ALLOWED_REUSE.values()}
    assert all(
        payload[target]["status"] == "accepted"
        for target in ALLOWED_REUSE
    )
    assert payload == materializer.materialize_reuse_attestations(
        **_inputs(tmp_path)
    )


def test_materializer_is_all_or_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fail_second(target, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("second reuse invalid")
        return _FakeAttestation(
            str(target["job_id"]),
            str(target["reuse_from_job_id"]),
        )

    monkeypatch.setattr(materializer, "validate_reuse", fail_second)
    output = tmp_path / "jobs" / "reuse.json"
    with pytest.raises(ValueError, match="second reuse invalid"):
        materializer.write_reuse_attestations(
            output=output,
            **_inputs(tmp_path),
        )
    assert not output.exists()
