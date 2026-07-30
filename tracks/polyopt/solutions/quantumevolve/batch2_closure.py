"""Batch 2 exact closure campaign: more perfect graphs + Petersen.

Strategy: perfect graphs (bipartite, complete multipartite) close at level 1.
Petersen graph: theta = alpha = 4 (strongly regular), should also close.
"""
from __future__ import annotations
import json, sys
from itertools import combinations
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import cvxpy as cp
import numpy as np


def basis_subsets(n, order):
    return tuple(subset for size in range(order + 1) for subset in combinations(range(n), size))

def _canonical_word(word, edges):
    items = list(word); sign = 1
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor-1] > items[cursor]:
            l, r = items[cursor-1], items[cursor]
            if tuple(sorted((l,r))) in edges: sign = -sign
            items[cursor-1], items[cursor] = r, l; cursor -= 1
    reduced = []
    for item in items:
        if reduced and reduced[-1] == item: reduced.pop()
        else: reduced.append(item)
    return sign, sum(1 << i for i in reduced)

def _adjoint_sign(mask, edges):
    v = tuple(i for i in range(mask.bit_length()) if mask & (1<<i))
    s, _ = _canonical_word(tuple(reversed(v)), edges); return s

def _entry_label(left, right, n, edges):
    counts = [0]*n
    for i in left+right: counts[i] += 1
    sign, mask = _canonical_word(tuple(reversed(left))+right, edges)
    if _adjoint_sign(mask, edges) < 0: return sign, None
    if mask and mask & (mask-1) == 0:
        counts[mask.bit_length()-1] += 1; mask = 0
    return sign, (tuple(counts), mask)

def try_closure(name, n, edges, alpha, order=1):
    edges = frozenset(tuple(sorted(e)) for e in edges)
    basis = tuple(sorted(basis_subsets(n, order), key=lambda x: (len(x), x)))
    size = len(basis)
    print(f"\n  {name}: n={n}, |E|={len(edges)}, alpha={alpha}, order={order}, basis={size}", flush=True)

    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, size):
            sign, label = _entry_label(left, basis[col], n, edges)
            if label is not None: groups[label].append((row, col, sign))
    labels = tuple(groups)
    matrices = []
    for label in labels:
        M = np.zeros((size, size))
        for r, c, s in groups[label]: M[r,c] = s; M[c,r] = s
        matrices.append(M)
    basis_idx = {w: i for i, w in enumerate(basis)}
    obj = np.zeros((size, size))
    for v in range(n): obj[basis_idx[(v,)], basis_idx[(v,)]] = 1.0
    coeffs = np.array([np.sum(obj * M) for M in matrices])
    norm_idx = labels.index(((0,)*n, 0))

    # SCS dual
    Z = cp.Variable((size, size), symmetric=True)
    margin = cp.Variable()
    upper_val = float(alpha)
    constraints = [Z - margin*np.eye(size) >> 0,
                   cp.sum(cp.multiply(matrices[norm_idx], Z)) <= upper_val]
    constraints.extend(cp.sum(cp.multiply(M, Z)) == -coeffs[i]
                       for i, M in enumerate(matrices) if i != norm_idx)
    prob = cp.Problem(cp.Maximize(margin), constraints)
    val = prob.solve(solver="SCS", eps=1e-14, max_iters=100000, verbose=False)
    if prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        print(f"    SCS failed ({prob.status})"); return False
    Z_num = np.asarray(Z.value, dtype=float)
    m = float(val)
    print(f"    SCS margin: {m:.2e}", flush=True)
    if m < -1e-9:
        print(f"    beta > {alpha} (quantum advantage!)"); return False

    # Rationalize
    upper = Fraction(alpha)
    for denom in [10**10, 10**11, 10**12, 10**13]:
        Q = [[Fraction(round(float(Z_num[r,c])*denom), denom) for c in range(size)] for r in range(size)]
        for r in range(size):
            for c in range(r): Q[r][c] = Q[c][r]
        targets = [Fraction(-int(round(v))) for v in coeffs]; targets[norm_idx] = upper
        for idx, label in enumerate(labels):
            members = groups[label]
            current = sum(s*(Q[r][c] if r==c else 2*Q[r][c]) for r,c,s in members)
            r,c,s = min(members, key=lambda x: 0 if x[0]==x[1] else 1)
            coeff = Fraction(s if r==c else 2*s)
            Q[r][c] += (targets[idx]-current)/coeff; Q[c][r] = Q[r][c]
        # LDL
        L = [[Fraction(int(r==c)) for c in range(size)] for r in range(size)]
        D = []; ok = True; zp = 0
        for k in range(size):
            pivot = Q[k][k] - sum(L[k][j]**2*D[j] for j in range(k))
            if pivot < 0: ok = False; break
            if pivot == 0:
                zp += 1; D.append(Fraction(0))
                for i in range(k+1, size):
                    if Q[i][k] - sum(L[i][j]*L[k][j]*D[j] for j in range(k)) != 0: ok = False; break
                if not ok: break
                continue
            D.append(pivot)
            for i in range(k+1, size):
                L[i][k] = (Q[i][k] - sum(L[i][j]*L[k][j]*D[j] for j in range(k)))/pivot
        if ok:
            pp = size - zp
            print(f"    *** CLOSED! {pp} pos + {zp} zero pivots (denom={denom:.0e})")
            # Save certificate
            cert_dir = Path(__file__).parent / "certificates"
            cert_dir.mkdir(parents=True, exist_ok=True)
            safe = name.replace(" ","_").replace("(","").replace(")","").replace("\\","").replace(",","")
            def fs(f): return str(f.numerator) if f.denominator==1 else f"{f.numerator}/{f.denominator}"
            payload = {"graph_name": name, "vertex_count": n,
                       "edges": [list(e) for e in sorted(edges)],
                       "independence_number": alpha, "upper_bound": str(upper),
                       "certificate_type": "exact-rational-PSD-dual-sohs",
                       "positive_pivots": pp, "zero_pivots": zp, "denominator": denom,
                       "basis": [list(w) for w in basis],
                       "dual_matrix": [[fs(Q[r][c]) for c in range(size)] for r in range(size)]}
            (cert_dir / f"{safe}_exact.json").write_text(json.dumps(payload, indent=2))
            return True
    print(f"    rationalization failed"); return False


