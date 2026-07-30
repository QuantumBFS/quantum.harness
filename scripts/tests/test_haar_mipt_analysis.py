import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_analysis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_analysis", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_analysis"] = module
    spec.loader.exec_module(module)
    return module


def _record(L, family, index, density, runtime=1.0):
    record_steps = 24 * L
    return {
        "schema_version": 1,
        "L": L,
        "p": 0.168,
        "initial_family": family,
        "sample_index": index,
        "seed": 100000 * L + 1000 * (family == "product") + index,
        "burn_in_steps": 4 * L,
        "record_steps": record_steps,
        "record_cost": density * L * record_steps,
        "cumulative_record_cost": [
            density * L * (j + 1) for j in range(record_steps)
        ],
        "runtime_seconds": runtime,
        "gate_count": 14 * L**2,
        "attempted_measurements": 1,
        "outcome_counts": [1, 0],
    }


def _synthetic_records(seed, central_charge, per_family):
    rng = np.random.default_rng(seed)
    records = []
    for L in (8, 10, 12, 14, 16, 18):
        target = 1.7 - np.pi * 0.81 * central_charge / (6 * L**2)
        for family, shift in (("global_haar", 0.0005), ("product", -0.0005)):
            for index in range(per_family):
                density = target + shift + 2e-5 * rng.normal()
                records.append(_record(L, family, index, density))
    return records


def _weighted_l4_rows():
    # Six non-collinear observations make the three-parameter fit overdetermined.
    return [
        {
            "L": L,
            "tilde_f": value,
            "tilde_f_se": error,
        }
        for L, value, error in (
            (2, 1.940, 0.004),
            (3, 1.972, 0.012),
            (4, 1.981, 0.006),
            (5, 1.988, 0.020),
            (6, 1.989, 0.008),
            (8, 1.995, 0.005),
        )
    ]


def test_aggregation_gives_families_equal_weight():
    module = _load_module()
    records = [_record(8, "global_haar", j, 1.0 + 0.01 * j) for j in range(4)]
    records += [_record(8, "product", j, 3.0 + 0.02 * j) for j in range(2)]
    row = module.aggregate_trajectory_records(records)[0]
    assert row["tilde_f"] == pytest.approx(
        0.5 * (np.mean([1.0, 1.01, 1.02, 1.03]) + np.mean([3.0, 3.02]))
    )
    expected_se = 0.5 * np.sqrt(
        np.var([1.0, 1.01, 1.02, 1.03], ddof=1) / 4
        + np.var([3.0, 3.02], ddof=1) / 2
    )
    assert row["tilde_f_se"] == pytest.approx(expected_se)
    assert row["families"]["global_haar"]["count"] == 4
    assert row["families"]["product"]["count"] == 2


def test_trajectory_entropy_fit_recovers_slope_and_intercept():
    module = _load_module()
    L, steps = 8, 40
    slope, intercept = 0.111, 0.37
    record = _record(L, "global_haar", 0, slope)
    record["cumulative_record_cost"] = [
        L * (intercept + slope * t) for t in range(1, steps + 1)
    ]
    record["record_steps"] = steps
    record["record_cost"] = record["cumulative_record_cost"][-1]
    fit = module.trajectory_entropy_fit(record)
    assert fit["slope"] == pytest.approx(slope, abs=1e-13)
    assert fit["intercept"] == pytest.approx(intercept, abs=1e-13)


def test_aggregate_uses_slope_not_endpoint_by_default():
    module = _load_module()
    records = []
    for family in ("global_haar", "product"):
        for index in range(2):
            record = _record(8, family, index, 0.2)
            record["cumulative_record_cost"] = [
                8 * (1.0 + 0.2 * t) for t in range(1, 193)
            ]
            record["record_cost"] = record["cumulative_record_cost"][-1]
            records.append(record)
    row = module.aggregate_trajectory_records(records)[0]
    assert row["tilde_f"] == pytest.approx(0.2)


def test_aggregation_rejects_duplicate_sample_identity():
    module = _load_module()
    records = [
        _record(8, "global_haar", 0, 1.0),
        _record(8, "global_haar", 0, 1.1),
        _record(8, "product", 0, 2.0),
        _record(8, "product", 1, 2.1),
    ]
    with pytest.raises(ValueError, match="duplicate"):
        module.aggregate_trajectory_records(records)


@pytest.mark.parametrize(
    "records",
    [
        [_record(8, "global_haar", j, 1.0) for j in range(2)],
        [
            _record(8, "global_haar", 0, 1.0),
            _record(8, "product", 0, 2.0),
            _record(8, "product", 1, 2.0),
        ],
    ],
    ids=("missing-family", "one-global-trajectory"),
)
def test_aggregation_requires_two_trajectories_per_family(records):
    module = _load_module()
    with pytest.raises(ValueError, match="needs two trajectories"):
        module.aggregate_trajectory_records(records)


