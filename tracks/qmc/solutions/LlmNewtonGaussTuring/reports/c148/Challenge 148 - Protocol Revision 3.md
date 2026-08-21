---
title: "Challenge 148: Protocol Revision 3 - Sampling-Test Calibration"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 2.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 4 Report.md
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
---

# Challenge 148: Protocol Revision 3

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3`.

This append-only revision freezes the sampling-test calibration before any
corrected triangular or honeycomb data were generated. It changes the
previously unregistered diagnostic threshold, not the scientific model or
verdict rule.

## 1. Blocking unit

For each chain, estimate the integrated autocorrelation time for the five raw
observables

$$
\bar m^2,\quad \bar m^4,\quad S(0),\quad S(q_{\min}),\quad E.
$$

The base block length is

$$
b=\left\lceil2\max\tau_{\rm int}\right\rceil.
$$

Every chain must contain at least eight such blocks. A point with fewer blocks
fails rather than falling back to an unblocked error estimate.

## 2. Frozen tests

Hot-versus-cold agreement and first-half-versus-second-half stationarity are
tested on the base blocks. For each test, the maximum standardized difference
over all five raw observables must not exceed 5.0.

The family-wise 5.0 threshold replaces the unregistered pilot implementation's
per-comparison 3.5 cutoff. Maximizing the old cutoff over roughly two thousand
square-calibration comparisons produced the expected false flags; those flags
were a calibration defect rather than evidence of non-equilibration.

Failures remain explicit in the analysis output and cannot be removed by
selecting observables or cells after inspection.
