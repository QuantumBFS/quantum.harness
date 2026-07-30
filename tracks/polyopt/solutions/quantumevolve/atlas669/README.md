# Challenge #232 — Atlas graph 669 (Table-4 closed constant)

## Summary

Seven Hermitian unitary observables with anti-commutation graph = atlas index 669
among 7-vertex graphs (11 edges, α = 2, ϑ₁ = √5).

**Result (hope signal):** 2 ≤ β(G) ≤ 200000001/100000000 = 2 + 10⁻⁸

This is a tight two-sided bound with gap = 10⁻⁸, well below the 10⁻⁶ hope-signal
threshold in the #232 verification plan.

## Exact certificate

The committed certificate proves β ≤ 2 + 10⁻⁸ via a 29×29 rational Gram matrix
(complete level-2 square-free basis). The independent verifier checks 112 affine
coefficient identities and 29 strictly positive exact LDL pivots.

```text
challenges/omnievolve/.venv/Scripts/python.exe \
  tracks/polyopt/solutions/quantumevolve/atlas669/verify_dual_certificate.py \
  tracks/polyopt/solutions/quantumevolve/atlas669/certificates/dual_certificate_exact.json
```

## Why exact closure (β ≤ 2) is structurally obstructed

When β = α = 2, the dual optimal Z* is positive semidefinite but singular
(complementary slackness forces Z*·M* = 0 with M* ≠ 0). The standard SOHS
certificate framework requires Z strictly positive definite (interior point),
so rationalization at upper = 2 always fails — there is no interior dual feasible
point at the exact bound.

The paper (arXiv:2310.00612) closes 18 of 43 Table-4 graphs using odd-hole
inequalities (Eq. 25) that make the dual strictly PD. For atlas#669, the 4
induced C₅ odd-holes have zero dual multipliers at both level-1 and level-2,
meaning they are not active and cannot provide the needed interior margin.

This graph falls into the "hope signal" category: the hierarchy converges
numerically to 2 (gap < 10⁻⁹ at level-2), but exact rational closure requires
either a novel certification technique for singular duals or a proof that β = 2
via an explicit quantum strategy achieving the bound.

## Hierarchy convergence

| Level | Matrix size | Value | Gap from 2 |
|-------|------------|-------|------------|
| 1 | 8×8 | 2.236068 | 2.4×10⁻¹ |
| 2 | 29×29 | 2.0000000027 | 2.7×10⁻⁹ |
| 2 + odd-hole | 29×29 | 2.0000000003 | 3.3×10⁻¹⁰ |
| 3 | 64×64 | 2.0000000018 | 1.8×10⁻⁹ |

## Graph data

- Vertices: 7
- Edges (11): (0,1), (0,2), (0,3), (0,4), (1,2), (1,6), (2,6), (3,4), (3,5), (4,5), (5,6)
- Independence number α = 2
- Induced C₅ odd-holes: (0,1,3,5,6), (0,1,4,5,6), (0,2,3,5,6), (0,2,4,5,6)

## Files

- `problem.py` — immutable graph definition
- `theta_relaxation.py` — state-polynomial SDP hierarchy solver
- `export_dual_certificate.py` — numeric + exact-rational certificate exporter
- `verify_dual_certificate.py` — independent exact verifier
- `certificates/dual_certificate_exact.json` — the proof (upper = 2 + 10⁻⁸)
- `certificates/dual_certificate_numeric.json` — floating-point diagnostics
