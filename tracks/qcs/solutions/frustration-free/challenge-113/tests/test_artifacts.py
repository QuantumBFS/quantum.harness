from __future__ import annotations

from dataclasses import replace
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import threading
import time

import pytest

import qcontrol.artifacts as artifacts_module
from qcontrol.artifacts import (
    ArtifactConflict,
    ArtifactDurabilityError,
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


def _claim_worker(root: str, queue: multiprocessing.Queue) -> None:
    store = ArtifactStore(root, stale_lock_seconds=0.0)
    try:
        with store.claim_trial("trial-race"):
            queue.put(("acquired", os.getpid()))
            time.sleep(0.4)
    except TrialClaimConflict:
        queue.put(("conflict", os.getpid()))


def _initialize_worker(
    root: str,
    trial_seed: int,
    queue: multiprocessing.Queue,
) -> None:
    store = ArtifactStore(root)
    plan = {
        "run_kind": "development",
        "schema_version": 1,
        "trials": [{"seed": trial_seed}],
    }
    try:
        store.initialize_run({"seed": trial_seed}, plan)
    except ArtifactConflict:
        queue.put(("conflict", trial_seed))
    else:
        queue.put(("winner", trial_seed))


def _crash_claim_worker(root: str, queue: multiprocessing.Queue) -> None:
    store = ArtifactStore(root)
    claim = store.claim_trial("trial-crash")
    queue.put((claim.owner, claim.lock_path))
    queue.close()
    queue.join_thread()
    os._exit(0)


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
    assert set(provenance["git"]) == {
        "dirty",
        "revision",
        "worktree_sha256",
    }
    assert len(provenance["uv_lock_sha256"]) == 64
    assert "truth" not in json.dumps(provenance).lower()


def test_live_claim_prevents_duplicate_trial_execution(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    claim = store.claim_trial("trial-1")

    with claim:
        with pytest.raises(TrialClaimConflict, match="kernel lock"):
            store.claim_trial("trial-1")

    with store.claim_trial("trial-1") as replacement:
        assert replacement.owner["pid"] == os.getpid()


def test_stale_claim_requires_explicit_dead_owner_metadata(tmp_path) -> None:
    store = ArtifactStore(tmp_path, stale_lock_seconds=0.0)
    lock_path = tmp_path / "claims" / "trial-1.owner.json"
    lock_path.parent.mkdir()
    owner = store.owner_identity(lease_seconds=-1.0)
    owner["pid"] = 999_999_999
    owner["process_start_id"] = "dead-process-start"
    prior_nonce = owner["nonce"]
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(owner))

    with store.claim_trial("trial-1") as claim:
        assert claim.owner["nonce"] != prior_nonce

    remote = store.owner_identity(lease_seconds=60.0)
    remote["hostname"] = "remote-host"
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(remote))
    with pytest.raises(TrialClaimConflict, match="active"):
        store.claim_trial("trial-1")


def test_completed_trial_is_verified_before_skip(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_trial("trial-1", {"schema_version": 1, "trial_id": "trial-1"})
    (tmp_path / "trials" / "trial-1.json").write_text('{"tampered":true}\n')

    with pytest.raises(ArtifactConflict, match="hash"):
        store.completed_trial_ids()


def test_two_reclaimers_have_exactly_one_winner(tmp_path) -> None:
    store = ArtifactStore(tmp_path, stale_lock_seconds=0.0)
    lock_path = tmp_path / "claims" / "trial-race.owner.json"
    lock_path.parent.mkdir()
    owner = store.owner_identity(lease_seconds=-1.0)
    owner["pid"] = 999_999_999
    owner["process_start_id"] = "dead-process-start"
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(owner))

    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    workers = [
        context.Process(target=_claim_worker, args=(str(tmp_path), queue))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    results = [queue.get(timeout=5) for _ in workers]
    for worker in workers:
        worker.join(timeout=5)
        assert worker.exitcode == 0

    assert sorted(kind for kind, _ in results) == ["acquired", "conflict"]


def test_pid_reuse_requires_matching_process_start_identity(tmp_path) -> None:
    store = ArtifactStore(tmp_path, stale_lock_seconds=0.0)
    lock_path = tmp_path / "claims" / "trial-1.owner.json"
    lock_path.parent.mkdir()
    reused = store.owner_identity(lease_seconds=-1.0)
    reused["process_start_id"] = f"{reused['process_start_id']}-different"
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(reused))

    with store.claim_trial("trial-1"):
        pass

    active = store.owner_identity(lease_seconds=-1.0)
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(active))
    with pytest.raises(TrialClaimConflict, match="cannot prove stale"):
        store.claim_trial("trial-1")


