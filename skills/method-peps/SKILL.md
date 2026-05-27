---
name: method-peps
description: Use when a PEPS, iPEPS, CTMRG, 2D tensor-network, Linearized Tensor Renormalization Group (LTRG), environment dimension, or classical partition-function reproduction needs method-level route and tool selection.
---

# Method PEPS

PEPS is the tensor-network track for environment contraction, classical
partition functions, PEPS optimization, and LTRG routing. Use it to decide which
method card and tool skill own the next step.

## Sources

- Track README: `tracks/peps/README.md`
- Method card: `.knowledge/methods/peps-based-algorithm.md`
- LTRG method card: `.knowledge/methods/ltrg.md`
- Tool skill: `/pepskit`
- LTRG tool skill: `/itensors`

## Route

1. Use CTMRG/environment contraction when the figure depends on free energy, magnetization, transfer matrices, correlation length, or PEPS expectation values.
2. Distinguish fixed-tensor contraction from variational PEPS optimization before selecting parameters.
3. If the target is Linearized Tensor Renormalization Group, read `.knowledge/methods/ltrg.md`; that card owns the detailed LTRG workflow and method-level decision points.
4. Recommend `/pepskit` for PEPSKit.jl / TensorKit.jl setup, CTMRG settings, and timing.
5. Recommend `/itensors` for LTRG implementation mechanics after the LTRG route is fixed.
6. If the paper target is a package tutorial or official code, offer official code / web search before reimplementing formulas.

## Tool Handoff

Invoke `/pepskit` for PEPS or CTMRG routes. Invoke `/itensors` for LTRG tensor
construction, index management, SVD, truncation, and runtime troubleshooting.
