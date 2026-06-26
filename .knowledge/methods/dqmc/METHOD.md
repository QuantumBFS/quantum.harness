<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Determinant Quantum Monte Carlo (DQMC / BSS)

Finite-temperature auxiliary-field QMC for interacting fermions: Hubbard–Stratonovich decouples the interaction, fermions are traced out as a determinant, and the auxiliary fields are sampled by Monte Carlo.

## Method card

### What it is

DQMC (Blankenbecler–Scalapino–Sugar) decouples the quartic interaction via a Hubbard–Stratonovich transformation, introducing an auxiliary field `{s_{i,τ}}` on each site and imaginary-time slice `τ=1,…,N_τ` (`N_τ=β/Δτ`). Fermions are integrated out exactly, yielding a weight `det[M↑(s)]·det[M↓(s)]` which is sampled by Monte Carlo over auxiliary-field configurations. At half-filling on bipartite lattices a particle-hole symmetry guarantees `det↑·det↓=|det|²≥0`, making the algorithm sign-free and numerically exact. The `N×N` matrices `M_σ(s)` are updated rank-1 or rank-N using stabilized matrix products (`QR/SVD` wraps), keeping numerical errors under control at large `β`.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Finite-T energy · double occupancy · magnetic and charge structure factors `S(q)` · single-particle Green's function `G(k,τ)` → spectral function `A(k,ω)` and self-energy via analytic continuation · superconducting pairing susceptibilities | Real-time dynamics blocked; `A(k,ω)` requires MaxEnt or SOAC analytic continuation (ill-posed). |
| M2 regime | Finite-T (primary); GS limit via large `β` | Cost grows as `β` → ∞; the GS is better attacked by AFQMC-CPMC. |
| M3 accuracy class | Numerically exact (sign-free regime), stochastic; controlled-bias (Trotter `O(Δτ²)`) | Statistical error `∝1/√N_s`; Trotter error eliminated by `Δτ→0` extrapolation; sign collapse in sign-ful regime. |
| M4 dimension fit (A1) | Any dimension (1D, 2D, 3D) | Sign-free condition depends on lattice bipartiteness and filling, not dimension. |
| M5 statistics & local dim (A3) | Fermions (primary); mixed fermion-boson via partial trace | `d=4` (Hubbard: empty, ↑, ↓, ↑↓); `N_τ=β/Δτ` slices; cost `O(βN³)` grows fast with `N`. |
| M6 entanglement regime (B5) | Volume-law tolerated | Auxiliary-field sampling imposes no entanglement restriction; the sign problem is the gate, not entanglement. |
| M7 sign-problem dependence (C12) | Sign-free at half-filling on bipartite lattices (`det↑det↓=\|det\|²≥0`) and attractive Hubbard at any filling; D14 doping / B8 frustration turn the sign on; sign `⟨s⟩~e^{−βNΔf}` → cost `∝e^{2βNΔf}` | Half-filling + bipartite = the canonical sign-free condition; any deviation from half-filling on repulsive Hubbard leads to the sign problem. |
| M8 symmetry exploitation (C9/C10) | Particle-hole symmetry (C9) at half-filling on bipartite lattices is the sign-free condition; translation/point-group reduce momentum-resolved measurements but do not change the core algorithm | PH symmetry is the decisive symmetry here — it is a correctness condition, not merely a speedup. |
| M9 time complexity | `O(β·N³)` per sweep (`N×N` matrix products over `N_τ=β/Δτ` slices with numerical stabilization); sign-ful cost `∝e^{2βNΔf}` | The `N³` matrix-algebra cost limits system size to `N~200–400`; lower `T` (larger `β`) is doubly costly: more slices and worse sign. |
| M10 memory | `O(N²·N_τ)` | Stores the `N×N` equal-time Green's function matrix plus `N_τ` auxiliary-field configurations. |
| M11 control knob | `Δτ` (Trotter step) → Trotter error `O(Δτ²)`; `N_s` (sweeps) → statistical error `∝1/√N_s`; `β` (inverse temperature) | Extrapolate `Δτ→0` for Trotter-free results; check convergence in `N_s`. |
| M12 scale frontier | `N~100–400` sites routine; `N~1000` possible on HPC with stabilization; thermodynamic limit via finite-size scaling | Sign-free regime: large-scale studies of Hubbard model on square lattice up to `N=20×20`. |
| M13 primary approximation / bias | Trotter discretization error `O(Δτ²)` (controlled, eliminated by `Δτ→0` extrapolation); sign collapse in sign-ful regimes (uncontrolled) | In sign-free cases the only approximation is controllable Trotter error and statistical noise. |
| M14 hard blocker / failure mode | Sign problem away from half-filling (D14 doping) and with frustration (B8): cost `∝e^{2βNΔf}`; low-T limit compounds both cost and sign penalty | Large `β` and large `N` simultaneously is the hardest regime; sign problem is exponential in both. |

