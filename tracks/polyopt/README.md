# Polynomial Optimization

## Reproduction target

Wang, Jansen, Frérot, Renou, Magron, Acín, "Scalable Ground-State Certification of Quantum Spin Systems via Structured Noncommutative Polynomial Optimization," arXiv:2604.01555 (2026), [arXiv:2604.01555](https://arxiv.org/abs/2604.01555).

Reproduce **Table 8 / Figure 7** — the certified ground-state energy per spin of the square-lattice antiferromagnetic Heisenberg model, $H = \frac{1}{4}\sum_{\langle ij\rangle}\vec{\sigma}_i\cdot\vec{\sigma}_j$ on the $L\times L$ lattice with periodic boundary conditions (Eq. 4.3), versus system size. The structured moment-SOHS / NPA-style semidefinite relaxation — correlative/term sparsity plus the model's sign, translation, and conjugation symmetries — returns a *provable* lower bound $E_\mathrm{SDP}\le E_0$ rather than a variational estimate, and scales to $L = 16$ (256 spins) in the paper. Scope for this track: $L = 4, 6, 8$, benchmarked against exact diagonalization ($L = 4, 6$) and QMC ($L = 8$).

### Benchmark (Table 8)

| L | N | E_SDP/N (certified lower bound) | E_ref/N (ED for L≤6, QMC for L=8) | rel. gap |
|---|---|---|---|---|
| 4 | 16 | −0.701783 | −0.701780 | 0.00% |
| 6 | 36 | −0.680886 | −0.678872 | 0.30% |
| 8 | 64 | −0.676370 | −0.673487 | 0.43% |

The bound sits at or below the reference at every size ($E_\mathrm{SDP}\le E_0\le E_\mathrm{ref}$), tightening on the predecessor work by orders of magnitude.

## References

1. **Scalable Ground-State Certification** — the reproduction target above; structured moment-SOHS SDP scaling certified spin-system bounds to 16×16 lattices. Ships the Julia package QMBCertify.
   J. Wang, D. Jansen, I. Frérot, M.-O. Renou, V. Magron, A. Acín, "Scalable Ground-State Certification of Quantum Spin Systems via Structured Noncommutative Polynomial Optimization," arXiv:2604.01555 (2026). [arXiv:2604.01555](https://arxiv.org/abs/2604.01555), [github](https://github.com/wangjie212/QMBCertify).
2. **Burgdorf, Klep & Povh** — noncommutative polynomial optimization: eigenvalue and trace optimization via the moment-SOHS hierarchy.
   S. Burgdorf, I. Klep, J. Povh, *Optimization of Polynomials in Non-Commuting Variables*, SpringerBriefs in Mathematics (Springer, 2016). [doi:10.1007/978-3-319-33338-0](https://doi.org/10.1007/978-3-319-33338-0).
3. **NPA hierarchy** — convergent moment-SOS relaxations for noncommutative polynomial optimization.
   M. Navascués, S. Pironio, A. Acín, "A convergent hierarchy of semidefinite programs characterizing the set of quantum correlations," *New J. Phys.* **10**, 073013 (2008). [doi:10.1088/1367-2630/10/7/073013](https://doi.org/10.1088/1367-2630/10/7/073013), [arXiv:0803.4290](https://arxiv.org/abs/0803.4290).
4. **Software** — QMBCertify.jl, the paper's structured-NPA reproduction code (1D/2D Heisenberg; Mosek SDP, exact rational rounding); NCTSSoS.jl is the general-purpose NC-polyopt engine (correlative/term sparsity, Clarabel/Mosek backend). [QMBCertify](https://github.com/wangjie212/QMBCertify), [NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl).
