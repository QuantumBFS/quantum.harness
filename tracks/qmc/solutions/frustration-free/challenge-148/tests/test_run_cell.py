from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from challenge148.acceptance import _adapter_request_hash
from challenge148.extension import build_directed_extension_plan
from challenge148.planning import build_coarse_plan
from challenge148.provenance import canonical_json
from test_acceptance import _bin


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = ROOT / "preregistration" / "coarse-crossing-v1.json"
EXTENSION_PREREGISTRATION = ROOT / "preregistration" / "directed-extension-v1.json"


def _completed_evidence(cell_root: Path) -> Path:
    entries = list((cell_root / "completed-evidence").iterdir())
    assert len(entries) == 1
    return entries[0]


def _completion_path(cell_root: Path) -> Path:
    return _completed_evidence(cell_root) / "completion.json"


def _has_completed_evidence(cell_root: Path) -> bool:
    root = cell_root / "completed-evidence"
    return root.is_dir() and any(root.iterdir())
BUILD_INFO = {
    "adapter": "QMC_SSE",
    "source_hash": "a" * 64,
    "build_hash": "b" * 64,
}
RUN_CELL_PATH = ROOT / "scripts" / "run_cell.py"


def _load_runner():
    specification = importlib.util.spec_from_file_location("challenge148_run_cell", RUN_CELL_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_memfd_creation_falls_back_to_direct_syscall(monkeypatch):
    runner = _load_runner()
    monkeypatch.delattr(runner.os, "memfd_create", raising=False)

    descriptor = runner._memfd_create("challenge148-test")
    try:
        os.write(descriptor, b"sealed")
        os.lseek(descriptor, 0, os.SEEK_SET)
        assert os.read(descriptor, 6) == b"sealed"
    finally:
        os.close(descriptor)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plan_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    plan = build_coarse_plan(
        json.loads(PREREGISTRATION.read_text(encoding="utf-8")),
        BUILD_INFO,
        tmp_path,
    )
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, plan)
    return plan_path, plan


def _extension_plan_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    plan = build_directed_extension_plan(
        json.loads(EXTENSION_PREREGISTRATION.read_text(encoding="utf-8")),
        BUILD_INFO,
        tmp_path,
    )
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, plan)
    return plan_path, plan


