<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Stochastic Series Expansion / Worldline QMC (SSE)

Finite-temperature Monte Carlo for spins and bosons via importance-sampled operator-loop updates on the Taylor expansion of `e^{−βH}`.

## Method card

### What it is

SSE samples the high-temperature expansion of the partition function `Z = Tr[e^{−βH}] = Σ_n (−β)^n/n! Tr[H^n]` by stochastically selecting a sequence of bond operators. The expansion order `⟨n⟩ ∝ N·β` sets the natural cutoff. Directed-loop (or operator-loop) updates move through the operator string and update both operator types and spin configurations simultaneously, removing critical slowing down near phase transitions (B6). In the worldline picture (equivalent formulation) the algorithm propagates particle worldlines in imaginary time. The method is sign-free for unfrustrated bipartite spin systems (Marshall sign rule) and bosons, giving numerically exact finite-temperature thermodynamics at scale.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Finite-T thermodynamics (energy, specific heat, susceptibility) · equal- and imaginary-time correlations · structure factors · spin stiffness / superfluid density · Binder cumulants · winding-number distributions | Spectra `S(q,ω)` require analytic continuation (ill-posed); real-time dynamics blocked by the dynamical sign problem. |
| M2 regime | Finite-T (primary); GS accessible via large `β` limit | The large-`β` limit extracts GS properties but cost grows with `β`. |
| M3 accuracy class | Numerically exact (in the sign-free regime), stochastic | Statistical error `∝1/√(N_s·⟨s⟩)` where `⟨s⟩=1` in sign-free cases; in sign-ful cases accuracy degrades as `⟨s⟩→0`. |
| M4 dimension fit (A1) | Any dimension (1D, 2D, 3D) | The decisive advantage over tensor-network methods in 2D/3D; no bond-dimension wall. |
| M5 statistics & local dim (A3) | Spins / hard-core bosons / soft-core bosons (sign-free); fermions / frustrated spins introduce the sign | Local dimension `d` enters via the operator basis; large `d` increases the diagonal/off-diagonal operator pool but does not cause exponential cost. |
| M6 entanglement regime (B5) | Volume-law tolerated | No entanglement restriction — worldlines can represent arbitrary correlations in the sign-free sector. |
| M7 sign-problem dependence (C12) | Sign-free for unfrustrated bipartite spins (Marshall sign rule) and bosons; B8 frustration / A3 fermions turn the sign on; sign-ful cost `∝1/⟨s⟩²~e^{2βNΔf}` | The primary gate: check bipartiteness and absence of frustration before choosing SSE. |
| M8 symmetry exploitation (C9/C10) | U(1) (Sᶻ, particle number) conservation reduces operator pool; translation / point-group target momentum sectors for correlations | Symmetry reduces variance but is not required for correctness. |
| M9 time complexity | `O(N·β)` per sweep (expansion order `⟨n⟩∝N·β`); statistical error `1/√(N_s·⟨s⟩)`; directed-loop/operator-loop updates remove critical slowing down; sign-ful cost `∝1/⟨s⟩²~e^{2βNΔf}` | Cost is linear in `N` and `β` in the sign-free regime — highly favorable for large systems at moderate temperatures. |
| M10 memory | `O(N·β)` to store the operator string | Operator string length `⟨n⟩∝N·β`; configuration vector `O(N)`; total modest compared to wave-function methods. |
| M11 control knob | `N_s` (Monte Carlo sweeps) → statistical error `∝1/√N_s`; `β` (inverse temperature) → GS vs finite-T physics; cutoff `n_max ≥ ⟨n⟩` | Convergence in `N_s` straightforward; `β` tuned to target temperature or GS extrapolation. |
| M12 scale frontier | Thousands to tens-of-thousands of sites in the sign-free regime | Thermodynamic-limit extrapolations routine; limited only by autocorrelation and the sign problem. |
| M13 primary approximation / bias | None in the sign-free regime (numerically exact); sign-ful approximation has uncontrolled bias unless `⟨s⟩≈1` | In the sign-ful regime the average-sign collapse is the approximation; no free-parameter knob removes it. |
| M14 hard blocker / failure mode | Sign problem for frustrated (B8) spins and fermions (A3): cost `∝e^{2βNΔf}` → exponential wall; real-time dynamics (dynamical sign problem) | Even weak frustration can turn the sign on; analytic continuation from imaginary-time data is ill-conditioned. |

### Cost & scaling