def test_foreign_host_uses_explicit_lease_expiry(tmp_path) -> None:
    store = ArtifactStore(tmp_path, stale_lock_seconds=0.0)
    lock_path = tmp_path / "claims" / "trial-1.owner.json"
    lock_path.parent.mkdir()
    foreign = store.owner_identity(lease_seconds=60.0)
    foreign["hostname"] = "other-host"
    foreign["pid"] = os.getpid()
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(foreign))
    with pytest.raises(TrialClaimConflict, match="active"):
        store.claim_trial("trial-1")

    foreign["lease_expires_at"] = time.time() - 1.0
    lock_path.write_bytes(artifacts_module.canonical_json_bytes(foreign))
    with store.claim_trial("trial-1"):
        pass


def test_held_trial_flock_blocks_expired_foreign_reclaim_then_allows_it(
    tmp_path,
) -> None:
    store = ArtifactStore(tmp_path, stale_lock_seconds=0.0)
    claims = tmp_path / "claims"
    claims.mkdir()
    lock_path = claims / "trial-foreign.flock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    owner = store.owner_identity(lease_seconds=-1.0)
    owner["hostname"] = "foreign-container"
    (claims / "trial-foreign.owner.json").write_bytes(
        artifacts_module.canonical_json_bytes(owner)
    )

    with pytest.raises(TrialClaimConflict, match="kernel lock"):
        store.claim_trial("trial-foreign")

    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)
    with store.claim_trial("trial-foreign"):
        pass


def test_crashed_claim_releases_kernel_lock_and_can_be_reclaimed(tmp_path) -> None:
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    worker = context.Process(
        target=_crash_claim_worker,
        args=(str(tmp_path), queue),
    )
    worker.start()
    owner, lock_path = queue.get(timeout=10)
    worker.join(timeout=10)
    assert worker.exitcode == 0
    assert Path(lock_path).exists()

    store = ArtifactStore(tmp_path)
    with store.claim_trial("trial-crash") as replacement:
        assert replacement.owner["nonce"] != owner["nonce"]


def test_claim_release_closes_dedicated_descriptor(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    before = len(list(Path("/proc/self/fd").iterdir()))

    claim = store.claim_trial("trial-fd")
    assert claim.lock_descriptor >= 0
    claim.release()

    with pytest.raises(OSError):
        os.fstat(claim.lock_descriptor)
    assert len(list(Path("/proc/self/fd").iterdir())) <= before


def test_concurrent_different_immutable_writers_have_one_winner(tmp_path) -> None:
    results: list[str] = []
    barrier = threading.Barrier(2)

    def publish(value: int) -> None:
        store = ArtifactStore(tmp_path)
        barrier.wait()
        try:
            store.publish_json("manifest.json", {"value": value}, immutable=True)
        except ArtifactConflict:
            results.append("conflict")
        else:
            results.append("winner")

    threads = [threading.Thread(target=publish, args=(value,)) for value in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert sorted(results) == ["conflict", "winner"]
    assert json.loads((tmp_path / "manifest.json").read_text()) in (
        {"value": 1},
        {"value": 2},
    )


def test_concurrent_initialization_has_self_consistent_winner(tmp_path) -> None:
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    workers = [
        context.Process(
            target=_initialize_worker,
            args=(str(tmp_path), seed, queue),
        )
        for seed in (1, 2)
    ]
    for worker in workers:
        worker.start()
    results = [queue.get(timeout=10) for _ in workers]
    for worker in workers:
        worker.join(timeout=5)
        assert worker.exitcode == 0

    assert sorted(kind for kind, _ in results) == ["conflict", "winner"]
    winner = next(seed for kind, seed in results if kind == "winner")
    ready = json.loads((tmp_path / "ready.json").read_text())
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert manifest["provenance"]["config"] == {"seed": winner}
    assert plan["trials"] == [{"seed": winner}]
    assert ready["manifest_sha256"] == hashlib.sha256(
        (tmp_path / "manifest.json").read_bytes()
    ).hexdigest()
    assert ready["plan_sha256"] == hashlib.sha256(
        (tmp_path / "plan.json").read_bytes()
    ).hexdigest()


def test_partial_initialization_is_not_resumable_until_ready(
    tmp_path,
    config,
    monkeypatch,
) -> None:
    store = ArtifactStore(tmp_path)
    real_publish = store._publish_bytes_locked

    def crash_on_ready(relative, data, *, immutable):
        if relative == Path("ready.json"):
            raise KeyboardInterrupt()
        return real_publish(relative, data, immutable=immutable)

    monkeypatch.setattr(store, "_publish_bytes_locked", crash_on_ready)
    with pytest.raises(KeyboardInterrupt):
        store.initialize_run(config.canonical_dict(), {"schema_version": 1})

    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "ready.json").exists()
    with pytest.raises(ArtifactConflict):
        ArtifactStore.resume(tmp_path, config)

    monkeypatch.setattr(store, "_publish_bytes_locked", real_publish)
    store.initialize_run(config.canonical_dict(), {"schema_version": 1})
    assert (tmp_path / "ready.json").exists()


@pytest.mark.parametrize(
    "token",
    ("", "..", "../x", "x/y", "/absolute", "UPPER", "white space"),
)
def test_trial_id_rejects_unsafe_tokens(tmp_path, token) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="token"):
        store.claim_trial(token)
    with pytest.raises(ValueError, match="token"):
        store.publish_trial(token, {"trial_id": token})


