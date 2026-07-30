from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def canonical_json(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value is not canonical JSON encodable") from exc
    return encoded.encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_non_finite_json(token: str) -> None:
    raise ValueError(f"source integrity mismatch: non-finite JSON token {token}")


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_non_finite_json,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("source integrity mismatch: invalid manifest JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("source integrity mismatch: manifest must be a JSON object")
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("source integrity mismatch: manifest.sources must be a non-empty object")
    return manifest


def _require_string(source: dict[str, Any], key: str, *, name: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"source integrity mismatch: {name} missing {key}")
    return value


def _resolve_candidate_path(external_root: Path, local_relative_path: str) -> Path:
    relative_path = Path(local_relative_path)
    if relative_path.is_absolute():
        raise ValueError("source integrity mismatch: local_relative_path must stay inside cache root")

    resolved_root = external_root.resolve()
    candidate_path = (resolved_root / relative_path).resolve()
    try:
        candidate_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            "source integrity mismatch: local_relative_path must stay inside cache root"
        ) from exc
    return candidate_path


def _git_stdout(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("source integrity mismatch: git command failed")
    return result.stdout.strip()


def _verify_repository_revision(path: Path) -> str:
    git_dir = path / ".git"
    if not git_dir.exists():
        raise ValueError("source integrity mismatch: repository root missing .git marker")

    resolved_root = Path(_git_stdout(path, "rev-parse", "--show-toplevel")).resolve()
    if resolved_root != path.resolve():
        raise ValueError("source integrity mismatch: candidate is not the exact git worktree root")

    status = _git_stdout(path, "status", "--short", "--untracked-files=all")
    if status:
        raise ValueError("source integrity mismatch: repository worktree is dirty")

    revision = _git_stdout(path, "rev-parse", "HEAD")
    if not revision:
        raise ValueError("source integrity mismatch: empty repository revision")
    return revision


def verify_source_manifest(path: Path, external_root: Path) -> dict[str, Any]:
    manifest = _load_manifest(path)
    resolved_external_root = external_root.resolve()
    verified_sources: dict[str, dict[str, Any]] = {}

    for source_name, raw_source in manifest["sources"].items():
        if not isinstance(raw_source, dict):
            raise ValueError(f"source integrity mismatch: {source_name} entry must be an object")

        source = dict(raw_source)
        name = _require_string(source, "name", name=source_name)
        if name != source_name:
            raise ValueError(f"source integrity mismatch: {source_name} key/name mismatch")

        _require_string(source, "kind", name=name)
        _require_string(source, "url", name=name)
        _require_string(source, "license", name=name)
        local_relative_path = _require_string(source, "local_relative_path", name=name)
        candidate_path = _resolve_candidate_path(resolved_external_root, local_relative_path)

        has_sha256 = "sha256" in source
        has_revision = "revision" in source
        if has_sha256 == has_revision:
            raise ValueError(
                f"source integrity mismatch: {name} must declare exactly one of sha256 or revision"
            )

        if has_sha256:
            expected_sha256 = _require_string(source, "sha256", name=name)
            if not candidate_path.is_file():
                raise ValueError(f"source integrity mismatch: {name} file is missing")
            actual_sha256 = sha256_file(candidate_path)
            if actual_sha256 != expected_sha256:
                raise ValueError(f"source integrity mismatch: {name} sha256 drifted")
        else:
            expected_revision = _require_string(source, "revision", name=name)
            if not candidate_path.is_dir():
                raise ValueError(f"source integrity mismatch: {name} repository is missing")
            actual_revision = _verify_repository_revision(candidate_path)
            if actual_revision != expected_revision:
                raise ValueError(f"source integrity mismatch: {name} revision drifted")

        verified_sources[source_name] = source

    verified_manifest = dict(manifest)
    verified_manifest["sources"] = verified_sources
    verified_manifest["valid"] = True
    return verified_manifest
