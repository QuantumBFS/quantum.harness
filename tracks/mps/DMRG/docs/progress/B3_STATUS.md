# B3 Thread Status: Stage 5 Exact and Small-3D Validation

## Thread identity

- Thread: B3
- Date closed: 2026-07-29
- Scope: implementation-plan Tasks 3-13 and the Stage 5 / M5 gate only
- Branch retained: `challenge/issue28-pure-neural`
- HEAD remained: `a734162e0e75098fd9326e0aeb45e9ae3247b0f5`
- Plan: [`2026-07-28-issue28-hard-goal-3d-spin-glass.md`](../superpowers/plans/2026-07-28-issue28-hard-goal-3d-spin-glass.md)
- Formal result: `results/hard_goal/stage5-b3-r1/`
- State: Stage 5 PASS; Stage 6 has not started

No commit, push, branch switch, PR mutation, Slurm submission, production run,
or second RG was performed in this thread.

## Completed in this thread

1. Implemented the cubic iid +/-J Edwards-Anderson model with exact integer
   energies/local deltas, L=2 enumeration, and an L=3 transfer oracle.
2. Implemented independent-replica overlap fields and the required q, q2, q4,
   Binder, spin-glass susceptibility, axial wave-vector susceptibility, xi_L,
   and xi_L/L estimators with one record per quenched J.
3. Implemented one- and two-level 3x3x3 majority caches, while keeping the
   second-RG execution gate disabled.
4. Implemented gauge-invariant cross, face/edge, cube, and factorized-3x3x3
   template encoders, all 48 cubic actions, q inversion, and reverse incidence.
5. Implemented trainable variable-length local Tensor Trains, exact O_h x Z2
   averaging, canonicalization, finite gradients, parameter diagnostics, and
   chi=2/4/8 support.
6. Implemented the conditioned finite linear baseline, Routes A/B/C, frozen
   cube lookup, exact local bias deltas, and generation-safe cache rebuilds.
7. Implemented unbiased two-ladder and biased paired parallel tempering with
   the general cross-bias swap action and random-sequential biased updates.
8. Implemented NumPy and optional JAX backends, resource records, round-trip,
   stationarity, split-Rhat, IAT/ESS, T_max-forgetting, and fail-closed
   completion diagnostics.
9. Implemented Route C/B VMCRG training, joint clipping, transactional numerical
   failure rollback, complete atomic checkpoints, trajectory-equivalent resume,
   held-out route evaluations, and evidence-bound C3 authorization.
10. Ran the fixed Stage 5 matrix: exact L=2/L=3 checks, L=6/L=9 PT mechanics,
    one RG, a biased local-MPS smoke, nine TT cells, and reference/JAX-CPU
    backend equivalence.

## Review findings closed

- Task 3: stabilized finite-beta transfer scaling and made absolute-tolerance
  exactness tests truly absolute.
- Task 6: expanded independent joint q/J covariance checks from one action to
  all 48 actions for all four templates; deduplicated periodically aliased L=2
  reverse-incidence centers.
- Task 8: made lookup rebuild refresh every local cached value and total before
  atomically changing generations; stale proposals are rejected.
- Task 11: replaced vacuous full-series reblocking with cumulative histories,
  always includes the complete N-sample tail for non-power-of-two N, records
  T_max forgetting and extension count, and rejects incomplete/nonfinite
  hardness metadata.
- Task 12: requires checkpoint context before training, restores backend state
  on all covered numerical failures, saves the last finite checkpoint, binds C3
  authorization to matched immutable held-out evaluations, and applies the
  correct active matching axis for proposal-budget versus wall-budget evidence.
- Task 13: runs matched cube C/B cells from identical TT initializations for
  chi=2/4/8 plus cross B chi=2/4/8; cross/C is explicitly unsupported because
  the fixed linear basis is cube-specific. Correctness failures abort before
  later sections and immutable output refuses overwrite.

No Critical or Important finding remains from the completed B3 review/fix
cycles. Deferred non-load-bearing observations are listed below rather than
silently discarded.

## Formal Stage 5 result

- Classification: `PASS`
- Failed gates: none
- Manifest SHA-256:
  `95ef85f4928dea3bfa1541be0ca34c9febcbec9b4375b50f621a419bdd3692f6`
- `exact.json`:
  `36e6a4ea540735c4bc7681f1389a902f2e6f58e291c7bd03bf5f6906ca86e332`
- `pt.json`:
  `119faad212d13a4a27b1cb1ee850600e4eb5de6e74d7df11b485962d0bcd1f9e`
