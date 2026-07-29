# PROGRESS.md — anyon-correlator

## 1. Current status

- **Branch:** `challenge/peps-anyon-correlator` (PR #185)
- **Current milestone:** M2 — completed; report ready
- **Last completed milestone:** M2 — passed 2026-07-30
- **Boundary:** paused before M3; no further optimization or M3 work authorized
- **Last updated:** 2026-07-30

## 2. Milestone overview

| M | Status |
|---|---|
| M0 stack setup | passed |
| M1 Hamiltonian + 2×2 ED unit test | passed |
| M2 h=0 random-init ground state | passed at χ=8 |
| M3 adiabatic path (hₓ, 0) | not started |
| M4 phase-line check | not started |
| M5 anyon spectra/correlators | not started |
| M6 handoff | not started |

## 3. Completed work

### M0 — stack setup (passed 2026-07-27)

- **Julia (native WSL):** `/home/huanyushi/.juliaup/bin/julia` — v1.12.6, juliaup-installed, NJU mirror.
- **Recorded versions (`julia-env`):** TensorKit 0.16.5, PEPSKit 0.8.0, MPSKit 0.13.12, MPSKitModels 0.4.7, KrylovKit 0.10.4, QuadGK 2.11.3, JLD2, Zygote 0.7.12. `Manifest.toml` local/gitignored per harness policy.
- **TensorKit 0.16 layout notes:** dense↔TensorMap is **first-leg-fastest** (kron factors reversed); `fuse(V1,V2)` basis = first factor fast; `TensorMap{T}(undef, cod, dom)`; `blocks(t)` / `block(t,c)` / `blocksectors(t)`; `@tensor M[a; b]` needs the semicolon.

### M1 — Hamiltonian + 2×2 ED unit test (passed 2026-07-28)

- H = −Σ Aₛ − Σ B_p − hₓ Σ Xᵢ − h_z Σ Zᵢ; Aₛ = ∏X stars, B_p = ∏Z plaquettes; 2×2 torus, 8 edge spins.
- **7/7 acceptance gates pass** (1.5 s): construction algebra, E₀ = −8 + degen 4 + gap 4, all ground states stabilized (1e-15), self-duality 1e-14, monotonicity, large-field windows.
- **Files:** `scripts/ed_checks.jl`, `tests/runtests.jl`, results CSV (gitignored).

### M2 (completed 2026-07-30) — random initialization to ground state

- **Design ratified:** composite single-tensor cell (vertex + E,N edges; fused dim-4 physical; (2,2) supercell); V/P split kept as parent construction; exact tensor = X-basis copy T = (−1)^{pE·e+pN·n}·δ_{n⊕e⊕s⊕w,0}/2 (PLAN §4.2 amended; the Z-basis copy builds the dual cycle gas).
- **Machinery validations (all pass):** exact state → CTMRG E_cell = −8, stabilizers = 1 to 2e-16; `expectation_value` = unit-cell total (E_cell = −8 / per site = −2 / per edge spin = −1, test T7); SU gates exact (tanh(2dt) single-gate match; gate-isolation runs → −8); **AD gradient FD-exact** (ratio 1.000 at init and at the GD stuck point; fixed-point differentiation ≡ full AD to 1e-3); retract path smooth and descending; all 4 plaquette operators = +1 to 12 digits on the exact state.
- **SU finding (`M2_SU_FINDINGS.md`, first committed in `da25ab7`):** random-init full-circuit SU stalls at non-ground fixed points at D = 2–6; mechanism = mean-field truncation + star/plaquette competition; validated working routes: stage-wise SU and product init (both reach −8 exactly).
- **Earlier AD diagnosis:** the fixed-point AD gradient is finite-difference exact. OptimKit L-BFGS failed in its accumulated search direction, while independent-tensor gradient descent entered a one-plaquette-defect minimum near E_cell = −6.99. The defect-repair direction was nearly orthogonal to the energy gradient (`inspection/ad_gradient_diagnosis.jl`, `ad_full_vs_fixedpoint.jl`, `retract_path_probe.jl`, `slow_plaquette_diagnosis.jl`).
- **Successful route:** one random dense `D=2` tensor was tied across all four cell positions. The four positional gradients were averaged and copied back before each normalized Armijo step, excluding the nonuniform one-cell defect mode. χ=4 handled the broad descent; χ=8 and warm-started CTMRG stabilized the near-ground line search.
- **Primary accepted result (random start, step 86):** E_cell = −7.999999995072, E/N = −0.999999999384, maximum star error 5.95e-10, maximum plaquette error 6.38e-10, CTMRG residual 2.82e-9. A fresh-environment contraction of the same tensor gives E_cell = −8.000000001560; the 6.49e-9 spread is documented as finite-χ contraction sensitivity, not as a second state.
- **Exact benchmark (separate):** E_cell = −8, projected gradient norm 4.526e-16, maximum stabilizer error 1.665e-15. It was not used to initialize the random trajectory.
- **Retained files:** `scripts/ad_tied_core.jl`, `scripts/ad_tied_gd.jl`, `tests/tied_ad_core_tests.jl`, `M2_REPORT.md`, `M2_SU_FINDINGS.md`, and `figures/m2_energy_convergence.svg`. Diagnostic scripts remain under `inspection/` and `scripts/ad_*.jl`; obsolete Slurm launchers were removed.

## 4. Current milestone — M2 completed

Ground state at h=0 by optimization (PLAN.md §6 M2):

- **Completed:** random dense `D=2` initialization reached the energy and every site-resolved stabilizer within 1e-6.
- **Evidence:** `M2_REPORT.md`, the tracked convergence figure, 38/38 focused tests, and the local step-86 checkpoint/CSV artifacts.
- **Not part of M2:** the virtual-ℤ₂ production state begins in M3; transfer spectra and VUMPS sector cross-checks begin in M5. A fresh end-to-end rerun with the final warm-start code was not required for M2 acceptance.
- **Not started:** M3.

No further compute is scheduled.

## 5. Open decisions and blockers

- No blocker remains for the current M2 random-start optimization objective.
- M3 requires a new setup confirmation and explicit authorization.

## 6. Reproduction commands (all verified)

```bash
export PATH="$HOME/.juliaup/bin:$PATH"
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/runtests.jl   # M1 7/7 + M2 T1–T7
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/tied_ad_core_tests.jl   # 38/38 tied-AD tests
```

## 7. Next actions

1. Preserve the M2 report, code, tests, and checkpoint artifacts.
2. Stop before M3 unless the user explicitly starts the next milestone.
3. Treat virtual symmetry as an M3 design decision and transfer spectra/VUMPS as M5 validation, not unfinished M2 work.

## 8. New-session handoff

Read first, in order: `M2_REPORT.md` → `M2_SU_FINDINGS.md` → `PROGRESS.md` → `PLAN.md` (§6 milestones). M2 is complete at step 86 with E/N = −0.999999999384 and site-resolved stabilizer errors below 6.38e-10. The exact tensor is a separate stationary benchmark. Result checkpoints and CSVs are local/gitignored under `tracks/peps/results/20260730-m2-chi8-warm-continue-77-to100/`; the durable plot is `figures/m2_energy_convergence.svg`. No M3 work has started.
