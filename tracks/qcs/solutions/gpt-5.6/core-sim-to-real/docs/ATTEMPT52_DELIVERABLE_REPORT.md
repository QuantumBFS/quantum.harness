# Attempt 52 — failure boundary and cross-size invariant

Status: **PASS** (22/22 checks).

This appendix turns sealed development/mechanism evidence into a directly
auditable Challenge-113 deliverable. It performs no simulator query and opens
no confirmation truth.

## Failure-mode evidence

For the historical Joint-15 v1 coordinate-scan package, the combined-mismatch
success rate falls from **0.875** at epsilon=0.05 to **0.15625** at
epsilon=0.10. Control-map and drift families also degrade at the largest gap.
These are development curves, not a fresh principal-global confirmation sweep.

## Cross-size mechanism invariant

| System | Hilbert dimension | Endpoint rank | Hessian rank |
|---|---:|---:|---:|
| general-d2 | 2 | 3 | 3 |
| general-d3 | 3 | 8 | 8 |
| general-d4 | 4 | 15 | 15 |
| original-d4-cnot | 4 | 15 | 15 |

The supported local statement is:
**Near a sufficiently converged optimum, Hessian rank equals the rank of accessible weighted phase-blind endpoint-error channels for the audited controllable systems.**

The unconditional statement
**Unconditional rank(H)=d^2-1.** is rejected. The old
d=4 discrepancy was classified as
**optimizer-residual/spectral-gap artifact**.

## Honest negative result

No cross-dimension resource advantage is claimed. Attempt 28 left the raw
warm-start baseline at zero restricted cost in d=2,3,4, so the proposed
resource-scaling comparison was not identifiable under that frozen epsilon.

## Reproduce

```bash
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
```

The displayed figure is
`../plots/attempt45-gap-size-evidence-development.png`.
