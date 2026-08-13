from __future__ import annotations

import numpy as np


class UnionFind:
    def __init__(self, length: int):
        if isinstance(length, bool) or not isinstance(length, int) or length < 1:
            raise ValueError("length must be a positive integer")
        self.parent = np.arange(length, dtype=np.int64)
        self.size = np.ones(length, dtype=np.int64)

    def find(self, node: int) -> int:
        if isinstance(node, bool) or not isinstance(node, int):
            raise ValueError("node must be an integer")
        if not 0 <= node < self.parent.size:
            raise ValueError("node is out of range")
        root = node
        while self.parent[root] != root:
            root = int(self.parent[root])
        while self.parent[node] != node:
            parent = int(self.parent[node])
            self.parent[node] = root
            node = parent
        return root

    def union(self, left: int, right: int) -> bool:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return False
        if (
            self.size[root_left] < self.size[root_right]
            or (
                self.size[root_left] == self.size[root_right]
                and root_left > root_right
            )
        ):
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        self.size[root_left] += self.size[root_right]
        return True

    def labels(self) -> np.ndarray:
        roots = np.array([self.find(i) for i in range(self.parent.size)])
        minimum = {}
        for node, root in enumerate(roots.tolist()):
            minimum[root] = min(node, minimum.get(root, node))
        return np.array([minimum[int(root)] for root in roots], dtype=np.int64)

    def component_sizes(self) -> np.ndarray:
        _, counts = np.unique(self.labels(), return_counts=True)
        return np.sort(counts.astype(np.int64))[::-1]
