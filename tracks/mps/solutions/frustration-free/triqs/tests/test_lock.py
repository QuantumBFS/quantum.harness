import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


TRIQS_DIR = Path(__file__).resolve().parents[1]
LOCK_PATH = TRIQS_DIR / "conda-linux-64.lock"
ENVIRONMENT_PATH = TRIQS_DIR / "environment.yml"
REQUIRED_RUNTIME_PACKAGES = {
    "jsonschema",
    "mpmath",
    "pytest",
    "triqs",
    "triqs_cthyb",
}
MD5_PATTERN = re.compile(r"^[0-9a-f]{32}$")


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


def test_explicit_lock_matches_active_prefix_exactly():
    lock_entries = _explicit_lock_entries()
    records = _installed_conda_records()
    installed_entries = {
        str(record["url"]): str(record["md5"]) for record in records
    }
    assert installed_entries == lock_entries

    installed_names = {str(record["name"]) for record in records}
    assert REQUIRED_RUNTIME_PACKAGES <= installed_names

    environment = ENVIRONMENT_PATH.read_text(encoding="utf-8")
    assert environment.startswith(
        "name: challenge81-triqs\nchannels:\n  - conda-forge\n"
    )
    for dependency in REQUIRED_RUNTIME_PACKAGES:
        assert f"  - {dependency}" in environment


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
    test_explicit_lock_matches_active_prefix_exactly()
    test_locked_runtime_imports_and_versions()