- `rg.json`:
  `50088c7084d04d82de4464cae555375feebdc31929b8396573b2947705c82bc3`
- `vmcrg.json`:
  `9a02e0c4df2581325666b20c26d05c69f943fcff65d89f391e7e5364f36613d5`
- `resources.json`:
  `7ca0e70541a8e613a9ac4a939e6ec35151f977fe879022bfdf88df9677361220`

All 47 artifact/source hashes in the manifest were independently recomputed
with zero mismatches. A second invocation refused overwrite with exit code 2
and left the manifest hash unchanged.

## Numerical evidence

- Maximum L=2 estimator absolute error: approximately 1.2143e-3, below 2e-3.
- L=3 energy derivative errors/site: 1.025e-10 and 9.247e-12.
- PT detailed-balance error: 1.952e-18.
- RG origin and incremental cache errors: exactly zero.
- Maximum local bias-cache error: 1.110e-16.
- Maximum symmetry error: 3.469e-18.
- Maximum TT finite-difference gradient error: 1.059e-11.
- NumPy and available JAX-CPU proposal deltas and shared-uniform accept
  decisions agreed exactly in the resource smoke.

## Tests and checks

| Check | Result |
|---|---|
| Task 6 gauge/template/symmetry suite | 33 passed |
| Task 11 equilibration suite | 10 passed |
| Task 12 VMCRG/checkpoint suite | 20 passed |
| Combined amended components | 63 passed in 65.17 s |
| Full HG3D suite | 233 passed in 148.85 s |
| Python syntax compilation | PASS |
| Scoped whitespace check | PASS |
| Manifest artifact/source rehash | 47 checked, 0 mismatches |
| Immutable overwrite refusal | PASS, exit 2 |

## Scientific limitations

- Stage 5 PT uses only 12 sweeps. It records zero round trips and zero
  acceptance on some edges. This is mechanics and detailed-balance evidence,
  not equilibration or Tc evidence.
- Stage 5 VMCRG uses a synthetic local overlap-field teacher and one update.
  Its no-bias `baseline_tv` is not the final conditioned-linear comparator.
- Stage 5 therefore does not satisfy the final requirement that an MPS beat a
  fair conditioned-linear baseline on held-out physical disorder data.
- JAX was exercised on CPU only and carries `performance_claim=false`; A800 and
  DCU throughput remain unmeasured.
- There is no finite-size crossing, L=45 production data, or Tc estimate.

## Deferred non-load-bearing observations

- `BinEstimate.block_count` retains a legacy name although cumulative records
  now store run lengths; clarify this schema before Stage 6 artifacts freeze.
- Validate `extension_count` as an integer, not merely a nonnegative value,
  before accepting external pilot records.
- Clarify the module-level `reverse_q_incidence(length, encoder)` ownership
  relative to the encoder method declared by the plan.
- Carry B2's source-integrity diagnostic-detail and direct classifier-branch
  test suggestions into the next workflow hardening pass.
- One beta=0 exact test record uses `temperature=1.0` metadata; its numerical
  assertions are unaffected, but the metadata should be corrected before a
  public report.

## Not completed

- No Stage 6 medium-size equilibration/performance/power pilot or frozen
  production candidate exists.
- No A800 compute-node Hard Goal smoke has run; SCNet SSH precheck currently
  fails and DCU compatibility remains unknown.
- No Stage 7 run spec, production array, or actual L=45 result exists.
- No Stage 8 whole-J bootstrap, Binder/xi_L crossing, correction-aware fit, or
  neural RG-flow interval exists.
- No Stage 9 report, final success classification, commit, push, or PR update
  exists.

## Cluster snapshot and next thread

The qdeshell precheck passes. At the 2026-07-29 probe, `qdagnormal` showed five
allocated and three mixed A800 nodes, with approximately seven unallocated GPUs
visible across the mixed nodes. Historical job 5311997 waited about 1 h 53 min
without starting before cancellation. Existing unrelated job 5312733 waited
about 1 h 46 min, was running, and had dependent jobs queued; do not alter that
chain implicitly.

Open B4 for Stage 6 / Task 14 only. Implement the pilot and protocol-freeze
tests first, run a local reference preflight, then use qdeshell for an A800
compute-node smoke and the approved medium pilot. Freeze no production request
until measured throughput, equilibrium, power, memory, and output margins pass.
Stage 7 remains a separate exact-resource preview and explicit user-confirmation
gate.
