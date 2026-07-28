from __future__ import annotations

from dataclasses import dataclass


def require_jax():
    try:
        import jax
        import jax.numpy as jnp
    except Exception as exc:
        raise RuntimeError(
            "Attempt 004 requires JAX/JAXLIB. Install dependencies from "
            "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt"
        ) from exc
    jax.config.update("jax_enable_x64", True)
    return jax, jnp


@dataclass(frozen=True)
class SystemConfig:
    name: str
    target: str
    hilbert_dim: int
    segments: int
    controls: int
    max_amplitude: float
    benchmark_rank: int

    @property
    def raw_dim(self) -> int:
        return self.segments * self.controls


@dataclass(frozen=True)
class OpenLoopConfig:
    steps: int
    learning_rate: float
    target_infidelity: float
    seed_scale: float


@dataclass(frozen=True)
class ClosedLoopConfig:
    query_budget: int
    target_infidelity: float
    initial_step: float


@dataclass(frozen=True)
class SweepConfig:
    systems: tuple[SystemConfig, ...]
    gaps: tuple[str, ...]
    shots_per_query: tuple[int, ...]
    seeds: tuple[int, ...]
    one_qubit_k: tuple[int, ...]
    two_qubit_k: tuple[int, ...]
    open_loop: OpenLoopConfig
    closed_loop: ClosedLoopConfig
    cpu_array_cores_per_task: int
    cpu_array_max_concurrent_tasks: int
    gpu_array_max_concurrent_tasks: int


ONE_QUBIT_X = SystemConfig("one_qubit_x", "X", 2, 8, 2, 0.8, 3)
TWO_QUBIT_CZ = SystemConfig("two_qubit_cz", "CZ", 4, 12, 4, 0.55, 15)


def default_smoke_sweep() -> SweepConfig:
    return SweepConfig(
        systems=(ONE_QUBIT_X, TWO_QUBIT_CZ),
        gaps=("small", "medium", "large"),
        shots_per_query=(128, 512, 2048),
        seeds=(0, 1),
        one_qubit_k=(0, 1, 2, 3, 4, 8, 16),
        two_qubit_k=(0, 3, 5, 8, 10, 15, 20, 24, 32, 48),
        open_loop=OpenLoopConfig(
            steps=80,
            learning_rate=0.045,
            target_infidelity=1e-4,
            seed_scale=0.03,
        ),
        closed_loop=ClosedLoopConfig(
            query_budget=120,
            target_infidelity=1e-3,
            initial_step=0.08,
        ),
        cpu_array_cores_per_task=4,
        cpu_array_max_concurrent_tasks=25,
        gpu_array_max_concurrent_tasks=1,
    )


def default_full_sweep() -> SweepConfig:
    cfg = default_smoke_sweep()
    return SweepConfig(
        systems=cfg.systems,
        gaps=cfg.gaps,
        shots_per_query=cfg.shots_per_query,
        seeds=tuple(range(8)),
        one_qubit_k=cfg.one_qubit_k,
        two_qubit_k=cfg.two_qubit_k,
        open_loop=OpenLoopConfig(
            steps=180,
            learning_rate=0.035,
            target_infidelity=1e-3,
            seed_scale=0.04,
        ),
        closed_loop=ClosedLoopConfig(
            query_budget=240,
            target_infidelity=1e-3,
            initial_step=0.08,
        ),
        cpu_array_cores_per_task=4,
        cpu_array_max_concurrent_tasks=25,
        gpu_array_max_concurrent_tasks=1,
    )
