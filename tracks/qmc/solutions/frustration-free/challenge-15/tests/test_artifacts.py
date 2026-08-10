import json
import hashlib
import errno
import multiprocessing
import os
from pathlib import Path

import pytest

import challenge15.artifacts as artifacts
from challenge15.artifacts import (
    publish_create_only,
    publish_json_atomic,
    publish_production_envelope,
    verify_artifact,
)


def test_publication_verifies_unique_sibling_partial_before_replace(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    events = []
    partials = []
    original_verify = artifacts.verify_artifact
    original_noreplace = artifacts._rename_noreplace_strict
    original_exchange = artifacts._rename_exchange_strict

    def recording_verify(path):
        path = Path(path)
        events.append(("verify", path))
        partials.append(path)
        return original_verify(path)

    def recording_noreplace(directory_fd, source, target):
        events.append(("publish", Path(source)))
        return original_noreplace(directory_fd, source, target)

    monkeypatch.setattr(artifacts, "verify_artifact", recording_verify)
    monkeypatch.setattr(artifacts, "_rename_noreplace_strict", recording_noreplace)
    monkeypatch.setattr(
        artifacts,
        "_rename_exchange_strict",
        lambda directory_fd, source, target: (
            events.append(("publish", Path(source))),
            original_exchange(directory_fd, source, target),
        )[1],
    )
    publish_json_atomic(destination, {"value": 1})
    publish_json_atomic(destination, {"value": 2})

    partials = [path for path in partials if path.name.endswith(".partial")]
    assert all(path.parent == destination.parent for path in partials)
    assert partials[0] != partials[1]
    assert events.index(("verify", partials[0])) < events.index(("publish", Path(partials[0].name)))
    assert verify_artifact(destination)["value"] == 2


def test_publication_fsyncs_file_and_parent_directory(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    fsynced_modes = []
    original_fsync = os.fsync

    def recording_fsync(fd):
        fsynced_modes.append(os.fstat(fd).st_mode)
        return original_fsync(fd)

    monkeypatch.setattr(artifacts.os, "fsync", recording_fsync)
    publish_json_atomic(destination, {"value": 1})

    assert any(not artifacts.stat.S_ISDIR(mode) for mode in fsynced_modes)
    assert any(artifacts.stat.S_ISDIR(mode) for mode in fsynced_modes)


def test_successful_stale_backup_unlink_is_directory_fsynced(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": 1})
    calls = 0
    original = artifacts._fsync_directory_fd

    def recording(directory_fd):
        nonlocal calls
        calls += 1
        return original(directory_fd)

    monkeypatch.setattr(artifacts, "_fsync_directory_fd", recording)
    publish_json_atomic(destination, {"value": 2})

    assert calls >= 3
    assert verify_artifact(destination) == {"value": 2}
    assert not tuple(tmp_path.glob("*.backup"))


def test_new_partial_verification_failure_preserves_existing_destination(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()
    verified_paths = []
    original_verify = artifacts.verify_artifact

    def fail_new_partial(path):
        path = Path(path)
        verified_paths.append(path)
        if path.name.endswith(".partial") and ".rollback." not in path.name:
            raise ValueError("injected new partial verification failure")
        return original_verify(path)

    monkeypatch.setattr(artifacts, "verify_artifact", fail_new_partial)
    with pytest.raises(ValueError, match="new partial"):
        publish_json_atomic(destination, {"value": "new"})

    assert verified_paths[0].as_posix().startswith("/proc/self/fd/")
    assert any(path.name.endswith(".backup") for path in verified_paths)
    assert any(path.name.endswith(".partial") for path in verified_paths)
    assert destination.read_bytes() == previous_bytes
    assert not tuple(tmp_path.glob("*.partial"))


def test_destination_replace_failure_preserves_existing_destination(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()
    replacement_attempted = False
    verified_backup = None

    def fail_destination_exchange(directory_fd, source, target):
        nonlocal replacement_attempted, verified_backup
        if target == destination.name:
            replacement_attempted = True
            backups = tuple(tmp_path.glob("*.backup"))
            assert len(backups) == 1
            verified_backup = verify_artifact(backups[0])
            raise OSError("injected destination replace failure")

    monkeypatch.setattr(
        artifacts,
        "_rename_exchange_strict",
        fail_destination_exchange,
    )
    with pytest.raises(OSError, match="destination replace"):
        publish_json_atomic(destination, {"value": "new"})

    assert replacement_attempted
    assert verified_backup == {"value": "old"}
    assert destination.read_bytes() == previous_bytes


def test_post_replace_directory_fsync_failure_restores_previous_bytes(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()
    original_fsync_directory = artifacts._fsync_directory_fd
    calls = 0

    def fail_post_replace(directory_fd):
        nonlocal calls
        calls += 1
        if calls == 1:
            assert verify_artifact(destination)["value"] == "new"
            raise OSError("injected post-replace directory fsync failure")
        return original_fsync_directory(directory_fd)

    monkeypatch.setattr(artifacts, "_fsync_directory_fd", fail_post_replace)
    with pytest.raises(OSError, match="post-replace"):
        publish_json_atomic(destination, {"value": "new"})

    assert calls >= 3
    assert destination.read_bytes() == previous_bytes
    assert not tuple(tmp_path.glob("*.backup"))


def test_transactional_validator_failure_restores_previous_bytes(tmp_path):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()

    def reject_post_replace(path):
        payload = verify_artifact(path)
        if Path(path) == destination and payload["value"] == "new":
            raise ValueError("injected post-publication verification failure")

    with pytest.raises(ValueError, match="post-publication"):
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=reject_post_replace,
        )

    assert destination.read_bytes() == previous_bytes
    assert verify_artifact(destination) == {"value": "old"}
    assert not tuple(tmp_path.glob("*.partial"))
    assert not tuple(tmp_path.glob("*.backup"))


def test_transactional_validator_failure_without_prior_destination_cleans_up(tmp_path):
    destination = tmp_path / "result.json"

    def reject_post_replace(path):
        verify_artifact(path)
        if Path(path) == destination:
            raise ValueError("injected absent-destination readback failure")

    with pytest.raises(ValueError, match="absent-destination"):
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=reject_post_replace,
        )

    assert not destination.exists()
    assert not tuple(tmp_path.glob("*.partial"))
    assert not tuple(tmp_path.glob("*.backup"))


@pytest.mark.parametrize("fail_calls", [{1, 2}, {1, 2, 3}])
def test_absent_rollback_double_fsync_failure_surfaces_recovery_path(
    tmp_path, monkeypatch, fail_calls
):
    destination = tmp_path / "result.json"
    original_fsync = artifacts._fsync_directory_fd
    calls = 0

    def fail_publication_and_rollback_fsync(directory_fd):
        nonlocal calls
        calls += 1
        if calls in fail_calls:
            raise OSError(f"injected fsync failure {calls}")
        return original_fsync(directory_fd)

    monkeypatch.setattr(
        artifacts,
        "_fsync_directory_fd",
        fail_publication_and_rollback_fsync,
    )
    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(destination, {"value": "new"})

    error = caught.value
    assert isinstance(error.publication_error, OSError)
    assert "failure 1" in str(error.publication_error)
    assert isinstance(error.recovery_error, OSError)
    assert "failure 2" in str(error.recovery_error)
    if 3 in fail_calls:
        assert isinstance(error.cleanup_error, OSError)
        assert "failure 3" in str(error.cleanup_error)
    else:
        assert error.cleanup_error is None
    assert error.state == "recovery_only"
    assert not destination.exists()
    assert len(error.recovery_paths) == 1
    assert error.recovery_paths[0].exists()
    assert verify_artifact(error.recovery_paths[0]) == {"value": "new"}


def test_absent_rollback_rename_failure_reports_destination_only(
    tmp_path, monkeypatch
):
    destination = tmp_path / "result.json"
    original_rename = artifacts._rename_noreplace_strict
    calls = 0

    def fail_rollback_rename(directory_fd, source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected rollback rename failure")
        return original_rename(directory_fd, source, target)

    monkeypatch.setattr(
        artifacts,
        "_rename_noreplace_strict",
        fail_rollback_rename,
    )

    def reject_destination(path):
        verify_artifact(path)
        if Path(path) == destination:
            raise ValueError("injected publication verification failure")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=reject_destination,
        )

    error = caught.value
    assert isinstance(error.publication_error, ValueError)
    assert isinstance(error.recovery_error, OSError)
    assert error.state == "destination_only"
    assert error.recovery_paths == ()
    assert verify_artifact(destination) == {"value": "new"}


def test_absent_recovery_cleanup_fsync_failure_recreates_visible_recovery(
    tmp_path, monkeypatch
):
    destination = tmp_path / "result.json"
    original_fsync = artifacts._fsync_directory_fd
    calls = 0

    def fail_cleanup_fsync(directory_fd):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("injected recovery cleanup fsync failure")
        return original_fsync(directory_fd)

    monkeypatch.setattr(artifacts, "_fsync_directory_fd", fail_cleanup_fsync)

    def reject_destination(path):
        verify_artifact(path)
        if Path(path) == destination:
            raise ValueError("injected publication verification failure")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=reject_destination,
        )

    error = caught.value
    assert error.state == "recovery_only"
    assert len(error.recovery_paths) == 1
    assert verify_artifact(error.recovery_paths[0]) == {"value": "new"}


@pytest.mark.parametrize("failure", ["restore_rename", "restore_fsync"])
def test_absent_concurrent_restore_failure_surfaces_all_valid_bytes(
    tmp_path, monkeypatch, failure
):
    destination = tmp_path / "result.json"
    concurrent = tmp_path / "concurrent.json"
    publish_json_atomic(concurrent, {"value": "concurrent"})
    original_rename = artifacts._rename_noreplace_strict
    original_fsync = artifacts._fsync_directory_fd
    rename_calls = 0
    fsync_calls = 0

    def maybe_fail_restore_rename(directory_fd, source, target):
        nonlocal rename_calls
        rename_calls += 1
        if failure == "restore_rename" and rename_calls == 3:
            raise OSError("injected concurrent restore rename failure")
        return original_rename(directory_fd, source, target)

    def maybe_fail_restore_fsync(directory_fd):
        nonlocal fsync_calls
        fsync_calls += 1
        if failure == "restore_fsync" and fsync_calls == 3:
            raise OSError("injected concurrent restore fsync failure")
        return original_fsync(directory_fd)

    monkeypatch.setattr(
        artifacts,
        "_rename_noreplace_strict",
        maybe_fail_restore_rename,
    )
    monkeypatch.setattr(artifacts, "_fsync_directory_fd", maybe_fail_restore_fsync)

    def replace_with_concurrent_then_fail(path):
        verify_artifact(path)
        if Path(path) == destination:
            os.replace(concurrent, destination)
            raise ValueError("injected absent concurrent replacement")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=replace_with_concurrent_then_fail,
        )

    error = caught.value
    assert isinstance(error.publication_error, ValueError)
    assert isinstance(error.recovery_error, OSError)
    if failure == "restore_rename":
        assert error.state == "recovery_only"
        assert not destination.exists()
        assert len(error.recovery_paths) == 1
        assert verify_artifact(error.recovery_paths[0]) == {
            "value": "concurrent"
        }
    else:
        assert error.state == "destination_only"
        assert error.recovery_paths == ()
        assert verify_artifact(destination) == {"value": "concurrent"}


def test_transactional_validator_detects_tampered_readback_and_rolls_back(
    tmp_path,
):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()

    def tamper_post_replace(path):
        verify_artifact(path)
        if Path(path) == destination:
            destination.write_bytes(b"tampered")
            raise ValueError("injected concurrent readback tamper")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=tamper_post_replace,
        )

    assert destination.read_bytes() == b"tampered"
    assert caught.value.backup_path.read_bytes() == previous_bytes


def test_transactional_validator_replaces_valid_destination_without_residue(tmp_path):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    verified = []

    def validate(path):
        verified.append(Path(path))
        assert verify_artifact(path)["value"] == "new"

    publish_json_atomic(destination, {"value": "new"}, validator=validate)

    assert verified[-1] == destination
    assert verify_artifact(destination) == {"value": "new"}
    assert not tuple(tmp_path.glob("*.partial"))
    assert not tuple(tmp_path.glob("*.backup"))


def test_atomic_create_loses_concurrent_creation_without_erasing_it(
    tmp_path, monkeypatch
):
    destination = tmp_path / "result.json"
    concurrent = tmp_path / "concurrent.json"
    publish_json_atomic(concurrent, {"value": "concurrent"})
    concurrent_bytes = concurrent.read_bytes()
    original = artifacts._rename_noreplace_strict

    def create_concurrently(directory_fd, source, target):
        if target == destination.name:
            os.link(concurrent, destination)
            raise FileExistsError(errno.EEXIST, "injected concurrent create", target)
        return original(directory_fd, source, target)

    monkeypatch.setattr(
        artifacts,
        "_rename_noreplace_strict",
        create_concurrently,
    )
    with pytest.raises(FileExistsError, match="concurrent create"):
        publish_json_atomic(destination, {"value": "ours"})

    assert destination.read_bytes() == concurrent_bytes
    assert verify_artifact(destination) == {"value": "concurrent"}


def test_atomic_exchange_detects_concurrent_existing_replacement(
    tmp_path, monkeypatch
):
    destination = tmp_path / "result.json"
    concurrent = tmp_path / "concurrent.json"
    publish_json_atomic(destination, {"value": "old"})
    publish_json_atomic(concurrent, {"value": "concurrent"})
    concurrent_bytes = concurrent.read_bytes()
    original = artifacts._rename_exchange_strict
    injected = False

    def replace_before_exchange(directory_fd, source, target):
        nonlocal injected
        if target == destination.name and not injected:
            injected = True
            os.replace(concurrent, destination)
        return original(directory_fd, source, target)

    monkeypatch.setattr(
        artifacts,
        "_rename_exchange_strict",
        replace_before_exchange,
    )
    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(destination, {"value": "ours"})

    assert destination.read_bytes() == concurrent_bytes
    assert verify_artifact(destination) == {"value": "concurrent"}
    assert "concurrent" in str(caught.value.publication_error)
    assert verify_artifact(caught.value.backup_path) == {"value": "old"}


def test_atomic_rollback_cas_mismatch_preserves_concurrent_destination(
    tmp_path,
):
    destination = tmp_path / "result.json"
    concurrent = tmp_path / "concurrent.json"
    publish_json_atomic(destination, {"value": "old"})
    publish_json_atomic(concurrent, {"value": "concurrent"})
    concurrent_bytes = concurrent.read_bytes()

    def replace_then_fail(path):
        verify_artifact(path)
        if Path(path) == destination:
            os.replace(concurrent, destination)
            raise ValueError("injected post-validation CAS mismatch")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "ours"},
            validator=replace_then_fail,
        )

    assert destination.read_bytes() == concurrent_bytes
    assert verify_artifact(destination) == {"value": "concurrent"}
    assert caught.value.backup_path.exists()
    assert verify_artifact(caught.value.backup_path) == {"value": "old"}


