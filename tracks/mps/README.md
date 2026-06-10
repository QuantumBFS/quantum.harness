# MPS — Linearized Tensor Renormalization Group (LTRG)

## Reproduction target

Li, Ran, Gong, Zhao, Xi, Ye, Su, "Linearized Tensor Renormalization Group Algorithm for the Calculation of Thermodynamic Properties of Quantum Lattice Models," *Phys. Rev. Lett.* **106**, 127202 (2011). [doi:10.1103/PhysRevLett.106.127202](https://doi.org/10.1103/PhysRevLett.106.127202), [arXiv:1011.0155](https://arxiv.org/abs/1011.0155).

Target: 1D spin-½ XY chain, Figs. 4–6a. Model $h_{i,i+1} = -J(S^x_i S^x_{i+1} + S^y_i S^y_{i+1})$, $J = 1$, $N = 2^{100}$. Parameters: Trotter step $\tau \in \{0.1, 0.05, 0.02, 0.01\}$, bond dimension $Dc \in \{100, 150\}$.

| Quantity | Fig. | Benchmark vs exact |
|---|---|---|
| Free energy / site $f$ | 4, 5a | $\delta f \approx 7\times10^{-6}$ ($\beta = 120$, $Dc = 150$) |
| Internal energy / site $e$ | 5b | $(e - e_0)/e_0 \approx 10^{-4}$ ($\beta = 120$, $Dc = 150$) |
| Specific heat $C$ | 6a | exact to $T/J \approx 0.008$ ($Dc = 150$) |

Benchmarks: exact (Jordan–Wigner free fermions), primary; TMRG ($M \le 200$), secondary. Error sources: Trotter ($\tau \to 0$) at high $T$, truncation ($Dc$) at low $T$. 2D honeycomb out of scope.

## References

1. W. Li, S.-J. Ran, S.-S. Gong, Y. Zhao, B. Xi, F. Ye, G. Su, *Phys. Rev. Lett.* **106**, 127202 (2011). [doi:10.1103/PhysRevLett.106.127202](https://doi.org/10.1103/PhysRevLett.106.127202), [arXiv:1011.0155](https://arxiv.org/abs/1011.0155). Rendered: `.knowledge/literature/ltrg/1011.0155_*.md`.
2. ITensors.jl — [github](https://github.com/ITensor/ITensors.jl), driven via `/using-itensors`.
