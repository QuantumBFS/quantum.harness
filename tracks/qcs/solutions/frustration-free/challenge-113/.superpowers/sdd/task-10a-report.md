# Task 10A controller report: current gate

## Status

The pre-Task10C scientific and reproducibility blockers are closed locally.
Production was not submitted. The only execution blocker is frozen-runtime
compatibility on both authorized clusters: glibc 2.17 cannot load the locked
`jaxlib==0.11.0` manylinux 2.27 wheel.

## RED/GREEN record

- RED: effective Hessian rank was also used as the available model-Hessian
  search basis, so approved high-k trials could not construct.
- GREEN: dense `p<=80` landscapes retain all `p` exact-Hessian eigenvectors in
  descending absolute-curvature order. Effective ranks remain 3 (`d=2`) and 15
  (`d=4`) at `1e-8`. Matrix-free paths report their actual available column
  count and never synthesize missing vectors.
- RED: public artifacts hashed only the selected basis slice.
- GREEN: model-Hessian artifacts additionally hash the complete source basis.
  Real `d=2,k=24` and `d=4,k=20,30,80` fixtures prove orthonormality, nested
  subspaces, unchanged ranks, and full-span `k=p` equivalence. Every canonical
  production search-space configuration constructs without spending budgets.
- RED: evidence accepted coercible JSON values, stale cross-document inputs,
  an environment record with x64 disabled, and deployment metadata that did
  not hash an actual archive file.
- GREEN: evidence requires exact JSON types, finite ranges, x64, provisional
  projection status, persisted-input arithmetic, config binding,
  cross-document hashes, and pilot/timing/validation consistency. Deployment
  verification hashes the supplied archive bytes, enforces revision naming,
  validates the complete evidence directory, and binds report/evidence/archive
  hashes.

## Current local rerun

Measured source revision: `dd16192953c130d738716238525760de73343e09`.

- Calibration: first query 0.217 s; 19 warm queries 0.0338 s (562/s);
  open-loop 7.75 s; dense landscape 5.81 s; exact trajectory 0.0340 s;
  geometry 1.67 s; restricted optimization 0.430 s/8 evaluations.
- Environment: JAX CPU, x64 enabled, 32 logical CPUs.
- Full pilot: 881 exact queries, 21.91 s wall, 864,260 KiB peak RSS, strict
  validation `valid=true`.
- Projection: provisional only; computed directly from persisted pilot wall
  time, artifact bytes, 9,500 trials, and eight cores as an arithmetic scenario.
  No resource class or concurrency is selected before Task 10C pilots.

The earlier calibration, seed-risk, and concurrency statements are superseded
and remain available only in Git history.

## Deployment state

The reviewed candidate is archived and validated locally after the final
evidence/documentation commit. Deployment metadata is generated beside the
extracted runtime rather than tracked in the source tree. No remote deployment
or Slurm submission was made.

## Remaining Task 10C decisions

1. Approve an exact cluster runtime solution for the glibc 2.17 / manylinux
   2.27 incompatibility.
2. Run representative CPU-count, memory, and concurrency pilots in that exact
   runtime.
3. Recompute the measured allocation gate before submitting the 9,500-trial
   array.
