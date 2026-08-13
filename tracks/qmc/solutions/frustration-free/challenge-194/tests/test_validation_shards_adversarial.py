from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Barrier, Thread

import pytest

import long_range_percolation.validation_shards as shards
from long_range_percolation.validation import ValidationProtocol


def _reduced() -> ValidationProtocol:
    return ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.0, 0.25),
        samples=3,
        replicates=5,
    )


@pytest.fixture(autouse=True)
def clean_source(monkeypatch: pytest.MonkeyPatch):
    revision = shards._repository_state()["source_revision"]
    monkeypatch.setattr(
        shards,
        "_repository_state",
        lambda: {
            "source_revision": revision,
            "clean_tree": True,
            "provenance_error": None,
        },
    )


def _prepared(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = (tmp_path / "run").resolve()
    spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_reduced(), root, spec_path)
    shards._run_test_global_checks(spec_path)
    for index in range(2):
        shards._run_test_cell(spec_path, index)
    return spec_path, json.loads(spec_path.read_text(encoding="utf-8"))


def _rewrite_spec(path: Path, mutate) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    document["run_spec_sha256"] = shards._document_hash(
        document, "run_spec_sha256"
    )
    path.write_bytes(shards._canonical_bytes(document))
    return document


def _rewrite_artifact(
    spec_path: Path,
    spec: dict[str, object],
    *,
    cell_index: int | None,
    mutate,
) -> None:
    if cell_index is None:
        partial_relative = spec["global_partial_path"]
        manifest_relative = spec["global_manifest_path"]
    else:
        partial_relative = spec["cells"][cell_index]["partial_path"]
        manifest_relative = spec["cells"][cell_index]["manifest_path"]
    partial = spec_path.parent / partial_relative
    manifest = spec_path.parent / manifest_relative
    document = json.loads(partial.read_text(encoding="utf-8"))
    mutate(document)
    payload = shards._canonical_bytes(document)
    partial.write_bytes(payload)
    manifest_document = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_document["artifact_sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_document["artifact_size"] = len(payload)
    manifest.write_bytes(shards._canonical_bytes(manifest_document))


def test_dirty_source_fails_before_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(
        shards,
        "_repository_state",
        lambda: {
            "source_revision": "a" * 40,
            "clean_tree": False,
            "provenance_error": None,
        },
    )
    root = (tmp_path / "dirty").resolve()
    with pytest.raises(RuntimeError, match="clean"):
        shards.build_validation_run_spec(
            ValidationProtocol.production_v1(), root
        )
    assert not root.exists()


@pytest.mark.parametrize("command", ("write", "global", "cell", "merge"))
def test_dirty_source_fails_every_invocation_before_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
):
    root = (tmp_path / command).resolve()
    spec_path = root / "run_spec.json"
    protocol = ValidationProtocol.production_v1()
    shards._write_test_run_spec(protocol, root, spec_path)
    revision = json.loads(spec_path.read_text(encoding="utf-8"))[
        "source_revision"
    ]
    monkeypatch.setattr(
        shards,
        "_repository_state",
        lambda: {
            "source_revision": revision,
            "clean_tree": False,
            "provenance_error": None,
        },
    )
    invocation = {
        "write": lambda: shards.write_validation_run_spec(
            protocol, root, spec_path
        ),
        "global": lambda: shards.run_validation_global_checks(spec_path),
        "cell": lambda: shards.run_validation_cell(spec_path, 0),
        "merge": lambda: shards.merge_validation_shards(
            spec_path, root / "report" / "report.json"
        ),
    }[command]
    with pytest.raises(RuntimeError, match="clean"):
        invocation()
    assert not (root / "global").exists()
    assert not (root / "cells").exists()
    assert not (root / "report").exists()


def test_reduced_spec_fails_every_public_execution_command(tmp_path: Path):
    root = (tmp_path / "reduced").resolve()
    spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_reduced(), root, spec_path)
    with pytest.raises((RuntimeError, ValueError), match="production"):
        shards.run_validation_global_checks(spec_path)
    with pytest.raises((RuntimeError, ValueError), match="production"):
        shards.run_validation_cell(spec_path, 0)
    with pytest.raises((RuntimeError, ValueError), match="production"):
        shards.merge_validation_shards(
            spec_path, root / "report" / "report.json"
        )
    with pytest.raises((RuntimeError, ValueError), match="production"):
        shards.build_validation_run_spec(_reduced(), root)


def test_implementation_hash_change_fails_before_compute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    root = (tmp_path / "implementation").resolve()
    spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_reduced(), root, spec_path)
    hashes = shards._implementation_hashes()
    changed = dict(hashes)
    changed[next(iter(changed))] = "0" * 64
    monkeypatch.setattr(shards, "_implementation_hashes", lambda: changed)
    with pytest.raises(RuntimeError, match="implementation"):
        shards._run_test_cell(spec_path, 0)
    assert not (root / "cells").exists()


