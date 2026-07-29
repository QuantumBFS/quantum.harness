# Challenge 148 Compute Handoff

Status date: 2026-07-29

## Current state

The current software checkpoint is committed. The direct SSE and ParaToric
pipelines, finite-size analysis adapters, resumable manifests, cost
projections, and their basic tests are present. Local production is
intentionally stopped because the projected workloads exceed the workstation
resource threshold.

The physics challenge is not complete. Stage 7 remains `gate-pending`: no
Revision 7 production grid, accepted independent thermodynamic-limit critical
fields, unsealed triangular-to-honeycomb ratio, or final verdict exists.

## Last local validation

From this directory at code commit
`e1de23fd213257136821d613f7bf8cec41fa47da`:

- `uv run --script tests/test_analysis.py`: pass;
- Python compilation of `tools/run_paratoric_critical.py` and
  `tools/analyze_paratoric_critical.py`: pass;
- generic parameter-scan tests: 36/36 pass;
- clean-source plan smoke: pass with commit and provenance fields fixed;
- corrected ParaToric cost pilots: 16/16 manifests pass the hardened validator;
- Release build: pass; C++ is unchanged since CTest passed 9/9 in 231.58 seconds.

The hardened validator rejects a source commit different from the plan,
tampered raw artifacts, inconsistent manifest diagnostics, mismatched $\mu$,
varying or negative package autocorrelation times, and non-boolean direct-route
acceptance fields. Observable columns are resolved by CSV header name rather
than fixed position.

An additional equal-time-estimator diagnostic on a square $3\times3$ system
at $h=3$, $\beta=4$ gave SSE $\xi/L=0.3461983990$ and exact ED
$\xi/L=0.3461010817$, a relative difference of $2.81\times10^{-4}$. This
supports retaining the current estimator implementation.

## Remaining software gate

The ParaToric analyzer requires an accepted Revision 7 direct-SSE summary, but
the repository does not yet contain the final producer for that accepted
`summary.json` contract. Implement and test that producer before either
independent critical field can be accepted. This is separate from the remote
compute-resource gate.

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
