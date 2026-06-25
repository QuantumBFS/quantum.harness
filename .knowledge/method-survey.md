# Many-Body Computational Methods — Survey

A catalog of quantum many-body (QMB) computational methods, each annotated with:

1. **Gating properties** — which axes from `model-property-checklist.md` (A1–D16)
   decide whether the method is *applicable* and what makes it *efficient*.
2. **Complexity & its property dependence** — explicit cost scaling, and how it
   changes with the property metrics (the answer to "ED cost depends heavily on
   the symmetry used").
3. **Tasks & cost-by-task** — what the method computes, and how cost varies with
   the quantity requested.

Companion files: `model-property-checklist.md` (the 16 property axes) and
`method-property-map.md` (the compact property↔method gate).

> **Provenance.** Complexity exponents were web-verified (2026-06) against the
> primary literature by six parallel research workers; citations are inline and in
> the References section. Notable corrections folded in: HOTRG is `O(χ^{4d−1})`
> (not `O(χ^{2d+1})`, which is ATRG); mean-field fluctuation corrections scale
> `1/Z` (the `√Z` is the DMFT hopping rescaling); ED frontier is 48–50 sites;
> DMRG-X is `O(Lχ⁶)` for the full-diagonalization variant.

### Cost-symbol legend
`N` sites/orbitals · `d` local Hilbert dim · `D_H = d^N` full Hilbert dim ·
`D_blk` largest symmetry block · `χ` MPS bond dim · `D` PEPS virtual bond ·
`χ_env` environment (CTMRG/boundary-MPS) bond · `M` #Chebyshev moments /
expansion order · `N_s` #MC samples · `N_w` #walkers · `β` inverse temperature ·
`Δτ` (imag-)time step, `N_τ=β/Δτ` · `τ_auto` autocorrelation time ·
`z` dynamical critical exponent · `⟨s⟩` average sign · `n` qubits ·
`N_p` #variational parameters · `N_c` cluster size · `N_kept` retained states.

---

# 1. Exact methods

### 1.1 Exact diagonalization — full (dense)
*Numerically exact spectrum of the finite Hamiltonian matrix.*
- **Gating properties:** A3 sets the wall (`D_H = d^N`); C9/C10 are the only lever
  that extends reach; A1/A2 only via total site count; works for ANY B5/B6/B7/B8/
  C11/C12/D16 (no sign problem, no entanglement restriction) — its role is the
  universal oracle.
- **Complexity & property dependence:** dense eigensolve **O(D_blk³)** time,
  **O(D_blk²)** memory. The decisive dependence is on symmetry (C9/C10):
  `D_blk = D_H / (reduction factor)`. U(1) (Sᶻ or N) restricts to one sector
  (`2^N → C(N,N/2) ≈ 2^N/√N`); translation (C10) divides by `≈N` (momentum `k`);
  point group by `|G|`; spin inversion/parity by ~2; SU(2) by working in total-`S`
  multiplets. Net: a spin-½ chain of `N≈20` is trivial dense; with full symmetry
  reduction iterative ED reaches `N≈40` routinely and **48–50 at the
  supercomputer frontier** (Wietek–Läuchli 2018, arXiv:1804.05028; xdiag, HΦ).
  Larger `d` (A3: spin-1, Hubbard `d=4`, bosons) shrinks the reachable `N`
  accordingly.
- **Tasks & cost-by-task:** full spectrum / all eigenvectors → full dense
  `O(D_blk³)` (thermodynamics, level statistics, ETH). This is the *only* task
  that needs full diagonalization; everything else is cheaper (below).

### 1.2 Exact diagonalization — iterative (Lanczos / Arnoldi / Krylov / shift-invert)
*Few extremal or interior eigenpairs by Krylov iteration, matrix-free.*
- **Gating properties:** same as 1.1 but memory is **O(D_blk)** (a few vectors),
  so it reaches much larger `N`. C9/C10 again the key lever. B6 matters for
  convergence: gapped → few iterations; near-degenerate/critical → many.
- **Complexity & property dependence:** **O(n_iter · N_nnz)** time, where
  `N_nnz ≈ (#Hamiltonian terms) · D_blk ≈ O(N · D_blk)` for short-range (A4) H;
  long-range (A4) raises `N_nnz`. `n_iter` ~ tens (gapped B6) to hundreds
  (critical/near-degenerate B6, or interior states via shift-invert). Memory
  **O(D_blk)**.
- **Tasks & cost-by-task:** ground state & low gap → cheapest, `O(n_iter·N_nnz)`;
  a few excited states (Sᶻ/`k` sectors) → same per sector; dynamical correlation
  `S(q,ω)` via continued-fraction / Lanczos → a few extra Krylov runs per `q`;
  real-time evolution on a finite cluster via Krylov exponentiation →
  `O(n_Krylov · N_nnz)` per time step.

### 1.3 Finite-temperature Lanczos (FTLM) & thermal pure quantum states (TPQ)
*Thermal averages without full diagonalization, via random-vector sampling.*
- **Gating properties:** A3 (`D_H` wall, but only `O(D_blk)` memory); D13 =
  finite-T; C9/C10 reduce per-sector cost. No C12 restriction.
- **Complexity & property dependence:** **O(R · n_iter · N_nnz)** where `R` is the
  number of random starting vectors (TPQ: `R` small at high `T`, must grow as `T`
  drops because of larger thermal fluctuations); the `1/√(R·D_H)` statistical
  error shrinks with system size (typicality).
- **Tasks & cost-by-task:** free energy, internal energy, specific heat,
  susceptibility (canonical TPQ); dynamical `S(q,ω)` at finite `T` via FTLM at
  extra Krylov cost.

### 1.4 Kernel polynomial method (KPM / Chebyshev)
*Expand spectral densities in Chebyshev polynomials of a sparse `H`.*
- **Gating properties:** A4 (sparsity → cheap `H|v⟩`); A3 (`D_H` memory wall);
  no C12 restriction; resolution set by `M` not by gap.
- **Complexity & property dependence:** **O(M · R · N_nnz)** time, **O(D_H)**
  memory. Spectral resolution `≈ bandwidth/M`; `R` random vectors for the
  stochastic trace (`1/√(R·D_H)` error). Linear in `M`, no `D_H³`.
- **Tasks & cost-by-task:** density of states, optical/dynamical conductivity,
  spectral functions `A(ω)`, finite-T traces — all at `O(M·R·N_nnz)`; higher
  frequency resolution = larger `M`.

### 1.5 Full configuration interaction (FCI)
*ED in the many-electron determinant basis (quantum chemistry).*
- **Gating properties:** A3 (statistics = fermions; `d=4` per spatial orbital);
  the wall is `binomial(2·#orbitals, #electrons)`; C9 (Sᶻ, S², point group) the
  reduction lever.
- **Complexity & property dependence:** exponential in #orbitals; ~18–20 orbitals
  in routine codes, with the distributed-memory frontier at **~10¹² determinants**
  (trillion-determinant FCI, *JCTC* 2024). Symmetry and selected-CI / DMRG-CI
  variants extend this.
- **Tasks & cost-by-task:** exact energies & wavefunctions in a chosen
  single-particle basis; benchmark for approximate quantum-chemistry methods.

---

# 2. Classical Monte Carlo

### 2.1 Metropolis (single-spin-flip)
*Importance sampling of classical Boltzmann weights.*
- **Gating properties:** applies to classical models / sign-free mappings; B6
  (criticality) controls cost via critical slowing down; B8 frustration / glassiness
  raises `τ_auto`; A1 sets per-sweep cost.
- **Complexity & property dependence:** **O(N)** per sweep; total
  **O(N · τ_auto · N_s)**. Near a continuous transition (B6) `τ_auto ~ ξ^z ~ L^z`
  with local (Glauber/Metropolis) dynamics `z = 2.1665(12)` for the 2D Ising model
  (Nightingale–Blöte 1996) → critical slowing down dominates.
- **Tasks & cost-by-task:** energy, magnetization, susceptibility, Binder
  cumulants, structure factors; correlation-time cost worst near `T_c`.

### 2.2 Cluster algorithms (Swendsen–Wang, Wolff) & Wang–Landau / parallel tempering
*Non-local updates that defeat critical slowing down (SW/Wolff) or rough
landscapes (tempering, Wang–Landau density-of-states sampling).*
- **Gating properties:** SW/Wolff need a valid cluster (Fortuin–Kasteleyn)
  construction — ferromagnetic / unfrustrated couplings; B8 frustration breaks it.
  Parallel tempering targets B8/D15 glassy landscapes.
- **Complexity & property dependence:** SW/Wolff crush `z` for 2D Ising — Swendsen–
  Wang `z ≈ 0.22`, Wolff effectively `~ln L` (equilibrium-autocorrelation
  convention; nonequilibrium-relaxation fits report a larger effective `z≈1.2`) →
  near-`O(N)` effective cost at criticality (B6), the main win over Metropolis.
  Parallel tempering multiplies cost by #replicas but flattens barriers.
- **Tasks & cost-by-task:** same observables; cluster methods make critical-region
  measurements and large-`L` finite-size scaling affordable.

### 2.3 Monte Carlo renormalization group (MCRG)
*Block-spin RG on MC configurations → renormalized couplings → critical exponents.*
- **Gating properties:** B6 (designed for the critical fixed point); any A1;
  classical spin models; D15 variant for quenched disorder.
- **Complexity & property dependence:** MC sampling cost × #RG iterations; the
  exponents come from eigenvalues of the linearized RG map (Swendsen 1979). Larger
  `L` near `T_c` improves exponent accuracy; variational MCRG (Wu–Car 2017)
  removes critical slowing down.
- **Tasks & cost-by-task:** critical exponents `y_t, y_h` (→ `ν, β, γ`), the
  critical manifold/tangent space; NOT thermodynamic-limit observables or GS
  energies.

---

# 3. Ground-state & RG tensor networks

### 3.1 DMRG / MPS (finite) and iDMRG / VUMPS (infinite)
*Variational optimization over matrix product states.*
- **Gating properties:** A1 is decisive — near-exact in 1D & quasi-1D, hits a wall
  in 2D. B5 is the cost driver via **χ ≳ e^S**: area-law (B5) → small `χ`;
  1D-critical (B5 area+log, B6 gapless) → `χ` grows polynomially with `L`;
  2D cylinder width `W` → cut entropy `∝W` → **χ ~ e^{cW}** (the 2D wall). A4
  long-range inflates the MPO bond `w`. C9 (U(1)/SU(2)) gives block-sparse/multiplet
  tensors. B7 topological order needs the minimally-entangled-state protocol. D16
  Hermitian assumed (non-Hermitian variants exist).
- **Complexity & property dependence:** **O(N · w · d · χ³)** time per sweep,
  **O(d·χ²)** memory. The property→cost chain: B5/B6/B8 set the required `χ`;
  A1 (width) sets `χ ~ e^{cW}`; A4 sets `w`; C9 reduces the effective `χ` at fixed
  accuracy (block structure), often a large constant-factor (≳10×) speedup.
- **Tasks & cost-by-task:** ground-state energy/observables → base cost; gap &
  low excitations → targeted/“excited-state” DMRG, similar cost per state;
  correlation length → transfer-matrix spectrum (cheap post-process); entanglement
  spectrum → free from the MPS (SPT/topo diagnostics); 2D physics → multiply by
  `e^{cW}` per cylinder width. Finite-T and real-time are separate algorithms
  (§5).

### 3.2 PEPS / iPEPS (2D)
*Projected entangled pair states; the 2D area law built in at fixed bond `D`.*
- **Gating properties:** A1 = 2D (its home); B5 2D area-law states at fixed `D`;
  B6 criticality and B8 frustration inflate `D`; A3 fermions need parity tensors
  (fPEPS); B7 topological order representable; D13 GS (dynamics/finite-T harder).
- **Complexity & property dependence:** the bottleneck is *contraction*, which is
  exact-#P-hard, so done approximately with environment bond `χ_env` (typically
  `χ_env ∝ D²`). Observable/energy evaluation via CTMRG/boundary-MPS
  **≈ O(χ_env³ D⁶)**; variational optimization (full update / AD gradient) a higher
  power, commonly quoted **O(D¹⁰)–O(D¹²)**; **simple update** is much cheaper
  (**~O(D⁵)** per step) at the price of a local environment. Cost is dominated by
  `D` (set by B5/B6/B8) and `χ_env` (accuracy of contraction).
