# Challenge #50 — Anyon Correlators from PEPS: Final Summary (Uncompleted, Time Limit)

> **Status: M3/6 — uncompleted at the challenge deadline.** Milestones M0–M2 passed;
> M3 (finite-field ground states) is diagnosed but not accepted; M4–M6 not started.
> This file is the readable record of the whole attempt: what was built, what
> worked, what failed and why, and the concrete next steps.
>
> Challenge: [issue #50](https://github.com/QuantumBFS/quantum.harness/issues/50) ·
> PR: [#185](https://github.com/QuantumBFS/quantum.harness/pull/185) ·
> Branch: `challenge/peps-anyon-correlator` ·
> Code: `tracks/peps/solutions/anyon-correlator/` ·
> Data (local only, gitignored): `tracks/peps/results/`

## 1. Goal and where the attempt stopped

Goal: an iPEPS workflow that computes anyon correlators Cₑ(r), Cₘ(r) of the 2D
toric code in magnetic fields,

    H = −Σ_s A_s − Σ_p B_p − hₓ Σᵢ Xᵢ − h_z Σᵢ Zᵢ ,   J = 1,

extracts correlation lengths ξₑ, ξₘ from ordinary and flux-twisted double-layer
transfer operators, and tracks them across the field-driven anyon-condensation
transition (h_z,c ≈ 0.3285 on the (0, h_z) axis).

Stopped at: **M3 of 6** — finite-field ground-state continuation. No anyon
correlator was reached. The blockers are understood (Section 5) and the next
run is prepared but unexecuted (Section 6).

## 2. Milestones

| M | Content | Status |
|---|---|---|
| M0 | Julia tensor stack | **passed** 2026-07-27 |
| M1 | Hamiltonian + 2×2 ED unit test | **passed** 2026-07-28 |
| M2 | h=0 ground state from a random tensor | **passed** 2026-07-30 |
| M3 | finite-field ground states along (0, h_z) | **uncompleted** (diagnosed) |
| M4 | phase-line check | blocked by M3 |
| M5 | anyon spectra/correlators | not started |
| M6 | handoff | this summary |

## 3. What works (accepted results)

- **M0.** Julia 1.12.6 (juliaup, NJU mirror); TensorKit 0.16.5 + PEPSKit 0.8.0 +
  MPSKit 0.13.12 in `julia-env`. TensorKit 0.16 layout conventions recorded in
  `PROGRESS.md` §3.
- **M1.** Toric-code Hamiltonian as a PEPSKit `LocalOperator` on a (2,2)
  composite cell (vertex + E,N edges, 8 edge spins). 2×2-torus ED: **7/7 gates**
  in 1.5 s — E₀ = −8, degeneracy 4, gap 4, all ground states stabilized to
  1e-15, self-duality 1e-14, large-field windows. `scripts/ed_checks.jl`,
  `tests/runtests.jl`.
- **M2.** From a **random dense D=2 tensor** (one tensor tied across the (2,2)
  cell), fixed-point-AD optimization with tied-gradient projection and
  normalized Armijo descent reached the exact h=0 ground state:
  **E_cell = −7.999999995072 (E/N = −0.999999999384)**, max star/plaquette
  errors 5.95e-10/6.38e-10 at χ=8; fresh-environment repeat differs by 6.49e-9
  (finite-χ sensitivity, documented). The exact X-basis-copy tensor is a
  separate zero-gradient benchmark. `M2_REPORT.md`.
- **Machinery validations** (all pass): exact state → CTMRG E_cell = −8 and
  stabilizers = 1 to 2e-16; AD gradient finite-difference exact; SU gates exact;
  normalization conventions verified. 132/132 M3 tests, 94/94 M1/M2 tests,
  38/38 tied-AD tests.
- **Simple-update study** (`M2_SU_FINDINGS.md`): random-init full-circuit SU
  stalls at non-ground fixed points (mean-field truncation + star/plaquette
  competition); stage-wise SU and product init reach −8 exactly.

## 4. M3 attempts and the two diagnosed blockers

M3 was attempted three times with increasing diagnostic discipline.

**Attempt 1 — dense continuation grid, χ=4/6 (rejected).** An 11-point grid to
h_z = 0.5 completed mechanically but AD accepted no update at five points;
m_z plateaued at 0.061 with no transition feature; stabilizers overshot the
Pauli bound by up to 0.024. The curve is retained only as failure evidence
(`figures/m3_mz_vs_hz_invalid.svg`).

**Attempt 2 — branch-consistent repair point (failed audit).** Repairing the
line search so gradient, energy, and Armijo trials share one warm CTMRG branch
gave smooth descent at h_z = 0.10 (gradnorm 0.197 → 0.065 in 4 steps), but the
independent three-seed audit failed: `max|⟨B_p⟩| = 1.000171798 > 1 + 1e-6`, a
finite-χ=6 contraction bias.

**Attempt 3 — series-validation pilot (this session, diagnosed).** A new
ratified protocol: continue the accepted M2 tensor to small fields and compare
against the hₓ=0 perturbative series (arXiv:0807.0487 Eq. 8, converted to
J = 1):

    e_series(h_z) = −1 − h_z²/4 − 15 h_z⁴/64 − 147 h_z⁶/256 − 18003 h_z⁸/8192
    per edge spin;  e(0.05) ≈ −1.0006264739,  e(0.10) ≈ −1.0025240337.

Driver `scripts/m3_series_validation.jl` (65/65 focused tests), artifacts
`tracks/peps/results/20260730-m3-series-pilot-chi8*/`. Protocol: tensor-only
continuation, no optimizer state across fields, per-point frozen-tensor audit
(warm + fresh deterministic + two fresh random CTMRG initializations at the
same χ/tol, plus a χ=16 stability check), acceptance only on stationary
optimizer + branch-consistent energies/observables + χ stability.

Results:
- **h_z = 0 anchor: ACCEPTED.** E/N = −1.0000000002, δ vs series −1.95e-10,
  4/4 initializations consistent (spread 8.1e-10), χ 8→16 stable. The audit
  machinery itself is validated.
- **h_z = 0.05 and 0.10: NOT ACCEPTED — contraction-ambiguous.** The warm
  CTMRG branch ran away to a trivial factorizing fixed point during
  optimization (claimed E/N → −1−h_z with unphysical ⟨A_s⟩, ⟨B_p⟩ > 1), while
  fresh contractions of the same frozen tensors agree among themselves
  (~1e-13) at much higher, physical energies (−0.9558 and −0.9225 per spin).
  Inter-branch spread 9.4e-2 and 1.8e-1 per spin → `energy_disagreement`.

## 5. Current problems and their causes

**Problem A — warm-branch artifact descent (root blocker).** With
warm-started CTMRG trials at α₀ = 0.05, the optimizer "descended" from step 3
at h_z = 0.05 into energies below the exact series, ending at the algebraic
floor −8−8h_z with stabilizers > 1 — impossible for any state. Per-step
re-contraction of every checkpoint
(`inspection/series_branch_divergence.jl` → `branch_divergence_0p05.csv`)
shows: steps 1–2 are branch-consistent and correctly variational; from step 3
the fresh-contracted (true) energy *rises* monotonically to −7.65/cell while
the warm branch claims descent to −8.40/cell.
*Cause:* the physical energy scale is tiny (~5e-3/cell); large normalized
steps let the continuously tracked environment fall into a trivial
factorizing CTMRG basin, and the fixed-point-AD gradient through that branch
then points downhill on the artifact surface. Branch-consistent optimization
(the Attempt-2 repair) makes the objective self-consistent but cannot detect
the branch itself going non-variational; only independent contractions can.
This same mechanism plausibly explains Attempts 1–2 at χ = 4/6.

**Problem B — warm-trial fragility at small steps.** Retrying with α₀ = 0.005
and fresh-verified acceptance (amendment A1) made every accepted step
branch-consistent (~1e-7), but the warm-carried trial environment then failed
to converge for perturbations α ≥ 0.005, collapsing Armijo to α ~ 1e-4 —
~7e-6 per step against the required 5e-3, guaranteeing budget exhaustion.
*Cause:* the warm environment carried across tensor perturbations is the
fragile element; fresh from-scratch contractions of the same trial tensors
converge robustly (residual ~1e-8).

**Underlying susceptibility (hypothesis).** The dense D=2 tied ansatz has no
virtual-ℤ₂ constraint; in the deformed-tensor region its transfer matrix is
near-defective, so CTMRG has multiple basins (physical vs trivial) and fresh
seeds sometimes fail outright (residual ~0.4) or land on different branches.
χ=8 is adequate only near the exact h=0 state.

## 6. Prepared next steps (not executed at the deadline)

1. **Amendment A2 — implemented and unit-tested, unexecuted.** Every Armijo
   trial is now a from-scratch deterministic (seed 424242) contraction, with
   an independent fresh random-seed (seed 1) veto per accepted step; the final
   multi-initialization + χ=16 audit is unchanged. Commands:

   ```bash
   julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/m3_series_tests.jl
   julia --project=julia-env tracks/peps/solutions/anyon-correlator/scripts/m3_series_validation.jl pilot \
     tracks/peps/results/20260730-m2-chi8-warm-continue-77-to100/random-continue_step086.jld2 \
     tracks/peps/results/<new-run-dir> 8 16 50 0.005
   ```

2. If h_z = 0.05 is accepted: re-enable h_z = 0.10 (currently deferred —
   `SERIES_PILOT_GRID = [0.0, 0.05]`), then the 10–20 point scan to h_z = 0.2
   with series comparison per the ratified protocol.
3. If the deterministic-branch objective still fails: optimize at χ = 16
   (χ_check = 32), or move to the virtual-ℤ₂-symmetric ansatz (PLAN C7) which
   is required for M5 anyway.
4. M4–M5 remain: phase-line window vs h_z,c ≈ 0.3285, then ordinary/twisted
   transfer-operator spectra, form-factor-selected anyon eigenvalues, and
   ξₑ(h), ξₘ(h) (PLAN §3, §6).

## 7. Repository map

- `PLAN.md` — living plan, conventions C1–C10, symmetry architecture, milestones.
- `PROGRESS.md` — session-by-session status and reproduction commands.
- `M2_REPORT.md`, `M2_SU_FINDINGS.md`, `M3_REPORT.md` — milestone evidence.
- `scripts/` — `tc_peps.jl` (shared conventions), `ed_checks.jl` (M1),
  `ad_tied_core.jl` + `ad_tied_gd.jl` (M2 optimizer),
  `m3_hz_continuation.jl` (M3 attempts 1–2, superseded),
  `m3_series_validation.jl` (M3 attempt 3, current protocol).
- `tests/` — `runtests.jl` (94/94), `tied_ad_core_tests.jl` (38/38),
  `m3_hz_tests.jl` (132/132), `m3_series_tests.jl` (69/69).
- `inspection/` — diagnostic probes including `series_branch_divergence.jl`.
- Results (local, gitignored): `tracks/peps/results/20260730-m3-series-pilot-chi8/`
  (pilot 1 + divergence map), `...-chi8-a005/` (pilot 2, budget-exhausted).
