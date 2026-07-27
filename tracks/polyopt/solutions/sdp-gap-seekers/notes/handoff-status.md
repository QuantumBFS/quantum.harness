# Status — SDP spectral-gap work (post PR #1 merge)

> State of the work after merging Sihan's foundation. For the companion agent /
> team. Branch: `challenge/polyopt-sdp-gap` @ `71a9506`.
> GitHub: `https://github.com/iintSjds/quantum.harness/tree/challenge/polyopt-sdp-gap`

## What just happened

- **PR #1 merged** (merge commit `71a9506`): Sihan's solver-free foundation —
  generic adapter (`GenericGapModel` / `SquareJ1J2Prototype` /
  `LocalSpinIdentities` / `SmallEDOracle`), authoritative spec, 182/182
  solver-free tests pass. The SPEC conflict was resolved by adopting his
  generic-adapter direction over the superseded QMBCertify-reuse v2.
- **Authoritative docs** are now `square-j1j2-gap-sdp-spec.md` (KMS /
  state-polynomial bulk-gap hierarchy from arXiv:2606.03836), plus
  `basis-counts.md` and `local-identities.md`. The cross-check and the older
  SPEC are reconciled to supporting roles.

## Accepted corrections (supersede earlier notes)

1. **Covariance term, not S=1 sector.** Orthogonality is `ω(a†a) − |ω(a)|²`, not
   a fixed S=1 excitation block. My earlier SPEC §4 / crosscheck A.2 was wrong;
   corrected in the merged docs.
2. **B1–B4 identities are regression tests**, not tightening constraints — in a
   complete Pauli quotient they are already implied by the reducer. Tightening
   needs projector/RDM positivity.
3. **Finite patch = local-consistency window**, not a PBC torus.
4. **Solver outcomes:** feasible / infeasible / unknown — timeout or numerical
   failure is never "infeasible".

## Strategic recommendation (team decision pending)

Convergence data from the other session: energy cert (0.17% @ L=4) is far
cheaper than gap cert (~74% at the same relaxation). Two-track hedge:

- **Floor (guaranteed strong result):** energy-cert deliverable (#124) — 0.17%
  2D square result is nearly paper-ready; add the contested Shastry–Sutherland
  g≈0.8 point.
- **Stretch (paper-worthy if it lands):** gap-SDP assembly — covariance term +
  structured basis + solver. Do not bet the deliverable on it.

## Next gates (no certified gap number exists yet)

1. Freeze the structured Square basis + SHA-256 fingerprint.
2. Snapshot legacy Ising/Kagome basis + affine inventories; compare coefficient
   by coefficient against the generic adapter. *(in progress — assistant
   producing the static inventory spec + a remote-ready dump script, no local
   solver run)*
3. Implement the covariance term + moment/gap matrices (the actual new code).
4. g=0 Shastry–Sutherland calibration (Δ_bulk = 1 exact) — labels solver flag
   semantics.

## Calibration anchor

**Shastry–Sutherland g=0, Δ_bulk = 1 exactly** (product of singlets). Any solver
run must recover Γ → 1; whichever side of 1 the finite-(L,d) value sits on
labels OPTIMAL/INFEASIBLE for the rest of the week.

## Artifacts (on the branch at `tracks/polyopt/solutions/sdp-gap-seekers/`)

- `src/` — `GenericGapModel.jl`, `SquareJ1J2Prototype.jl`,
  `LocalSpinIdentities.jl`, `SmallEDOracle.jl`
- `square-j1j2-gap-sdp-spec.md` (authoritative), `basis-counts.md`,
  `local-identities.md`, `spectralgap-refactor-plan.md`, `validation-report.md`
- `notes/` — `theory-problems-for-offloading.md` (the questions),
  `theory-problems-offloading-crosscheck.md` (reconciled),
  `certify_Heisenberg_square_gap_SPEC.md` (reconciled), `handoff-status.md`
- `test/runtests.jl` (182 checks), `scripts/` (3 solver-free scripts)

## What is NOT done (do not over-claim)

- No SDP assembled or solved; **no certified Square J1-J2 bulk-gap number**.
- Covariance term / moment matrices / symmetry blocking: unimplemented.
- feasible/infeasible/unknown handling under real solver responses: untested.
- Infeasibility-witness extraction / rational/interval validation: unimplemented.