### Cost & scaling

- Time: `O(β·N³)` per sweep; sign-ful cost `∝e^{2βNΔf}`
- Memory: `O(N²·N_τ)` with `N_τ=β/Δτ`
- Control knob: `Δτ` (Trotter error `O(Δτ²)`); `N_s` (statistical error `∝1/√N_s`)
- Scale frontier: `N~100–400` routine (sign-free); `N~1000` HPC; finite-size scaling to thermodynamic limit

### Accuracy & guarantees

- Class: numerically exact (sign-free, stochastic); controlled-bias Trotter error
- Primary approximation & its control: Trotter discretization `O(Δτ²)` → controlled by `Δτ→0` extrapolation
- Error scaling: statistical `∝1/√N_s`; Trotter `O(Δτ²)`; sign-ful `∝1/⟨s⟩²`

### Tasks it computes

- Finite-temperature energy, specific heat, double occupancy
- Magnetic and charge structure factors `S(q)`, compressibility
- Single-particle Green's function `G(k,τ)` → spectral function `A(k,ω)` via analytic continuation
- Self-energy `Σ(k,ω)` from Dyson's equation applied to `G(k,τ)`
- Superconducting pairing susceptibilities and pair-field correlations
- Imaginary-time correlations for dynamic susceptibilities

### Recommended for (models / regimes)

- **Repulsive Hubbard model at half-filling (D14):** the canonical sign-free regime; benchmark-quality finite-T phase diagram
- **Attractive Hubbard at any filling:** sign-free, ideal for BCS–BEC crossover studies
- **Finite-T magnetic and charge order:** square-lattice Heisenberg-Hubbard at half-filling up to `N~400`
- **Single-particle spectral functions on fermion models:** DQMC + MaxEnt/SOAC → `A(k,ω)` for comparison with ARPES
- Per `method-property-map.md`: preferred over AFQMC-CPMC when finite-T thermodynamics is needed; blocked by D14 doping in sign-ful regimes

### Key reference

[@bercx_2017_alf] — the ALF (Algorithms for Lattice Fermions) code documentation; comprehensive reference for the stabilized DQMC algorithm, Green's function updates, and observable implementations.
Rendered: `../../literature/quantum-monte-carlo/1704.00131_the-alf-algorithms-for-lattice-fermions-project-release-1-0.md` _(reused)_.

### Benchmarks

- Hubbard model half-filling square lattice (`N=16×16`, `U/t=4`, `β=8`): energy, double occupancy, structure factor converged [@bercx_2017_alf; verified in `method-survey.md` §4.4].
- Trotter extrapolation: `Δτ=0.05`–`0.1` typically sufficient; linear extrapolation in `Δτ²` removes systematic error to < 0.1% [@bercx_2017_alf].

## How it is used / Operational

**Owning skill:** `/method-qmc`.

**Default workflow:**
1. Verify sign-free condition: bipartite lattice + half-filling, or attractive Hubbard.
2. Set `Δτ` (typically `0.05`–`0.1`), `β`, and system size `N`; initialize auxiliary field randomly.
3. Perform stabilized matrix product updates (`QR`/`SVD` wrap every `N_stab~10` slices).
4. Accumulate measurements of `G(τ)`, structure factors, double occupancy over `N_s` sweeps.
5. Extrapolate `Δτ→0` using two or three `Δτ` values; check `N_s` convergence.
6. For spectral functions: feed `G(k,τ)` into MaxEnt/SOAC analytic continuation.

**Verification pointers:**
- At half-filling check `⟨s⟩=1.0` (sign-free condition satisfied).
- Double occupancy `⟨n↑n↓⟩` at `U→0` should approach `0.25` (non-interacting); `U→∞` should approach 0.
- Compare to ED on small clusters (`N≤16`) for energy and structure factor as baseline.

**Cross-links:**
- Survey: `method-survey.md` §4.4 (Determinant QMC / BSS)
- Model↔method gate: `method-property-map.md` (DQMC profile)
- Complementary methods: AFQMC-CPMC for GS and doped regimes; SSE for spin/boson models; analytic continuation codes (ALF, ana_cont) for spectral functions
