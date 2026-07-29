# Challenge 148 Compute Handoff

Status date: 2026-07-29

## Current state

The software checkpoint is complete. The direct SSE and ParaToric pipelines,
finite-size analysis adapters, resumable manifests, cost projections, and
their basic tests are committed. Local production is intentionally stopped
because the projected workloads exceed the workstation resource threshold.

The physics challenge is not complete. Stage 7 remains `gate-pending`: no
Revision 7 production grid, accepted independent thermodynamic-limit critical
fields, unsealed triangular-to-honeycomb ratio, or final verdict exists.

## Last local validation

From this directory at commit
`1ca7b46c76f1466cb1aad9e82f68d905aa51b412`:

- `uv run --script tests/test_analysis.py`: pass;
- Python compilation of `tools/run_paratoric_critical.py` and
  `tools/analyze_paratoric_critical.py`: pass;
- Release build: pass;
- CTest: 9/9 pass in 231.58 seconds;
- corrected ParaToric cost pilots: 16/16 cells pass.

An additional equal-time-estimator diagnostic on a square $3\times3$ system
at $h=3$, $\beta=4$ gave SSE $\xi/L=0.3461983990$ and exact ED
$\xi/L=0.3461010817$, a relative difference of $2.81\times10^{-4}$. This
supports retaining the current estimator implementation.

## Deferred cluster work

1. Provision and validate an authenticated remote CPU-cluster profile.
2. Ratify proposed Protocol Revision 8, then run its finite-volume
   equilibration repair.
3. Run both frozen Revision 7 ParaToric production grids on the cluster.
4. Complete the separately frozen direct-SSE production route.
5. Apply all sampling, precision, independent-route, and finite-size gates.
6. Unseal the ratio only after both lattice results pass; then issue the
   preregistered verdict.

The existing pilot projections assume ideal scaling at 16 workers: 39.33 CPU
hours (2.46 hours wall) for triangular and 18.01 CPU hours (1.13 hours wall)
for honeycomb. These are planning estimates, not production evidence.
