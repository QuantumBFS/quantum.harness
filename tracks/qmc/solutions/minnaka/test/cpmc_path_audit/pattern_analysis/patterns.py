"""Auxiliary-field mask decoding, lattice symmetries, and time features."""

from __future__ import annotations

from itertools import product
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


SITE_X = np.array([0, 1, 0, 1], dtype=np.int8)
SITE_Y = np.array([0, 0, 1, 1], dtype=np.int8)


def decode_masks(
    config_ids: np.ndarray, slices: int, sites: int
) -> np.ndarray:
    """Decode chronological config bits into masks whose bit i is site i."""

    ids = np.asarray(config_ids, dtype=np.uint64)
    if slices <= 0 or sites <= 0 or slices * sites > 64:
        raise ValueError("invalid slices/sites for uint64 config ids")
    masks = np.zeros((len(ids), slices), dtype=np.uint64)
    site_mask = (1 << sites) - 1
    for slice_index in range(slices):
        shift = (slices - 1 - slice_index) * sites
        chronological = (ids >> np.uint64(shift)) & np.uint64(site_mask)
        converted = np.zeros(len(ids), dtype=np.uint64)
        for site in range(sites):
            bit = (chronological >> np.uint64(sites - 1 - site)) & 1
            converted |= bit << np.uint64(site)
        masks[:, slice_index] = converted
    if sites <= 8:
        return masks.astype(np.uint8)
    if sites <= 16:
        return masks.astype(np.uint16)
    if sites <= 32:
        return masks.astype(np.uint32)
    return masks


def mask_class(mask: int) -> str:
    """Return one exact class for a four-site square-lattice mask."""

    if mask < 0 or mask >= 16:
        raise ValueError("2x2 mask must lie in [0,15]")
    if mask == 0:
        return "uniform_minus"
    if mask == 15:
        return "uniform_plus"
    count = mask.bit_count()
    if count == 1:
        return f"one_defect_plus_s{(mask & -mask).bit_length() - 1}"
    if count == 3:
        missing = ((~mask) & 0xF)
        return f"one_defect_minus_s{(missing & -missing).bit_length() - 1}"
    exact = {
        0b1001: "neel_plus",
        0b0110: "neel_minus",
        0b0101: "x_stripe_plus",
        0b1010: "x_stripe_minus",
        0b0011: "y_stripe_plus",
        0b1100: "y_stripe_minus",
    }
    return exact[mask]


def mask_family(mask: int) -> str:
    label = mask_class(mask)
    if label.startswith("one_defect"):
        return "one_defect"
    if label.startswith("uniform"):
        return "uniform"
    if label.startswith("neel"):
        return "neel"
    if label.startswith("x_stripe"):
        return "x_stripe"
    return "y_stripe"


def spatial_components(mask: int) -> dict[str, int]:
    """Return the four real 2x2 Fourier amplitudes."""

    if mask < 0 or mask >= 16:
        raise ValueError("2x2 mask must lie in [0,15]")
    field = np.array(
        [1 if ((mask >> site) & 1) else -1 for site in range(4)],
        dtype=np.int8,
    )
    staggered_sign = np.where((SITE_X + SITE_Y) % 2 == 0, 1, -1)
    x_sign = np.where(SITE_X == 0, 1, -1)
    y_sign = np.where(SITE_Y == 0, 1, -1)
    return {
        "uniform": int(field.sum()),
        "staggered": int((field * staggered_sign).sum()),
        "x_stripe": int((field * x_sign).sum()),
        "y_stripe": int((field * y_sign).sum()),
    }


def site_permutations_2x2() -> tuple[tuple[int, ...], ...]:
    """Return unique translations and D4 operations as old-to-new maps."""

    def operations(x: int, y: int) -> tuple[tuple[int, int], ...]:
        return (
            (x, y),
            (-y, x),
            (-x, -y),
            (y, -x),
            (-x, y),
            (x, -y),
            (y, x),
            (-y, -x),
        )

    permutations = set()
    for operation_index in range(8):
        for tx, ty in product(range(2), repeat=2):
            permutation = []
            for old_site in range(4):
                x = old_site % 2
                y = old_site // 2
                ox, oy = operations(x, y)[operation_index]
                nx = (ox + tx) % 2
                ny = (oy + ty) % 2
                permutation.append(ny * 2 + nx)
            permutations.add(tuple(permutation))
    return tuple(sorted(permutations))


