from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


TRIQS_DIR = Path(__file__).resolve().parents[1]
LOCK_PATH = TRIQS_DIR / "conda-linux-64.lock"
ENVIRONMENT_PATH = TRIQS_DIR / "environment.yml"
EXPECTED_ENVIRONMENT_DEPENDENCIES = {
    "python": "3.12",
    "pytest": None,
    "jsonschema": None,
    "mpmath": None,
    "triqs": "4.0.0",
    "triqs_cthyb": "4.0.0",
}
EXPECTED_LOCK_SHA256 = (
    "0ca3767832e4e5dfebbb5c263000d646bd6e1ab0395636458eb21c28457bed2d"
)
EXPECTED_CRITICAL_LOCK_ENTRIES = {
    "python": (
        "https://conda.anaconda.org/conda-forge/linux-64/"
        "python-3.12.13-hd63d673_0_cpython.conda",
        "7eccb41177e15cc672e1babe9056018e",
    ),
    "pytest": (
        "https://conda.anaconda.org/conda-forge/noarch/"
        "pytest-9.1.1-pyhc364b38_2.conda",
        "64c98a12c4e23eb238bf66bbecafdf3c",
    ),
    "jsonschema": (
        "https://conda.anaconda.org/conda-forge/noarch/"
        "jsonschema-4.26.0-pyhcf101f3_0.conda",
        "ada41c863af263cc4c5fcbaff7c3e4dc",
    ),
    "mpmath": (
        "https://conda.anaconda.org/conda-forge/noarch/"
        "mpmath-1.4.1-pyhd8ed1ab_0.conda",
        "2e81b32b805f406d23ba61938a184081",
    ),
    "triqs": (
        "https://conda.anaconda.org/conda-forge/linux-64/"
        "triqs-4.0.0-py312h0f5f726_1.conda",
        "159cce12bffed2f3fa11d220f4a5d90f",
    ),
    "triqs_cthyb": (
        "https://conda.anaconda.org/conda-forge/linux-64/"
        "triqs_cthyb-4.0.0-py312h1ea1904_0.conda",
        "cf923934136a829e76adff575ca7f34d",
    ),
}
REQUIRED_RUNTIME_PACKAGES = set(EXPECTED_ENVIRONMENT_DEPENDENCIES)
MD5_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _environment_dependencies() -> dict[str, str | None]:
    lines = ENVIRONMENT_PATH.read_text(encoding="utf-8").splitlines()
    assert lines[:4] == [
        "name: challenge81-triqs",
        "channels:",
        "  - conda-forge",
        "dependencies:",
    ]
    dependencies: dict[str, str | None] = {}
    for line in lines[4:]:
        match = re.fullmatch(r"  - ([a-z0-9_-]+)(?:=([^\s=]+))?", line)
        assert match, f"unsupported environment dependency: {line!r}"
        name, spec = match.groups()
        assert name not in dependencies
        dependencies[name] = spec
    return dependencies


def _explicit_lock_entries() -> dict[str, str]:
    lines = LOCK_PATH.read_text(encoding="utf-8").splitlines()
    assert "# platform: linux-64" in lines
    assert lines.count("@EXPLICIT") == 1
    entries: dict[str, str] = {}
    for line in lines[lines.index("@EXPLICIT") + 1 :]:
        if not line:
            continue
        url, separator, md5 = line.partition("#")
        assert separator == "#"
        assert MD5_PATTERN.fullmatch(md5)
        parsed = urlsplit(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "conda.anaconda.org"
        path_parts = parsed.path.removeprefix("/").split("/")
        assert path_parts[:2] in (
            ["conda-forge", "linux-64"],
            ["conda-forge", "noarch"],
        )
        assert not parsed.query
        assert url not in entries
        entries[url] = md5
    assert entries
    return entries


def _installed_conda_records() -> list[dict[str, object]]:
    metadata_root = Path(sys.prefix) / "conda-meta"
    assert metadata_root.is_dir()
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(metadata_root.glob("*.json"))
    ]
    assert records
    return records


def test_environment_declares_exact_runtime_dependencies():
    assert _environment_dependencies() == EXPECTED_ENVIRONMENT_DEPENDENCIES


def test_explicit_lock_has_independent_trusted_digests():
    assert sha256(LOCK_PATH.read_bytes()).hexdigest() == EXPECTED_LOCK_SHA256
    lock_entries = _explicit_lock_entries()
    for package, (url, md5) in EXPECTED_CRITICAL_LOCK_ENTRIES.items():
        assert lock_entries.get(url) == md5, package


def test_explicit_lock_matches_active_prefix_exactly():
    lock_entries = _explicit_lock_entries()
    records = _installed_conda_records()
    installed_entries = {
        str(record["url"]): str(record["md5"]) for record in records
    }
    assert installed_entries == lock_entries

    installed_names = {str(record["name"]) for record in records}
    assert REQUIRED_RUNTIME_PACKAGES <= installed_names


def test_locked_runtime_imports_and_versions():
    import jsonschema
    import mpmath
    import pytest
    import triqs
    import triqs_cthyb

    modules = (jsonschema, mpmath, pytest, triqs, triqs_cthyb)
    assert all(module.__file__ for module in modules)
    versions = {
        str(record["name"]): str(record["version"])
        for record in _installed_conda_records()
    }
    assert versions["triqs"] == "4.0.0"
    assert versions["triqs_cthyb"] == "4.0.0"


if __name__ == "__main__":
    test_environment_declares_exact_runtime_dependencies()
    test_explicit_lock_has_independent_trusted_digests()
    test_explicit_lock_matches_active_prefix_exactly()
    test_locked_runtime_imports_and_versions()
