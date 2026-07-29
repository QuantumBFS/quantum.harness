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

## Final review correction

- RED: a full-column orthonormal Hessian basis spanned the full pulse space but
  did not equal the bounded full baseline because rotating a coordinate box
  changes its feasible pulse set.
- GREEN: model-Hessian `k=p` now returns the exact identity-basis full search
  space. Boundary, alternating-corner, and axis-corner samples at `p=24` and
  `p=80` have exactly equal origins, bases, coordinate bounds, and pulse
  mappings. The method label and complete model-source-basis hash remain in
  trial provenance; `k<p` continues to use curvature-ordered columns.
- RED: local production verification expected `.deployment.json` inside the
  source root and the README omitted mandatory inputs.
- GREEN: all entry points require an explicit external metadata path, reject
  symlinks and in-tree metadata, and hash that exact regular file's bindings.
  The documented check-only workflow supplies every mandatory input, reaches
  `{"production_gate":"ready"}`, and leaves a Git checkout clean.

## Task 10C frozen-runtime integration

- The LASG02 compute-verified SIF is pinned by filename and SHA256; metadata
  also binds Python 3.12.12, uv 0.9.9, JAX/JAXLIB 0.11.0, NumPy 2.5.1,
  SciPy 1.18.0, pyproject, lock, archive, evidence, report, source revision,
  and the separate `lasg02-cpu-v1` scheduler profile.
- `prepare_apptainer_runtime.sh` performs the sole frozen sync in
  `apptainer exec --no-home`, runs the deterministic runtime gate, and writes
  a hash-bound readiness marker.
- Pilot and production scripts are LASG02-only, offline/no-sync, rehash the
  actual SIF/archive/project/lock, revalidate metadata and the runtime marker,
  and force JAX CPU x64 before physics.
- No representative pilot or production array was submitted. The next action
  is to stage the final committed source beside the verified SIF, prepare the
  runtime once, then submit only the representative pilot.

## Final pilot-blocker correction

- Deployment metadata now has a separately supplied, exact 64-character
  lowercase SHA256. Preparation checks those bytes before its first Apptainer
  call; jobs do the same before container entry. The readiness marker persists
  the metadata hash and the pre-submit gate rechecks it.
- LASG02 was probed read-only after loading Apptainer 1.3.4. The hash-verified
  SIF successfully ran a Python 3.12.12 no-physics command with unprivileged
  `--cleanenv --net --network none`; all preparation, smoke, pilot, and
  production container commands now require those flags.
- Fake-container integration tests prove a metadata mismatch exits before the
  first runtime call and that prepared jobs contain no sync or package-manager
  operation. No pilot or array was submitted.

## LASG archive-bind correction

- RED: the real fresh-root preparation bound the source archive under the
  synthetic name `/challenge113-archive.tar.gz`; strict deployment validation
  correctly rejected it because metadata binds the original revision filename.
- GREEN: preparation and job gates derive the basename from the quoted host
  archive path, require exactly `challenge-113-<revision-prefix>.tar.gz`, and
  bind and validate it under that same basename. Traversal, option-like,
  control-character, wrong-revision, and otherwise noncanonical basenames fail
  before the first Apptainer call.
- Fake-container tests cover the exact realistic prepare/job argv and prove
  malicious names enter neither preparation nor pilot runtime execution.

## Frozen networked preparation correction

- RED: network-none preparation could not fetch locked NumPy because LASG02 had
  no bound complete uv cache or wheelhouse.
- GREEN: after all source/runtime hashes pass, preparation requires
  `CHALLENGE113_ACK_NETWORKED_PREPARE=1` and runs exactly one network-enabled
  command: `uv sync --frozen --group dev --project /workspace` under
  `--no-home --cleanenv`. It runs no qcontrol, smoke, analysis, scheduler, or
  physics entry point.
- The post-sync runtime gate immediately returns to
  `--cleanenv --net --network none`. Its marker records the one-time frozen
  networked mode, strict execution isolation, exact runtime versions,
  lock/source/runtime hashes, metadata digest, and isolated objective/
  propagation smoke. Jobs reconstruct and compare that marker and never invoke
  uv or a package manager.
- Tests prove missing/wrong acknowledgement reaches no container, the sole sync
  command has no network-namespace flags, every later command has network-none,
  and no repository script submits a scheduler job.

## Slurm spool-path correction

- RED: pilot 2817990 resolved its shared gate relative to `BASH_SOURCE[0]`;
  Slurm had copied that launcher into its private spool, so the gate path did
  not exist and execution stopped before the runtime gate.
- GREEN: pilot and array launchers now require an absolute, canonical
  `CHALLENGE113_DEPLOYMENT`, reject a missing or symlinked gate, and source the
  gate only from that deployment. The existing gate still verifies the source
  revision, archive, evidence, runtime, and readiness marker before execution.
- Integration tests copy both launchers to an unrelated simulated Slurm spool.
  Correct deployment succeeds; relative, missing, and symlinked gate paths fail
  before any container command. No job was submitted.
