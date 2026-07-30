"""Screen 7-vertex graphs for SOHS level-1 closability.

Reuses the proven dual SDP formulation from batch2_closure.py.
For each 7-vertex graph with alpha=2, attempts to prove beta <= alpha
at level 1. Reports which are closeable.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from collections import defaultdict

import cvxpy as cp
import networkx as nx
import numpy as np


def basis_subsets(n, order):
    return tuple(subset for size in range(order + 1) for subset in combinations(range(n), size))


def _canonical_word(word, edges):
    items = list(word)
    sign = 1
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor - 1] > items[cursor]:
            l, r = items[cursor - 1], items[cursor]
            if tuple(sorted((l, r))) in edges:
                sign = -sign
            items[cursor - 1], items[cursor] = r, l
            cursor -= 1
    reduced = []
    for item in items:
        if reduced and reduced[-1] == item:
            reduced.pop()
        else:
            reduced.append(item)
    return sign, sum(1 << i for i in reduced)


def _adjoint_sign(mask, edges):
    v = tuple(i for i in range(mask.bit_length()) if mask & (1 << i))
    s, _ = _canonical_word(tuple(reversed(v)), edges)
    return s


def _entry_label(left, right, n, edges):
    counts = [0] * n
    for i in left + right:
        counts[i] += 1
    sign, mask = _canonical_word(tuple(reversed(left)) + right, edges)
    if _adjoint_sign(mask, edges) < 0:
        return sign, None
    if mask and mask & (mask - 1) == 0:
        counts[mask.bit_length() - 1] += 1
        mask = 0
    return sign, (tuple(counts), mask)


def independence_number(G: nx.Graph) -> int:
    n = G.number_of_nodes()
    nodes = list(G.nodes())
    for size in range(n, 0, -1):
        for subset in combinations(nodes, size):
            if all(not G.has_edge(u, v) for u, v in combinations(subset, 2)):
                return size
    return 0


def try_level1_closure(n, edges, alpha):
    """Try to prove beta <= alpha at level 1 using dual SDP.
    
    Returns (success, margin, upper_bound).
    """
    edges = frozenset(tuple(sorted(e)) for e in edges)
    basis = tuple(sorted(basis_subsets(n, 1), key=lambda x: (len(x), x)))
    size = len(basis)  # n+1

    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, size):
            sign, label = _entry_label(left, basis[col], n, edges)
            if label is not None:
                groups[label].append((row, col, sign))
    
    labels = tuple(groups)
    matrices = []
    for label in labels:
        M = np.zeros((size, size))
        for r, c, s in groups[label]:
            M[r, c] = s
            M[c, r] = s
        matrices.append(M)

    basis_idx = {w: i for i, w in enumerate(basis)}
    obj = np.zeros((size, size))
    for v in range(n):
        obj[basis_idx[(v,)], basis_idx[(v,)]] = 1.0
    coeffs = np.array([np.sum(obj * M) for M in matrices])

    # Find normalization label
    norm_label = None
    for label in labels:
        if label[1] == 0 and all(c == 0 for c in label[0]):
            norm_label = label
            break
    if norm_label is None:
        # Try the all-zeros entry
        for i, label in enumerate(labels):
            if label == ((0,) * n, 0):
                norm_label = label
                break
    if norm_label is None:
        return False, 0.0, float("inf")
    
    norm_idx = labels.index(norm_label)

    # Dual SDP: find Z >> 0 proving beta <= alpha
    Z = cp.Variable((size, size), symmetric=True)
    margin = cp.Variable()
    upper_val = float(alpha)
    
    constraints = [
        Z - margin * np.eye(size) >> 0,
        cp.sum(cp.multiply(matrices[norm_idx], Z)) <= upper_val,
    ]
    constraints.extend(
        cp.sum(cp.multiply(M, Z)) == -coeffs[i]
        for i, M in enumerate(matrices) if i != norm_idx
    )

    prob = cp.Problem(cp.Maximize(margin), constraints)
    try:
        prob.solve(solver=cp.SCS, eps=1e-9, max_iters=50000, verbose=False)
        if prob.status in ("optimal", "optimal_inaccurate") and margin.value is not None:
            m = float(margin.value)
            return m > 1e-7, m, upper_val
    except Exception:
        pass
    return False, 0.0, float("inf")


def main():
    print("Screening 7-vertex graphs (alpha=2) for level-1 SOHS closure...", flush=True)
    print(f"{'idx':>5} {'edges':>5} {'alpha':>5} {'margin':>12} {'status':>10}", flush=True)
    print("-" * 45, flush=True)

    atlas_graphs = nx.graph_atlas_g()
    seven_vertex = [G for G in atlas_graphs if G.number_of_nodes() == 7]
    
    closeable = []
    total_checked = 0

    for idx, G in enumerate(seven_vertex):
        n_edges = G.number_of_edges()
        if n_edges < 7 or n_edges > 18:
            continue

        alpha = independence_number(G)
        if alpha != 2:
            continue

        total_checked += 1
        edges = list(G.edges())
        success, margin, _ = try_level1_closure(7, edges, alpha)

        status = "CLOSED" if success else "open"
        if success:
            closeable.append({"idx": idx, "edges": edges, "n_edges": n_edges, "margin": margin})
            print(f"{idx:>5} {n_edges:>5} {alpha:>5} {margin:>12.8f} {status:>10} <<<", flush=True)
        elif total_checked % 20 == 0:
            print(f"{idx:>5} {n_edges:>5} {alpha:>5} {'---':>12} {status:>10} ({total_checked} checked)", flush=True)

    print(f"\n=== SUMMARY ===", flush=True)
    print(f"Total alpha=2 graphs checked: {total_checked}", flush=True)
    print(f"Level-1 closeable: {len(closeable)}", flush=True)
    for c in closeable:
        print(f"  atlas idx={c['idx']}, edges={c['n_edges']}, margin={c['margin']:.8f}", flush=True)

    with open("table4_screen.json", "w", encoding="utf-8") as f:
        json.dump(closeable, f, indent=2)
    print(f"\nSaved to table4_screen.json", flush=True)


if __name__ == "__main__":
    main()
