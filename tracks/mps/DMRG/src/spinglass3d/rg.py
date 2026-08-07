"""Incremental 3D majority-rule overlap-field renormalization."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np


Origin3D = tuple[int, int, int]
Site3D = tuple[int, int, int]


def _validated_origin(origin: Origin3D) -> Origin3D:
    if len(origin) != 3 or any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        for value in origin
    ):
        raise ValueError("origin must contain three integer offsets")
    result = tuple(int(value) for value in origin)
    if any(value < 0 or value >= 3 for value in result):
        raise ValueError("origin offsets must lie in {0,1,2}")
    return result


def _validated_q(q: np.ndarray, *, divisor: int = 3) -> np.ndarray:
    values = np.asarray(q)
    if (
        values.ndim != 3
        or values.shape[0] != values.shape[1]
        or values.shape[1] != values.shape[2]
    ):
        raise ValueError("q must have cubic shape (L, L, L)")
    if values.shape[0] < 3 or values.shape[0] % divisor:
        raise ValueError(f"q length must be divisible by {divisor}")
    if not np.all((values == -1) | (values == 1)):
        raise ValueError("q must contain only -1 and +1")
    return values.astype(np.int8, copy=False)


def _block_sums(q: np.ndarray, origin: Origin3D) -> np.ndarray:
    shifted = np.roll(q, shift=tuple(-value for value in origin), axis=(0, 1, 2))
    coarse_length = q.shape[0] // 3
    blocked = shifted.reshape(
        coarse_length,
        3,
        coarse_length,
        3,
        coarse_length,
        3,
    )
    return np.sum(blocked, axis=(1, 3, 5), dtype=np.int16)


def block_majority_3d(
    q: np.ndarray,
    origin: Origin3D = (0, 0, 0),
) -> np.ndarray:
    """Apply one periodic 3x3x3 majority block with a selected origin."""
    values = _validated_q(q)
    selected_origin = _validated_origin(origin)
    sums = _block_sums(values, selected_origin)
    if np.any(sums == 0):
        raise AssertionError("an odd 3x3x3 block cannot tie")
    return np.where(sums > 0, 1, -1).astype(np.int8)


@dataclass(frozen=True)
class RGLevelChange:
    level: int
    input_site: Site3D
    coarse_site: Site3D
    old_input: int
    old_sum: int
    new_sum: int
    old_coarse: int
    new_coarse: int

    @property
    def changed(self) -> bool:
        return self.old_coarse != self.new_coarse


@dataclass(frozen=True)
class RGProposal3D:
    site: Site3D
    old_spin: int
    new_spin: int
    level_changes: tuple[RGLevelChange, ...]
    final_site: Site3D
    final_changed: bool


def _read_only_view(array: np.ndarray) -> np.ndarray:
    view = array.view()
    view.setflags(write=False)
    return view


class MajorityRG3D:
    """Incremental one- or two-level majority cache for one overlap field."""

    def __init__(
        self,
        q: np.ndarray,
        block_size: int = 3,
        levels: int = 1,
        origin: Origin3D = (0, 0, 0),
    ) -> None:
        if block_size != 3:
            raise ValueError("only block_size=3 is supported")
        if isinstance(levels, (bool, np.bool_)) or levels not in (1, 2):
            raise ValueError("levels must be one or two")
        divisor = 3 ** int(levels)
        source = _validated_q(q, divisor=divisor).copy()
        self.block_size = 3
        self.levels = int(levels)
        self.origin = _validated_origin(origin)
        self.source_fingerprint = hashlib.sha256(source.tobytes()).hexdigest()
        self._fields: list[np.ndarray] = [source]
        self._sums: list[np.ndarray] = []
        for level in range(self.levels):
            level_origin = self.origin if level == 0 else (0, 0, 0)
            sums = _block_sums(self._fields[level], level_origin)
            if np.any(sums == 0):
                raise AssertionError("an odd 3x3x3 block cannot tie")
            coarse = np.where(sums > 0, 1, -1).astype(np.int8)
            self._sums.append(sums)
            self._fields.append(coarse)

    @property
    def q(self) -> np.ndarray:
        return _read_only_view(self._fields[0])

    @property
    def coarse(self) -> np.ndarray:
        return _read_only_view(self._fields[-1])

    @property
    def level_fields(self) -> tuple[np.ndarray, ...]:
        return tuple(_read_only_view(field) for field in self._fields)

    def _coarse_site(self, level: int, site: Site3D) -> Site3D:
        length = self._fields[level].shape[0]
        origin = self.origin if level == 0 else (0, 0, 0)
        return tuple(((site[axis] - origin[axis]) % length) // 3 for axis in range(3))

    def proposal(self, site: Site3D) -> RGProposal3D:
        if len(site) != 3 or any(
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, np.integer))
            for value in site
        ):
            raise ValueError("site must contain three integer coordinates")
        microscopic_site = tuple(int(value) for value in site)
        length = self._fields[0].shape[0]
        if any(value < 0 or value >= length for value in microscopic_site):
            raise ValueError("site lies outside q")

        current_site = microscopic_site
        current_old = int(self._fields[0][current_site])
        old_spin = current_old
        changes: list[RGLevelChange] = []
        for level in range(self.levels):
            coarse_site = self._coarse_site(level, current_site)
            old_sum = int(self._sums[level][coarse_site])
            new_sum = old_sum - 2 * current_old
            old_coarse = int(self._fields[level + 1][coarse_site])
            new_coarse = 1 if new_sum > 0 else -1
            change = RGLevelChange(
                level=level,
                input_site=current_site,
                coarse_site=coarse_site,
                old_input=current_old,
                old_sum=old_sum,
                new_sum=new_sum,
                old_coarse=old_coarse,
                new_coarse=new_coarse,
            )
            changes.append(change)
            if not change.changed:
                break
            current_site = coarse_site
            current_old = old_coarse

        final = changes[-1]
        return RGProposal3D(
            site=microscopic_site,
            old_spin=old_spin,
            new_spin=-old_spin,
            level_changes=tuple(changes),
            final_site=final.coarse_site,
            final_changed=final.changed,
        )

    def commit(self, proposal: RGProposal3D) -> None:
        if not isinstance(proposal, RGProposal3D):
            raise TypeError("proposal must be an RGProposal3D")
        if int(self._fields[0][proposal.site]) != proposal.old_spin:
            raise RuntimeError("stale RG proposal: microscopic spin changed")
        for change in proposal.level_changes:
            if (
                int(self._fields[change.level][change.input_site])
                != change.old_input
                or int(self._sums[change.level][change.coarse_site])
                != change.old_sum
                or int(self._fields[change.level + 1][change.coarse_site])
                != change.old_coarse
            ):
                raise RuntimeError("stale RG proposal: cached path changed")

        self._fields[0][proposal.site] = proposal.new_spin
        for change in proposal.level_changes:
            self._sums[change.level][change.coarse_site] = change.new_sum
            self._fields[change.level + 1][change.coarse_site] = change.new_coarse

    def assert_consistent(self) -> None:
        for level in range(self.levels):
            origin = self.origin if level == 0 else (0, 0, 0)
            expected_sums = _block_sums(self._fields[level], origin)
            expected_field = np.where(expected_sums > 0, 1, -1).astype(np.int8)
            np.testing.assert_array_equal(self._sums[level], expected_sums)
            np.testing.assert_array_equal(self._fields[level + 1], expected_field)
