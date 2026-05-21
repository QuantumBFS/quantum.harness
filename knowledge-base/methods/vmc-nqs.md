# VMC / NQS (Variational Monte Carlo / Neural Quantum States)

Variational method: parameterize a wavefunction ansatz, optimize parameters by minimizing energy via stochastic sampling. Neural quantum states (NQS) use neural networks as the ansatz.

## Setup

Canonical stack: `netket` (`tools/software/stacks/netket.toml`).

```
make install netket
source .venv/bin/activate
```

GPU and multi-node GPU installs are separate `netket` stack profiles. Smoke
tests for those profiles must run inside a compute allocation, not on a login
node.

## Notation

- Ansatz `|ψ_θ⟩`: parameterized wavefunction (RBM, CNN, Transformer, ...).
- Variational energy `E_θ = ⟨ψ_θ|H|ψ_θ⟩ / ⟨ψ_θ|ψ_θ⟩`, estimated by Monte Carlo sampling.
- Energy variance `σ²_E = ⟨H²⟩ - ⟨H⟩²`: zero for exact eigenstate.
- V-score: `N × σ²_E / (E - E_∞)²`, with `E_∞ = Tr(H)/dim(H)` the infinite-temperature reference (Wu et al., arXiv:2302.04919).

## Code shape (Python / NetKet)

```python
import netket as nk

# 1. Lattice + Hilbert space
graph = nk.graph.Chain(length=N, pbc=True)
hi = nk.hilbert.Spin(s=0.5, N=graph.n_nodes)

# 2. Hamiltonian
H = nk.operator.Heisenberg(hilbert=hi, graph=graph, J=1.0)

# 3. Ansatz (RBM default; swap for other architectures)
model = nk.models.RBM(alpha=4, param_dtype=complex)

# 4. Sampler + optimizer
sampler = nk.sampler.MetropolisLocal(hi, n_chains=16)
optimizer = nk.optimizer.Sgd(learning_rate=0.01)
sr = nk.optimizer.SR(diag_shift=0.01)

# 5. VMC driver
vs = nk.VMC(H, optimizer, sampler, model, n_samples=1024, preconditioner=sr)

# 6. Run
vs.run(n_iter=500, out="output")

# 7. Read results
import json
data = json.load(open("output.log"))
energy = data["Energy"]["Mean"][-1]
variance = data["Energy"]["Variance"][-1]
```

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| `alpha` (RBM hidden-unit ratio) | Ansatz expressiveness. Higher = more flexible, slower. | 2–4 for entry; 8+ for frustrated 2D. |
| `n_samples` | MC samples per gradient step. More = lower variance gradient. | 1024–4096. |
| `learning_rate` | Optimizer step size. | 0.01 (SGD); 0.001 (Adam). |
| `diag_shift` (SR) | Stochastic reconfiguration regularization. | 0.01; reduce as training progresses. |
| `n_iter` | Training iterations. | 500–2000; monitor energy convergence. |
| Architecture | RBM, CNN, Transformer, ... | RBM for entry; CNN/Transformer for 2D frustrated. |

## When to use

- Frustrated 2D problems where DMRG cylinder geometry biases the answer (kagome, triangular, J1-J2).
- Comparing variational energies across ansatz families.
- V-score benchmarking (Wu et al., arXiv:2302.04919).
- Sign-problem regimes where QMC is blocked.

## When NOT to use

- 1D chains — DMRG is cheaper and more accurate.
- Small clusters — ED is exact.
- When the user needs a certified bound (VMC gives upper bounds only; no error bars on the gap to exact).

## Pitfalls

- **Local minima**: VMC optimizes a non-convex landscape. Restart with different seeds; compare multiple runs.
- **Sign structure**: for frustrated / fermionic problems, the ansatz must capture the sign structure of the wavefunction. Marshall-sign-rule initialization helps for bipartite AFM.
- **Autocorrelation**: MC samples are correlated. Use decorrelation steps or check integrated autocorrelation time.
- **Variance vs energy**: a low energy with high variance is suspicious. Report both. V-score summarizes the tradeoff.
- **Finite-size effects**: VMC with PBC is natural (no boundary bias). Compare sizes.

## Verification

- **Energy upper bound**: VMC energy is variational — it must be ≥ the true ground-state energy. If it's lower than a published exact result, something is wrong.
- **Variance**: should decrease during training and be small at convergence.
- **Cross-method**: compare VMC energy to DMRG (if available) on the same system. Agreement within variance is good.
- **V-score**: compute and compare to published values in the V-score paper (Wu et al., arXiv:2302.04919).
- **Multiple seeds**: run 3–5 independent optimizations; they should converge to similar energies.

## Citations

- Carleo & Troyer, *Science* **355**, 602 (2017) — NQS with RBM.
- NetKet documentation — https://www.netket.org
- Becca & Sorella, *Quantum Monte Carlo Approaches for Correlated Systems* (Cambridge, 2017) — VMC foundations.
- Wu et al., *Variational benchmarks for quantum many-body problems*, arXiv:2302.04919 — V-score definition and benchmark families.
