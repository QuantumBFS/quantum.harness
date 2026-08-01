#!/usr/bin/env python3
"""Exact finite certificates for the issue-251 interface note.

No floating-point arithmetic or third-party package is used.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence


Partition = tuple[int, ...]
Monomial = tuple[int, ...]
Polynomial = dict[Monomial, int]


def canonical(labels: Iterable[int]) -> Partition:
    renaming: dict[int, int] = {}
    result: list[int] = []
    for label in labels:
        if label not in renaming:
            renaming[label] = len(renaming)
        result.append(renaming[label])
    return tuple(result)


def set_partitions(n: int) -> tuple[Partition, ...]:
    result: list[Partition] = []

    def visit(prefix: list[int]) -> None:
        if len(prefix) == n:
            result.append(tuple(prefix))
            return
        upper = 0 if not prefix else max(prefix) + 1
        for label in range(upper + 1):
            prefix.append(label)
            visit(prefix)
            prefix.pop()

    visit([])
    return tuple(result)


def join_partition(left: Partition, right: Partition) -> Partition:
    parent = list(range(len(left)))

    def find(vertex: int) -> int:
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    def union(a: int, b: int) -> None:
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for partition in (left, right):
        first: dict[int, int] = {}
        for vertex, block in enumerate(partition):
            if block in first:
                union(first[block], vertex)
            else:
                first[block] = vertex
    return canonical(find(vertex) for vertex in range(len(left)))


def partition_rank(partition: Partition) -> int:
    return len(partition) - len(set(partition))


def union_is_forest(left: Partition, right: Partition) -> bool:
    joined = join_partition(left, right)
    return (
        partition_rank(left) + partition_rank(right)
        == partition_rank(joined)
    )


def compose_exact(
    partitions: Sequence[Partition],
    left: Sequence[int],
    right: Sequence[int],
) -> tuple[int, ...]:
    index = {partition: i for i, partition in enumerate(partitions)}
    result = [0] * len(partitions)
    for i, left_partition in enumerate(partitions):
        for j, right_partition in enumerate(partitions):
            if union_is_forest(left_partition, right_partition):
                joined = join_partition(left_partition, right_partition)
                result[index[joined]] += left[i] * right[j]
    return tuple(result)


def three_coordinates(
    partitions: Sequence[Partition], signature: Sequence[int]
) -> tuple[int, int, int, int, int]:
    values = dict(zip(partitions, signature, strict=True))
    return (
        values[(0, 1, 2)],  # p: all separate
        values[(0, 0, 1)],  # q: uv connected
        values[(0, 1, 0)],  # r: uz connected
        values[(0, 1, 1)],  # s: vz connected
        values[(0, 0, 0)],  # t: all connected
    )


def three_gap(partitions: Sequence[Partition], signature: Sequence[int]) -> int:
    p, q, r, s, t = three_coordinates(partitions, signature)
    return p * (t - s) - (r + s) * (q + s)


def poly_add(*polynomials: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for polynomial in polynomials:
        for monomial, coefficient in polynomial.items():
            result[monomial] = result.get(monomial, 0) + coefficient
            if result[monomial] == 0:
                del result[monomial]
    return result


def poly_scale(polynomial: Polynomial, scalar: int) -> Polynomial:
    return {
        monomial: scalar * coefficient
        for monomial, coefficient in polynomial.items()
        if scalar * coefficient
    }


def poly_multiply(left: Polynomial, right: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            monomial = tuple(sorted(left_monomial + right_monomial))
            result[monomial] = (
                result.get(monomial, 0)
                + left_coefficient * right_coefficient
            )
    return {monomial: coefficient for monomial, coefficient in result.items() if coefficient}


def poly_variable(index: int) -> Polynomial:
    return {(index,): 1}


def symbolic_three_gap(coordinates: Sequence[Polynomial]) -> Polynomial:
    p, q, r, s, t = coordinates
    return poly_add(
        poly_multiply(p, poly_add(t, poly_scale(s, -1))),
        poly_scale(
            poly_multiply(poly_add(r, s), poly_add(q, s)),
            -1,
        ),
    )


def verify_three_terminal_identity() -> None:
    partitions = set_partitions(3)
    assert len(partitions) == 5
    index = {partition: i for i, partition in enumerate(partitions)}
    left_variables = tuple(poly_variable(i) for i in range(5))
    right_variables = tuple(poly_variable(5 + i) for i in range(5))
    composed: list[Polynomial] = [{} for _ in range(5)]
    for i, left_partition in enumerate(partitions):
        for j, right_partition in enumerate(partitions):
            if not union_is_forest(left_partition, right_partition):
                continue
            joined = join_partition(left_partition, right_partition)
            term = poly_multiply(left_variables[i], right_variables[j])
            composed[index[joined]] = poly_add(composed[index[joined]], term)

    coordinate_order = (
        index[(0, 1, 2)],
        index[(0, 0, 1)],
        index[(0, 1, 0)],
        index[(0, 1, 1)],
        index[(0, 0, 0)],
    )
    left_coordinates = tuple(left_variables[i] for i in coordinate_order)
    right_coordinates = tuple(right_variables[i] for i in coordinate_order)
    composed_coordinates = tuple(composed[i] for i in coordinate_order)
    p_left, _, _, s_left, _ = left_coordinates
    p_right, _, _, s_right, _ = right_coordinates

    actual = symbolic_three_gap(composed_coordinates)
    expected = poly_add(
        poly_multiply(
            poly_multiply(p_left, p_left),
            symbolic_three_gap(right_coordinates),
        ),
        poly_multiply(
            poly_multiply(p_right, p_right),
            symbolic_three_gap(left_coordinates),
        ),
        poly_scale(
            poly_multiply(
                poly_multiply(p_left, p_right),
                poly_multiply(s_left, s_right),
            ),
            -2,
        ),
    )
    assert actual == expected
    print(
        "three-terminal identity: complete symbolic coefficient check "
        f"passed ({len(actual)} nonzero monomials)"
    )


def edge_partition(edge: tuple[int, int]) -> Partition:
    left, right = edge
    labels = list(range(4))
    labels[right] = labels[left]
    return canonical(labels)


def disjoint_totals(
    partitions: Sequence[Partition],
    signature: Sequence[int],
    edge1: tuple[int, int],
    edge2: tuple[int, int],
) -> tuple[int, int, int, int]:
    A = sum(signature)
    B = C = D = 0
    e_partition = edge_partition(edge1)
    f_partition = edge_partition(edge2)
    for partition, value in zip(partitions, signature, strict=True):
        e_ok = partition[edge1[0]] != partition[edge1[1]]
        f_ok = partition[edge2[0]] != partition[edge2[1]]
        if e_ok:
            B += value
        if f_ok:
            C += value
        if e_ok and f_ok:
            after_e = join_partition(partition, e_partition)
            after_both = join_partition(after_e, f_partition)
            if partition_rank(after_both) == partition_rank(partition) + 2:
                D += value
    return A, B, C, D


def reversed_gap(totals: Sequence[int]) -> int:
    A, B, C, D = totals
    return A * D - B * C


def verify_four_terminal_crossover() -> None:
    partitions = set_partitions(4)
    assert len(partitions) == 15
    left = (69, 74, 58, 54, 6, 87, 17, 18, 38, 76, 1, 35, 34, 3, 61)
    right = (72, 57, 58, 29, 3, 17, 72, 90, 16, 6, 79, 89, 81, 11, 24)
    matchings = (
        ((0, 1), (2, 3)),
        ((0, 2), (1, 3)),
        ((0, 3), (1, 2)),
    )
    expected_left = (-32521, -71096, -51330)
    expected_right = (-20413, -19316, -67112)
    expected_composed = (1134803118, 413278037, 74494526)
    composed = compose_exact(partitions, left, right)
    left_gaps = tuple(
        reversed_gap(disjoint_totals(partitions, left, *matching))
        for matching in matchings
    )
    right_gaps = tuple(
        reversed_gap(disjoint_totals(partitions, right, *matching))
        for matching in matchings
    )
    composed_gaps = tuple(
        reversed_gap(disjoint_totals(partitions, composed, *matching))
        for matching in matchings
    )
    assert left_gaps == expected_left
    assert right_gaps == expected_right
    assert composed_gaps == expected_composed
    assert all(gap < 0 for gap in left_gaps + right_gaps)
    assert all(gap > 0 for gap in composed_gaps)
    print(f"four-terminal crossover: exact gaps {composed_gaps}")


def book_edges(r: int) -> tuple[tuple[int, int, int], ...]:
    edges: list[tuple[int, int, int]] = []
    for left, right in itertools.combinations(range(3), 2):
        edges.append((left, right, 2))
    for leaf in range(3, 3 + r):
        for core in range(3):
            edges.append((core, leaf, 3))
    return tuple(edges)


def verify_book_slice() -> None:
    total_pairs = 0
    for r in range(1, 5):
        edges = book_edges(r)
        edge_count = len(edges)
        Z = 0
        Ze = [0] * edge_count
        Zef = [[0] * edge_count for _ in range(edge_count)]
        for mask in range(1 << edge_count):
            parent = list(range(3 + r))

            def find(vertex: int) -> int:
                while parent[vertex] != vertex:
                    parent[vertex] = parent[parent[vertex]]
                    vertex = parent[vertex]
                return vertex

            chosen: list[int] = []
            weight = 1
            acyclic = True
            for index, (left, right, activity) in enumerate(edges):
                if not (mask >> index) & 1:
                    continue
                left_root, right_root = find(left), find(right)
                if left_root == right_root:
                    acyclic = False
                    break
                parent[right_root] = left_root
                chosen.append(index)
                weight *= activity
            if not acyclic:
                continue
            Z += weight
            for index in chosen:
                Ze[index] += weight
            for first, second in itertools.combinations(chosen, 2):
                Zef[first][second] += weight
        for first, second in itertools.combinations(range(edge_count), 2):
            negative_correlation_gap = (
                Ze[first] * Ze[second] - Zef[first][second] * Z
            )
            assert negative_correlation_gap > 0
            total_pairs += 1
    print(f"symmetric-book regression: {total_pairs} exact edge pairs passed")


def main() -> None:
    verify_three_terminal_identity()
    verify_four_terminal_crossover()
    verify_book_slice()
    print("all exact interface certificates passed")


if __name__ == "__main__":
    main()
