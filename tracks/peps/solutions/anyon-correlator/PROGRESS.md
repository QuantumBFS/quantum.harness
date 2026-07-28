# PROGRESS.md — anyon-correlator

## 1. Current status

- **Branch:** `challenge/peps-anyon-correlator` (in sync with origin; PR #185)
- **Current milestone:** M2 — not started
- **Last completed milestone:** M1 — passed 2026-07-28 (work uncommitted, awaiting review)
- **Latest relevant commit:** `08777d9` "[peps] anyon-correlator: M0 done" (pushed)
- **Last updated:** 2026-07-28

## 2. Milestone overview

| M | Status |
|---|---|
| M0 stack setup | passed |
| M1 Hamiltonian + 2×2 ED unit test | passed |
| M2 h=0 ground state (SU+AD) | not started |
| M3 adiabatic path (hₓ, 0) | not started |
| M4 phase-line check | not started |
| M5 anyon spectra/correlators | not started |
| M6 handoff | not started |

## 3. Completed work

### M0 — stack setup (passed 2026-07-27)

- **Julia (native WSL):** `/home/huanyushi/.juliaup/bin/julia` — v1.12.6
  (BINDIR `/home/huanyushi/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu/bin`), juliaup-installed, NJU mirror in `.bashrc` + `~/.julia/config/startup.jl`.
- **Recorded versions (`julia-env`):** TensorKit 0.16.5 (held from 0.17 by PEPSKit compat), PEPSKit 0.8.0, MPSKit 0.13.12, MPSKitModels 0.4.7, KrylovKit 0.10.4, QuadGK 2.11.3. `Manifest.toml` local/gitignored per harness policy.
- **Smoke tests (all passed):** package load; ℤ₂-graded `TensorMap` construction + block access + contraction with asserts; `scripts/setup-julia.sh verify julia-env PEPSKit` → "ok: PEPSKit loaded".
- **Files:** `PLAN.md` (M0 done, versions, TensorKit 0.16 API notes); `julia-env/Project.toml` (PEPSKit added — deliberately **uncommitted**).
- **TensorKit 0.16 API notes (needed in M2/M5):** constructor `TensorMap{T}(undef, cod, dom)`; iterate `blocks(t)`, access `block(t, c)`, list `blocksectors(t)`; `@tensor M[a; b]` needs the semicolon or all free indices land in the codomain.

### M1 — Hamiltonian + 2×2 ED unit test (passed 2026-07-28)

- **Convention implemented (PLAN.md C1/C2):** H = −Σ Aₛ − Σ B_p − hₓ Σ Xᵢ − h_z Σ Zᵢ; Aₛ = ∏X stars, B_p = ∏Z plaquettes; 2×2 periodic torus, 8 edge spins (h(x,y) → 1+x+2y, v(x,y) → 5+x+2y).
- **7/7 acceptance gates pass** (1.5 s): operator construction (incidence 2 stars + 2 plaquettes per edge, involutions, mutual commutation, [Aₛ, ΣX] = 0); E₀ = −8, degeneracy 4, gap 4 (gap above the ground space); all 4 ground states stabilized (⟨Aₛ⟩ = ⟨B_p⟩ = 1 to 1e-15); self-duality E₀(hₓ,h_z) = E₀(h_z,hₓ) to 1e-14; monotonicity along (hₓ,0); large-field windows: E₀/N = −5.5125 at (5,0) (theory: −hₓ − Jₑ/2 = −5.5, stars commute with the X-field), E₀/N = −7.3538 at (5,5) (−√50 = −7.0711 plus O(J) shift).
- **Files:** `scripts/ed_checks.jl` (Hamiltonian + gates + CSV driver), `tests/runtests.jl` (testset), `tracks/peps/results/20260728-114418-ed-checks/ed_2x2.csv` (gitignored).
- **PLAN.md amended:** large-field limit formula corrected (was "−(hₓ+h_z)"); M1 marked done.

## 4. Current milestone — M2 (not started)

Ground state at h=0 by optimization (PLAN.md §6 M2): random-init D=2 ℤ₂-graded PEPS → simple-update warm start → AD `fixedpoint` → CTMRG environment (χ=20, tol 1e-8) with one MPSKit/VUMPS boundary cross-check.

- **Acceptance gates:** |E₀/N + 1| ≤ 1e-6 (target 1e-8); site-resolved ⟨Aₛ⟩ = ⟨B_p⟩ = 1 within the same tolerance; fixed-point transfer spectrum; CTMRG/VUMPS agreement.
- **Fallbacks in order:** new seed → more SU steps / smaller Trotter step → AD settings (`:diffgauge` vs `:fixed`, LBFGS memory) → exact-tensor fallback (PLAN.md §5).

## 5. Open decisions and blockers

None.

## 6. Reproduction commands (all verified)

```bash
export PATH="$HOME/.juliaup/bin:$PATH"
julia --version                                    # julia version 1.12.6
julia --project=julia-env -e 'using TensorKit, PEPSKit, MPSKit, MPSKitModels'   # loads OK
bash scripts/setup-julia.sh verify julia-env PEPSKit # "ok: PEPSKit loaded"
# M1 (1.5 s, 7/7 gates):
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/runtests.jl
# M1 CSV regeneration:
julia --project=julia-env tracks/peps/solutions/anyon-correlator/scripts/ed_checks.jl
```

## 7. Next actions (M2, ordered)

1. Implement the D=2 ℤ₂-graded PEPS construction + random init (PLAN.md §4.2, exact tensor as reference: Tᵖ_{lrud} = δ_{p, l⊕r⊕u⊕d}).
2. Hamiltonian as PEPSKit `LocalOperator` for the 2-site unit cell (PLAN.md C3) — cross-check terms against M1's verified construction.
3. Simple-update warm start → AD `fixedpoint` at h=0; CTMRG χ=20, tol 1e-8; log energy/stabilizers per stage.
4. MPSKit/VUMPS boundary cross-check; evaluate M2 acceptance gates; record `groundstate_h0.jld2`.
5. Amend PLAN.md M2 status; update this file; commit + push (this folder only).

## 8. New-session handoff

Read first, in order: `tracks/peps/solutions/anyon-correlator/PROGRESS.md` (this file) → `PLAN.md` (authoritative plan, §6 for milestone gates) → `README.md`. Git: branch `challenge/peps-anyon-correlator` @ `08777d9` pushed (PR #185); M1 files uncommitted in working tree. Environment: `export PATH="$HOME/.juliaup/bin:$PATH"`, project env `julia-env/` (TensorKit 0.16.5 / PEPSKit 0.8.0 / MPSKit 0.13.12). Note: `julia-env/Project.toml` has a deliberate uncommitted local modification.