- **Tasks & cost-by-task:** GS energy & order parameters (CTMRG environment);
  correlation length (transfer matrix of the boundary); thermodynamic limit
  directly (iPEPS); finite-T via thermal-state PEPS or `D`-doubling (more
  expensive). Excitations via PEPS tangent space (specialized).

### 3.3 Tree tensor networks (TTN)
*Loop-free hierarchical network; exact contraction.*
- **Gating properties:** good when entanglement is hierarchical / bounded across a
  tree bipartition; handles some 2D and long-range (A4) better than a 1D MPS path;
  B5 area-law-ish.
- **Complexity & property dependence:** **O(χ⁴)**-ish per tensor (connectivity
  dependent); exact contraction (no environment approximation). `χ` set by the
  worst tree-cut entanglement.
- **Tasks & cost-by-task:** GS energy/observables; natural for systems with
  branching geometry or for quantum-chemistry orbital trees.

### 3.4 MERA (multiscale entanglement renormalization)
*Scale-invariant network with disentanglers; captures criticality at finite `χ`.*
- **Gating properties:** B6 = criticality / scale invariance (its reason to exist —
  reproduces the `log` entanglement of 1D CFTs at finite `χ`); A1 1D & some 2D.
- **Complexity & property dependence:** expensive — **O(χ⁹)** (binary 1D),
  **O(χ⁸)** (ternary 1D), **O(χ⁷)** (modified-binary; Evenbly–Vidal 2011); 2D MERA
  much higher (up to ~O(χ¹⁶)). Cost dominated by `χ`.
