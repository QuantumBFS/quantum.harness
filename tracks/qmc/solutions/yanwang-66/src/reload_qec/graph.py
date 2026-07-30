"""Circuit-derived space-time matching graphs conditioned on erasure history."""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import pymatching

from .geometry import Geometry


MAX_FINITE_WEIGHT = 1_000_000.0


class GraphError(ValueError):
    """Raised when graph inputs violate the frozen incidence contract."""


def probability_weight(probability: float) -> float:
    if probability == 0.0:
        return MAX_FINITE_WEIGHT
    if not 0.0 < probability < 0.5:
        raise GraphError(f"edge probability must be in [0,1/2), got {probability}")
    return math.log((1.0 - probability) / probability)


def xor_probability(left: float, right: float) -> float:
    return left * (1.0 - right) + right * (1.0 - left)


@dataclass(frozen=True)
class GraphEdge:
    endpoints: tuple[int, ...]
    logical: int
    base_weight: float
    reload_weight: float
    erasure_site_id: int
    round_index: int
    kind: str


@dataclass(frozen=True)
class DecodeResult:
    prediction: np.ndarray
    catastrophic_loss: np.ndarray
    distinct_graphs: int


class _ParityUnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size
        self.parity_to_parent = [0] * size

    def find(self, node: int) -> tuple[int, int]:
        parent = self.parent[node]
        if parent == node:
            return node, 0
        root, parent_parity = self.find(parent)
        parity = self.parity_to_parent[node] ^ parent_parity
        self.parent[node] = root
        self.parity_to_parent[node] = parity
        return root, parity

    def union(self, left: int, right: int, edge_parity: int) -> bool:
        left_root, left_parity = self.find(left)
        right_root, right_parity = self.find(right)
        if left_root == right_root:
            return (left_parity ^ right_parity) != edge_parity
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
            left_parity, right_parity = right_parity, left_parity
        self.parent[right_root] = left_root
        self.parity_to_parent[right_root] = left_parity ^ right_parity ^ edge_parity
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1
        return False


class MatchingGraph:
    def __init__(
        self, geometry: Geometry, *, p: float, p_m: float, p_reset: float
    ):
        self.geometry = geometry
        self.rounds = geometry.rounds
        self.n_checks = len(geometry.relevant_checks)
        if self.n_checks == 0:
            raise GraphError("geometry has no checks for the requested basis")
        self.n_detectors = (self.rounds + 1) * self.n_checks
        data_probability = 2.0 * p / 3.0
        data_weight = probability_weight(data_probability)
        data_reload_weight = probability_weight(
            xor_probability(data_probability, p_reset)
        )
        measurement_weight = probability_weight(p_m)
        measurement_reload_weight = probability_weight(
            xor_probability(p_m, p_reset)
        )
        parallel_logicals: dict[tuple[int, ...], set[int]] = {}
        for data_edge in geometry.data_edges():
            parallel_logicals.setdefault(data_edge.endpoints, set()).add(
                data_edge.logical
            )
        ambiguous = {
            endpoints: logicals
            for endpoints, logicals in parallel_logicals.items()
            if len(logicals) > 1
        }
        if ambiguous:
            raise GraphError(
                "parallel data edges with different logical parities: "
                f"{ambiguous}"
            )
        edges: list[GraphEdge] = []
        for round_index in range(self.rounds):
            detector_offset = round_index * self.n_checks
            for data_edge in geometry.data_edges():
                edges.append(
                    GraphEdge(
                        endpoints=tuple(
                            detector_offset + endpoint for endpoint in data_edge.endpoints
                        ),
                        logical=data_edge.logical,
                        base_weight=data_weight,
                        reload_weight=data_reload_weight,
                        erasure_site_id=data_edge.site_id,
                        round_index=round_index,
                        kind="data",
                    )
                )
            for check_index, ancilla_site_id in enumerate(
                geometry.relevant_ancilla_site_ids
            ):
                edges.append(
                    GraphEdge(
                        endpoints=(
                            detector_offset + check_index,
                            detector_offset + self.n_checks + check_index,
                        ),
                        logical=0,
                        base_weight=measurement_weight,
                        reload_weight=measurement_reload_weight,
                        erasure_site_id=ancilla_site_id,
                        round_index=round_index,
                        kind="measurement",
                    )
                )
        self.edges = tuple(edges)

    def condition_key(
        self, erasure_mask: np.ndarray, reload_mask: np.ndarray
    ) -> bytes:
        self._validate_erasure_mask(erasure_mask)
        self._validate_reload_mask(reload_mask)
        flags = np.fromiter(
            (
                flag
                for edge in self.edges
                for flag in (
                    bool(erasure_mask[edge.round_index, edge.erasure_site_id]),
                    bool(reload_mask[edge.round_index, edge.erasure_site_id]),
                )
            ),
            dtype=np.uint8,
            count=2 * len(self.edges),
        )
        return np.packbits(flags, bitorder="little").tobytes()

    def build(
        self, erasure_mask: np.ndarray, reload_mask: np.ndarray
    ) -> pymatching.Matching:
        self._validate_erasure_mask(erasure_mask)
        self._validate_reload_mask(reload_mask)
        matching = pymatching.Matching()
        for edge in self.edges:
            erased = bool(erasure_mask[edge.round_index, edge.erasure_site_id])
            reloaded = bool(reload_mask[edge.round_index, edge.erasure_site_id])
            weight = 0.0 if erased else (
                edge.reload_weight if reloaded else edge.base_weight
            )
            fault_ids = {0} if edge.logical else set()
            if len(edge.endpoints) == 1:
                matching.add_boundary_edge(
                    edge.endpoints[0],
                    fault_ids=fault_ids,
                    weight=weight,
                    merge_strategy="independent",
                )
            elif len(edge.endpoints) == 2:
                matching.add_edge(
                    edge.endpoints[0],
                    edge.endpoints[1],
                    fault_ids=fault_ids,
                    weight=weight,
                    merge_strategy="independent",
                )
            else:
                raise GraphError(f"non-graphlike edge endpoints {edge.endpoints}")
        return matching

    def is_catastrophic(self, erasure_mask: np.ndarray) -> bool:
        self._validate_erasure_mask(erasure_mask)
        boundary = self.n_detectors
        components = _ParityUnionFind(self.n_detectors + 1)
        for edge in self.edges:
            if not erasure_mask[edge.round_index, edge.erasure_site_id]:
                continue
            left = edge.endpoints[0]
            right = edge.endpoints[1] if len(edge.endpoints) == 2 else boundary
            if components.union(left, right, edge.logical):
                return True
        return False

    def _validate_erasure_mask(self, erasure_mask: np.ndarray) -> None:
        expected = (self.rounds, self.geometry.n_sites)
        if erasure_mask.shape != expected:
            raise GraphError(f"erasure mask shape {erasure_mask.shape} != {expected}")

    def _validate_reload_mask(self, reload_mask: np.ndarray) -> None:
        expected = (self.rounds + 1, self.geometry.n_sites)
        if reload_mask.shape != expected:
            raise GraphError(f"reload mask shape {reload_mask.shape} != {expected}")


