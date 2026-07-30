"""Extended exact closure campaign: more graphs, including perfect graphs at level 1."""
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

def try_closure(name, n, edges, alpha, order=2):
    edges = frozenset(tuple(sorted(e)) for e in edges)
    basis = tuple(sorted(basis_subsets(n, order), key=lambda x: (len(x), x)))
    size = len(basis)
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
        print(f"  {name}: SCS failed ({prob.status})"); return False
    Z_num = np.asarray(Z.value, dtype=float)
    m = float(val)
    if m < -1e-9:
        print(f"  {name}: margin={m:.2e} (beta > {alpha})"); return False

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
            print(f"  {name}: CLOSED! {pp} pos + {zp} zero pivots (denom={denom:.0e})")
            # Save
            cert_dir = Path(__file__).parent / "certificates"
            cert_dir.mkdir(parents=True, exist_ok=True)
            safe = name.replace(" ","_").replace("(","").replace(")","").replace("\\","")
            def fs(f): return str(f.numerator) if f.denominator==1 else f"{f.numerator}/{f.denominator}"
            payload = {"graph_name": name, "vertex_count": n,
                       "edges": [list(e) for e in sorted(edges)],
                       "independence_number": alpha, "upper_bound": str(upper),
                       "positive_pivots": pp, "zero_pivots": zp, "denominator": denom,
                       "basis": [list(w) for w in basis],
                       "dual_matrix": [[fs(Q[r][c]) for c in range(size)] for r in range(size)]}
            (cert_dir / f"{safe}_exact.json").write_text(json.dumps(payload, indent=2))
            return True
    print(f"  {name}: rationalization failed"); return False


def main():
    print("EXTENDED EXACT CLOSURE CAMPAIGN", flush=True)
    results = {}

    # --- alpha=2 graphs (level 2) ---
    # Complement of C6 (D6 symmetry, 6 vertices, 9 edges, alpha=2)
    c6 = {(0,1),(1,2),(2,3),(3,4),(4,5),(0,5)}
    comp_c6 = set(combinations(range(6),2)) - c6
    results["comp_C6"] = try_closure("comp_C6", 6, comp_c6, 2, order=2)

    # K4 minus edge + 2 universal vertices? Try K2,2,2 (octahedral = K6\matching, already done)
    # Try: 5-wheel W5 = C4 + universal vertex (5 vertices, alpha=2)
    w5 = {(0,1),(1,2),(2,3),(3,0),(4,0),(4,1),(4,2),(4,3)}
    results["W5"] = try_closure("W5_wheel", 5, w5, 2, order=2)

    # K4 (alpha=1, trivial but tests the pipeline)
    k4 = set(combinations(range(4),2))
    results["K4"] = try_closure("K4", 4, k4, 1, order=2)

    # --- alpha=3 perfect graphs (level 1 should suffice) ---
    # C6 (bipartite, alpha=3, D6 symmetry)
    results["C6"] = try_closure("C6_bipartite", 6, c6, 3, order=1)

    # K3,3 (complete bipartite, alpha=3, S3xS3 symmetry order 72)
    k33 = {(i,j) for i in range(3) for j in range(3,6)}
    results["K33"] = try_closure("K3_3", 6, k33, 3, order=1)

    # K4,4 minus... actually K3,3 is good. Try K4 (alpha=1) at level 1
    results["K4_L1"] = try_closure("K4_level1", 4, k4, 1, order=1)

    # --- Summary ---
    print("\n" + "="*50)
    closed = [k for k,v in results.items() if v]
    failed = [k for k,v in results.items() if not v]
    print(f"CLOSED: {closed}")
    print(f"FAILED: {failed}")
    print(f"Total closures this session: {len(closed)}")

if __name__ == "__main__":
    main()