def test_weighted_l2_fit_uses_inverse_variance_weights():
    module = _load_module()
    # Literal coefficients come from solving (X^T W X)b = X^T W y by hand.
    rows = [
        {"L": 1, "tilde_f": 3.0, "tilde_f_se": 0.10},
        {"L": 2, "tilde_f": 2.2, "tilde_f_se": 0.20},
        {"L": 4, "tilde_f": 2.0, "tilde_f_se": 0.40},
        {"L": 8, "tilde_f": 2.1, "tilde_f_se": 0.05},
    ]
    result = module.weighted_l2_fit(rows, lmin=1)
    assert result["intercept"] == pytest.approx(2.078582202111614, abs=2e-13)
    assert result["slope"] == pytest.approx(0.9146304675716435, abs=2e-13)
    assert result["widths"] == [1, 2, 4, 8]


def test_slope_extrapolation_recovers_known_central_charge():
    module = _load_module()
    alpha, expected_c = 0.81, 0.25
    m_inf = -np.pi * alpha * expected_c / 6.0
    fits = [
        {"lmin": lmin, "slope": m_inf + 0.7 / lmin**2}
        for lmin in (8, 10, 12, 14)
    ]
    result = module.extrapolate_slopes(fits, alpha)
    assert result["central_charge"] == pytest.approx(expected_c, abs=2e-13)


def test_l4_stability_fit_uses_inverse_variance_weights():
    module = _load_module()
    # Literal coefficients independently solve weighted normal equations.
    result = module.l4_stability_fit(_weighted_l4_rows(), alpha=0.9)
    assert result["intercept"] == pytest.approx(1.998621121206348, abs=2e-12)
    assert result["l2_coefficient"] == pytest.approx(
        -0.2841864320769388, abs=2e-11
    )
    assert result["l4_coefficient"] == pytest.approx(
        0.19934495009559716, abs=2e-10
    )
    assert result["central_charge"] == pytest.approx(
        0.6030623389959197, abs=5e-11
    )


def test_summary_honors_alpha_and_is_json_serializable():
    module = _load_module()
    records = _synthetic_records(seed=11, central_charge=0.25, per_family=6)
    _, summary = module.central_charge_summary(
        records, samples=8, seed=3, alpha=0.9
    )
    assert summary["alpha"] == 0.9
    assert summary["alpha_se"] == 0.09
    assert summary["anisotropy_error"] == pytest.approx(
        abs(summary["central_charge"]) * 0.09 / 0.9
    )
    assert summary["central_charge"] == pytest.approx(0.225, abs=0.03)
    assert summary["pc"] == 0.168
    assert summary["pc_literature_error"] == 0.005
    assert summary["pc_error_propagated"] is False
    assert summary["literature_central_charge"] == 0.25
    assert summary["literature_central_charge_error"] == 0.03
    json.dumps(summary)


def test_bootstrap_keeps_observed_weights_when_resamples_have_zero_variance():
    module = _load_module()
    records = []
    for L in (8, 10, 12, 14, 16, 18):
        target = 1.7 - np.pi * 0.81 * 0.25 / (6 * L**2)
        for family, shift in (("global_haar", 0.0005), ("product", -0.0005)):
            records.append(_record(L, family, 0, target + shift - 0.0001))
            records.append(_record(L, family, 1, target + shift + 0.0001))
    first = module.bootstrap_central_charge(records, samples=25, seed=23)
    second = module.bootstrap_central_charge(records, samples=25, seed=23)
    assert first.shape == (25,)
    assert np.all(np.isfinite(first))
    np.testing.assert_array_equal(first, second)


def test_bootstrap_and_artifacts_are_reproducible(tmp_path):
    module = _load_module()
    records = _synthetic_records(seed=7, central_charge=0.25, per_family=20)
    widths, first = module.central_charge_summary(records, samples=40, seed=19)
    _, second = module.central_charge_summary(records, samples=40, seed=19)
    assert first["bootstrap_se"] == second["bootstrap_se"]
    assert first["bootstrap_percentile_95"] == second["bootstrap_percentile_95"]
    assert abs(first["central_charge"] - 0.25) < 0.03
    module.write_analysis_artifacts(records, widths, first, tmp_path)
    names = {p.name for p in tmp_path.iterdir()}
    assert {
        "trajectory_summary.csv",
        "width_summary.csv",
        "fit_summary.json",
        "central_charge_fit.png",
        "record_entropy_growth.png",
    } <= names
    with (tmp_path / "fit_summary.json").open(encoding="utf-8") as handle:
        assert json.load(handle) == first
    assert (tmp_path / "central_charge_fit.png").stat().st_size > 0
    assert (tmp_path / "record_entropy_growth.png").stat().st_size > 0


def test_central_charge_plot_line_uses_a_single_weighted_window():
    module = _load_module()
    records = _synthetic_records(seed=11, central_charge=0.25, per_family=20)
    widths = module.aggregate_trajectory_records(records)
    expected = module.weighted_l2_fit(widths, lmin=8)

    line = module._central_charge_plot_line(widths, lmin=8)

    assert line["intercept"] == pytest.approx(expected["intercept"])
    assert line["slope"] == pytest.approx(expected["slope"])
    np.testing.assert_allclose(
        line["y"], line["intercept"] + line["slope"] * line["x"]
    )
