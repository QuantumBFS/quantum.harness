from __future__ import annotations

import numpy as np

from src.two_mode_joint_fit import (
    LossBlock,
    build_loss_blocks,
    fit_registered_model,
    joint_loss,
    robust_train_scales,
    score_registered_parameters,
)
from src.two_mode_observables import JointObservablePanel

RULES = {
    "optimization": {"multistarts": 8, "maxiter": 300, "seed": 17},
    "thresholds": {"scale_numerical_floor": 1e-8},
}


def test_each_observable_block_has_equal_weight() -> None:
    dense = LossBlock(
        "profile",
        observed=np.zeros((2, 100)),
        predicted=np.ones((2, 100)),
        scale=np.asarray(1.0),
        mask=np.asarray([True, True]),
    )
    sparse = LossBlock(
        "fcs",
        observed=np.zeros((2, 1), dtype=complex),
        predicted=np.full((2, 1), 2.0 + 2.0j),
        scale=np.asarray(1.0),
        mask=np.asarray([True, True]),
    )
    result = joint_loss([dense, sparse])
    assert result["per_block"]["profile"] == 1.0
    assert result["per_block"]["fcs"] == 4.0
    assert result["loss"] == 2.5


def _panel(observed: np.ndarray) -> JointObservablePanel:
    t = np.asarray([50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0])
    return JointObservablePanel(
        t=t,
        x=np.arange(observed.shape[1], dtype=float),
        profile={"synthetic": observed},
        current={},
        response_cmm={},
        response_cjm={},
        response_even={},
        fcs_gamma={},
        fcs_logz={},
        masks={
            "train": t <= 150.0,
            "validation": t > 150.0,
            "blind": np.zeros(t.size, dtype=bool),
        },
        diagnostics={},
    )


def test_recovers_independent_model_on_manufactured_data() -> None:
    t = np.asarray([50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0])
    basis_d = np.outer(t / 200.0, np.asarray([1.0, 0.5, -0.25]))
    basis_l = np.outer((t / 200.0) ** 2, np.asarray([0.2, -0.4, 0.7]))
    truth = np.asarray([0.8, 0.55])
    observed = truth[0] * basis_d + truth[1] * basis_l
    panel = _panel(observed)

    def predictor(name, parameters, panel, noise):
        return {
            "profile:synthetic": (
                parameters.Dm * basis_d + parameters.lambda_m * basis_l
            )
        }

    result = fit_registered_model(
        "independent_two_burgers",
        panel,
        noise_panel=None,
        rules=RULES,
        predictor=predictor,
    )
    assert result["status"] == "fit_complete"
    np.testing.assert_allclose(result["free"], truth, rtol=1e-4, atol=1e-4)
    assert result["validation"]["normalized_rmse"] < 1e-4


def test_recovers_coupled_five_parameter_model() -> None:
    t = np.asarray([50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0])
    q = t / 200.0
    bases = [
        np.outer(q ** (index + 1), np.roll(np.asarray([1.0, -0.3, 0.7, 0.2, -0.5]), index))
        for index in range(5)
    ]
    truth = np.asarray([0.9, 1.1, 0.35, -0.2, 0.4])
    observed = sum(value * basis for value, basis in zip(truth, bases))
    panel = _panel(observed)

    def predictor(name, parameters, panel, noise):
        values = [
            parameters.Dm,
            parameters.Dphi,
            parameters.lambda_m,
            parameters.lambda_phi,
            parameters.alpha,
        ]
        return {
            "profile:synthetic": sum(
                value * basis for value, basis in zip(values, bases)
            )
        }

    result = fit_registered_model(
        "coupled_two_mode",
        panel,
        noise_panel=None,
        rules=RULES,
        predictor=predictor,
    )
    assert result["status"] == "fit_complete"
    np.testing.assert_allclose(result["free"], truth, rtol=0.02, atol=0.02)


def test_frozen_scoring_does_not_refit_parameters() -> None:
    t = np.asarray([50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0])
    basis = np.outer(t / 200.0, np.asarray([1.0, -0.5, 0.2]))
    observed = 0.8 * basis
    panel = _panel(observed)

    def predictor(name, parameters, panel, noise):
        return {"profile:synthetic": parameters.Dm * basis}

    scored = score_registered_parameters(
        "gaussian_diffusion",
        np.asarray([0.8]),
        panel,
        noise_panel=None,
        predictor=predictor,
        scales={"profile:synthetic": 1.0},
        phase="validation",
    )
    assert scored["validation"]["loss"] < 1e-20
    assert scored["validation_n"] == 6


def test_amplitude_holdout_and_stress_rows_do_not_enter_training() -> None:
    t = np.asarray([50.0, 100.0, 150.0, 175.0, 200.0])
    values = np.outer(t / 200.0, np.asarray([1.0, -0.5]))
    panel = JointObservablePanel(
        t=t,
        x=np.arange(2.0),
        profile={
            "core": values,
            "holdout": 2.0 * values,
            "stress": 4.0 * values,
        },
        current={},
        response_cmm={},
        response_cjm={},
        response_even={},
        fcs_gamma={},
        fcs_logz={},
        masks={
            "train": t <= 150.0,
            "validation": t > 150.0,
            "blind": np.zeros(t.size, dtype=bool),
        },
        diagnostics={},
        metadata={
            "core": {"role": "primary_amplitude", "mu": 0.05},
            "holdout": {"role": "primary_amplitude", "mu": 0.10},
            "stress": {"role": "primary_amplitude", "mu": 0.20},
        },
    )
    predictions = {
        f"profile:{key}": value.copy()
        for key, value in panel.profile.items()
    }
    scales = robust_train_scales(panel, numerical_floor=1e-8)
    assert scales["profile:holdout"] == scales["profile:core"]
    assert scales["profile:stress"] == scales["profile:core"]
    train = build_loss_blocks(
        panel,
        predictions,
        phase="train",
        scales=scales,
    )
    validation = build_loss_blocks(
        panel,
        predictions,
        phase="validation",
        scales=scales,
    )
    stress = build_loss_blocks(
        panel,
        predictions,
        phase="stress_validation",
        scales=scales,
    )
    assert [block.name for block in train] == ["profile:core"]
    assert [block.name for block in validation] == [
        "profile:core",
        "profile:holdout",
    ]
    assert [block.name for block in stress] == ["profile:stress"]
