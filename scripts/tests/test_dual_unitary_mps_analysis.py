import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "dual_unitary_mps_analysis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "dual_unitary_mps_analysis", _SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_infinite_chi_plateau_uses_only_converged_groups():
    module = _load_module()
    records = []
    for chi, discard, center in (
        (16, 2e-3, 0.08),
        (32, 2e-5, 0.09),
        (64, 2e-7, 0.10),
        (128, 1e-9, 0.102),
    ):
        for sample in range(4):
            records.append(
                {
                    "L": 8,
                    "chi": chi,
                    "sample_index": sample,
                    "tilde_f": center + 0.001 * (sample - 1.5),
                    "discarded_weight_rate": discard,
                }
            )

    row = module.estimate_infinite_chi(
        records, discard_rate_threshold=1e-5
    )[0]
    assert row["selected_chis"] == [64, 128]
    assert row["trajectory_count"] == 8
    assert row["f_infinite"] == pytest.approx(0.101)
    assert row["f_infinite_se"] > 0.0


def test_finite_size_fit_recovers_known_central_charge():
    module = _load_module()
    central_charge = 0.25
    rows = []
    for L in (8, 10, 12, 14, 16):
        value = 0.09 - np.pi * central_charge / (6 * L**2) + 0.2 / L**4
        rows.append(
            {
                "L": L,
                "f_infinite": value,
                "f_infinite_se": 1e-5,
                "chi_systematic": 0.0,
            }
        )

    fit = module.fit_central_charge(rows, include_l4=True, alpha=1.0)
    assert fit["central_charge"] == pytest.approx(central_charge, abs=1e-10)
    assert fit["coefficients"][0] == pytest.approx(0.09, abs=1e-10)
    assert fit["chi2_per_dof"] < 1e-15


def test_chi_threshold_envelope_reports_all_valid_thresholds():
    module = _load_module()
    records = []
    for L in (8, 10, 12, 14, 16):
        target = 0.09 - np.pi * 0.25 / (6 * L**2)
        for chi, discard in ((32, 5e-5), (64, 5e-6), (128, 5e-8)):
            for sample in range(3):
                records.append(
                    {
                        "L": L,
                        "chi": chi,
                        "sample_index": sample,
                        "tilde_f": target + 1e-5 * (sample - 1),
                        "discarded_weight_rate": discard,
                    }
                )

    summary = module.threshold_fit_envelope(
        records, thresholds=(1e-4, 1e-5, 1e-6), alpha=1.0
    )
    assert len(summary["fits"]) == 3
    assert summary["central_charge_min"] == pytest.approx(0.25, abs=1e-10)
    assert summary["central_charge_max"] == pytest.approx(0.25, abs=1e-10)
