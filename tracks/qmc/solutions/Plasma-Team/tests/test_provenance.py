from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from chiral_graviton.provenance import collect_provenance


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def test_collect_provenance_records_versions_config_tolerances_and_times(tmp_path: Path):
    repository = tmp_path / "checkout"
    repository.mkdir()
    _git(repository, "init")
    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "initial",
    )

    local_zone = timezone(timedelta(hours=8))
    fixed_time = datetime(2026, 7, 30, 9, 10, 11, 123456, tzinfo=local_zone)
    payload = collect_provenance(
        {"n": 7, "seed": 1729, "interaction": "coulomb", "max_iterations": 400},
        {"variance": 1e-10, "residual": 1e-9, "l2": 1e-7},
        repository=repository,
        now=fixed_time,
    )

    assert payload["timestamps"] == {
        "utc": "2026-07-30T01:10:11.123456Z",
        "local": "2026-07-30T09:10:11.123456+08:00",
    }
    assert payload["software"]["python"]["version"]
    assert set(payload["software"]["dependencies"]) == {"numpy", "scipy", "sympy"}
    assert all(value != "not-installed" for value in payload["software"]["dependencies"].values())
    assert payload["platform"]["system"]
    assert len(payload["git"]["commit"]) == 40
    assert payload["git"]["dirty"] is False
    assert payload["run_config"]["seed"] == 1729
    assert payload["tolerances"]["variance"] == 1e-10
    json.dumps(payload, allow_nan=False)

    (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    assert collect_provenance({}, {}, repository=repository)["git"]["dirty"] is True


def test_collect_provenance_rejects_nonfinite_or_non_json_configuration(tmp_path: Path):
    with pytest.raises(ValueError, match="finite JSON"):
        collect_provenance({"energy": float("nan")}, {}, repository=tmp_path)
    with pytest.raises(ValueError, match="finite JSON"):
        collect_provenance({}, {"path": tmp_path}, repository=tmp_path)
    with pytest.raises(ValueError, match="timezone-aware"):
        collect_provenance({}, {}, repository=tmp_path, now=datetime(2026, 7, 30))


def test_collect_provenance_degrades_when_git_metadata_is_unavailable(tmp_path: Path):
    payload = collect_provenance({}, {}, repository=tmp_path)
    assert payload["git"]["available"] is False
    assert payload["git"]["commit"] is None
    assert payload["git"]["dirty"] is None
