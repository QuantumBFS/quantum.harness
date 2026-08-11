from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
sys.path.insert(0, str(ROOT / "scripts"))

from kernel_extended import c_infinity, infinite_axial_sigma2  # noqa: E402


def read_rows(name: str) -> list[dict[str, str]]:
    with (ARTIFACTS / "tables" / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_analytic_kernel_anchor() -> None:
    predicted = math.pi * float(c_infinity()) / 2
    assert predicted == pytest_approx(1.0425387859782584, abs=1e-14)

    k1 = 2 * math.pi / 4096
    k2 = 2 * math.pi / 8192
    y1 = infinite_axial_sigma2(k1) / k1**2
    y2 = infinite_axial_sigma2(k2) / k2**2
    local_slope = (y2 - y1) / math.log(2)
    assert local_slope == pytest_approx(predicted, rel=2e-7)


def pytest_approx(value: float, **kwargs):
    import pytest

    return pytest.approx(value, **kwargs)


def test_committed_kernel_result() -> None:
    result = json.loads(
        (ARTIFACTS / "kernel_extended_results.json").read_text()
    )
    assert abs(result["relative_slope_error"]) < 1e-6
    assert result["predicted_log_slope"] == pytest_approx(
        1.0425387859782584,
        abs=1e-14,
    )


def test_registered_scalar_anchors() -> None:
    expected_p = {
        1: 0.316410,
        2: 0.102189,
        4: 0.044184,
        8: 0.020541,
    }
    rows = read_rows("scalar_fit_windows.csv")
    for beta, expected in expected_p.items():
        row = next(
            item
            for item in rows
            if int(float(item["beta"])) == beta
            and int(float(item["Lmin"])) == 64
            and item["model"] == "D2"
        )
        assert float(row["p"]) == pytest_approx(expected, abs=1e-5)


def test_source_matched_decay_preferred_on_registered_window() -> None:
    rows = read_rows("publication_matched_windows.csv")
    for beta in [1, 2, 4, 8]:
        row = next(
            item
            for item in rows
            if int(float(item["beta"])) == beta
            and int(float(item["Lmin"])) == 64
            and item["model"] == "OP"
        )
        assert float(row["delta_AICc_OP_minus_DP"]) > 0


def test_synthetic_and_joint_sensitivity_counts() -> None:
    synthetic = read_rows("synthetic_identifiability.csv")
    assert len(synthetic) == 8
    assert all(
        int(float(row["replicates"])) == 2000 for row in synthetic
    )

    joint = read_rows("joint_covariance_sensitivity.csv")
    assert len(joint) == 36
    assert min(
        float(row["delta_AICc_ordered_minus_decaying"])
        for row in joint
    ) > 0
