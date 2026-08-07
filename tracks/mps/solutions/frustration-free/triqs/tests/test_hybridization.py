from __future__ import annotations

import copy
import math
from pathlib import Path
import sys

import mpmath
import numpy as np
import pytest


TRIQS_DIR = Path(__file__).resolve().parents[1]
SOLUTION_DIR = TRIQS_DIR.parent
sys.path.insert(0, str(TRIQS_DIR))
sys.path.insert(0, str(SOLUTION_DIR))

from artifacts import canonical_json, sha256_bytes
import bath
from hybridization import (
    delta_iw,
    install_g0,
    reported_tau_indices,
    serialize_complex128,
    verify_common_real_frequency,
)


COMMON_SHA256 = "d424a7438f1b7da8938256f2cae9812a2b52c737d34f6026453ca4aa15f55b0f"


def _common_real_frequency() -> dict[str, object]:
    values = {"omega": [-1.0, 0.0, 1.0], "Gamma": [0.0, 0.1, 0.0]}
    return {**values, "sha256": sha256_bytes(canonical_json(values))}


def test_delta_iw_has_branch_safe_symmetry_causality_and_asymptotic():
    omega = np.array([-1.0e6, -3.0, -0.2, 0.2, 3.0, 1.0e6])
    values = delta_iw(omega, gamma=0.1, bandwidth=1.0)

    assert values.dtype == np.dtype(np.complex128)
    assert np.array_equal(values.real, np.zeros(omega.size))
    assert np.allclose(values[:3], np.conjugate(values[:2:-1]), rtol=0.0, atol=0.0)
    assert np.all(values[omega > 0.0].imag < 0.0)
    assert np.all(values[omega < 0.0].imag > 0.0)
    assert (values[-1] * (1j * omega[-1])).real == pytest.approx(
        0.05, rel=2.0e-4
    )


def test_delta_iw_agrees_with_independent_gauss_chebyshev_rule():
    omega = np.array([-7.0, -0.9, 0.13, 2.4], dtype=np.float64)
    gamma = 0.17
    bandwidth = 1.3
    count = 4096
    indices = np.arange(1, count + 1, dtype=np.float64)
    angles = indices * np.pi / (count + 1)
    nodes = np.cos(angles)
    weights = np.pi * np.sin(angles) ** 2 / (count + 1)
    quadrature = np.array(
        [
            gamma
            * bandwidth
            / np.pi
            * np.sum(weights / (1j * value - bandwidth * nodes))
            for value in omega
        ],
        dtype=np.complex128,
    )

    assert delta_iw(omega, gamma=gamma, bandwidth=bandwidth) == pytest.approx(
        quadrature, rel=2.0e-13, abs=2.0e-15
    )


@pytest.mark.parametrize("omega", [-5.7, -0.21, 0.19, 3.4])
def test_delta_iw_agrees_with_independent_high_precision_integral(omega):
    with mpmath.workdps(80):
        gamma = mpmath.mpf("0.1")
        bandwidth = mpmath.mpf("1.0")
        frequency = mpmath.mpf(str(omega))
        expected = (
            gamma
            / mpmath.pi
            * mpmath.quad(
                lambda energy: mpmath.sqrt(
                    1 - (energy / bandwidth) ** 2
                )
                / (1j * frequency - energy),
                [-bandwidth, 0, bandwidth],
            )
        )

    actual = delta_iw(
        np.array([omega], dtype=np.float64), gamma=0.1, bandwidth=1.0
    )[0]
    assert actual.real == pytest.approx(float(mpmath.re(expected)), abs=1.0e-15)
    assert actual.imag == pytest.approx(float(mpmath.im(expected)), rel=2.0e-14)


@pytest.mark.parametrize(
    ("omega", "gamma", "bandwidth"),
    [
        (np.array([0.0]), 0.1, 1.0),
        (np.array([np.inf]), 0.1, 1.0),
        (np.array([1.0], dtype=np.float32), 0.1, 1.0),
        (np.array([[1.0]], dtype=np.float64), 0.1, 1.0),
        (np.array([1.0]), True, 1.0),
        (np.array([1.0]), 0.1, -1.0),
    ],
)
def test_delta_iw_rejects_nonfermionic_or_non_float64_inputs(
    omega, gamma, bandwidth
):
    with pytest.raises((TypeError, ValueError)):
        delta_iw(omega, gamma=gamma, bandwidth=bandwidth)


def test_complex128_serialization_is_exact_ordered_and_hash_bound():
    values = np.array(
        [complex(1.0, -2.0), complex(-0.0, 0.25), complex(3.5, 0.0)],
        dtype=np.complex128,
    )
    split = serialize_complex128(values)

    assert list(split) == ["real", "imag", "sha256"]
    assert split["real"] == [1.0, -0.0, 3.5]
    assert split["imag"] == [-2.0, 0.25, 0.0]
    assert split["sha256"] == sha256_bytes(
        canonical_json({"real": split["real"], "imag": split["imag"]})
    )

    with pytest.raises(TypeError, match="complex128"):
        serialize_complex128(values.astype(np.complex64))
    with pytest.raises(ValueError, match="finite"):
        serialize_complex128(np.array([complex(np.inf, 0.0)], dtype=np.complex128))


