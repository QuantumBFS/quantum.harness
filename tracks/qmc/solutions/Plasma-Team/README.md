# Plasma-Team

## Team

| | |
|---|---|
| **Team name** | Plasma-Team |
| **Members** | Chenzhuo Xue |

## Challenge

| Row | |
|---|---|
| **Challenge** | Build a symmetric neural-network ansatz (antisymmetric + SO(3)-equivariant) for the chiral graviton in ν = 1/3 fractional quantum Hall state on the Haldane sphere, and compute the neutral gap Δ = E(L=2) − E(L=0). |
| **Catalog issue** | `Addresses #15` — released by Lei Wang, Institute of Physics, CAS |
| **Track** | `qmc` — from the issue's `Method` field: Variational Monte Carlo / Neural Quantum States |

## Approach

SO(3)-equivariant NQS with:
- **Single-particle basis**: Monopole harmonics Y_{Qlm} on the Haldane sphere
- **Fermionic antisymmetry**: Slater determinant + backflow + Jastrow
- **SO(3) equivariance**: Clebsch-Gordan tensor products for all message-passing layers
- **Verification**: ⟨L²⟩ = 6, 5-fold degeneracy, ED cross-check at small N, chirality decomposition via s⁺₂ operator

## References

- S.-F. Liou, F. D. M. Haldane, K. Yang, E. H. Rezayi, *Chiral Gravitons in Fractional Quantum Hall Liquids*, Phys. Rev. Lett. 123, 146801 (2019), [arXiv:1904.12231](https://arxiv.org/abs/1904.12231)
