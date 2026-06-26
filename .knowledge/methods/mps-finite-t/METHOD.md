<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# MPS Finite-Temperature Methods (mps-finite-t)

MPS-based finite-temperature simulation via purification/ancilla (thermofield) or METTS (minimally entangled typical thermal states), computing thermal expectation values `⟨O⟩_β` for 1D quantum lattice models.

## Method card

### What it is

Two complementary MPS methods target finite-T equilibrium. **Purification (ancilla / thermofield double):** each physical site gains an ancilla copy (local dim `d→d²`), and the maximally entangled state `|I⟩ = ∑_n |n⟩_phys|n⟩_anc / √d^N` is evolved in imaginary time `β/2` to yield a purification `|ρ(β)⟩` of the thermal state `ρ(β) = e^{-βH}/Z`; thermal expectation values follow as `⟨O⟩_β = ⟨ρ(β)|O_phys|ρ(β)⟩`. **METTS:** sample typical thermal states by (i) collapse the current pure state to a classical product state, (ii) evolve it in imaginary time to `β/2`, (iii) measure, (iv) re-collapse and repeat — a Markov chain over pure states whose average reproduces `⟨O⟩_β` with lower entanglement per sample than the full purification, at the cost of `N_s` stochastic samples.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Free energy · internal energy · specific heat `C_v` · magnetic susceptibility `χ` · finite-T correlations · finite-T spectral functions (combine with real-time TDVP/TEBD) | Thermodynamic quantities from `⟨H⟩_β`, `⟨H²⟩_β − ⟨H⟩²_β`; finite-T spectral functions require additional real-time step after reaching `β`. |
| M2 regime | Finite-T thermodynamics (D13) | Core purpose: equilibrium thermal properties at target inverse temperature `β`; not a real-time method (though finite-T spectral functions combine both). |
| M3 accuracy class | Controlled deterministic (purification) + controlled stochastic (METTS) | Purification: controlled by `χ` and Trotter `Δτ`; METTS: additionally stochastic `1/√N_s` from sampling; both are systematically improvable. |
| M4 dimension fit (A1) | 1D native; quasi-1D (ladders/narrow cylinders) feasible; **walls in 2D** | Same as TEBD/TDVP: entanglement of thermal state grows as T drops, worsening in 2D; purification maps to a `(d²)`-dim 1D problem. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion / any; local dim `d→d²` for purification | Doubling `d` to `d²` raises per-site cost; for spin-½ `d²=4` (manageable); for Hubbard `d=4→16` (expensive); METTS avoids `d²` by collapsing to product states. |
| M6 entanglement regime (B5) | Moderate at high T (area-law); grows as T→0 → `χ` diverges | Entanglement of purified thermal state rises as T drops → `χ` must grow at low T; METTS samples states with lower entanglement → cheaper at intermediate T. |
| M7 sign-problem dependence (C12) | Sign-immune | Tensor-network method; no Monte Carlo sign problem (METTS uses classical sampling, no quantum sign). |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂ quantum-number-conserving tensors for both purification and METTS | Symmetry doubles the block structure (physical + ancilla); still provides ~5–10× speedup. |
| M9 time complexity | Purification: **`O(N·d²·χ³)`** per imaginary-time step × `β/Δτ` steps; METTS: `O(N·d·χ³)` per sample × `N_s` samples | METTS per-sample cost uses `d` (not `d²`) and smaller `χ` (typical states); total cost `N_s · O(N·d·χ³)`; tradeoff vs purification depends on `d` and required accuracy. |
| M10 memory | Purification: `O(N·d²·χ²)`; METTS: `O(N·d·χ²)` per sample | Purification memory dominated by doubled local dim; METTS memory is standard MPS size. |
| M11 control knob | `χ` (truncation error) + Trotter step `Δτ` (`O(Δτ^p)` error) + `N_s` samples (METTS statistical error `1/√N_s`) | Three independent knobs for METTS; two for purification; all must be converged. |
| M12 scale frontier | Purification: `N~200–500` sites at moderate T (β`J~10`); METTS: comparable or larger `N` at intermediate T | Low-T limit `β→∞` requires large `χ` for both methods; METTS is competitive at intermediate T where typical states have lower entanglement. |
| M13 primary approximation / bias | Purification: finite-`χ` SVD truncation (controlled) + Trotter `O(Δτ^p)` (controlled); METTS: additionally stochastic sampling bias `1/√N_s` | Purification is a deterministic approximation; METTS adds a stochastic component — must check ergodicity of the collapse chain. |
| M14 hard blocker / failure mode | Low-T entanglement divergence: as `β→∞`, thermal-state entanglement → GS entanglement → `χ` must grow; 2D walls (`χ~e^{cW}`); large local dim `d` makes purification expensive (`d²` scaling); METTS ergodicity failure for some collapse bases at very low T | The low-T limit is where both methods become most expensive; consider DMRG+GS extrapolation for `T→0`. |

