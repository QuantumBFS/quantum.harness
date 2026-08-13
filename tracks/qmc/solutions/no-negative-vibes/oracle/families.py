"""Structured random generators for candidate matrix families."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FamilyCase:
    family: str
    shape: tuple[int, int]
    p: int | None = None
    q: int | None = None
    prior_status: str = "candidate"


_CASES = {
    "so3": FamilyCase("so", (3, 3), prior_status="known_nonnegative"),
    "o11": FamilyCase("o_pq", (2, 2), 1, 1, "known_nonnegative"),
    "o22": FamilyCase("o_pq", (4, 4), 2, 2, "known_nonnegative"),
    "sl2": FamilyCase("sl_real", (2, 2), prior_status="known_counterexample"),
    "sl3": FamilyCase("sl_real", (3, 3), prior_status="candidate"),
    "sp2": FamilyCase("sp_real", (2, 2), prior_status="known_counterexample"),
    "sp4": FamilyCase("sp_real", (4, 4), prior_status="known_counterexample"),
    "u2": FamilyCase("u_pq", (2, 2), 2, 0, "complex_phase"),
    "u11": FamilyCase("u_pq", (2, 2), 1, 1, "complex_phase"),
    "su2": FamilyCase("su_pq", (2, 2), 2, 0, "known_nonnegative"),
    "su3": FamilyCase("su_pq", (3, 3), 3, 0, "known_counterexample"),
    "su11": FamilyCase("su_pq", (2, 2), 1, 1, "known_counterexample"),
    "su21": FamilyCase("su_pq", (3, 3), 2, 1, "known_counterexample"),
    "usp2": FamilyCase("usp", (2, 2), prior_status="known_nonnegative"),
    "usp4": FamilyCase("usp", (4, 4), prior_status="known_nonnegative"),
}


def available_cases() -> dict[str, FamilyCase]:
    return dict(_CASES)


def _metric(p: int, q: int) -> np.ndarray:
    return np.diag([1.0] * p + [-1.0] * q)


def _symplectic_form(size: int) -> np.ndarray:
    half = size // 2
    identity = np.eye(half)
    return np.block([[np.zeros_like(identity), identity], [-identity, np.zeros_like(identity)]])


def _real_random(rng: np.random.Generator, size: int) -> np.ndarray:
    return rng.standard_normal((size, size)) / np.sqrt(size)


def _complex_random(rng: np.random.Generator, size: int) -> np.ndarray:
    real = rng.standard_normal((size, size))
    imag = rng.standard_normal((size, size))
    return (real + 1j * imag) / np.sqrt(2.0 * size)


def random_generator(
    case: str,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    spec = _CASES[case]
    size = spec.shape[0]

    if spec.family == "so":
        raw = _real_random(rng, size)
        generator = 0.5 * (raw - raw.T)
    elif spec.family == "o_pq":
        raw = _real_random(rng, size)
        eta = _metric(spec.p or 0, spec.q or 0)
        generator = 0.5 * (raw - eta @ raw.T @ eta)
    elif spec.family == "sl_real":
        raw = _real_random(rng, size)
        generator = raw - np.trace(raw) * np.eye(size) / size
    elif spec.family == "sp_real":
        raw = _real_random(rng, size)
        symmetric = 0.5 * (raw + raw.T)
        generator = _symplectic_form(size) @ symmetric
    elif spec.family in {"u_pq", "su_pq"}:
        raw = _complex_random(rng, size)
        antihermitian = 0.5 * (raw - raw.conj().T)
        eta = _metric(spec.p or 0, spec.q or 0)
        generator = eta @ antihermitian
        if spec.family == "su_pq":
            generator = generator - np.trace(generator) * np.eye(size) / size
    elif spec.family == "usp":
        half = size // 2
        raw_a = _complex_random(rng, half)
        block_a = 0.5 * (raw_a - raw_a.conj().T)
        raw_b = _complex_random(rng, half)
        block_b = 0.5 * (raw_b + raw_b.T)
        generator = np.block(
            [[block_a, block_b], [-block_b.conj(), block_a.conj()]]
        )
    else:
        raise ValueError(f"unsupported family: {spec.family}")

    return scale * generator


def structure_residual(case: str, generator: np.ndarray) -> float:
    spec = _CASES[case]
    matrix = np.asarray(generator)
    scale = max(1.0, float(np.linalg.norm(matrix)))
    residuals: list[float] = []

    if spec.family == "so":
        residuals.append(float(np.linalg.norm(matrix.T + matrix)))
    elif spec.family == "o_pq":
        eta = _metric(spec.p or 0, spec.q or 0)
        residuals.append(float(np.linalg.norm(matrix.T @ eta + eta @ matrix)))
    elif spec.family == "sl_real":
        residuals.append(abs(complex(np.trace(matrix))))
        residuals.append(float(np.linalg.norm(matrix.imag)) if np.iscomplexobj(matrix) else 0.0)
    elif spec.family == "sp_real":
        form = _symplectic_form(matrix.shape[0])
        residuals.append(float(np.linalg.norm(matrix.T @ form + form @ matrix)))
        residuals.append(float(np.linalg.norm(matrix.imag)) if np.iscomplexobj(matrix) else 0.0)
    elif spec.family in {"u_pq", "su_pq"}:
        eta = _metric(spec.p or 0, spec.q or 0)
        residuals.append(
            float(np.linalg.norm(matrix.conj().T @ eta + eta @ matrix))
        )
        if spec.family == "su_pq":
            residuals.append(abs(complex(np.trace(matrix))))
    elif spec.family == "usp":
        form = _symplectic_form(matrix.shape[0])
        residuals.append(float(np.linalg.norm(matrix.conj().T + matrix)))
        residuals.append(float(np.linalg.norm(matrix.T @ form + form @ matrix)))
    else:
        raise ValueError(f"unsupported family: {spec.family}")

    return max(residuals, default=0.0) / scale