def test_atomic_rollback_rejects_identical_bytes_from_different_inode(tmp_path):
    destination = tmp_path / "result.json"
    replacement = tmp_path / "replacement.json"
    publish_json_atomic(destination, {"value": "old"})

    def replace_with_identical_bytes(path):
        verify_artifact(path)
        if Path(path) == destination:
            replacement.write_bytes(destination.read_bytes())
            os.replace(replacement, destination)
            raise ValueError("injected identical-byte inode replacement")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "ours"},
            validator=replace_with_identical_bytes,
        )

    assert verify_artifact(destination) == {"value": "ours"}
    assert verify_artifact(caught.value.backup_path) == {"value": "old"}


def test_atomic_publication_fails_closed_when_renameat2_is_unsupported(
    tmp_path, monkeypatch
):
    destination = tmp_path / "result.json"

    def unsupported(*args, **kwargs):
        raise OSError(errno.EOPNOTSUPP, "renameat2 unsupported")

    monkeypatch.setattr(artifacts, "_renameat2_strict", unsupported)
    with pytest.raises(OSError, match="unsupported"):
        publish_json_atomic(destination, {"value": "ours"})

    assert not destination.exists()


def test_atomic_publication_exclusive_lock_blocks_cooperating_writer(tmp_path):
    destination = tmp_path / "result.json"
    lock = tmp_path / f".{destination.name}.transaction.lock"
    lock.write_bytes(b"other writer")

    with pytest.raises(FileExistsError):
        publish_json_atomic(destination, {"value": "ours"})

    assert lock.read_bytes() == b"other writer"
    assert not destination.exists()


