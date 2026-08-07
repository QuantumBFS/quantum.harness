from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


MODULE_PATH = (
    Path(__file__).parents[1] / "references" / "download_references.py"
)
SPEC = importlib.util.spec_from_file_location("download_references", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
download_references = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(download_references)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_sync_references_downloads_and_verifies_paper_and_pinned_repo(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nchallenge-81\n")

    origin = tmp_path / "origin"
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    (origin / "README.md").write_text("reference code\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(origin), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(origin),
            "-c",
            "user.name=Reference Test",
            "-c",
            "user.email=reference@example.invalid",
            "commit",
            "-q",
            "-m",
            "reference",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    manifest_path = tmp_path / "references.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "papers": [
                    {
                        "name": "paper.pdf",
                        "url": source_pdf.as_uri(),
                        "size": source_pdf.stat().st_size,
                        "sha256": _sha256(source_pdf.read_bytes()),
                    }
                ],
                "repositories": [
                    {
                        "name": "reference-code",
                        "url": str(origin),
                        "commit": commit,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "downloads"
    stale_repo = output_dir / "code" / "reference-code"
    stale_repo.mkdir(parents=True)
    (stale_repo / "USER-NOTE.txt").write_text("preserve me", encoding="utf-8")

    downloaded = download_references.sync_references(manifest_path, output_dir)

    assert downloaded == [
        output_dir / "papers" / "paper.pdf",
        output_dir / "code" / "reference-code",
    ]
    assert download_references.verify_manifest(manifest_path, output_dir) == []
    archived = list((output_dir / "code").glob(".reference-code.superseded-*"))
    assert len(archived) == 1
    assert (archived[0] / "USER-NOTE.txt").read_text(encoding="utf-8") == (
        "preserve me"
    )
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(output_dir / "code" / "reference-code"),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == commit
    )
    (output_dir / "code" / "reference-code" / "UNTRACKED").write_text(
        "dirty", encoding="utf-8"
    )
    assert not download_references.verify_repository(
        output_dir / "code" / "reference-code",
        {"commit": commit},
    )


def test_verify_manifest_reports_corrupt_paper_and_wrong_repo_revision(tmp_path):
    output_dir = tmp_path / "downloads"
    paper_dir = output_dir / "papers"
    repo_dir = output_dir / "code" / "reference-code"
    paper_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    (paper_dir / "paper.pdf").write_bytes(b"corrupt")
    subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)

    manifest_path = tmp_path / "references.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "papers": [
                    {
                        "name": "paper.pdf",
                        "url": "https://example.invalid/paper.pdf",
                        "size": 3,
                        "sha256": _sha256(b"pdf"),
                    }
                ],
                "repositories": [
                    {
                        "name": "reference-code",
                        "url": "https://example.invalid/reference-code.git",
                        "commit": "0" * 40,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert download_references.verify_manifest(manifest_path, output_dir) == [
        "paper:paper.pdf",
        "repository:reference-code",
    ]
