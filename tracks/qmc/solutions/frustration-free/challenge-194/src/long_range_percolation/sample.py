from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .union_find import UnionFind


@dataclass(frozen=True)
class GraphSample:
    length: int
    edges: np.ndarray
    labels: np.ndarray

    def __post_init__(self) -> None:
        if (
            isinstance(self.length, bool)
            or not isinstance(self.length, int)
            or self.length < 1
        ):
            raise ValueError("length must be a positive integer")
        edges = np.array(self.edges, dtype=np.int64, copy=True)
        labels = np.array(self.labels, dtype=np.int64, copy=True)
        if edges.ndim != 2 or edges.shape[1:] != (2,):
            raise ValueError("edges must have shape (n_edges, 2)")
        if labels.shape != (self.length,):
            raise ValueError("labels must have shape (length,)")
        if edges.size and (
            np.any(edges < 0) or np.any(edges >= self.length)
        ):
            raise ValueError("edge endpoint is out of range")
        if edges.size and np.any(edges[:, 0] >= edges[:, 1]):
            raise ValueError("edges must have canonical increasing endpoints")
        edge_tuples = [tuple(edge) for edge in edges.tolist()]
        if edge_tuples != sorted(edge_tuples):
            raise ValueError("edges must be sorted")
        if len(edge_tuples) != len(set(edge_tuples)):
            raise ValueError("duplicate edges are forbidden")
        union_find = UnionFind(self.length)
        for left, right in edge_tuples:
            union_find.union(left, right)
        if not np.array_equal(labels, union_find.labels()):
            raise ValueError("labels do not match the edge-induced partition")
        edges.setflags(write=False)
        labels.setflags(write=False)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "labels", labels)
