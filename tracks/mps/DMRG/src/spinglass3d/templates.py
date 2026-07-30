"""Gauge-canonical local token templates for shared Tensor-Train densities."""

from __future__ import annotations

from enum import Enum
import itertools
from collections.abc import Sequence

import numpy as np

from .gauge import Edge, canonical_chords
from .model import EABonds
from .symmetry import CubicTransform, cubic_transforms


Offset = tuple[int, int, int]
Site = tuple[int, int, int]


class TemplateKind(str, Enum):
    CROSS = "cross"
    FACE_EDGE = "face_edge"
    CUBE = "cube"
    FACTORIZED_3X3X3 = "factorized_3x3x3"


_CROSS_OFFSETS: tuple[Offset, ...] = (
    (0, 0, 0),
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)


def _face_offsets() -> tuple[Offset, ...]:
    result = list(_CROSS_OFFSETS)
    for first, second in ((0, 1), (0, 2), (1, 2)):
        for signs in itertools.product((-1, 1), repeat=2):
            offset = [0, 0, 0]
            offset[first], offset[second] = signs
            result.append(tuple(offset))
    return tuple(result)


_CUBE_OFFSETS: tuple[Offset, ...] = (
    (0, 0, 0),
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 1, 1),
    (1, 1, 1),
    (1, 0, 1),
    (0, 0, 1),
)


def _factorized_offsets() -> tuple[Offset, ...]:
    result: list[Offset] = []
    for z_index, z in enumerate((-1, 0, 1)):
        rows = (-1, 0, 1) if z_index % 2 == 0 else (1, 0, -1)
        for row_index, y in enumerate(rows):
            x_values = (-1, 0, 1) if (z_index * 3 + row_index) % 2 == 0 else (1, 0, -1)
            result.extend((x, y, z) for x in x_values)
    return tuple(result)


_OFFSETS = {
    TemplateKind.CROSS: _CROSS_OFFSETS,
    TemplateKind.FACE_EDGE: _face_offsets(),
    TemplateKind.CUBE: _CUBE_OFFSETS,
    TemplateKind.FACTORIZED_3X3X3: _factorized_offsets(),
}


def _graph_edges(offsets: tuple[Offset, ...]) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for left in range(len(offsets)):
        for right in range(left + 1, len(offsets)):
            if sum(abs(offsets[left][axis] - offsets[right][axis]) for axis in range(3)) == 1:
                edges.append((left, right))
    return tuple(edges)


