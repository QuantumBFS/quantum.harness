"""Exact index maps for 3x3 square-lattice patch symmetries."""

from __future__ import annotations

import numpy as np


PATCH_COORDINATES: tuple[tuple[int, int], ...] = tuple(
    (x, y) for x in range(-1, 2) for y in range(-1, 2)
)


def _transforms(x: int, y: int) -> tuple[tuple[int, int], ...]:
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


def _build_d4_index_maps() -> tuple[np.ndarray, ...]:
    coordinate_index = {coordinate: index for index, coordinate in enumerate(PATCH_COORDINATES)}
    maps = []
    for transform_index in range(8):
        mapping = np.empty(9, dtype=np.int8)
        for source, coordinate in enumerate(PATCH_COORDINATES):
            destination_coordinate = _transforms(*coordinate)[transform_index]
            destination = coordinate_index[destination_coordinate]
            mapping[destination] = source
        maps.append(mapping)
    if len({tuple(mapping) for mapping in maps}) != 8:
        raise AssertionError("D4 construction did not produce eight unique maps")
    return tuple(maps)


D4_INDEX_MAPS = _build_d4_index_maps()


def transform_patch(patch: np.ndarray, transform_index: int) -> np.ndarray:
    values = np.asarray(patch)
    if values.shape != (9,):
        raise ValueError("patch must have shape (9,)")
    if not 0 <= transform_index < 8:
        raise ValueError("transform_index must lie in [0, 8)")
    return values[D4_INDEX_MAPS[transform_index]]


def transform_patches(patches: np.ndarray, transform_index: int) -> np.ndarray:
    values = np.asarray(patches)
    if values.ndim != 2 or values.shape[1] != 9:
        raise ValueError("patches must have shape (samples, 9)")
    if not 0 <= transform_index < 8:
        raise ValueError("transform_index must lie in [0, 8)")
    return values[:, D4_INDEX_MAPS[transform_index]]
