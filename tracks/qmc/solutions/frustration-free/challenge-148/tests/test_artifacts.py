from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import challenge148.artifacts as artifacts_module
from challenge148.provenance import canonical_json

from challenge148.artifacts import publish_run, validate_run


def fixture_run_spec() -> dict[str, object]:
    return {
        "beta": 1.5,
        "field": 4.76811,
        "lattice": "triangular",
        "length": 3,
        "stage": "ed",
    }


def fixture_spec_sha256() -> str:
    return hashlib.sha256(canonical_json(fixture_run_spec())).hexdigest()


def default_producer(stage: Path) -> None:
    (stage / "summary.json").write_text(
        json.dumps({"energy": -1.25, "ok": True}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    data_dir = stage / "data"
    data_dir.mkdir()
    (data_dir / "raw.bin").write_bytes(b"challenge-148\n")


def publish_valid_fixture(
    tmp_path: Path,
    *,
    run_spec: dict[str, object] | None = None,
    producer=default_producer,
) -> Path:
    return publish_run(tmp_path, run_spec=run_spec or fixture_run_spec(), producer=producer)


def read_current_pointer(output_root: Path) -> dict[str, object]:
    return json.loads((output_root / "current.json").read_text(encoding="utf-8"))


def failed_stage_directories(output_root: Path) -> list[Path]:
    failed_root = output_root / "failed"
    if not failed_root.exists():
        return []
    return sorted(path for path in failed_root.iterdir() if path.is_dir())


def install_fsync_recorder(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    real_fsync = os.fsync
    recorded: list[Path] = []

    def recording_fsync(fd: int) -> None:
        target = Path(os.readlink(f"/proc/self/fd/{fd}"))
        recorded.append(target.resolve())
        real_fsync(fd)

    monkeypatch.setattr(artifacts_module.os, "fsync", recording_fsync)
    return recorded


def test_failed_first_publication_leaves_no_current_pointer(tmp_path):
    def fail(stage: Path) -> None:
        (stage / "partial.json").write_text("{}", encoding="utf-8")
        raise RuntimeError("injected")

    with pytest.raises(RuntimeError, match="injected"):
        publish_run(tmp_path, run_spec={"stage": "test"}, producer=fail)

    assert not (tmp_path / "current.json").exists()
    failed = failed_stage_directories(tmp_path)
    assert len(failed) == 1
    assert (failed[0] / "partial.json").read_text(encoding="utf-8") == "{}"


def test_publish_run_creates_deterministic_immutable_run_and_current_pointer(tmp_path):
    run_path = publish_valid_fixture(tmp_path)
    expected = tmp_path / "runs" / f"run-{fixture_spec_sha256()}"

    assert run_path == expected
    assert validate_run(run_path, expected_spec_sha256=fixture_spec_sha256())["run_spec_sha256"] == (
        fixture_spec_sha256()
    )

    current = read_current_pointer(tmp_path)
    assert current == {
        "path": f"runs/run-{fixture_spec_sha256()}",
        "run_id": fixture_spec_sha256(),
        "run_spec_sha256": fixture_spec_sha256(),
    }


def test_validation_rejects_symlink_hash_drift_and_unexpected_files(tmp_path):
    run = publish_valid_fixture(tmp_path)
    (run / "summary.json").write_text('{"changed":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())

    run = publish_valid_fixture(tmp_path / "symlinked")
    target = run / "summary.json"
    payload = target.read_text(encoding="utf-8")
    target.unlink()
    os.symlink("data/raw.bin", target)
    with pytest.raises(ValueError, match="symlink"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())

    run = publish_valid_fixture(tmp_path / "unexpected")
    (run / "extra.txt").write_text("surprise\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())


def test_validate_run_rejects_symlinked_run_directory(tmp_path):
    run = publish_valid_fixture(tmp_path)
    alias = tmp_path / "run-alias"
    os.symlink(run, alias, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        validate_run(alias, expected_spec_sha256=fixture_spec_sha256())


@pytest.mark.parametrize("control_name", ["completion.json", "run_spec.json"])
def test_validate_run_rejects_symlinked_control_files(tmp_path, control_name):
    run = publish_valid_fixture(tmp_path)
    control_path = run / control_name
    target_name = "summary.json" if control_name == "completion.json" else "data/raw.bin"
    control_path.unlink()
    os.symlink(target_name, control_path)

    with pytest.raises(ValueError, match="symlink"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())


def test_validate_run_rejects_non_finite_or_malformed_completion_manifest(tmp_path):
    run = publish_valid_fixture(tmp_path)
    completion = run / "completion.json"
    completion.write_text('{"artifacts":{},"run_id":"x","run_spec_sha256":NaN}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite|invalid completion"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())

    completion.write_text('{"run_id":"x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="completion"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())


def test_validate_run_rejects_nested_path_escape_and_stale_spec_hash(tmp_path):
    run = publish_valid_fixture(tmp_path)
    completion = json.loads((run / "completion.json").read_text(encoding="utf-8"))
    completion["artifacts"]["../escape.bin"] = completion["artifacts"].pop("summary.json")
    (run / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed completion|inside run directory|escape"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())

    other_run = publish_valid_fixture(tmp_path / "stale")
    with pytest.raises(ValueError, match="stale spec hash"):
        validate_run(other_run, expected_spec_sha256="0" * 64)


def test_publish_run_rejects_producer_symlink_and_preserves_prior_current(tmp_path):
    winner = publish_valid_fixture(tmp_path)
    winner_current = read_current_pointer(tmp_path)

    def bad_symlink(stage: Path) -> None:
        os.symlink("/tmp/outside", stage / "summary.json")

    with pytest.raises(ValueError, match="symlink"):
        publish_run(tmp_path, run_spec={"stage": "bad"}, producer=bad_symlink)

    assert read_current_pointer(tmp_path) == winner_current
    assert validate_run(winner, expected_spec_sha256=fixture_spec_sha256())["run_id"] == (
        fixture_spec_sha256()
    )
    assert failed_stage_directories(tmp_path)


def test_publish_run_same_spec_conflict_never_overwrites_existing_winner(tmp_path):
    winner = publish_valid_fixture(tmp_path)
    winner_hash = sha256_tree(winner)

    def conflicting(stage: Path) -> None:
        (stage / "summary.json").write_text('{"energy":999.0}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="conflict|immutable"):
        publish_run(tmp_path, run_spec=fixture_run_spec(), producer=conflicting)

    assert sha256_tree(winner) == winner_hash
    assert read_current_pointer(tmp_path)["path"] == f"runs/run-{fixture_spec_sha256()}"
    assert failed_stage_directories(tmp_path)


def test_publish_run_identical_concurrent_publishers_converge(tmp_path):
    barrier = threading.Barrier(2)

    def concurrent_producer(stage: Path) -> None:
        default_producer(stage)
        barrier.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(publish_run, tmp_path, run_spec=fixture_run_spec(), producer=concurrent_producer)
            for _ in range(2)
        ]
    results = [future.result() for future in futures]

    expected = tmp_path / "runs" / f"run-{fixture_spec_sha256()}"
    assert results == [expected, expected]
    assert validate_run(expected, expected_spec_sha256=fixture_spec_sha256())["artifacts"][
        "summary.json"
    ]["sha256"] == hashlib.sha256((expected / "summary.json").read_bytes()).hexdigest()
    archived = failed_stage_directories(tmp_path)
    assert len(archived) == 1
    assert "identical" in archived[0].name


def test_publish_run_fsyncs_every_stage_file_and_directory_before_final_rename(tmp_path, monkeypatch):
    recorded = install_fsync_recorder(monkeypatch)
    real_rename = os.rename
    observed: list[list[Path]] = []

    def checking_rename(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        if dst_path == tmp_path / "runs" / f"run-{fixture_spec_sha256()}":
            snapshot = list(recorded)
            observed.append(snapshot)
            required = {
                (src_path / "summary.json").resolve(),
                (src_path / "data" / "raw.bin").resolve(),
                (src_path / "run_spec.json").resolve(),
                (src_path / "completion.json").resolve(),
                (src_path / "data").resolve(),
                src_path.resolve(),
            }
            assert required.issubset(set(snapshot))
            data_indices = [index for index, path in enumerate(snapshot) if path == (src_path / "data").resolve()]
            stage_indices = [index for index, path in enumerate(snapshot) if path == src_path.resolve()]
            assert data_indices[-1] < stage_indices[-1]
        real_rename(src, dst)

    monkeypatch.setattr(artifacts_module.os, "rename", checking_rename)

    publish_valid_fixture(tmp_path)

    assert len(observed) == 1


@pytest.mark.parametrize("failing_relative_path", ["data/raw.bin", "data"])
def test_publish_run_archives_stage_when_recursive_durability_fails(
    tmp_path, monkeypatch, failing_relative_path
):
    winner = publish_valid_fixture(tmp_path)
    prior_current = read_current_pointer(tmp_path)
    recorded = install_fsync_recorder(monkeypatch)
    captured_stage: dict[str, Path] = {}
    real_fsync = artifacts_module.os.fsync

    def producer(stage: Path) -> None:
        captured_stage["path"] = stage
        default_producer(stage)

    def flaky_fsync(fd: int) -> None:
        target = Path(os.readlink(f"/proc/self/fd/{fd}")).resolve()
        recorded.append(target)
        stage = captured_stage.get("path")
        if stage is not None and target == (stage / failing_relative_path).resolve():
            raise OSError("durability boom")
        real_fsync(fd)

    monkeypatch.setattr(artifacts_module.os, "fsync", flaky_fsync)

    with pytest.raises(OSError, match="durability boom"):
        publish_run(tmp_path, run_spec={"stage": f"durability-{failing_relative_path}"}, producer=producer)

    assert read_current_pointer(tmp_path) == prior_current
    assert validate_run(winner, expected_spec_sha256=fixture_spec_sha256())["run_id"] == (
        fixture_spec_sha256()
    )
    archived = failed_stage_directories(tmp_path)
    assert archived
    assert any("failed" in path.name for path in archived)


def test_publish_run_archives_stage_when_directory_rename_fails(tmp_path, monkeypatch):
    publish_valid_fixture(tmp_path / "seed")
    prior = publish_valid_fixture(tmp_path)
    prior_current = read_current_pointer(tmp_path)
    real_rename = os.rename

    def flaky_rename(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith(f"runs/run-{hashlib.sha256(canonical_json({'stage': 'rename-fail'})).hexdigest()}"):
            raise OSError("rename boom")
        real_rename(src, dst)

    monkeypatch.setattr("challenge148.artifacts.os.rename", flaky_rename)

    with pytest.raises(OSError, match="rename boom"):
        publish_run(
            tmp_path,
            run_spec={"stage": "rename-fail"},
            producer=lambda stage: (stage / "summary.json").write_text("{}\n", encoding="utf-8"),
        )

    assert read_current_pointer(tmp_path) == prior_current
    assert validate_run(prior, expected_spec_sha256=fixture_spec_sha256())["run_id"] == (
        fixture_spec_sha256()
    )
    assert failed_stage_directories(tmp_path)


def test_publish_run_rolls_back_new_immutable_run_when_current_replace_fails(tmp_path, monkeypatch):
    winner = publish_valid_fixture(tmp_path)
    prior_current = read_current_pointer(tmp_path)
    real_replace = os.replace
    real_fsync_directory = __import__("challenge148.artifacts", fromlist=["_fsync_directory"])._fsync_directory
    spec = {"stage": "replace-fail"}
    spec_hash = hashlib.sha256(canonical_json(spec)).hexdigest()
    fsynced_paths: list[Path] = []

    def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(dst) == tmp_path / "current.json":
            raise OSError("replace boom")
        real_replace(src, dst)

    def tracking_fsync_directory(path: Path) -> None:
        fsynced_paths.append(Path(path))
        real_fsync_directory(path)

    monkeypatch.setattr("challenge148.artifacts.os.replace", flaky_replace)
    monkeypatch.setattr("challenge148.artifacts._fsync_directory", tracking_fsync_directory)

    with pytest.raises(OSError, match="replace boom"):
        publish_run(
            tmp_path,
            run_spec=spec,
            producer=lambda stage: (stage / "summary.json").write_text("{}\n", encoding="utf-8"),
        )

    assert read_current_pointer(tmp_path) == prior_current
    assert not (tmp_path / "runs" / f"run-{spec_hash}").exists()
    assert validate_run(winner, expected_spec_sha256=fixture_spec_sha256())["run_id"] == (
        fixture_spec_sha256()
    )
    assert failed_stage_directories(tmp_path)
    assert tmp_path / "runs" in fsynced_paths
    assert tmp_path / "failed" in fsynced_paths


def test_publish_run_archives_stage_when_fsync_fails(tmp_path, monkeypatch):
    real_fsync = os.fsync
    counter = {"count": 0}

    def flaky_fsync(fd: int) -> None:
        counter["count"] += 1
        if counter["count"] == 4:
            raise OSError("fsync boom")
        real_fsync(fd)

    monkeypatch.setattr("challenge148.artifacts.os.fsync", flaky_fsync)

    with pytest.raises(OSError, match="fsync boom"):
        publish_run(
            tmp_path,
            run_spec={"stage": "fsync-fail"},
            producer=lambda stage: (stage / "summary.json").write_text("{}\n", encoding="utf-8"),
        )

    assert not (tmp_path / "current.json").exists()
    assert failed_stage_directories(tmp_path)


def sha256_tree(root: Path) -> dict[str, str]:
    hashed: dict[str, str] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        hashed[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashed
