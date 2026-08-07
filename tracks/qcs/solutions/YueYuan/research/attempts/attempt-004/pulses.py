from __future__ import annotations

import numpy as np

from config import SystemConfig


def initial_pulse(config: SystemConfig, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.normal(scale=0.05, size=config.raw_dim)
    return clip_pulse(raw, config)


def zero_pulse(config: SystemConfig) -> np.ndarray:
    return np.zeros(config.raw_dim, dtype=float)


def clip_pulse(theta: np.ndarray, config: SystemConfig) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    if theta.shape != (config.raw_dim,):
        raise ValueError(f"pulse must have shape ({config.raw_dim},)")
    return np.clip(theta, -config.max_amplitude, config.max_amplitude)


def as_segments(theta, config: SystemConfig):
    return theta.reshape((config.segments, config.controls))
