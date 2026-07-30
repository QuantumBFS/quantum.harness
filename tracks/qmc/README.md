# Quantum Monte Carlo

## Reproduction target

Nguyen, Shi, Xu, Zhang, "CPMC-Lab: A Matlab package for Constrained Path Monte Carlo calculations," *Computer Physics Communications* **185**, 3344 (2014), [doi:10.1016/j.cpc.2014.08.003](https://doi.org/10.1016/j.cpc.2014.08.003), [arXiv:1407.7967](https://arxiv.org/abs/1407.7967).

The official MATLAB constrained-path QMC (CPMC) package for the single-band repulsive Hubbard model; the paper documents the CPQMC algorithm in detail. CPMC controls the fermion sign problem by constraining the random walk with a trial wavefunction — trading an exact-but-exponentially-hard sign problem for a polynomial-cost, *systematically biased* (non-variational) ground-state energy whose size is set by trial-wavefunction quality. Which of the paper's figures to reproduce — the sign problem and constrained-path stability, energy vs interaction strength benchmarked against exact diagonalization, or finite-size scaling to the thermodynamic limit — is decided interactively when the track is started.

## References

1. **Zhang (2019)** — survey / main reference: AFQMC formalism (ground-state projection and finite-T grand-canonical), the sign/phase problem, the constrained-path and phaseless approximations.
   S. Zhang, "Auxiliary-Field Quantum Monte Carlo at Zero- and Finite-Temperature," in *Many-Body Methods for Real Materials*, eds. E. Pavarini, E. Koch, S. Zhang, Modeling and Simulation Vol. 9 (Forschungszentrum Jülich, 2019), ISBN 978-3-95806-400-3. [manuscript](https://www.cond-mat.de/events/correl19/manuscripts/zhang.pdf).
2. **CPMC-Lab** — the reproduction target above; detailed CPMC algorithm + MATLAB implementation.
   H. Nguyen, H. Shi, J. Xu, S. Zhang, *Computer Physics Communications* **185**, 3344 (2014). [doi:10.1016/j.cpc.2014.08.003](https://doi.org/10.1016/j.cpc.2014.08.003), [arXiv:1407.7967](https://arxiv.org/abs/1407.7967).
3. **Sandvik (2010)** — stochastic series expansion (SSE) methodology for sign-free spin/boson lattices.
   A. W. Sandvik, "Computational Studies of Quantum Spin Systems," *AIP Conf. Proc.* **1297**, 135 (2010). [doi:10.1063/1.3518900](https://doi.org/10.1063/1.3518900), [arXiv:1101.3281](https://arxiv.org/abs/1101.3281).
4. **Becca & Sorella (2017)** — textbook on QMC for correlated systems.
   F. Becca and S. Sorella, *Quantum Monte Carlo Approaches for Correlated Systems* (Cambridge University Press, 2017). [doi:10.1017/9781316417041](https://doi.org/10.1017/9781316417041).

## LlmNewtonGaussTuring TFIM solution

`solutions/LlmNewtonGaussTuring/` shares one graph, ED, SSE, and Berry-curvature
codebase across Challenges 148 and 73. Its audited contracts are:

- The paper-faithful Challenge 148 time aspect is `beta*h/L = c_tau`, so
  `beta = c_tau*L/h`; the current reproduction uses `c_tau=1` and its doubled
  finite-temperature check uses `c_tau=2`.
- The Challenge 73 FHS curvature is minus the normalized-overlap Wilson phase
  divided by the oriented plaquette area. Finite-grid FHS is checked against a
  same-size Jordan-Wigner oracle under grid refinement.
- The historical `dthetah_diagonal` quantity is only the prefactor-weighted ZZ
  expectation in the unrotated TFIM ensemble. It is not a generalized force or
  a physical component expectation in the rotated ground state.
- `config_checked=false` means no per-sweep world-line check was performed; the
  result exports `consistency_failures=-1`, never a misleading zero.
- The deterministic Stage 4 scanner is not yet a production runner: resumable
  cell manifests, atomic output, full build/host provenance, and hashes remain
  pending.
