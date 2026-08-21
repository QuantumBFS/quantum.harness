# Issue draft: quantum chaos under exact degeneracy

## Suggested title

`What replaces spectral chaos diagnostics in an exactly degenerate quantum subspace?`

## Problem

Level statistics and the spectral form factor cannot resolve dynamics internal to an exactly degenerate eigenspace. This occurs in frustration-free fractional-quantum-Hall parents, supersymmetric/cohomological kernels, stabilizer models, index-protected chiral systems, and protected BPS sectors. The challenge is to construct a gauge-invariant, reproducible test of whether such a subspace has random or structured response under changes of couplings or boundary conditions.

The relevant object is the projector bundle (P(\lambda)) over parameter space. Its off-fiber response (X_a=Q\partial_aP\,P), quantum geometric tensor, non-Abelian Berry curvature, and Wilson transport remain nontrivial even when every energy in the protected fiber is identical.

## Requested deliverable

Submit a reproducible calculation that contains all of the following:

1. an exact-degeneracy audit, including the internal bandwidth and the gap to (Q=1-P);
2. a gauge-covariant definition of the response observable;
3. at least one local statistic and one complete covariance or connected fourth-order statistic;
4. the ensemble unit, symmetry class, uncertainty construction, and finite-size sequence;
5. one structured or frozen negative control;
6. a machine-readable claim gate that distinguishes finite-size evidence from an asymptotic or universal statement;
7. source code, tests, figure provenance, a manuscript PDF, and a one-command verifier.

## Suggested model classes

- fractional-quantum-Hall or fractional-Chern-insulator parent Hamiltonians;
- supersymmetric/cohomological Hamiltonians (H=\{Q,Q^\dagger\});
- commuting-projector and subsystem-stabilizer models;
- chiral or index-protected kernels;
- protected BPS sectors in SYK, super-JT, or related microscopic models.

A submission need not cover every class. An independent mechanism or operator ensemble is more valuable than another fit to the same finite-size data.

## Evaluation criteria

| Criterion | Required evidence |
|---|---|
| Exactness | Numerically or analytically certified degeneracy and external gap |
| Gauge covariance | Invariance under a basis change within the protected fiber |
| Statistical completeness | Covariance and pseudocovariance included where the variables are complex |
| Controls | A case known to be frozen, scalar, reducible, or otherwise nonchaotic |
| Independence | Held-out size, independently sampled Hamiltonian, or a clearly labeled retrospective analysis |
| Reproducibility | Deterministic scripts, hashes, tests, and archived figures/PDFs |
| Claim discipline | No thermodynamic, universal, thermalization, or black-hole claim without a corresponding gate |

## Current reference implementation

The accompanying Wander submission provides two back-to-back papers:

- Paper I establishes finite-size, mechanism-resolved evidence that non-Abelian projector geometry remains informative when the energy spectrum is exactly silent.
- Paper II proves an exact weighted-channel cumulant identity under stated independence assumptions and tests a parameter-free specialization in an index-protected chiral model. The sealed physical test fails, showing that (N_{\mathrm{eff}}) alone is insufficient for that registered ensemble. The positive title *The Geometric ETH* is therefore withheld.

This negative branch is part of the reference result, not a missing output. It identifies the next scientific target: determine whether the obstruction is channel correlation, noncomparable single-channel cumulants, finite-rank geometry, or the chosen tangent ensemble.

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