def _fake_executable(
    path: Path,
    *,
    build_info: dict[str, object] = BUILD_INFO,
    launch_exit: int = 0,
    semantic_output: bool = False,
) -> None:
    body = f"""#!{sys.executable}
import json
import pathlib
import sys

BUILD = {build_info!r}
if sys.argv[1:] == ["--build-info"]:
    print(json.dumps(BUILD, sort_keys=True))
    raise SystemExit(0)

request_fd = int(sys.argv[sys.argv.index("--request-fd") + 1])
output_fd = int(sys.argv[sys.argv.index("--output-directory-fd") + 1])
request = pathlib.Path(f"/proc/self/fd/{{request_fd}}")
output = pathlib.Path(f"/proc/self/fd/{{output_fd}}")
count_path = output / "launch-count"
count = int(count_path.read_text()) + 1 if count_path.exists() else 1
count_path.write_text(str(count))
(output / "saw-existing-output").write_text(str(count > 1 or (output / "partial").exists()))
if {launch_exit}:
    print("adapter stdout", flush=True)
    print("adapter failed", file=sys.stderr, flush=True)
    raise SystemExit({launch_exit})
if {semantic_output!r}:
    if (output / "current-generation.json").exists():
        raise SystemExit(0)
    sys.path.insert(0, {str(ROOT / ".venv/lib/python3.12/site-packages")!r})
    sys.path.insert(0, {str(ROOT / "src")!r})
    sys.path.insert(0, {str(ROOT / "tests")!r})
    from test_run_cell import _write_real_output_fixture
    _write_real_output_fixture(output, json.loads(request.read_text()))
    raise SystemExit(0)
(output / "current-generation.json").write_text(
    json.dumps({{"generation_sha256": "c" * 64}}, sort_keys=True) + "\\n"
)
"""
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _write_canonical(path: Path, value: object) -> bytes:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _write_real_output_fixture(output: Path, request: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    request_hash = _adapter_request_hash(request, "QMC_SSE")
    state = output / ".qmc-sse-lock-state"
    state.mkdir()
    lock = state / ".qmc-sse.lock"
    identity = state / "identity.json"
    lock.touch()
    _write_canonical(identity, {"request_sha256": request_hash})
    state_stat, lock_stat, identity_stat = state.stat(), lock.stat(), identity.stat()
    binding = {
        "identity_device": identity_stat.st_dev,
        "identity_inode": identity_stat.st_ino,
        "lock_device": lock_stat.st_dev,
        "lock_inode": lock_stat.st_ino,
        "output_namespace": (
            f"qmc-sse-fd-output-v1:{output.stat().st_dev}:{output.stat().st_ino}"
        ),
        "request_sha256": request_hash,
        "schema_version": "qmc-sse-lock-state-binding-v2",
        "state_device": state_stat.st_dev,
        "state_inode": state_stat.st_ino,
    }
    anchor = {
        key: value for key, value in binding.items() if key != "schema_version"
    } | {
        "schema_version": "qmc-sse-run-lock-anchor-v2",
        "lock_state_identity_sha256": hashlib.sha256(
            canonical_json(binding)
        ).hexdigest(),
    }
    anchor_payload = canonical_json(anchor) + b"\n"
    anchor_hash = hashlib.sha256(anchor_payload).hexdigest()
    anchor_path = output / "run-lock-anchors" / f"{anchor_hash}.json"
    anchor_path.parent.mkdir()
    anchor_path.write_bytes(anchor_payload)
    os.link(anchor_path, anchor_path.with_suffix(".pin"))
    anchor_stat = anchor_path.stat()
    _write_canonical(
        output / "run-lock-anchor.json",
        {
            "schema_version": "qmc-sse-run-lock-anchor-selection-v1",
            "anchor_device": anchor_stat.st_dev,
            "anchor_inode": anchor_stat.st_ino,
            "anchor_sha256": anchor_hash,
            "path": f"run-lock-anchors/{anchor_hash}.json",
        },
    )

    bin_hashes = []
    for index in range(16):
        payload = canonical_json(_bin("QMC_SSE", index)) + b"\n"
        digest = hashlib.sha256(payload).hexdigest()
        (output / "bins").mkdir(exist_ok=True)
        (output / "bins" / f"{digest}.ndjson").write_bytes(payload)
        bin_hashes.append(digest)
    manifest = {
        "schema_version": "qmc-checkpoint-generation-v2",
        "anchor_sha256": anchor_hash,
        "request_sha256": request_hash,
        "adapter": "QMC_SSE",
        "source_hash": request["expected_source_hash"],
        "build_hash": request["expected_build_hash"],
        "seed": request["seed"],
        "completed_bin_count": 16,
        "bin_object_hashes": bin_hashes,
        "previous_generation_sha256": None,
        "replay_update_count": 4_200,
    }
    manifest_payload = canonical_json(manifest) + b"\n"
    generation_hash = hashlib.sha256(manifest_payload).hexdigest()
    manifest_path = output / "generations" / generation_hash / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(manifest_payload)
    _write_canonical(
        output / "current-generation.json",
        {
            "schema_version": "qmc-current-generation-v2",
            "anchor_sha256": anchor_hash,
            "generation_sha256": generation_hash,
            "path": f"generations/{generation_hash}",
        },
    )


def _patch_validator(monkeypatch, runner, calls: list[tuple[Path, dict, str, Path]]) -> None:
    def validate(output, request, adapter, *, graph, output_namespace, archival=False):
        pointer = os.open(
            "current-generation.json",
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=output,
        )
        try:
            payload = os.pread(pointer, 1_000_000, 0)
            metadata = os.fstat(pointer)
        finally:
            os.close(pointer)
        if not archival:
            calls.append((Path(output_namespace), request, adapter, Path(graph["lattice"])))
        return {
            "records": [{"bin_index": index} for index in range(16)],
            "current_generation_payload": payload,
            "current_generation_identity": [metadata.st_dev, metadata.st_ino],
            "descriptor_snapshot": {
                "directories": [],
                "files": [
                    {
                        "path": ["current-generation.json"],
                        "identity": [metadata.st_dev, metadata.st_ino],
                        "payload": payload,
                        "label": "current generation pointer",
                    }
                ],
                "enumerations": [],
            },
            "semantic_snapshot_sha256": hashlib.sha256(
                canonical_json(
                    {
                        "files": [
                            {
                                "path": ["current-generation.json"],
                                "sha256": hashlib.sha256(payload).hexdigest(),
                            }
                        ],
                        "enumerations": [],
                    }
                )
            ).hexdigest(),
        }

    monkeypatch.setattr(runner, "validate_qmc_adapter_output_descriptor", validate)


def test_plan_validation_dispatches_only_exact_known_schema(monkeypatch):
    runner = _load_runner()
    calls = []
    monkeypatch.setattr(runner, "validate_plan", lambda plan: calls.append("coarse"))
    monkeypatch.setattr(
        runner,
        "validate_directed_extension_plan",
        lambda plan: calls.append("extension"),
    )

    runner._validate_plan_schema({"schema_version": "challenge148-coarse-plan-v1"})
    runner._validate_plan_schema(
        {"schema_version": "challenge148-directed-extension-plan-v1"}
    )

    assert calls == ["coarse", "extension"]
    with pytest.raises(ValueError, match="unknown plan schema_version"):
        runner._validate_plan_schema(
            {"schema_version": "challenge148-directed-extension-plan-v2"}
        )


def test_valid_extension_cell_executes_and_completed_cell_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _extension_plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)

    first = runner.run_cell(plan_path, 23, executable, timeout=5)
    second = runner.run_cell(plan_path, 23, executable, timeout=5)

    assert first == second
    assert (first / "adapter-output" / "launch-count").read_text() == "1"
    assert json.loads(_completion_path(first).read_text())["cell_id"] == (
        plan["cells"][23]["cell_id"]
    )
    assert len(calls) == 1


