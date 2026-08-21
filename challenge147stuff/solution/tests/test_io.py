import pytest
from core.io import MemoryBudgetExceeded, assert_mem_available, write_manifest, write_csv
import json
import os
import tempfile


def test_assert_mem_available_noop_when_enough():
    # 0.0001 GB = ~100 KB, always available
    assert_mem_available(0.0001, "unit-test")  # must not raise


def test_assert_mem_available_raises_when_too_much():
    with pytest.raises(MemoryBudgetExceeded) as exc:
        assert_mem_available(1e9, "unit-test")  # 1 billion GB -> impossible
    assert exc.value.context == "unit-test"
    assert exc.value.requested_gb == 1e9
    assert exc.value.available_gb > 0


def test_write_manifest_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.json")
        write_manifest(p, {"engine": "ed", "Lx": 4, "degraded": False})
        with open(p) as f:
            assert json.load(f)["engine"] == "ed"


def test_write_csv_creates_parent_and_header():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sub", "out.csv")
        write_csv(p, [{"a": 1, "b": 2}], ["a", "b"])
        with open(p) as f:
            # line endings are platform-dependent (\r\n or \n); compare line-wise
            lines = [ln.rstrip("\r\n") for ln in f]
        assert lines == ["a,b", "1,2"]
