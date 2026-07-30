# PROGRESS.md — anyon-correlator

## 1. Current status

- **Branch:** `challenge/peps-anyon-correlator` (PR #185)
- **Current milestone:** M3 — uncompleted; no accepted finite-field ground-state path
- **Last passed milestone:** M2 — passed 2026-07-30
- **Boundary:** current session closed with M3 unfinished; no further compute authorized
- **Last updated:** 2026-07-30

## 2. Milestone overview

| M | Status |
|---|---|
| M0 stack setup | passed |
| M1 Hamiltonian + 2×2 ED unit test | passed |
| M2 h=0 random-init ground state | passed at χ=8 |
| M3 adiabatic path (0, h_z) | uncompleted; attempted path rejected |
| M4 phase-line check | blocked by M3 |
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

### M3 — dense continuation along `(0,h_z)` (first pass 2026-07-30)

- **Approved diagnostic:** field polarization `m_z = Σ_i⟨Z_i⟩/N`; one main curve only.
- **Route:** accepted M2 step-86 dense tied `D=2` tensor; sequential tensor/environment warm starts; fresh final CTMRG; at most four fixed-point-AD updates per field.
- **Grid:** `0.00, 0.10, 0.20, 0.28, 0.30, 0.32, 0.33, 0.34, 0.36, 0.40, 0.50`.
- **Numerics:** `χ=4` was branch-unstable and stopped at `h_z=0.28`; the allowed `χ=6` fallback completed with fresh-energy Armijo checks, CTMRG tolerance `1e-6`, and 80 CTMRG iterations maximum.
- **Outcome:** continuation mechanics and AD updates worked below the transition, but five positive-field points accepted no update. `m_z` plateaued near `0.061`, so no transition interval is accepted; the mechanical largest slope `[0,0.1]` is an initialization artifact.
- **Plaquette check:** maximum `|⟨B_p⟩-1| = 0.0240`; close in magnitude but values overshoot the exact operator bound, so this is a warning rather than production validation.
- **Evidence:** `M3_REPORT.md`, `figures/m3_mz_vs_hz_invalid.svg`, `scripts/m3_hz_continuation.jl`, `tests/m3_hz_tests.jl`, and gitignored artifacts under `tracks/peps/results/20260730-m3-hz-*-fresh-armijo/`.
- **Repair attempt:** same-branch Armijo with `alpha_0=0.05` gave four descending
  updates at `h_z=0.10` and reduced the gradient norm from `0.1968` to `0.0645`.
  The point still failed the final independent audit because `max|⟨B_p⟩|` exceeded
  `1+1e-6`. Artifacts:
  `tracks/peps/results/20260730-m3-repair-point-chi6/`. No chain or smoke followed.

## 4. Current milestone — M3 uncompleted

- **Attempted:** bounded dense `D=2` exploratory grids, incremental checkpoints/CSV,
  one invalid `m_z(h_z)` curve, and fresh-environment stabilizer/convergence records.
- **Infrastructure repaired:** same-branch Armijo objective, independent multi-seed
  audits, site-resolved physical gates, staged execution, and provenance-bound stage
  markers.
- **Not accepted:** the ground-state path near `h_z≈0.33`; most near-transition points
  ended in Armijo failure, and the repaired `h_z=0.10` point still exceeded the
  physical plaquette bound.
- **Consequence:** no critical interval or comparison claim is carried into M4/M5.

The completed exploratory runs and code repairs do not mean that M3 is finished.

No further compute is scheduled pending user review.

## 5. Open decisions and blockers

- M3 production acceptance is blocked by CTMRG branch sensitivity and AD line-search
  failure in the original dense `D=2`, `χ≤6` first-pass budget. The line-search
  objective is now repaired, but finite-χ stabilizer estimates still violate the
  approved site-resolved operator bound.
- The current `m_z` curve must not be treated as transition evidence.

## 6. Reproduction commands (all verified)

```bash
export PATH="$HOME/.juliaup/bin:$PATH"
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/runtests.jl   # M1 7/7 + M2 T1–T7
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/tied_ad_core_tests.jl   # 38/38 tied-AD tests
julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/m3_hz_tests.jl
```

## 7. Next actions

1. Preserve the M1/M2 accepted work and all bounded M3 failure evidence.
2. Keep M3 marked uncompleted; do not begin M4/M5 from the rejected dense path.
3. In a new session only, consider finite small `h_x,h_z` ground states that can be
   checked against series expansion, and reconsider the phase diagnostic because
   `m_z` did not expose the expected transition.
4. Do not treat the next-session idea as work performed or approved in this session.

## 8. New-session handoff

Read first, in order: `M3_REPORT.md` → `M2_REPORT.md` → `PROGRESS.md` → `PLAN.md` (§6 milestones). M2 remains the last completed milestone and is accepted at step 86. M3 is uncompleted: the dense path is rejected, `m_z` did not diagnose the transition, and the repaired `h_z=0.10` point failed the site-resolved operator-bound audit. Repair artifacts are under `tracks/peps/results/20260730-m3-repair-point-chi6/`; the older invalid curve remains `figures/m3_mz_vs_hz_invalid.svg` only as failure evidence. A new session may investigate small finite `h_x,h_z` values against series expansion, but no such work has started.
