from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from floquet_if_manybody.poles import (
    TransferPole,
    fit_pole_residues,
    match_transfer_poles,
    transfer_poles,
)


def _poles(values: list[complex]) -> tuple[TransferPole, ...]:
    return tuple(
        TransferPole(
            eigenvalue=value,
            decay_rate=float(-np.log(abs(value))),
            quasifrequency=float(np.angle(value)),
            eigenpair_residual=1e-13,
        )
        for value in values
    )


def test_transfer_poles_convert_eigenvalues_to_rates() -> None:
    period = 2.0
    values = np.array([1.0, np.exp((-0.2 + 0.7j) * period)])
    poles = transfer_poles(values, np.array([1e-13, 2e-13]), period)
    assert len(poles) == 1
    assert_allclose(poles[0].decay_rate, 0.2, atol=1e-12)
    assert_allclose(poles[0].quasifrequency, 0.7, atol=1e-12)


def test_transfer_poles_accept_resolved_approximate_steady_mode() -> None:
    poles = transfer_poles(
        np.array([0.9991 + 1e-15j, 0.8 + 0.1j]),
        np.array([1e-13, 1e-13]),
        period=1.0,
    )
    assert len(poles) == 1
    assert poles[0].eigenvalue == 0.8 + 0.1j


def test_fit_recovers_complex_residues() -> None:
    period = 1.5
    eigenvalues = np.array([0.8 * np.exp(0.2j), 0.55 * np.exp(-0.4j)])
    residues = np.array([0.7 - 0.1j, -0.2 + 0.3j])
    n = np.arange(16)
    connected = sum(
        residue * eigenvalue**n
        for residue, eigenvalue in zip(residues, eigenvalues, strict=True)
    )
    fit = fit_pole_residues(
        transfer_poles(
            np.r_[1.0, eigenvalues],
            np.full(3, 1e-13),
            period,
        ),
        n * period,
        connected,
        period,
        max_modes=2,
    )
    assert_allclose(
        [item.residue for item in fit.residues],
        residues,
        atol=1e-10,
    )
    assert fit.reconstruction_residual < 1e-12


def test_fit_uses_only_stroboscopic_delays() -> None:
    poles = _poles([0.8 + 0.1j])
    delays = np.arange(9) * 0.5
    connected = np.full(9, 99 + 0j)
    connected[::2] = (0.3 - 0.2j) * poles[0].eigenvalue ** np.arange(5)
    fit = fit_pole_residues(
        poles,
        delays,
        connected,
        period=1.0,
        max_modes=1,
    )
    assert_allclose(fit.residues[0].residue, 0.3 - 0.2j)
    assert_allclose(fit.stroboscopic_delays, delays[::2])


def test_fit_requires_an_overdetermined_stroboscopic_window() -> None:
    with pytest.raises(ValueError, match="stroboscopic samples"):
        fit_pole_residues(
            _poles([0.8, 0.7]),
            np.array([0.0, 1.0]),
            np.array([1.0, 0.5], dtype=complex),
            period=1.0,
            max_modes=2,
        )


def test_mode_matching_follows_nearest_complex_poles() -> None:
    previous = _poles([0.9 + 0.1j, 0.7 - 0.2j])
    current = _poles([0.69 - 0.19j, 0.89 + 0.11j])
    matched = match_transfer_poles(previous, current)
    assert [item.current_index for item in matched] == [1, 0]


def test_degenerate_matching_is_marked_ambiguous() -> None:
    previous = _poles([0.8 + 0.1j, 0.8 + 0.1j])
    current = _poles([0.8 + 0.1j, 0.8 + 0.1j])
    assert all(item.ambiguous for item in match_transfer_poles(previous, current))
