from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pulses import clip_pulse


@dataclass(frozen=True)
class ProbeConfig:
    direction_count: int
    append_count: int
    step: float
    repeats: int = 1
    min_positive_curvature: float = 0.0


@dataclass(frozen=True)
class ProbeResult:
    basis: np.ndarray
    curvatures: np.ndarray
    query_count: int
    shot_count: int
    selected_count: int
    metadata: dict


def _as_basis(matrix, raw_dim: int) -> np.ndarray:
    basis = np.asarray(matrix, dtype=float)
    if basis.size == 0:
        return np.zeros((raw_dim, 0), dtype=float)
    if basis.ndim != 2 or basis.shape[0] != raw_dim:
        raise ValueError(f"basis must have shape ({raw_dim}, k)")
    return basis


def orthonormalize_against(
    existing_basis,
    candidate_basis,
    tolerance: float = 1e-10,
) -> np.ndarray:
    candidates = np.asarray(candidate_basis, dtype=float)
    if candidates.ndim != 2:
        raise ValueError("candidate_basis must be a matrix")
    raw_dim = candidates.shape[0]
    existing = _as_basis(existing_basis, raw_dim)
    vectors = []
    for column in range(candidates.shape[1]):
        vector = candidates[:, column].astype(float)
        if existing.shape[1]:
            vector = vector - existing @ (existing.T @ vector)
        for accepted in vectors:
            vector = vector - accepted * float(accepted @ vector)
        norm = float(np.linalg.norm(vector))
        if norm > tolerance:
            vectors.append(vector / norm)
    if not vectors:
        return np.zeros((raw_dim, 0), dtype=float)
    return np.column_stack(vectors)


def random_residual_directions(raw_dim: int, existing_basis, count: int, seed: int) -> np.ndarray:
    if raw_dim <= 0:
        raise ValueError("raw_dim must be positive")
    if count <= 0:
        return np.zeros((raw_dim, 0), dtype=float)
    existing = _as_basis(existing_basis, raw_dim)
    residual_dim = max(0, raw_dim - existing.shape[1])
    draw_count = min(int(count), residual_dim)
    if draw_count == 0:
        return np.zeros((raw_dim, 0), dtype=float)
    rng = np.random.default_rng(seed)
    candidates = rng.normal(size=(raw_dim, max(draw_count, count)))
    return orthonormalize_against(existing, candidates)[:, :draw_count]


def _validate_probe_config(cfg: ProbeConfig) -> None:
    if cfg.direction_count < 0:
        raise ValueError("direction_count must be non-negative")
    if cfg.append_count < 0:
        raise ValueError("append_count must be non-negative")
    if cfg.step <= 0.0:
        raise ValueError("step must be positive")
    if cfg.repeats <= 0:
        raise ValueError("repeats must be positive")


def estimate_device_subspace(
    oracle,
    system_config,
    center_theta,
    existing_basis,
    shots: int,
    seed: int,
    cfg: ProbeConfig,
    on_query=None,
) -> ProbeResult:
    _validate_probe_config(cfg)
    if shots <= 0:
        raise ValueError("shots must be positive")
    raw_dim = system_config.raw_dim
    center = clip_pulse(np.asarray(center_theta, dtype=float), system_config)
    existing = _as_basis(existing_basis, raw_dim)
    query_start = int(getattr(oracle, "query_count", 0))
    shot_start = int(getattr(oracle, "shot_count", 0))
    directions = random_residual_directions(raw_dim, existing, cfg.direction_count, seed)

    center_value = float(oracle.query(center, shots=shots))
    if on_query is not None:
        on_query(center)

    curvatures = []
    for column in range(directions.shape[1]):
        direction = directions[:, column]
        plus_values = []
        minus_values = []
        for _repeat in range(cfg.repeats):
            plus = clip_pulse(center + cfg.step * direction, system_config)
            minus = clip_pulse(center - cfg.step * direction, system_config)
            plus_values.append(float(oracle.query(plus, shots=shots)))
            if on_query is not None:
                on_query(plus)
            minus_values.append(float(oracle.query(minus, shots=shots)))
            if on_query is not None:
                on_query(minus)
        curvature = (
            float(np.mean(plus_values)) + float(np.mean(minus_values)) - 2.0 * center_value
        ) / (cfg.step**2)
        curvatures.append(curvature)

    curvatures_array = np.asarray(curvatures, dtype=float)
    order = np.argsort(curvatures_array)[::-1]
    selected_columns = [
        int(index)
        for index in order
        if curvatures_array[index] >= cfg.min_positive_curvature
    ][: cfg.append_count]
    selected = (
        directions[:, selected_columns]
        if selected_columns
        else np.zeros((raw_dim, 0), dtype=float)
    )
    selected = orthonormalize_against(existing, selected)
    query_count = int(getattr(oracle, "query_count", 0)) - query_start
    shot_count = int(getattr(oracle, "shot_count", 0)) - shot_start
    return ProbeResult(
        basis=selected,
        curvatures=curvatures_array,
        query_count=query_count,
        shot_count=shot_count,
        selected_count=selected.shape[1],
        metadata={
            "direction_count": directions.shape[1],
            "append_count": cfg.append_count,
            "selected_indices": selected_columns[: selected.shape[1]],
            "step": cfg.step,
            "repeats": cfg.repeats,
        },
    )
