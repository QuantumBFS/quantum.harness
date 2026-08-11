import numpy as np

from ceffflow.analysis import fit_window_audit, reblocking_audit
from ceffflow.fits import casimir_gls
from ceffflow.runner import execute_cell
from ceffflow.schema import CellConfig


def test_fit_window_audit_reports_lmin_and_leave_one_out_variants():
    lengths = [6, 8, 10, 12, 14, 16]
    config = CellConfig(
        model="nishimori",
        lengths=lengths,
        channel={"kind": "identity", "parameter": 0.0},
        steps=200,
        burn_in=10,
        block_size=10,
        seed=0,
        particles=1,
    )
    sizes = np.asarray(lengths, dtype=float)
    curve = -1.3 * sizes - np.pi * 0.464 / (6.0 * sizes)
    rng = np.random.default_rng(122)
    blocks = curve + rng.normal(scale=2e-5, size=(20, sizes.size))
    audit = fit_window_audit(config, blocks)
    labels = {variant["label"] for variant in audit["variants"]}
    assert "without_l3" in labels
    assert "lmin_8" in labels
    assert "omit_6" in labels
    assert audit["baseline"]["samples"] == 20
    assert isinstance(audit["stable_within_two_combined_se"], bool)


def test_fit_window_audit_baseline_uses_width_covariance_gls():
    lengths = [6, 8, 10, 12, 14, 16]
    config = CellConfig(
        model="nishimori",
        lengths=lengths,
        channel={"kind": "identity", "parameter": 0.0},
        steps=400,
        burn_in=10,
        block_size=10,
        seed=0,
        particles=1,
    )
    sizes = np.asarray(lengths, dtype=float)
    curve = (
        -1.1 * sizes
        - np.pi * 0.464 / (6.0 * sizes)
        + 0.2 / sizes**3
        + 0.7 / sizes**5
    )
    rng = np.random.default_rng(7)
    scales = np.asarray([2e-4, 3e-5, 8e-5, 2e-5, 6e-5, 1e-5])
    blocks = curve + rng.normal(size=(40, sizes.size)) * scales
    covariance_of_mean = np.cov(blocks, rowvar=False, ddof=1) / blocks.shape[0]
    expected = casimir_gls(
        sizes,
        blocks.mean(axis=0),
        covariance_of_mean,
        alpha=1.0,
        include_l3=True,
        compute_leave_one_out=False,
    )
    baseline = fit_window_audit(config, blocks)["baseline"]
    assert np.isclose(
        baseline["central_charge"], expected.central_charge, atol=1e-12
    )
    assert np.isclose(
        baseline["standard_error"], expected.standard_error, atol=1e-12
    )


def test_fit_window_audit_skips_exact_clean_calibration():
    config = CellConfig(
        model="clean_ising",
        lengths=[6, 8, 10, 12],
        channel={"kind": "identity", "parameter": 0.0},
        steps=20,
        burn_in=0,
        block_size=10,
        seed=0,
        particles=1,
    )
    audit = fit_window_audit(config, np.zeros((1, 4)))
    assert audit["status"] == "not_applicable_exact_calibration"


def test_fit_window_audit_marks_complete_loss_as_analytic():
    endpoints = [("confusion", 0.5), ("erasure", 0.0)]
    for kind, parameter in endpoints:
        config = CellConfig(
            model="self_dual",
            lengths=[6, 8, 10, 12, 14, 16],
            channel={"kind": kind, "parameter": parameter},
            steps=20,
            burn_in=0,
            block_size=10,
            seed=0,
            particles=1,
        )
        audit = fit_window_audit(config, execute_cell(config))
        assert audit["status"] == "not_applicable_analytic_endpoint"
        assert audit["exact_central_charge"] == -0.5
        assert abs(audit["finite_width_bias"]) < 3e-5


def test_reblocking_audit_preserves_seed_boundaries_and_reports_scales():
    config = CellConfig(
        model="self_dual",
        lengths=[6, 8, 10, 12, 14, 16],
        channel={"kind": "identity", "parameter": 0.0},
        steps=100,
        burn_in=0,
        block_size=5,
        seed=0,
        particles=1,
    )
    rng = np.random.default_rng(122)
    arrays = [rng.normal(size=(20, 6)) for _ in range(8)]
    audit = reblocking_audit(config, arrays)
    assert audit["baseline"]["samples"] == 160
    assert [item["factor"] for item in audit["variants"]] == [2, 4, 5, 10]
    assert [item["samples"] for item in audit["variants"]] == [80, 40, 32, 16]
    assert [item["effective_block_size"] for item in audit["variants"]] == [
        10,
        20,
        25,
        50,
    ]