- **Tasks & cost-by-task:** GS of critical systems, extraction of scaling
  dimensions/central charge (CFT data) from the RG superoperator spectrum.

### 3.5 Tensor RG for classical / partition functions — TRG, HOTRG, TNR, CTMRG
*Real-space coarse-graining of a 2D/3D tensor network (e.g. a classical partition
function or a path integral).*
- **Gating properties:** A1 = 2D (TRG/CTMRG) or 3D (HOTRG); B6 criticality
  (TNR/loop-TNR remove the CFT-contaminating short-range correlations); sign-free
  (real Boltzmann weights), so C12 is sidestepped for classical models.
- **Complexity & property dependence:** per coarse-graining step **TRG O(χ⁶)** in
  2D; **HOTRG O(χ^{4d−1})** time / `O(χ^{2d})` memory = `O(χ⁷)`/`O(χ⁴)` in 2D and
  `O(χ¹¹)`/`O(χ⁶)` in 3D (Xie et al. 2012 — note the cheaper `O(χ^{2d+1})` scaling
  belongs to **ATRG**, a different algorithm); **TNR** higher still but yields clean
  scale invariance; **CTMRG** environment `O(χ³)`-ish per move. `χ` is the retained
  bond after truncation.
- **Tasks & cost-by-task:** free energy / partition function, critical temperature,
  critical exponents and central charge (from the transfer-matrix / RG spectrum);
  also contracts 2D quantum thermal & PEPS networks.

---

# 4. Monte Carlo (quantum)

### 4.1 Variational Monte Carlo (VMC) & neural quantum states (NQS)
*Sample a parameterized wavefunction; optimize its energy. No sign problem, but
ansatz-biased (variational upper bound).*
- **Gating properties:** thrives exactly where QMC fails — B8 frustration, C12
  sign-ful, A1 2D — because there is no sign problem, only ansatz bias. A1 any
  dimension; B5 no hard restriction (NQS can carry volume-law in principle); D16
  Hermitian (variational principle). Quality is set by the ansatz, not by a model
  property.
- **Complexity & property dependence:** **O(N_s · c_eval)** per optimization step,
  `c_eval` = cost of amplitude + local energy (`O(N)`–`O(N²)` for Jastrow/RBM,
  network forward-pass for deep NQS). Stochastic reconfiguration / natural gradient
  adds **O(N_p²)**–`O(N_p³)` (or `O(N_s N_p)` with iterative/minSR). Independent of
  C12 — the sign appears only as a sign-structure the ansatz must learn.
- **Tasks & cost-by-task:** GS energy & variational observables; excited states via
  symmetry sectors or penalty methods; dynamics via time-dependent VMC (extra cost,
  growing error). Gives an *upper* bound only — pair with PolyOpt (§7) for a
  rigorous bracket.

### 4.2 Projector / Green's-function / diffusion MC (GFMC, DMC) + fixed-node
*Imaginary-time projection of a trial state toward the ground state.*
- **Gating properties:** C12 sign problem for fermions/frustration → controlled by
  **fixed-node** (nodal-surface bias) or stochastic reconfiguration; A1 any
  dimension; D13 GS.
- **Complexity & property dependence:** **O(N_w · N_proj · c_step)**; statistical
  error `1/√(N_w N_proj)`. Sign-free for bosons/unfrustrated; fixed-node makes
  fermionic cost polynomial at the price of a variational bias set by the trial
  node.
- **Tasks & cost-by-task:** GS energy (fixed-node = best variational energy given
  the node), mixed/forward-walking estimators for other observables.

### 4.3 Stochastic series expansion (SSE) / worldline QMC
*Finite-T sampling of the high-`T` series / path integral for spins & bosons.*
- **Gating properties:** C12 is the gate — **sign-free** for unfrustrated bipartite
  spins (Marshall) and bosons (A3); B8 frustration / A3 fermions turn the sign on.
  D13 finite-T (and GS via large `β`); A1 any dimension (the big advantage over
  tensor networks); B5 no area-law restriction.
- **Complexity & property dependence:** **O(N·β)** per sweep (expansion order
  `∝ N·β`); statistical error `1/√(N_s·⟨s⟩)`. Directed-loop/operator-loop updates
  remove critical slowing down (B6). When sign-ful: cost `∝ 1/⟨s⟩² ~ e^{2βNΔf}`.
- **Tasks & cost-by-task:** finite-T thermodynamics (energy, `C_v`, `χ`), equal-
  and imaginary-time correlations, structure factors, spin stiffness/superfluid
  density, Binder cumulants; spectra `S(q,ω)` need analytic continuation
  (ill-posed). Real-time blocked (dynamical sign).

