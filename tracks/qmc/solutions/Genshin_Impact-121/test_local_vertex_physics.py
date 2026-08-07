from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import local_vertex_physics as local


def assert_report_close(actual: Any, expected: Any, path: str = "root") -> None:
    assert type(actual) is type(expected), path
    if isinstance(actual, dict):
        assert set(actual) == set(expected), path
        for key in actual:
            assert_report_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, list):
        assert len(actual) == len(expected), path
        for index, (left, right) in enumerate(zip(actual, expected)):
            assert_report_close(left, right, f"{path}[{index}]")
    elif isinstance(actual, float):
        assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-13), path
    else:
        assert actual == expected, path


def test_frozen_local_vertex_report_matches_independent_rebuild() -> None:
    frozen = json.loads(
        Path(__file__).with_name("local_vertex_physics_frozen.json").read_text(
            encoding="utf-8"
        )
    )
    rebuilt = local.build_report()
    assert rebuilt["status"] == "analytic_numeric_local_result"
    assert rebuilt["self_checks"]["status"] == "pass"
    assert_report_close(rebuilt, frozen)
