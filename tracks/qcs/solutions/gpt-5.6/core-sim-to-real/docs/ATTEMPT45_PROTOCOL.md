# Attempt 45 protocol — existing gap and size evidence

Date frozen: 2026-07-29
Parent: `RESEARCH_CHARTER_05.md`
Status: frozen before Attempt-44 outcomes

## Purpose

Assemble the already source-sealed model-truth-gap and system-size evidence
without spending new simulator queries or silently treating incompatible
experiments as one confirmation.

## Inputs

- Attempt 25: finite-shot mismatch boundary at epsilon 0.02, 0.05, and 0.10.
- Attempt 28: failed/unidentifiable fixed-epsilon dimension-scaling test.
- Attempt 34: converged endpoint-map and Hessian rank audit.

Every input is development or mechanism evidence. Attempt 22 remains the sole
fresh confirmation.

## Gap output

For each truth family and epsilon, copy the frozen Joint-15 v1 and principal-15
success rates versus raw-40, paired success differences, query/shot ratios, and
gate outcomes from Attempt 25.

This evidence belongs to the earlier Joint-15/coordinate-scan package. It may
support a statement about the useful model-truth-gap window, but it cannot be
presented as a new principal-global gap sweep.

## Size output

For converged exact/refined points in Attempt 34, report:

- system label and Hilbert dimension;
- parameter count;
- endpoint-map rank;
- Hessian rank;
- nominal infidelity; and
- equality of endpoint and Hessian ranks.

Use Attempt 28 only to preserve the negative result: the fixed epsilon made
the raw baseline a zero-cost warm success in d=2,3,4, so a cross-dimension
resource ratio was not identifiable.

## No-new-compute rule

Attempt 45 performs no fidelity, gradient, Hessian, or optimization call. It
hashes inputs, validates expected schemas, writes a compact evidence inventory,
and states missing claims explicitly.

No new size/gap matrix is authorized in this attempt. The new primary evidence
is the normalized dimension-`k` sweep in Attempt 44; cross-Hilbert-dimension
resource scaling remains outside the final positive claim.

## Required decision

The package passes when:

- all three source hashes close;
- all three epsilon values and all three truth families are retained;
- converged ranks are 3, 8, 15, and 15 for general d=2, d=3, d=4, and original
  d=4 CNOT;
- the Attempt-28 zero-cost-raw limitation is preserved; and
- no fresh confirmation or new simulator query is generated.

