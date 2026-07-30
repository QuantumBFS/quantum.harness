---
title: "Challenge 148: Protocol Revision 4 - Sampling and Finite-Temperature Gates"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 3.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 5.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 5 Report.md
---

# Challenge 148: Protocol Revision 4

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3+rev4`.

This append-only revision froze the remaining sampling diagnostics before any
doubled-$c_\tau$ or larger-size Stage 5 data were generated.

## 1. Reblocking and chain-spread gates

Using Revision 3's base block $b$:

1. repeat the estimate with block length $2b$;
2. require the maximum raw-observable mean difference to be no larger than 5.0
   standard errors;
3. require every doubled-to-base standard-error ratio to lie in $[1/2,2]$;
4. compare each individual chain to all other chains and require the maximum
   raw-observable difference to be no larger than 5.0 standard errors.

All checks use the five stored raw observables and all failures remain visible.

## 2. Additional-prefix gate

Registered refits discard 10% and 20% of every measured chain. For each
observable and discard fraction, the fitted critical-field shift must be no
larger than 5.0 combined standard errors.

## 3. Original $c_\tau$ clause

Revision 4 originally required the $c_\tau=1$ and $c_\tau=2$ dimensionless
observables to agree pointwise under the same 5.0 threshold. It also required
the fitted critical-field shift to satisfy

$$
|\Delta h_c|+1.96\sigma_{\Delta h_c}\leq
\begin{cases}
4.5\times10^{-6}, & \text{triangular},\\
2.0\times10^{-6}, & \text{honeycomb}.
\end{cases}
$$

A statistically consistent but under-resolved shift fails this systematic
gate.

## 4. Supersession notice

Protocol Revision 5 supersedes only the pointwise-invariance requirement in
Section 3. The reblocking, chain-spread, prefix, fitted-shift, and resolution
requirements remain frozen.
