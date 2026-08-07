# Challenge 113 team synthesis

Status: evidence map for coordination and defence
Date: 2026-07-29

The two validated submission directions are independent implementations.
Their value is a triangulated scientific story, not a claim that they are one
common benchmark. The public paper-reproduction workspace is optional and is
not part of the fallback candidate.

## Strongest shared bounded claim

> A nominal simulator's low-rank fidelity-Hessian geometry can identify a
> compact black-box calibration space. This can reduce finite-shot query cost
> and avoid noisy nominally flat directions, provided the device mismatch does
> not rotate the active response too far or introduce error channels outside
> the nominal span.

The first sentence is directly supported in two different synthetic models.
The condition in the second sentence is supported by the neutral-atom
robustness scans and is a mechanistic interpretation, not a universal theorem.

## Evidence chain

### 1. Nominal geometry reconstructed

The `robustness/` direction builds an ideal, closed, exchange-symmetric
perfect-blockade neutral-atom CZ model. Its validated nominal point has:

- baseline infidelity `6.5996e-6`;
- active Hessian rank `5`;
- `lambda_5 / lambda_1 = 7.2087e-2`; and
- `lambda_6 / lambda_1 = 2.6815e-16`.

The clean baseline and full reruns passed 32/32 and 33/33 checks. A
standard-library comparator independently reproduced 3,951 numerical and 402
categorical scientific fields with zero mismatches.

### 2. Transfer boundary mapped

The `robustness/` direction keeps the same five nominal CZ directions and
varies distortion magnitude and orientation. All 30 tested cases per
distortion magnitude succeed through `eta = 0.35`. At `eta = 0.60`, success
is `10/10`, `6/10`, and `2/10` for initial principal-space powers `0`, `0.5`,
and `1`.

The fixed nominal subspace also fails on the named symmetry-breaking and
new-leakage pathologies. These failures support a concrete boundary: strong
local-subspace rotation, nonlinear breakdown, or a new physical response
channel can invalidate a fixed low-rank loop.

### 3. Finite-shot query advantage confirmed

The `core-sim-to-real/` direction uses a separate synthetic two-qubit CNOT
benchmark with 40 pulse controls and nominal Hessian rank 15. Its
preregistered 24-truth-cell confirmation gives:

| Method | Success | Full queries/run | Full shots/run |
|---|---:|---:|---:|
| model-informed `k=15` | 90.625% | 66 | 2,099,200 |
| completed model-informed `k=40` | 25.00% | 166 | 5,376,000 |
| raw-coordinate `k=40` | 0.00% | 166 | 5,376,000 |

The completed `k=40` method contains the same 15 principal directions. Its
lower success therefore isolates a useful mechanism: adding nominally flat
coordinates can consume finite-shot queries and inject estimator noise rather
than help the global update.

On the fresh benchmark, the restricted-mean post-hoc queries-to-target values
are 48.76 for `k=15`, 160.63 for completed model-informed `k=40`, and 166 for
raw `k=40`. Failures are charged the complete method cap. This directly
addresses the issue's query-count deliverable but is not an online stopping
certificate.

## What must not be merged into one claim

| Dimension | Robustness study | Core confirmation |
|---|---|---|
| Gate/model | perfect-blockade neutral-atom CZ | generic synthetic CNOT |
| Active rank | 5 | 15 |
| Controls | 512 real sampled waveform coordinates in robustness study | 40 pulse parameters |
| Target | robustness study uses `1-F <= 1e-5` | confirmation uses `1-F <= 1e-3` |
| Noise/cost | deterministic scans plus optional estimator-noise studies | finite-shot query ledger and frozen resource caps |
| Statistics | exploratory 10-seed boundary cells | 24 truth cells, nested replicates, preregistered bootstrap gates |
| Physical scope | perfect blockade, no cesium/hardware claim | synthetic scalar oracle, no hardware claim |

Consequently, no cross-model numerical success-rate comparison, universal
rank law, cesium claim, or hardware-readiness claim is authorized.

## Three-figure defence sequence

1. **Geometry:** the nominal robustness eigenvalue spectrum showing five active CZ
   directions and a negligible sixth direction.
2. **Boundary:** the robustness failure map at increasing distortion,
   highlighting orientation dependence and out-of-span pathologies.
3. **Closed-loop payoff:** the fresh CNOT success/cost figure showing `k=15`
   versus completed and raw `k=40`.

The verbal bridge is: *identify the active geometry; map when it transfers;
then measure the finite-shot benefit when it does*.

## Likely reviewer questions

### Why does `k=40` lose even though it contains the successful `k=15` space?

The extra 25 directions are nominally flat. Finite-shot central differences
along them add estimator noise and consume trust radius and queries in the
same frozen global-update rule. The comparison controls for the principal
directions and optimizer structure.

### Is 90.625% based on 96 independent devices?

No. There are 24 independent truth cells. Four shot-noise replicates are
nested within each cell, and uncertainty is bootstrapped at the truth-cell
level within mismatch families.

### Does the result prove online queries-to-target are lower?

No. The proposed online stopping certificate failed. The cost headline is the
deterministic two-cycle full cap; final success is scored post hoc.

### Is the robustness simulator the same as the CNOT confirmation simulator?

No. They are intentionally independent physical models. Their agreement is
mechanistic triangulation, not pooled statistical evidence.

### What would be the next scientific validation?

Expose a teammate platform simulator or real device through the same scalar
`query(parameters, shots)` boundary, then preregister a new benchmark, seeds,
gates, and mismatch conditions before opening results. Existing holdouts must
not be reused for tuning.

## Integration decision

No code-level merger is required for a valid submission. The safest final
package keeps each direction self-contained, links their handoffs, and uses
this document only to coordinate the common defence narrative.

## Optional team workspaces

Two additional directions are valuable, but neither is required to support
the headline:

- `reproduce/` supplies an independently tested partial theoretical
  reconstruction of Liu et al. Figures 1--4, equivalent reoptimization where
  unpublished arrays are unavailable, and explicitly synthetic data
  interfaces. It does not reproduce author measurements and is excluded from
  the default candidate.
- `Cold_Atom Gate Simu_Platform/` supplies a broader Cs/Rb digital-twin,
  query-facing interfaces, multilevel models, noise/readout components, and
  open-source pulse replay. It is not calibrated to a real Cs device and is
  excluded from the default candidate.

These workspaces show credible next steps: connect the frozen query protocol
to a richer platform model, then preregister a new experiment. They must not be
used retroactively to strengthen the already frozen core statistics.
