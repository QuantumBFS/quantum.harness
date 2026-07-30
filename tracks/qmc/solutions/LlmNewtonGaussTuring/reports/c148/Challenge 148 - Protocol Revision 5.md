---
title: "Challenge 148: Protocol Revision 5 - Corrected Aspect-Ratio Gate"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 4.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 5 Report.md
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
---

# Challenge 148: Protocol Revision 5

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3+rev4+rev5`.

The first doubled-$c_\tau$ pilot exposed a false premise in Revision 4. This
append-only correction changes the finite-temperature diagnostic without
changing its absolute uncertainty budget.

## 1. Corrected invariant

The primary estimator contains a full imaginary-time average,

$$
\bar m=\frac{1}{\beta}\int_0^\beta m(\tau)\,d\tau,
$$

and both $Q_L$ and $\xi_L/L$ are finite-size scaling functions of the
space-time aspect ratio. Changing $c_\tau$ is therefore expected to change
their finite-$L$ point values. Pointwise agreement is not a physical
invariant.

The invariant is the extrapolated transition location. The $c_\tau=1$ and
$c_\tau=2$ analyses must still report both dimensionless observables on the
common grid, but pointwise standardized shifts are diagnostics rather than
pass/fail gates.

## 2. Retained hard gate

For each fitted observable, require

$$
|\Delta h_c|+1.96\sigma_{\Delta h_c}\leq
\begin{cases}
4.5\times10^{-6}, & \text{triangular},\\
2.0\times10^{-6}, & \text{honeycomb}.
\end{cases}
$$

The fit may be statistically consistent while this bound remains unresolved.
Under-resolution is a failed final systematic gate, not evidence that the
finite-temperature shift is zero.

The doubled-$c_\tau$ data and resulting gate assessment are recorded in the
Stage 5 report.