def test_reported_tau_points_are_exact_mesh_nodes():
    assert reported_tau_indices(
        16.0, 4001, [0.0, 4.0, 8.0, 12.0, 16.0]
    ) == [0, 1000, 2000, 3000, 4000]

    with pytest.raises(ValueError, match="node"):
        reported_tau_indices(16.0, 4001, [0.101])
    with pytest.raises(ValueError):
        reported_tau_indices(16.0, 4001, [-4.0])
    with pytest.raises(TypeError):
        reported_tau_indices(16.0, True, [0.0])


def test_common_real_frequency_matches_schema_two_mps_bath_fixture():
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    bath.verify_bath_artifact(artifact)
    common = {
        "omega": artifact["payload"]["frequency_grid"],
        "Gamma": artifact["payload"]["target_continuum_hybridization"],
        "sha256": COMMON_SHA256,
    }
    assert common == _common_real_frequency()
    assert verify_common_real_frequency(common) is None

    for key, replacement in (
        ("omega", [-1.0, 0.1, 1.0]),
        ("Gamma", [0.0, 0.2, 0.0]),
        ("sha256", "1" * 64),
    ):
        changed = copy.deepcopy(common)
        changed[key] = replacement
        with pytest.raises(ValueError):
            verify_common_real_frequency(changed)
    changed = copy.deepcopy(common)
    changed["unknown"] = None
    with pytest.raises(ValueError):
        verify_common_real_frequency(changed)


class _Mesh:
    def __init__(self, omega: np.ndarray, beta: float):
        self._points = [1j * value for value in omega]
        self.beta = beta

    def __iter__(self):
        return iter(self._points)


class _Block:
    def __init__(self, omega: np.ndarray, beta: float):
        self.mesh = _Mesh(omega, beta)
        self.data = np.zeros((omega.size, 1, 1), dtype=np.complex128)


class _Blocks:
    indices = ("up", "down")

    def __init__(self, omega: np.ndarray, beta: float):
        self._blocks = {
            spin: _Block(omega, beta)
            for spin in self.indices
        }

    def __getitem__(self, spin: str) -> _Block:
        return self._blocks[spin]


class _Solver:
    def __init__(self, omega: np.ndarray, beta: float):
        self.G0_iw = _Blocks(omega, beta)


def _installation_payload(omega: np.ndarray) -> dict[str, object]:
    delta = delta_iw(omega, gamma=0.1, bandwidth=1.0)
    return {
        "model": {
            "D": 1.0,
            "Gamma": 0.1,
            "epsilon_d": -0.4,
            "mu": 0.0,
            "beta": 16.0,
        },
        "hybridization": {
            "dtype": "complex128",
            "n_iw": 8,
            "matsubara_omega": omega.tolist(),
            "delta_iw": serialize_complex128(delta),
            "common_real_frequency": _common_real_frequency(),
        },
        "meshes": {"n_tau": 33, "reported_tau": [0.0, 8.0, 16.0]},
    }


def _assert_installed_convention(solver, omega: np.ndarray) -> None:
    delta = delta_iw(omega, gamma=0.1, bandwidth=1.0)
    expected_inverse = 1j * omega + 0.0 - (-0.4) - delta
    double_counted_inverse = 1j * omega + 0.0 - 2.0 * (-0.4) - delta
    for spin in ("up", "down"):
        installed = np.asarray(solver.G0_iw[spin].data[:, 0, 0])
        assert installed == pytest.approx(1.0 / expected_inverse, rel=2.0e-14)
        assert 1.0 / installed == pytest.approx(expected_inverse, rel=2.0e-14)
        assert not np.allclose(1.0 / installed, double_counted_inverse)
    assert np.array_equal(solver.G0_iw["up"].data, solver.G0_iw["down"].data)


def test_install_g0_uses_exact_single_impurity_level_convention():
    omega = (2 * np.arange(-8, 8, dtype=np.float64) + 1) * np.pi / 16.0
    solver = _Solver(omega, 16.0)
    payload = _installation_payload(omega)

    install_g0(solver, payload)
    _assert_installed_convention(solver, omega)


def test_install_g0_with_locked_triqs_solver_when_available():
    Solver = pytest.importorskip("triqs_cthyb").Solver
    solver = Solver(
        beta=16.0,
        gf_struct=[("up", 1), ("down", 1)],
        n_iw=8,
        n_tau=33,
    )
    omega = np.array(
        [complex(point).imag for point in solver.G0_iw["up"].mesh],
        dtype=np.float64,
    )

    install_g0(solver, _installation_payload(omega))
    _assert_installed_convention(solver, omega)
