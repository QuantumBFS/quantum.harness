import pathlib
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import hessian
import pulses
import systems


def test_attempt_004_dense_hessian_is_symmetric_and_hvp_matches():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=6)
    hess = hessian.dense_hessian(system, theta)
    vector = np.linspace(-0.2, 0.2, theta.size)
    hvp = hessian.hessian_vector_product(system, theta, vector)

    assert hess.shape == (theta.size, theta.size)
    assert np.max(np.abs(hess - hess.T)) < 1e-8
    assert np.linalg.norm(hess @ vector - hvp) / max(1.0, np.linalg.norm(hess @ vector)) < 1e-6


def test_attempt_004_eigenspace_is_orthonormal_and_ranked():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=7)
    hess = hessian.dense_hessian(system, theta)
    eig = hessian.leading_eigenspace(hess, k=3)

    assert eig.vectors.shape == (theta.size, 3)
    assert np.max(np.abs(eig.vectors.T @ eig.vectors - np.eye(3))) < 1e-8
    for index in range(3):
        residual = hess @ eig.vectors[:, index] - eig.values[index] * eig.vectors[:, index]
        assert np.linalg.norm(residual) < 1e-6


def test_attempt_004_effective_rank_and_curvature_cover_are_data_driven():
    eigenvalues = np.array([4.0, -2.0, 1.0, 0.25, 1e-10])

    assert hessian.effective_rank(eigenvalues, threshold=1e-8) == 4
    assert hessian.curvature_fraction(eigenvalues, k=0) == 0.0
    assert np.isclose(hessian.curvature_fraction(eigenvalues, k=2), 6.0 / 7.25)
    assert hessian.curvature_fraction(eigenvalues, k=99) == 1.0
    assert hessian.min_k_for_curvature(eigenvalues, 0.50) == 1
    assert hessian.min_k_for_curvature(eigenvalues, 0.90) == 3
    assert hessian.min_k_for_curvature(eigenvalues, 0.99) == 4
