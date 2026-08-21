---
title: "Challenge 148: Protocol Revision 6 - ParaToric Dual Normalization"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
  - paratoric
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 5.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 7 Report.md
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
---

# Challenge 148: Protocol Revision 6

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6`.

This append-only revision freezes the independent-route normalization before
any ParaToric thermodynamic-limit scan.

## 1. Pinned implementation

- ParaToric version: v1.0.3.
- Upstream commit: `e7bc78446ba083aeeae1ada9c883fa03bf205890`.
- External build-only compatibility diff SHA-256:
  `3bd7a5231c38f048035f13f23bb20162b6f6e1f2264270dbeb61e2ce35073d30`.
- Basis and boundary: ParaToric `x` basis with periodic boundaries.

The compatibility diff adds the missing `<print>` include and replaces
indexed `std::println` placeholders with standard `{}` placeholders. It does
not modify the model or Monte Carlo algorithm.

## 2. Dual mapping

With $\lambda=0$, freeze

$$
h_{\rm eTC}=J_{\rm TFIM}=1,\qquad
J_{\rm eTC}=h_{\rm TFIM},\qquad
\mu=64.
$$

| Target TFIM | ParaToric gauge lattice |
|---|---|
| Triangular | Honeycomb |
| Honeycomb | Triangular |

ParaToric's periodic observable trace is compared to the full finite-volume
TFIM thermal trace. The even spin-flip sector remains a reported diagnostic,
not the comparison oracle. A nondegenerate square $L=3$ calculation fixed this
ensemble choice before target-lattice production.

## 3. Qualification gates

1. Compare exchange and transverse-field energies to ED.
2. Set the QMC uncertainty to the maximum of base-block, doubled-block, and
   independent-chain standard errors.
3. Assign ED an absolute uncertainty of $10^{-10}$ and require agreement
   within five combined standard errors.
4. Require every sampled star observable $A_v$ to remain $+1$.
5. Record the analytic full-edge-flip acceptance bound
   $\exp[-\beta(4\mu-2)]$.

ParaToric's triangular gauge lattice at $L=2$ has degenerate periodic
plaquette incidence and is not a valid honeycomb-target oracle. The first
independent honeycomb scan must therefore use $L\geq4$.

These checks qualify normalization and the sampled charge sector only. They do
not satisfy the independent thermodynamic-limit verdict gate.