@pytest.mark.parametrize(
    "mutation",
    (
        lambda spec: spec.__setitem__("global_partial_path", "../outside.json"),
        lambda spec: spec.__setitem__(
            "global_manifest_path", spec["global_partial_path"]
        ),
        lambda spec: spec["cells"][1].__setitem__(
            "partial_path", spec["cells"][0]["partial_path"]
        ),
    ),
    ids=("outside-root", "overlap", "duplicate-artifact"),
)
def test_run_spec_rejects_unsafe_or_duplicate_paths(
    tmp_path: Path, mutation
):
    root = (tmp_path / "unsafe").resolve()
    spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_reduced(), root, spec_path)
    _rewrite_spec(spec_path, mutation)
    with pytest.raises(RuntimeError):
        shards._run_test_global_checks(spec_path)


def test_symlinked_report_directory_is_rejected(tmp_path: Path):
    spec_path, spec = _prepared(tmp_path)
    report_directory = spec_path.parent / "report"
    outside = tmp_path / "outside"
    outside.mkdir()
    report_directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        shards._merge_test_shards(spec_path)
    assert not (outside / "report.json").exists()


def test_arbitrary_merge_output_is_rejected(tmp_path: Path):
    spec_path, _ = _prepared(tmp_path)
    with pytest.raises(RuntimeError, match="fixed"):
        shards._merge_test_shards(spec_path, tmp_path / "arbitrary.json")


def test_existing_valid_final_report_is_idempotent_but_different_is_rejected(
    tmp_path: Path,
):
    spec_path, spec = _prepared(tmp_path)
    first = shards._merge_test_shards(spec_path)
    report = spec_path.parent / spec["final_report_path"]
    before = report.stat().st_mtime_ns
    second = shards._merge_test_shards(spec_path)
    assert first == second
    assert report.stat().st_mtime_ns == before
    report.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="immutable|existing"):
        shards._merge_test_shards(spec_path)
    assert report.read_text(encoding="utf-8") == "{}\n"


@pytest.mark.parametrize(
    "mutation",
    (
        lambda records: records.pop(),
        lambda records: records.append(dict(records[0])),
        lambda records: records.append(
            {
                **records[0],
                "check_id": "extra",
            }
        ),
        lambda records: records.reverse(),
        lambda records: records[0].__setitem__("case_id", "other-case"),
        lambda records: records[0].__setitem__("family", "other-family"),
        lambda records: records[0]["check"].__setitem__(
            "case_id", "cross-cell/check"
        ),
    ),
    ids=(
        "missing",
        "duplicate",
        "extra",
        "reordered",
        "cross-case",
        "family-substituted",
        "cross-cell-inner",
    ),
)
def test_merge_rejects_noncanonical_cell_check_registry(
    tmp_path: Path, mutation
):
    spec_path, spec = _prepared(tmp_path)
    _rewrite_artifact(
        spec_path,
        spec,
        cell_index=0,
        mutate=lambda document: mutation(document["check_records"]),
    )
    with pytest.raises(RuntimeError, match="check registry"):
        shards._merge_test_shards(spec_path)


def test_cell_rejects_global_check_and_global_rejects_case_check(tmp_path: Path):
    spec_path, spec = _prepared(tmp_path)
    global_artifact = json.loads(
        (spec_path.parent / spec["global_partial_path"]).read_text(encoding="utf-8")
    )
    cell_artifact = json.loads(
        (
            spec_path.parent / spec["cells"][0]["partial_path"]
        ).read_text(encoding="utf-8")
    )
    _rewrite_artifact(
        spec_path,
        spec,
        cell_index=0,
        mutate=lambda document: document["check_records"].__setitem__(
            0, global_artifact["check_records"][0]
        ),
    )
    with pytest.raises(RuntimeError, match="check registry"):
        shards._merge_test_shards(spec_path)

    # Restore the cell and independently substitute a case record globally.
    (spec_path.parent / spec["cells"][0]["partial_path"]).unlink()
    (spec_path.parent / spec["cells"][0]["manifest_path"]).unlink()
    shards._run_test_cell(spec_path, 0)
    _rewrite_artifact(
        spec_path,
        spec,
        cell_index=None,
        mutate=lambda document: document["check_records"].__setitem__(
            0, cell_artifact["check_records"][0]
        ),
    )
    with pytest.raises(RuntimeError, match="check registry"):
        shards._merge_test_shards(spec_path)


def test_concurrent_no_clobber_accepts_identical_and_rejects_different(
    tmp_path: Path,
):
    identical = tmp_path / "identical.json"
    barrier = Barrier(2)
    errors: list[Exception] = []

    def publish(path: Path, payload: bytes) -> None:
        try:
            barrier.wait()
            shards._write_once(path, payload)
        except Exception as error:
            errors.append(error)

    threads = [
        Thread(target=publish, args=(identical, b'{"same":true}\n'))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert identical.read_bytes() == b'{"same":true}\n'

    different = tmp_path / "different.json"
    barrier = Barrier(2)
    errors.clear()
    threads = [
        Thread(target=publish, args=(different, payload))
        for payload in (b'{"winner":1}\n', b'{"winner":2}\n')
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(errors) == 1
    assert different.read_bytes() in (b'{"winner":1}\n', b'{"winner":2}\n')