@pytest.mark.parametrize("schema", ["unknown", "challenge148-directed-extension-plan-v2"])
def test_unknown_schema_rejected_before_build_info(
    tmp_path: Path, schema: str
):
    runner = _load_runner()
    plan_path, _ = _extension_plan_fixture(tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["schema_version"] = schema
    _write_json(plan_path, plan)
    launched = tmp_path / "launched"
    executable = tmp_path / "qmc-sse"
    _write_executable = f"#!/bin/sh\nprintf launched > {str(launched)!r}\nexit 0\n"
    executable.write_text(_write_executable)
    executable.chmod(0o755)

    with pytest.raises(ValueError, match="schema_version"):
        runner.run_cell(plan_path, 0, executable, timeout=5)

    assert not launched.exists()


def test_mutated_extension_rejected_before_build_info(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _extension_plan_fixture(tmp_path)
    plan["cells"][0]["field"] += 0.1
    _write_json(plan_path, plan)
    launched = tmp_path / "launched"
    executable = tmp_path / "qmc-sse"
    executable.write_text(f"#!/bin/sh\nprintf launched > {str(launched)!r}\nexit 0\n")
    executable.chmod(0o755)

    with pytest.raises(ValueError, match="plan_sha256"):
        runner.run_cell(plan_path, 0, executable, timeout=5)

    assert not launched.exists()


@pytest.mark.parametrize("index", [-1, 72])
def test_cell_index_must_be_in_frozen_plan_bounds(tmp_path: Path, index: int):
    runner = _load_runner()
    plan_path, _ = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)

    with pytest.raises(ValueError, match="cell index"):
        runner.run_cell(plan_path, index, executable, timeout=5)


@pytest.mark.parametrize("damage", ["request", "graph", "build"])
def test_plan_artifact_and_executable_hash_mismatches_fail_closed(
    tmp_path: Path, damage: str
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    cell = plan["cells"][0]
    assert isinstance(cell, dict)
    executable = tmp_path / "qmc-sse"
    build_info = BUILD_INFO
    if damage == "request":
        request = json.loads((tmp_path / cell["request_path"]).read_text())
        request["seed"] += 1
        _write_json(tmp_path / cell["request_path"], request)
    elif damage == "graph":
        graph = json.loads((tmp_path / cell["graph_path"]).read_text())
        graph["site_count"] += 1
        _write_json(tmp_path / cell["graph_path"], graph)
    else:
        build_info = dict(BUILD_INFO, build_hash="0" * 64)
    _fake_executable(executable, build_info=build_info)

    with pytest.raises(ValueError, match=damage):
        runner.run_cell(plan_path, 0, executable, timeout=5)

    assert not _has_completed_evidence(tmp_path / "cells" / cell["cell_id"])


def test_fully_validated_completed_cell_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)

    first = runner.run_cell(plan_path, 0, executable, timeout=5)
    second = runner.run_cell(plan_path, 0, executable, timeout=5)

    assert first == second
    assert (first / "adapter-output" / "launch-count").read_text() == "1"
    assert len(calls) == 1
    completion = json.loads(_completion_path(first).read_text())
    assert completion["cell_id"] == plan["cells"][0]["cell_id"]
    assert completion["request_sha256"] == plan["cells"][0]["request_sha256"]


def test_matching_partial_output_is_replayed_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    cell = plan["cells"][0]
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    output = tmp_path / "cells" / cell["cell_id"] / "adapter-output"
    identity = output / ".qmc-sse-lock-state" / "identity.json"
    _write_json(
        identity,
        {
            "schema_version": "qmc-sse-lock-identity-v2",
            "request_sha256": cell["request_sha256"],
        },
    )
    (output / "partial").write_text("interrupted", encoding="utf-8")
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)

    result = runner.run_cell(plan_path, 0, executable, timeout=5)

    assert result == output.parent
    assert (output / "saw-existing-output").read_text() == "True"
    assert _completion_path(result).is_file()
    assert len(calls) == 1