### 4.4 Determinant QMC (DQMC / BSS, finite-T auxiliary field)
*Hubbard–Stratonovich the interaction; sample auxiliary fields; trace out fermions
as a determinant.*
- **Gating properties:** C12 the gate — **sign-free** at D14 half-filling on
  bipartite lattices (particle-hole, `det↑det↓=|det|²≥0`) and attractive Hubbard at
  any filling; D14 doping / B8 frustration / A4 turn the sign on. A1 any dimension;
  D13 finite-T.
- **Complexity & property dependence:** **O(β·N³)** per sweep (`N×N` matrix
  products over `N_τ=β/Δτ` slices, with numerical stabilization), **O(N²·N_τ)**
  memory; Trotter error `O(Δτ²)`. Sign: `⟨s⟩ ~ e^{−βNΔf}` → cost to fixed error
  `∝ e^{2βNΔf}` in the sign-ful regime (the exponential wall set by D14/B8).
- **Tasks & cost-by-task:** finite-T energy, double occupancy, magnetic/charge
  structure factors, single-particle Green's function & (via analytic continuation)
  spectral function/self-energy, superconducting susceptibilities. Lower `T` (large
  `β`) raises both cost and the sign penalty.

### 4.5 Auxiliary-field QMC ground state (AFQMC) & constrained-path / phaseless (CPMC)
*Ground state by imaginary-time projection in auxiliary-field space; the sign/phase
problem controlled by a trial-state constraint.*
- **Gating properties:** C12 — phaseless/constrained-path removes the sign at the
  cost of a trial-state bias; A1 any dimension; D13 GS; A3 fermions.
- **Complexity & property dependence:** **O(N³)** per walker per step × `N_w` ×
  `N_steps`; memory `O(N²)` per walker. Free-projection (unbiased) cost blows up
  `∝ e^{2τ...}` with the sign; the constraint trades that for polynomial cost +
  controllable bias.
- **Tasks & cost-by-task:** GS energy (benchmark-grade for many Hubbard regimes),
  back-propagated observables, imaginary-time correlations → spectra via analytic
  continuation.

### 4.6 Diagrammatic Monte Carlo (DiagMC)
*Stochastic summation of Feynman-diagram series directly in the thermodynamic limit.*
- **Gating properties:** A1 thermodynamic limit (no finite-size error — a key
  differentiator); C12 diagram-sign + series-convergence as the limiters; weak–
  intermediate coupling regimes.
- **Complexity & property dependence:** cost grows with maximum diagram order;
  convergence/resummation of the series is the bottleneck, not lattice size.
- **Tasks & cost-by-task:** self-energy, Green's function, vertex functions,
  thermodynamics in the thermodynamic limit; polaron and impurity problems.

### 4.7 Path-integral Monte Carlo (PIMC)
*Continuum/lattice imaginary-time path integral for bosons.*
- **Gating properties:** A3 bosons (sign-free) — fermions reintroduce the sign;
  D13 finite-T; continuous (D.O.F.) or lattice.
- **Complexity & property dependence:** **O(N·N_τ)** per sweep; worm algorithm for
  efficient winding/superfluid sampling.
- **Tasks & cost-by-task:** finite-T thermodynamics, superfluid density, condensate
  fraction, structure factors for bosonic systems (e.g. ⁴He, cold atoms).

---

# 5. Tensor-network dynamics & finite temperature

### 5.1 TEBD (Trotter MPS time evolution)
- **Gating properties:** D13 real-time / imaginary-time; A4 nearest-neighbor (or
  short-range with swaps); B5 the killer — real-time entanglement grows **linearly**
  `S(t)∝t` for thermalizing systems → **χ ~ e^{S(t)}** caps reachable time;
  C11 integrable & D15 MBL slow the growth → longer reachable times.
- **Complexity & property dependence:** **O(N·d·χ(t)³)** per Trotter step, Trotter
  error `O(Δτ^p)`; the wall is `χ(t)` growth: reachable `t* ~ log(χ_max)/(rate)`,
  with rate set by C11/D15/B6.
- **Tasks & cost-by-task:** quench dynamics, real-time correlations →
  `S(q,ω)`/spectral functions by time-evolve+Fourier (cost set by the max time
  reachable before `χ` saturates), transport; imaginary-time TEBD → ground states
  & finite-T (purification).

### 5.2 TDVP (time-dependent variational principle) & W^I/W^II MPO evolution
- **Gating properties:** handles A4 **long-range** Hamiltonians (via MPO), unlike
  TEBD; D13 dynamics; energy-conserving; 1-site TDVP fixes `χ` (projection error,
  no growth) vs 2-site TDVP grows `χ`.
- **Complexity & property dependence:** **O(N·w·d·χ³)** per step (`w` = MPO bond,
  set by A4 interaction range); same `χ(t)` entanglement-barrier limit as TEBD.
- **Tasks & cost-by-task:** long-range/2D-cylinder dynamics, spectral functions,
  long-time evolution within the manifold (1-site) when controlled bias is
  acceptable.

### 5.3 Finite-T via purification / ancilla (thermofield)
- **Gating properties:** D13 finite-T; B5 the entanglement of the purified state
  grows as `T` drops → `χ` rises at low `T`; A1 1D/quasi-1D.
- **Complexity & property dependence:** local dim `d → d²` (ancilla) →
  **O(N·d²·χ³)** per imaginary-time step to reach `β`; low-`T` cost set by the
  thermal-state entanglement.
- **Tasks & cost-by-task:** free energy, `C_v`, `χ`, finite-T correlations; combine
  with real-time evolution for finite-T spectra.

### 5.4 METTS (minimally entangled typical thermal states)
- **Gating properties:** D13 finite-T; lower entanglement than purification (samples
  typical states) → cheaper at intermediate `T`, at the price of MC sampling noise.
- **Complexity & property dependence:** per sample = imaginary-time evolve a product
  state to `β/2`, `O(N·d·χ³)`; `N_s` samples for `1/√N_s` error; `χ` smaller than
  purification's.
- **Tasks & cost-by-task:** finite-T thermodynamics & correlations, especially when
  purification's doubled bond is too costly.

### 5.5 LTRG / XTRG (thermal tensor RG)
- **Gating properties:** D13 finite-T thermodynamics; A1 1D, quasi-1D **and 2D** —
  **sign-free even in 2D** (maps `d`-dim quantum at finite `T` to a `(d+1)`-dim
  classical tensor network), the advantage over QMC in frustrated cases (B8);
  A3 any local dim.
