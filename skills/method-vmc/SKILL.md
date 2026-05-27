---
name: method-vmc
description: Use when a VMC, variational Monte Carlo, neural quantum state, NQS, NetKet, ansatz, sampler, optimizer, or V-score reproduction needs method-level route and tool selection.
---

# Method VMC

VMC/NQS is the variational stochastic track. Use it to decide whether a paper target is an ansatz benchmark, variational energy, V-score, or neural-state training task, then invoke the right tool skills.

## Sources

- Track README: `tracks/vmc/README.md`
- Method card: `.knowledge/methods/variational-monte-carlo-neural-quantum-states.md`
- Tool skills: `/using-netket`, `/using-jax`

## Route

1. Use VMC/NQS when the paper's claim is about a variational ansatz, training curve, energy benchmark, variance/V-score, or sign-problem regime where QMC is blocked.
2. Recommend `/using-netket` for NetKet model/sampler/optimizer setup and VMC timing.
3. Invoke `/using-jax` when CPU/GPU backend, precision, device smoke test, or compilation behavior matters.
4. Use `/using-xdiag` only as a small-size validation route when exact comparison is feasible; it is not the primary VMC tool.
5. If the paper uses a custom architecture or official training code, offer official code / web search before mapping it to NetKet.

## Tool Handoff

Invoke `/using-netket` after the route is chosen. `/using-netket` owns ansatz, sampler, optimizer, learning rate, samples, steps, seeds, variance, error bars, and time estimate. Invoke `/using-jax` for backend setup.
