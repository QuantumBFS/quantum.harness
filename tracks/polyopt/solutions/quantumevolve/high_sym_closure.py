"""Try SCS + PSD exact closure on high-symmetry alpha=2 graphs.

Key insight from C5 success: high symmetry -> affine correction = 0 -> PSD preserved.
Candidates: complement of C7 (D7 symmetry), complement of perfect matching (S3xZ2).
"""
from __future__ import annotations
import json
import sys
from itertools import combinations
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import cvxpy as cp
import numpy as np


def basis_subsets(n, order):
    return tuple(
        subset for size in range(order + 1)
        for subset in combinations(range(n), size)
    )

def _canonical_word(word, edges):
    items = list(word)
    sign = 1
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor - 1] > items[cursor]:
            left, right = items[cursor - 1], items[cursor]
            if tuple(sorted((left, right))) in edges:
                sign = -sign
            items[cursor - 1], items[cursor] = right, left
            cursor -= 1
    reduced = []
    for item in items:
        if reduced and reduced[-1] == item:
            reduced.pop()
        else:
            reduced.append(item)
    return sign, sum(1 << item for item in reduced)

def _adjoint_sign(mask, edges):
    vertices = tuple(i for i in range(mask.bit_length()) if mask & (1 << i))
    sign, _ = _canonical_word(tuple(reversed(vertices)), edges)
    return sign

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


def build_model(n, edges, order=2):
    edges = frozenset(tuple(sorted(e)) for e in edges)
    basis = tuple(sorted(basis_subsets(n, order), key=lambda x: (len(x), x)))
    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col], n, edges)
            if label is not None:
                groups[label].append((row, col, sign))
    labels = tuple(groups)
    matrices = []
    for label in labels:
        M = np.zeros((len(basis), len(basis)))
        for r, c, s in groups[label]:
            M[r, c] = s
            M[c, r] = s
        matrices.append(M)
    basis_idx = {w: i for i, w in enumerate(basis)}
    obj = np.zeros((len(basis), len(basis)))
    for v in range(n):
        idx = basis_idx[(v,)]
        obj[idx, idx] = 1.0
    coeffs = np.array([np.sum(obj * M) for M in matrices])
    norm_idx = labels.index(((0,) * n, 0))
    return {"basis": basis, "groups": groups, "labels": labels,
            "matrices": matrices, "coeffs": coeffs, "norm_idx": norm_idx, "n": n}


def try_exact_closure(name, n, edges, alpha):
    """Attempt exact PSD closure for a graph."""
    print(f"\n{'='*60}")
    print(f"  {name}: n={n}, |E|={len(edges)}, alpha={alpha}")
    print(f"{'='*60}", flush=True)

    model = build_model(n, edges, order=2)
    size = len(model["basis"])
    print(f"  Basis size: {size}", flush=True)

    # Solve with SCS
    matrices = model["matrices"]
    coeffs = model["coeffs"]
    norm_idx = model["norm_idx"]
    upper_val = float(alpha)

    Z = cp.Variable((size, size), symmetric=True)
    margin = cp.Variable()
    constraints = [
        Z - margin * np.eye(size) >> 0,
        cp.sum(cp.multiply(matrices[norm_idx], Z)) <= upper_val,
    ]
    constraints.extend(
        cp.sum(cp.multiply(M, Z)) == -coeffs[i]
        for i, M in enumerate(matrices) if i != norm_idx
    )
    prob = cp.Problem(cp.Maximize(margin), constraints)
    val = prob.solve(solver="SCS", eps=1e-14, max_iters=100000, verbose=False)

    if prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        print(f"  SCS failed: {prob.status}")
        return False

    Z_num = np.asarray(Z.value, dtype=float)
    margin_val = float(val)
    print(f"  SCS margin: {margin_val:.2e}", flush=True)

    if margin_val < -1e-9:
        print(f"  Margin too negative, skipping")
        return False

    # Rationalize and verify
    upper = Fraction(alpha)
    for denom in [10**10, 10**11, 10**12, 10**13, 10**14]:
        Q = [[Fraction(round(float(Z_num[r, c]) * denom), denom)
              for c in range(size)] for r in range(size)]
        for r in range(size):
            for c in range(r):
                Q[r][c] = Q[c][r]

        # Affine correction
        groups = model["groups"]
        labels = model["labels"]
        targets = [Fraction(-int(round(v))) for v in coeffs]
        targets[norm_idx] = upper
        max_corr = 0.0
        for idx, label in enumerate(labels):
            members = groups[label]
            current = Fraction(0)
            for r, c, s in members:
                current += s * (Q[r][c] if r == c else 2 * Q[r][c])
            r, c, s = min(members, key=lambda x: 0 if x[0] == x[1] else 1)
            coeff = Fraction(s if r == c else 2 * s)
            correction = (targets[idx] - current) / coeff
            Q[r][c] += correction
            Q[c][r] = Q[r][c]
            if abs(float(correction)) > max_corr:
                max_corr = abs(float(correction))

        # LDL PSD check
        L = [[Fraction(int(r == c)) for c in range(size)] for r in range(size)]
        D = []
        ok = True
        zero_pivots = 0
        for k in range(size):
            pivot = Q[k][k] - sum(L[k][j]**2 * D[j] for j in range(k))
            if pivot < 0:
                ok = False
                break
            if pivot == 0:
                zero_pivots += 1
                D.append(Fraction(0))
                for i in range(k + 1, size):
                    schur = Q[i][k] - sum(L[i][j] * L[k][j] * D[j] for j in range(k))
                    if schur != 0:
                        ok = False
                        break
                if not ok:
                    break
                continue
            D.append(pivot)
            for i in range(k + 1, size):
                schur = Q[i][k] - sum(L[i][j] * L[k][j] * D[j] for j in range(k))
                L[i][k] = schur / pivot

        if ok:
            pos_pivots = size - zero_pivots
            min_pos = min(p for p in D if p > 0) if any(p > 0 for p in D) else None
            print(f"  *** SUCCESS at denom={denom:.0e}: {pos_pivots} pos + {zero_pivots} zero pivots, max_corr={max_corr:.2e}")
            if min_pos:
                print(f"      min positive pivot: {float(min_pos):.4f}")

            # Save certificate
            cert_dir = Path("certificates")
            cert_dir.mkdir(parents=True, exist_ok=True)
            safe_name = name.replace(" ", "_").replace("(", "").replace(")", "")
            cert_path = cert_dir / f"{safe_name}_exact_psd.json"

            def frac_str(f):
                return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"

            payload = {
                "graph_name": name,
                "vertex_count": n,
                "edges": [list(e) for e in sorted(edges)],
                "independence_number": alpha,
                "upper_bound": str(upper),
                "certificate_type": "exact-rational-PSD-dual-sohs",
                "positive_pivots": pos_pivots,
                "zero_pivots": zero_pivots,
                "denominator": denom,
                "basis": [list(w) for w in model["basis"]],
                "dual_matrix": [[frac_str(Q[r][c]) for c in range(size)] for r in range(size)],
            }
            cert_path.write_text(json.dumps(payload, indent=2))
            print(f"      Saved: {cert_path}")
            return True
        else:
            if denom == 10**12:
                print(f"  denom={denom:.0e}: FAIL (max_corr={max_corr:.2e})")

    print(f"  All denominators failed")
    return False


