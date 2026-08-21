"""Delivery tests for the X-cube structured geometric control."""

from __future__ import annotations

import json

import numpy as np

from run_xcube_geometric_control_v11 import (
    OPENED_LENGTHS,
    run_control,
    scientific_projection,
)


def test_opened_xcube_control_is_complete(tmp_path) -> None:
    result = run_control(tmp_path)
    assert OPENED_LENGTHS == (2, 3, 4, 5)
    assert result["all_checks_pass"] is True
    assert len(result["cases"]) == len(OPENED_LENGTHS)
    assert (tmp_path / "xcube_geometric_control_v11.json").is_file()
    assert (tmp_path / "xcube_geometric_control_v11.npz").is_file()
    for case in result["cases"]:
        length = case["length"]
        assert case["logical_qubits"] == 6 * length - 3
        assert case["ground_dimension"] == 2 ** (6 * length - 3)
        assert case["coefficient_control"]["berry_curvature"] == 0.0
        assert case["transport_control"]["curvature_eigenvalue"] == -0.5
        assert case["transport_control"]["connected_curvature_variance"] == 0.0
        assert all(case["checks"].values())


def test_xcube_result_is_deterministic_and_arrays_match(tmp_path) -> None:
    first = run_control(tmp_path / "first", lengths=(2, 3))
    second = run_control(tmp_path / "second", lengths=(2, 3))
    assert scientific_projection(first) == scientific_projection(second)
    with np.load(
        tmp_path / "first" / "xcube_geometric_control_v11.npz",
        allow_pickle=False,
    ) as arrays:
        assert arrays["lengths"].tolist() == [2, 3]
        assert arrays["logical_qubits"].tolist() == [9, 15]
        assert np.all(arrays["coefficient_curvature"] == 0.0)
        assert np.all(arrays["transport_curvature"] == -0.5)
    payload = json.loads(
        (tmp_path / "first" / "xcube_geometric_control_v11.json").read_text(
            encoding="utf-8"
        )
    )
    assert scientific_projection(payload) == scientific_projection(first)
