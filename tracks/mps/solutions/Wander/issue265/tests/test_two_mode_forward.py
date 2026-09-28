from __future__ import annotations

import numpy as np

from src.two_mode_forward import (
    ForwardFidelity,
    RegisteredForwardPredictor,
    fidelity_from_rules,
)
from src.two_mode_models import parameters_for_model
from src.two_mode_observables import (
    EQUILIBRIUM,
    PULSE_NEG,
    PULSE_POS,
    JointObservablePanel,
    subset_joint_observable_panel,
)


def _panel() -> JointObservablePanel:
    x = np.linspace(-4.0, 4.0, 16, endpoint=False)
    t = np.array([0.0, 0.001, 0.002])
    gaussian = np.exp(-0.5 * (x / 1.5) ** 2)
    initial = {
        PULSE_POS: 0.01 * gaussian,
        PULSE_NEG: -0.01 * gaussian,
        EQUILIBRIUM: np.zeros_like(x),
    }
    gamma = np.array([-0.4, -0.2, 0.0, 0.2, 0.4])
    metadata = {
        PULSE_POS: {
            "mu": 0.02,
            "orientation": 1,
            "background_m": 0.0,
            "role": "two_mode_response",
        },
        PULSE_NEG: {
            "mu": 0.02,
            "orientation": -1,
            "background_m": 0.0,
            "role": "two_mode_response",
        },
        EQUILIBRIUM: {
            "mu": 0.02,
            "orientation": 1,
            "background_m": 0.0,
            "role": "two_mode_equilibrium",
        },
    }
    profiles = {
        key: np.zeros((t.size, x.size)) for key in initial
    }
    currents = {
        key: np.zeros((t.size, x.size - 1)) for key in initial
    }
    return JointObservablePanel(
        t=t,
        x=x,
        profile=profiles,
        current=currents,
        response_cmm={"pulse_pair": np.zeros((t.size, x.size))},
        response_cjm={"pulse_pair": np.zeros((t.size, x.size - 1))},
        response_even={},
        fcs_gamma={EQUILIBRIUM: gamma},
        fcs_logz={EQUILIBRIUM: np.zeros((t.size, gamma.size), complex)},
        masks={
            "train": np.array([True, True, False]),
            "validation": np.array([False, False, True]),
            "blind": np.zeros(t.size, bool),
        },
        diagnostics={},
        metadata=metadata,
        simulation_x=x,
        profile_mask=np.ones(x.size, bool),
        current_masks={
            key: np.ones(x.size - 1, bool) for key in initial
        },
        physical_initial=initial,
        czz={EQUILIBRIUM: np.zeros((t.size, x.size))},
    )


def test_forward_operator_emits_every_joint_block() -> None:
    panel = _panel()
    predictor = RegisteredForwardPredictor(
        ForwardFidelity(
            spatial_stride=2,
            dt_internal=0.001,
            n_ensemble=8,
            seed=43,
        )
    )
    parameters = parameters_for_model(
        "independent_two_burgers", np.array([0.8, 0.5])
    )
    predicted = predictor(
        "independent_two_burgers", parameters, panel, None
    )
    expected = {
        *(f"profile:{key}" for key in panel.profile),
        *(f"current:{key}" for key in panel.current),
        "response_cmm:pulse_pair",
        "response_cjm:pulse_pair",
        f"czz:{EQUILIBRIUM}",
        f"fcs_logz:{EQUILIBRIUM}",
    }
    assert set(predicted) == expected
    for key in panel.profile:
        assert predicted[f"profile:{key}"].shape == panel.profile[key].shape
    assert (
        predicted[f"fcs_logz:{EQUILIBRIUM}"].shape
        == panel.fcs_logz[EQUILIBRIUM].shape
    )
    assert (
        predicted[f"czz:{EQUILIBRIUM}"].shape
        == panel.czz[EQUILIBRIUM].shape
    )


def test_forward_operator_supports_a_single_condition_fold() -> None:
    panel = subset_joint_observable_panel(_panel(), {PULSE_POS})
    predictor = RegisteredForwardPredictor(
        ForwardFidelity(
            spatial_stride=2,
            dt_internal=0.001,
            n_ensemble=8,
            seed=44,
        )
    )
    parameters = parameters_for_model(
        "independent_two_burgers", np.array([0.8, 0.5])
    )
    predicted = predictor(
        "independent_two_burgers", parameters, panel, None
    )
    assert set(predicted) == {
        f"profile:{PULSE_POS}",
        f"current:{PULSE_POS}",
    }


def test_registered_final_fidelity_refines_space_time_and_ensemble() -> None:
    rules = {
        "forward_model": {
            "screening_spatial_stride": 4,
            "screening_dt_internal": 0.2,
            "final_spatial_stride": 2,
            "final_dt_internal": 0.1,
            "screening_ensemble": 1024,
            "final_ensemble": 2048,
            "seed": 17,
        }
    }
    screening = fidelity_from_rules(rules, final=False)
    final = fidelity_from_rules(rules, final=True)
    assert screening == ForwardFidelity(4, 0.2, 1024, 17)
    assert final == ForwardFidelity(2, 0.1, 2048, 17)


def test_scalar_forward_respects_paired_pulse_spin_flip() -> None:
    panel = _panel()
    predictor = RegisteredForwardPredictor(
        ForwardFidelity(
            spatial_stride=2,
            dt_internal=0.001,
            n_ensemble=8,
            seed=47,
        )
    )
    parameters = parameters_for_model(
        "scalar_surrogate", np.array([0.8, 0.5])
    )
    predicted = predictor("scalar_surrogate", parameters, panel, None)
    physical_up = 0.02 * predicted[f"profile:{PULSE_POS}"]
    physical_down = 0.02 * predicted[f"profile:{PULSE_NEG}"]
    np.testing.assert_allclose(physical_down, -physical_up, atol=1e-12)
    np.testing.assert_allclose(
        predicted[f"current:{PULSE_NEG}"],
        -predicted[f"current:{PULSE_POS}"],
        atol=1e-12,
    )
    logz = predicted[f"fcs_logz:{EQUILIBRIUM}"]
    np.testing.assert_allclose(logz[:, :2], np.conj(logz[:, -1:-3:-1]))


def test_scalar_forward_is_invariant_to_a_uniform_background_shift() -> None:
    panel_zero = _panel()
    shift = 0.07
    panel_shifted = JointObservablePanel(
        **{
            **panel_zero.__dict__,
            "metadata": {
                key: {**values, "background_m": shift}
                for key, values in panel_zero.metadata.items()
            },
            "physical_initial": {
                key: values + shift
                for key, values in panel_zero.physical_initial.items()
            },
        }
    )
    predictor = RegisteredForwardPredictor(
        ForwardFidelity(
            spatial_stride=2,
            dt_internal=0.001,
            n_ensemble=8,
            seed=53,
        )
    )
    parameters = parameters_for_model(
        "scalar_surrogate", np.array([0.8, 0.5])
    )
    zero = predictor("scalar_surrogate", parameters, panel_zero, None)
    shifted = predictor(
        "scalar_surrogate", parameters, panel_shifted, None
    )
    for key in panel_zero.profile:
        np.testing.assert_allclose(
            shifted[f"profile:{key}"],
            zero[f"profile:{key}"],
            atol=1e-12,
        )
    for key in panel_zero.current:
        np.testing.assert_allclose(
            shifted[f"current:{key}"],
            zero[f"current:{key}"],
            atol=1e-12,
        )
