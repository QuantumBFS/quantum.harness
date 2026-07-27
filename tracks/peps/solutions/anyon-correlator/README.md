# [peps] anyon-correlator: anyon correlators from PEPS transfer matrices across the toric-code field transition

## Team

| | |
|---|---|
| **Team name** | anyon-correlator |
| **Members** | Huanyu Shi (KITS-UCAS) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Numerical computation of anyon correlators Cₑ(r), Cₘ(r) in topologically ordered states from PEPS — going beyond ground-state PEPS optimization by resolving the anyon sectors of the PEPS transfer matrix and tracking the extracted correlation lengths across the anyon-condensation transition. |
| **Catalog issue** | `Addresses #50` — released by Huanyu Shi (KITS-UCAS). |
| **Track** | `tracks/peps/` — from the issue's `Method` field (PEPS Based Algorithm). |

## Plan

Benchmark model: toric code in external magnetic fields,

H = −Jₑ Σₛ Aₛ − Jₘ Σₚ Bₚ − hₓ Σᵢ Xᵢ − h_z Σᵢ Zᵢ

1. Optimize PEPS ground-state approximations at representative points / paths in the (hₓ, h_z) phase diagram.
2. Construct the PEPS transfer matrix and its relevant anyon (twisted) sectors.
3. Compute Cₑ(r), Cₘ(r) — directly, or from the leading transfer-matrix eigenvalues per sector.
4. Extract correlation lengths and analyze their evolution across the field-driven transition.

Deliverable: a working PEPS workflow plus representative plots/tables of Cₑ(r), Cₘ(r) and the extracted correlation lengths.

References: Haegeman et al., Nat. Commun. 6, 8284 (2015); Duivenvoorden et al., PRB 95, 235119 (2017); Zauner et al., NJP 17, 053002 (2015); Schuch et al., Ann. Phys. 325, 2153 (2010).
