"""Continuous eight-chain Metropolis sampling on spinor coordinates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MetropolisBatch:
    configurations: np.ndarray
    proposals: int
    accepted: int

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.proposals if self.proposals else 0.0


class SU2TangentMetropolis:
    """Persistent reversible Metropolis chains using SU(2) tangent moves."""

    def __init__(
        self,
        *,
        model: object,
        sector_index: int,
        seed: int,
        chains: int = 8,
        burn_in_sweeps: int = 1024,
        proposal_scale: float = 0.15,
    ) -> None:
        n_electrons = getattr(model, "n_electrons", None)
        if (
            isinstance(n_electrons, bool)
            or not isinstance(n_electrons, (int, np.integer))
            or int(n_electrons) <= 0
        ):
            raise ValueError("model.n_electrons must be a positive integer")
        if (
            isinstance(sector_index, bool)
            or not isinstance(sector_index, (int, np.integer))
            or not 0 <= int(sector_index) < 6
        ):
            raise ValueError("sector_index must be an integer from 0 through 5")
        for name, value, lower in (
            ("chains", chains, 1),
            ("burn_in_sweeps", burn_in_sweeps, 0),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, np.integer))
                or int(value) < lower
            ):
                qualifier = "positive" if lower else "non-negative"
                raise ValueError(f"{name} must be a {qualifier} integer")
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
            raise ValueError("seed must be an integer")
        if not np.isfinite(proposal_scale) or not 0.0 < proposal_scale <= np.pi:
            raise ValueError("proposal_scale must be finite and in (0, pi]")

        self.model = model
        self.sector_index = int(sector_index)
        self.chains = int(chains)
        self.burn_in_sweeps = int(burn_in_sweeps)
        self.proposal_scale = float(proposal_scale)
        self._rng = np.random.default_rng(int(seed))
        values = self._rng.normal(
            size=(self.chains, int(n_electrons), 2)
        ) + 1j * self._rng.normal(size=(self.chains, int(n_electrons), 2))
        self._states = values / np.linalg.norm(values, axis=-1, keepdims=True)
        self._current_amplitudes: np.ndarray | None = None
        self._burned_in = False

    def invalidate_amplitudes(self) -> None:
        """Force re-evaluation after the model parameters change."""

        self._current_amplitudes = None

    def _evaluate_selected(self, configs: np.ndarray) -> np.ndarray:
        amplitudes = np.asarray(
            self.model.amplitudes(configs), dtype=np.complex128
        )
        if amplitudes.shape != (configs.shape[0], 6):
            raise ValueError("model amplitudes must have shape (batch, 6)")
        return amplitudes[:, self.sector_index]

    def _ensure_current(self) -> None:
        if self._current_amplitudes is None:
            self._current_amplitudes = self._evaluate_selected(self._states)

    def _sweep(self) -> int:
        self._ensure_current()
        assert self._current_amplitudes is not None

        proposals = self._states.copy()
        particle_indices = self._rng.integers(
            0, self._states.shape[1], size=self.chains
        )
        rows = np.arange(self.chains)
        spinors = self._states[rows, particle_indices]
        tangent = np.stack(
            (-np.conjugate(spinors[:, 1]), np.conjugate(spinors[:, 0])),
            axis=1,
        )
        angles = self._rng.uniform(
            -self.proposal_scale, self.proposal_scale, size=self.chains
        )
        phases = self._rng.uniform(0.0, 2.0 * np.pi, size=self.chains)
        moved = (
            np.cos(angles)[:, None] * spinors
            + np.sin(angles)[:, None]
            * np.exp(1j * phases)[:, None]
            * tangent
        )
        moved /= np.linalg.norm(moved, axis=1, keepdims=True)
        proposals[rows, particle_indices] = moved

        proposed_amplitudes = self._evaluate_selected(proposals)
        current_absolute = np.abs(self._current_amplitudes)
        proposed_absolute = np.abs(proposed_amplitudes)
        current_valid = np.isfinite(current_absolute) & (current_absolute > 0.0)
        proposed_valid = np.isfinite(proposed_absolute) & (
            proposed_absolute > 0.0
        )
        log_ratio = np.full(self.chains, -np.inf, dtype=np.float64)
        both_valid = current_valid & proposed_valid
        log_ratio[both_valid] = 2.0 * (
            np.log(proposed_absolute[both_valid])
            - np.log(current_absolute[both_valid])
        )
        log_ratio[~current_valid & proposed_valid] = np.inf
        accepted = np.log(self._rng.random(self.chains)) < log_ratio
        self._states[accepted] = proposals[accepted]
        self._current_amplitudes[accepted] = proposed_amplitudes[accepted]
        return int(np.count_nonzero(accepted))

    def sample(self, *, batch_size: int) -> MetropolisBatch:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, (int, np.integer))
            or int(batch_size) <= 0
        ):
            raise ValueError("batch_size must be a positive integer")

        accepted = 0
        proposals = 0
        if not self._burned_in:
            for _ in range(self.burn_in_sweeps):
                accepted += self._sweep()
                proposals += self.chains
            self._burned_in = True

        collected: list[np.ndarray] = []
        while sum(item.shape[0] for item in collected) < int(batch_size):
            accepted += self._sweep()
            proposals += self.chains
            collected.append(self._states.copy())
        configurations = np.concatenate(collected, axis=0)[: int(batch_size)]
        return MetropolisBatch(
            configurations=configurations,
            proposals=proposals,
            accepted=accepted,
        )
