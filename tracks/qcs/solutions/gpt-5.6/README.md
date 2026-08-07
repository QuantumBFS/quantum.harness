# gpt-5.6 — Challenge 113: Sim-to-Real for Quantum Gates

This is the human entry point for our Challenge 113 submission.

## Team

| | |
|---|---|
| **Team name** | gpt-5.6 |
| **Members** | Hongye Tang, Yizhou Wei, Hao Wu |
| **Challenge** | [#113 Sim-to-Real for Quantum Gates](https://github.com/QuantumBFS/quantum.harness/issues/113) |
| **Track** | `qcs` |

## Result in one paragraph

On a preregistered synthetic two-qubit CNOT benchmark with 40 pulse
parameters, calibrating only the 15 active model-Hessian directions achieved
90.625% fresh-truth success at a fixed 66-query online cap. A matched
40-dimensional model-informed search achieved 25%, and raw-coordinate
40-dimensional search achieved 0%, each at 166 queries. The result supports a
bounded local claim: simulator-informed low-rank geometry can reduce
finite-shot calibration cost when model mismatch remains inside a transferable
response span. This is synthetic evidence, not real-hardware calibration.

## Start here

1. Open [`core-sim-to-real/final/report.html`](core-sim-to-real/final/report.html).
   It is a standalone offline report written for human readers, with the
   Challenge, Approach, Results, and Highlight sections required by the
   organizer's `challenge-report` workflow.
2. Read [`EVIDENCE_MATRIX.md`](EVIDENCE_MATRIX.md) for a one-page mapping from
   every official deliverable to its artifact, verification command, evidence
   level, and claim boundary.
3. Read [`core-sim-to-real/docs/FINAL_REPORT.md`](core-sim-to-real/docs/FINAL_REPORT.md)
   for the numerical interpretation and honest negative results.
4. Read [`core-sim-to-real/docs/REPRODUCIBILITY.md`](core-sim-to-real/docs/REPRODUCIBILITY.md)
   for exact environments and reproduction commands.

The report embeds all three headline figures and has no external assets.

## What we built

The primary package, `core-sim-to-real/`, implements the requested three-stage
pipeline:

1. optimize a pulse in a differentiable nominal simulator;
2. extract the active Hessian subspace; and
3. calibrate a mismatched finite-shot device through a counted scalar
   `query(parameters, shots)` interface, without exposing device gradients,
   Hamiltonians, exact fidelity, or random state to the online controller.

The independent `robustness/` package reconstructs a rank-five
perfect-blockade neutral-atom CZ geometry and maps when a fixed low-rank
subspace transfers, rotates, or fails because a new physical response channel
appears. Its statistics are not pooled with the CNOT benchmark.

## Headline evidence

| Method | Search dimension | Fresh success | Fixed online queries | Fixed online shots |
|---|---:|---:|---:|---:|
| model-informed | 15 | 90.625% | 66 | 2,099,200 |
| completed model-informed | 40 | 25.00% | 166 | 5,376,000 |
| raw-coordinate | 40 | 0.00% observed | 166 | 5,376,000 |

There are 24 independent truth cells and four nested shot-noise replicates per
cell. Uncertainty is resampled at the truth-cell level within mismatch
families. The post-hoc restricted-mean queries-to-target values are 48.76,
160.63, and 166; they are benchmark scores, not an online stopping
certificate.

## Exploratory optimizer comparison

After freezing the confirmation result, we also tested whether noisy Bayesian
optimization (BO), or BO followed by one Hessian-preconditioned local update,
could reduce measurements. This separate development comparison used 12 new
synthetic CNOT truth cells, two finite-shot replicates per cell, one
online-selected terminal pulse per run, and seven frozen methods:

| Method | Queries | Shots | Terminal success |
|---|---:|---:|---:|
| one-cycle principal-global | 34 | 1,050,624 | 62.50% |
| two-cycle principal-global | 66 | 2,099,200 | **95.83%** |
| sequential quadratic scan proxy | 66 | 2,099,200 | 50.00% |
| BO-32 | 34 | 1,050,624 | 0.00% |
| BO-64 | 66 | 2,099,200 | 4.17% |
| BO16 then one local cycle | 50 | 1,574,912 | 45.83% |
| BO32 then one local cycle | 66 | 2,099,200 | 83.33% |

Thus this BO implementation did not retain performance at reduced query/shot
budgets and does not replace the headline method. The full-budget hybrid was
12.50 percentage points below the two-cycle local baseline (paired
truth-cell bootstrap 95% interval `[-25.00, 0.00]`). Complete exploratory
code, raw results, plot, audit notes, and claim boundaries are preserved at
[commit `d2d06ff`](https://github.com/thy10817/quantum.harness/tree/d2d06ff13710c3a1f9c6b872296ee69b1bf218e7/tracks/qcs/solutions/gpt-5.6/core-sim-to-real).
This is a 15-dimensional synthetic-CNOT method screen, not a direct test of
the paper's ten-dimensional ytterbium experiment and not confirmation
evidence.

## Verify before believing

From this solution directory, the standard-library closure audit checks the
explicit file manifest, forbidden paths, source seals, archived results,
report structure, link closure, dependency separation, and the independent
robustness comparison:

```bash
python tools/validate_team_package.py --strict-closure
```

Expected output:

```text
team package pass; checks=27/27; files=109
```

For an independent numerical audit of the primary result:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r core-sim-to-real/requirements.txt

python core-sim-to-real/code/attempt50_result_audit.py --verify-only
python core-sim-to-real/code/attempt51_queries_to_target.py --verify-only
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
python -m unittest core-sim-to-real/tests/test_final_contract.py
python core-sim-to-real/run_challenge.py --mwe
```

The MWE writes to a new ignored output directory and retains every query row.
It verifies the software and ledger contract; it is not a second independent
confirmation. The two numerical packages require separate environments, as
documented in [`TEAM_SUBMISSION_PLAN.md`](TEAM_SUBMISSION_PLAN.md).

## What failed and what we do not claim

- The proposed online early-stop certificate failed and is not used.
- Adding 25 nominally flat directions consumed queries and reduced success.
- Large subspace rotation and new leakage channels can invalidate a fixed
  low-rank loop.
- The unconditional statement `rank(H) = d² - 1` is rejected; the supported
  cross-size result is conditional on controllability, accessibility, and
  convergence.
- We do not claim real hardware, calibrated cesium performance, 96 independent
  devices, a universal mismatch threshold, or a universal scaling law.

The full claim firewall and non-comparable quantities are recorded in
[`TEAM_SYNTHESIS.md`](TEAM_SYNTHESIS.md). The submission remains an open pull
request so teammates can review and amend it before any final merge decision.
