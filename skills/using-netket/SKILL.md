---
name: using-netket
description: Use when choosing or running NetKet for VMC, neural quantum states, sampler or optimizer choices, JAX CPU/GPU setup, or NetKet setup failures.
---

# NetKet

Use NetKet for VMC / neural-quantum-state workflows where the task needs a variational ansatz, sampler, optimizer, and statistical validation.

## Sources

- Stack contract: `skills/using-netket/stack.toml`
- Method card: `skills/method-vmc/SKILL.md`
- CPU install target: `make install netket`
- GPU install target: `make install netket-gpu`
- Docs: NetKet <https://www.netket.org>

## Workflow

1. Consult the stack contract and choose CPU, single-node GPU, or multi-node GPU before installing.
2. Smoke-test JAX devices and NetKet import in the same environment where the run will execute.
3. Pin ansatz, sampler, optimizer, learning rate, samples, steps, seeds, and validation observable before compute.
4. Treat energy variance, independent seeds, and exact/small-size comparison as required validation when feasible.

## Parameter setup

Use this section as the source for NetKet-specific reproduction knobs unless the paper or official code fixes a value. The `## Knobs` table below gives concrete starting points; the method card supplies the conceptual notation.

- Hilbert and graph: lattice, boundary, local states, constraints, symmetries, and operator convention.
- Ansatz: RBM/CNN/Transformer or paper architecture, hidden ratio/width/depth/features, parameter count, dtype/precision, initialization, and seed policy.
- Sampler: sampler type, chains, samples per iteration, burn-in, sweep size/decorrelation, and acceptance/autocorrelation diagnostics.
- Optimizer: SGD/Adam/SR or paper optimizer, learning-rate schedule, diagonal shift, iteration count, and stopping rule.
- Runtime profile: CPU, single-node GPU, or multi-node GPU; use `/using-jax` and the NetKet stack profile for device setup.
- Validation: energy variance, energy upper-bound sanity check, multiple seeds, small-size ED comparison when feasible, error bars/binning, and observable stability.

## Knobs

Concrete starting points for the knobs in Parameter setup.

| Knob | Effect | Starting point |
|---|---|---|
| `alpha` (RBM hidden-unit ratio) | Ansatz expressiveness. Higher = more flexible, slower. | 2–4 for entry; 8+ for frustrated 2D. |
| `n_samples` | MC samples per gradient step. More = lower variance gradient. | 1024–4096. |
| `learning_rate` | Optimizer step size. | 0.01 (SGD); 0.001 (Adam). |
| `diag_shift` (SR) | Stochastic reconfiguration regularization. | 0.01; reduce as training progresses. |
| `n_iter` | Training iterations. | 500–2000; monitor energy convergence. |
| Architecture | RBM, CNN, Transformer, ... | RBM for entry; CNN/Transformer for 2D frustrated. |

## Code shape

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

## Time estimate

Estimate from `iterations * samples_per_iteration * model_eval_cost`, plus JAX compilation and sampler overhead.

- CPU vs GPU changes the rate; use `stack.toml` to choose the profile, then smoke-test `jax.devices()` in the same environment.
- JAX compilation is a one-time setup/runtime overhead and should be reported separately from steady-state VMC iteration time.
- Memory is dominated by model parameters, sampler state, per-device batch size, and optimizer/SR state; SR can dominate memory for large parameter counts.
- For paper-size estimates, time a few warmup iterations after compilation or use an existing measured rate; then estimate the largest local-PC-in-15-min run without recommending a scale.

## Common Setup Notes

- GPU smoke tests belong inside a compute allocation, not on a login node.
- Multi-node GPU needs MPI/JAX distributed setup; compose with `/using-slurm`.
- Do not silently fall back from GPU to CPU; report the setup failure and ask.