def main():
    print("BATCH 2: EXACT CLOSURE CAMPAIGN")
    print("=" * 60, flush=True)
    results = {}

    # --- Complete graphs (alpha=1, level 1) ---
    k5 = set(combinations(range(5), 2))
    results["K5"] = try_closure("K5", 5, k5, 1, order=1)

    k6 = set(combinations(range(6), 2))
    results["K6"] = try_closure("K6", 6, k6, 1, order=1)

    # --- Complete bipartite (alpha=max part, level 1) ---
    k44 = {(i,j) for i in range(4) for j in range(4,8)}
    results["K44"] = try_closure("K4_4", 8, k44, 4, order=1)

    k55 = {(i,j) for i in range(5) for j in range(5,10)}
    results["K55"] = try_closure("K5_5", 10, k55, 5, order=1)

    # --- Even cycles (bipartite, alpha=n/2, level 1) ---
    c8 = {(i, (i+1) % 8) for i in range(8)}
    results["C8"] = try_closure("C8", 8, c8, 4, order=1)

    c10 = {(i, (i+1) % 10) for i in range(10)}
    results["C10"] = try_closure("C10", 10, c10, 5, order=1)

    # --- Complete tripartite K3,3,3 (alpha=3, level 1) ---
    k333 = set()
    for part_a in range(3):
        for part_b in range(part_a+1, 3):
            for i in range(3):
                for j in range(3):
                    k333.add((part_a*3 + i, part_b*3 + j))
    results["K333"] = try_closure("K3_3_3", 9, k333, 3, order=1)

    # --- Petersen graph (strongly regular, theta=alpha=4) ---
    # Standard construction: outer cycle 0-4, inner star 5-9, spokes
    petersen = set()
    for i in range(5):
        petersen.add(tuple(sorted((i, (i+1) % 5))))  # outer cycle
        petersen.add(tuple(sorted((i+5, (i+2) % 5 + 5))))  # inner star (pentagram)
        petersen.add(tuple(sorted((i, i+5))))  # spokes
    results["Petersen"] = try_closure("Petersen", 10, petersen, 4, order=1)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    closed = [k for k, v in results.items() if v]
    failed = [k for k, v in results.items() if not v]
    print(f"CLOSED ({len(closed)}): {closed}")
    print(f"FAILED ({len(failed)}): {failed}")
    print(f"Total new closures: {len(closed)}")


if __name__ == "__main__":
    main()