class GraphDecoder:
    """Decode batches while caching graphs by revealed erasure history only."""

    def __init__(self, graph: MatchingGraph, *, max_cache_entries: int = 4_096):
        if max_cache_entries <= 0:
            raise ValueError("max_cache_entries must be positive")
        self.graph = graph
        self.max_cache_entries = max_cache_entries
        self._cache: OrderedDict[bytes, tuple[pymatching.Matching, bool]] = OrderedDict()

    def decode(
        self,
        detection_events: np.ndarray,
        erasure_mask: np.ndarray,
        reload_mask: np.ndarray,
    ) -> DecodeResult:
        expected_detection = (
            erasure_mask.shape[0],
            self.graph.rounds + 1,
            self.graph.n_checks,
        )
        if detection_events.shape != expected_detection:
            raise GraphError(
                f"detection shape {detection_events.shape} != {expected_detection}"
            )
        expected_erasure = (
            detection_events.shape[0],
            self.graph.rounds,
            self.graph.geometry.n_sites,
        )
        if erasure_mask.shape != expected_erasure:
            raise GraphError(f"erasure shape {erasure_mask.shape} != {expected_erasure}")
        expected_reload = (
            detection_events.shape[0],
            self.graph.rounds + 1,
            self.graph.geometry.n_sites,
        )
        if reload_mask.shape != expected_reload:
            raise GraphError(f"reload shape {reload_mask.shape} != {expected_reload}")
        groups: dict[bytes, list[int]] = {}
        representatives: dict[bytes, tuple[np.ndarray, np.ndarray]] = {}
        for shot_index in range(detection_events.shape[0]):
            shot_mask = erasure_mask[shot_index]
            shot_reload = reload_mask[shot_index]
            key = self.graph.condition_key(shot_mask, shot_reload)
            groups.setdefault(key, []).append(shot_index)
            representatives.setdefault(key, (shot_mask, shot_reload))
        prediction = np.zeros((detection_events.shape[0], 1), dtype=np.uint8)
        catastrophic = np.zeros(detection_events.shape[0], dtype=np.uint8)
        for key, indices in groups.items():
            representative_mask, representative_reload = representatives[key]
            matching, graph_catastrophic = self._get_graph(
                key, representative_mask, representative_reload
            )
            batch = detection_events[np.asarray(indices)].reshape(len(indices), -1)
            decoded = np.asarray(matching.decode_batch(batch), dtype=np.uint8)
            if decoded.ndim == 1:
                decoded = decoded.reshape(-1, 1)
            if decoded.shape != (len(indices), 1):
                raise GraphError(f"unexpected decoder output shape {decoded.shape}")
            prediction[np.asarray(indices)] = decoded
            catastrophic[np.asarray(indices)] = int(graph_catastrophic)
        return DecodeResult(
            prediction=prediction,
            catastrophic_loss=catastrophic,
            distinct_graphs=len(groups),
        )

    def _get_graph(
        self, key: bytes, erasure_mask: np.ndarray, reload_mask: np.ndarray
    ) -> tuple[pymatching.Matching, bool]:
        cached = self._cache.pop(key, None)
        if cached is not None:
            self._cache[key] = cached
            return cached
        value = (
            self.graph.build(erasure_mask, reload_mask),
            self.graph.is_catastrophic(erasure_mask),
        )
        self._cache[key] = value
        if len(self._cache) > self.max_cache_entries:
            self._cache.popitem(last=False)
        return value
