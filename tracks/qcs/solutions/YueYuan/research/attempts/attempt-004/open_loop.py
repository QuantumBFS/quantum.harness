from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import OpenLoopConfig, require_jax
from dynamics import gate_infidelity, propagator
from pulses import clip_pulse


jax, jnp = require_jax()


@dataclass(frozen=True)
class OpenLoopResult:
    theta: np.ndarray
    final_infidelity: float
    history: list[dict[str, float]]
    final_unitary: np.ndarray


def finite_difference_gradient(loss_fn, theta: np.ndarray, step: float) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    gradient = np.zeros_like(theta)
    for index in range(theta.size):
        basis = np.zeros_like(theta)
        basis[index] = step
        gradient[index] = (loss_fn(theta + basis) - loss_fn(theta - basis)) / (2.0 * step)
    return gradient


def optimize_model_pulse(system, start_theta: np.ndarray, cfg: OpenLoopConfig) -> OpenLoopResult:
    theta = jnp.asarray(start_theta, dtype=jnp.float64)
    loss_fn = lambda candidate: gate_infidelity(candidate, system)
    grad_fn = jax.grad(loss_fn)
    first_moment = jnp.zeros_like(theta)
    second_moment = jnp.zeros_like(theta)
    beta1 = 0.9
    beta2 = 0.999
    epsilon = 1e-8
    history: list[dict[str, float]] = []

    for step in range(1, cfg.steps + 1):
        loss = loss_fn(theta)
        gradient = grad_fn(theta)
        grad_norm = jnp.linalg.norm(gradient)
        history.append(
            {"step": float(step), "loss": float(loss), "grad_norm": float(grad_norm)}
        )
        if float(loss) <= cfg.target_infidelity:
            break

        first_moment = beta1 * first_moment + (1.0 - beta1) * gradient
        second_moment = beta2 * second_moment + (1.0 - beta2) * (gradient * gradient)
        first_hat = first_moment / (1.0 - beta1**step)
        second_hat = second_moment / (1.0 - beta2**step)
        theta = theta - cfg.learning_rate * first_hat / (jnp.sqrt(second_hat) + epsilon)
        theta = jnp.asarray(clip_pulse(np.asarray(theta), system.config), dtype=jnp.float64)

    final = float(loss_fn(theta))
    return OpenLoopResult(
        theta=np.asarray(theta),
        final_infidelity=final,
        history=history,
        final_unitary=np.asarray(propagator(theta, system)),
    )
