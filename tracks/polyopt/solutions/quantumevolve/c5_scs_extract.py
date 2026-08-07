"""Extract SCS dual solution at upper=2 and attempt exact rationalization.

SCS gives margin = +3.6e-15 at upper=2, suggesting the true SDP value IS 2.
This script extracts the SCS dual and attempts to rationalize it to an exact
PSD certificate.
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

N = 5
EDGES = frozenset([(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)])
UPPER = Fraction(2)


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


def build_model():
    basis = tuple(sorted(basis_subsets(N, 2), key=lambda x: (len(x), x)))
    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col], N, EDGES)
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
    for v in range(N):
        idx = basis_idx[(v,)]
        obj[idx, idx] = 1.0
    coeffs = np.array([np.sum(obj * M) for M in matrices])
    norm_idx = labels.index(((0,) * N, 0))
    return {
        "basis": basis, "groups": groups, "labels": labels,
        "matrices": matrices, "coeffs": coeffs, "norm_idx": norm_idx,
    }


def solve_scs_dual(model, upper_val):
    """Solve dual with SCS and extract Z."""
    matrices = model["matrices"]
    coeffs = model["coeffs"]
    norm_idx = model["norm_idx"]
    size = len(model["basis"])

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
    val = prob.solve(solver="SCS", eps=1e-13, max_iters=50000, verbose=False)

    if prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        print(f"SCS failed: {prob.status}")
        return None, None

    Z_val = np.asarray(Z.value, dtype=float)
    margin_val = float(val)
    print(f"SCS margin: {margin_val:.2e}")
    print(f"Z eigenvalues: {np.linalg.eigvalsh(Z_val)}")
    return Z_val, margin_val


def rationalize_and_verify(model, Z_num, upper, denom):
    """Rationalize Z and verify PSD with exact arithmetic."""
    size = Z_num.shape[0]

    # Rationalize
    Q = [[Fraction(round(float(Z_num[r, c]) * denom), denom)
          for c in range(size)] for r in range(size)]
    for r in range(size):
        for c in range(r):
            Q[r][c] = Q[c][r]

    # Affine correction
    groups = model["groups"]
    labels = model["labels"]
    coeffs = model["coeffs"]
    norm_idx = model["norm_idx"]
    targets = [Fraction(-int(round(v))) for v in coeffs]
    targets[norm_idx] = upper

    corrections = []
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
        corrections.append(float(correction))

    print(f"  Max affine correction: {max(abs(c) for c in corrections):.2e}")

    # LDL with PSD allowance
    n = size
    L = [[Fraction(int(r == c)) for c in range(n)] for r in range(n)]
    D = []
    zero_pivots = 0
    min_positive = None

    for k in range(n):
        pivot = Q[k][k] - sum(L[k][j]**2 * D[j] for j in range(k))

        if pivot < 0:
            print(f"  FAIL: negative pivot at k={k}: {float(pivot):.2e}")
            return False, None, None

        if pivot == 0:
            zero_pivots += 1
            D.append(Fraction(0))
            # Check Schur complement row is zero
            for i in range(k + 1, n):
                schur = Q[i][k] - sum(L[i][j] * L[k][j] * D[j] for j in range(k))
                if schur != 0:
                    print(f"  FAIL: zero pivot but nonzero Schur[{i},{k}]: {float(schur):.2e}")
                    return False, None, None
            continue

        D.append(pivot)
        if min_positive is None or pivot < min_positive:
            min_positive = pivot
        for i in range(k + 1, n):
            schur = Q[i][k] - sum(L[i][j] * L[k][j] * D[j] for j in range(k))
            L[i][k] = schur / pivot

    print(f"  SUCCESS: {zero_pivots} zero pivots, {n - zero_pivots} positive pivots")
    if min_positive:
        print(f"  Min positive pivot: {float(min_positive):.2e}")
    return True, D, zero_pivots


def main():
    print("=" * 70)
    print("SCS DUAL EXTRACTION + EXACT RATIONALIZATION FOR C5")
    print("=" * 70, flush=True)

    model = build_model()
    size = len(model["basis"])
    print(f"Basis size: {size}")

    # Solve with SCS at upper=2
    print("\n--- Solving dual at upper=2 with SCS ---", flush=True)
    Z_num, margin = solve_scs_dual(model, 2.0)
    if Z_num is None:
        return 1

    # Try rationalization with increasing denominators
    print("\n--- Rationalization attempts ---", flush=True)
    for denom in [10**6, 10**8, 10**10, 10**12]:
        print(f"\nDenom = {denom:.0e}:", flush=True)
        success, D, zero_count = rationalize_and_verify(model, Z_num, UPPER, denom)
        if success:
            print(f"\n*** EXACT PSD CERTIFICATE FOUND ***")
            print(f"Upper bound: {UPPER}")
            print(f"Zero pivots: {zero_count}")
            print(f"Positive pivots: {size - zero_count}")

            # Save certificate
            cert_dir = Path("certificates")
            cert_dir.mkdir(parents=True, exist_ok=True)
            cert_path = cert_dir / "c5_exact_psd_scs.json"

            # Reconstruct Q for saving
            Q = [[Fraction(round(float(Z_num[r, c]) * denom), denom)
                  for c in range(size)] for r in range(size)]
            for r in range(size):
                for c in range(r):
                    Q[r][c] = Q[c][r]
            # Apply affine corrections
            groups = model["groups"]
            labels = model["labels"]
            coeffs = model["coeffs"]
            norm_idx = model["norm_idx"]
            targets = [Fraction(-int(round(v))) for v in coeffs]
            targets[norm_idx] = UPPER
            for idx, label in enumerate(labels):
                members = groups[label]
                current = Fraction(0)
                for r, c, s in members:
                    current += s * (Q[r][c] if r == c else 2 * Q[r][c])
                r, c, s = min(members, key=lambda x: 0 if x[0] == x[1] else 1)
                coeff = Fraction(s if r == c else 2 * s)
                Q[r][c] += (targets[idx] - current) / coeff
                Q[c][r] = Q[r][c]

            payload = {
                "graph": "C5",
                "vertices": N,
                "edges": [list(e) for e in sorted(EDGES)],
                "upper_bound": str(UPPER),
                "certificate_type": "exact-rational-PSD-dual",
                "solver": "SCS",
                "denominator": denom,
                "zero_pivots": zero_count,
                "positive_pivots": size - zero_count,
                "basis": [list(w) for w in model["basis"]],
                "dual_matrix": [[str(Q[r][c]) for c in range(size)] for r in range(size)],
            }
            cert_path.write_text(json.dumps(payload, indent=2))
            print(f"Certificate saved to {cert_path}")
            return 0

    print("\nFailed to find exact certificate")
    return 1


if __name__ == "__main__":
    sys.exit(main())
