from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np


Vertex = Tuple[int, int]


@dataclass(frozen=True)
class OperatorShape:
    name: str
    vertices: tuple[Vertex, ...]
    parity: str


EVEN_SHAPES: tuple[OperatorShape, ...] = (
    OperatorShape("even_01_nn", ((0, 0), (1, 0)), "even"),
    OperatorShape("even_02_diag", ((0, 0), (1, 1)), "even"),
    OperatorShape("even_03_axis2", ((0, 0), (2, 0)), "even"),
    OperatorShape("even_04_21", ((0, 0), (2, 1)), "even"),
    OperatorShape("even_05_diag2", ((0, 0), (2, 2)), "even"),
    OperatorShape("even_06_axis3", ((0, 0), (3, 0)), "even"),
    OperatorShape("even_07_31", ((0, 0), (3, 1)), "even"),
    OperatorShape("even_08_square", ((0, 0), (1, 0), (0, 1), (1, 1)), "even"),
    OperatorShape("even_09_diamond", ((0, 0), (1, 1), (2, 0), (1, -1)), "even"),
    OperatorShape("even_10_t", ((0, 0), (-1, 0), (1, 0), (0, 1)), "even"),
    OperatorShape("even_11_four", ((0, 0), (-1, 0), (1, 0), (-1, 1)), "even"),
    OperatorShape("even_12_four", ((0, 0), (0, 1), (1, 0), (-1, 1)), "even"),
    OperatorShape("even_13_four", ((0, 0), (0, 1), (1, 0), (-1, -1)), "even"),
)


ODD_SHAPES: tuple[OperatorShape, ...] = (
    OperatorShape("odd_00_magnetization", ((0, 0),), "odd"),
    OperatorShape("odd_01_corner", ((0, 0), (0, -1), (-1, 0)), "odd"),
    OperatorShape("odd_02_line", ((0, 0), (-1, 0), (1, 0)), "odd"),
    OperatorShape("odd_03_three", ((0, 0), (1, -1), (-1, 0)), "odd"),
    OperatorShape("odd_04_three", ((0, 0), (1, -1), (-1, -1)), "odd"),
)


def _normalize(vertices: Iterable[Vertex]) -> tuple[Vertex, ...]:
    points = tuple(vertices)
    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    return tuple(sorted((x - min_x, y - min_y) for x, y in points))


def d4_orbit(vertices: Iterable[Vertex]) -> tuple[tuple[Vertex, ...], ...]:
    points = tuple(vertices)

    def transforms(x: int, y: int) -> tuple[Vertex, ...]:
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

    orbit = set()
    for transform_index in range(8):
        orbit.add(_normalize(transforms(x, y)[transform_index] for x, y in points))
    return tuple(sorted(orbit))


class OperatorBasis:
    """Translation- and D4-symmetrized spin-product operators on a torus."""

    def __init__(self, length: int, shapes: Iterable[OperatorShape]) -> None:
        if length < 2:
            raise ValueError("length must be at least 2")
        self.length = int(length)
        self.shapes = tuple(shapes)
        self.instances: tuple[np.ndarray, ...] = tuple(
            self._build_instances(shape) for shape in self.shapes
        )
        self._incidence = self._build_incidence()
        self._packed_incidence_cache: (
            tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None
        ) = None

    def _build_instances(self, shape: OperatorShape) -> np.ndarray:
        unique: set[tuple[int, ...]] = set()
        for orientation in d4_orbit(shape.vertices):
            for x0 in range(self.length):
                for y0 in range(self.length):
                    sites = tuple(
                        sorted(
                            ((x0 + dx) % self.length) * self.length
                            + ((y0 + dy) % self.length)
                            for dx, dy in orientation
                        )
                    )
                    if len(set(sites)) != len(sites):
                        raise ValueError(
                            f"shape {shape.name} aliases a site at lattice length {self.length}"
                        )
                    unique.add(sites)
        if not unique:
            raise AssertionError(f"shape {shape.name} generated no instances")
        return np.asarray(sorted(unique), dtype=np.int32)

    def _build_incidence(self) -> tuple[tuple[tuple[int, int], ...], ...]:
        per_site: list[list[tuple[int, int]]] = [
            [] for _ in range(self.length * self.length)
        ]
        for operator_index, instances in enumerate(self.instances):
            for instance_index, sites in enumerate(instances):
                for site in sites:
                    per_site[int(site)].append((operator_index, instance_index))
        return tuple(tuple(entries) for entries in per_site)

    @property
    def instance_counts(self) -> tuple[int, ...]:
        return tuple(int(instances.shape[0]) for instances in self.instances)

    def packed_incidence(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return a CSR-like incidence table suitable for compiled kernels."""
        if self._packed_incidence_cache is not None:
            return self._packed_incidence_cache
        offsets = np.zeros(self.length * self.length + 1, dtype=np.int64)
        for site, entries in enumerate(self._incidence):
            offsets[site + 1] = offsets[site] + len(entries)

        count = int(offsets[-1])
        operator_indices = np.empty(count, dtype=np.int32)
        arities = np.empty(count, dtype=np.int8)
        max_arity = max(len(shape.vertices) for shape in self.shapes)
        sites = np.full((count, max_arity), -1, dtype=np.int32)
        cursor = 0
        for entries in self._incidence:
            for operator_index, instance_index in entries:
                instance = self.instances[operator_index][instance_index]
                operator_indices[cursor] = operator_index
                arities[cursor] = len(instance)
                sites[cursor, : len(instance)] = instance
                cursor += 1
        self._packed_incidence_cache = offsets, operator_indices, arities, sites
        return self._packed_incidence_cache

    def values(self, spins: np.ndarray) -> np.ndarray:
        flat = np.asarray(spins, dtype=np.int8).reshape(-1)
        if flat.size != self.length * self.length:
            raise ValueError("spin array has the wrong size")
        result = np.empty(len(self.shapes), dtype=np.int64)
        for index, instances in enumerate(self.instances):
            products = np.prod(flat[instances], axis=1, dtype=np.int64)
            result[index] = -int(products.sum(dtype=np.int64))
        return result

    def delta_for_flip(self, spins: np.ndarray, x: int, y: int) -> np.ndarray:
        flat = np.asarray(spins, dtype=np.int8).reshape(-1)
        site = (x % self.length) * self.length + (y % self.length)
        delta = np.zeros(len(self.shapes), dtype=np.int64)
        for operator_index, instance_index in self._incidence[site]:
            sites = self.instances[operator_index][instance_index]
            product = int(np.prod(flat[sites], dtype=np.int64))
            delta[operator_index] += 2 * product
        return delta
