---
name: method-qmc
description: Use when a quantum Monte Carlo, QMC, stochastic series expansion, SSE, finite-temperature, sign-problem, or statistical-bin reproduction needs method-level route and tool selection.
---

# Method QMC

QMC is the stochastic sampling track. Use it to decide whether the target is sign-problem-free SSE and whether stochastic error bars can reproduce the requested figure.

## Sources

- Track README: `tracks/qmc/README.md`
- Method card: `.knowledge/methods/quantum-monte-carlo.md`
- Tool skill: `/using-sse`

## Route

1. Check sign-problem control first: lattice, coupling signs, basis, and observable must be compatible with the selected QMC route.
2. Use SSE for sign-free spin/bosonic lattice targets, finite-temperature curves, beta convergence, and large-size statistical checks.
3. Recommend `/using-sse` for StochasticSeriesExpansion.jl / Carlo.jl setup, stochastic parameters, MPI choice, and timing.
4. If the target is determinant QMC, AFQMC, impurity CTQMC, or has an uncontrolled sign problem, do not force `/using-sse`; offer official code / web search or another track.

## Tool Handoff

Invoke `/using-sse` after the route is chosen. `/using-sse` owns thermalization, sweeps, chains, bins, beta/temperature grid, autocorrelation checks, sign checks, MPI setup, and time estimate.
