# PROGRESS.md — anyon-correlator

## 1. Current status

- **Branch:** `challenge/peps-anyon-correlator` (in sync with origin; PR #185)
- **Current milestone:** M2 — in progress (machinery validated; SU-stage amendment pending)
- **Last completed milestone:** M1 — passed 2026-07-28 (committed `acc6325`)
- **Latest relevant commit:** this commit — M2 partial: machinery + inspection findings
- **Last updated:** 2026-07-28

## 2. Milestone overview

| M | Status |
|---|---|
| M0 stack setup | passed |
| M1 Hamiltonian + 2×2 ED unit test | passed |
| M2 h=0 ground state (SU+AD) | in progress — machinery validated; SU stall documented; route amendment pending |
| M3 adiabatic path (hₓ, 0) | not started |
| M4 phase-line check | not started |
| M5 anyon spectra/correlators | not started |
| M6 handoff | not started |

## 3. Completed work

### M0 — stack setup (passed 2026-07-27)

- **Julia (native WSL):** `/home/huanyushi/.juliaup/bin/julia` — v1.12.6
  (BINDIR `/home/huanyushi/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu/bin`), juliaup-installed, NJU mirror in `.bashrc` + `~/.julia/config/startup.jl`.
- **Recorded versions (`julia-env`):** TensorKit 0.16.5 (held from 0.17 by PEPSKit compat), PEPSKit 0.8.0, MPSKit 0.13.12, MPSKitModels 0.4.7, KrylovKit 0.10.4, QuadGK 2.11.3, JLD2 (added at M2). `Manifest.toml` local/gitignored per harness policy.
- **Smoke tests (all passed):** package load; ℤ₂-graded `TensorMap` construction + block access + contraction with asserts; `scripts/setup-julia.sh verify julia-env PEPSKit` → "ok: PEPSKit loaded".
- **TensorKit 0.16 API notes (needed in M2/M5):** constructor `TensorMap{T}(undef, cod, dom)`; iterate `blocks(t)`, access `block(t, c)`, list `blocksectors(t)`; `@tensor M[a; b]` needs the semicolon or all free indices land in the codomain. Dense↔TensorMap layout is **first-leg-fastest** (kron factors must be reversed); `fuse(V1,V2)` basis = first factor fast.

### M1 — Hamiltonian + 2×2 ED unit test (passed 2026-07-28)

- **Convention implemented (PLAN.md C1/C2):** H = −Σ Aₛ − Σ B_p − hₓ Σ Xᵢ − h_z Σ Zᵢ; Aₛ = ∏X stars, B_p = ∏Z plaquettes; 2×2 periodic torus, 8 edge spins (h(x,y) → 1+x+2y, v(x,y) → 5+x+2y).
- **7/7 acceptance gates pass** (1.5 s): operator construction (incidence 2 stars + 2 plaquettes per edge, involutions, mutual commutation, [Aₛ, ΣX] = 0); E₀ = −8, degeneracy 4, gap 4 (gap above the ground space); all 4 ground states stabilized (⟨Aₛ⟩ = ⟨B_p⟩ = 1 to 1e-15); self-duality |ΔE₀| < 1e-14; monotonicity; large-field windows (E₀/N = −5.5125 at (5,0); −7.3538 at (5,5) vs −√50 = −7.0711).
- **Files:** `scripts/ed_checks.jl` (Hamiltonian + gates + CSV driver), `tests/runtests.jl` (testset), `tracks/peps/results/20260728-114418-ed-checks/ed_2x2.csv` (gitignored).
- **PLAN.md amended:** large-field limit formula corrected (was "−(hₓ+h_z)"); M1 marked done.

### M2 (partial, 2026-07-28) — machinery + SU inspection

- **Design ratified:** composite single-tensor unit cell (one vertex + E,N edges; fused dim-4 physical leg, trivially Z₂-graded; virtual Z2Space(0⇒⌈D/2⌉, 1⇒⌊D/2⌋)); (2,2) supercell; V/P split construction kept as parent (exact tensor built by contracting V and P, unit-tested against the closed form).
- **Exact tensor corrected** (PLAN §4.2 amendment): X-basis copy T = (−1)^{pE·e+pN·n}·δ_{n⊕e⊕s⊕w,0}/2. The naive Z-basis copy builds the dual (cycle-gas) toric code, ⟨Aₛ⟩ = 0 — caught by a finite-patch dense contraction (`inspection/patch_check.jl`).
- **Validated:** exact state → CTMRG E_cell = −8, stabilizers = 1 to 2e-16; normalization anchored (`expectation_value` = unit-cell total; E_cell = −8, per site = −2, per spin = −1, test T7); SU gates exact (single-gate tanh(2dt) match; gate-isolation runs converge to −8).
- **SU finding:** random-init full-circuit SU stalls at non-ground fixed points at D = 2 (graded and ungraded), 3, 4, 6 — mean-field truncation + star/plaquette competition; stage-wise continuation (plaquette-only) reaches −8. Full documentation in `FINDINGS.md`; probes in `inspection/`.
- **Files:** `scripts/tc_peps.jl` (machinery), `scripts/groundstate_h0.jl` (driver, stages 0–6 active, 7–8 deferred), `scripts/ed_checks.jl` (M1), `inspection/` (8 probe scripts + README), `FINDINGS.md`, `tests/runtests.jl` (M1 + M2 T1–T7).

## 4. Current milestone — M2 (in progress)

Ground state at h=0 by optimization (PLAN.md §6 M2).

- **Done:** machinery + exact anchor + SU finding (above).
- **Pending decision:** SU-stage route — stage-wise SU (random init → pin A sector → plaquette-only phase) vs product-state init (|+⟩^N). Both validated to reach E_cell = −8; awaiting ratification.
- **Then:** re-run pipeline → gates A1–A3 (E/edge spin within 1e-6 of −1, stabilizers site-resolved, χ 20→40 spot) → spectrum (stage 7) + VUMPS cross-check (stage 8, deferred) → M2 acceptance.

## 5. Open decisions and blockers

1. SU-stage route for M2's ground state (stage-wise SU vs product init) — see §4.
2. Role of AD after the route is fixed (currently suspended).

## 6. Reproduction commands (all verified)

```bash
export PATH="$HOME/.juliaup/bin:$PATH"
julia --version                                    # julia version 1.12.6
julia --project=julia-env -e 'using TensorKit, PEPSKit, MPSKit, MPSKitModels'   # loads OK
# M1 (1.5 s, 7/7 gates):
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/runtests.jl
# M1 CSV regeneration:
julia --project=julia-env tracks/peps/solutions/anyon-correlator/scripts/ed_checks.jl
# M2 ungraded SU inspection (the stall reproduction):
julia --project=julia-env tracks/peps/solutions/anyon-correlator/inspection/su_ungraded_test.jl
```

## 7. Next actions (M2, ordered)

1. Ratify the SU-stage route (stage-wise SU vs product init).
2. Wire the route into `scripts/groundstate_h0.jl`; re-run; evaluate gates A1–A3.
3. Spectrum (stage 7) + VUMPS cross-check (stage 8); record `groundstate_h0.jld2`.
4. Amend PLAN.md M2 status; update this file; commit + push (this folder only).

## 8. New-session handoff

Read first, in order: `PROGRESS.md` (this file) → `PLAN.md` (authoritative plan, §6 for milestone gates) → `FINDINGS.md` (M2 inspection results) → `README.md`. Git: branch `challenge/peps-anyon-correlator`; M1 @ `acc6325`. Environment: `export PATH="$HOME/.juliaup/bin:$PATH"`, project env `julia-env/` (TensorKit 0.16.5 / PEPSKit 0.8.0 / MPSKit 0.13.12). Note: `julia-env/Project.toml` has a deliberate uncommitted local modification (PEPSKit + JLD2).
