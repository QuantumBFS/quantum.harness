---
name: method-mps
description: Use when an MPS, DMRG, TEBD, 1D tensor-network, matrix-product-state, or quasi-1D cylinder reproduction needs method-level route and tool selection.
---

# Method MPS

MPS is the controlled 1D and quasi-1D tensor-network track. Use it to decide whether the paper needs DMRG, imaginary-time TEBD, real-time TEBD, or an MPS diagnostic, then invoke the tool skill for setup.

## Sources

- Track README: `tracks/mps/README.md`
- Method card: `.knowledge/methods/mps-based-algorithm.md`
- Tool skill: `/using-itensors`

## Route

1. Use DMRG for ground-state energies, order parameters, correlations, and finite-size trends in 1D or narrow cylinders.
2. Use imaginary-time TEBD when the paper uses a preparation/evolution route or when a product initial state is part of the scientific setup.
3. Use real-time TEBD only when the target figure is dynamics; otherwise treat dynamics as out of the basic reproduction route.
4. Recommend `/using-itensors` for ITensors.jl / ITensorMPS.jl setup, MPS parameters, and timing. MPSKit is part of the same Julia stack when an infinite-system interface is required.
5. If the paper uses official non-ITensors code, offer official code / web search as the setup fork before falling back.

## Tool Handoff

Invoke `/using-itensors` after the route is chosen. `/using-itensors` owns bond-dimension, sweeps, cutoff, initialization, TEBD step, convergence checks, and time estimate.
