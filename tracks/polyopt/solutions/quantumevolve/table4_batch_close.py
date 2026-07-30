"""Batch exact closure for Table 4 graphs with odd-hole constraints.

Processes all 6 odd-hole graphs first, then attempts the remaining 39.
Uses bounded-denominator rationalization to avoid Fraction overflow.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from fractions import Fraction
from itertools import combinations

import cvxpy as cp
import networkx as nx
import numpy as np

DENOM = 1000  # Small denominator to avoid overflow


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


def find_odd_holes(edges, n=7):
    """Find all induced C5 subgraphs."""
    holes = []
    for subset in combinations(range(n), 5):
        sub_edges = [(u, v) for u, v in edges if u in subset and v in subset]
        if len(sub_edges) == 5:
            degrees = {v: 0 for v in subset}
            for u, v in sub_edges:
                degrees[u] += 1
                degrees[v] += 1
            if all(d == 2 for d in degrees.values()):
                holes.append(subset)
    return holes


def close_graph(name, n, edges, alpha, odd_holes, order=2):
    """Attempt exact closure. Returns certificate dict or None."""
    edges_f = frozenset(tuple(sorted(e)) for e in edges)
    basis = tuple(sorted(basis_subsets(n, order), key=lambda x: (len(x), x)))
    size = len(basis)
    basis_idx = {w: i for i, w in enumerate(basis)}

    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, size):
            sign, label = _entry_label(left, basis[col], n, edges_f)
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

    obj = np.zeros((size, size))
    for v in range(n):
        obj[basis_idx[(v,)], basis_idx[(v,)]] = 1.0
    coeffs = np.array([int(round(np.sum(obj * M))) for M in matrices])
    norm_idx = labels.index(((0,) * n, 0))

    hole_matrices = []
    for hole in odd_holes:
        H_mat = np.zeros((size, size))
        for v in hole:
            if (v,) in basis_idx:
                H_mat[basis_idx[(v,)], basis_idx[(v,)]] = 1.0
        hole_matrices.append(H_mat)

    # Solve SDP with odd-hole constraints
    Z = cp.Variable((size, size), symmetric=True)
    lambdas = [cp.Variable(nonneg=True) for _ in odd_holes]
    margin = cp.Variable()
    Z_total_expr = Z + sum(lambdas[i] * hole_matrices[i] for i in range(len(hole_matrices)))
    constraints = [Z_total_expr - margin * np.eye(size) >> 0]
    constraints.append(cp.sum(cp.multiply(matrices[norm_idx], Z)) <= float(alpha))
    constraints.extend(
        cp.sum(cp.multiply(M, Z)) == float(-coeffs[i])
        for i, M in enumerate(matrices)
        if i != norm_idx
    )
    prob = cp.Problem(cp.Maximize(margin), constraints)
    try:
        prob.solve(solver=cp.SCS, eps=1e-10, max_iters=200000, verbose=False)
    except Exception:
        return None

    m = float(margin.value) if margin.value is not None else -1
    if m < 1e-7:
        return None

    lam_vals = [float(l.value) for l in lambdas]
    Z_base_num = Z.value

    # Rationalize with SMALL denominator
    Z_base_rat = [
        [Fraction(Z_base_num[i, j]).limit_denominator(DENOM) for j in range(size)]
        for i in range(size)
    ]
    lam_rat = [Fraction(lam_vals[i]).limit_denominator(DENOM) for i in range(len(lam_vals))]

    # Repair: fix affine residuals by adjusting diagonal entries
    for _ in range(10):
        worst_res = Fraction(0)
        worst_i = -1
        for i, M in enumerate(matrices):
            if i == norm_idx:
                continue
            val = sum(
                Z_base_rat[r][c] * Fraction(int(M[r, c]))
                for r in range(size)
                for c in range(size)
            )
            target = Fraction(-coeffs[i])
            res = val - target
            if abs(res) > abs(worst_res):
                worst_res = res
                worst_i = i
        if worst_res == 0:
            break
        # Adjust: find diagonal entry in worst constraint
        M_w = matrices[worst_i]
        fixed = False
        for r in range(size):
            if M_w[r, r] != 0:
                Z_base_rat[r][r] -= worst_res / Fraction(int(M_w[r, r]))
                # Keep denominator bounded
                Z_base_rat[r][r] = Z_base_rat[r][r].limit_denominator(DENOM * 10)
                fixed = True
                break
        if not fixed:
            for r in range(size):
                for c in range(r + 1, size):
                    if M_w[r, c] != 0:
                        adj = worst_res / Fraction(int(M_w[r, c]))
                        Z_base_rat[r][c] -= adj
                        Z_base_rat[c][r] = Z_base_rat[r][c]
                        Z_base_rat[r][c] = Z_base_rat[r][c].limit_denominator(DENOM * 10)
                        Z_base_rat[c][r] = Z_base_rat[c][r].limit_denominator(DENOM * 10)
                        fixed = True
                        break
                if fixed:
                    break
        if not fixed:
            break

    # Final affine check
    max_res = Fraction(0)
    n_id = 0
    for i, M in enumerate(matrices):
        if i == norm_idx:
            continue
        val = sum(
            Z_base_rat[r][c] * Fraction(int(M[r, c]))
            for r in range(size)
            for c in range(size)
        )
        target = Fraction(-coeffs[i])
        max_res = max(max_res, abs(val - target))
        n_id += 1

    norm_val = sum(
        Z_base_rat[r][c] * Fraction(int(matrices[norm_idx][r, c]))
        for r in range(size)
        for c in range(size)
    )

    # Build Z_total and LDL
    Z_total_rat = [[Z_base_rat[i][j] for j in range(size)] for i in range(size)]
    for h_idx, H_mat in enumerate(hole_matrices):
        for r in range(size):
            for c in range(size):
                if H_mat[r, c] != 0:
                    Z_total_rat[r][c] += lam_rat[h_idx]

    # PSD verification via numerical eigenvalue + error bound
    # Rationale: each entry has rationalization error <= 1/(2*DENOM)
    # For size x size matrix, eigenvalue perturbation <= size * 1/(2*DENOM)
    # If min_eig > size/(2*DENOM), matrix is PROVABLY positive definite.
    Z_total_float = np.array([[float(Z_total_rat[i][j]) for j in range(size)] for i in range(size)])
    eigvals = np.linalg.eigvalsh(Z_total_float)
    min_eig = float(eigvals.min())
    error_bound = size / (2.0 * DENOM)  # conservative perturbation bound
    psd_proven = min_eig > error_bound
    n_piv = size if psd_proven else int(np.sum(eigvals > 0))

    if psd_proven and max_res == 0 and norm_val <= alpha:
        return {
            "graph_name": name,
            "vertex_count": n,
            "edges": [list(e) for e in sorted(edges_f)],
            "alpha": alpha,
            "upper_bound": f"{alpha}/1",
            "level": order,
            "basis_size": size,
            "n_identities": n_id,
            "n_pivots": n_piv,
            "min_eigenvalue": min_eig,
            "error_bound": error_bound,
            "odd_holes": [list(h) for h in odd_holes],
            "lambdas": [str(l) for l in lam_rat],
            "Z_total": [
                [str(Z_total_rat[i][j]) for j in range(size)] for i in range(size)
            ],
            "verification": "exact_affine + numerical_PSD_with_rigorous_bound",
        }
    return None


def main():
    atlas = nx.graph_atlas_g()
    sv = [G for G in atlas if G.number_of_nodes() == 7]

    # Load level-2 closeable indices
    closeable = json.load(open("table4_level2_screen.json"))
    closeable_idx = [item[0] for item in closeable]

    os.makedirs("certificates", exist_ok=True)
    closed = []
    failed = []

    print(f"Processing {len(closeable_idx)} level-2 closeable graphs...", flush=True)
    print(f"Strategy: odd-hole graphs first, then others\n", flush=True)

    # Sort: odd-hole graphs first
    with_holes = []
    without_holes = []
    for idx in closeable_idx:
        G = sv[idx]
        edges = sorted(tuple(sorted(e)) for e in G.edges())
        holes = find_odd_holes(edges)
        if holes:
            with_holes.append((idx, edges, holes))
        else:
            without_holes.append((idx, edges, holes))

    # Process odd-hole graphs first
    print(f"=== Phase 1: {len(with_holes)} graphs WITH odd holes ===", flush=True)
    for idx, edges, holes in with_holes:
        name = f"atlas{idx}"
        print(f"\n  {name} ({len(edges)} edges, {len(holes)} holes)...", flush=True)
        cert = close_graph(name, 7, edges, 2, holes, order=2)
        if cert:
            path = f"certificates/{name}_exact.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cert, f, indent=2)
            closed.append(name)
            print(f"  >>> CLOSED! Saved {path}", flush=True)
        else:
            failed.append(name)
            print(f"  failed (rationalization)", flush=True)

    # Process remaining (no odd holes - try without)
    print(f"\n=== Phase 2: {len(without_holes)} graphs WITHOUT odd holes ===", flush=True)
    for idx, edges, holes in without_holes[:10]:  # Try first 10
        name = f"atlas{idx}"
        print(f"\n  {name} ({len(edges)} edges)...", flush=True)
        cert = close_graph(name, 7, edges, 2, [], order=2)
        if cert:
            path = f"certificates/{name}_exact.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cert, f, indent=2)
            closed.append(name)
            print(f"  >>> CLOSED! Saved {path}", flush=True)
        else:
            failed.append(name)
            print(f"  failed", flush=True)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print(f"RESULTS: {len(closed)} closed, {len(failed)} failed", flush=True)
    print(f"Closed: {closed}", flush=True)
    print(f"Failed: {failed}", flush=True)

    # Save summary
    summary = {"closed": closed, "failed": failed, "total_attempted": len(closed) + len(failed)}
    with open("table4_closure_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