def test_adapter_failure_is_propagated_and_logged_immutably(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, launch_exit=9)

    with pytest.raises(RuntimeError, match="exit 9"):
        runner.run_cell(plan_path, 0, executable, timeout=5)

    cell = plan["cells"][0]
    cell_root = tmp_path / "cells" / cell["cell_id"]
    logs = list((cell_root / "logs").glob("*.json"))
    assert logs
    for log in logs:
        payload = log.read_bytes()
        assert log.stem == hashlib.sha256(payload).hexdigest()
        assert payload == canonical_json(json.loads(payload)) + b"\n"
    assert not _has_completed_evidence(cell_root)


def test_success_is_semantically_validated_before_immutable_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)

    result = runner.run_cell(plan_path, 1, executable, timeout=5)

    cell = plan["cells"][1]
    completion_path = _completion_path(result)
    payload = completion_path.read_bytes()
    completion = json.loads(payload)
    assert payload == canonical_json(completion) + b"\n"
    assert not (result / "completion.json").exists()
    assert not (result / "evidence-snapshots").exists()
    assert completion == {
        "schema_version": "challenge148-production-cell-completion-v3",
        "cell_id": cell["cell_id"],
        "cell_index": 1,
        "plan_sha256": plan["plan_sha256"],
        "request_sha256": cell["request_sha256"],
        "graph_sha256": cell["graph_sha256"],
        "build_info_sha256": hashlib.sha256(
            canonical_json(plan["build_info"])
        ).hexdigest(),
        "executable_sha256": completion["executable_sha256"],
        "semantic_snapshot_sha256": completion["semantic_snapshot_sha256"],
        "current_generation_sha256": hashlib.sha256(
            (result / "adapter-output" / "current-generation.json").read_bytes()
        ).hexdigest(),
        "log_sha256": completion["log_sha256"],
    }
    assert len(completion["log_sha256"]) == 2
    assert len(calls) == 1