- **Complexity & property dependence:** **LTRG** adds imaginary-time slices
  linearly, `K = β/τ` layers, cost per layer polynomial in `d` and retained `Dc`;
  Trotter error `O(τ²)`. **XTRG** evolves exponentially (`ρ → ρ·ρ` doubles `β` each
  step) → only **`O(log β)`** steps to reach low `T`, far more accurate at low `T`;
  cost per step a higher power of `Dc`. `Dc` set by the thermal-state entanglement.
- **Tasks & cost-by-task:** free energy, internal energy, `C_v`, susceptibility,
  thermal phase transitions; low-`T` reach is XTRG's strength.

### 5.6 DMRG-X
- **Gating properties:** D15 MBL — targets highly-excited eigenstates that obey an
  **area law** (MBL), which thermal excited states do not; D13 (excited eigenstates).
- **Complexity & property dependence:** DMRG-like, but for interior eigenstates
  selected by *maximum overlap*: **`O(L·χ⁶)`** for the full local-diagonalization
  variant, or **`~O(L·χ³)`** for the k-eigenstate-near-target variant; works only
  because MBL keeps `χ` bounded.
- **Tasks & cost-by-task:** individual excited eigenstates, l-bit structure,
  eigenstate observables across the MBL phase.

---

# 6. Quantum embedding & perturbative / RG methods

### 6.1 DMFT (single-site) and cluster extensions (CDMFT, DCA, EDMFT)
*Map the lattice to a self-consistent quantum impurity; exact local self-energy.*
- **Gating properties:** A1 — **exact as coordination `Z→∞` / infinite dimension**
  (Metzner–Vollhardt); finite-D it neglects spatial correlations, restored short-
  range by clusters (`N_c`); A3 multi-orbital grows the impurity local dim; C12 the
  impurity-solver sign (CT-HYB: severe for off-diagonal hybridization / multi-orbital
  / clusters); D13 finite-T natural, real-frequency needs analytic continuation;
  B6/D14 Mott transition & doping are its core physics.
- **Complexity & property dependence:** self-consistency loop × impurity-solver
  cost. Solvers: **CT-QMC** (CT-HYB/CT-INT) ~ polynomial in `β` with a sign that
  worsens with #orbitals/cluster size; **ED solver** exponential in #bath sites;
  **NRG solver** (§6.3). Cluster DMFT cost grows **exponentially with `N_c`** (sign
  + impurity size) — the price of spatial resolution.
- **Tasks & cost-by-task:** single-particle spectral function / self-energy / DOS
  (its home turf), Mott transition & phase diagram, finite-T thermodynamics;
  two-particle response (susceptibilities, optical conductivity) needs vertex
  functions → substantially more expensive; momentum resolution needs clusters.

### 6.2 DMET (density matrix embedding theory)
*Embed a fragment + a small bath built from the Schmidt decomposition; solve with a
high-level solver; match the 1-RDM self-consistently.*
- **Gating properties:** A1 any dimension; B7 strong correlation OK (unlike
  perturbation theory); cost set by fragment size and the embedded solver (DMRG/FCI);
  C12 only via the embedded solver.
- **Complexity & property dependence:** dominated by the impurity solver on a system
  of size `2·N_frag` (fragment + bath); self-consistency on the correlation
  potential is cheap. Larger fragments → better accuracy, exponentially harder
  solver.
- **Tasks & cost-by-task:** GS energy & local observables, phase diagrams; spectral
  functions are harder (frequency-dependent DMET extensions).

### 6.3 NRG (Wilson numerical renormalization group)
*Logarithmic energy discretization of the bath; iterative diagonalization.*
- **Gating properties:** impurity / quantum-dot problems (Anderson, Kondo); D13 all
  `T` and real-frequency (its strength); A3 #channels/bands is the wall; C9 exploited
  per iteration.
- **Complexity & property dependence:** **O(N_kept³)**-ish per iteration (diagonalize
  a `≈ d·N_kept` matrix, truncate to `N_kept`); `N_kept` must grow **exponentially
  with #bands/channels**, so NRG is limited to ~1–3 channels. Excellent low-energy
  resolution from the log grid.
- **Tasks & cost-by-task:** Kondo scale `T_K`, impurity spectral function, thermo-
  dynamics, flow diagrams; as a DMFT solver for real-frequency self-energies.

### 6.4 Functional RG (fRG)
*Flow equations for the one-particle-irreducible vertices from a cutoff scale.*
- **Gating properties:** weak–intermediate coupling; A1 any dimension; B6 detects
  leading instabilities (magnetic / superconducting / charge); truncation order is
  the controlled approximation.
- **Complexity & property dependence:** cost set by the vertex parameterization —
  `N_patch` momentum patches → vertex storage/flow `~ O(N_patch³)` (and more for
  frequency dependence). Strong coupling not controlled.
- **Tasks & cost-by-task:** leading-instability phase diagrams, susceptibilities,
  pseudo-critical scales; not GS energies of strongly-correlated phases.

### 6.5 Coupled cluster (CCSD, CCSD(T), periodic variants)
*Exponential cluster ansatz `e^T|HF⟩`; size-extensive.*
- **Gating properties:** B7 — excellent for weak/moderate **dynamic** correlation,
  **fails for strong static correlation / B8 frustration / open-shell degeneracy**
  (single-reference breakdown); A3 fermions; A1 any (periodic CC for solids).
- **Complexity & property dependence:** **CCSD O(N⁶)**, **CCSD(T) O(N⁷)** in the
  number of orbitals `N`; the gold standard scaling of quantum chemistry. Cost is
  set by orbital count, not by a phase property — but accuracy collapses in the
  strong-correlation regime.
- **Tasks & cost-by-task:** GS energies/observables (high accuracy when
  single-reference); EOM-CC for excitations/spectra at higher cost.

### 6.6 Many-body perturbation theory — GW, RPA, GF2, SEET
*Diagrammatic self-energy / correlation-energy approximations.*
- **Gating properties:** weak coupling; A3 fermions; A1 any; B6 (GW for
  quasiparticle gaps); strong correlation out of reach (SEET embeds a correlated
  subspace to fix this).
