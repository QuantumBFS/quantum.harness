# cpafqmc — Diagnosing ergodicity in constrained-path AFQMC

**Team:** cpafqmc
**Members:** Yifan Chen

**Challenge:** Diagnosing ergodicity in Constrained Path Auxiliary Field Quantum Monte Carlo (#90)

**Released by:** Mingpu Qin (Shanghai Jiao Tong University)

## The question

In CP-AFQMC, walkers are discarded when they intersect the nodal surface ⟨ψ|ψ_T⟩ = 0. The topology of the allowed space is poorly understood — it may fragment into disconnected domains, preventing the random walk from exploring the full space and introducing an uncontrolled ergodicity bias.

**Goal:** Develop a visualization method for the high-dimensional Slater determinant space to diagnose when and how ergodicity breaks down.

## References

- Zhang, S. *Auxiliary-Field Quantum Monte Carlo for Correlated Electron Systems*, in Emergent Phenomena in Correlated Matter, Vol. 3 (2013)
- Qin, M., Shi, H., Zhang, S. PRB 94, 085103 (2016)
