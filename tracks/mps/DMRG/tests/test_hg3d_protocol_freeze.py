from __future__ import annotations

import json
from pathlib import Path

import pytest

from hg3d_stage6_fixture import write_passing_stage6_pilot
from spinglass3d.workflow import freeze_production_candidate
from scripts.hard_goal_freeze_protocol import build_parser, main
from vmcrg_ref.artifacts import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


def _passing_pilot_fixture(root: Path) -> Path:
    return write_passing_stage6_pilot(root)


def _sync_artifact(
    manifest: Path,
    payload: dict[str, object],
    name: str,
) -> None:
    if name == "protocol.json":
        value = {
            "second_rg_enabled": payload["second_rg_enabled"],
            "temperatures_by_length": payload["temperatures_by_length"],
            "sampling": payload["sampling"],
            "thresholds": payload["thresholds"],
            "seeds": payload["seeds"],
        }
    else:
        value = payload[name.removesuffix(".json")]
    artifact = manifest.parent / payload["artifact_root"] / name
    artifact.write_bytes(canonical_json_bytes(value))
    payload["artifacts"][name] = sha256_file(artifact)
    payload["hashes"]["artifacts"] = sha256_bytes(
        canonical_json_bytes(payload["artifacts"])
    )
    manifest.write_bytes(canonical_json_bytes(payload))


def test_freeze_rejects_failed_round_trips(tmp_path: Path) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["equilibration"]["round_trips_min"] = 2
    _sync_artifact(manifest, payload, "equilibration.json")
    with pytest.raises(ValueError, match="round trips"):
        freeze_production_candidate(manifest, tmp_path / "candidate.json")


def test_freeze_rejects_a_non_improving_mps(tmp_path: Path) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["selection"]["mps_beats_conditioned_linear"] = False
    _sync_artifact(manifest, payload, "selection.json")
    with pytest.raises(ValueError, match="conditioned linear"):
        freeze_production_candidate(manifest, tmp_path / "candidate.json")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("projected_l45_segment_seconds", 25 * 3600, "24-hour"),
        ("projected_peak_memory_bytes", 12 * 1024**3, "memory margin"),
        ("reserved_output_bytes", 5 * 1024**3, "output margin"),
    ),
)
def test_freeze_rejects_resource_or_margin_failures(
    tmp_path: Path,
    field: str,
    value: int,
    message: str,
) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["resources"][field] = value
    _sync_artifact(manifest, payload, "resources.json")
    with pytest.raises(ValueError, match=message):
        freeze_production_candidate(manifest, tmp_path / "candidate.json")


def test_freeze_rejects_provisional_thresholds(tmp_path: Path) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["thresholds"]["provisional"] = True
    _sync_artifact(manifest, payload, "protocol.json")
    with pytest.raises(ValueError, match="provisional"):
        freeze_production_candidate(manifest, tmp_path / "candidate.json")


@pytest.mark.parametrize("tamper", ("artifact", "config", "design", "source"))
def test_freeze_rehashes_complete_stage6_evidence(
    tmp_path: Path,
    tamper: str,
) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    if tamper == "artifact":
        (tmp_path / payload["artifact_root"] / "power.json").write_text(
            '{"tampered":true}\n',
            encoding="ascii",
        )
    elif tamper in {"config", "design"}:
        payload["provenance"][f"{tamper}_sha256"] = "0" * 64
        payload["hashes"][tamper] = "0" * 64
        manifest.write_bytes(canonical_json_bytes(payload))
    else:
        source_name = next(iter(payload["provenance"]["source_sha256"]))
        payload["provenance"]["source_sha256"][source_name] = "0" * 64
        manifest.write_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="hash|inventory|provenance"):
        freeze_production_candidate(manifest, tmp_path / "candidate.json")


def test_freeze_rejects_self_consistent_artifact_manifest_disagreement(
    tmp_path: Path,
) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    artifact = tmp_path / payload["artifact_root"] / "selection.json"
    artifact.write_bytes(
        canonical_json_bytes(
            {
                **payload["selection"],
                "chi": 8,
            }
        )
    )
    payload["artifacts"]["selection.json"] = sha256_file(artifact)
    payload["hashes"]["artifacts"] = sha256_bytes(
        canonical_json_bytes(payload["artifacts"])
    )
    manifest.write_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="artifact.*selection|selection.*artifact"):
        freeze_production_candidate(manifest, tmp_path / "candidate.json")


def test_freeze_writes_an_immutable_evidence_bound_candidate(tmp_path: Path) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    output = tmp_path / "candidate.json"
    candidate = freeze_production_candidate(manifest, output)
    assert candidate["classification"] == "PASS"
    assert candidate["pilot_manifest_sha256"] == sha256_file(manifest)
    assert candidate["selection"] == {
        "route": "C",
        "template": "cube",
        "chi": 4,
        "mps_beats_conditioned_linear": True,
        "held_out_metric": "uniform_target_tv",
    }
    with pytest.raises(FileExistsError, match="overwrite"):
        freeze_production_candidate(manifest, output)


def test_freeze_cli_uses_explicit_pilot_and_output_paths(tmp_path: Path) -> None:
    manifest = _passing_pilot_fixture(tmp_path)
    output = tmp_path / "cli-candidate.json"
    args = build_parser().parse_args(
        ["--pilot", str(manifest), "--output", str(output)]
    )
    assert args.pilot == manifest
    assert args.output == output
    assert main(["--pilot", str(manifest), "--output", str(output)]) == 0
    assert output.is_file()