def main():
    print("HIGH-SYMMETRY GRAPH EXACT CLOSURE CAMPAIGN")
    print("=" * 60, flush=True)

    results = {}

    # 1. Complement of C7 (D7 symmetry, order 14)
    # C7 edges: (0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(0,6)
    # Complement: all other pairs
    c7_edges = {(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(0,6)}
    all_7 = set(combinations(range(7), 2))
    comp_c7 = all_7 - c7_edges
    results["comp_C7"] = try_exact_closure("complement of C7", 7, comp_c7, alpha=2)

    # 2. Complement of perfect matching on 6 vertices (S3 x Z2, order 48)
    # Matching: (0,1), (2,3), (4,5)
    # Complement of matching = K6 minus matching edges
    matching = {(0,1), (2,3), (4,5)}
    all_6 = set(combinations(range(6), 2))
    k6_minus_matching = all_6 - matching
    results["K6_minus_matching"] = try_exact_closure("K6 minus matching", 6, k6_minus_matching, alpha=2)

    # 3. C5 (control - should succeed)
    c5_edges = {(0,1),(1,2),(2,3),(3,4),(0,4)}
    results["C5"] = try_exact_closure("C5 (control)", 5, c5_edges, alpha=2)

    # 4. Paley graph on 5 vertices (= C5, skip)
    # 5. Complement of C5 (= C5, self-complementary)

    # 6. Circulant graph C7(1,2) - 7 vertices, connect if distance 1 or 2
    circ7_12 = set()
    for i in range(7):
        for d in [1, 2]:
            j = (i + d) % 7
            circ7_12.add(tuple(sorted((i, j))))
    # alpha of C7(1,2): this is the complement of C7(3) = complement of C7
    # Actually C7(1,2) has 14 edges, same as complement of C7
    # Let me check: C7(1) = C7 (7 edges), C7(1,2) has 14 edges
    # complement of C7 has 21-7=14 edges. Are they the same?
    # C7(1,2) connects i to i+1 and i+2. Complement of C7 connects i to i+2, i+3, i+4.
    # These are different! C7(1,2) has edges at distance 1,2; complement has distance 2,3.
    # Actually for 7 vertices: distances are 1,2,3. Complement of C7 (distance 1) = distance 2,3.
    # C7(1,2) = distance 1,2. These are different graphs.
    # alpha of C7(1,2): independent set = no two vertices at distance 1 or 2.
    # Max such set: {0, 3, 5}? dist(0,3)=3 ok, dist(0,5)=2 NO.
    # {0, 3, 6}? dist(0,3)=3, dist(0,6)=1 NO.
    # {0, 3}: dist=3 ok. Can we add more? {0,3,5}: dist(3,5)=2 NO.
    # {0,3,6}: dist(0,6)=1 NO. {0,4}: dist=3 ok (via 0-1-2-3-4). Actually dist(0,4)=min(4,3)=3.
    # {0,3}: size 2. {0,4}: dist(0,4)=3 ok. {0,3,?}: need dist>=3 from both 0 and 3.
    # From 0: need dist>=3, so vertices 3,4. From 3: need dist>=3, so vertices 0,6.
    # Intersection: {0,3} intersect {3,4} intersect {0,6} = empty for third vertex.
    # So alpha(C7(1,2)) = 2.
    results["C7_12"] = try_exact_closure("Circulant C7(1,2)", 7, circ7_12, alpha=2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {name}: {'CLOSED' if ok else 'FAILED'}")


if __name__ == "__main__":
    main()
