#!/usr/bin/env python3
"""Download and verify papers and pinned code for challenge #81."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import urllib.request


DEFAULT_MANIFEST = Path(__file__).with_name("references.json")
DEFAULT_OUTPUT = Path("tracks/mps/results/frustration-free/references")
USER_AGENT = "quantum-harness/challenge-81-references"


def load_manifest(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError("reference manifest must use schema_version=1")
    return manifest


def _safe_name(value: str) -> str:
    if not value or Path(value).name != value or value in {".", ".."}:
        raise ValueError(f"unsafe reference name: {value!r}")
    return value


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_paper(path: str | Path, entry: dict[str, Any]) -> bool:
    path = Path(path)
    return (
        path.is_file()
        and path.stat().st_size == entry["size"]
        and sha256_file(path) == entry["sha256"]
    )


def _repository_head(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def verify_repository(path: str | Path, entry: dict[str, Any]) -> bool:
    path = Path(path)
    if _repository_head(path) != entry["commit"]:
        return False
    status = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    return status.returncode == 0 and not status.stdout


def _unused_path(parent: Path, prefix: str) -> Path:
    descriptor, name = tempfile.mkstemp(dir=parent, prefix=prefix)
    os.close(descriptor)
    os.unlink(name)
    return Path(name)


def download_paper(entry: dict[str, Any], output_dir: Path) -> Path:
    name = _safe_name(entry["name"])
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / name
    if verify_paper(destination, entry):
        print(f"verified paper {name}")
        return destination

    partial = _unused_path(output_dir, f".{name}.stage-")
    archived = None
    request = urllib.request.Request(entry["url"], headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            with open(partial, "wb") as handle:
                shutil.copyfileobj(response, handle, length=1024 * 1024)
        if not verify_paper(partial, entry):
            raise RuntimeError(f"paper checksum mismatch: {name}")
        if destination.exists() or destination.is_symlink():
            archived = _unused_path(
                output_dir, f".{name}.superseded-"
            )
            os.replace(destination, archived)
        try:
            os.replace(partial, destination)
        except BaseException:
            if archived is not None and archived.exists():
                os.replace(archived, destination)
            raise
    finally:
        partial.unlink(missing_ok=True)
    print(f"downloaded paper {name}")
    return destination


def sync_repository(entry: dict[str, Any], output_dir: Path) -> Path:
    name = _safe_name(entry["name"])
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / name
    if verify_repository(destination, entry):
        print(f"verified repository {name}@{entry['commit']}")
        return destination

    partial = _unused_path(output_dir, f".{name}.stage-")
    archived = None
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--no-checkout", entry["url"], str(partial)],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(partial),
                "checkout",
                "--quiet",
                "--detach",
                entry["commit"],
            ],
            check=True,
        )
        if not verify_repository(partial, entry):
            raise RuntimeError(f"repository revision mismatch: {name}")
        if destination.exists() or destination.is_symlink():
            archived = _unused_path(
                output_dir, f".{name}.superseded-"
            )
            os.replace(destination, archived)
        try:
            os.replace(partial, destination)
        except BaseException:
            if archived is not None and archived.exists():
                os.replace(archived, destination)
            raise
    finally:
        if partial.exists():
            shutil.rmtree(partial)
    print(f"downloaded repository {name}@{entry['commit']}")
    return destination


def verify_manifest(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    output_dir: str | Path = DEFAULT_OUTPUT,
) -> list[str]:
    manifest = load_manifest(manifest_path)
    output_dir = Path(output_dir)
    failures = [
        f"paper:{entry['name']}"
        for entry in manifest["papers"]
        if not verify_paper(
            output_dir / "papers" / _safe_name(entry["name"]),
            entry,
        )
    ]
    failures.extend(
        f"repository:{entry['name']}"
        for entry in manifest["repositories"]
        if not verify_repository(
            output_dir / "code" / _safe_name(entry["name"]),
            entry,
        )
    )
    return failures


def sync_references(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    output_dir: str | Path = DEFAULT_OUTPUT,
) -> list[Path]:
    manifest = load_manifest(manifest_path)
    output_dir = Path(output_dir)
    papers = [
        download_paper(entry, output_dir / "papers")
        for entry in manifest["papers"]
    ]
    repositories = [
        sync_repository(entry, output_dir / "code")
        for entry in manifest["repositories"]
    ]
    return papers + repositories


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify_only:
        failures = verify_manifest(args.manifest, args.output_dir)
        if failures:
            print("invalid or missing: " + ", ".join(failures))
            return 1
        print("all challenge #81 references verified")
        return 0
    sync_references(args.manifest, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
