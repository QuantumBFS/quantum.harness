# Polynomial Optimization (moment-SOS / SOHS hierarchy)

Certified-bound track: noncommutative polynomial optimization via the structured
moment-SOHS hierarchy, solved as a semidefinite program. Unlike every other track
here, it returns a **provable lower bound** on the ground-state energy (not an
estimate) — the natural rigorous cross-check for a variational / QMC value.

- **Method card:** `/method-polyopt` — routing, certification role, SDP cost heuristic.
- **Software:** `/using-nctssos` — NCTSSoS.jl + Clarabel (`make install nctssos`).
- **Modeling brain:** `/polyopt-guide` (reused upstream, `exAClior/easy-nctssos`) — algebra / formulation / sparsity / GNS. Ground truth on modeling.

## Reproduction target

Wang, Surace, Frérot, Legat, Renou, Magron, Acín, "Certifying ground-state
properties of quantum many-body systems," *Phys. Rev. X* **14**, 031006 (2024),
[doi:10.1103/PhysRevX.14.031006](https://doi.org/10.1103/PhysRevX.14.031006),
[arXiv:2310.05844](https://arxiv.org/abs/2310.05844).

**Figure 8** — ground-state energy of the **square-lattice antiferromagnetic
Heisenberg model** with periodic boundary conditions: the certified SDP **lower
bound** on the energy per site vs system size, compared to quantum Monte Carlo
(QMC ≈ exact). Paper covers N = L×L with L = 4, 6, 8, 10.

**Scope for this track: L = 4, 6, 8** (drop the paper's L = 10 — it is the
expensive point and the one where degree-4 monomials are discarded).

- **Hamiltonian.** H = ¼ Σ_{⟨ij⟩} Σ_{a∈{x,y,z}} σ^a_i σ^a_j on the L×L square
  lattice, nearest-neighbor bonds, PBC (Eq. 13). Antiferromagnetic. Energy
  reported **per site** (E/N).
- **Method.** NCTSSoS moment-SOHS / NPA-style SDP via `/method-polyopt` →
  `/using-nctssos`; Pauli algebra; monomial set and sparsity per `/polyopt-guide`
  (the paper's basis: identity, single σ, two-spin σσ up to range 3, and a set of
  three-/four-spin terms — see the Fig. 8 paragraph in the rendered paper).
- **Target metric.** The certified lower bound E_SDP/N at each L, plotted vs L
  beside the QMC reference; the takeaway is the ~1% relative gap E_SDP ≤ E₀ ≈ E_MC.

### Benchmark (Table IX — the comparison anchor)

| L | N | E_SDP/N (certified lower bound) | E_MC/N (QMC ≈ exact) |
|---|---|---|---|
| 4 | 16 | −0.70305078 | −0.7017777 |
| 6 | 36 | −0.68317181 | −0.6788734 |
| 8 | 64 | −0.67967080 | −0.6734875 |

E_SDP is below E_MC at every size (a valid lower bound: E_SDP ≤ E₀ ≤ E_MC),
relative gap ≈ 0.002–0.009.

## References

1. **Reproduction target** — [@wang_2024_certifying] (above). Rendered:
   `.knowledge/literature/polynomial-optimization/2310.05844_*.md`; Table IX in Appendix F. Ships the Julia package QMBCertify.
2. **NCTSSoS.jl** — the solver. [github.com/QuantumSOS/NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl).
3. **Optimization of Polynomials in Non-Commuting Variables** — Burgdorf, Klep & Povh, SpringerBriefs in Mathematics, Springer (2016), [doi:10.1007/978-3-319-33338-0](https://doi.org/10.1007/978-3-319-33338-0). NC-variables theory background ([@burgdorf_2016_optimization]).
4. **Moment-SOS / NPA hierarchy** — Navascués, Pironio, Acín, *New J. Phys.* **10**, 073013 (2008), [arXiv:0803.4290](https://arxiv.org/abs/0803.4290).
