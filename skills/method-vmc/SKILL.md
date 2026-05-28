---
name: method-vmc
description: Use when a VMC, variational Monte Carlo, neural quantum state, NQS, NetKet, ansatz, sampler, optimizer, or V-score reproduction needs method-level route and tool selection.
---

# Method VMC

VMC/NQS is the variational stochastic track. Use it to decide whether a paper target is an ansatz benchmark, variational energy, V-score, or neural-state training task, then invoke the right tool skills.

## Sources

- Track README: `tracks/vmc/README.md`
- Tool skills: `/using-netket`, `/using-jax`

## Route

1. Use VMC/NQS when the paper's claim is about a variational ansatz, training curve, energy benchmark, variance/V-score, or sign-problem regime where QMC is blocked.
2. Recommend `/using-netket` for NetKet model/sampler/optimizer setup and VMC timing.
3. Invoke `/using-jax` when CPU/GPU backend, precision, device smoke test, or compilation behavior matters.
4. Use `/using-xdiag` only as a small-size validation route when exact comparison is feasible; it is not the primary VMC tool.
5. If the paper uses a custom architecture or official training code, offer official code / web search before mapping it to NetKet.

## Tool Handoff

Invoke `/using-netket` after the route is chosen. `/using-netket` owns ansatz, sampler, optimizer, learning rate, samples, steps, seeds, variance, error bars, and time estimate. Invoke `/using-jax` for backend setup.

## Details

Variational method: parameterize a wavefunction ansatz, optimize parameters by minimizing energy via stochastic sampling. Neural quantum states (NQS) use neural networks as the ansatz.

### Notation

- Ansatz `|ψ_θ⟩`: parameterized wavefunction (RBM, CNN, Transformer, ...).
- Variational energy `E_θ = ⟨ψ_θ|H|ψ_θ⟩ / ⟨ψ_θ|ψ_θ⟩`, estimated by Monte Carlo sampling.
- Energy variance `σ²_E = ⟨H²⟩ - ⟨H⟩²`: zero for exact eigenstate.
- V-score: `N × σ²_E / (E - E_∞)²`, with `E_∞ = Tr(H)/dim(H)` the infinite-temperature reference (Wu et al., arXiv:2302.04919).

### When to use

- Frustrated 2D problems where DMRG cylinder geometry biases the answer (kagome, triangular, J1-J2).
- Comparing variational energies across ansatz families.
- V-score benchmarking (Wu et al., arXiv:2302.04919).
- Sign-problem regimes where QMC is blocked.

### When NOT to use

- 1D chains — DMRG is cheaper and more accurate.
- Small clusters — ED is exact.
- When the user needs a certified bound (VMC gives upper bounds only; no error bars on the gap to exact).

### Pitfalls

- **Local minima**: VMC optimizes a non-convex landscape. Restart with different seeds; compare multiple runs.
- **Sign structure**: for frustrated / fermionic problems, the ansatz must capture the sign structure of the wavefunction. Marshall-sign-rule initialization helps for bipartite AFM.
- **Autocorrelation**: MC samples are correlated. Use decorrelation steps or check integrated autocorrelation time.
- **Variance vs energy**: a low energy with high variance is suspicious. Report both. V-score summarizes the tradeoff.
- **Finite-size effects**: VMC with PBC is natural (no boundary bias). Compare sizes.

### Verification

- **Energy upper bound**: VMC energy is variational — it must be ≥ the true ground-state energy. If it's lower than a published exact result, something is wrong.
- **Variance**: should decrease during training and be small at convergence.
- **Cross-method**: compare VMC energy to DMRG (if available) on the same system. Agreement within variance is good.
- **V-score**: compute and compare to published values in the V-score paper (Wu et al., arXiv:2302.04919).
- **Multiple seeds**: run 3–5 independent optimizations; they should converge to similar energies.

### Citations

- Carleo & Troyer, *Science* **355**, 602 (2017) — NQS with RBM.
- Becca & Sorella, *Quantum Monte Carlo Approaches for Correlated Systems* (Cambridge, 2017) — VMC foundations.
- Wu et al., *Variational benchmarks for quantum many-body problems*, arXiv:2302.04919 — V-score definition and benchmark families.
