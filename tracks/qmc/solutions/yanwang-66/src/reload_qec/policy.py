"""Explicit loss/reload state machine and causal policy decisions."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from .config import PolicyConfig


class StateError(RuntimeError):
    """Raised on an illegal carrier-state transition."""


class CarrierState(IntEnum):
    ACTIVE = 0
    LOST_UNDETECTED = 1
    LOST_DETECTED = 2
    RELOADING = 3


@dataclass(frozen=True)
class CompletionBatch:
    succeeded: tuple[int, ...]
    failed: tuple[int, ...]


class PolicyMachine:
    def __init__(self, n_sites: int, policy: PolicyConfig, delay_rounds: int):
        if n_sites <= 0 or delay_rounds < 0:
            raise ValueError("n_sites must be positive and delay non-negative")
        self.n_sites = n_sites
        self.policy = policy
        self.delay_rounds = delay_rounds
        self.states = [CarrierState.ACTIVE] * n_sites
        self.reload_due: list[int | None] = [None] * n_sites

    def missing_snapshot(self) -> tuple[int, ...]:
        return tuple(int(state != CarrierState.ACTIVE) for state in self.states)

    def complete_due(
        self, boundary: int, succeeds: Callable[[int], bool]
    ) -> CompletionBatch:
        completed: list[int] = []
        failed: list[int] = []
        for site_id, due in enumerate(self.reload_due):
            if due != boundary:
                continue
            if self.states[site_id] != CarrierState.RELOADING:
                raise StateError(f"site {site_id} has due completion outside RELOADING")
            self.reload_due[site_id] = None
            if succeeds(site_id):
                self.states[site_id] = CarrierState.ACTIVE
                completed.append(site_id)
            else:
                self.states[site_id] = CarrierState.LOST_DETECTED
                failed.append(site_id)
        return CompletionBatch(tuple(completed), tuple(failed))

    def lose(self, site_id: int) -> None:
        self._validate_site(site_id)
        if self.states[site_id] != CarrierState.ACTIVE:
            raise StateError(f"site {site_id} cannot be lost from {self.states[site_id].name}")
        self.states[site_id] = CarrierState.LOST_UNDETECTED

    def reveal_losses(self) -> tuple[int, ...]:
        revealed = []
        for site_id, state in enumerate(self.states):
            if state == CarrierState.LOST_UNDETECTED:
                self.states[site_id] = CarrierState.LOST_DETECTED
                revealed.append(site_id)
        return tuple(revealed)

    def decide_and_request(self, round_index: int) -> tuple[int, ...]:
        detected = [
            site_id
            for site_id, state in enumerate(self.states)
            if state == CarrierState.LOST_DETECTED
        ]
        if not detected or not self._should_request(round_index, len(detected)):
            return ()
        due = round_index + self.delay_rounds + 1
        for site_id in detected:
            if self.reload_due[site_id] is not None:
                raise StateError(f"duplicate reload request for site {site_id}")
            self.states[site_id] = CarrierState.RELOADING
            self.reload_due[site_id] = due
        return tuple(detected)

    def _should_request(self, round_index: int, detected_count: int) -> bool:
        if self.policy.name == "none":
            return False
        if self.policy.name == "immediate":
            return True
        if self.policy.name == "periodic":
            assert self.policy.interval is not None
            return (round_index + 1) % self.policy.interval == 0
        if self.policy.name == "threshold":
            assert self.policy.fraction is not None
            return detected_count >= math.ceil(self.policy.fraction * self.n_sites)
        raise StateError(f"unsupported policy {self.policy.name!r}")

    def _validate_site(self, site_id: int) -> None:
        if not 0 <= site_id < self.n_sites:
            raise StateError(f"site {site_id} outside [0,{self.n_sites})")