- **Complexity & property dependence:** **GW O(N⁴)** (down to `O(N³)` with
  factorization), **RPA O(N⁴)→O(N³)**, **GF2 O(N⁵)**; scaling in orbital count.
- **Tasks & cost-by-task:** quasiparticle band structures / photoemission spectra
  (GW), correlation energies (RPA), screened interactions; SEET adds local strong
  correlation for spectra of correlated solids.

---

# 7. Mean-field / semiclassical, circuit, and certified methods

### 7.1 Hartree–Fock / UHF (and DFT / DFT+U as a lattice baseline)
- **Gating properties:** A1 — leading fluctuation corrections scale `~1/Z` (the
  `√Z` is the DMFT *hopping* rescaling `t=t*/√Z`, **not** the MF error), so MF is
  best at high dimension/large coordination and **exact as Z→∞** (Metzner–Vollhardt
  1989); it **fails in 1D** (Mermin–Wagner → spurious order) and under B8
  frustration; B7 product-like (no entanglement); fast baseline & trial-state seed.
- **Complexity & property dependence:** **O(N³)–O(N⁴)** per SCF iteration (Fock
  build), negligible vs correlated methods. Independent of B5 (it carries none).
- **Tasks & cost-by-task:** mean-field phase diagrams, order parameters, band
  structures; seeds for DMRG/VMC/AFQMC.

### 7.2 Linear spin-wave theory (1/S) & large-N / large-S
- **Gating properties:** B7 requires magnetic order (expands around an ordered
  classical state); large `S` (A3) is the control parameter; B8 frustration / small
  `S` → corrections blow up (breakdown signals disorder/spin liquid).
- **Complexity & property dependence:** diagonalize a Bogoliubov–de Gennes problem
  of size `m` (= #magnetic sublattices/bands): **O(m³)** per `k`-point × #k-points.
  Cheap.
- **Tasks & cost-by-task:** magnon dispersions, dynamical structure factor `S(q,ω)`
  at the harmonic level, sublattice-magnetization `1/S` corrections, thermo-
  dynamics; magnon–magnon interactions need higher orders.

### 7.3 Slave-particle / parton mean field (slave-boson, Schwinger boson, Abrikosov
fermion) & Gutzwiller
- **Gating properties:** B7 fractionalized / spin-liquid phases & Mott physics —
  builds in fractionalization that HF cannot; mean-field-level (fluctuations beyond
  need gauge theory).
- **Complexity & property dependence:** self-consistent mean field on the enlarged
  (parton) space, HF-like cost; Gutzwiller-projected wavefunctions evaluated by VMC
  (§4.1) cost.
- **Tasks & cost-by-task:** candidate spin-liquid / fractionalized ansätze and their
  energies, mean-field phase diagrams, spinon/holon dispersions.

### 7.4 Cluster mean field / VCA (variational cluster approximation)
- **Gating properties:** A1 2D; B7 ordered & Mott phases; treats short-range
  correlation exactly inside a cluster, mean field between clusters.
- **Complexity & property dependence:** dominated by the exact cluster solver (ED,
  §1) → exponential in cluster size; the inter-cluster part is cheap.
- **Tasks & cost-by-task:** spectral functions & phase boundaries (VCA via the
  self-energy functional), symmetry-breaking order parameters.

### 7.5 Quantum-circuit simulation — state-vector, tensor-network, stabilizer
*Classical simulation of quantum circuits (and the VQE/QPE algorithms run on them).*
- **Gating properties:** the cost is governed by **B5 entanglement** and circuit
  structure, not a lattice phase. State-vector: exact, `O(2^n)` memory. TN-based:
  cost `= exp(treewidth)` of the contraction graph (Markov–Shi) → polynomial for
  low-depth / area-law / 1D-like circuits (MPS, Vidal). Stabilizer: Clifford-only
  (Gottesman–Knill) is polynomial; non-Clifford "magic" (T-gates) costs
  exponentially in their count (stabilizer rank).
- **Complexity & property dependence:** state-vector **O(gates·2ⁿ)** time /
  **O(2ⁿ)** memory; TN **O(exp(treewidth))** (→ poly when B5 area-law/low-depth,
  Markov–Shi); stabilizer **O(n)** per Clifford gate and **O(n²)** per measurement
  (Aaronson–Gottesman), but exponential in the #non-Clifford T-gates via stabilizer
  rank (`~2^{αt}`, `α≈0.396` — Qassim–Pashayan–Gosset 2021).
- **Tasks & cost-by-task:** sampling, expectation values, VQE energy minimization,
  Hamiltonian-dynamics simulation; cost set by entanglement/depth generated, and
  whether the circuit is near-Clifford.

### 7.6 Certified bounds — SDP / moment-SOS relaxations (NPA, NCTSSOS) & bootstrap
*Rigorous LOWER bounds on ground-state energies (and bounds on observables) via
semidefinite relaxations of the moment problem — the complement to variational
upper bounds.*
- **Gating properties:** works in C12 sign-ful / B8 frustrated regimes (no
  sampling, no sign problem) — a key niche; C9 symmetry block-diagonalizes the SDP
  (large speedup); A1 1D/2D feasible, 3D blows up; any algebra (Pauli/fermion/
  boson) (A3).
- **Complexity & property dependence:** relaxation level `k` → moment-matrix size
  `~ #monomials of degree ≤k = O(N^k)`; SDP solve a high polynomial in that size
  (interior-point). Structured sparsity (NCTSSOS, term/correlative sparsity) and
  symmetry (C9) shrink the blocks — recent structured solvers certify large 1D/2D
  Heisenberg lattices. Tighter bound = higher `k` = rapidly growing SDP.
- **Tasks & cost-by-task:** rigorous GS energy lower bound (→ two-sided bracket with
  VMC), certified bounds on local observables / correlations, Bell-inequality
  bounds; the **bootstrap** variant imposes positivity + consistency for two-sided
  constraints, including phase-diagram features.

---

# 8. Master complexity table

Per the dominant cost; `*` marks the property metric that drives it.

