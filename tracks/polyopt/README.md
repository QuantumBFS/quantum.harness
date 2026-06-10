# Polynomial Optimization

## Reproduction target

Wang, Surace, Frérot, Legat, Renou, Magron, Acín, "Certifying ground-state properties of quantum many-body systems," *Phys. Rev. X* **14**, 031006 (2024), [doi:10.1103/PhysRevX.14.031006](https://doi.org/10.1103/PhysRevX.14.031006), [arXiv:2310.05844](https://arxiv.org/abs/2310.05844).

Reproduce **Figure 8** — the certified ground-state energy per site of the square-lattice antiferromagnetic Heisenberg model, $H = \frac{1}{4}\sum_{\langle ij\rangle}\vec{\sigma}_i\cdot\vec{\sigma}_j$ on the $L\times L$ lattice with periodic boundary conditions (Eq. 13), versus system size. The moment-SOHS / NPA-style semidefinite relaxation returns a *provable* lower bound $E_\mathrm{SDP}\le E_0$ rather than a variational estimate, plotted against quantum Monte Carlo ($\approx$ exact). Scope: $N = L\times L$ with $L = 4, 6, 8$ (the paper's $L = 10$, where degree-4 monomials are discarded, is dropped).

### Benchmark (Table IX)

| L | N | E_SDP/N (certified lower bound) | E_MC/N (QMC ≈ exact) |
|---|---|---|---|
| 4 | 16 | −0.70305078 | −0.7017777 |
| 6 | 36 | −0.68317181 | −0.6788734 |
| 8 | 64 | −0.67967080 | −0.6734875 |

The bound sits below the QMC value at every size ($E_\mathrm{SDP}\le E_0\le E_\mathrm{MC}$), relative gap $\approx 0.002$–$0.009$.

## References

1. **Certifying ground-state properties** — the reproduction target above; certified moment-SOHS SDP bounds for 1D/2D spin systems. Ships the Julia package QMBCertify.
   J. Wang, J. Surace, I. Frérot, B. Legat, M.-O. Renou, V. Magron, A. Acín, "Certifying ground-state properties of quantum many-body systems," *Phys. Rev. X* **14**, 031006 (2024). [doi:10.1103/PhysRevX.14.031006](https://doi.org/10.1103/PhysRevX.14.031006), [arXiv:2310.05844](https://arxiv.org/abs/2310.05844).
2. **Burgdorf, Klep & Povh** — noncommutative polynomial optimization: eigenvalue and trace optimization via the moment-SOHS hierarchy.
   S. Burgdorf, I. Klep, J. Povh, *Optimization of Polynomials in Non-Commuting Variables*, SpringerBriefs in Mathematics (Springer, 2016). [doi:10.1007/978-3-319-33338-0](https://doi.org/10.1007/978-3-319-33338-0).
3. **NPA hierarchy** — convergent moment-SOS relaxations for noncommutative polynomial optimization.
   M. Navascués, S. Pironio, A. Acín, "A convergent hierarchy of semidefinite programs characterizing the set of quantum correlations," *New J. Phys.* **10**, 073013 (2008). [doi:10.1088/1367-2630/10/7/073013](https://doi.org/10.1088/1367-2630/10/7/073013), [arXiv:0803.4290](https://arxiv.org/abs/0803.4290).
4. **NCTSSoS.jl** — moment-SOHS SDP solver with correlative/term sparsity (Clarabel/Mosek backend). [github](https://github.com/QuantumSOS/NCTSSoS.jl).
