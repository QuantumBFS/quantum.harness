# Frozen Baseline Model

Version: `1.0`
Frozen: `2026-07-28`
Scope: Challenge #66 core independent-loss benchmark

This file fixes the model that implementation attempts must preserve. Any material change requires a dated override in `research/STATE.md`, a validator update, and a new model version. Chinese prose is used for interpretation; identifiers are normative.

## 1. Code and memory experiment

- Rotated planar surface code with odd `d in {3,5}`.
- Memory basis `X` and `Z` are separate experiments.
- Syndrome rounds `T in {d,2d}`.
- The code contains data sites and measurement/ancilla sites with stable integer IDs and integer lattice coordinates.
- The baseline is a Clifford stabilizer circuit expressed in Stim. Arbitrary super-stabilizer products may use Stim `MPP` measurements; this is a round-level stabilizer-circuit model, not a native Rydberg pulse schedule.
- `p` is a single-qubit depolarizing probability on every active data qubit once per syndrome round. It is not silently reinterpreted as a per-CZ probability.
- `p_m` flips every otherwise valid stabilizer measurement independently.

The report must call this a **round-level circuit model**. A gate-native Rydberg schedule is an extension and cannot be implied by the word “circuit-level.”

## 2. Canonical round timeline

For round `t=0,...,T-1`:

1. Complete reload operations whose delay expires before round `t`.
2. Define `missing_mask[t]` at the start-of-round boundary.
3. Compose the X/Z stabilizer generators from data atoms known missing at this boundary.
4. Sample/apply active-data Pauli errors using the counter-addressed `data_pauli` stream.
5. Sample new loss events on currently active data and ancilla sites. A newly lost data carrier is represented by a uniformly random element of `{I,X,Y,Z}`, equivalent to complete depolarization. The loss is not yet available to the policy or decoder.
6. Measure the round’s stabilizers. A newly lost carrier can corrupt this round; the exact rule is part of the circuit generator and is covered by the independent oracle fixtures.
7. Apply `p_m` to valid measurement outcomes. Store invalid outcomes as `0` only together with `syndrome_valid_mask=0`; a consumer must never interpret that zero as a measurement.
8. Reveal this round’s loss events at the end-of-round boundary, transition them to `LOST_DETECTED`, and let the policy request reload using only revealed history.
9. A successful `L_reload=0` request restores the carrier before round `t+1`; larger delays leave it missing for that many complete subsequent round starts.

The final data readout happens after round `T-1`; loss detected after the last syndrome round still affects final observable accounting.

## 3. Loss and reload state machine

Per site:

```text
ACTIVE -> LOST_UNDETECTED -> LOST_DETECTED -> RELOADING -> ACTIVE
```

Allowed transitions are append-only events. Invalid coordinates, reload while `ACTIVE`, duplicate request while `RELOADING`, or direct `LOST_DETECTED -> ACTIVE` without a successful completion are errors.

Reload places a fresh carrier in the role-appropriate initialization state. It repairs array occupancy, not the lost unknown state. On completion, `reload_reset` may apply an error with probability `p_reset`; completion may fail with `p_reload_fail` and leave the site `LOST_DETECTED`.

- `p_reload_fail` is sampled once at the scheduled completion boundary. A failed completion applies no reset fault, returns the site to `LOST_DETECTED`, and can be requested again only at a later policy decision boundary.
- `p_reset` is sampled once after a successful completion. For data sites it is the probability of one relevant Pauli component on the first active round; for ancilla sites it is the probability of flipping the first otherwise valid stabilizer outcome. It is not applied again on later rounds.
- `reload_mask[t,site]=1` marks a successful completion at boundary `t`; request, failure, and reset-fault events remain separate append-only records.
- Boundary `T` resolves completions due after the last syndrome round and then stores `missing_mask[T]`. A final-round loss remains in the erasure/logical accounting even if an ideal reload restores occupancy at boundary `T`.

## 4. Dynamic stabilizers

For data loss, start from ideal same-type stabilizer generators. Connect generators that share a missing data site, find connected components with union-find, multiply all generators in each component, and cancel the missing-qubit factors. The resulting products are super-stabilizers.

- Components and supports use sorted stable IDs.
- A zero-support generator is invalid.
- When a data site is reloaded, regenerate components from the current missing set; do not mutate the previous round in place.
- An ancilla loss invalidates the associated measurement resource until reloaded. The fixed-shape dataset records both the outcome placeholder and `syndrome_valid_mask`.
- A loss configuration connecting incompatible code boundaries is recorded as `catastrophic_loss`; it cannot be dropped from the denominator.

## 5. Policies

- `none`: no request during active memory.
- `immediate`: request every newly detected missing site at the same end-of-round boundary.
- `periodic(R)`: at end-of-round number `r` with `(r+1) mod R == 0`, request all detected missing sites.
- `threshold(theta)`: request all detected missing sites when their count is at least `ceil(theta*N_sites)`.

`N_sites` includes data and ancilla sites. Threshold counting includes sites in `LOST_DETECTED` and excludes sites already `RELOADING`; a request targets every currently `LOST_DETECTED` site.

With `L_reload=p_reset=p_reload_fail=0`, `immediate` and `periodic(1)` must be bitwise equivalent. This is a model invariant, not an expected statistical trend.

## 6. Randomness and paired comparison

Use a deterministic counter-addressed generator keyed by:

```text
(master_seed, shot_id, round, site_id, event_type, subindex)
```

The streams `data_pauli`, `measurement_flip`, `loss`, `reload_reset`, and `reload_success` are independent. A policy may suppress the physical application of a pre-indexed event when the carrier is absent, but cannot change any other event’s value. All policies in a comparison share `master_seed` and `shot_id`.

## 7. Decoder contract

- Baseline: minimum-weight perfect matching built from the realized round-level circuit/detector model.
- Known loss/reload history must affect graph construction or weights; merely saving `missing_mask` while using the no-loss matching graph is invalid.
- Candidate decoder input is restricted to syndrome/detection events, validity masks, revealed loss/reload history, public metadata, and current/past rounds.
- Final logical observable, hidden Pauli events, undetected/future losses, and holdout provenance are forbidden inputs.
- A circuit/model that cannot be decomposed to graph-like errors must fail explicitly or use a separately validated decomposition; it cannot silently discard hyperedges.

## 8. Output semantics

Every shot records `shot_id`, `syndrome` or `detection_events`, `syndrome_valid_mask`, `missing_mask[T+1,N_sites]`, `reload_mask[T+1,N_sites]`, revealed loss/reload events, decoder prediction, final logical observable, logical failure, and `catastrophic_loss`.

All array axes, data types, coordinate order, and event boundary conventions live in a versioned manifest. Labels are stored separately from the decoder input view.

## 9. Model controls

- Zero-noise output is deterministic and failure-free.
- `p_loss=0` is bitwise invariant across policies.
- One deterministic loss matches the hand-written timeline for every policy/delay.
- `none` missing occupancy is pathwise monotone.
- Independent `none` occupancy follows `N*(1-(1-p_loss)^t)` within the predeclared Monte Carlo band.
- Reload never resurrects the old state or erases the recorded loss event.
- Every requested shot, including catastrophic cases, remains in the logical-error denominator.