def trial_preserving_permutations_2x2(
    trial: str,
) -> tuple[tuple[int, ...], ...]:
    """Return the spatial subgroup that preserves the trial's ordering axis."""

    reference_orbits = {
        "rhf_x": {0b0101, 0b1010},
        "rhf_y": {0b0011, 0b1100},
        "uhf": {0b1001, 0b0110},
    }
    if trial not in reference_orbits:
        raise ValueError(f"unknown trial: {trial}")
    reference = next(iter(reference_orbits[trial]))
    allowed = reference_orbits[trial]
    result = tuple(
        permutation
        for permutation in site_permutations_2x2()
        if transform_mask(reference, permutation) in allowed
    )
    if not result:
        raise RuntimeError("trial-preserving subgroup is empty")
    return result


def transform_mask(mask: int, permutation: Sequence[int]) -> int:
    if len(permutation) != 4 or sorted(permutation) != list(range(4)):
        raise ValueError("site permutation must contain 0,1,2,3")
    transformed = 0
    for old_site, new_site in enumerate(permutation):
        if (mask >> old_site) & 1:
            transformed |= 1 << new_site
    return transformed


def canonical_mask(
    mask: int,
    transforms: Iterable[Sequence[int]],
    allow_global_flip: bool = False,
) -> int:
    candidates = []
    for permutation in transforms:
        transformed = transform_mask(mask, permutation)
        candidates.append(transformed)
        if allow_global_flip:
            candidates.append((~transformed) & 0xF)
    if not candidates:
        raise ValueError("at least one transform is required")
    return min(candidates)


def _encode_site_masks(masks: Sequence[int], sites: int) -> int:
    config_id = 0
    for mask in masks:
        for site in range(sites):
            config_id <<= 1
            config_id |= (int(mask) >> site) & 1
    return config_id


def canonical_path(
    config_id: int,
    slices: int,
    transforms: Iterable[Sequence[int]],
    allow_global_flip: bool = False,
) -> int:
    masks = decode_masks(
        np.array([config_id], dtype=np.uint64), slices=slices, sites=4
    )[0]
    candidates = []
    for permutation in transforms:
        transformed = [transform_mask(int(mask), permutation) for mask in masks]
        candidates.append(_encode_site_masks(transformed, 4))
        if allow_global_flip:
            candidates.append(
                _encode_site_masks([(~mask) & 0xF for mask in transformed], 4)
            )
    if not candidates:
        raise ValueError("at least one transform is required")
    return min(candidates)


def temporal_features(masks: np.ndarray) -> pd.DataFrame:
    """Return one row per path and slice with spatial/time diagnostics."""

    array = np.asarray(masks)
    if array.ndim != 2:
        raise ValueError("masks must have shape (paths,slices)")
    rows = []
    for path_index, path_masks in enumerate(array):
        run_family = None
        run_length = 0
        previous = None
        for slice_index, raw_mask in enumerate(path_masks):
            mask = int(raw_mask)
            family = mask_family(mask)
            if family == run_family:
                run_length += 1
            else:
                run_family = family
                run_length = 1
            components = spatial_components(mask)
            rows.append(
                {
                    "path_index": path_index,
                    "slice": slice_index,
                    "mask": mask,
                    "mask_class": mask_class(mask),
                    "mask_family": family,
                    **components,
                    "hamming_previous": (
                        -1 if previous is None else (mask ^ previous).bit_count()
                    ),
                    "repeat_previous": (
                        False if previous is None else mask == previous
                    ),
                    "global_flip_previous": (
                        False
                        if previous is None
                        else mask == ((~previous) & 0xF)
                    ),
                    "class_run_length": run_length,
                }
            )
            previous = mask
    return pd.DataFrame.from_records(rows)
