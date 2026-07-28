from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .protocol import ProtocolConfig


@dataclass(frozen=True)
class AuditResult:
    valid: bool
    issues: tuple[str, ...]
    manifest_sha256: str
    artifact_bytes: int = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def imported_modules(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def freeze_manifest(
    *,
    run_dir: Path,
    project_root: Path,
    route: str,
    attempt: str,
    protocol: ProtocolConfig,
    selected_update: int,
    training_seed: int,
    source_files: list[Path],
    artifact_files: dict[str, Path],
) -> Path:
    run_dir = Path(run_dir).resolve()
    project_root = Path(project_root).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    expected_roles = {"checkpoint", "optimizer_state", "training_log"}
    if set(artifact_files) != expected_roles:
        raise ValueError("artifact roles must be checkpoint, optimizer_state, training_log")

    sources = []
    for source_file in source_files:
        source_path = Path(source_file).resolve()
        sources.append(
            {
                "path": source_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(source_path),
            }
        )

    artifacts = []
    for role, artifact_file in artifact_files.items():
        artifact_path = Path(artifact_file).resolve()
        artifacts.append(
            {
                "role": role,
                "path": artifact_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(artifact_path),
            }
        )

    payload = {
        "schema_version": "challenge-15-frozen-manifest-v1",
        "route": route,
        "attempt": attempt,
        "protocol_sha256": protocol.sha256,
        "training_seed": training_seed,
        "selected_capacity": dict(protocol.capacity["routes"][route]),
        "selected_update": selected_update,
        "checkpoint_policy": "final_update",
        "human_blind": False,
        "oracle_accesses": [],
        "source_files": sources,
        "artifacts": artifacts,
    }
    manifest_path = run_dir / "training-manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def verify_manifest(
    manifest_path: Path,
    *,
    project_root: Path,
    protocol: ProtocolConfig,
    expected_training_seed: int | None = None,
) -> AuditResult:
    manifest_path = Path(manifest_path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues: list[str] = []

    if payload.get("schema_version") != "challenge-15-frozen-manifest-v1":
        issues.append("manifest schema mismatch")
    if payload.get("protocol_sha256") != protocol.sha256:
        issues.append("protocol hash mismatch")

    route = payload.get("route")
    routes = protocol.capacity["routes"]
    if route not in routes:
        issues.append("route not frozen by protocol")
    elif payload.get("selected_capacity") != dict(routes[route]):
        issues.append("selected capacity mismatch")

    if payload.get("selected_update") != protocol.training["optimizer_updates"]:
        issues.append("selected update mismatch")
    training_seed = payload.get("training_seed")
    if training_seed not in protocol.training["seeds"]:
        issues.append("training seed not frozen by protocol")
    if expected_training_seed is not None and training_seed != expected_training_seed:
        issues.append("training seed mismatch")
    if payload.get("checkpoint_policy") != "final_update":
        issues.append("checkpoint policy mismatch")
    if payload.get("human_blind") is not False:
        issues.append("human_blind must be false")
    if payload.get("oracle_accesses") != []:
        issues.append("oracle accesses must be empty")

    source_items = payload.get("source_files", [])
    if not source_items:
        issues.append("source files must be nonempty")
    forbidden_prefixes = protocol.oracle["forbidden_module_prefixes"]
    forbidden_fragments = protocol.oracle["forbidden_path_fragments"]
    root = Path(project_root).resolve()
    for item in source_items:
        source_path = (root / item["path"]).resolve()
        if (
            root not in source_path.parents
            or not source_path.is_file()
            or sha256_file(source_path) != item.get("sha256")
        ):
            issues.append(f"source hash mismatch or path escape: {source_path}")
            continue
        source = source_path.read_text(encoding="utf-8")
        for module in sorted(imported_modules(source)):
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden_prefixes
            ):
                issues.append(f"forbidden candidate import: {module}")
        for prefix in forbidden_prefixes:
            if prefix in source and not any(prefix in issue for issue in issues):
                issues.append(f"forbidden candidate module reference: {prefix}")
        for fragment in forbidden_fragments:
            if fragment in source:
                issues.append(f"forbidden oracle path fragment: {fragment}")

    artifact_items = payload.get("artifacts", [])
    artifact_roles = [item.get("role") for item in artifact_items]
    expected_roles = {"checkpoint", "optimizer_state", "training_log"}
    if set(artifact_roles) != expected_roles or len(artifact_roles) != len(expected_roles):
        issues.append("artifact roles mismatch")
    artifact_bytes = 0
    run_root = manifest_path.parent.resolve()
    for item in artifact_items:
        role = item.get("role")
        artifact_path = (run_root / item["path"]).resolve()
        if (
            run_root not in artifact_path.parents
            or not artifact_path.is_file()
            or sha256_file(artifact_path) != item.get("sha256")
        ):
            issues.append(
                f"artifact hash mismatch or path escape ({role}): {artifact_path}"
            )
            continue
        artifact_bytes += artifact_path.stat().st_size

    return AuditResult(
        valid=not issues,
        issues=tuple(issues),
        manifest_sha256=sha256_file(manifest_path),
        artifact_bytes=artifact_bytes,
    )