| Method | Time (leading) | Memory | Driving property metric |
|--------|----------------|--------|--------------------------|
| ED full | `O(D_blk³)` | `O(D_blk²)` | A3 `d^N`, reduced by C9/C10* |
| ED Lanczos | `O(n_iter·N·D_blk)` | `O(D_blk)` | C9/C10* ; B6 → `n_iter` |
| FTLM/TPQ | `O(R·n_iter·N·D_blk)` | `O(D_blk)` | C9/C10* ; D13 |
| KPM | `O(M·R·N_nnz)` | `O(D_H)` | A4 sparsity* ; `M` = resolution |
| Classical MC (local) | `O(N·τ_auto·N_s)` | `O(N)` | B6 → `τ_auto~L^z`* |
| Cluster MC | `≈O(N·N_s)` near `T_c` | `O(N)` | B8 (breaks clusters)* |
| MCRG | MC × #RG steps | `O(N)` | B6* |
| DMRG/MPS | `O(N·w·d·χ³)` | `O(d·χ²)` | B5/B6/B8 → χ* ; A1 width → `e^{cW}`* ; A4 → `w` ; C9 ↓ |
| iPEPS | `O(χ_env³ D⁶)`–`O(D¹⁰⁻¹²)` | `O(χ_env² D⁴)` | B5/B8 → D* ; contraction χ_env |
| MERA | `O(χ⁷⁻⁹)` | `O(χ⁴)` | B6 criticality → χ* |
| TRG/HOTRG | `O(χ⁶)` / `O(χ^{4d−1})` | `O(χ⁴)` / `O(χ^{2d})` | B6 → χ* ; A1 dim → exponent |
| TEBD/TDVP | `O(N·w·d·χ(t)³)` | `O(d·χ²)` | D13+B5 → χ(t)~e^{S(t)}* ; A4 → w |
| purification/METTS | `O(N·d²·χ³)` | `O(d²·χ²)` | D13 ; low-T → χ* |
| LTRG/XTRG | poly(`d,Dc`)×(`β/τ` or `log β`) | `O(Dc²)` | D13 ; low-T → Dc* ; A1 (2D ok) |
| SSE/worldline | `O(N·β/⟨s⟩²·N_s)` | `O(N·β)` | C12 ⟨s⟩* ; B6 → updates |
| DQMC | `O(β·N³/⟨s⟩²)` | `O(N²·N_τ)` | C12 ⟨s⟩~e^{−βNΔf}* (D14/B8) |
| AFQMC/CPMC | `O(N³·N_w·N_steps)` | `O(N²·N_w)` | C12 (constraint bias)* |
| VMC/NQS | `O(N_s·c_eval + N_p²)` | `O(N_p)` | ansatz quality (not C12)* |
| DMC/GFMC | `O(N_w·N_proj·c_step)` | `O(N_w·N)` | C12 (fixed-node bias)* |
| DiagMC | grows with diagram order | — | C12 + series convergence* |
| DMFT (+solver) | loop × solver; cluster `~e^{N_c}` | solver | A1 Z* ; C12 (solver) ; N_c |
| DMET | solver on `2N_frag` | solver | fragment size* |
| NRG | `O(N_kept³)`/iter | `O(N_kept²)` | A3 #channels → N_kept* |
| fRG | `~O(N_patch³)` | `O(N_patch²)` | coupling strength (truncation)* |
| CCSD / CCSD(T) | `O(N⁶)` / `O(N⁷)` | `O(N⁴)` | B7 (single-ref validity)* ; N orbitals |
| GW / RPA / GF2 | `O(N⁴)` / `O(N⁴)` / `O(N⁵)` | `O(N³)` | weak coupling* ; N orbitals |
| HF / DFT | `O(N³⁻⁴)`/iter | `O(N²)` | A1 Z (accuracy)* |
| spin-wave | `O(m³)`×#k | `O(m²)` | B7 order required* ; A3 large-S |
| circuit: state-vector | `O(gates·2ⁿ)` | `O(2ⁿ)` | n* |
| circuit: TN | `O(exp(treewidth))` | varies | B5/depth → treewidth* |
| circuit: stabilizer | `O(n²⁻³)`; exp in #T | `O(n²)` | #non-Clifford gates* |
| SDP / NCTSSOS | high-poly in `O(N^k)` | `O(N^{2k})` | level k* ; C9 ↓ ; A1 dim |

---

# 9. Tasks → which methods (and how cost scales with the task)

| Task | Methods (cheap → expensive within reach) | Cost note |
|------|------------------------------------------|-----------|
| Ground-state energy | integrable-exact (C11) ≪ MF ≪ DMRG(1D)/QMC(sign-free)/AFQMC/VMC ≪ iPEPS(2D) ≪ ED | tensor-network cost set by B5; QMC by C12 |
| Full spectrum / level statistics | ED full only | `O(D_blk³)`; needs C9/C10 to reach useful `N` |
| Few excited states / gap | ED Lanczos, DMRG (targeted) | per-state ≈ GS cost |
| Finite-T thermodynamics | classical/quantum MC, LTRG/XTRG, FTLM/TPQ, DMFT, purification/METTS | low-`T` raises χ (TN) / sign (DQMC) |
| Real-time dynamics | ED-Krylov (small), TEBD/TDVP, t-VMC | capped by entanglement barrier (B5,D13); QMC blocked |
| Spectral function `S(q,ω)`/`A(ω)` | KPM, ED continued-fraction, DMFT(+solver), DQMC+analytic-cont., TEBD+Fourier | analytic continuation is ill-posed |
| Critical exponents / CFT data | MCRG, TRG/TNR, MERA, finite-size scaling of any GS method | needs B6 criticality |
| Order parameters / phase diagram | MF, QMC, DMRG/iPEPS, VCA, DMFT | accuracy vs method bias |
| Entanglement entropy / spectrum | DMRG/MPS (free), replica-trick QMC, ED | SPT/topo diagnostics (B7) |
| Topological order (TEE, degeneracy) | DMRG (MES protocol), ED on torus | needs A2 torus/cylinder |
| Rigorous energy bracket | VMC (upper) + SDP/NCTSSOS (lower) | two-sided, works in C12 sign-ful regimes |
| Spectra of correlated solids | DMFT/CDMFT/DCA, GW+DMFT, NRG (impurity) | momentum resolution needs clusters |

---

## References (anchored in the harness KB `literature/`, plus standard reviews)

