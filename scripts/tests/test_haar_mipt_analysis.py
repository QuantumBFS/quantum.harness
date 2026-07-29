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


def _exact_width_rows():
    # y = 2 - 0.45/L^2 + 1.2/L^4, with deliberately unequal errors.
    return [
        {
            "L": L,
            "tilde_f": 2.0 - 0.45 / L**2 + 1.2 / L**4,
            "tilde_f_se": 0.001 * (1 + L / 10),
        }
        for L in (8, 10, 12, 14, 16, 18)
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


def test_weighted_l2_fit_recovers_hand_derived_line():
    module = _load_module()
    rows = [
        {"L": 8, "tilde_f": 1.996875, "tilde_f_se": 0.001},
        {"L": 10, "tilde_f": 1.998, "tilde_f_se": 0.003},
        {"L": 20, "tilde_f": 1.9995, "tilde_f_se": 0.002},
    ]
    result = module.weighted_l2_fit(rows, lmin=10)
    assert result["intercept"] == pytest.approx(2.0, abs=2e-13)
    assert result["slope"] == pytest.approx(-0.2, abs=2e-13)
    assert result["widths"] == [10, 20]


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


def test_l4_stability_fit_recovers_hand_derived_coefficients():
    module = _load_module()
    result = module.l4_stability_fit(_exact_width_rows(), alpha=0.9)
    assert result["intercept"] == pytest.approx(2.0, abs=2e-12)
    assert result["l2_coefficient"] == pytest.approx(-0.45, abs=2e-10)
    assert result["l4_coefficient"] == pytest.approx(1.2, abs=2e-8)
    assert result["central_charge"] == pytest.approx(3 / np.pi, abs=5e-10)


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
