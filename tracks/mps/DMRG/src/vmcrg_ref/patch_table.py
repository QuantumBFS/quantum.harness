"""Exact 512-state compilation and periodic local caches for 3x3 patches."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .mps_patch import PatchMPS
from .symmetries import PATCH_COORDINATES


def decode_patch(pattern_id: int) -> np.ndarray:
    if not 0 <= int(pattern_id) < 512:
        raise ValueError("pattern_id must lie in [0, 512)")
    bits = (int(pattern_id) >> np.arange(9, dtype=np.int64)) & 1
    return (2 * bits - 1).astype(np.int8)


def encode_patch(patch: np.ndarray) -> int:
    values = np.asarray(patch, dtype=np.int8)
    if values.shape != (9,) or not np.all((values == -1) | (values == 1)):
        raise ValueError("patch must contain nine -1/+1 spins")
    bits = ((values + 1) // 2).astype(np.int64)
    return int(np.sum(bits << np.arange(9, dtype=np.int64), dtype=np.int64))


def enumerate_patches() -> np.ndarray:
    pattern_ids = np.arange(512, dtype=np.int64)[:, None]
    bits = (pattern_ids >> np.arange(9, dtype=np.int64)[None, :]) & 1
    return (2 * bits - 1).astype(np.int8)


@dataclass(frozen=True)
class PatchLookupTable:
    values: np.ndarray
    uncentered_mean: float
    chi: int
    symmetrized: bool

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=np.float64)
        if values.shape != (512,) or not np.all(np.isfinite(values)):
            raise ValueError("lookup values must be 512 finite numbers")
        object.__setattr__(self, "values", values.copy())

    @classmethod
    def from_model(
        cls,
        model: PatchMPS,
        symmetrize: bool | None = None,
    ) -> "PatchLookupTable":
        enabled = model.symmetrize if symmetrize is None else bool(symmetrize)
        uncentered = model.symmetric_values(
            enumerate_patches(), symmetrize=enabled
        )
        mean = float(uncentered.mean())
        centered = uncentered - mean
        centered -= centered.mean()
        return cls(centered, mean, model.chi, enabled)


class PatchGeometry:
    def __init__(self, length: int) -> None:
        if length < 3:
            raise ValueError("3x3 periodic patches require length >= 3")
        self.length = int(length)
        self.n_sites = self.length * self.length
        self.patch_sites = np.empty((self.n_sites, 9), dtype=np.int32)
        reverse_centers = [[] for _ in range(self.n_sites)]
        reverse_bits = [[] for _ in range(self.n_sites)]
        for cx in range(self.length):
            for cy in range(self.length):
                center = cx * self.length + cy
                for bit, (dx, dy) in enumerate(PATCH_COORDINATES):
                    x = (cx + dx) % self.length
                    y = (cy + dy) % self.length
                    site = x * self.length + y
                    self.patch_sites[center, bit] = site
                    reverse_centers[site].append(center)
                    reverse_bits[site].append(bit)
        if any(len(entries) != 9 for entries in reverse_centers):
            raise AssertionError("each coarse site must affect exactly nine patches")
        self.reverse_centers = np.asarray(reverse_centers, dtype=np.int32)
        self.reverse_bits = np.asarray(reverse_bits, dtype=np.int8)

    def pattern_ids(self, spins: np.ndarray) -> np.ndarray:
        values = np.asarray(spins, dtype=np.int8)
        if values.shape != (self.length, self.length):
            raise ValueError("spin array has the wrong shape")
        if not np.all((values == -1) | (values == 1)):
            raise ValueError("spins must contain only -1 and +1")
        flat = values.reshape(-1)
        bits = ((flat[self.patch_sites] + 1) // 2).astype(np.int64)
        return np.sum(
            bits << np.arange(9, dtype=np.int64)[None, :],
            axis=1,
            dtype=np.int64,
        ).reshape(self.length, self.length)


@dataclass(frozen=True)
class PatchEnergyProposal:
    x: int
    y: int
    old_spin: int
    centers: np.ndarray
    old_ids: np.ndarray
    new_ids: np.ndarray
    new_values: np.ndarray
    delta_energy: float


class PatchEnergyCache:
    """Cache each patch id/value so a spin flip touches only nine entries."""

    def __init__(self, spins: np.ndarray, lookup: PatchLookupTable) -> None:
        values = np.asarray(spins, dtype=np.int8)
        if values.ndim != 2 or values.shape[0] != values.shape[1]:
            raise ValueError("spins must be a square array")
        self.spins = values
        self.lookup = lookup
        self.geometry = PatchGeometry(values.shape[0])
        self.pattern_ids = self.geometry.pattern_ids(values)
        self.values = self.lookup.values[self.pattern_ids]
        self.histogram = np.bincount(self.pattern_ids.reshape(-1), minlength=512).astype(
            np.int64
        )

    @property
    def energy(self) -> float:
        return float(self.values.sum())

    def full_energy(self, spins: np.ndarray) -> float:
        pattern_ids = self.geometry.pattern_ids(spins)
        return float(self.lookup.values[pattern_ids].sum())

    def proposal(self, x: int, y: int) -> PatchEnergyProposal:
        length = self.geometry.length
        x %= length
        y %= length
        old_spin = int(self.spins[x, y])
        site = x * length + y
        centers = self.geometry.reverse_centers[site].copy()
        bit_positions = self.geometry.reverse_bits[site]
        flat_ids = self.pattern_ids.reshape(-1)
        old_ids = flat_ids[centers].copy()
        new_ids = old_ids ^ (1 << bit_positions.astype(np.int64))
        new_values = self.lookup.values[new_ids]
        old_values = self.values.reshape(-1)[centers]
        return PatchEnergyProposal(
            x=x,
            y=y,
            old_spin=old_spin,
            centers=centers,
            old_ids=old_ids,
            new_ids=new_ids,
            new_values=new_values,
            delta_energy=float((new_values - old_values).sum()),
        )

    def commit(self, proposal: PatchEnergyProposal) -> None:
        if int(self.spins[proposal.x, proposal.y]) != proposal.old_spin:
            raise AssertionError("spin changed before patch-cache commit")
        flat_ids = self.pattern_ids.reshape(-1)
        flat_values = self.values.reshape(-1)
        if not np.array_equal(flat_ids[proposal.centers], proposal.old_ids):
            raise AssertionError("patch ids changed before proposal commit")
        for old_id, new_id in zip(proposal.old_ids, proposal.new_ids):
            self.histogram[int(old_id)] -= 1
            self.histogram[int(new_id)] += 1
        flat_ids[proposal.centers] = proposal.new_ids
        flat_values[proposal.centers] = proposal.new_values

    def refresh_lookup(self, lookup: PatchLookupTable) -> None:
        self.lookup = lookup
        self.values[:] = lookup.values[self.pattern_ids]

    def assert_consistent(self) -> None:
        expected_ids = self.geometry.pattern_ids(self.spins)
        np.testing.assert_array_equal(self.pattern_ids, expected_ids)
        np.testing.assert_allclose(
            self.values, self.lookup.values[expected_ids], atol=1e-12, rtol=0.0
        )
        expected_histogram = np.bincount(expected_ids.reshape(-1), minlength=512)
        np.testing.assert_array_equal(self.histogram, expected_histogram)
        if abs(self.energy - self.full_energy(self.spins)) > 1e-12:
            raise AssertionError("cached patch energy drifted from full recomputation")