def _spanning_tree(vertex_count: int, edges: tuple[Edge, ...]) -> tuple[Edge, ...]:
    parent = list(range(vertex_count))

    def root(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    tree: list[Edge] = []
    for left, right in edges:
        left_root, right_root = root(left), root(right)
        if left_root == right_root:
            continue
        parent[right_root] = left_root
        tree.append((left, right))
    if len(tree) != vertex_count - 1:
        raise ValueError("template graph is not connected")
    return tuple(tree)


def _plaquettes() -> tuple[frozenset[Offset], ...]:
    result: list[frozenset[Offset]] = []
    for first, second in ((0, 1), (0, 2), (1, 2)):
        for low_first, low_second in itertools.product((-1, 0), repeat=2):
            vertices: list[Offset] = []
            for first_step, second_step in itertools.product((0, 1), repeat=2):
                value = [0, 0, 0]
                value[first] = low_first + first_step
                value[second] = low_second + second_step
                vertices.append(tuple(value))
            result.append(frozenset(vertices))
    return tuple(result)


_PLAQUETTES = _plaquettes()


def _edge_key(left: int, right: int) -> Edge:
    return (left, right) if left < right else (right, left)


def _step_product(
    bonds: EABonds,
    start: Site,
    axis: int,
    direction: int,
    steps: int,
) -> int:
    position = list(start)
    product = 1
    for _ in range(steps):
        if direction > 0:
            product *= int(bonds.values[tuple(position) + (axis,)])
            position[axis] = (position[axis] + 1) % bonds.length
        else:
            position[axis] = (position[axis] - 1) % bonds.length
            product *= int(bonds.values[tuple(position) + (axis,)])
    return product


def _effective_edge_sign(
    bonds: EABonds,
    microscopic_anchor: Site,
    left: Offset,
    right: Offset,
    scale: int,
) -> int:
    differences = [right[axis] - left[axis] for axis in range(3)]
    axis = next(axis for axis, value in enumerate(differences) if value)
    direction = 1 if differences[axis] > 0 else -1
    start = tuple(
        (microscopic_anchor[coordinate] + scale * left[coordinate]) % bonds.length
        for coordinate in range(3)
    )
    return _step_product(bonds, start, axis, direction, scale)


def _plaquette_flux(
    bonds: EABonds,
    microscopic_anchor: Site,
    vertices: frozenset[Offset],
    scale: int,
) -> int:
    varying = [axis for axis in range(3) if len({vertex[axis] for vertex in vertices}) == 2]
    first, second = varying
    low = tuple(min(vertex[axis] for vertex in vertices) for axis in range(3))
    start = tuple(
        (microscopic_anchor[axis] + scale * low[axis]) % bonds.length
        for axis in range(3)
    )
    position = list(start)
    product = _step_product(bonds, tuple(position), first, 1, scale)
    position[first] = (position[first] + scale) % bonds.length
    product *= _step_product(bonds, tuple(position), second, 1, scale)
    position[second] = (position[second] + scale) % bonds.length
    product *= _step_product(bonds, tuple(position), first, -1, scale)
    position[first] = (position[first] - scale) % bonds.length
    product *= _step_product(bonds, tuple(position), second, -1, scale)
    return product


class TemplateEncoder:
    """Encode one translated q/J neighborhood as a binary token sequence."""

    def __init__(
        self,
        kind: TemplateKind | str,
        conditioned: bool,
        rg_level: int,
    ) -> None:
        self.kind = TemplateKind(kind)
        self.conditioned = bool(conditioned)
        if isinstance(rg_level, bool) or rg_level not in (1, 2):
            raise ValueError("rg_level must be one or two")
        self.rg_level = int(rg_level)
        self.offsets = _OFFSETS[self.kind]
        self.q_token_count = len(self.offsets)
        self._edges: tuple[Edge, ...] = ()
        self._tree: tuple[Edge, ...] = ()
        self._chords: tuple[Edge, ...] = ()
        if self.kind in (TemplateKind.CUBE, TemplateKind.FACTORIZED_3X3X3):
            self._edges = _graph_edges(self.offsets)
            self._tree = _spanning_tree(len(self.offsets), self._edges)
            tree_set = set(self._tree)
            self._chords = tuple(edge for edge in self._edges if edge not in tree_set)
            expected = 5 if self.kind is TemplateKind.CUBE else 28
            if len(self._chords) != expected:
                raise AssertionError("unexpected template chord count")
            feature_count = len(self._chords)
            self.disorder_encoding = "spanning_tree_chords"
        else:
            feature_count = 12
            self.disorder_encoding = "plaquette_flux"
        self._feature_count = feature_count if self.conditioned else 0
        self._layout = self._build_layout()
        self.q_token_indices = tuple(
            index for index, item in enumerate(self._layout) if item[0] == "q"
        )
        self.token_count = len(self._layout)

    @property
    def cubic_group_size(self) -> int:
        return 48

    def _build_layout(self) -> tuple[tuple[str, int], ...]:
        buckets: list[list[int]] = [[] for _ in self.offsets]
        if self.conditioned:
            if self.disorder_encoding == "spanning_tree_chords":
                for feature, edge in enumerate(self._chords):
                    buckets[max(edge)].append(feature)
            else:
                offset_to_index = {offset: index for index, offset in enumerate(self.offsets)}
                for feature, plaquette in enumerate(_PLAQUETTES):
                    anchors = [offset_to_index[v] for v in plaquette if v in offset_to_index]
                    buckets[max(anchors) if anchors else 0].append(feature)
        layout: list[tuple[str, int]] = []
        for q_index, features in enumerate(buckets):
            layout.append(("q", q_index))
            label = "chord" if self.disorder_encoding == "spanning_tree_chords" else "flux"
            layout.extend((label, feature) for feature in features)
        return tuple(layout)

    def _pack(self, q_values: Sequence[int], disorder: Sequence[int]) -> np.ndarray:
        values = [
            q_values[index] if label == "q" else disorder[index]
            for label, index in self._layout
        ]
        return np.asarray(values, dtype=np.int8)

    def _unpack(self, tokens: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        values = np.asarray(tokens)
        if values.shape != (self.token_count,) or not np.all((values == -1) | (values == 1)):
            raise ValueError("tokens must be one binary sequence of the declared length")
        q_values = np.empty(self.q_token_count, dtype=np.int8)
        disorder = np.empty(self._feature_count, dtype=np.int8)
        for token, (label, index) in zip(values, self._layout, strict=True):
            if label == "q":
                q_values[index] = token
            else:
                disorder[index] = token
        return q_values, disorder

    def encode(
        self,
        q_coarse: np.ndarray,
        bonds: EABonds,
        center: Site,
    ) -> np.ndarray:
        q = np.asarray(q_coarse)
        if q.ndim != 3 or q.shape[0] != q.shape[1] or q.shape[1] != q.shape[2]:
            raise ValueError("q_coarse must be cubic")
        if not np.all((q == -1) | (q == 1)):
            raise ValueError("q_coarse must contain only -1 and +1")
        if not isinstance(bonds, EABonds):
            raise TypeError("bonds must be EABonds")
        scale = 3**self.rg_level
        if bonds.length != q.shape[0] * scale:
            raise ValueError("bonds must cover the full microscopic RG preimage")
        if len(center) != 3:
            raise ValueError("center must contain three coordinates")
        selected_center = tuple(int(value) % q.shape[0] for value in center)
        q_values = [
            int(q[tuple((selected_center[axis] + offset[axis]) % q.shape[0] for axis in range(3))])
            for offset in self.offsets
        ]
        if not self.conditioned:
            return self._pack(q_values, ())

        microscopic_anchor = tuple(
            (selected_center[axis] * scale) % bonds.length for axis in range(3)
        )
        if self.disorder_encoding == "plaquette_flux":
            disorder = [
                _plaquette_flux(bonds, microscopic_anchor, vertices, scale)
                for vertices in _PLAQUETTES
            ]
        else:
            edge_signs = {
                edge: _effective_edge_sign(
                    bonds,
                    microscopic_anchor,
                    self.offsets[edge[0]],
                    self.offsets[edge[1]],
                    scale,
                )
                for edge in self._edges
            }
            disorder = canonical_chords(edge_signs, self._tree)
        return self._pack(q_values, disorder)

    def _transformed_offset(
        self,
        offset: Offset,
        transform: CubicTransform,
    ) -> Offset:
        if self.kind is TemplateKind.CUBE:
            centered = 2 * np.asarray(offset, dtype=np.int8) - 1
            result = transform.matrix @ centered
            return tuple(int(value) for value in ((result + 1) // 2))
        return transform.apply(offset)

    def transform_tokens(
        self,
        tokens: np.ndarray,
        transform: CubicTransform,
    ) -> np.ndarray:
        if not isinstance(transform, CubicTransform):
            raise TypeError("transform must be CubicTransform")
        q_values, disorder = self._unpack(tokens)
        inverse = transform.inverse()
        index_of = {offset: index for index, offset in enumerate(self.offsets)}
        transformed_q = [
            int(q_values[index_of[self._transformed_offset(offset, inverse)]])
            for offset in self.offsets
        ]
        if not self.conditioned:
            return self._pack(transformed_q, ())

        if self.disorder_encoding == "plaquette_flux":
            plaquette_index = {vertices: index for index, vertices in enumerate(_PLAQUETTES)}
            transformed_disorder = []
            for vertices in _PLAQUETTES:
                source = frozenset(inverse.apply(vertex) for vertex in vertices)
                transformed_disorder.append(int(disorder[plaquette_index[source]]))
        else:
            input_signs = {edge: 1 for edge in self._tree}
            input_signs.update(
                {edge: int(disorder[index]) for index, edge in enumerate(self._chords)}
            )
            transformed_edges: dict[Edge, int] = {}
            for edge in self._edges:
                source_offsets = (
                    self._transformed_offset(self.offsets[edge[0]], inverse),
                    self._transformed_offset(self.offsets[edge[1]], inverse),
                )
                source_edge = _edge_key(index_of[source_offsets[0]], index_of[source_offsets[1]])
                transformed_edges[edge] = input_signs[source_edge]
            transformed_disorder = canonical_chords(transformed_edges, self._tree)
        return self._pack(transformed_q, transformed_disorder)

    def symmetry_images(self, tokens: np.ndarray) -> tuple[np.ndarray, ...]:
        return tuple(self.transform_tokens(tokens, transform) for transform in cubic_transforms())

    def flip_q_tokens(self, tokens: np.ndarray) -> np.ndarray:
        values = np.asarray(tokens, dtype=np.int8).copy()
        if values.shape != (self.token_count,):
            raise ValueError("tokens have the wrong length")
        values[np.asarray(self.q_token_indices, dtype=np.int64)] *= -1
        return values

    def reverse_q_incidence(self, length: int) -> dict[Site, tuple[Site, ...]]:
        if isinstance(length, bool) or not isinstance(length, (int, np.integer)) or int(length) < 2:
            raise ValueError("length must be an integer at least two")
        size = int(length)
        result: dict[Site, tuple[Site, ...]] = {}
        for site in np.ndindex((size, size, size)):
            centers = tuple(
                dict.fromkeys(
                    tuple(
                        (site[axis] - offset[axis]) % size
                        for axis in range(3)
                    )
                    for offset in self.offsets
                )
            )
            result[site] = centers
        return result

    def metadata(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "conditioned": self.conditioned,
            "rg_level": self.rg_level,
            "q_token_count": self.q_token_count,
            "token_count": self.token_count,
            "disorder_encoding": self.disorder_encoding,
            "token_sequence": [label for label, _ in self._layout],
        }


def reverse_q_incidence(
    length: int,
    encoder: TemplateEncoder,
) -> dict[Site, tuple[Site, ...]]:
    return encoder.reverse_q_incidence(length)
