# PEPS (Projected Entangled Pair States)

## Reproduction target

R. van der Werff, "Simulating classical spin systems using the Corner Transfer
Matrix Renormalization Group method," Bachelor thesis, University of Amsterdam
(2016). Supervisor: P. Corboz. Local copy: [CTMRG-thesis.pdf](CTMRG-thesis.pdf) —
not on arXiv, no DOI, and not in the UvA thesis repository, so this file is the
only retrievable copy.

Its text and figures are extracted locally with the `download-ref` renderer.

Reproduce three figures for the 2D square-lattice classical Ising model
contracted by CTMRG:

1. **Fig. 10** — magnetization per site vs temperature at bond dimensions
   χ = 4, 6, 10, 20, against the exact curve.
2. **Fig. 16** — free energy per site vs temperature at χ = 8, 16, 24, 32, and
   its error against Onsager's solution.
3. **Fig. 17** — specific heat per site at χ = 60, whose logarithmic behaviour
   at T_c gives the critical exponent α = 0.

The CTMRG algorithm is implemented from the thesis — Figs. 4–9 give the lattice
growth, boundary contraction, singular-value truncation, and environment
renormalization — rather than called as a high-level routine from an existing
package. Tensor primitives may come from a library; the renormalization loop is
written here.

## References

1. **van der Werff (2016)** — the reproduction target above.
2. **Orús & Vidal (2009)** — CTMRG for infinite-lattice tensor contraction.
   *Phys. Rev. B* **80**, 094403.
   [arXiv:0905.3225](https://arxiv.org/abs/0905.3225).
3. TensorKit.jl for tensor primitives, PEPSKit.jl for comparison — driven via
   `/using-pepskit`.
