# MPS (Matrix Product States)

## Reproduction target

Zauner-Stauber, Vanderstraeten, Fishman, Verstraete, Haegeman, "Variational optimization algorithms for uniform matrix product states," *Phys. Rev. B* **97**, 045145 (2018), [doi:10.1103/PhysRevB.97.045145](https://doi.org/10.1103/PhysRevB.97.045145), [arXiv:1701.07035](https://arxiv.org/abs/1701.07035).

Reproduce the **XXZ ground-state panels of Fig. 7** — a convergence benchmark of the three infinite/uniform MPS ground-state algorithms (VUMPS, IDMRG, iTEBD) on the spin XXZ chain, $H = \sum_i (S^x_i S^x_{i+1} + S^y_i S^y_{i+1} + \Delta\, S^z_i S^z_{i+1})$, plotting energy error and the tangent-space gradient norm $\lVert B\rVert$ against wall time:

1. **Fig. 7(a)** — spin-1 XXZ, $\Delta = 1$ (Haldane phase, **gapped**), bond dimension $D = 120$, 1-site unit cell. Reference $e_0 \approx -1.401484$.
2. **Fig. 7(b)** — spin-$\frac{1}{2}$ XXZ, $\Delta = 2$ (Néel-ordered, **gapped**), $D = 54$, 2-site unit cell.
3. **Fig. 7(c)** — spin-$\frac{1}{2}$ XXZ, $\Delta = 1$ (isotropic Heisenberg, **critical/gapless**), $D = 70$, 1-site unit cell via sublattice rotation. Reference $e_0 = \frac{1}{4} - \ln 2 \approx -0.44315$. This is the headline panel: VUMPS drives $\lVert B\rVert$ to machine precision while IDMRG and iTEBD stall.

The paper exploits **no symmetry** in this benchmark (to test the bare algorithm). Panel (d) (Hubbard) is outside this XXZ track.

## References

1. **VUMPS paper** — the reproduction target (above); source for the algorithms, the $\lVert B\rVert$ convergence criterion (Eq. 34), and the Eq. 29 canonical convention.
   Rendered in `.knowledge/literature/mps-based-algorithm/1701.07035_*.md`.
2. **Schollwöck** — modern MPS / DMRG / TEBD review.
   U. Schollwöck, "The density-matrix renormalization group in the age of matrix product states," *Ann. Phys.* **326**, 96 (2011). [doi:10.1016/j.aop.2010.09.012](https://doi.org/10.1016/j.aop.2010.09.012), [arXiv:1008.3477](https://arxiv.org/abs/1008.3477).
3. **Orús** — practical tensor-network / MPS introduction.
   R. Orús, "A practical introduction to tensor networks: Matrix product states and projected entangled pair states," *Ann. Phys.* **349**, 117 (2014). [doi:10.1016/j.aop.2014.06.013](https://doi.org/10.1016/j.aop.2014.06.013), [arXiv:1306.2164](https://arxiv.org/abs/1306.2164).
4. **MPSKit.jl** — research-grade Julia stack for infinite/finite MPS (VUMPS, IDMRG, DMRG, TDVP). Maintained by the QuantumKitHub / Verstraete group. [github](https://github.com/QuantumKitHub/MPSKit.jl). Used with MPSKitModels.jl and TensorKit.jl.
5. **TeNPy** — Python tensor-network library; the route for iTEBD (which MPSKit lacks).
   J. Hauschild and F. Pollmann, "Efficient numerical simulations with Tensor Networks: Tensor Network Python (TeNPy)," *SciPost Phys. Lect. Notes* **5** (2018). [doi:10.21468/SciPostPhysLectNotes.5](https://doi.org/10.21468/SciPostPhysLectNotes.5), [arXiv:1805.00055](https://arxiv.org/abs/1805.00055), [github](https://github.com/tenpy/tenpy).
6. **ITensor** — alternative Julia MPS stack (finite DMRG/TEBD; infinite via ITensorInfiniteMPS).
   M. Fishman, S. R. White, E. M. Stoudenmire, "The ITensor Software Library for Tensor Network Calculations," *SciPost Phys. Codebases* **4** (2022). [doi:10.21468/SciPostPhysCodeb.4](https://doi.org/10.21468/SciPostPhysCodeb.4), [arXiv:2007.14822](https://arxiv.org/abs/2007.14822), [github](https://github.com/ITensor/ITensors.jl).
