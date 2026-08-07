# Attempt 52 protocol — derived failure and invariant audit

Date recorded: 2026-07-29
Evidence class: development/mechanism-derived audit

## Purpose

Close the Challenge-113 failure-mode and cross-system-size deliverables from
sealed evidence without issuing a simulator query, fidelity call, gradient,
Hessian evaluation, optimization call, or confirmation-truth access.

## Inputs

- Attempt 25: historical model-truth-gap development curves.
- Attempts 26–28: dimension construction, old spectral-gap result, and the
  unidentifiable resource-scaling experiment.
- Attempt 34 v1 and final: numerical-artifact diagnosis and corrected endpoint
  / Hessian-rank audit.
- Attempt 45: compact gap and size evidence inventory.

## Passing contract

- Every source hash closes.
- The gap appendix retains control-map, drift, and combined families at
  `epsilon = 0.02, 0.05, 0.10`.
- At least two distinct Hilbert dimensions are audited; the sealed evidence
  contains `d=2,3,4`.
- Selected invariant points are only `exact-construction` or
  `refined-optimized`.
- Every selected system is full-SU controllable.
- Endpoint and Hessian ranks agree at every selected converged point and never
  exceed `d^2-1`.
- Endpoint finite-difference error is below `5e-3`, unitarity residual is below
  `1e-6`, and weighted endpoint-Gram/Hessian relative error is below `0.05`.
- Attempt 27's old `d=4` rank 8 is explicitly classified as an
  optimizer-residual/spectral-gap artifact.
- Attempt 28 remains `resource_scaling_testable=false`; zero-cost raw warm
  starts establish neither an advantage nor a disadvantage.
- The audit records zero new compute and zero confirmation truths opened.

## Authorized claim

Across the audited fully controllable systems with Hilbert dimensions
`d=2,3,4`, sufficiently converged optima exhibit a local mechanism invariant:
the infidelity-Hessian rank equals the rank of accessible weighted
phase-blind endpoint-error channels.

This is not a universal `rank(H)=d^2-1` theorem, qubit-count scaling result,
cross-dimension resource advantage, hardware result, or cesium claim.
