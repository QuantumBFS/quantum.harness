---
title: "Challenge 148: Protocol Revision 2 - Fit Windows and Minimum Sizes"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 1.md
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
---

# Challenge 148: Protocol Revision 2

Protocol identifier: `c148-prereg-v1+rev1+rev2`.

This append-only revision closes numeric omissions in the Stage 0 fit matrix.
It does not change the Hamiltonian, estimators, fit family, fixed exponents,
uncertainty rules, blinding rule, or ratio verdict gate.

## 1. Frozen windows and minimum sizes

| Lattice | Broad field window | Narrow field window | Registered $L_{\min}$ |
|---|---:|---:|---|
| Square calibration | [3.00, 3.10] | [3.03, 3.06] | 4, 6, 8 |
| Triangular | [4.70, 4.84] | [4.74, 4.80] | 6, 8, 10, 12 |
| Honeycomb | [2.08, 2.18] | [2.11, 2.15] | 10, 12, 14 |

These values were copied from pre-verdict historical grids and commands before
any corrected triangular or honeycomb production data existed.

## 2. Enforcement

1. A scan may cover a superset of either field window, but a registered fit
   must identify and enforce the selected window.
2. The robustness matrix must report the registered $L_{\min}$ variants rather
   than selecting one after inspecting the hidden ratio.
3. Pilot evidence may add larger sizes. It may not tune these windows after
   viewing the triangular-to-honeycomb ratio.
4. Any later change to the windows or $L_{\min}$ matrix requires a new protocol
   identifier and an explicit justification.
