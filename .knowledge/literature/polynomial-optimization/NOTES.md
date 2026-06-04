# Polynomial optimization — survey notes

Built by `/survey` on 2026-06-04. Focus: materials by Jie Wang (wangjie212, AMSS;
author of NCTSSOS / NCTSSoS / TSSOS) — foundational sparse polynomial optimization
and its quantum many-body certification applications.

## Field landscape

- **Foundations / textbook.** [@magron_2023_sparse] (*Sparse Polynomial
  Optimization: Theory and Practice*, World Scientific 2023, arXiv 2208.11158) is
  the comprehensive treatment of the moment-SOS / Lasserre hierarchy and its
  sparsity-exploiting variants (correlative, term, chordal), commutative and
  noncommutative, with the TSSOS / NCTSSOS software. The canonical background
  reference for `/method-polyopt` and `/using-nctssos`.
- **Quantum many-body certification.** [@wang_2024_certifying] (PRX 14, 031006,
  2024) is the flagship application: NPA / moment-SOHS SDP relaxations giving
  *certified lower bounds* on ground-state energy and two-sided bounds on
  ground-state observables for 1D/2D spin systems (incl. J1–J2 Heisenberg). Ships
  the Julia package QMBCertify. This is the direct evidence for method-polyopt's
  certification role and a source for worked-example scales.

Active group: Jie Wang with V. Magron, A. Acín, I. Frérot, M.-O. Renou, and
(state/trace polynomials) I. Klep, J. Volčič. Temporal trend: the sparse-POP
machinery (2019–2022) matured into quantum many-body certification (2023→).

Not yet pulled into this KB (surfaced by the survey, available via `/download-ref`):
NCTSSOS term-sparsity paper (arXiv 2010.06956), state-polynomial / nonlinear Bell
(2301.12513), trace-polynomial optimization (2006.12510), scalable spin-system
certification (2604.01555), phase-diagram mapping via SDP (2507.03137).

## Key open problems

- Scaling certified bounds to larger 2D lattices and to fermionic/bosonic systems
  while keeping the SDP tractable (sparsity + symmetry reduction).
- Tightness: when does a finite relaxation order certify the exact energy
  (flatness), and quantitative accuracy guarantees per order.
- Extracting physical observables (correlations, order parameters) with rigorous
  two-sided bounds, beyond the energy.

## Key bottlenecks

- SDP size grows ~O(n^order) in the operator count; memory is the binding
  resource. Correlative + term sparsity is the main lever but trades some
  tightness.
- The method certifies bounds, not the state — GNS reconstruction yields *a*
  realizing representation, not the lattice ground state.
