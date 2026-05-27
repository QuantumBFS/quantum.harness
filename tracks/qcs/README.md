# Quantum Circuit Simulation

## Reproduction target

Target paper: **TensorCircuit-NG**. See Reference 1.

Using the paper's Fig. 2 setup as the scale reference, reproduce and profile a single-machine, non-distributed variant:

1. **1D TFIM VQE one-step profile** — profile one variational quantum eigensolver step for the one-dimensional transverse-field Ising model: forward expectation-value evaluation plus backward gradient propagation.
2. **Required CPU baseline** — reproduce a 24-qubit, 12-layer VQE circuit as the pure-CPU reference scale.
3. **GPU extension** — reproduce the 32-qubit, 16-layer VQE circuit when GPU resources are available.
4. **Time accounting** — report JIT compilation time and warm execution time separately; report contraction-path search time when path search is part of the run.
5. **Memory accounting** — report peak memory / largest-intermediate-tensor pressure for the same benchmark.

## Challenge objective

Build a repeatable benchmark harness for TensorCircuit-NG VQE performance work: a scriptable benchmark that can automatically evaluate time efficiency and space efficiency, including first-call JIT compilation cost and subsequent warm-runtime execution cost.

The advanced goal is to beat the official TensorCircuit-NG baseline for the matched single-machine VQE workload through algorithmic and engineering improvements, then turn those improvements into a reliable assistant for optimizing TensorCircuit-NG scripts.

Candidate optimization gadgets:

1. **Algorithmic** — tensor-network contraction-path search and slicing search.
2. **Engineering** — scan-style control flow, ahead-of-time compilation, operator fusion or custom operators, automatic-differentiation checkpointing, memory offloading, and mixed precision.

## References

1. **TensorCircuit-NG** — focal reproduction target and benchmark source.
   "TensorCircuit-NG: A Universal, Composable, and Scalable Platform for Quantum Computing and Quantum Simulation." [arXiv:2602.14167](https://arxiv.org/abs/2602.14167).
2. **TensorCircuit** — first-generation software white paper.
   "TensorCircuit: a Quantum Software Framework for the NISQ Era." [arXiv:2205.10091](https://arxiv.org/abs/2205.10091).
3. **cotengra** — contraction-path optimization reference.
   "Hyper-optimized tensor network contraction." [arXiv:2002.01935](https://arxiv.org/abs/2002.01935).
4. **TensorCircuit-NG repository** — open-source framework and starter harness.
   [github.com/tensorcircuit/tensorcircuit-ng](https://github.com/tensorcircuit/tensorcircuit-ng).

## Coordination note

The original track note listed two online discussion slots: May 26, 2026 at 11:00 and May 27, 2026 at 11:00.