- **ED:** Weisse–Fehske "Exact Diagonalization Techniques" (2008); Sandvik
  "Computational Studies of Quantum Spin Systems" (arXiv:1101.3281); Wietek et al.
  "XDiag" (arXiv:2505.02901); Wietek–Läuchli 48–50-site sublattice coding
  (arXiv:1804.05028); QuSpin (arXiv:1610.03042); KPM review Weisse et al.
  RMP 78, 275 (2006); FTLM Jaklič–Prelovšek PRB 49, 5065; TPQ Sugiura–Shimizu PRL
  108, 240401 & 111, 010401.
- **Classical MC:** Swendsen–Wang PRL 58, 86; Wolff PRL 62, 361; local-update
  `z=2.1665(12)` Nightingale–Blöte PRL 76, 4548 (1996); cluster `z` Du–Zheng–Wang
  J. Stat. Mech. (2006) P05004; Wang–Landau PRL 86, 2050; parallel tempering
  Hukushima–Nemoto JPSJ 65, 1604.
- **MPS/DMRG:** Schollwöck Ann. Phys. 326, 96 (arXiv:1008.3477); Orús
  (arXiv:1306.2164); VUMPS Zauner-Stauber et al. (arXiv:1701.07035); TDVP/MPS
  unification Haegeman et al. (arXiv:1408.5056); Vidal TEBD (PRL 93, 040502).
- **PEPS/TN-RG:** Verstraete–Cirac (cond-mat/0407066); Jordan et al. iPEPS
  (cond-mat/0703788); Orús–Vidal CTMRG (arXiv:0905.3225); Corboz variational iPEPS
  (arXiv:1605.03006); fast full update (arXiv:1503.05345); simple update
  Jiang–Weng–Xiang PRL 101, 090603; Lubasch–Cirac–Bañuls NJP 16, 033014;
  differentiable TN Liao–Liu–Wang–Xiang (arXiv:1903.09650); iPEPS review
  (arXiv:2308.12358); TRG Levin–Nave PRL 99, 120601; HOTRG `O(χ^{4d−1})` Xie et al.
  PRB 86, 045139 (arXiv:1201.1144); MERA Evenbly–Vidal (arXiv:0707.1454, 1109.5334).
- **Thermal TN & dynamics:** LTRG Li et al. (arXiv:1011.0155); bilayer LTRG
  (arXiv:1612.01896); XTRG Chen et al. (arXiv:1801.00142); MPS time-evolution review
  Paeckel et al. Ann. Phys. 411, 167998 (arXiv:1901.05824); quench entanglement
  growth Calabrese–Cardy (cond-mat/0503393); MPS-simulability Rényi-`α<1` criterion
  Schuch et al. PRL 100, 030504 (arXiv:0705.0292); W^II Zaletel et al. PRB 91,
  165112 (arXiv:1407.1832); METTS White PRL 102, 190601 & Stoudenmire–White NJP 12,
  055026; DMRG-X Khemani et al. PRL 116, 247204 (arXiv:1509.00483); MBL log-growth
  Bardarson–Pollmann–Moore PRL 109, 017202; MBL review Abanin et al. RMP 91, 021001
  (arXiv:1804.11065).
- **QMC:** Becca–Sorella (2017, DOI:10.1017/9781316417041); Sandvik
  (arXiv:1101.3281); directed loops Syljuåsen–Sandvik (cond-mat/0202316);
  AFQMC Zhang (2019); CPMC-Lab (arXiv:1407.7967); ALF/DQMC (arXiv:1704.00131);
  Troyer–Wiese sign problem PRL 94, 170201.
- **VMC/NQS:** Sorella SR (cond-mat/9803107, PRB 64, 024512); Carleo–Troyer
  (arXiv:1606.02318); NetKet (arXiv:2112.10526); quantum natural gradient
  (arXiv:1909.02108); mVMC (arXiv:1711.11418).
- **Embedding:** DMFT-exact-at-Z→∞ Metzner–Vollhardt PRL 62, 324 (1989) +
  self-energy-locality proof Müller-Hartmann Z. Phys. B 74, 507 (1989); Georges et
  al. DMFT RMP 68, 13 (Eq. 18 hopping `t=t*/√(2d)`); Kotliar et al. RMP 78, 865;
  Caffarel–Krauth ED-DMFT (cond-mat/9306057); Maier et al. cluster RMP 77, 1027
  (N_c control); CT-QMC solver sign Gull et al. RMP 83, 349; Knizia–Chan DMET
  PRL 109, 186404; Bulla et al. NRG RMP 80, 395; Metzner et al. fRG RMP 84, 299;
  Bartlett–Musiał CC RMP 79, 291.
- **MF/semiclassical:** Arovas et al. "The Hubbard Model" (arXiv:2103.12097);
  Auerbach, *Interacting Electrons and Quantum Magnetism*; spin-wave/Colpa
  Tóth–Lake SpinW J. Phys. Condens. Matter 27, 166002 (arXiv:1402.6069);
  slave-boson Kotliar–Ruckenstein PRL 57, 1362; VCA/SFT Potthoff EPJB 32, 429 &
  Potthoff–Aichhorn–Dahnken PRL 91, 206402.
- **Circuit sim:** Vidal (quant-ph/0301063); Markov–Shi treewidth
  (quant-ph/0511069); hyper-optimized contraction (arXiv:2002.01935);
  TensorCircuit-NG (arXiv:2602.14167); stabilizer Gottesman–Knill (quant-ph/9807006)
  & Aaronson–Gottesman PRA 70, 052328; stabilizer-rank `α≈0.396`
  Qassim–Pashayan–Gosset Quantum 5, 606 (arXiv:2106.07740).
- **Certified bounds:** NPA hierarchy Navascués–Pironio–Acín NJP 10, 073013
  (arXiv:0803.4290); convergent NC polynomial optimization Pironio–Navascués–Acín
  SIAM J. Optim. (arXiv:0903.4368, the harness KB copy); Lasserre moment-SOS SIAM
  J. Optim. 11, 796; Kull et al. RG lower bounds (arXiv:2212.03014); Wang et al.
  certifying GS properties PRX 14, 031006 (arXiv:2310.05844) & scalable NCTSSOS
  (arXiv:2604.01555); many-body bootstrap Han (arXiv:2006.06002) & Cho et al.
  (arXiv:2206.12538); coarse-grained bootstrap (arXiv:2412.07837).
- **MCRG:** Swendsen PRL 42, 859 (1979) & 52, 1165 (1984); variational MCRG
  Wu–Car (arXiv:1707.08683).
