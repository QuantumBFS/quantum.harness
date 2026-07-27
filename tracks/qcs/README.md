# Quantum Circuit Simulation

## Reproduction target

S.-X. Zhang et al., "TensorCircuit-NG: A Universal, Composable, and Scalable
Platform for Quantum Computing and Quantum Simulation," arXiv:2602.14167 (2026),
[arXiv:2602.14167](https://arxiv.org/abs/2602.14167).

Following the paper's Fig. 2, in a **non-distributed (single-machine)** setting:
reproduce and profile a single VQE step of the 1D transverse-field Ising model
(TFIM) — the forward expectation value plus the backward gradient — measuring
**compile time**, **run time**, and **memory**.

Both panels of Fig. 2 are distributed measurements: (a) speedup against GPU
count, (b) time per step across system sizes on a fixed 8-GPU cluster. The
single-machine counterpart is the 1-GPU point of panel (a), and that point is the
one value directly comparable to the paper. Distributed scaling is out of scope.

The circuit size is set by the hardware available — one tier, not both:

| Hardware | Circuit |
|---|---|
| GPU available | 32 qubits, 16 layers |
| CPU only | 24 qubits, 12 layers (baseline) |

Profile a range of sizes up to that ceiling, scaling depth with qubit number as
the paper does, so the outcome is a single-device time-and-memory curve rather
than one point. Sizes below the ceiling are new measurements, not reproductions.

Report compile time and run time separately — the first traced call versus the
warm call after compilation — alongside peak memory. Contraction-path search is
a separate cost, paid at every size.

The Hamiltonian, ansatz, and contraction settings follow the paper's Fig. 2
benchmark.

## References

1. **TensorCircuit-NG** — the reproduction target above; second-generation
   software whitepaper.
   S.-X. Zhang et al., arXiv:2602.14167 (2026).
   [arXiv:2602.14167](https://arxiv.org/abs/2602.14167).
2. **TensorCircuit** — first-generation software whitepaper.
   S.-X. Zhang et al., *Quantum* **7**, 912 (2023).
   [doi:10.22331/q-2023-02-02-912](https://doi.org/10.22331/q-2023-02-02-912),
   [arXiv:2205.10091](https://arxiv.org/abs/2205.10091).
3. **cotengra** — the core contraction-path reference.
   J. Gray and S. Kourtis, "Hyper-optimized tensor network contraction,"
   *Quantum* **5**, 410 (2021).
   [doi:10.22331/q-2021-03-15-410](https://doi.org/10.22331/q-2021-03-15-410),
   [arXiv:2002.01935](https://arxiv.org/abs/2002.01935).
4. TensorCircuit-NG — the open-source framework, which ships its own basic
   harness. [github](https://github.com/tensorcircuit/tensorcircuit-ng), driven
   via `/using-tensorcircuit-ng`.
