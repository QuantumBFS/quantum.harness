# Exact no-common-quadratic-metric certificate for the leading oddcycle pair

Consider the two rational matrices

```text
B0 = B(1/1000, 1, 1)
B1 = B(4/5, 1, 1)
```

and the four-letter alphabet
`{B0, B0^T, B1, B1^T}`.  The numerical common-metric SDP returns zero
margin, but zero numerical margin alone is not a novelty theorem.  The
frozen exact certificate in `oracle/oddcycle_metric_dual.py` upgrades this
observation to an algebraic exclusion.

## Certificate

The oracle stores four rational symmetric positive-definite matrices
`X0, X1, Y0, Y1`.  Exact fraction arithmetic verifies

```text
sum_j [
    Xj - Bj Xj Bj^T
  + Yj - Bj^T Yj Bj
] = 0
```

and `sum_j Tr(Xj + Yj) = 1`.  Positive definiteness of every multiplier is
proved by Sylvester's criterion using exact integer leading principal
minors.

If a real symmetric `R` made all four Lyapunov gaps

```text
R - Bj^T R Bj > 0
R - Bj R Bj^T > 0
```

strictly positive definite, taking Frobenius inner products with `Xj` and
`Yj` would give a strictly positive sum.  Moving each `Bj` through the
trace turns that same sum into the inner product of `R` with the exact
zero matrix above, a contradiction.  Therefore no such common `R`
exists.

This excludes only the specific common *quadratic* split-contraction
metric inequalities tested above.  It does not exclude the common
nonquadratic cone preserved by the inverse alphabet, nor the full
10-Majorana Wei contraction framework.  Arbitrary-word determinant
positivity is proved independently by the four-state certificate in
`ODDCYCLE_PATH_METRIC_CERTIFICATE.md`; the combination shows that the
finite-state quadratic certificate is strictly more expressive than a
one-state quadratic metric for this alphabet.

## Exact replay

From `tracks/qmc/solutions/no-negative-vibes`:

```bash
PYTHONPATH=. python -m oracle.oddcycle_metric_dual --exact-leading-pair
PYTHONPATH=. python -m pytest -q tests/test_oddcycle_metric_dual.py
```
