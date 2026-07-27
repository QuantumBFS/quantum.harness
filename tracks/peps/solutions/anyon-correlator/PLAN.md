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
  Unit cell = one vertex plus its two outgoing edges (east and north) → **2 physical
  spins per unit cell**; tensors T_E (horizontal edge) and T_N (vertical edge), related
  by rotation. Stars are centered on vertices, plaquettes on faces. The exact PEPSKit
  `InfiniteSquare` shape mapping (e.g. unitcell=(1,2)) is fixed at implementation time
  and recorded in run.json.
- **C4 Environment contraction.** iPEPS in the thermodynamic limit. Default: CTMRG
  (PEPSKit). Sanctioned alternative: boundary-MPS / VUMPS fixed points (MPSKit;
  arXiv:1810.07006). Both share the environment bond dimension χ; one cross-check at a
  fixed setting is required (M2). Finite periodic tori (2×2, optional 3×3) serve only
  as ED references.
- **C5 (g, α) anyon sectors.** See §3–§4. Provisional labeling
  **1 = (0,+), e = (0,−), m = (1,+), ε = (1,−)**, subject to V1/V2 verification (§5).
- **C6 Ground-state sector.** iPEPS converges to one topological sector; we accept and
  record it (initialization, seed), we do not control it.
- **C7 Virtual-ℤ₂ symmetry — exact throughout the main workflow.** See §4 for the four
  required distinctions. The local PEPS tensors remain **exactly virtual-ℤ₂ symmetric
  (intertwiners) at every stage**: random initialization, simple update (or full
  update), AD `fixedpoint` optimization, and adiabatic field continuation. This is an
  exact ansatz constraint, never relaxed in the main workflow, so that the ordinary and
  twisted transfer operators retain well-defined (g, α) sectors. The symmetry pattern
  of the transfer-matrix **boundary fixed points is never imposed** (§4.4). The
  dense/unconstrained (nonsymmetric ComplexF64) calculation is retained **only as a
  limited validation comparison** (§5, M3): energy comparison at 1–2 field points,
  small D — never the production path.
- **C8 Normalization.** Energies **per spin**, N = number of edge spins = 2 per unit
  cell. h=0 anchor: E₀/N = −(Jₑ+Jₘ)/2 = −1. Correlators normalized by the ⟨ψ|ψ⟩
  network value.
- **C9 Field path.** MVP: the (hₓ, 0) axis, h ∈ [0, 0.6], dense near h_c ≈ 0.328.
  The model is self-dual under stars ↔ plaquettes with hₓ ↔ h_z, so (0, h_z) is
  identical physics. The diagonal hₓ = h_z (multicritical point 0.418(2), Wu–Deng–
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
   where total leg charge is conserved (for the exact toric-code tensor:
   Tᵖ_{lrud} = δ_{p, l⊕r⊕u⊕d}, i.e. p⊕l⊕r⊕u⊕d = 0). Maintained exactly through
   initialization, simple/full update, AD optimization, and field continuation (C7).
3. **Pulling-through relations.** The operational content of the symmetry. Single
   layer: Z_v^⊗4·T = Z_p·T (since (−1)^{l+r+u+d} = (−1)^p) — a virtual-Z string pulls
   through a tensor, converting to a physical Z. Double layer: bra/ket phases cancel,
   so virtual-Z strings pull through the norm network freely; hence [𝕋, 𝒵] = 0 with
   𝒵 the global virtual-Z string, and twist seams are well-defined and movable.
4. **Symmetry of transfer-matrix boundary fixed points — NOT imposed.** The boundary
   fixed points (dominant eigenvectors of 𝕋₍g,α₎, MPOs on the virtual legs) may or may
   not be 𝒵-symmetric. Their symmetry breaking, sector degeneracy, and endpoint form
   factors are **physical outputs**: unbroken vs broken fixed-point symmetry and the
   form-factor structure diagnose anyon confinement vs condensation (Duivenvoorden
   2017). We measure them; we never constrain them.

## 5. Verification protocol

- **V1 (machinery floor, h=0).** With the M2-optimized h=0 state, every non-vacuum
  sector shows |λ/λ₀| below a documented residual floor set by the optimization error
  (ideal fixed point: ξ = 0). If the floor is too high for M5, tighten the h=0
  optimization or trigger the exact-tensor fallback (below).
- **V2 (e/m assignment).** Along (hₓ, 0): hₓ anticommutes with B_p = ∏Z, so it
  condenses plaquette violations — the sector assigned m = (1,+) must show growing ξ
  while e = (0,−) stays short-ranged. If observed reversed, swap e ↔ m labels for our
  basis convention and record the swap in run.json.
- **V3 (optional).** Fusion consistency ε = e × m from the (1,−) sector; sanity only.
- **Exact-tensor fallback — trigger.** Any of: (i) M2 acceptance not met after the
  optimizer budget in M2-Fallback is exhausted; (ii) sector structure at h=0
  unresolvable (vacuum degeneracy / parity blocks not identifiable); (iii) M5 requires
  a cleaner ξ floor than optimization reached. Action: construct the analytic
  ℤ₂-graded toric-code tensor Tᵖ_{lrud} = δ_{p, l⊕r⊕u⊕d}, validate the full machinery
  with it (E₀/N = −1 exactly, ξ = 0 in all sectors), then use it as the h=0 anchor and
  as the M3 initialization.
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
  endomorphism V→V). `julia-env/Project.toml` carries PEPSKit locally but stays
  **uncommitted** (submission cleanliness: commits confined to this folder).

