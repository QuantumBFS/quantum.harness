"""Discovers every <card>/oracle.py and runs its self_test()."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARDS = sorted(p for p in ROOT.glob("*/oracle.py") if not p.parent.name.startswith("_"))


def _load(path):
    spec = importlib.util.spec_from_file_location(f"oracle_{path.parent.name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("path", CARDS, ids=lambda p: p.parent.name)
def test_oracle_self_test(path):
    mod = _load(path)
    assert hasattr(mod, "self_test"), f"{path} lacks self_test()"
    mod.self_test()
