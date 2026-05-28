---
name: using-tensorcircuit-ng
description: Use when choosing or running TensorCircuit-NG for quantum-circuit simulation, differentiable circuits, VQE, JAX backend setup, or TensorCircuit-NG setup failures.
---

# TensorCircuit-NG

Use TensorCircuit-NG for JAX-backed circuit simulation, differentiable circuit workflows, and quantum-circuit-simulation track reproductions.

## Sources

- Stack contract: `skills/using-tensorcircuit-ng/stack.toml`
- JAX prerequisite: `skills/using-jax/stack.toml`
- Method card: `skills/method-qcs/SKILL.md`
- QCS interview notes: `docs/qcs/interview.html`
- QCS review notes: `docs/qcs/review.html`
- QCS challenge brief: `docs/qcs/backup.md`
- Install target: `make install tensorcircuit-ng`
- Upstream agent resources (not vendored here; consult when working in this method): skills <https://github.com/tensorcircuit/using-tensorcircuit-ng/tree/master/.agents/skills>, memory <https://github.com/tensorcircuit/using-tensorcircuit-ng/tree/master/.agents/memory>

## Workflow

1. Install and smoke-test JAX first; TensorCircuit-NG depends on the selected JAX backend.
2. Choose CPU or GPU based on the actual run size and cluster availability, then smoke-test in that environment.
3. Pin backend, dtype/precision, circuit depth, batch size, random seeds, and observable before compute.
4. For differentiable runs, record optimizer, gradient path, and JIT/compilation expectations.

## Parameter setup

Use this section as the source for TensorCircuit-NG-specific reproduction knobs unless the paper or official code fixes a value. QCS setup starts with representation and stack, then tunes settings inside that choice.

- Representation: tensor-network contraction, full statevector, or MPS. Pick contraction for large/deep differentiable VQE when the largest intermediate tensor fits; statevector for small/full-state/noise/sampling; MPS for 1D low-entanglement circuits after `chi` convergence.
- Backend/runtime: usually JAX for compiled speed, automatic differentiation, and batching; NumPy is debugging only. Use `/using-jax` for device, dtype, and compile setup.
- Precision: default complex64 for performance scans; complex128 when the observable, gradient, or baseline accuracy demands it.
- Circuit/task: qubit count, geometry, gate set, depth/layers, parameter shape, initialization, seed policy, and whether the target is expectation, gradient/VQE, sampling, or training.
- Observable form: Pauli-term loop, batched Pauli structure, sparse matrix, dense matrix only for small cases, or MPO-like form for short-range Hamiltonians.
- Differentiation/compilation: reverse-mode AD for simulation; parameter-shift only to mimic hardware. JIT the value-and-gradient step for benchmark timing; use `scan` for deep repeated layers and checkpointing when backward memory is tight.
- Contraction/memory: greedy for smoke/moderate circuits; cotengra when contraction cost matters. Record path-search budget, objective (`flops`, `write`, `size`, or blend), largest intermediate, slicing target, and whether distributed contraction is data-parallel or model-parallel.
- Optimizer/runtime loop: Adam/SGD for large noisy objectives, L-BFGS for smooth tensor-network objectives, SciPy optimizers for small special cases, gradient-free only when gradients are unavailable.
- Validation: small-system exact check, Pauli/sparse/MPO agreement, energy not below exact ground state, AD vs finite-difference spot check, contractor cross-check (a simpler contractor must reproduce the same energy/gradient), MPS `chi` convergence when used, and matched baseline for speed claims.

## Knobs

Concrete starting points for the knobs in Parameter setup.

| Knob | Effect | Starting point |
|---|---|---|
| dtype | Accuracy and memory/runtime. | `complex64` for performance scans; `complex128` for precision checks. |
| ansatz depth | Expressiveness and compilation graph size. | Sweep depth; avoid interpreting one depth as converged. |
| contractor | Controls contraction order and memory. | `greedy` for smoke; cotengra-backed search for larger circuits. |
| path-search budget | Better paths vs planning overhead. | Separate path-search time from steady execution time. |
| slicing target | Trades memory for additional contraction work. | Use when peak memory blocks execution. |
| `jit` boundary | Controls compilation granularity. | JIT the full value-and-gradient step for benchmarkable steady runtime. |
| `scan` | Reduces graph growth for repeated layers. | Use for deep homogeneous layer stacks. |
| checkpointing | Reduces backward memory at extra compute cost. | Use when gradients OOM before forward pass does. |
| batching / `vmap` | Parallelizes seeds, terms, or parameter points. | Use only when batch axes are physically independent. |

## Code shape

```python
import jax
import tensorcircuit as tc

tc.set_backend("jax")
tc.set_contractor("greedy")  # switch to cotengra-backed contractors when needed


def ansatz(params, n, depth):
    c = tc.Circuit(n)
    for layer in range(depth):
        for i in range(n):
            c.rx(i, theta=params[layer, i, 0])
            c.rz(i, theta=params[layer, i, 1])
        for i in range(n - 1):
            c.cnot(i, i + 1)
    return c


def energy(params, hamiltonian, n, depth):
    c = ansatz(params, n, depth)
    return tc.backend.real(tc.templates.measurements.operator_expectation(c, hamiltonian))


value_and_grad = tc.backend.jit(tc.backend.value_and_grad(energy))
e, grad = value_and_grad(params, hamiltonian, n, depth)
```

For deep repeated layers, express the layer update with JAX control flow (`jax.lax.scan`) when possible. For large contractions, move path search and slicing into explicit contractor settings and record the contractor identity in the run manifest.

## Time estimate

Estimate from representation, qubit count, depth/gate count, observable form, batch size, gradient path, contraction path, and device.

- Statevector: memory is `2^n` complex amplitudes times dtype, multiplied by batches/gradients. `docs/qcs/review.html` gives an 80 GB GPU anchor of about 33 complex64 qubits.
- Tensor-network contraction: memory is the largest intermediate tensor from contraction info, not qubit count alone; wall is contraction FLOPs plus path search and compile time.
- MPS: memory/time depend on bond dimension `chi`; the run is approximate unless `chi` convergence is shown.
- Timing must separate one-off path search, JAX compile, warm value-and-gradient runtime, and optimizer-loop overhead. The QCS benchmark anchor is 32 qubits x 16 layers with one warm energy+gradient evaluation on a single H200 GPU; `docs/qcs/backup.md` gives a CPU baseline target of 24 qubits x 12 layers.
- First estimate paper-size qubits/depth and the largest local-PC-in-15-min circuit. If memory is infeasible, use slicing, GPU/cluster, MPS approximation, or reduced scope as explicit options.

## Common Setup Notes

- Long first-run latency can be JAX compilation, not stalled physics.
- GPU availability must be checked with `jax.devices()` inside the runtime allocation.
- Do not substitute another circuit package without recording it as a protocol deviation.
- Shape or dtype changes can trigger JAX recompilation; record parameter shape and dtype, and profile the `value_and_grad` step separately from the outer optimizer loop.
- Path/contractor settings are part of the numerical method; do not change the contractor mid-scan without recording it.
