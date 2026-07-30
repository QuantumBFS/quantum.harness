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

- Repository: https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026
- Immutable source snapshot:
  https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/tree/e98148a54b35b9bdb7ad0b2672f027790a0f1603
- [Human-readable reviewer guide](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/e98148a54b35b9bdb7ad0b2672f027790a0f1603/challenges/15-chiral-graviton/REVIEWER_GUIDE.md)
- [Reproduction guide](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/e98148a54b35b9bdb7ad0b2672f027790a0f1603/challenges/15-chiral-graviton/REPRODUCIBILITY.md)

## Verified finite-size result

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

Challenge 121 is intentionally absent from this branch and PR. It is submitted
separately by team 格格巫.