### M1 — Hamiltonian + required 2×2 ED unit test
- **Purpose:** validate term construction independently of any PEPS machinery.
- **Tasks:** build Aₛ, B_p, field terms; exact diagonalization on the 2×2 periodic
  torus (8 spins). Required checks: E₀(h=0) = −8; a few (hₓ, h_z) field points;
  large-field polarized limit E₀/N → −(hₓ+h_z). Optional (stretch): 3×3 ED (18
  spins); TFIM-duality spectrum check along (hₓ, 0).
- **Files/outputs:** `scripts/ed_checks.jl`; `tests/runtests.jl` (2×2 test);
  `results/<run>/ed_2x2.csv`.
- **Acceptance:** unit test passes in seconds and is re-runnable before every later stage.
- **Failure/fallback:** mismatch → fix sign/factor conventions in the terms; never
  loosen the test.
- **Depends/status:** M0 → **pending**.

### M2 — Ground state at h=0 by optimization (workflow steps 1–3)
- **Purpose:** validate the full ground-state pipeline (random init → update → AD →
  environment) end-to-end against the exact anchor.
- **Tasks:** random-init D=2 ℤ₂-graded tensors; simple-update imaginary-time warm
  start; AD `fixedpoint` polish; CTMRG environment (χ=20, tol 1e-8) with one
  MPSKit/VUMPS boundary cross-check; measure E₀/N, site-resolved ⟨Aₛ⟩, ⟨B_p⟩, and the
  h=0 transfer spectrum.
- **Files/outputs:** `scripts/groundstate_h0.jl`;
  `results/<run>/groundstate_h0.jld2` (tensors+env); `energy_convergence.csv`;
  `stabilizers_h0.csv`; `spectrum_h0.csv`; optimizer log (residuals, gradient norms).
- **Acceptance:** |E₀/N + 1| ≤ 1e-6 (target 1e-8); ⟨Aₛ⟩=⟨B_p⟩=1 within the same
  tolerance site-resolved; spectrum shows the expected fixed-point structure;
  CTMRG/VUMPS cross-check agrees.
- **Failure/fallback (in order):** new random seed; more SU steps / smaller Trotter
  step; AD settings (iterscheme :diffgauge vs :fixed, LBFGS memory); then the
  **exact-tensor fallback** (§5).
- **Depends/status:** M0, M1 → **pending**.

### M3 — Adiabatic ground states along (hₓ, 0) (workflow step 4)
- **Purpose:** production ground states on the MVP path.
- **Tasks:** adiabatic warm-start chain — each field point initialized from the
  previous point's converged tensors; simple-update scans + AD polish at selected
  points; D=2 → D=3 production (D=4 spot-check only if budget allows, cluster
  candidate via `/using-slurm`); χ = 20 → 40/80 near the transition; record
  initialization/route per point. Limited dense validation comparison per §5.
- **Files/outputs:** `scripts/groundstate_path.jl`; `path_energies.csv` (h, E/N, ⟨X⟩,
  residuals, χ, D); per-point tensor checkpoints (jld2).
- **Acceptance:** E/N and ⟨X⟩ converged in D and χ within recorded tolerances; the
  adiabatic chain is continuous (no energy-density jumps between neighboring points
  beyond warm-start tolerance).
- **Failure/fallback:** branch jump → refine h-grid locally; D=2 insufficient near
  transition → D=3 required, D=4 spot on cluster; dense comparison flags large
  ansatz-restriction error → record, and flag affected observables in the report.
- **Depends/status:** M2 → **pending**.

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
- **Depends/status:** M3 → **pending**.

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
  ξ floor too high → tighten h=0 optimization or exact-tensor fallback (§5); V2
  reversed → swap labels, record.
- **Depends/status:** M2 (machinery), M3 (states) → **pending**.

### M6 — Handoff
- **Purpose:** submission-ready run.
- **Tasks:** finalize run.json (reproduce-paper schema); figures
  **F1** E/N(h), ⟨X⟩(h) with transition window · **F2** 4-panel (g, α) sector spectra
  at representative h · **F3** semilog Cₑ(r), Cₘ(r) · **F4** ξₑ(h), ξₘ(h) with
  h_c ≈ 0.328 marked; then `/challenge-report`; PR #185 accumulates all commits.
- **Files/outputs:** `results/<run>/run.json`; F1–F4 (PDF/PNG) in the results dir.
- **Acceptance:** report renders; PR updated before Thu 20:00.
- **Failure/fallback:** time overrun → deliver F1–F4 + report; D=4, diagonal path,
  3×3/duality checks remain stretch.
- **Depends/status:** M2–M5 → **pending**.

## 7. Settled scope exclusions (do not reopen)

Diagonal (h, h) path and the 0.418(2) multicritical point; full (hₓ, h_z) phase map
(F5); critical exponents / finite-entanglement scaling; mandatory D ≥ 4; 3×3 ED and
TFIM-duality as required tests; controlling the topological sector; imposing any
symmetry on transfer-matrix boundary fixed points; nonsymmetric tensors in the
production path.

## 8. Timeline and compute budget

M0–M1 Mon (setup ~1 h precompile; tests minutes) · M2 Mon–Tue (hours) · M3 Tue–Wed
(hours; D=4 spot → `/using-slurm` candidate) · M4 byproduct of M3 · M5 Wed–Thu ·
M6 Thu, report before 20:00. All scripts flush progress per harness norms; results
written incrementally per field point.
