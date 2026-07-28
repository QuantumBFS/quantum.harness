# Phase 6 validated local reproduction design

## Goal and scope

Phase 6 now targets a validated local reproduction at `sigma=1.75`, with
separate estimates of MPS truncation uncertainty and exponential-MPO
approximation uncertainty. It does not attempt the original
`L=64,128,256` production scaling campaign. No calculation above `L=64` and
no Slurm workflow is in scope.

## Fixed physical setup

The Hamiltonian is

```text
H = -sum_{i<j} J_L(j-i; sigma=1.75) Z_phys_i Z_phys_j
    - Gamma sum_i X_phys_i,
```

where `J_L` is the pinned periodic Hurwitz-zeta image sum. In the rotated
TeNPy basis, `X_phys` is `Sigmaz` and `Z_phys` is `Sigmax`. The even parity
sector supplies the ground state and the full correlation function without
connected-correlation subtraction; the odd parity sector supplies the first
excitation. Thus `C(r)` is evaluated as the translation-averaged
`Sigmax-Sigmax` correlation.

All calculations retain exact-zero exponential-channel pruning, HDF5
checkpoints with full provenance, and initialization-only checkpoint reuse.
Approximate MPO compression is forbidden.

## MPS truncation uncertainty

The baseline is the existing `K=24`, `chi=128` local pilot. Targeted
refinement is restricted to:

- `L=64`;
- `Gamma=1.560` and `Gamma=1.565`;
- even and odd parity sectors;
- `chi=256`, initialized from the matching `chi=128` checkpoint.

For each point and sector, record runtime, energy, variance, maximum
discarded weight, sweeps, requested and reached bond dimensions, checkpoint
provenance, and code/fit hashes. Record `R_xi`, `S(0)`, `S(k_min)`, `xi`, and
the full correlation table from the even state. Record the gap from the
odd-even energy difference.

The analysis compares `chi=128` with `chi=256` at fixed `L`, `Gamma`, and
`K`. It reports absolute and relative changes in energy and gap, and
absolute changes in `R_xi`, variance, and discarded weight. These shifts
quantify the dominant local MPS uncertainty; they do not satisfy or replace
the original cluster-level `chi=384` protocol.

`chi=384` is not launched automatically. If a `chi=128` to `chi=256` shift
is unexpectedly large, the result is marked unresolved and the additional
calculation is proposed with a measured cost estimate for separate user
approval.

## MPO approximation uncertainty

Regenerate the locked `sigma=1.75`, `alpha=0.5`, `r_fit=2048`
decompositions independently at `K=24` and `K=32`. For `L=32` and `L=64`,
compare:

- distance-resolved coupling reconstruction error against the exact
  periodic Hurwitz-zeta table, including maximum/RMS errors and the central
  tail;
- `R_xi` at `Gamma=1.560` and `Gamma=1.565`;
- the interpolated two-size crossing behavior over that fixed bracket,
  using the same linear interpolation of
  `R_xi(L,Gamma) - R_xi(2L,Gamma)` for both K values;
- odd-even gaps at the same two Gamma values.

The K comparison uses direct `chi=128` as its common MPS baseline, exact-zero
pruning, and checkpointing. It is deliberately not a full K=32 scan or
finite-size scaling campaign. K-induced changes are kept separate from the
`K=24`, `chi=128` to `chi=256` MPS shifts.

If K=32 cost becomes limiting, retain the L=64 comparisons and avoid
repeating L=32 cells beyond the minimum needed to define the two-size
crossing. Any resulting incomplete crossing comparison is labeled rather
than replaced by an expanded or adaptive scan.

## Execution order and resumability

1. Add a checkpoint-refinement entry point and tests without launching
   physics runs.
2. Run the four targeted `K=24`, `L=64`, `chi=256` sector cells and write
   each result atomically.
3. Analyze the `chi=128` to `chi=256` shifts.
4. Regenerate and validate the `K=32` fit.
5. Run only the fixed K-comparison cells, reusing completed matching cells.
6. Produce separate MPS- and MPO-uncertainty tables and a compact local
   reproduction report.

Every cell is independently resumable. A completed checkpoint is reused
only when its physical parameters, parity, K, alpha, `r_fit`, requested
bond dimension, code hash, and fit hash match exactly.

## Acceptance and interpretation

The local result is accepted as a validated reproduction when:

- all requested cells have complete raw observables and provenance;
- exact-zero pruning remains validated and no approximate compression is
  present;
- the `chi=128` to `chi=256` shifts are explicitly reported;
- the `K=24` to `K=32` coupling, crossing, and gap shifts are explicitly
  reported;
- the critical-region behavior remains qualitatively stable under the tested
  chi and K variations, without requiring agreement with published
  thermodynamic-limit values;
- unresolved convergence is labeled rather than hidden or escalated
  automatically.

The final report may quote a local two-size crossing and diagnostic gap
behavior, but it must not claim an `L -> infinity` critical field or dynamic
exponent.
