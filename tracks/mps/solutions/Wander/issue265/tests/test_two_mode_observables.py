from __future__ import annotations

import numpy as np
import pytest

from src.research_dataset import ResearchDataset
from src.two_mode_observables import (
    EQUILIBRIUM,
    PULSE_NEG,
    PULSE_POS,
    build_joint_observable_panel,
    subset_joint_observable_panel,
)


def _dataset(
    condition_id: str,
    *,
    orientation: int,
    response: np.ndarray,
    current: np.ndarray,
    x: np.ndarray,
    t: np.ndarray,
    width: float = 2.0,
) -> ResearchDataset:
    metadata = {
        "delta": 1.0,
        "J": 1.0,
        "J2": 0.0,
        "temperature": "infinite",
        "L": x.size,
        "boundary_condition": "open",
        "mu": 0.02,
        "orientation": orientation,
        "width": width,
    }
    return ResearchDataset(
        condition_id=condition_id,
        x=x,
        t=t,
        u=response.copy(),
        m=response.copy(),
        current=current.copy(),
        czz=response**2,
        metadata=metadata,
    )


def _linear_panel() -> tuple[dict[str, ResearchDataset], np.ndarray, np.ndarray]:
    x = np.linspace(-3.5, 3.5, 8)
    t = np.asarray([0.0, 50.0, 100.0, 150.0, 175.0, 200.0, 300.0])
    response = np.outer(1.0 + t / 100.0, np.exp(-x**2))
    current = np.outer(1.0 + t / 200.0, np.ones(x.size - 1))
    epsilon = 0.02
    datasets = {
        PULSE_POS: _dataset(
            PULSE_POS,
            orientation=1,
            response=epsilon * response,
            current=epsilon * current,
            x=x,
            t=t,
        ),
        PULSE_NEG: _dataset(
            PULSE_NEG,
            orientation=-1,
            response=-epsilon * response,
            current=-epsilon * current,
            x=x,
            t=t,
        ),
        EQUILIBRIUM: _dataset(
            EQUILIBRIUM,
            orientation=1,
            response=np.zeros_like(response),
            current=np.zeros_like(current),
            x=x,
            t=t,
        ),
    }
    return datasets, response, current


def test_centered_pulse_response_and_even_remainder() -> None:
    datasets, expected_m, expected_j = _linear_panel()
    panel = build_joint_observable_panel(
        datasets,
        pulse_amplitude=0.02,
        spatial_window=(-4.0, 4.0),
    )
    np.testing.assert_allclose(panel.response_cmm["pulse_pair"], expected_m)
    np.testing.assert_allclose(panel.response_cjm["pulse_pair"], expected_j)
    np.testing.assert_allclose(panel.response_even["magnetization"], 0.0)
    np.testing.assert_allclose(panel.response_even["current"], 0.0)
    np.testing.assert_allclose(
        panel.czz[PULSE_POS],
        datasets[PULSE_POS].czz,
    )
    assert np.count_nonzero(panel.masks["train"]) == 3
    assert np.count_nonzero(panel.masks["validation"]) == 2
    assert np.count_nonzero(panel.masks["blind"]) == 1


def test_even_nonlinear_remainder_is_retained() -> None:
    datasets, _, _ = _linear_panel()
    datasets[PULSE_POS].m[:] += 1e-3
    datasets[PULSE_POS].u[:] += 1e-3
    panel = build_joint_observable_panel(
        datasets,
        pulse_amplitude=0.02,
        spatial_window=(-4.0, 4.0),
    )
    np.testing.assert_allclose(panel.response_even["magnetization"], 5e-4)
    assert panel.diagnostics["pulse_even_magnetization_max_abs"] == pytest.approx(
        5e-4
    )


def test_rejects_spatial_grid_mismatch() -> None:
    datasets, _, _ = _linear_panel()
    datasets[PULSE_NEG] = ResearchDataset(
        **{
            **datasets[PULSE_NEG].__dict__,
            "x": datasets[PULSE_NEG].x + 0.1,
        }
    )
    with pytest.raises(ValueError, match="spatial grid"):
        build_joint_observable_panel(
            datasets,
            pulse_amplitude=0.02,
            spatial_window=(-4.0, 4.0),
        )


def test_rejects_pulse_width_mismatch() -> None:
    datasets, _, _ = _linear_panel()
    datasets[PULSE_NEG].metadata["width"] = 3.0
    with pytest.raises(ValueError, match="width mismatch"):
        build_joint_observable_panel(
            datasets,
            pulse_amplitude=0.02,
            spatial_window=(-4.0, 4.0),
        )


def test_condition_subset_keeps_response_only_with_both_pulses() -> None:
    datasets, _, _ = _linear_panel()
    panel = build_joint_observable_panel(
        datasets,
        pulse_amplitude=0.02,
        spatial_window=(-4.0, 4.0),
    )
    pair = subset_joint_observable_panel(
        panel,
        {PULSE_POS, PULSE_NEG},
    )
    assert set(pair.profile) == {PULSE_POS, PULSE_NEG}
    assert set(pair.response_cmm) == {"pulse_pair"}
    single = subset_joint_observable_panel(panel, {PULSE_POS})
    assert single.response_cmm == {}
    assert single.response_cjm == {}
