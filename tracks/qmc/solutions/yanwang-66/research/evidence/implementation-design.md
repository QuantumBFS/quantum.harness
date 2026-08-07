# Baseline implementation design

Status: survey-stage design, not yet a validated implementation.
Model authority: `MODEL.md` v1.0.

## Why this representation

The benchmark needs all of the following at once:

- a circuit-derived rotated-code geometry;
- per-shot dynamic loss/reload history;
- loss-conditioned decoding rather than a decorative mask;
- counter-addressed exogenous randomness shared across policies;
- enough throughput for millions of shots.

Generating and compiling a different full Stim circuit for every shot is correct in principle but too expensive, while a single fixed no-loss circuit cannot represent persistent vacancies. The baseline therefore uses Stim to derive the ideal rotated-code checks and logical support, then builds the corresponding graph-like space-time detector model directly. This is equivalent to the round-level direct-stabilizer/MPP model frozen in `MODEL.md`; it is not presented as a native Rydberg gate schedule.

## Package boundaries

```text
reload_qec.geometry   Stim-derived sites, checks, logical support
reload_qec.rng        stable counter-addressed uint64 generator
reload_qec.policy     none/immediate/periodic/threshold state machine
reload_qec.graph      space-time edges and erasure-conditioned weights
reload_qec.simulate   shot scheduling, sampled faults, detector arrays
reload_qec.decode     cached PyMatching graphs and logical predictions
reload_qec.schema     manifest, NPZ shards, input/label separation
reload_qec.stats      Wilson intervals, paired differences, FDR
reload_qec.cli        simulate, verify, aggregate, export-inputs
```

Imports point inward: CLI/schema may call simulation and decoding; physics modules never import result/report code. The validator has an independent fixture oracle and does not import candidate implementation modules.

## Counter-addressed randomness

Every Bernoulli or categorical event is a pure function of:

```text
(master_seed, shot_id, round, site_id, event_type, subindex)
```

A documented SplitMix64-style mixer produces uint64 values; conversion to uniform floats uses the top 53 bits. Event IDs are fixed in the schema. Data-error occurrence/type, measurement error, loss, loss Pauli component, reload reset, and reload success use different event IDs.

The simulator computes an event even when the current policy makes the site inactive, but suppresses its physical application. It never consumes a sequential RNG stream. Sharding, policy order, batching, and process count therefore cannot change a shot.

## Policy state arrays

For each shot/site, maintain `ACTIVE`, `LOST_UNDETECTED`, `LOST_DETECTED`, or `RELOADING`, plus an absolute completion boundary. At round `t`:

1. resolve completions due at boundary `t`;
2. store `missing_mask[t]`;
3. sample loss for active carriers;
4. expose the newly lost carrier to the current round’s circuit rule;
5. reveal loss after the measurement boundary;
6. request reload from history available through `t`.

`L_reload=0` schedules completion at boundary `t+1`; `L_reload=k` completes at `t+k+1`. This makes ideal `immediate` and `periodic(1)` identical by construction. Reload attempts, successes, failures, and reset errors are distinct arrays.

## Circuit-derived spatial edges

For memory-X, relevant Z faults terminate on X checks; for memory-Z, relevant X faults terminate on Z checks. For each data site and relevant check family:

- support in two checks: a spatial edge between those detectors;
- support in one boundary check: a detector-to-boundary edge;
- `fault_id=0` iff the site intersects the exported logical support.

The relevant component of a single-qubit depolarizing error occurs with probability `2p/3`, hence base spatial weight

```text
w_data = log((1-2p/3)/(2p/3)).
```

The implementation must cross-check the no-loss graph against Stim’s detector error model on `d=3` and `d=5`; disagreement is a validator failure, not an approximation warning.

## Time edges

For each measured check and round, a measurement flip connects the check detector at adjacent time boundaries with

```text
w_measurement = log((1-p_m)/p_m).
```

Initial and final boundary conventions are exported in the instance schema. Raw syndrome history is the cumulative XOR of detection events and is reconstructed only after graph incidence is fixed.

## Loss conditioning

A newly lost data carrier samples one relevant Pauli component with probability `1/2`. From the loss round until successful reload, each corresponding spatial edge is available to the decoder at weight zero. This is the matching-graph form of known erasure/super-stabilizer contraction.

An unavailable ancilla makes the associated measurement edge weight zero and marks the raw measurement invalid. Fixed-shape output stores placeholder zero only with `syndrome_valid_mask=0`.

The matching graph is keyed by the complete revealed erasure/reload history and cached. Cache keys include `d,T,basis,p,p_m` and the packed data/ancilla mask; they never include labels or sampled Pauli outcomes.

## Fault sampling and decoding

Sampled relevant Pauli and measurement faults XOR their edge endpoints into `detection_events`; their `fault_id` values XOR into the true logical observable. Loss-onset and reload-reset faults use the same edge-incidence rule.

PyMatching decodes only the detection array using the graph conditioned on revealed masks. Logical failure is `prediction XOR observable`. No failure or catastrophic shot may be removed from the denominator.

When `p=0` or `p_m=0`, absent non-erasure edges use an explicit large finite weight and can never be sampled. Infinite/NaN weights are rejected at schema boundaries.

## Catastrophic erasure diagnostic

Run a parity-aware union-find over zero-weight edges, including the matching boundary node. Each union carries the edge’s logical fault parity. A contradiction within an already connected component identifies a zero-cost logical cycle and sets `catastrophic_loss=1`.

This flag is diagnostic only. It does not force the logical label or skip decoding; the observed failure remains determined by sampled erasure Pauli components and decoder prediction.

## Independent oracle

The validator’s small oracle enumerates all relevant fault subsets for `d=3`, short `T`, and deterministic masks. It constructs incidence matrices directly from JSON geometry and performs exhaustive minimum-weight subset search. It shares neither the production graph builder nor PyMatching.

Oracle scope is deliberately small; stochastic large-grid results are checked by invariants, exact replay, analytic occupancy, and independent seeds rather than claiming exhaustive truth.

## Expected optimization headroom

The first correct baseline may rebuild one PyMatching graph per distinct mask. Later attempts can change one dimension at a time:

- packed-mask cache and canonical keys;
- group shots by mask history;
- vectorized counter RNG and incidence accumulation;
- parallel decode across history groups;
- incremental graph construction;
- bit-packed detector batches;
- cache eviction and memory layout.

Every optimization must preserve hidden fixture outputs exactly. Throughput is rewarded only after the correctness guards pass.
