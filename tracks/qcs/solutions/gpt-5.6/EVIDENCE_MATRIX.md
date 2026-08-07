# Challenge 113 evidence matrix

Status: validated core-plus-robustness fallback
Date: 2026-07-29

This page maps every requested Challenge-113 deliverable to its primary
artifact, verification route, evidence level, and claim boundary. It is the
fastest entry point for judges, teammates, and review agents.

The challenge explicitly permits a query-only device built in software.
Real-hardware calibration is a bonus and is not claimed here.

## Deliverable closure

| Official deliverable | Primary artifact | Verification | What the evidence supports | Boundary |
|---|---|---|---|---|
| 1. Reproducible three-stage pipeline with a strict differentiable-model / query-only-device boundary | `core-sim-to-real/run_challenge.py`, `core-sim-to-real/code/phase3_common.py`, `core-sim-to-real/final/run.json` | `run_challenge.py --mwe`; complete MWE ledgers; archived formal run 288/288 | Nominal optimization, Hessian-subspace extraction, and finite-shot derivative-free calibration are connected through a counted scalar device interface | Synthetic CNOT only; device internals are hidden from the optimizer but remain available to the post-hoc evaluator |
| 2. Queries to target versus search dimension, with baselines and uncertainty | `core-sim-to-real/final/queries-to-target.png`, `core-sim-to-real/results_summary/QL1F-attempt51-queries-to-target.json` | Attempt 51: 11/11 | Development sweep covers `k=5,10,15,20,40`; fresh comparison gives post-hoc first-hit indices 48.76, 160.63, and 166, while the deployable fixed online caps are 66 versus 166 queries | First-hit values use post-hoc exact scoring and are not an online stopping certificate |
| 3. Failure mode versus model–truth gap and whether extra/adaptive directions help | `core-sim-to-real/final/gap-and-invariant.png`, `robustness/comparison/figs/fig03_failure_map.png`, `robustness/comparison/summary.json` | Attempt 52: 22/22; fresh robustness comparison: 3,951 numerical plus 402 categorical fields, zero mismatches | Historical development curves show gap-dependent degradation; the independent CZ scan shows orientation-dependent and out-of-span failure; the fresh completed-`k=40` safety margin adds 25 directions but performs worse than `k=15` | Exploratory mechanism evidence, not a precise universal failure threshold; no new Attempt-49 gap sweep and no validated adaptive subspace re-estimation |
| 4. Invariant check across at least two system sizes | `core-sim-to-real/results_summary/QL1F-attempt52-gap-invariant-audit.json`, lower-right panel of `gap-and-invariant.png` | Attempt 52 source/artifact audit: 22/22 | At sufficiently converged controllable points, accessible phase-blind endpoint-error channel rank equals local Hessian rank; observed pairs include `d=2: 3/3`, `d=3: 8/8`, and `d=4: 15/15` | Conditional local mechanism; not a universal resource-scaling theorem and not proof that every ansatz has rank `d^2-1` |
| 5. Short report plus an honest failed case | `core-sim-to-real/final/report.html`, `core-sim-to-real/final/report.json`, `robustness/comparison/figs/fig08_pathology_gallery.png` | Final HTML contract: 7/7 | Four-section offline report contains the successful comparison, the failed online stopping certificate, strong-gap degradation, and out-of-span pathologies | No hardware, cesium, or population-wide claim |

## Headline comparison

The preregistered fresh confirmation contains 24 independent truth cells and
four nested shot-noise replicates per cell:

| Method | Search dimension | Fresh success | Fixed online queries | Fixed online shots |
|---|---:|---:|---:|---:|
| model-informed | 15 | 90.625% | 66 | 2,099,200 |
| completed model-informed | 40 | 25.00% | 166 | 5,376,000 |
| raw-coordinate | 40 | 0.00% observed | 166 | 5,376,000 |

Uncertainty is resampled at the truth-cell level within mismatch families,
not across 96 independent devices. The raw-method empirical bootstrap interval
is degenerate at `[0,0]` because every observed cell and resample fails; it is
not a strict confidence interval asserting zero population success
probability.

## Reproduction gates

Run from the extracted candidate root:

```bash
python tools/validate_team_package.py --strict-closure
python core-sim-to-real/code/attempt50_result_audit.py --verify-only
python core-sim-to-real/code/attempt51_queries_to_target.py --verify-only
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
python core-sim-to-real/tests/test_final_contract.py
python core-sim-to-real/run_challenge.py --mwe --output <new-empty-dir>
```

The team validator is standard-library only and also recomputes the complete
archived-versus-fresh robustness scientific comparison. The MWE requires the
pinned core numerical environment and must write outside the candidate.

## Claim firewall

Authorized:

> In two independent synthetic models, a simulator-derived active
> fidelity-Hessian subspace can reduce finite-shot calibration cost when the
> device mismatch stays inside a transferable response span. Strong subspace
> rotation or a new response channel can invalidate the fixed subspace.

Not authorized:

- real-hardware or cesium validation;
- an online first-hit stopping certificate;
- 96 independent devices;
- pooled statistics across the CNOT and neutral-atom models;
- a universal `d^2-1` or resource-scaling theorem;
- an exact universal failure value of the mismatch parameter;
- describing the optional paper workspace as a complete experimental
  reproduction;
- using the optional Cs/Rb platform as real-device calibration evidence.

## Submission decision

The default official candidate is `core-sim-to-real/ + robustness/`. The
public `reproduce/` workspace and Cs/Rb platform remain optional follow-up
work. The reconstruction passed isolated code tests but contains no author raw
experimental observations and retains validation/licensing closure work. The
platform passed its local regression after a clean-clone checksum correction
but is not calibrated to real Cs hardware. Neither enters the default
candidate or its statistical evidence.
