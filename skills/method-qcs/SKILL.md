---
name: method-qcs
description: Use when a quantum circuit simulation, VQE, TensorCircuit-NG, JAX backend, contraction path, statevector, MPS circuit, gradient, or circuit-performance reproduction needs method-level route and tool selection.
---

# Method QCS

Quantum circuit simulation is the differentiable-circuit and performance track. Use it to choose representation and software stack before tuning backend settings.

## Sources

- Track README: `tracks/qcs/README.md`
- Method card: `.knowledge/methods/quantum-circuit-simulation.md`
- Interview notes: `docs/qcs/interview.html`
- Review notes: `docs/qcs/review.html`
- Challenge brief: `docs/qcs/backup.md`
- Tool skills: `/using-tensorcircuit-ng`, `/using-jax`

## Route

1. Choose representation first: tensor-network contraction, full statevector, or MPS circuit. This determines memory and whether the result is exact or approximate.
2. Recommend `/using-tensorcircuit-ng` for large/deep differentiable VQE, energy+gradient profiling, contraction tuning, batching, scan/checkpointing, and the QCS track benchmark.
3. Invoke `/using-jax` for backend, CPU/GPU, precision, device, and compile/warm-runtime setup.
4. If the paper requires Qiskit, PennyLane, Yao, cuQuantum, or quimb specifically, offer official code / web search or a new tool skill instead of silently forcing TensorCircuit-NG.
5. Keep compile time, path-search time, warm runtime, and optimizer-loop time separate in any proposal or report.

## Tool Handoff

Invoke `/using-tensorcircuit-ng` after the route is chosen. `/using-tensorcircuit-ng` owns representation-specific parameters, contraction/path settings, observable format, gradients, validation, and time estimate. Invoke `/using-jax` for backend setup.
