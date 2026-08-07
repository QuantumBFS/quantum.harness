from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from challenge148 import provenance


PDF_SOURCES = {
    "blote-deng-2002": {
        "kind": "paper",
        "url": "https://doi.org/10.1103/PhysRevE.66.066110",
        "license": "publisher PDF (license not stated in cached file)",
        "local_relative_path": "papers/blote-deng-2002-ustc.pdf",
        "sha256": "aae5ff7690b1d6f0922254c492fa78fce3854c7e7cfc029d9571f1a00a73cd17",
    },
    "sandvik-2003-sse": {
        "kind": "paper",
        "url": "https://doi.org/10.1103/PhysRevE.68.056701",
        "license": "publisher PDF (license not stated in cached file)",
        "local_relative_path": "papers/sandvik-2003-sse.pdf",
        "sha256": "e6e2efcccaa4e5ba68024c4e68ac9d01909e5d23c079d2aae1da616d2f944dab",
    },
    "rieger-kawashima-1999": {
        "kind": "paper",
        "url": "https://doi.org/10.1007/s100510050761",
        "license": "publisher PDF (license not stated in cached file)",
        "local_relative_path": "papers/rieger-kawashima-1999.pdf",
        "sha256": "5f554ed84b9ffded1bd0910a5691ea5d7f14085a8066c9f4a67d95f4351dec5d",
    },
    "carlo-jl-codebase": {
        "kind": "paper",
        "url": "https://doi.org/10.21468/SciPostPhysCodeb.49",
        "license": "CC-BY 4.0",
        "local_relative_path": "papers/carlo-jl-codebase.pdf",
        "sha256": "ba9015cc4cecf34edd60071e09ebf0c4adc4ce76a8e07c9ebc9f9fc88363bf6a",
    },
}

REPOSITORY_SOURCES = {
    "StochasticSeriesExpansion.jl": {
        "kind": "repository",
        "url": "https://github.com/lukas-weber/StochasticSeriesExpansion.jl.git",
        "license": "MIT",
        "local_relative_path": "code/StochasticSeriesExpansion.jl",
        "revision": "0ee4bb3e78ad90306d594978e0ad405edebe8961",
    },
    "Carlo.jl": {
        "kind": "repository",
        "url": "https://github.com/lukas-weber/Carlo.jl.git",
        "license": "MIT",
        "local_relative_path": "code/Carlo.jl",
        "revision": "4ce0a96650163ded76cab716ab28051813fd27a2",
    },
    "QMC_SSE": {
        "kind": "repository",
        "url": "https://github.com/Renmusxd/QMC_SSE.git",
        "license": "GPL-3.0-only",
        "local_relative_path": "code/QMC_SSE",
        "revision": "35f100af856f3273cc67d31962f3e67f801b0c37",
    },
    "QMC_LTFIM": {
        "kind": "repository",
        "url": "https://github.com/PIQuIL/QMC_LTFIM.git",
        "license": "Apache-2.0",
        "local_relative_path": "code/QMC_LTFIM",
        "revision": "524860b9c0e212ac630b0d9754075bb24198da3b",
    },
}


def workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".external" / "challenge-148").exists():
            return candidate
    pytest.skip(
        "source provenance integration requires the ignored "
        ".external/challenge-148 cache"
    )


def fixture_external_source_root() -> Path:
    return workspace_root() / ".external" / "challenge-148"


def seed_external_fixture(tmp_path: Path) -> Path:
    external_root = tmp_path / ".external" / "challenge-148"
    papers_root = external_root / "papers"
    code_root = external_root / "code"
    papers_root.mkdir(parents=True)
    code_root.mkdir(parents=True)

    source_root = fixture_external_source_root()
    for source in PDF_SOURCES.values():
        source_path = source_root / source["local_relative_path"]
        target_path = external_root / source["local_relative_path"]
        shutil.copy2(source_path, target_path)

    for source in REPOSITORY_SOURCES.values():
        repo_source = source_root / source["local_relative_path"]
        repo_target = external_root / source["local_relative_path"]
        subprocess.run(
            ["git", "clone", "--quiet", str(repo_source), str(repo_target)],
            check=True,
        )

    return external_root


def manifest_payload() -> dict[str, object]:
    sources: dict[str, dict[str, str]] = {}
    for name, entry in PDF_SOURCES.items():
        sources[name] = {"name": name, **entry}
    for name, entry in REPOSITORY_SOURCES.items():
        sources[name] = {"name": name, **entry}
    return {"challenge": "148", "sources": sources}