def test_store_rejects_symlink_root_parent_and_final(tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    root_link = tmp_path / "root-link"
    root_link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ArtifactConflict, match="symlink"):
        ArtifactStore(root_link)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ArtifactConflict, match="symlink"):
        ArtifactStore(parent_link / "child")

    store = ArtifactStore(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactConflict, match="symlink"):
        store.publish_json("linked/value.json", {"value": 1})

    target = outside / "target.json"
    target.write_text("{}")
    (store.root / "final.json").symlink_to(target)
    with pytest.raises(ArtifactConflict, match="symlink"):
        store.read_json("final.json")
    with pytest.raises(ArtifactConflict, match="symlink"):
        store.publish_json("final.json", {"value": 1})


def test_store_rejects_traversal_and_absolute_artifact_paths(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    for path in (
        "../escape.json",
        "/tmp/escape.json",
        "a/../../escape.json",
        r"..\escape.json",
        r"C:\absolute.json",
    ):
        with pytest.raises(ValueError, match="relative"):
            store.publish_json(path, {"value": 1})
        with pytest.raises(ValueError, match="relative"):
            store.read_json(path)


def test_cleanup_failure_after_durable_replace_does_not_report_failure(
    tmp_path,
    monkeypatch,
) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    monkeypatch.setattr(
        store,
        "_unlink",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup")),
    )

    digest = store.publish_json("summary.json", {"version": 2})

    assert digest == hashlib.sha256(b'{"version":2}\n').hexdigest()
    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 2}


def test_directory_fsync_failure_reports_verified_bytes(tmp_path, monkeypatch) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    calls = 0
    real_fsync = store._fsync_directory

    def fail_once(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("fsync")
        real_fsync(path)

    monkeypatch.setattr(store, "_fsync_directory", fail_once)
    with pytest.raises(ArtifactDurabilityError) as raised:
        store.publish_json("summary.json", {"version": 2})

    assert raised.value.present == "old"
    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 1}


def test_rollback_failure_reports_actual_new_bytes(tmp_path, monkeypatch) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    real_replace = store._replace
    replaces = 0

    def fail_rollback(source: Path, destination: Path) -> None:
        nonlocal replaces
        replaces += 1
        if replaces == 2:
            raise OSError("rollback")
        real_replace(source, destination)

    monkeypatch.setattr(store, "_replace", fail_rollback)
    monkeypatch.setattr(
        store,
        "_fsync_directory",
        lambda *_: (_ for _ in ()).throw(OSError("fsync")),
    )
    with pytest.raises(ArtifactDurabilityError) as raised:
        store.publish_json("summary.json", {"version": 2})

    assert raised.value.present == "new"
    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 2}


def test_write_failure_closes_descriptor_and_removes_temp(
    tmp_path,
    monkeypatch,
) -> None:
    store = ArtifactStore(tmp_path)
    before = len(list(Path("/proc/self/fd").iterdir()))
    monkeypatch.setattr(
        os,
        "write",
        lambda *_: (_ for _ in ()).throw(OSError("write failed")),
    )

    with pytest.raises(OSError, match="write failed"):
        store.publish_json("value.json", {"value": 1})

    after = len(list(Path("/proc/self/fd").iterdir()))
    assert after <= before
    assert not list(tmp_path.glob(".artifact.tmp-*"))


def test_post_replace_hash_read_failure_reports_unknown_durability(
    tmp_path,
    monkeypatch,
) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    real_hash = artifacts_module._file_sha256
    calls = 0

    def fail_new_hash(path: Path) -> str:
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise OSError("read failed")
        return real_hash(path)

    monkeypatch.setattr(artifacts_module, "_file_sha256", fail_new_hash)
    with pytest.raises(ArtifactDurabilityError) as raised:
        store.publish_json("summary.json", {"version": 2})

    assert raised.value.present == "unreadable"
    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 2}