def test_atomic_create_and_exchange_leave_no_transaction_debris(tmp_path):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "one"})
    publish_json_atomic(destination, {"value": "two"})

    assert verify_artifact(destination) == {"value": "two"}
    assert not tuple(tmp_path.glob(f".{destination.name}.transaction.*"))


def test_rollback_replace_failure_retains_verified_backup(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()
    original_fsync_directory = artifacts._fsync_directory_fd
    original_exchange = artifacts._rename_exchange_strict
    fsync_calls = 0

    def fail_post_replace(directory_fd):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 1:
            raise OSError("injected post-replace directory fsync failure")
        return original_fsync_directory(directory_fd)

    exchange_calls = 0

    def fail_rollback_replace(directory_fd, source, target):
        nonlocal exchange_calls
        exchange_calls += 1
        if exchange_calls == 2:
            raise OSError("injected rollback replace failure")
        return original_exchange(directory_fd, source, target)

    monkeypatch.setattr(artifacts, "_fsync_directory_fd", fail_post_replace)
    monkeypatch.setattr(
        artifacts,
        "_rename_exchange_strict",
        fail_rollback_replace,
    )
    with pytest.raises(artifacts.ArtifactRecoveryError, match="recoverable backup") as caught:
        publish_json_atomic(destination, {"value": "new"})

    backup = caught.value.backup_path
    assert backup.read_bytes() == previous_bytes
    assert original_verify_artifact(backup)["value"] == "old"


def test_rollback_directory_fsync_failure_retains_verified_backup(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    previous_bytes = destination.read_bytes()
    original_fsync_directory = artifacts._fsync_directory_fd
    calls = 0

    def fail_replacement_and_rollback_fsync(directory_fd):
        nonlocal calls
        calls += 1
        if calls in {1, 2}:
            raise OSError("injected rollback durability failure")
        return original_fsync_directory(directory_fd)

    monkeypatch.setattr(
        artifacts,
        "_fsync_directory_fd",
        fail_replacement_and_rollback_fsync,
    )
    with pytest.raises(artifacts.ArtifactRecoveryError, match="recoverable backup") as caught:
        publish_json_atomic(destination, {"value": "new"})

    backup = caught.value.backup_path
    assert destination.read_bytes() == previous_bytes
    assert backup.read_bytes() == previous_bytes
    assert original_verify_artifact(backup)["value"] == "old"


@pytest.mark.parametrize("failure", ["exchange", "fsync"])
def test_existing_validation_rollback_failure_surfaces_truthful_state(
    tmp_path, monkeypatch, failure
):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    original_exchange = artifacts._rename_exchange_strict
    original_fsync = artifacts._fsync_directory_fd
    exchange_calls = 0
    fsync_calls = 0

    def maybe_fail_exchange(directory_fd, source, target):
        nonlocal exchange_calls
        exchange_calls += 1
        if failure == "exchange" and exchange_calls == 2:
            raise OSError("injected validation rollback exchange failure")
        return original_exchange(directory_fd, source, target)

    def maybe_fail_fsync(directory_fd):
        nonlocal fsync_calls
        fsync_calls += 1
        if failure == "fsync" and fsync_calls == 2:
            raise OSError("injected validation rollback fsync failure")
        return original_fsync(directory_fd)

    monkeypatch.setattr(
        artifacts,
        "_rename_exchange_strict",
        maybe_fail_exchange,
    )
    monkeypatch.setattr(artifacts, "_fsync_directory_fd", maybe_fail_fsync)

    def reject_destination(path):
        verify_artifact(path)
        if Path(path) == destination:
            raise ValueError("injected publication verification failure")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=reject_destination,
        )

    error = caught.value
    assert isinstance(error.publication_error, ValueError)
    assert isinstance(error.recovery_error, OSError)
    assert error.state == "destination_and_recovery"
    assert error.recovery_paths
    assert all(path.exists() for path in error.recovery_paths)
    assert any(verify_artifact(path) == {"value": "old"} for path in error.recovery_paths)


@pytest.mark.parametrize(
    "failed_fsync,expected_state",
    [
        (2, "destination_and_recovery"),
        (3, "destination_and_recovery"),
        (4, "destination_and_possible_recovery"),
    ],
)
def test_existing_rollback_every_fsync_failure_is_typed_and_truthful(
    tmp_path, monkeypatch, failed_fsync, expected_state
):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": "old"})
    original_fsync = artifacts._fsync_directory_fd
    calls = 0

    def fail_selected_fsync(directory_fd):
        nonlocal calls
        calls += 1
        if calls == failed_fsync:
            raise OSError(f"injected rollback fsync {failed_fsync}")
        return original_fsync(directory_fd)

    monkeypatch.setattr(artifacts, "_fsync_directory_fd", fail_selected_fsync)

    def reject_destination(path):
        verify_artifact(path)
        if Path(path) == destination:
            raise ValueError("injected publication verification failure")

    with pytest.raises(artifacts.ArtifactRecoveryError) as caught:
        publish_json_atomic(
            destination,
            {"value": "new"},
            validator=reject_destination,
        )

    error = caught.value
    assert error.state == expected_state
    assert isinstance(error.publication_error, ValueError)
    assert isinstance(error.recovery_error, OSError)
    assert verify_artifact(destination) == {"value": "old"}
    assert all(path.exists() for path in error.recovery_paths)
    if failed_fsync == 4:
        assert error.recovery_paths == ()
        assert len(error.possible_recovery_paths) == 1
        assert error.possible_recovery_paths[0].name.endswith(".backup")
        assert not error.possible_recovery_paths[0].exists()
    elif failed_fsync == 3:
        assert error.possible_recovery_paths
        assert error.possible_recovery_paths[0].name.endswith(".partial")
    else:
        assert error.possible_recovery_paths == ()


@pytest.mark.parametrize("manifest_path", ["/absolute/input.dat", "../escape.dat", "a/../../escape.dat"])
def test_manifest_rejects_absolute_and_parent_traversing_paths(tmp_path, manifest_path):
    with pytest.raises(ValueError, match="manifest path"):
        publish_json_atomic(
            tmp_path / "result.json",
            {"manifest": {manifest_path: "0" * 64}},
        )


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_publication_rejects_nonfinite_json(tmp_path, bad_value):
    with pytest.raises(ValueError, match="finite"):
        publish_json_atomic(tmp_path / "result.json", {"value": bad_value})


def test_verification_rejects_tampered_payload(tmp_path):
    destination = tmp_path / "result.json"
    publish_json_atomic(destination, {"value": 1})
    document = json.loads(destination.read_text())
    document["payload"]["value"] = 2
    destination.write_text(json.dumps(document))

    with pytest.raises(ValueError, match="SHA256"):
        verify_artifact(destination)


original_verify_artifact = verify_artifact


def _create_only_writer(path, value, queue):
    try:
        publish_create_only(path, value)
    except FileExistsError:
        queue.put("exists")
    else:
        queue.put("published")


def _crash_create_only(path, boundary):
    if boundary == "fsync":
        artifacts._fsync_directory_fd = lambda _fd: os._exit(71)
    elif boundary == "rename":
        artifacts._rename_noreplace = lambda *_args, **_kwargs: os._exit(72)
    publish_create_only(path, b"value")


def test_create_only_uses_staging_and_noreplace_without_unsafe_cleanup(
    tmp_path, monkeypatch
):
    destination = tmp_path / "immutable"

    def fail_rename(*_args, **_kwargs):
        raise OSError("injected rename failure")

    monkeypatch.setattr(artifacts, "_rename_noreplace", fail_rename)
    with pytest.raises(OSError, match="rename"):
        publish_create_only(destination, b"value")

    assert not destination.exists()
    assert len(tuple(tmp_path.glob(".*.partial.*"))) == 1


def test_create_only_never_deletes_replacement_staging_inode(tmp_path, monkeypatch):
    destination = tmp_path / "immutable"

    def replace_staging_then_fail(directory_fd, source, _destination, *_args):
        os.unlink(source, dir_fd=directory_fd)
        replacement_fd = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=directory_fd,
        )
        os.write(replacement_fd, b"replacement")
        os.close(replacement_fd)
        raise OSError("injected replacement race")

    monkeypatch.setattr(artifacts, "_rename_noreplace", replace_staging_then_fail)
    with pytest.raises(OSError, match="replacement race"):
        publish_create_only(destination, b"owned")

    partial = tuple(tmp_path.glob(".*.partial.*"))
    assert len(partial) == 1
    assert partial[0].read_bytes() == b"replacement"


