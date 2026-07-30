"""Independent verifier for atlas#878 dual certificate at upper=2+1e-8.

No CVXPY dependency. Pure Fraction arithmetic.
Checks:
1. Graph consistency
2. Basis validity (square-free subsets through degree 2)
3. Dual matrix symmetry and rational entries
4. Affine constraints: <B_l, Z> = -coeff_l (non-norm), <B_norm, Z> = upper
5. Z is strictly positive definite (all LDL pivots > 0)
6. Certificate bound matches claimed upper_bound
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from problem import EDGES, VERTICES, PROBLEM_ID

PREFIX = "ATLAS878_CERT_RESULT="

def _canonical_word(word):
    items = list(word)
    sign = 1
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor-1] > items[cursor]:
            if tuple(sorted((items[cursor-1], items[cursor]))) in EDGES:
                sign = -sign
            items[cursor-1], items[cursor] = items[cursor], items[cursor-1]
            cursor -= 1
    reduced = []
    for item in items:
        if reduced and reduced[-1] == item:
            reduced.pop()
        else:
            reduced.append(item)
    return sign, sum(1 << item for item in reduced)

def _entry_label(left, right):
    n = len(VERTICES)
    counts = [0] * n
    for idx in left + right:
        counts[idx] += 1
    sign, mask = _canonical_word(tuple(reversed(left)) + right)
    vertices = tuple(i for i in VERTICES if mask & (1 << i))
    adjoint_sign, _ = _canonical_word(tuple(reversed(vertices)))
    if adjoint_sign < 0:
        return sign, None
    if mask and mask & (mask - 1) == 0:
        counts[mask.bit_length() - 1] += 1
        mask = 0
    return sign, (tuple(counts), mask)

def verify(path):
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('problem_id') != PROBLEM_ID:
        raise ValueError('wrong problem_id')
    graph = payload.get('graph', {})
    if graph.get('vertex_count') != len(VERTICES):
        raise ValueError('wrong vertex count')
    if {tuple(e) for e in graph.get('edges', [])} != set(EDGES):
        raise ValueError('certificate graph differs')

    basis = tuple(tuple(w) for w in payload['basis'])
    n = len(VERTICES)
    required = {subset for deg in range(3) for subset in combinations(range(n), deg)}
    if set(basis) != required:
        raise ValueError('basis must be degree-2 square-free subsets')

    # Parse dual matrix
    raw = payload['dual_matrix']
    size = len(basis)
    if len(raw) != size or any(len(row) != size for row in raw):
        raise ValueError('matrix shape mismatch')
    Z = [[Fraction(v) for v in row] for row in raw]
    if any(Z[r][c] != Z[c][r] for r in range(size) for c in range(r)):
        raise ValueError('matrix not symmetric')

    # Build label groups
    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col])
            if label is not None:
                groups[label].append((row, col, sign))

    # Compute objective coefficients
    basis_index = {w: i for i, w in enumerate(basis)}
    obj_diags = {basis_index[(v,)] for v in VERTICES}
    normalization = ((0,) * n, 0)

    # Check affine constraints
    checked = 0
    for label, members in groups.items():
        contraction = sum(s * (Z[r][c] if r == c else 2*Z[r][c]) for r, c, s in members)
        if label == normalization:
            expected = Fraction(payload['upper_bound']['fraction'])
        else:
            obj_coeff = sum(s for r, c, s in members if r == c and r in obj_diags)
            expected = Fraction(-obj_coeff)
        if contraction != expected:
            raise ValueError(f'affine fail at label {label}: {contraction} != {expected}')
        checked += 1

    # LDL positive definite check
    lower = [[Fraction(int(r==c)) for c in range(size)] for r in range(size)]
    diag = []
    for k in range(size):
        pivot = Z[k][k] - sum(lower[k][j]**2 * diag[j] for j in range(k))
        if pivot <= 0:
            raise ValueError(f'non-positive LDL pivot {k}: {pivot}')
        diag.append(pivot)
        for i in range(k+1, size):
            lower[i][k] = (Z[i][k] - sum(lower[i][j]*lower[k][j]*diag[j] for j in range(k))) / pivot

    claimed = Fraction(payload['upper_bound']['fraction'])
    return {
        'valid': True,
        'problem_id': PROBLEM_ID,
        'upper_bound_fraction': str(claimed),
        'upper_bound': float(claimed),
        'matrix_size': size,
        'affine_constraints_checked': checked,
        'positive_ldl_pivots': len(diag),
        'minimum_ldl_pivot': str(min(diag)),
    }

def main():
    if len(sys.argv) != 2:
        print('usage: verify_1e8_certificate.py CERT.json', file=sys.stderr)
        return 2
    try:
        result = verify(Path(sys.argv[1]))
    except Exception as exc:
        result = {'valid': False, 'error': f'{type(exc).__name__}: {exc}'}
    print(PREFIX + json.dumps(result, sort_keys=True), flush=True)
    return 0 if result.get('valid') else 1

if __name__ == '__main__':
    raise SystemExit(main())
