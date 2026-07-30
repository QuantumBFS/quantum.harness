#!/usr/bin/env python3
"""Fail-closed verification of the task-05 public release contract."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SCRIPT_ROOT.parents[2]
DEFAULT_MANIFEST = SCRIPT_ROOT / "output" / "release_manifest_v1.json"
REGISTERED_BRANCHES = {
    "matrix_element": "deformed_geometric_eth",
    "topology": "fixed_chern_deformed_holonomy",
}
FORBIDDEN_IMPORTS = {"task_03", "task_04", "qgeom", "gaccess"}
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record_matches(record: dict[str, Any], repo_root: Path) -> bool:
    path = repo_root / record.get("path", "")
    return (
        path.is_file()
        and path.stat().st_size == record.get("size_bytes")
        and _sha256(path) == record.get("sha256")
    )


def _tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [
        repo_root / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _task_isolated(repo_root: Path) -> bool:
    source = repo_root / "01_task_folder" / "task_05" / "script"
    for path in source.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in FORBIDDEN_IMPORTS:
                        return False
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".", 1)[0] in FORBIDDEN_IMPORTS:
                    return False
    return True


def _local_links_valid(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#")):
            continue
        local = target.split("#", 1)[0]
        if local and not (path.parent / local).resolve().exists():
            return False
    return True


def _citation_valid(repo_root: Path) -> bool:
    path = repo_root / "CITATION.cff"
    if not path.is_file():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return (
        data.get("cff-version") == "1.2.0"
        and data.get("title")
        == (
            "Spectral Silence and Geometric Chaos in an Exactly "
            "Degenerate Topological Manifold"
        )
        and data.get("license") == "GPL-3.0-only"
        and len(data.get("authors", [])) == 2
    )


def verify_manifest(path: Path, *, repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    tracked = _tracked_files(repo_root)
    release_tracked = [
        item
        for item in tracked
        if item.relative_to(repo_root).as_posix().startswith(
            (
                "01_task_folder/task_05/",
                "overleaf_sync/geometric_eth_large_scale/",
            )
        )
    ]
    max_bytes = int(
        os.environ.get("TASK05_RELEASE_MAX_TRACKED_BYTES", 10 * 1024 * 1024)
    )
    figures = manifest.get("figures", [])
    compact = manifest.get("compact_artifacts", [])
    external = manifest.get("external_artifacts", [])

    checks = {
        "schema_version": manifest.get("schema_version") == 1,
        "release_id": (
            manifest.get("release_id") == "task05-geometric-chaos-v1"
        ),
        "registered_result_branches": (
            manifest.get("result_branches") == REGISTERED_BRANCHES
        ),
        "paper_record": (
            manifest.get("paper", {}).get("page_count") == 17
            and _record_matches(manifest.get("paper", {}), repo_root)
        ),
        "seven_figures": (
            len(figures) == 7
            and all(_record_matches(item, repo_root) for item in figures)
        ),
        "compact_artifacts": (
            bool(compact)
            and all(_record_matches(item, repo_root) for item in compact)
        ),
        "external_records": (
            len(external) == 25
            and all(
                item.get("storage_class") == "recompute_or_release_asset"
                and isinstance(item.get("size_bytes"), int)
                and item["size_bytes"] > 0
                and len(item.get("sha256", "")) == 64
                and bool(item.get("producer"))
                for item in external
            )
        ),
        "verification_commands": (
            manifest.get("verification", {}).get("quick")
            == "bash run_quick_verify_v1.sh"
            and manifest.get("verification", {}).get("full")
            == "bash run_full_recompute_v1.sh"
        ),
        "tracked_blob_limit": all(
            not item.is_file() or item.stat().st_size <= max_bytes
            for item in release_tracked
        ),
        "no_tracked_caches": all(
            not CACHE_PARTS.intersection(item.parts) for item in tracked
        ),
        "task_runtime_isolated": _task_isolated(repo_root),
        "public_readmes": (
            _local_links_valid(repo_root / "README.md")
            and _local_links_valid(
                repo_root / "01_task_folder" / "task_05" / "README.md"
            )
        ),
        "citation_metadata": _citation_valid(repo_root),
        "release_notes": (
            repo_root / "docs" / "2026-07-30-task05-release-notes.md"
        ).is_file(),
        "technical_report": (
            repo_root / "docs" / "2026-07-30-task05-technical-report.md"
        ).is_file(),
        "pr_handoff": all(
            (
                repo_root / "docs" / name
            ).is_file()
            for name in (
                "2026-07-30-task05-pr-body.md",
                "2026-07-30-task05-pr-review-comment.md",
                "2026-07-30-task05-public-release-checklist.md",
            )
        ),
        "challenge_handoff": (
            repo_root
            / "docs"
            / "2026-07-30-quantum-geometry-harness-challenge-draft.md"
        ).is_file(),
    }
    return {"passed": all(checks.values()), "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "manifest", type=Path, nargs="?", default=DEFAULT_MANIFEST
    )
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    args = parser.parse_args()

    report = verify_manifest(args.manifest, repo_root=args.repo_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
