from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

import jsonschema

from .provenance import canonical_json, sha256_file


def _reject_non_finite_json(token: str) -> None:
    raise ValueError(f"non-finite JSON token {token}")


def _completion_schema_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "schemas" / "completion.schema.json"


def _load_completion_schema() -> dict[str, object]:
    path = _completion_schema_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_directory(path: Path) -> None:
    if path.exists():
        path_stat = os.lstat(path)
        if stat.S_ISLNK(path_stat.st_mode):
            raise ValueError(f"expected real directory at {path}")
        if not stat.S_ISDIR(path_stat.st_mode):
            raise ValueError(f"expected directory at {path}")
        return
    path.mkdir(parents=True, exist_ok=True)
    _fsync_directory(path.parent)
    _fsync_directory(path)


def _json_text(value: object) -> str:
    canonical_json(value)
    return json.dumps(value, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _lstat_path(path: Path) -> os.stat_result:
    return os.lstat(path)


def _require_real_directory(path: Path, *, label: str) -> None:
    path_stat = _lstat_path(path)
    if stat.S_ISLNK(path_stat.st_mode):
        raise ValueError(f"{label} must not be a symlink")
    if not stat.S_ISDIR(path_stat.st_mode):
        raise ValueError(f"{label} must be a directory")


def _require_regular_file(path: Path, *, label: str) -> None:
    path_stat = _lstat_path(path)
    if stat.S_ISLNK(path_stat.st_mode):
        raise ValueError(f"{label} must not be a symlink")
    if not stat.S_ISREG(path_stat.st_mode):
        raise ValueError(f"{label} must be a regular file")


def _fsync_regular_file(path: Path) -> None:
    _require_regular_file(path, label=str(path))
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    _ensure_directory(path.parent)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temp_path = Path(temp_name)
    wrote_temp = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        wrote_temp = True
        os.replace(temp_path, path)
        _fsync_directory(path.parent)
    except Exception:
        if wrote_temp and temp_path.exists():
            temp_path.unlink()
            _fsync_directory(path.parent)
        raise


def atomic_write_json(path: Path, value: object) -> str:
    _atomic_write_bytes(path, _json_text(value).encode("utf-8"))
    return sha256_file(path)


def _run_spec_sha256(run_spec: dict[str, object]) -> str:
    if not isinstance(run_spec, dict):
        raise ValueError("run_spec must be a JSON object")
    return hashlib.sha256(canonical_json(run_spec)).hexdigest()


def _resolve_relative_path(root: Path, relative_path: str, *, context: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError(f"{context} must stay inside run directory")
    resolved_root = root.resolve()
    resolved_candidate = (resolved_root / candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{context} must stay inside run directory") from exc
    return resolved_candidate


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    _require_regular_file(path, label=label)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_non_finite_json,
        )
    except ValueError as exc:
        if str(exc).startswith("non-finite JSON token"):
            raise ValueError(str(exc)) from exc
        raise ValueError(f"invalid {label} JSON") from exc
    except OSError as exc:
        raise ValueError(f"invalid {label} JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _walk_run_regular_files(root: Path) -> dict[str, Path]:
    _require_real_directory(root, label="run directory")

    discovered: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        dirnames.sort()
        filenames.sort()

        for name in tuple(dirnames):
            candidate = directory_path / name
            entry_stat = os.lstat(candidate)
            if stat.S_ISLNK(entry_stat.st_mode):
                raise ValueError("run directory contains a symlink")
            if not stat.S_ISDIR(entry_stat.st_mode):
                raise ValueError("run directory contains a non-directory entry")

        for name in filenames:
            candidate = directory_path / name
            entry_stat = os.lstat(candidate)
            if stat.S_ISLNK(entry_stat.st_mode):
                raise ValueError("run directory contains a symlink")
            if not stat.S_ISREG(entry_stat.st_mode):
                raise ValueError("run directory contains a non-regular file")
            relative = candidate.relative_to(root).as_posix()
            discovered[relative] = candidate
    return discovered


def _collect_stage_entries(stage_path: Path) -> tuple[list[Path], list[Path]]:
    _require_real_directory(stage_path, label="stage directory")

    files: list[Path] = []
    directories: list[Path] = []

    def visit(directory: Path) -> None:
        _require_real_directory(directory, label="stage directory")
        child_directories: list[Path] = []
        child_files: list[Path] = []
        for child in sorted(directory.iterdir(), key=lambda path: path.name):
            child_stat = _lstat_path(child)
            if stat.S_ISLNK(child_stat.st_mode):
                raise ValueError("stage directory contains a symlink")
            if stat.S_ISDIR(child_stat.st_mode):
                child_directories.append(child)
                continue
            if not stat.S_ISREG(child_stat.st_mode):
                raise ValueError("stage directory contains a non-regular file")
            child_files.append(child)

        for child in child_files:
            files.append(child)
        for child in child_directories:
            visit(child)
        directories.append(directory)

    visit(stage_path)
    return files, directories


def _durability_sync_stage(stage_path: Path) -> None:
    files, directories = _collect_stage_entries(stage_path)
    for file_path in files:
        _fsync_regular_file(file_path)
    for directory_path in directories:
        _fsync_directory(directory_path)


def _validate_artifact_table(
    run_directory: Path,
    artifacts: object,
) -> dict[str, dict[str, Any]]:
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("completion manifest artifacts must be a non-empty object")

    validated: dict[str, dict[str, Any]] = {}
    for relative_path, entry in artifacts.items():
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("completion manifest artifact path must be a non-empty string")
        if relative_path == "completion.json":
            raise ValueError("completion manifest must not self-list completion.json")
        _resolve_relative_path(run_directory, relative_path, context="artifact path")

        if not isinstance(entry, dict):
            raise ValueError("completion manifest artifact entry must be an object")
        sha256_value = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(sha256_value, str) or len(sha256_value) != 64:
            raise ValueError("completion manifest artifact entry missing sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("completion manifest artifact entry missing size")
        validated[relative_path] = {"sha256": sha256_value, "size": size}
    return validated


def validate_run(run_directory: Path, *, expected_spec_sha256: str) -> dict:
    if not isinstance(expected_spec_sha256, str) or len(expected_spec_sha256) != 64:
        raise ValueError("stale spec hash")

    run_directory = Path(run_directory)
    completion_path = run_directory / "completion.json"
    completion = _load_json_object(completion_path, label="completion manifest")
    schema = _load_completion_schema()
    try:
        jsonschema.validate(completion, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError("malformed completion manifest") from exc

    run_id = completion.get("run_id")
    manifest_spec_sha256 = completion.get("run_spec_sha256")
    if run_id != expected_spec_sha256 or manifest_spec_sha256 != expected_spec_sha256:
        raise ValueError("stale spec hash")

    artifacts = _validate_artifact_table(run_directory, completion.get("artifacts"))
    discovered = _walk_run_regular_files(run_directory)

    expected_paths = set(artifacts)
    actual_paths = set(discovered)
    actual_payload_paths = actual_paths - {"completion.json"}
    unexpected = sorted(actual_payload_paths - expected_paths)
    missing = sorted(expected_paths - actual_payload_paths)
    if unexpected:
        raise ValueError(f"unexpected run files: {', '.join(unexpected)}")
    if missing:
        raise ValueError(f"completion manifest missing files: {', '.join(missing)}")

    run_spec_path = run_directory / "run_spec.json"
    run_spec_payload = _load_json_object(run_spec_path, label="run_spec")
    actual_spec_sha256 = hashlib.sha256(canonical_json(run_spec_payload)).hexdigest()
    if actual_spec_sha256 != expected_spec_sha256:
        raise ValueError("stale spec hash")

    for relative_path, entry in artifacts.items():
        candidate = discovered.get(relative_path)
        if candidate is None:
            raise ValueError(f"completion manifest missing files: {relative_path}")
        actual_sha256 = sha256_file(candidate)
        if actual_sha256 != entry["sha256"]:
            raise ValueError(f"artifact hash mismatch: {relative_path}")
        if candidate.stat().st_size != entry["size"]:
            raise ValueError(f"artifact size mismatch: {relative_path}")

    return {
        "artifacts": artifacts,
        "run_id": run_id,
        "run_spec_sha256": manifest_spec_sha256,
    }


def _build_completion_manifest(stage_path: Path, *, run_id: str) -> dict[str, object]:
    discovered = _walk_run_regular_files(stage_path)
    if "completion.json" in discovered:
        raise ValueError("producer must not write completion.json")
    if "run_spec.json" not in discovered:
        raise ValueError("run_spec.json missing from stage")

    artifacts: dict[str, dict[str, object]] = {}
    for relative_path, path in sorted(discovered.items()):
        artifacts[relative_path] = {
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
    return {
        "artifacts": artifacts,
        "run_id": run_id,
        "run_spec_sha256": run_id,
    }


def _make_stage_directory(output_root: Path, *, run_id: str) -> Path:
    _ensure_directory(output_root)
    stage_path = Path(tempfile.mkdtemp(prefix=f".{run_id}.stage-", dir=output_root))
    _fsync_directory(output_root)
    return stage_path


def _archive_stage(stage_path: Path, *, output_root: Path, reason: str) -> Path | None:
    if not stage_path.exists():
        return None
    failed_root = output_root / "failed"
    _ensure_directory(failed_root)
    archive_path = failed_root / f"{stage_path.name}.{reason}-{uuid.uuid4().hex}"
    source_parent = stage_path.parent
    os.rename(stage_path, archive_path)
    _fsync_directory(source_parent)
    _fsync_directory(failed_root)
    return archive_path


def publish_run(
    output_root: Path,
    *,
    run_spec: dict,
    producer: Callable[[Path], None],
) -> Path:
    output_root = output_root.resolve()
    run_id = _run_spec_sha256(run_spec)
    runs_root = output_root / "runs"
    _ensure_directory(output_root)
    _ensure_directory(runs_root)

    stage_path = _make_stage_directory(output_root, run_id=run_id)
    stage_active = True
    created_final_run = False
    final_run = runs_root / f"run-{run_id}"
    try:
        atomic_write_json(stage_path / "run_spec.json", run_spec)
        producer(stage_path)
        completion = _build_completion_manifest(stage_path, run_id=run_id)
        atomic_write_json(stage_path / "completion.json", completion)
        _durability_sync_stage(stage_path)
        validate_run(stage_path, expected_spec_sha256=run_id)

        try:
            os.rename(stage_path, final_run)
            _fsync_directory(output_root)
            _fsync_directory(runs_root)
            stage_active = False
            created_final_run = True
        except OSError:
            if not final_run.exists():
                raise
            existing = validate_run(final_run, expected_spec_sha256=run_id)
            candidate = validate_run(stage_path, expected_spec_sha256=run_id)
            if existing != candidate:
                _archive_stage(stage_path, output_root=output_root, reason="conflict")
                stage_active = False
                raise ValueError("immutable run conflict for identical spec")

        current_payload = {
            "path": f"runs/run-{run_id}",
            "run_id": run_id,
            "run_spec_sha256": run_id,
        }
        try:
            atomic_write_json(output_root / "current.json", current_payload)
        except Exception:
            if created_final_run:
                _archive_stage(final_run, output_root=output_root, reason="current-pointer-failed")
                created_final_run = False
            elif stage_active:
                _archive_stage(stage_path, output_root=output_root, reason="current-pointer-failed")
                stage_active = False
            raise

        if stage_active:
            _archive_stage(stage_path, output_root=output_root, reason="identical")
            stage_active = False
        return final_run
    except Exception:
        if stage_active:
            _archive_stage(stage_path, output_root=output_root, reason="failed")
            stage_active = False
        raise
