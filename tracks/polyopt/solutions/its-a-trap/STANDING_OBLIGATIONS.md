# STANDING OBLIGATIONS — EXHAUSTIVE ACTIVE WHITELIST
(arbiter-issued Wed ~15:45. This list is the only source of executable
work. Anything not listed is ARCHIVED and must not be executed, refreshed,
or used as a trigger for new work. Completed provenanced evidence from
archived routes remains available for the final report. Do not reconstruct
obligations from PLAN_HISTORY.md, HISTORY.md, ROUTE_A_ACTIVE.md, old tower
plans, or archived scheduling documents.)

## TONIGHT

1. JOINT critical path only: G1 → G2 → G3 → G4 → 22:00 status → 00:15
   method freeze / arbiter decision → 01:00 N=200 build probe and ONE
   base/joint pair, or kill switch. G1b, G1c, G2 soundness, G3 freeze, or
   G4 ordering failure blocks N=200.
2. v200hi passive verdict: valid row gap ≤ 1e-5 → Target 1 met under that
   configuration; valid row gap > 1e-5 → numerical miss; OOM/timeout/
   invalid residual/missing row → resource frontier, NOT a numerical miss.
3. Conditional T1L: submit only if (a) v200hi valid numerical miss,
   (b) construction probe passes, (c) no delay/resource conflict with the
   JOINT G1–G4 path, build probe, or N=200 pair — conflict ⇒ new explicit
   arbiter GO. One row only; no follow-up family.
4. Passive harvest only: e49p0v2; already-submitted 2D 10×10 cells;
   already-submitted DMRG/Target cells; fline artifacts if they appear.
   Ingested and audited; they trigger no new jobs.
5. PLAN.md cleanup at the next green-gate commit: ≤10-line pointer
   (LAW.md = law; rg_selection/PLAN_OF_RECORD.md = sole active method
   plan; this whitelist = sole active task list; everything else archive).

## CUT TONIGHT
No Route-A arbitration / r* / A3 / A4; no new reach cells; no reach-table
generation before Thursday; no tower scaling; no plan-history maintenance;
no memory-note rewriting; no new experiment families; no architecture
redesign.

## THURSDAY

6. Freeze and harvest: fetch+merge existing SCNet results; rerun only
   already-defined red cells when explicitly justified; every table from
   CSV; freeze numerical data.
7. Minimal audit package: gates.json, training.csv, holdout.csv,
   FROZEN_SELECTION.json, provenance.csv, claims_ledger.md, git diff +
   commit list.
8. Codex audit scope: unsupported claims; provenance gaps; terminology
   violations; numerical-ordering violations; holdout leakage;
   coefficient-space/model-signature mismatches; other correctness or
   soundness failures. GO or NO-GO only; no new features/experiments/
   architecture.
9. Finalization: preview outward-facing content to the user; update
   PR #193; final push before Thursday 20:00.
