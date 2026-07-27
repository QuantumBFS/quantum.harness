from __future__ import annotations

from typing import Callable

import numpy as np

from quantum_device import CONTROLS, RAW_DIM, SEGMENTS, gate_infidelity, propagate_error_pulse, target_gate


VISIBLE_RANK = 15


class AttemptModel:
    def __init__(
        self,
        raw_dim: int,
        visible_rank: int,
        raw_basis: np.ndarray,
        model_mixing: np.ndarray,
        model_hessian: np.ndarray,
        target: np.ndarray,
    ) -> None:
        self.raw_dim = raw_dim
        self.visible_rank = visible_rank
        self.raw_basis = raw_basis
        self.model_mixing = model_mixing
        self.model_hessian = model_hessian
        self.target = target


def build_model(seed: int = 3113) -> AttemptModel:
    rng = np.random.default_rng(seed)
    raw_basis = _visible_raw_basis(rng)
    model_mixing = raw_basis.reshape(SEGMENTS, CONTROLS, VISIBLE_RANK)
    target = target_gate("CZ")

    def visible_loss(coords: np.ndarray) -> float:
        params = raw_basis @ coords
        unitary = propagate_error_pulse(params, model_mixing, np.zeros(VISIBLE_RANK), target)
        return gate_infidelity(unitary, target)

    visible_hessian = finite_difference_hessian(
        visible_loss, np.zeros(VISIBLE_RANK), step=2.0e-4
    )
    model_hessian = raw_basis @ visible_hessian @ raw_basis.T
    model_hessian = 0.5 * (model_hessian + model_hessian.T)
    return AttemptModel(
        raw_dim=RAW_DIM,
        visible_rank=VISIBLE_RANK,
        raw_basis=raw_basis,
        model_mixing=model_mixing,
        model_hessian=model_hessian,
        target=target,
    )


def finite_difference_hessian(
    loss_fn: Callable[[np.ndarray], float], point: np.ndarray, step: float
) -> np.ndarray:
    point = np.asarray(point, dtype=float)
    dim = point.size
    hessian = np.zeros((dim, dim), dtype=float)
    base = float(loss_fn(point))
    for i in range(dim):
        ei = np.zeros(dim)
        ei[i] = step
        plus = float(loss_fn(point + ei))
        minus = float(loss_fn(point - ei))
        hessian[i, i] = (plus - 2.0 * base + minus) / (step * step)
        for j in range(i + 1, dim):
            ej = np.zeros(dim)
            ej[j] = step
            fpp = float(loss_fn(point + ei + ej))
            fpm = float(loss_fn(point + ei - ej))
            fmp = float(loss_fn(point - ei + ej))
            fmm = float(loss_fn(point - ei - ej))
            value = (fpp - fpm - fmp + fmm) / (4.0 * step * step)
            hessian[i, j] = value
            hessian[j, i] = value
    return 0.5 * (hessian + hessian.T)


def top_subspace(hessian: np.ndarray, k: int) -> np.ndarray:
    hessian = np.asarray(hessian, dtype=float)
    if k < 0 or k > hessian.shape[0]:
        raise ValueError("k must be between 0 and the Hessian dimension")
    if k == 0:
        return np.zeros((hessian.shape[0], 0))
    values, vectors = np.linalg.eigh(hessian)
    order = np.argsort(values)[::-1]
    return vectors[:, order[:k]]


def random_subspace(raw_dim: int, k: int, seed: int) -> np.ndarray:
    if k < 0 or k > raw_dim:
        raise ValueError("k must be between 0 and raw_dim")
    if k == 0:
        return np.zeros((raw_dim, 0))
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.normal(size=(raw_dim, k)))
    return q[:, :k]


def _visible_raw_basis(rng: np.random.Generator) -> np.ndarray:
    q, _ = np.linalg.qr(rng.normal(size=(RAW_DIM, RAW_DIM)))
    return q[:, :VISIBLE_RANK]
