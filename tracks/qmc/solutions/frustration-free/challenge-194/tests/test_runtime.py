import importlib.metadata
import json
import subprocess
import sys

from long_range_percolation.runtime import runtime_capability


def test_numba_is_exactly_pinned_and_imports_in_fresh_python():
    declared = open("pyproject.toml", encoding="utf-8").read()
    version = importlib.metadata.version("numba")
    assert f'"numba=={version}"' in declared
    completed = subprocess.run(
        [sys.executable, "-c", "import numba, numpy; print(numba.__version__)"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == version


def test_runtime_capability_is_complete_and_json_stable():
    first = runtime_capability()
    second = runtime_capability()
    assert first == second
    assert first["schema_version"] == "challenge-194-runtime-v1"
    assert first["fastmath"] is False
    assert first["boundscheck"] is True
    assert json.loads(json.dumps(first, sort_keys=True)) == first