def write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_fixture_manifest(tmp_path: Path) -> Path:
    seed_external_fixture(tmp_path)
    manifest_path = tmp_path / "SOURCES.json"
    write_manifest(manifest_path, manifest_payload())
    return manifest_path


def test_canonical_json_is_sorted_utf8_and_rejects_non_finite_numbers():
    encoded = provenance.canonical_json({"beta": "b", "alpha": "mu", "zeta": [3, 2, 1]})
    assert encoded == b'{"alpha":"mu","beta":"b","zeta":[3,2,1]}'

    with pytest.raises(ValueError):
        provenance.canonical_json({"nan": math.nan})


def test_sha256_file_matches_fixture_hash(tmp_path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"challenge-148")
    assert provenance.sha256_file(path) == (
        "7c5fc9f711f9818b52bdd831917397f339dd2e8cfa877c8e5a66eb4374d15638"
    )


def test_source_manifest_binds_pdf_hashes_and_repository_revisions(tmp_path):
    manifest = load_fixture_manifest(tmp_path)
    verified = provenance.verify_source_manifest(
        manifest, tmp_path / ".external" / "challenge-148"
    )
    assert verified["valid"] is True
    assert verified["sources"]["QMC_SSE"]["revision"] == (
        "35f100af856f3273cc67d31962f3e67f801b0c37"
    )


def test_source_manifest_rejects_hash_or_revision_drift(tmp_path):
    manifest = load_fixture_manifest(tmp_path)
    (tmp_path / ".external/challenge-148/papers/blote-deng-2002-ustc.pdf").write_bytes(
        b"drift"
    )
    with pytest.raises(ValueError, match="source integrity mismatch"):
        provenance.verify_source_manifest(manifest, tmp_path / ".external/challenge-148")


def test_source_manifest_rejects_repository_subdirectory_even_if_git_would_walk_up(tmp_path):
    manifest = load_fixture_manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["sources"]["QMC_SSE"]["local_relative_path"] = "code/QMC_SSE/src"
    write_manifest(manifest, payload)

    with pytest.raises(ValueError, match="source integrity mismatch"):
        provenance.verify_source_manifest(manifest, tmp_path / ".external/challenge-148")


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_source_manifest_rejects_non_finite_manifest_json(tmp_path, token):
    seed_external_fixture(tmp_path)
    manifest = tmp_path / "SOURCES.json"
    sources = json.dumps(manifest_payload()["sources"], sort_keys=True)
    manifest.write_text(
        f'{{"challenge":"148","marker":{token},"sources":{sources}}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source integrity mismatch"):
        provenance.verify_source_manifest(manifest, tmp_path / ".external/challenge-148")


@pytest.mark.parametrize("dirty_kind", ["modified", "untracked"])
def test_source_manifest_rejects_dirty_repository_worktrees(tmp_path, dirty_kind):
    manifest = load_fixture_manifest(tmp_path)
    repo = tmp_path / ".external" / "challenge-148" / "code" / "QMC_SSE"

    if dirty_kind == "modified":
        readme = repo / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nlocal drift\n", encoding="utf-8")
    else:
        (repo / "UNTRACKED.txt").write_text("drift\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source integrity mismatch"):
        provenance.verify_source_manifest(manifest, tmp_path / ".external/challenge-148")


@pytest.mark.parametrize(
    ("bad_path", "outside_builder"),
    [
        (
            "ABSOLUTE_PLACEHOLDER",
            lambda tmp_path, original: tmp_path / "absolute-escape" / original.name,
        ),
        (
            "../outside-cache/copied-reference.pdf",
            lambda tmp_path, original: tmp_path / "outside-cache" / "copied-reference.pdf",
        ),
        (
            "papers/../../outside-cache/nested-reference.pdf",
            lambda tmp_path, original: tmp_path / "outside-cache" / "nested-reference.pdf",
        ),
    ],
)
def test_source_manifest_rejects_paths_outside_cache_root(tmp_path, bad_path, outside_builder):
    manifest = load_fixture_manifest(tmp_path)
    original = tmp_path / ".external" / "challenge-148" / "papers" / "blote-deng-2002-ustc.pdf"
    outside_target = outside_builder(tmp_path, original)
    outside_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, outside_target)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if bad_path == "ABSOLUTE_PLACEHOLDER":
        payload["sources"]["blote-deng-2002"]["local_relative_path"] = str(outside_target)
    else:
        payload["sources"]["blote-deng-2002"]["local_relative_path"] = bad_path
    write_manifest(manifest, payload)

    with pytest.raises(ValueError, match="source integrity mismatch"):
        provenance.verify_source_manifest(manifest, tmp_path / ".external/challenge-148")
