# Attempt 49 protocol — one-shot fresh confirmation of selected `k=15`

Date frozen: 2026-07-29

Parent audited checkpoint: `375e1bf175bc9ba66f862b3b9fb20a1a84734433`

Evidence status before execution: preregistration only

## Purpose

Attempt 44 selected a model-informed principal-global search with `k=15` on
development truths. Attempt 49 asks whether that frozen choice transfers to a
new, disjoint truth set while preserving its deterministic full-cap resource
advantage over both:

1. the same nominal basis completed to `k=40`; and
2. a raw-coordinate global `k=40` search.

This is a single confirmatory run. A pass or failure is retained unchanged.
No method, seed, benchmark rule, metric, or gate may be edited after this
protocol and the runner are committed. An interrupted computation may resume
from an integrity-checked deterministic checkpoint; resumption is not a new
experiment.

## Fresh-truth firewall and fixed benchmark

The benchmark contains exactly 24 truth cells. No cell is screened, excluded,
or replaced:

| Family | Fixed mismatch magnitude | Truth seeds |
|---|---:|---|
| `control-map` | 0.05 | 260641–260648 |
| `drift` | 0.10 | 260641–260648 |
| `combined` | 0.05 | 260641–260648 |

These seeds are disjoint from development `260605–260612` and both earlier
confirmation ranges `260613–260620` and `260621–260628`.

The preregistration validator must not import or construct the simulator and
must not call `make_truth`. Fresh truth may be constructed only by explicit
`--run` mode after the preregistration commit is public and tracked files are
clean. Warm infidelity, reachability, or any exact optimizer outcome cannot
change the benchmark denominator.

## Frozen methods

The implementation is exactly the Attempt-44 principal-global algorithm:

- two global-update cycles;
- central-difference displacement `0.05`;
- 32768 shots per gradient or validation query;
- two 1024-shot sentinels;
- trust radius `0.25`;
- common ridge equal to 10% of the median top-15 positive nominal curvature;
- model and validation confidence `0.995`;
- target infidelity `1e-3`; and
- exact fidelity used only after the black-box client closes.

The three frozen geometries are:

| Method | Search geometry | Full query cap | Full shot cap |
|---|---|---:|---:|
| `model-informed-k15` | top 15 nominal positive-curvature eigenvectors | 66 | 2,099,200 |
| `model-informed-k40` | same 15 plus deterministic nominal complement | 166 | 5,376,000 |
| `raw-coordinate-global-40` | ordered raw coordinates | 166 | 5,376,000 |

The deterministic complement, sign convention, curvature convention, and
ridge are inherited from the source-sealed Attempt 44. No new hyperparameter
is fitted.

## Randomness and pairing

Each truth cell receives four nested finite-shot replicates. The same noise
seed is paired across all three methods:

```text
SeedSequence([113, 49, family_index, truth_seed, replicate])
```

The independent statistical unit is the truth cell, not a nested replicate.

## Outcomes and cost semantics

Primary success is **oracle-scored accepted-incumbent target success**: after
the black-box client has closed, at least one accepted incumbent has exact
infidelity at most `1e-3`. The hidden exact value never changes a calibration
decision. This is not an online target certificate.

The only headline cost is **full-cap online cost**. Every run, including a
success, failure, exception, or non-finite outcome, receives its deterministic
full query and shot cap. Hidden-exact first-hit cost may be stored as a
supplementary diagnostic but cannot support the resource claim.

Nested replicates are averaged within truth cell. The three families receive
equal weight in the pooled macro-average. Pooled intervals and paired method
differences use 20,000 family-stratified truth-cell bootstrap draws with seed
`113049`. Family results are reported descriptively without treating nested
replicates as independent.

For the `k=15` safety outcome, count destructive accepted nonzero steps among
all accepted nonzero steps. Report the one-sided 95% exact Clopper–Pearson
upper bound, which remains positive even when zero destructive events are
observed. Step events are a safety diagnostic; they do not increase the 24
independent truth cells used for performance inference. With no accepted
nonzero step, the safety upper bound is defined as one and cannot pass.

## Confirmation gate

The confirmation passes only if every condition holds:

1. all 24 frozen truth cells and all 288 method/replicate runs are retained;
2. `LCB95` of pooled macro-average `k=15` success is at least 75%;
3. `LCB95(success_k15 - success_model_informed_k40) > -0.10`;
4. `LCB95(success_k15 - success_raw40) > 0`;
5. deterministic full-cap query and shot ratios versus each `k=40` comparator
   are below 0.60;
6. `UCB95` of the `k=15` destructive accepted-step rate is at most 5%;
7. all query/shot ledgers close, paired seeds match, post-hoc values remain
   separated, and all source/manifest integrity checks pass; and
8. no run, exception, or non-finite value is omitted.

The completed-basis comparator tests non-inferiority while using substantially
fewer resources. The raw comparator requires a positive fresh-truth advantage
over an uninformed full-space search. There is no multiple retry, fallback
gate, family subgroup selection, or post-hoc replacement of `k`.

## Exceptions and interruption

An exception, non-finite result, or irrecoverable run is retained as failure
with the method's full cap. It also fails the integrity gate, so an
exception-containing experiment cannot be called a valid confirmation. Seeds
are never replaced.

Before `--run`, a committed manifest seals canonical SHA-256 hashes of this
protocol, the config, runner, and imported frozen dependencies. The runner
records the public preregistration commit and refuses tracked modifications.

An atomic `.partial.json` may record completed runs. Resumption is allowed only
for the same commit, hashes, truth cell, method, and seed. The partial record
cannot change a rule and is replaced by the immutable full result on
completion.

## Required outputs

- full machine-readable result with all 24 cells and 288 runs;
- source, config, protocol, dependency, and preregistration-commit seals;
- pooled macro-average and family success estimates;
- paired truth-cell bootstrap intervals for both success differences;
- deterministic full-cap query and shot ratios;
- destructive-rate, ledger, firewall, and exception checks;
- a concise report and clearly labeled confirmation figure; and
- an explicit `pass` or `fail` that remains unchanged in Attempt 50.
