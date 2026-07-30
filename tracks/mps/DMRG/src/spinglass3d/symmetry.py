"""The 48 rotations and reflections of the cubic point group O_h."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import itertools
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .templates import TemplateEncoder


@dataclass(frozen=True)
class CubicTransform:
    matrix: np.ndarray

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=np.int8)
        if matrix.shape != (3, 3):
            raise ValueError("cubic transform must be a 3x3 matrix")
        if not np.all(np.sum(np.abs(matrix), axis=0) == 1) or not np.all(
            np.sum(np.abs(matrix), axis=1) == 1
        ):
            raise ValueError("cubic transform must be a signed permutation")
        owned = matrix.copy()
        owned.setflags(write=False)
        object.__setattr__(self, "matrix", owned)

    @property
    def key(self) -> tuple[int, ...]:
        return tuple(int(value) for value in self.matrix.ravel())

    @property
    def determinant(self) -> int:
        return int(round(float(np.linalg.det(self.matrix))))

    def inverse(self) -> "CubicTransform":
        return CubicTransform(self.matrix.T)

    def compose(self, other: "CubicTransform") -> "CubicTransform":
        if not isinstance(other, CubicTransform):
            raise TypeError("other must be a CubicTransform")
        return CubicTransform(self.matrix @ other.matrix)

    def apply(self, offset: tuple[int, int, int]) -> tuple[int, int, int]:
        transformed = self.matrix @ np.asarray(offset, dtype=np.int8)
        return tuple(int(value) for value in transformed)


@lru_cache(maxsize=1)
def cubic_transforms() -> tuple[CubicTransform, ...]:
    transforms: list[CubicTransform] = []
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            matrix = np.zeros((3, 3), dtype=np.int8)
            for row, column in enumerate(permutation):
                matrix[row, column] = signs[row]
            transforms.append(CubicTransform(matrix))
    transforms.sort(key=lambda transform: transform.key)
    if len({transform.key for transform in transforms}) != 48:
        raise AssertionError("cubic group construction is incomplete")
    return tuple(transforms)


def symmetry_images(
    tokens: np.ndarray,
    encoder: "TemplateEncoder",
) -> tuple[np.ndarray, ...]:
    return tuple(
        encoder.transform_tokens(tokens, transform)
        for transform in cubic_transforms()
    )
