from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
import socket
import time

import pytest

import qcontrol.artifacts as artifacts_module
from qcontrol.artifacts import (
    ArtifactConflict,
    ArtifactStore,
    TrialClaimConflict,
)
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig


@pytest.fixture
def config() -> ExperimentConfig:
    return ExperimentConfig(
        run_kind="development",
        system=SystemConfig("one_qubit", 3, 4.0),
        device=DeviceConfig(gap=0.02, shots=1_000, perturbation_seed=7),
        search=SearchConfig("model_hessian", 2, 200),
        trial_seed=11,
    )


def test_failed_publish_preserves_previous_artifact(tmp_path, monkeypatch) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    monkeypatch.setattr(
        store,
        "_replace",
        lambda *_: (_ for _ in ()).throw(OSError("boom")),
    )

    with pytest.raises(OSError, match="boom"):
        store.publish_json("summary.json", {"version": 2})

    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 1}
    assert not list(tmp_path.glob("*.tmp-*"))


def test_failed_post_replace_verification_restores_previous_artifact(
    tmp_path,
    monkeypatch,
) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    monkeypatch.setattr(artifacts_module, "_file_sha256", lambda _: "0" * 64)

    with pytest.raises(ArtifactConflict, match="hash"):
        store.publish_json("summary.json", {"version": 2})

    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 1}


def test_publish_is_canonical_fsynced_and_hash_verified(tmp_path, monkeypatch) -> None:
    fsync_calls: list[int] = []
    real_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    store = ArtifactStore(tmp_path)
    digest = store.publish_json("nested/value.json", {"z": 2, "a": 1})

    content = (tmp_path / "nested/value.json").read_bytes()
    assert content == b'{"a":1,"z":2}\n'
    assert digest == hashlib.sha256(content).hexdigest()
    assert len(fsync_calls) >= 2
    assert store.verify_file("nested/value.json", digest)


def test_immutable_artifact_rejects_different_bytes(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    first = store.publish_json("trials/trial-1.json", {"value": 1}, immutable=True)

    assert (
        store.publish_json("trials/trial-1.json", {"value": 1}, immutable=True)
        == first
    )
    with pytest.raises(ArtifactConflict, match="immutable"):
        store.publish_json("trials/trial-1.json", {"value": 2}, immutable=True)
    assert json.loads((tmp_path / "trials/trial-1.json").read_text()) == {"value": 1}


def test_resume_rejects_changed_config(tmp_path, config) -> None:
    ArtifactStore.create(tmp_path, config)

    with pytest.raises(ArtifactConflict, match="provenance"):
        ArtifactStore.resume(
            tmp_path,
            replace(config, trial_seed=config.trial_seed + 1),
        )


def test_resume_rejects_source_or_lock_change(tmp_path, config, monkeypatch) -> None:
    store = ArtifactStore.create(tmp_path, config)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["provenance"]["uv_lock_sha256"] = "0" * 64
    store.publish_json("manifest.json", manifest)

    with pytest.raises(ArtifactConflict, match="provenance"):
        ArtifactStore.resume(tmp_path, config)


def test_manifest_contains_complete_public_provenance(tmp_path, config) -> None:
    ArtifactStore.create(tmp_path, config)
    provenance = json.loads((tmp_path / "manifest.json").read_text())["provenance"]

    assert provenance["config"] == config.canonical_dict()
    assert set(provenance["source_hashes"])
    assert all(path.startswith("src/qcontrol/") for path in provenance["source_hashes"])
    assert set(provenance["versions"]) == {
        "jax",
        "jaxlib",
        "numpy",
        "python",
        "scipy",
    }
    assert set(provenance["jax"]) == {"platform", "x64_enabled"}
    assert set(provenance["git"]) == {"dirty", "revision"}
    assert len(provenance["uv_lock_sha256"]) == 64
    assert "truth" not in json.dumps(provenance).lower()


def test_live_claim_prevents_duplicate_trial_execution(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    claim = store.claim_trial("trial-1")

    with claim:
        with pytest.raises(TrialClaimConflict, match="claimed"):
            store.claim_trial("trial-1")

    with store.claim_trial("trial-1") as replacement:
        assert replacement.owner["pid"] == os.getpid()


def test_stale_claim_requires_explicit_dead_owner_metadata(tmp_path) -> None:
    store = ArtifactStore(tmp_path, stale_lock_seconds=0.0)
    lock_path = tmp_path / "claims" / "trial-1.lock"
    lock_path.parent.mkdir()
    lock_path.write_text(
        json.dumps(
            {
                "hostname": socket.gethostname(),
                "pid": 999_999_999,
                "started_at": time.time() - 60,
                "token": "prior-owner",
            }
        )
    )

    with store.claim_trial("trial-1") as claim:
        assert claim.owner["token"] != "prior-owner"

    lock_path.write_text(
        json.dumps(
            {
                "hostname": "remote-host",
                "pid": 999_999_999,
                "started_at": time.time() - 60,
                "token": "remote-owner",
            }
        )
    )
    with pytest.raises(TrialClaimConflict, match="cannot prove stale"):
        store.claim_trial("trial-1")


def test_completed_trial_is_verified_before_skip(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_trial("trial-1", {"schema_version": 1, "trial_id": "trial-1"})
    (tmp_path / "trials" / "trial-1.json").write_text('{"tampered":true}\n')

    with pytest.raises(ArtifactConflict, match="hash"):
        store.completed_trial_ids()
