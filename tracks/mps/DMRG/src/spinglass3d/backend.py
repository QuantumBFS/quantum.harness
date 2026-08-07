"""Reference sampler backend protocol and resource telemetry."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import copy
import math
import resource
import sys
import time
from typing import Protocol, runtime_checkable

import numpy as np

from .model import EABonds, delta_energy, energy


@dataclass(frozen=True)
class BackendCase:
    spins: np.ndarray
    bonds: np.ndarray
    betas: np.ndarray
    seed: int

    def __post_init__(self) -> None:
        spins = np.asarray(self.spins)
        bonds = np.asarray(self.bonds)
        betas = np.asarray(self.betas, dtype=np.float64)
        if spins.ndim != 6:
            raise ValueError("spins must have shape (sample,temp,walker,L,L,L)")
        samples, temperatures, _, length_x, length_y, length_z = spins.shape[:6]
        if length_x != length_y or length_y != length_z:
            raise ValueError("backend spins must be cubic")
        if bonds.shape != (samples, length_x, length_x, length_x, 3):
            raise ValueError("backend bonds have the wrong shape")
        if betas.shape != (temperatures,) or np.any(betas <= 0.0):
            raise ValueError("backend betas have the wrong shape or values")
        if not np.all((spins == -1) | (spins == 1)) or not np.all(
            (bonds == -1) | (bonds == 1)
        ):
            raise ValueError("backend spins and bonds must be binary")
        owned_spins = spins.astype(np.int8, copy=True)
        owned_bonds = bonds.astype(np.int8, copy=True)
        owned_betas = betas.copy()
        for value in (owned_spins, owned_bonds, owned_betas):
            value.setflags(write=False)
        object.__setattr__(self, "spins", owned_spins)
        object.__setattr__(self, "bonds", owned_bonds)
        object.__setattr__(self, "betas", owned_betas)

    @classmethod
    def random(
        cls,
        *,
        length: int,
        temperatures: int,
        samples: int,
        walkers: int,
        seed: int,
    ) -> "BackendCase":
        if min(length, temperatures, samples, walkers) < 1:
            raise ValueError("backend dimensions must be positive")
        rng = np.random.default_rng(seed)
        spins = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(samples, temperatures, walkers, length, length, length),
        )
        bonds = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(samples, length, length, length, 3),
        )
        betas = np.linspace(0.35, 1.1, temperatures, dtype=np.float64)
        return cls(spins=spins, bonds=bonds, betas=betas, seed=seed)


@runtime_checkable
class SamplerBackend(Protocol):
    accepted_changes: int
    proposed_changes: int

    def sweeps(self, count: int) -> None: ...

    def measure(self) -> dict[str, np.ndarray]: ...

    def checkpoint_state(self) -> dict[str, object]: ...

    def resource_snapshot(self) -> dict[str, object]: ...


def _host_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


class NumpyReferenceBackend:
    def __init__(self, case: BackendCase) -> None:
        if not isinstance(case, BackendCase):
            raise TypeError("case must be BackendCase")
        self.case = case
        self.spins = case.spins.copy()
        self.rng = np.random.default_rng(case.seed + 1_000_003)
        self.accepted_changes = 0
        self.proposed_changes = 0

    def all_proposal_deltas(self) -> np.ndarray:
        result = np.empty_like(self.spins, dtype=np.int64)
        for sample in range(self.spins.shape[0]):
            bonds = EABonds(self.case.bonds[sample])
            for temperature in range(self.spins.shape[1]):
                for walker in range(self.spins.shape[2]):
                    state = self.spins[sample, temperature, walker]
                    for site in np.ndindex(state.shape):
                        result[(sample, temperature, walker) + site] = delta_energy(
                            state,
                            bonds,
                            site,
                        )
        return result

    def accept_decisions(self, uniforms: np.ndarray) -> np.ndarray:
        values = np.asarray(uniforms, dtype=np.float64)
        if values.shape != self.spins.shape or np.any(values <= 0.0) or np.any(values >= 1.0):
            raise ValueError("uniforms must lie strictly inside (0,1) with spin shape")
        deltas = self.all_proposal_deltas().astype(np.float64)
        beta_shape = (1, self.case.betas.size, 1, 1, 1, 1)
        log_ratio = -deltas * self.case.betas.reshape(beta_shape)
        return np.log(values) < np.minimum(0.0, log_ratio)

    def sweeps(self, count: int) -> None:
        if count < 0:
            raise ValueError("sweep count must be nonnegative")
        length = self.spins.shape[-1]
        n_sites = length**3
        for _ in range(count):
            for sample in range(self.spins.shape[0]):
                bonds = EABonds(self.case.bonds[sample])
                for temperature, beta in enumerate(self.case.betas):
                    for walker in range(self.spins.shape[2]):
                        state = self.spins[sample, temperature, walker]
                        for flat_site in self.rng.permutation(n_sites):
                            site = tuple(
                                int(value)
                                for value in np.unravel_index(flat_site, (length,) * 3)
                            )
                            difference = delta_energy(state, bonds, site)
                            self.proposed_changes += 1
                            if math.log(float(self.rng.random())) < min(
                                0.0,
                                -float(beta * difference),
                            ):
                                state[site] *= -1
                                self.accepted_changes += 1

    def measure(self) -> dict[str, np.ndarray]:
        result = np.empty(self.spins.shape[:3], dtype=np.int64)
        for sample in range(self.spins.shape[0]):
            bonds = EABonds(self.case.bonds[sample])
            for temperature in range(self.spins.shape[1]):
                for walker in range(self.spins.shape[2]):
                    result[sample, temperature, walker] = energy(
                        self.spins[sample, temperature, walker],
                        bonds,
                    )
        return {"energy": result}

    def checkpoint_state(self) -> dict[str, object]:
        return {
            "spins": self.spins.copy(),
            "rng_state": copy.deepcopy(self.rng.bit_generator.state),
            "accepted_changes": self.accepted_changes,
            "proposed_changes": self.proposed_changes,
        }

    def resource_snapshot(self) -> dict[str, object]:
        return {
            "backend": "numpy-reference",
            "host_rss_bytes": _host_rss_bytes(),
            "device_memory_bytes": 0,
            "float64_enabled": True,
        }


@dataclass(frozen=True)
class BenchmarkRecord:
    backend: str
    length: int
    temperatures: int
    samples: int
    walkers: int
    sweeps: int
    spin_proposals_per_second: float
    accepted_changes_per_second: float
    peak_host_memory_bytes: int
    peak_device_memory_bytes: int
    compile_seconds: float
    checkpoint_bytes: int
    elapsed_seconds: float
    provenance: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def checkpoint_nbytes(state: dict[str, object]) -> int:
    total = 0
    stack = list(state.values())
    while stack:
        value = stack.pop()
        if isinstance(value, np.ndarray):
            total += int(value.nbytes)
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, (int, float, bool)):
            total += 8
    return total