### Cost & scaling

- Time: Purification `O(N·d²·χ³)` per imaginary-time step; METTS `O(N_s · N·d·χ³)` per sample
- Memory: Purification `O(N·d²·χ²)`; METTS `O(N·d·χ²)` per sample
- Control knob: `χ` + `Δτ` (+ `N_s` samples for METTS)
- Scale frontier: `N~200–500` at moderate-T purification; similar for METTS at intermediate T

### Accuracy & guarantees

- Class: controlled deterministic (purification) / controlled stochastic (METTS)
- Primary approximation & its control: SVD truncation at `χ` + Trotter `O(Δτ^p)` for purification; additionally `1/√N_s` statistical error for METTS
- Error scaling: purification truncation error measurable from discarded weight per step; METTS error bar from sample variance

### Tasks it computes

- Free energy `F = −T log Z` via `Z = d^N · ⟨ρ(β)|ρ(β)⟩` (the `d^N` accounts for the initial `|I⟩` normalization)
- Thermal averages: `⟨H⟩_β`, `C_v(T) = β²(⟨H²⟩−⟨H⟩²)`, susceptibility `χ(T)`
- Finite-T correlation functions `⟨O_i O_j⟩_β`
- Finite-T spectral functions `A(ω, T)` by combining imaginary-time to `β` with a real-time TDVP/TEBD step

### Recommended for (models / regimes)

- **1D quantum magnets and correlated chains at finite T:** Heisenberg chains, Hubbard chains at elevated T (β`J ≲ 20`)
- **Frustrated 1D/quasi-1D models (B8):** sign-free alternative to QMC in the frustrated regime
- **Intermediate-T regime (METTS preference):** when `d` is small and typical-state entanglement is low; cheaper than purification per accuracy unit
- **Low-T approach curves:** purification is the preferred choice when `T/J≲0.05` and `N_s` would need to be very large for METTS
- Per `method-property-map.md` (mps-finite-t profile): primary finite-T tool for 1D sign-ful (frustrated/fermionic) models where QMC fails

### Key reference

[@paeckel_2019_timeevolution] — comprehensive review of all MPS time-evolution methods including purification and METTS; provides complexity derivations, convergence benchmarks, and software guidance.
Rendered: `./1901.05824_time-evolution-methods-for-matrix-product-states.md` _(downloaded: `1901.05824_time-evolution-methods-for-matrix-product-states.md`)_.

### Benchmarks

- Purification of Heisenberg chain (`N=100`, `χ=64`): `C_v(T)` converged to < 1% at `T/J ≥ 0.1` (Paeckel et al., arXiv:1901.05824, §5).
- METTS vs purification crossover: METTS cheaper at `T/J ≥ 0.5` for spin-½ chains (same reference, §6).
- Finite-T spectral function `S(q,ω,T)` for XXZ chain at `T/J=0.5`: `χ=128`, `N_s=200` METTS samples sufficient for `< 5%` error [@paeckel_2019_timeevolution].

## How it is used / Operational

**Owning skill:** `/method-mps` (primary); tool skills `/using-tenpy` (has native purification), `/using-itensors`, `/using-mpskit`.

**Default workflow (purification):**
1. Set up the doubled Hilbert space (physical + ancilla) in tenpy or ITensor.
2. Prepare the infinite-T state `|I⟩` (product of maximally entangled local pairs).
3. Apply imaginary-time TEBD/TDVP with Trotter step `Δτ` to reach `β/2`.
4. Compute `⟨O⟩_β = ⟨ρ(β)|O_phys|ρ(β)⟩ / ⟨ρ(β)|ρ(β)⟩`.
5. Converge in `χ` and `Δτ`; verify partition function `Z(β) = ⟨ρ(β)|ρ(β)⟩` against known limits.

**Default workflow (METTS):**
1. Start from a random product state in the chosen basis (site-product of eigenstates).
2. Imaginary-time evolve `β/2` steps → measure observables.
3. Collapse to a new product state by local projective measurement.
4. Repeat `N_s` times; average observables; report error bars from sample variance.
5. Check ergodicity: alternate collapse bases (e.g., `Sz` and `Sx` eigenstates).

**Verification pointers:**
- High-T limit (`β→0`): observables match infinite-T exact values (e.g., `⟨Sz_i⟩=0`, `⟨H⟩=0` for Heisenberg).
- Low-T limit: purification energy approaches DMRG GS energy as `β→∞`.
- METTS: check that different collapse bases give consistent results (ergodicity test).

**Cross-links:**
- Survey: `method-survey.md` §5.3 (purification/ancilla) and §5.4 (METTS)
- Model↔method gate: `method-property-map.md` (mps-finite-t profile)
- Complementary methods: LTRG/XTRG (2D finite-T, sign-free), QMC (sign-free models at scale), TEBD/TDVP (real-time follow-up for finite-T spectra)
