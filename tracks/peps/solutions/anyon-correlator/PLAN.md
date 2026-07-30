# PLAN.md — anyon-correlator

> **Living document.** This plan is subject to change at any time, depending on the
> progress of the actual work and problems encountered. Amendments are made by
> discussion, then recorded here with the date.

Challenge: [issue #50](https://github.com/QuantumBFS/quantum.harness/issues/50) — Numerical computation of anyon correlators from PEPS
Team: anyon-correlator — Huanyu Shi (KITS-UCAS)
Track: `peps` · Registration: PR #185 · Branch: `challenge/peps-anyon-correlator`
Code: `tracks/peps/solutions/anyon-correlator/` · Data/figures: `tracks/peps/results/<run>/` (gitignored)

## 1. Goal

Build an iPEPS workflow that computes anyon correlators Cₑ(r), Cₘ(r) of the toric code
in magnetic fields, extracts the correlation lengths ξₑ, ξₘ from the spectra of the
ordinary and flux-twisted double-layer transfer operators, and tracks them across the
field-driven anyon-condensation transition along one production-quality field path.

Hamiltonian (issue convention):

    H = −Jₑ Σₛ Aₛ − Jₘ Σₚ Bₚ − hₓ Σᵢ Xᵢ − h_z Σᵢ Zᵢ ,     Jₑ = Jₘ = 1

## 2. Conventions

- **C1 Hamiltonian.** Exactly as above; Jₑ = Jₘ = 1 sets the energy unit.
- **C2 Operators.** Aₛ = ∏_{i∈s} Xᵢ (star, X-type); B_p = ∏_{i∈p} Zᵢ (plaquette, Z-type).
- **C3 Lattice and unit cell.** Square lattice of vertices; spin-½ on every *edge*.
  Unit cell = one **composite site**: a vertex together with its two outgoing edges
  (east and north) → **2 physical spins per composite site** (fused dim-4 leg).
  **One PEPS tensor per composite site** (the vertex simplex V and the two edge
  projection tensors P_E, P_N contracted — the split V/P network is the parent
  construction, see §4.2 note). Stored as a **(2,2) supercell** (4 composite sites =
  8 physical spins) for Hamiltonian construction and finite-cell diagnostics; the
  completed M2 calculation ties the same tensor across all four positions. Stars are
  centered on vertices, plaquettes on faces; both are **3-site L-shaped terms** on the composite
  lattice: star (r,c) = {E(r,c), E(r,c−1), N(r,c), N(r+1,c)}, plaquette (r,c) =
  {E(r,c), E(r−1,c), N(r,c), N(r,c+1)} — incidence identical to M1's ED construction.
- **C4 Environment contraction.** iPEPS in the thermodynamic limit. Default: CTMRG
  (PEPSKit). M2 uses χ=4 for the broad optimization and χ=8 near the ground state,
  with a fresh χ=8 environment as a sensitivity check. Boundary-MPS / VUMPS fixed
  points (MPSKit; arXiv:1810.07006) remain a future cross-check for transfer-sector
  work in M5, not an M2 requirement. Finite periodic tori (2×2, optional 3×3) serve
  only as ED references.
- **C5 (g, α) anyon sectors.** See §3–§4. Provisional labeling
  **1 = (0,+), e = (0,−), m = (1,+), ε = (1,−)**, subject to V1/V2 verification (§5).
- **C6 Ground-state sector.** In the future symmetry-preserving M3/M5 workflow, iPEPS
  converges to one topological sector; we accept and record it (initialization, seed),
  we do not control it. The dense M2 calibration does not assign a virtual sector.
- **C7 Virtual-ℤ₂ symmetry — exact throughout the sector-resolved production workflow.** See §4 for
  the four required distinctions. The local PEPS tensors remain **exactly virtual-ℤ₂ symmetric
  (intertwiners) throughout the sector-resolved M3 refinement and later production**:
  random initialization, simple
  update (or full update), AD `fixedpoint` optimization, and adiabatic field
  continuation. This is an exact production ansatz constraint so that the ordinary and
  twisted transfer operators retain well-defined (g, α) sectors. The symmetry pattern
  of the transfer-matrix **boundary fixed points is never imposed** (§4.4). The
  completed M2 optimization is an explicit calibration stage: one
  dense/unconstrained ComplexF64 `D=2` tensor was tied across the `(2,2)` cell and
  optimized from random values to validate the AD/environment pipeline. The explicit
  2026-07-30 M3 feasibility instruction extended this dense tensor along `(0,h_z)` for
  one bounded coarse pass; that pass is not a sector-resolved production state and did
  not meet M3 production acceptance. Exact virtual symmetry remains required before M5.
- **C8 Normalization.** Energies **per spin**, N = number of edge spins = 2 per unit
  cell. h=0 anchor: E₀/N = −(Jₑ+Jₘ)/2 = −1. Correlators normalized by the ⟨ψ|ψ⟩
  network value.
- **C9 Field path.** The first M3 feasibility pass uses the `(0,h_z)` axis,
  `h_z ∈ [0,0.5]`, dense near `h_z,c ≈ 0.328`. The model is self-dual under
  stars ↔ plaquettes with hₓ ↔ h_z, so the original `(hₓ,0)` MVP has identical
  physics. The diagonal hₓ = h_z (multicritical point 0.418(2), Wu–Deng–
  Prokof'ev, PRB 85, 195104, Fig. 17) is a stretch goal, out of MVP scope.
- **C10 Verification anchors.** h_c(hₓ,0) ≈ 0.3285 (3D-Ising; Trebst 2007, Dusuel 2011,
  Wu 2012); diagonal multicritical 0.418(2); Duivenvoorden 2017 (PRB 95, 235119) for
  qualitative ξ_a behavior and boundary-fixed-point diagnostics.

## 3. Transfer operators, sectors, and anyon correlators

**Ordinary (untwisted) transfer operator** 𝕋 ≡ 𝕋₍₀₎: row-to-row (and column-to-column)
double-layer transfer operator, local tensor Σₚ Tᵖ ⊗ T̄ᵖ, virtual bond dimension D².

**Flux-twisted transfer operator** 𝕋₍₁₎: 𝕋 with a virtual-Z string threaded along the
transfer direction (a seam of (−1)^l insertions on the virtual bonds; the seam position
is a gauge choice, movable by the pulling-through relations, §4.3).

**Sector-resolved (mixed) operators** 𝕋₍g,α₎: each 𝕋₍g₎ commutes with the global virtual
𝒵 string (§4.2–4.3), so its spectrum decomposes into parity blocks α = ±. The four
(g, α) sectors — with twist and parity combined ("mixed") — are

    1 = (0,+)   e = (0,−)   m = (1,+)   ε = (1,−)      [provisional, §5 V2]

**Eigenvalue selection.** For anyon a = (g, α) with endpoint/string operator S_a on the
virtual legs, define the endpoint form factor F_a(ν) = ⟨L_ν|S_a|R_vac⟩ over eigenstates
ν of 𝕋₍g,α₎. Then

    λ_a = leading-magnitude eigenvalue of 𝕋₍g,α₎ among eigenstates with F_a ≠ 0

— **not** generically a subleading twisted eigenvalue: symmetry can force F_a = 0 on
the leading state, in which case the next eigenstate with nonzero form factor governs.

**Correlators.** ξ_a = 1/ln|λ₀/λ_a| (λ₀ = vacuum eigenvalue of 𝕋₍₀,+₎);
C_a(r) ∼ |F_a|² |λ_a/λ₀|ʳ asymptotically; cross-checked against explicit two-endpoint
insertions at separation r where accessible.

## 4. Symmetry architecture — four distinct notions (do not conflate)

1. **ℤ₂-graded tensor storage.** A data-layout choice: TensorKit `Z2Irrep`-graded
   spaces (V = Z2Space(0⇒1, 1⇒1) at D=2), block-sparse storage by charge. Graded
   storage alone does not imply any physical symmetry.
2. **Exact virtual-ℤ₂ invariance of the local tensor.** A constraint on tensor
   *values*: each local tensor is an exact ℤ₂ intertwiner — nonzero components only
   where total leg charge is conserved. For the exact toric-code tensor (amended at
   M2): the composite rank-6 tensor
   T^{pE pN}_{nesw} = (−1)^{pE·e + pN·n} · δ_{n⊕e⊕s⊕w,0} / 2,
   i.e. the vertex parity simplex with the edge-occupancy copied to the physical
   spins **in the X basis** (amplitude ⟨p|H|a⟩). Rationale: the naive Z-basis copy
   (δ_{pE,e}δ_{pN,n}·δ_{parity}) builds the Z-basis *cycle gas* — the toric code
   with stars↔plaquettes exchanged (⟨Aₛ⟩ = 0 for our H); the X-basis copy builds
   the cycle gas in the X basis = the cut gas in the Z basis = ∏ₛ(1+Aₛ)|0⟩.
   Verified: E_cell = −8 and ⟨Aₛ⟩ = ⟨B_p⟩ = 1 to 2e-16 by CTMRG with zero
   optimization. Maintained exactly through initialization, simple/full update,
   AD optimization, and field continuation in the symmetry-preserving production
   route (C7). The dense tied-tensor M2 calibration is the documented exception.
3. **Pulling-through relations.** The operational content of the symmetry. For the
   composite rank-6 tensor (amended at M2): Z^{⊗4}·T = T on the virtual legs
   (virtual invariance), and a virtual Z on a single leg equals a physical Z on the
   corresponding edge spin (Z_e·T = Z_{pE}·T, Z_n·T = Z_{pN}·T) — a virtual-Z
   string pulls through a tensor and can be absorbed by physical Z's. Double layer:
   bra/ket phases cancel, so virtual-Z strings pull through the norm network freely;
   hence [𝕋, 𝒵] = 0 with 𝒵 the global virtual-Z string, and twist seams are
   well-defined and movable.
4. **Symmetry of transfer-matrix boundary fixed points — NOT imposed.** The boundary
   fixed points (dominant eigenvectors of 𝕋₍g,α₎, MPOs on the virtual legs) may or may
   not be 𝒵-symmetric. Their symmetry breaking, sector degeneracy, and endpoint form
   factors are **physical outputs**: unbroken vs broken fixed-point symmetry and the
   form-factor structure diagnose anyon confinement vs condensation (Duivenvoorden
   2017). We measure them; we never constrain them.

## 5. Verification protocol for future sector work

- **V1 (M5 machinery floor, h=0).** Before accepting M5 sector results, use a
   symmetry-preserving h=0 anchor. In every non-vacuum sector the leading
   **form-factor-selected** eigenvalue (§3 selection rule) must show |λ/λ₀| below a
   documented residual floor (ideal fixed point: ξ = 0). The boundary-parity partner
   of the vacuum — the (0,−) dominant state whose endpoint form factor vanishes — is
   exempt by construction. The dense M2 state is an optimizer calibration and is not
   used for this sector test.
- **V2 (e/m assignment).** Along (hₓ, 0): hₓ anticommutes with B_p = ∏Z, so it
  condenses plaquette violations — the sector assigned m = (1,+) must show growing ξ
  while e = (0,−) stays short-ranged. If observed reversed, swap e ↔ m labels for our
  basis convention and record the swap in run.json.
- **V3 (optional).** Fusion consistency ε = e × m from the (1,−) sector; sanity only.
- **Exact symmetry-preserving anchor.** If the h=0 sector structure is unresolvable or
  M5 requires a cleaner ξ floor, use the analytic ℤ₂-graded toric-code tensor of §4.2
  (composite rank-6, X-basis copy), validate the sector machinery with it
  (E_cell = −8 exactly, ideal ξ = 0), and use it as the symmetry-preserving h=0
  anchor. This is future M3/M5 setup, not part of completed M2.
- **Dense/unconstrained validation comparison (limited).** One nonsymmetric ComplexF64
  energy comparison at 1–2 mid-field points, small D, quantifying the exact-ℤ₂ ansatz
  restriction; recorded in run.json. Never the production path.

## 6. Milestones

### M0 — Stack setup
- **Purpose:** working Julia tensor-stack.
- **Tasks:** `make install julia`; `make install pepskit`; `make install mpskit`;
  smoke test `julia --project=julia-env -e 'using TensorKit, PEPSKit'` and MPSKit equivalent.
- **Files/outputs:** `julia-env/Manifest.toml` (pinned); smoke-test log.
- **Acceptance:** both smoke tests load and run a trivial contraction.
- **Failure/fallback:** precompile/mirror issues → `/setup-julia` (mirror config);
  version conflicts → pin compatible versions in Manifest.
- **Depends/status:** none → **done 2026-07-27** — Julia 1.12.6 (juliaup, NJU mirror);
  TensorKit 0.16.5 + PEPSKit 0.8.0 + MPSKit 0.13.12 + MPSKitModels 0.4.7 in `julia-env`
  (resolved combo: PEPSKit 0.8.0 requires TensorKit 0.16.x, not 0.17); ℤ₂-graded smoke
  test passed. TensorKit 0.16 API notes for later milestones: constructor
  `TensorMap{T}(undef, cod, dom)` (no function-based form); iterate `blocks(t)`, access
  `block(t, c)`, list `blocksectors(t)`; `@tensor M[a; b]` — the semicolon is required,
  otherwise all free indices land in the codomain (V⊗V′ vector instead of an
   endomorphism V→V). `julia-env/Project.toml` records the direct PEPSKit, JLD2, and
   Zygote dependencies required by the retained M2 scripts.

### M1 — Hamiltonian + required 2×2 ED unit test
- **Purpose:** validate term construction independently of any PEPS machinery.
- **Tasks:** build Aₛ, B_p, field terms; exact diagonalization on the 2×2 periodic
  torus (8 spins). Required checks: E₀(h=0) = −8; a few (hₓ, h_z) field points;
  large-field limits: along (hₓ, 0) E₀/N → −hₓ − Jₑ/2 (exact, since
  [Aₛ, ΣᵢXᵢ] = 0 makes the star part contribute its minimum −NₛJₑ at all hₓ);
  generic direction E₀/N → −√(hₓ² + h_z²) up to an O(J) first-order shift.
  Optional (stretch): 3×3 ED (18 spins); TFIM-duality spectrum check along (hₓ, 0).
- **Files/outputs:** `scripts/ed_checks.jl`; `tests/runtests.jl` (2×2 test);
  `results/<run>/ed_2x2.csv`.
- **Acceptance:** unit test passes in seconds and is re-runnable before every later stage.
- **Failure/fallback:** mismatch → fix sign/factor conventions in the terms; never
  loosen the test.
- **Depends/status:** M0 → **done 2026-07-28** — 7/7 gates pass in 1.5 s
  (`tests/runtests.jl`): operator construction (incidence, involutions, commutation,
  [Aₛ, ΣX] = 0), E₀ = −8 with degeneracy 4 and gap 4 (gap measured **above the
  degenerate ground space**, vals[degen+1] − E₀), all ground states stabilized
  (⟨Aₛ⟩ = ⟨B_p⟩ = 1 to 1e-15), self-duality |ΔE₀| < 1e-14, monotonicity, large-field
  windows (E₀/N = −5.5125 at (5,0); −7.3538 at (5,5) vs −√50 = −7.0711).
  CSV: `tracks/peps/results/20260728-114418-ed-checks/ed_2x2.csv`.

### M2 — Random initialization to the h=0 ground state
- **Purpose:** validate random tensor → fixed-point AD → CTMRG → ground-state
  observables end-to-end against the exact h=0 anchor.
- **Ansatz:** one random dense ComplexF64 `D=2` tensor copied to all four positions of
  the `(2,2)` cell. No virtual ℤ₂ constraint and no exact-state initialization.
- **Tasks:** optimize the shared tensor with fixed-point AD, average the four
  positional gradients into the tied-tensor tangent direction, use normalized Armijo
  backtracking, contract with CTMRG at χ=4 for the broad descent and χ=8 near the
  target, and measure E₀/N plus all site-resolved ⟨Aₛ⟩ and ⟨B_p⟩. Evaluate the exact
  tensor separately as a stationary code benchmark. Recontract the accepted final
  tensor from a fresh χ=8 environment to record contraction sensitivity.
- **Files/outputs:** `scripts/ad_tied_core.jl`, `scripts/ad_tied_gd.jl`,
  `tests/tied_ad_core_tests.jl`, `M2_REPORT.md`, `M2_SU_FINDINGS.md`, and
  `figures/m2_energy_convergence.svg`; local checkpoint and CSV artifacts under
  `results/20260730-m2-chi8-warm-continue-77-to100/`.
- **Acceptance:** using the accepted warm-started environment,
  |E₀/N + 1| ≤ 1e-6 and every site-resolved |⟨Aₛ⟩−1| and |⟨B_p⟩−1| ≤ 1e-6;
  E_cell ≥ −8−1e-6 and |⟨Aₛ⟩|,|⟨B_p⟩| ≤ 1+1e-6. Record a fresh χ=8 contraction of
  the same tensor and require its energy/stabilizers to agree within 1e-6.
- **Failure handling:** reject physical-bound violations; reduce the Armijo step after
  a non-convergent trial environment; warm-start trial CTMRG from the accepted
  environment; increase χ only after fixed-tensor diagnostics show that the smaller
  environment is unreliable.
- **Depends/status:** M0, M1 → **completed 2026-07-30**. The random-start step-86
  tensor gives E_cell = −7.999999995072 (E/N = −0.999999999384), with maximum
  star/plaquette errors 5.95e-10/6.38e-10 at χ=8. A fresh χ=8 contraction of the same
  tensor differs in energy by 6.49e-9. The exact tensor is a separate stationary
  benchmark. See `M2_REPORT.md` for the result and `M2_SU_FINDINGS.md` for the
  superseded simple-update investigation.

### M3 — Adiabatic ground states along `(0,h_z)` (workflow step 4)
- **Purpose:** establish whether the accepted M2 dense tensor can support a bounded
  finite-field continuation and a qualitative transition diagnostic.
- **Tasks:** warm-start the tensor and environment from each field to the next; use
  fixed-point AD with bounded Armijo trials; report fresh-environment observables;
  plot only `m_z = Σ_i⟨Z_i⟩/N`; retain energy, stabilizers, and convergence metadata.
- **Files/outputs:** `scripts/m3_hz_continuation.jl`, `tests/m3_hz_tests.jl`,
  `M3_REPORT.md`, `figures/m3_mz_vs_hz_invalid.svg`, incremental CSV/JLD2 artifacts under
  `tracks/peps/results/20260730-m3-hz-*/`.
- **Acceptance:** continuation accepts updates through the grid, fresh and warm
  contractions agree within the declared tolerance, operator bounds are respected,
  `<B_p>` remains close to one, and the single diagnostic supports a coarse transition
  interval.
- **Failure/fallback:** record bounded non-convergence and stop; do not increase beyond
  the approved `χ=6` fallback or turn the first pass into open-ended optimization.
- **Depends/status:** M2 optimizer/environment machinery → **M3 UNCOMPLETED;
  production acceptance not met**. `χ=4` was branch-unstable. The guarded
  `χ=6` grid completed, but AD accepted no update at five positive-field points,
  stabilizers overshot
  physical bounds, and `m_z` showed no feature near `h_z≈0.33`. See `M3_REPORT.md`;
  no transition estimate is accepted. A branch-consistent repair then produced smooth
  energy descent and a decreasing gradient at `h_z=0.10`, but the final independent
  multi-seed audit failed the declared operator bound
  (`max|⟨B_p⟩|=1.000171798 > 1+10⁻⁶`). The chain and later stages were not run.
  Completed exploratory runs and optimizer repairs are failure evidence, not M3
  completion.
- **2026-07-30 amendment (series-validation protocol).** A second session ratified
  a small-field validation against the hₓ=0 series expansion
  (e_series(h_z) = −1 − h_z²/4 − 15h_z⁴/64 − 147h_z⁶/256 − 18003h_z⁸/8192 per edge
  spin; arXiv:0807.0487 Eq. 8 with e_ours(h) = 2 e_paper(h/2)): tensor-only
  continuation from the M2 step-86 anchor, no optimizer state across fields,
  frozen-tensor multi-initialization CTMRG audit (warm + fresh deterministic +
  ≥2 fresh random, same χ/tol) plus a χ-increase stability check, acceptance only
  on stationary optimizer + branch consistency + χ stability. The h_z=0 anchor was
  accepted (δ = −1.95e-10 vs series); h_z=0.05/0.10 were flagged
  contraction-ambiguous after the warm CTMRG branch drifted to a trivial
  factorizing fixed point (artifact descent to −8−8h_z, stabilizers > 1) while
  fresh branches stayed physical — the same disease as the χ=4/6 pass, now caught
  quantitatively (`M3_REPORT.md` §Series-Validation Pilot). Ratified optimizer
  amendments: **A1** α₀=0.005 with fresh-verified acceptance (ran; warm-trial
  fragility found); **A2** from-scratch deterministic trial objective + fresh
  random-seed veto (implemented and unit-tested; unexecuted at the deadline).
  h_z=0.10 deferred until 0.05 passes. Next-session commands:
  `CHALLENGE_SUMMARY.md` §6.

### M4 — Phase-line check (workflow step 5, MVP scope)
- **Purpose:** locate and honestly report the transition on the MVP path.
- **Tasks:** transition window from E/N(h), ⟨X⟩(h) (optionally a fidelity/dE proxy);
  compare with h_c ≈ 0.3285. Finite-(D, χ) rounding turns the divergence into a
  crossover — report a **window**, no critical-exponent claims.
- **Files/outputs:** analysis inside the M3 driver or `scripts/phase_line.jl`;
  figure data for F1.
- **Acceptance:** window stated with D, χ provenance; literature comparison stated.
- **Failure/fallback:** window too wide → report as-is with provenance; do not densify
  h beyond the budget.
- **Depends/status:** accepted M3 ground-state path → **blocked by the inconclusive
  M3 first pass**. Do not interpret the current `m_z` curve as a phase boundary.

### M5 — Anyon spectra and correlators (workflow step 6, the challenge content)
- **Purpose:** deliver Cₑ(r), Cₘ(r), ξₑ(h), ξₘ(h) along the path.
- **Tasks:** build 𝕋₍₀₎, 𝕋₍₁₎ and sector-resolved 𝕋₍g,α₎ from each optimized state
  (PEPSKit CTMRG edge tensors, or MPSKit leading boundary of the uniform-MPS form);
  sector spectra; endpoint form factors F_a; λ_a per §3 (form-factor selection);
  ξ_a(h); explicit two-endpoint insertion cross-checks at accessible r; V1 floor at
  h=0; V2 assignment along the path; boundary fixed-point symmetry pattern recorded
  (§4.4) as the condensation diagnostic; optional V3.
- **Files/outputs:** `scripts/anyon_spectra.jl`; `spectra_<h>.csv` per sector;
  `formfactors.csv`; `xi_vs_h.csv`; `correlators_<h>.csv`; run log.
- **Acceptance:** V1 floor documented; V2 outcome recorded; spectral C_a(r) consistent
  with explicit insertions at accessible r; ξ_e(h), ξ_m(h) delivered with D, χ
  provenance.
- **Failure/fallback:** leading-state form factor zero → next eigenstate (by
  definition, §3); nonsymmetric eigensolver mixing → rely on graded sector blocks;
  ξ floor too high → tighten the symmetry-preserving h=0 anchor (§5); V2
  reversed → swap labels, record.
- **Depends/status:** M2 (optimizer/environment machinery), M3 (symmetry-preserving
  states) → **pending**. Transfer-spectrum and VUMPS cross-checks begin here as part
  of sector validation; they were not M2 acceptance gates.

### M6 — Handoff
- **Purpose:** submission-ready run.
- **Tasks:** finalize run.json (reproduce-paper schema); figures
  **F1** E/N(h), ⟨X⟩(h) with transition window · **F2** 4-panel (g, α) sector spectra
  at representative h · **F3** semilog Cₑ(r), Cₘ(r) · **F4** ξₑ(h), ξₘ(h) with
  h_c ≈ 0.328 marked; then `/challenge-report`; PR #185 accumulates all commits.
- **Files/outputs:** `results/<run>/run.json`; F1–F4 (PDF/PNG) in the results dir.
- **Acceptance:** report renders and the PR contains the reviewed scripts, data
  provenance, and figures.
- **Failure/fallback:** time overrun → deliver F1–F4 + report; D=4, diagonal path,
  3×3/duality checks remain stretch.
- **Depends/status:** M2–M5 → **pending**.

## 7. Settled scope exclusions (do not reopen)

Diagonal (h, h) path and the 0.418(2) multicritical point; full (hₓ, h_z) phase map
(F5); critical exponents / finite-entanglement scaling; mandatory D ≥ 4; 3×3 ED and
TFIM-duality as required tests; controlling the topological sector; imposing any
symmetry on transfer-matrix boundary fixed points; nonsymmetric tensors in the
production path.

## 8. Milestone state and compute policy

- M0 completed 2026-07-27; M1 completed 2026-07-28; M2 completed 2026-07-30.
- M3 remains uncompleted after a bounded dense-tensor attempt and repair point failed
  production acceptance; M4–M6 remain pending. A second-session series-validation
  pilot (2026-07-30) accepted the h_z=0 anchor but flagged h_z=0.05/0.10 as
  contraction-ambiguous; the diagnosed optimizer amendments A1/A2 and the prepared
  relaunch are recorded in `M3_REPORT.md` and `CHALLENGE_SUMMARY.md` §6.
  **Challenge closed at the deadline with status M3/6 uncompleted.**
- Before each future numerical milestone, confirm the Hamiltonian, lattice, boundary,
  ansatz/symmetry, target observable, system size, and local-versus-cluster cost.
- Future scripts must flush progress and write results incrementally per field point.
