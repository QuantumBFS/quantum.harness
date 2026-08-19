# Correction — job 23004880 (pre-quotient D4 Rung B gamma=0)

Date: 2026-07-29 (advisor current-status review, P0.1)

The `equivalence_note` in this bundle's `runmeta.toml` is **overstated** and is
retracted. This job solved the **pre-quotient D4 block-compression** model
(commit `695df27`), not the current moment-orbit quotient model.

## What this model actually was

The pre-quotient builder imposed the five diagonal congruence blocks
`Q_lambda' M Q_lambda ⪰ 0` but **dropped the off-irrep blocks** `Q_lambda' M Q_mu`
(lambda != mu) while retaining all 12,826 independent moment variables. For an
arbitrary moment functional `L`, `M(L)` is not D4-covariant, so those off-irrep
blocks are generally nonzero; dropping them makes the model a **weaker sound
principal-compression relaxation**, not an invertible reparameterization of the
full unsymmetrized moment-PSD constraint.

## What is still valid about this evidence

- Every full PSD moment matrix has PSD principal compressions, so requiring the
  diagonal blocks PSD is a **sound necessary condition** (a valid, weaker
  relaxation).
- The `OPTIMAL / feasible_candidate` result at `gamma=0` demonstrates
  **tractability** (the D4 block structure fits in ~87 GB and the IPM converges)
  and exercises the build/MOF/solve path. It is a **tractability smoke**.
- gamma=0 is the ground-state condition (expected feasible for any sound
  relaxation), so this does not establish a gap threshold.

## What is NOT supported

- The `equivalence_note` claiming "exactly-equivalent reparameterization."
- The implication that matching the unsymmetrized `assembly_sha256` proves
  equivalence (that hash identifies the unreduced 12,826-moment assembly and is
  unchanged by the D4 transform).
- Treating this job as a solve of the current 1,831-variable quotient model.

## Correct framing

> Pre-quotient D4 principal-compression Rung B tractability smoke (gamma=0,
> OPTIMAL). Not equivalent to the unrestricted relaxation; the exactly-equivalent
> quotient model is separate and requires its own validated solve.

The current quotient model (commit `79a1157`) identifies D4-equivalent moments
(forcing `L` D4-invariant), which is what makes the off-irrep blocks vanish and
the diagonal blocks exactly equivalent to the full `M ⪰ 0`. That equivalence is
plausible by the group-averaging argument but must be validated by the exact
coefficient covariance/cancellation gates before any positive-gamma claim.