@pytest.mark.parametrize(
    "component", ["cells", "cell", "logs", "adapter-output", "completed-evidence"]
)
def test_output_ancestry_never_follows_preexisting_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, component: str
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    cell = plan["cells"][0]
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    outside = tmp_path / "outside"
    outside.mkdir()
    cells = tmp_path / "cells"
    cell_root = cells / cell["cell_id"]
    if component == "cells":
        cells.symlink_to(outside, target_is_directory=True)
    else:
        cells.mkdir()
        if component == "cell":
            cell_root.symlink_to(outside, target_is_directory=True)
        else:
            cell_root.mkdir()
            target = cell_root / component
            target.symlink_to(outside, target_is_directory=True)
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)

    with pytest.raises(ValueError, match="symlink|directory|completion|output"):
        runner.run_cell(plan_path, 0, executable, timeout=5)

    assert not (outside / "current-generation.json").exists()


def test_snapshot_creation_rejects_raced_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    cell = plan["cells"][0]
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    outside = tmp_path / "outside"
    outside.mkdir()

    def hook(event, details):
        if event == "before_snapshot_create":
            (Path(details["cell_root"]) / details["name"]).symlink_to(
                outside, target_is_directory=True
            )

    with pytest.raises(ValueError, match="snapshot"):
        runner.run_cell(plan_path, 0, executable, timeout=5, race_hook=hook)

    assert list(outside.iterdir()) == []
    assert not _has_completed_evidence(tmp_path / "cells" / cell["cell_id"])


def test_real_semantic_validator_controls_completion(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)

    result = runner.run_cell(plan_path, 0, executable, timeout=5)

    completion = json.loads(_completion_path(result).read_text())
    assert completion["request_sha256"] == plan["cells"][0]["request_sha256"]
    assert completion["current_generation_sha256"] == hashlib.sha256(
        (result / "adapter-output" / "current-generation.json").read_bytes()
    ).hexdigest()


