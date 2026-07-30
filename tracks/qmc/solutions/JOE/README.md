# JOE — Challenge 15

## Team

| | |
|---|---|
| **Team name** | JOE |
| **Members** | Bei Qiao (乔北), Institute of Physics, Chinese Academy of Sciences (IOP) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Construct an exchange-antisymmetric, SO(3)-equivariant neural quantum state for the ν = 1/3 chiral graviton and compute the gap Δ = E(L=2) − E(L=0). |
| **Catalog issue** | Addresses #15. |
| **Track** | `qmc` — Variational Monte Carlo / Neural Quantum States. |

## Working repository

- [Immutable reviewer-ready snapshot `a74b92a`](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/tree/a74b92a7da96f1eaceebd57f550e0405cf6c04f5)
- [Concise Challenge 15 review](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/a74b92a7da96f1eaceebd57f550e0405cf6c04f5/challenges/15-chiral-graviton/CHALLENGE15_REVIEW.md)
- [Projected-CF Pfaffian derivation and implementation scope](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/a74b92a7da96f1eaceebd57f550e0405cf6c04f5/challenges/15-chiral-graviton/PROJECTED_CF_PFAFFIAN.md)
- [Reproduction guide](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/a74b92a7da96f1eaceebd57f550e0405cf6c04f5/challenges/15-chiral-graviton/REPRODUCIBILITY.md)
- [Machine-readable \(N=4\) Pfaffian oracle](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/a74b92a7da96f1eaceebd57f550e0405cf6c04f5/challenges/15-chiral-graviton/results/projected_cf_pfaffian_N4_oracle.json)

## Verified finite-size results

For \(N=4\), the joint VMC calculation gives

```math
E_0/E_C=1.871850\pm0.001026,
\qquad
E_2/E_C=2.004406\pm0.003022,
```

and

```math
\Delta_4/E_C=0.132556\pm0.002941.
```

The corresponding exact-diagonalization value is

```math
\Delta_4^{\mathrm{ED}}/E_C=0.131856754927,
```

so the VMC and ED gaps differ by \(0.24\) Monte Carlo standard errors. This
closes the small-system validation loop; it is not a thermodynamic-limit gap
claim. The snapshot contains 84 project tests and 61 independent Stage-1
Fock-oracle tests.

The newer projected-CF route constructs the pure rank-two broken-pair tangent

```math
\Psi_{2,M}(X)
=(-1)^P
\left.
\frac{d}{d\epsilon}
\operatorname{Pf}\!\left(G+\epsilon B^M\right)
\right|_{\epsilon=0}.
```

At \(N=4\), its two active channels span the complete
\(\mu_2=2\) multiplicity space. The deterministic certificate reports

```text
|E₂(Pfaffian) − E₂(ED)| = 4.44×10⁻¹⁶
maximum fivefold splitting = 4.44×10⁻¹⁶
maximum coordinate-symmetry residual = 2.83×10⁻¹⁵
maximum ‖(L²−6)ψ‖ residual = 1.31×10⁻¹³
```

This Pfaffian result is a deterministic small-system oracle, not a Monte Carlo
error bar. It does not establish a large-\(N\) neural state, a thermodynamic
gap, or chirality. Production coordinate evaluation is polynomial and does
not enumerate Fock determinants, but the current large-\(N\) VMC extrapolation
remains unfinished.

Challenge 121 is intentionally absent from this branch and PR. It is submitted
separately by team 格格巫.