def test_create_only_post_rename_fsync_failure_keeps_published_object(
    tmp_path, monkeypatch
):
    destination = tmp_path / "immutable"
    original = artifacts._fsync_directory_fd

    def fail_directory_fsync(fd):
        raise OSError("injected directory fsync failure")

    monkeypatch.setattr(artifacts, "_fsync_directory_fd", fail_directory_fsync)
    with pytest.raises(OSError, match="directory fsync"):
        publish_create_only(destination, b"value")

    assert destination.read_bytes() == b"value"
    monkeypatch.setattr(artifacts, "_fsync_directory_fd", original)
    with pytest.raises(FileExistsError):
        publish_create_only(destination, b"replacement")


def test_create_only_rejects_symlink_parent(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        publish_create_only(linked / "artifact", b"value")

    assert not (real / "artifact").exists()


def test_create_only_multiprocess_writers_publish_exactly_one_value(tmp_path):
    destination = tmp_path / "artifact"
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [
        context.Process(
            target=_create_only_writer,
            args=(destination, f"value-{index}".encode(), queue),
        )
        for index in range(8)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    outcomes = [queue.get(timeout=1) for _ in processes]
    assert outcomes.count("published") == 1
    assert outcomes.count("exists") == 7
    assert destination.read_bytes() in {f"value-{index}".encode() for index in range(8)}


def test_create_only_detects_parent_symlink_swap_without_writing_attacker_tree(
    tmp_path, monkeypatch
):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    displaced = tmp_path / "displaced"
    original = artifacts._rename_noreplace

    def swap_then_rename(*args, **kwargs):
        trusted.rename(displaced)
        trusted.symlink_to(attacker, target_is_directory=True)
        return original(*args, **kwargs)

    monkeypatch.setattr(artifacts, "_rename_noreplace", swap_then_rename)
    with pytest.raises(ValueError, match="identity changed"):
        publish_create_only(trusted / "result.json", b"trusted")

    assert not (attacker / "result.json").exists()
    assert (displaced / "result.json").read_bytes() == b"trusted"


@pytest.mark.parametrize(
    "boundary,exitcode,published",
    [("fsync", 71, True), ("rename", 72, False)],
)
def test_process_crash_has_atomic_publication_boundary(
    tmp_path, boundary, exitcode, published
):
    destination = tmp_path / "result.json"
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_create_only,
        args=(destination, boundary),
    )
    process.start()
    process.join(timeout=10)
    assert process.exitcode == exitcode
    assert destination.exists() is published
    if not published:
        assert tuple(tmp_path.glob(".*.partial.*"))


def test_context_bound_receipt_cannot_be_published_without_context(tmp_path):
    payload = {
        "profile_sha256": "a" * 64,
        "bundle_sha256": "b" * 64,
        "destination": "/approved/deployment",
        "interpreter": "/approved/deployment/bin/python",
        "interpreter_sha256": "c" * 64,
        "scheduler_test": {"exit_code": 0},
        "validated_at_utc": "2026-07-29T00:00:00Z",
    }
    with pytest.raises(ValueError, match="requires complete context"):
        publish_production_envelope(
            tmp_path / "dry-run.json",
            "challenge15.dry-run-receipt.v1",
            payload,
        )
    assert not (tmp_path / "dry-run.json").exists()


def test_invalid_context_never_occupies_create_only_destination(tmp_path):
    destination = tmp_path / "dry-run.json"
    deployment = tmp_path / "deployment"
    (deployment / "bin").mkdir(parents=True)
    interpreter = deployment / "bin" / "python"
    interpreter.write_bytes(b"python")
    payload = {
        "profile_sha256": "a" * 64,
        "bundle_sha256": "b" * 64,
        "destination": str(deployment),
        "interpreter": str(interpreter),
        "interpreter_sha256": hashlib.sha256(b"python").hexdigest(),
        "scheduler_test": {"exit_code": 0},
        "validated_at_utc": "2026-07-29T00:00:00Z",
    }
    context = {
        "profile": {"wrong": True},
        "bundle": {"wrong": True},
        "scheduler_test": {"exit_code": 0},
        "destination": str(deployment),
        "interpreter": str(interpreter),
        "interpreter_sha256": payload["interpreter_sha256"],
        "approved_roots": (tmp_path,),
    }
    with pytest.raises(ValueError, match="profile"):
        publish_production_envelope(
            destination,
            "challenge15.dry-run-receipt.v1",
            payload,
            context=context,
        )
    assert not destination.exists()
