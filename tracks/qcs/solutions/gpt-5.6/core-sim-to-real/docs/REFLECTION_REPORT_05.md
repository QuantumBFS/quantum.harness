# Reflection report 05 — Attempts 41–50

Date: 2026-07-29

## Executive decision

The core synthetic-CNOT direction was worth continuing and has now reached a
credible stopping point. Attempt 49 independently confirms the selected
`k=15` model-informed geometry on a frozen holdout benchmark. Further tuning
on the same truths would reduce credibility rather than add useful evidence.

The right next step is integration with the teammates' reproduction and
platform-simulator work, not another local hyperparameter sweep.

## What survived

The strongest mechanism is not a generic claim that fewer coordinates are
always better. It is more specific:

1. the nominal CNOT Hessian exposes 15 positive-curvature directions;
2. the same principal-global update in those 15 directions is robust under
   the tested finite-shot mismatch families;
3. deterministically completing that basis to 40 dimensions injects noisy,
   nominally flat directions into the same trust-region update; and
4. the wider search is both more expensive and less successful.

This explanation survived development selection, a separate preregistration,
a fresh-truth confirmation, an independent statistical reconstruction, and a
complete public replay.

## Formal confirmation

Attempt 49 retained 24 truth cells, four nested finite-shot replicates per
cell, and three frozen methods: 288 runs with no exception.

| Method | Success | Truth-cell bootstrap 95% interval |
|---|---:|---:|
| model-informed `k=15` | 90.625% | [81.25%, 97.92%] |
| completed model-informed `k=40` | 25.00% | [12.50%, 37.50%] |
| raw-coordinate `k=40` | 0.00% | [0.00%, 0.00%] |

The paired `k=15 - completed k=40` advantage is 65.625 percentage points,
with lower 95% bound 51.04 points. The paired advantage over raw `k=40` is
90.625 points, with lower bound 81.25 points.

The `k=15` deterministic full-cap ratios are:

- queries: `66 / 166 = 0.397590`;
- shots: `2,099,200 / 5,376,000 = 0.390476`.

There were zero destructive accepted steps among 165 accepted nonzero
`k=15` steps; the one-sided exact 95% upper bound is 1.799%.

All six preregistered gates passed.

## Important failures that remain part of the result

### Online stopping

Attempt 43 showed that the proposed online target certificate was not an
acceptable cost-saving rule. It missed exact successes and its cost upper
bound exceeded the frozen threshold. Therefore the final resource headline
is the deterministic full cap, not observed online queries-to-target.

### Cross-dimension invariant

The tested dimension-general construction did not confirm a universal
`d^2-1` rank/resource law. The d=4 representative rank was below 15 and raw
baselines were often warm successes, making query ratios uninformative. The
attempt was correctly falsified rather than repaired post hoc.

### Platform-adaptive route

The perfect-blockade neutral-atom adapter passed scalar-oracle interface
checks and produced meaningful out-of-subspace stress labels. A frozen
32-direction residual sketch nevertheless reached the target in 0/4 seeds on
both positive scenarios. No finite-shot platform claim was authorized.

## Audit lessons

1. **Preregistration mattered.** The fresh seeds, methods, gates, pairing, and
   exception rules were public before truth construction.
2. **Truth cell is the statistical unit.** Four shot-noise replicates improve
   within-cell estimation but do not create 96 independent devices.
3. **Cost semantics must be named.** Full cap, online stopping cost, and
   post-hoc oracle first hit answer different questions.
4. **Source seals need byte-level care.** Line-ending normalization and
   harmless-looking Markdown whitespace can invalidate provenance.
5. **Compact evidence has a cost.** Formal query ledgers were reduced to
   aggregate closure plus hashes. Attempt 50 keeps complete MWE rows so a
   reviewer can inspect the actual query contract.
6. **Metadata labels matter.** The drift-only sampled control-map norm is now
   explicitly documented as unapplied.

## Direction assessment

### Value

Yes. The result directly addresses the Challenge-113 core idea: a
differentiable simulator supplies a low-dimensional geometry that makes a
noisy query-only device loop materially more effective. The completed-basis
comparison is especially useful because it controls more tightly for
optimizer choice than an unrelated raw baseline.

### Probability of successful defense

High for the bounded claim:

> On the frozen 40-parameter synthetic CNOT benchmark, a simulator-informed
> `k=15` principal-global search has substantially higher fresh-truth success
> and about 39% of the fixed two-cycle resource cap of the tested `k=40`
> searches.

Low for stronger claims about hardware, cesium, universal scaling, or an
online stopping advantage. Those claims are excluded.

### What could still add value

- Connect the team's cesium/platform simulator through the audited scalar
  oracle interface without retuning on the existing stress cases.
- Compare the teammate paper reproduction with the observed noisy-complement
  failure mechanism.
- If real device access becomes available, preregister a separate hardware
  protocol rather than treating it as an extension of the synthetic holdout.

## Final stop rule

The core direction stops after Attempt 50 packaging. No more result-dependent
changes to `k`, methods, holdout seeds, or gates are allowed. Any future
scientific extension must declare a new benchmark and a new protocol.

Attempt 51 is not a scientific extension: it makes no device or simulator
query. It was added during final issue-compliance review to expose the
requested queries-to-target versus dimension plot from already sealed
Attempts 44 and 49. Its post-hoc scoring and failed online-certificate
boundary are explicit.