- Time: `O(N·β)` per sweep (sign-free); cost `∝1/⟨s⟩²~e^{2βNΔf}` in sign-ful cases
- Memory: `O(N·β)` operator string
- Control knob: `N_s` (sweeps → statistical error `∝1/√N_s`); `β` controls temperature/GS convergence
- Scale frontier: thousands–tens-of-thousands of sites (sign-free bipartite spin / boson models)

### Accuracy & guarantees

- Class: numerically exact (sign-free), stochastic
- Primary approximation & its control: none (sign-free); sign-ful regime has sign collapse (uncontrolled bias)
- Error scaling: statistical `∝1/√(N_s·⟨s⟩)`; systematic errors absent in sign-free case

### Tasks it computes

- Finite-temperature thermodynamics: internal energy, specific heat, magnetic susceptibility, compressibility
- Imaginary-time and equal-time correlations `⟨A(τ)B(0)⟩`
- Structure factors `S(q)` and `S(q,τ)` → spectral function `S(q,ω)` via analytic continuation (MaxEnt/SOAC)
- Spin stiffness (helicity modulus) and superfluid density via winding-number estimator
- Binder cumulants and finite-size scaling for phase-transition analysis
- GS energy and correlations via large-`β` extrapolation

### Recommended for (models / regimes)

- **Unfrustrated bipartite spin models (B8=no):** Heisenberg, XXZ, transverse-field Ising on square/honeycomb/cubic lattices — the method of choice for finite-T thermodynamics
- **Bosonic systems (A3 bosons):** Bose-Hubbard model, lattice bosons — sign-free, efficient worm/SSE updates
- **Any dimension (A1):** the key advantage over tensor-network methods for 2D/3D at finite temperature
- **Critical phenomena (B6):** directed-loop updates eliminate critical slowing down near phase transitions
- Per `method-property-map.md`: first choice for sign-free finite-T spin/boson models; blocked by B8 frustration and A3 fermions

### Key reference

[@syljuasen_2002_quantum] — introduces directed-loop updates in SSE; the standard implementation reference for efficient worldline/SSE codes.
Rendered: `../../literature/quantum-monte-carlo/cond-mat-0202316_quantum-monte-carlo-with-directed-loops.md` _(reused)_.

[@alet_2003_generalized] — generalized directed-loop method; extends applicability to wider operator classes.
Rendered: `../../literature/quantum-monte-carlo/cond-mat-0308495_generalized-directed-loop-method-for-quantum-monte-carlo-sim.md` _(reused)_.

### Benchmarks

- Heisenberg square lattice (`N=64×64`, `T/J=0.5`): susceptibility, stiffness converged to sub-percent accuracy with `N_s~10⁵` sweeps [@syljuasen_2002_quantum].
- Critical slowing down suppression: directed-loop/operator-loop updates greatly reduce critical slowing down — autocorrelation `τ_auto~L^z` with `z` reduced to ≈1–1.5 for the spin stiffness (vs `z≈2` for local updates) [@sandvik_2010_computational].

## How it is used / Operational

**Owning skill:** `/method-qmc`, with tool skill `/using-sse`.

**Default workflow:**
1. Verify the model is sign-free: unfrustrated bipartite lattice (Marshall sign rule) or bosonic statistics.
2. Set up the diagonal/off-diagonal operator pool for the Hamiltonian bond terms.
3. Initialize the operator string and spin configuration; run thermalization sweeps.
4. Accumulate measurements (energy, susceptibility, correlations, winding numbers) over `N_s` sweeps.
5. Extract spectral functions via analytic continuation (MaxEnt) if `S(q,ω)` is needed.
6. Perform finite-size scaling over multiple `L` to extract thermodynamic-limit quantities.

**Verification pointers:**
- Specific heat sum rule: `∫₀^∞ C_v(T) dT/T = S(T=∞) - S(T=0)` (entropy).
- Susceptibility: compare χ(T→0) to ED or exact Bethe ansatz for 1D Heisenberg as a benchmark.
- Average sign `⟨s⟩` should be checked — if `⟨s⟩ < 0.5`, results are unreliable.

**Cross-links:**
- Survey: `method-survey.md` §4.3 (Stochastic series expansion / worldline QMC)
- Model↔method gate: `method-property-map.md` (SSE/worldline profile)
- Complementary methods: DQMC for fermionic models; PIMC for continuum bosons; tensor-network methods for 1D/quasi-1D