@pytest.mark.parametrize("artifact", ["pointer", "manifest", "bin"])
@pytest.mark.parametrize("completed", [False, True])
def test_artifact_replacement_cannot_cross_semantic_validation_boundary(
    tmp_path: Path, completed: bool, artifact: str
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    if completed:
        runner.run_cell(plan_path, 0, executable, timeout=5)

    fired = False

    def hook(event, details):
        nonlocal fired
        expected_event = (
            "after_completed_evidence_validation"
            if completed
            else "after_output_validation"
        )
        if not fired and event == expected_event:
            fired = True
            if completed:
                output = _completed_evidence(cell_root) / "output"
            else:
                output = cell_root / "adapter-output"
            pointer = output / "current-generation.json"
            pointer_value = json.loads(pointer.read_text())
            manifest = output / pointer_value["path"] / "manifest.json"
            if artifact == "pointer":
                victim = pointer
            elif artifact == "manifest":
                victim = manifest
            else:
                manifest_value = json.loads(manifest.read_text())
                victim = (
                    output
                    / "bins"
                    / f"{manifest_value['bin_object_hashes'][0]}.ndjson"
                )
            replacement = victim.with_suffix(".replacement")
            replacement.write_text("{}\n")
            os.replace(replacement, victim)

    with pytest.raises(ValueError, match="identity|bytes|changed|hash|invalid"):
        runner.run_cell(
            plan_path, 0, executable, timeout=5, race_hook=hook
        )
    assert fired
    if not completed:
        assert not _has_completed_evidence(cell_root)


def test_mutation_before_atomic_completed_evidence_rename_fails(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    fired = False

    def hook(event, details):
        nonlocal fired
        if event == "before_completed_evidence_publish":
            fired = True
            pointer = Path(details["staged_path"]) / "output" / "current-generation.json"
            replacement = pointer.with_suffix(".replacement")
            replacement.write_text("{}\n")
            os.replace(replacement, pointer)

    with pytest.raises(ValueError, match="hash|invalid|mismatch"):
        runner.run_cell(plan_path, 0, executable, timeout=5, race_hook=hook)

    assert fired
    assert not _has_completed_evidence(cell_root)
    assert _completion_path(runner.run_cell(plan_path, 0, executable, timeout=5)).is_file()


def test_completed_evidence_directories_are_fsynced_bottom_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    root = tmp_path / "tree"
    (root / "output" / "generations" / "generation").mkdir(parents=True)
    (root / "output" / "bins").mkdir()
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    observed: list[tuple[str, ...]] = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: None)
    try:
        runner._fsync_directories_bottom_up(
            descriptor,
            [
                (),
                ("output",),
                ("output", "bins"),
                ("output", "generations"),
                ("output", "generations", "generation"),
            ],
            observer=lambda path: observed.append(tuple(path)),
        )
    finally:
        monkeypatch.setattr(os, "fsync", real_fsync)
        os.close(descriptor)

    assert observed == [
        ("output", "generations", "generation"),
        ("output", "bins"),
        ("output", "generations"),
        ("output",),
        (),
    ]


def test_completed_publication_fsyncs_every_staged_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, _ = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    observed: list[tuple[str, ...]] = []
    original = runner._fsync_directories_bottom_up

    def record(root, paths, *, observer=None):
        original(
            root,
            paths,
            observer=lambda path: observed.append(tuple(path)),
        )

    monkeypatch.setattr(runner, "_fsync_directories_bottom_up", record)
    result = runner.run_cell(plan_path, 0, executable, timeout=5)
    completed = _completed_evidence(result)
    expected = {()}
    for directory, names, _ in os.walk(completed / "output"):
        relative = Path(directory).relative_to(completed)
        expected.add(relative.parts)

    assert expected <= set(observed)
    assert all(observed.count(path) == 2 for path in expected)


def test_competing_completed_evidence_publisher_reuses_identical_winner(
    tmp_path: Path,
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    fired = False

    def hook(event, details):
        nonlocal fired
        if event == "before_completed_evidence_publish":
            fired = True
            destination = (
                cell_root / "completed-evidence" / details["completed_evidence_sha256"]
            )
            shutil.copytree(details["staged_path"], destination)

    result = runner.run_cell(plan_path, 0, executable, timeout=5, race_hook=hook)

    assert fired
    assert _completion_path(result).is_file()
    assert len(list((result / "completed-evidence").iterdir())) == 1


@pytest.mark.parametrize(
    ("location", "kind"),
    [
        ("completed-parent", "file"),
        ("completed-root", "directory"),
        ("output-root", "symlink"),
        ("nested-output", "file"),
        ("type-change", "directory"),
    ],
)
def test_completed_skip_rejects_any_extra_member_or_type_change(
    tmp_path: Path, location: str, kind: str
):
    runner = _load_runner()
    plan_path, _ = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    result = runner.run_cell(plan_path, 0, executable, timeout=5)
    completed = _completed_evidence(result)
    if location == "completed-parent":
        target = result / "completed-evidence" / "extra"
    elif location == "completed-root":
        target = completed / "extra"
    elif location == "output-root":
        target = completed / "output" / "extra"
    elif location == "nested-output":
        target = completed / "output" / "bins" / "extra"
    else:
        target = completed / "manifest.json"
        target.unlink()
    if kind == "file":
        target.write_text("extra")
    elif kind == "directory":
        target.mkdir()
    else:
        target.symlink_to(completed / "completion.json")

    with pytest.raises(ValueError, match="member|membership|type|directory|file"):
        runner.run_cell(plan_path, 0, executable, timeout=5)


def test_cell_root_replacement_before_publication_fails_without_completion(
    tmp_path: Path
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    displaced = tmp_path / "displaced-cell"
    fired = False

    def hook(event, details):
        nonlocal fired
        if event == "before_completed_evidence_publish":
            fired = True
            cell_root.rename(displaced)
            cell_root.mkdir()

    with pytest.raises(ValueError, match="cell root.*identity"):
        runner.run_cell(
            plan_path, 0, executable, timeout=5, race_hook=hook
        )

    assert fired
    assert not _has_completed_evidence(cell_root)
    assert not _has_completed_evidence(displaced)


def test_timeout_terminates_descendant_group_and_drains_evidence(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    executable.write_text(
        f"""#!/usr/bin/env python3
import json, os, pathlib, signal, sys, time
if sys.argv[1:] == ["--build-info"]:
    print(json.dumps({BUILD_INFO!r}, sort_keys=True))
    raise SystemExit(0)
output_fd = int(sys.argv[sys.argv.index("--output-directory-fd") + 1])
output = pathlib.Path(f"/proc/self/fd/{{output_fd}}")
child = os.fork()
if child == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    heartbeat = output / "heartbeat"
    while True:
        heartbeat.write_text(str(time.time_ns()))
        time.sleep(0.02)
time.sleep(60)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    with pytest.raises(RuntimeError, match="timed out"):
        runner.run_cell(plan_path, 0, executable, timeout=1)

    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    heartbeat = cell_root / "adapter-output" / "heartbeat"
    before = heartbeat.read_bytes()
    time.sleep(0.15)
    assert heartbeat.read_bytes() == before
    evidence = [
        json.loads(path.read_text())
        for path in (cell_root / "logs").glob("*.json")
    ]
    timeout_log = next(item for item in evidence if item["timed_out"])
    assert timeout_log["process_group_terminated"] is True
    assert timeout_log["stdout_drained"] is True
    assert not _has_completed_evidence(cell_root)


def test_timeout_kills_term_ignoring_descendant_after_pipe_drain(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    executable.write_text(
        f"""#!{sys.executable}
import json, os, pathlib, signal, sys, time
if sys.argv[1:] == ["--build-info"]:
    print(json.dumps({BUILD_INFO!r}, sort_keys=True))
    raise SystemExit(0)
output_fd = int(sys.argv[sys.argv.index("--output-directory-fd") + 1])
output = pathlib.Path(f"/proc/self/fd/{{output_fd}}")
child = os.fork()
if child == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    devnull = os.open("/dev/null", os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)
    heartbeat = output / "detached-heartbeat"
    while True:
        heartbeat.write_text(str(time.time_ns()))
        time.sleep(0.02)
time.sleep(60)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    with pytest.raises(RuntimeError, match="timed out"):
        runner.run_cell(plan_path, 0, executable, timeout=1)

    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    heartbeat = cell_root / "adapter-output" / "detached-heartbeat"
    before = heartbeat.read_bytes()
    time.sleep(0.15)
    assert heartbeat.read_bytes() == before
    timeout_log = next(
        json.loads(path.read_text())
        for path in (cell_root / "logs").glob("*.json")
        if json.loads(path.read_text())["timed_out"]
    )
    assert timeout_log["process_group_terminated"] is True
    assert not _has_completed_evidence(cell_root)


def test_adapter_output_stays_anchored_when_lexical_cell_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)
    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    displaced = tmp_path / "retained-cell"
    outside = tmp_path / "outside"
    outside.mkdir()
    fired = False

    def hook(event, details):
        nonlocal fired
        if event == "before_adapter_launch":
            fired = True
            cell_root.rename(displaced)
            cell_root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="cell root.*identity"):
        runner.run_cell(
            plan_path, 0, executable, timeout=5, race_hook=hook
        )

    assert fired
    assert list(outside.iterdir()) == []
    assert (displaced / "adapter-output" / "current-generation.json").is_file()
    assert not _has_completed_evidence(displaced)


def test_runner_native_fd_contract_with_real_qmc_sse_survives_hierarchy_replacement(
    tmp_path: Path,
):
    from test_primary_qmc_sse_adapter import (
        EXECUTABLE,
        MANIFEST,
        cargo_executable,
        make_request,
        rust_environment,
    )

    runner = _load_runner()
    built = subprocess.run(
        [cargo_executable(), "build", "--locked", "--manifest-path", str(MANIFEST)],
        check=False,
        capture_output=True,
        env=rust_environment(),
        text=True,
        timeout=180,
    )
    assert built.returncode == 0, built.stderr
    build_info = json.loads(
        subprocess.run(
            [str(EXECUTABLE), "--build-info"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    )
    request_path, request = make_request(tmp_path / "input", build_info)
    graph = json.loads(Path(request["graph_path"]).read_text())
    lexical_cell = tmp_path / "cell"
    output = lexical_cell / "adapter-output"
    logs = lexical_cell / "logs"
    output.mkdir(parents=True)
    logs.mkdir()
    request_fd = os.open(request_path, os.O_RDONLY | os.O_NOFOLLOW)
    output_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    logs_fd = os.open(logs, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    executable_fd, executable_sha256 = runner._open_executable(EXECUTABLE)
    displaced = tmp_path / "displaced-cell"
    lexical_cell.rename(displaced)
    replacement = lexical_cell / "adapter-output"
    replacement.mkdir(parents=True)
    try:
        runner._run_process(
            executable_fd,
            EXECUTABLE,
            [
                "--request-fd",
                str(request_fd),
                "--output-directory-fd",
                str(output_fd),
            ],
            phase="real-adapter-fd-integration",
            timeout=30,
            cwd=tmp_path / "input",
            logs=logs_fd,
            executable_sha256=executable_sha256,
            extra_pass_fds=(request_fd, output_fd),
        )
        validation = runner.validate_qmc_adapter_output_descriptor(
            output_fd,
            request,
            "QMC_SSE",
            graph=graph,
            output_namespace=runner._output_fd_namespace(output_fd),
        )
    finally:
        for descriptor in (executable_fd, logs_fd, output_fd, request_fd):
            os.close(descriptor)

    assert validation["records"]
    assert (displaced / "adapter-output" / "current-generation.json").is_file()
    assert list(replacement.iterdir()) == []


def test_spawn_failure_publishes_immutable_failure_evidence(tmp_path: Path):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    executable.write_bytes(b"not an executable format\n")
    executable.chmod(0o755)

    with pytest.raises(RuntimeError, match="spawn"):
        runner.run_cell(plan_path, 0, executable, timeout=5)

    cell_root = tmp_path / "cells" / plan["cells"][0]["cell_id"]
    evidence = [
        json.loads(path.read_text())
        for path in (cell_root / "logs").glob("*.json")
    ]
    assert len(evidence) == 1
    assert evidence[0]["phase"] == "build-info"
    assert evidence[0]["spawn_error"]
    assert not _has_completed_evidence(cell_root)


def test_executable_replacement_uses_and_binds_retained_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    original = executable.read_bytes()
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)
    fired = False

    def hook(event, details):
        nonlocal fired
        if event == "after_executable_open":
            fired = True
            replacement = executable.with_suffix(".replacement")
            replacement.write_text("#!/bin/sh\nexit 91\n")
            replacement.chmod(0o755)
            os.replace(replacement, executable)

    result = runner.run_cell(
        plan_path, 0, executable, timeout=5, race_hook=hook
    )

    assert fired
    completion = json.loads(_completion_path(result).read_text())
    assert completion["executable_sha256"] == hashlib.sha256(original).hexdigest()
    logs = [
        json.loads(path.read_text()) for path in (result / "logs").glob("*.json")
    ]
    assert {item["executable_sha256"] for item in logs} == {
        hashlib.sha256(original).hexdigest()
    }


def test_executable_in_place_mutation_cannot_change_sealed_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runner = _load_runner()
    plan_path, _ = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable)
    original = executable.read_bytes()
    calls: list[tuple[Path, dict, str, Path]] = []
    _patch_validator(monkeypatch, runner, calls)
    fired = False

    def hook(event, details):
        nonlocal fired
        if event == "after_executable_open":
            fired = True
            executable.write_text("#!/bin/sh\nexit 92\n")
            executable.chmod(0o755)

    result = runner.run_cell(
        plan_path, 0, executable, timeout=5, race_hook=hook
    )

    assert fired
    completion = json.loads(_completion_path(result).read_text())
    assert completion["executable_sha256"] == hashlib.sha256(original).hexdigest()
    assert (result / "adapter-output" / "launch-count").read_text() == "1"
