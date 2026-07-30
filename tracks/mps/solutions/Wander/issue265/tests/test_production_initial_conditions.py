from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import src.production_initial_conditions as module
from src.production_initial_conditions import (
    production_initial_magnetization,
    production_source_closure,
)


ROOT = Path(__file__).resolve().parents[1]


def test_uniform_zero_is_exact() -> None:
    x = np.linspace(-8.0, 8.0, 16)
    condition = {
        "profile": "uniform_zero",
        "background_m": 0.0,
        "temperature": "infinite",
    }
    np.testing.assert_array_equal(
        production_initial_magnetization(x, condition),
        np.zeros_like(x),
    )


def test_uniform_zero_rejects_nonzero_background() -> None:
    with pytest.raises(ValueError, match="zero background"):
        production_initial_magnetization(
            np.arange(5.0),
            {
                "profile": "uniform_zero",
                "background_m": 0.01,
                "temperature": "infinite",
            },
        )


def test_nonuniform_condition_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = np.arange(5.0)
    monkeypatch.setattr(module, "_base_initial", lambda x, c: sentinel)
    result = production_initial_magnetization(
        np.arange(5.0), {"profile": "gaussian"}
    )
    assert result is sentinel


def test_source_closure_covers_wrapper_and_frozen_dependencies() -> None:
    audit = production_source_closure(ROOT)
    assert audit["valid"] is True
    assert len(audit["files"]) == 7
    assert "scripts/run_tenpy_production_job.py" in audit["files"]
    assert len(audit["source_closure_sha256"]) == 64
