# Issue #28 Local N3/N4 Execution Deviation Design

## Status and Scope

This document records the user-authorized execution-policy deviation for the
Issue #28 Pure-Neural VMCRG Easy Goal. It changes only where N3 and N4 run.
The frozen scientific scope remains unchanged:

- periodic 45 x 45 Ising model at K = 0.436;
- non-overlapping 3 x 3 majority blocking;
- five consecutive neural-to-neural RG rounds;
- exactly five predeclared formal seed bundles;
- total neural energy with every handoff U_next = -V_frozen;
- the pure-neural 13-operator linear branch is exactly zero;
- the frozen objective, stopping, gauge, paired-stream, and classification
  rules remain authoritative;
- no failed formal seed replacement or post-formal seed extension.

The prior requirement to use Slurm for large N3/N4 compute is replaced by an
explicit, recorded `LOCAL_COMPUTE_DEVIATION`. This deviation is not scientific
success evidence by itself.

## Host and Parallelism Contract

The local host currently exposes 16 physical cores, 32 logical CPUs, 31 GiB
RAM, and sufficient disk. Runtime manifests must record the observed host,
CPU count, available memory, code hash, protocol hash, and worker limits rather
than trusting these discovery-time values.

- N3 runs alone with `ISSUE28_WORKERS_PER_BUNDLE=8`.
- N4 launches at most two independent seed-bundle subprocesses concurrently.
- Each N4 subprocess is capped at eight Issue #28 worker threads.
- BLAS, OpenMP, and Numba nested thread pools are capped independently so two
  bundle processes cannot expand beyond the declared worker budget.
- The operating system schedules workers; the implementation does not assume
  stable logical-CPU numbering under WSL.
- A second N4 bundle starts only when at least 12 GiB memory is available.
  Otherwise the coordinator temporarily reduces concurrency to one.

The five formal bundles execute in waves of 2 + 2 + 1. Parallelism is only
between seed bundles. Rounds within a bundle and arms whose outputs depend on
earlier arms retain their existing strict order.

## Execution Flow

1. Run the full local test suite and a two-round, small-lattice local smoke.
2. Verify the canonical code/protocol/operator hashes and that no target local
   output directory exists.
3. Cancel qdeshell job 5311997 only after the local preflight is green and
   immediately before launching N3, preventing duplicate pilot execution.
4. Run the disjoint N3 pilot locally for five rounds with eight workers.
5. Require a verified N3 manifest, five contiguous predecessor hashes, exact
   zero linear branch, resource records, and freeze-eligible classification.
6. Freeze `config/issue28_formal_v1.json` from that measured N3 result. The
   formal resource record identifies the matched local host class, eight
   workers per bundle, and maximum bundle concurrency two.
7. Create one immutable five-cell N4 run spec and launch exactly formal-1
   through formal-5 with the bounded local coordinator.
8. Fetching is unnecessary locally, but every bundle still writes the same
   independent manifests, validation data, three-arm comparison artifacts,
   resource records, and terminal classification expected from Slurm runs.

N4 cannot start before N3 verification and formal-protocol freezing. N3 and N4
are never run concurrently.

## Interfaces

Large local execution requires explicit authorization at every public entry:

- N3 CLI: `--backend local --allow-large-local`;
- N4 bundle CLI: `--backend local --allow-large-local`;
- local coordinator: protocol, output root, maximum parallel bundles, workers
  per bundle, resume flag, and explicit large-local authorization.

Without `--allow-large-local`, the existing fail-closed rejection remains.
The cluster cell runner remains Slurm-only and is not reused to disguise local
compute as remote compute.

The coordinator uses subprocesses, not Python threads, so Numba state, logs,
exceptions, and memory accounting remain isolated per formal bundle. Each
subprocess receives a distinct output directory and the same frozen host and
thread environment.

## Failure and Resume Rules

- Output directories are never overwritten.
- N3 resumes only hash-verified completed rounds; an interrupted in-progress
  round restarts without releasing a partial manifest.
- N4 resumes only the five named formal bundles and never substitutes a seed.
- A correctness or protocol failure stops launching new dependent work.
  Already-running sibling subprocesses are terminated cleanly after their
  current atomic write boundary when possible.
- A scientific negative result is preserved and does not trigger retries,
  threshold changes, added updates, or added seeds.
- A host reboot, nonzero subprocess exit, memory floor violation, or hash
  mismatch is classified separately from a scientific negative result.
- Coordinator state and per-bundle process records are written atomically so
  an interrupted 2 + 2 + 1 schedule can be reconstructed exactly.

## Verification

Implementation follows test-driven development and must add failing tests for:

- explicit authorization being required for large local N3 and N4;
- the worker cap being honored instead of raw `os.cpu_count()`;
- no more than two formal bundle subprocesses running concurrently;
- unique, complete formal-1 through formal-5 dispatch with no replacement;
- local hardware/resource provenance in the frozen formal protocol;
- correctness/protocol failures preventing new bundle launches;
- scientific negatives being retained without retry;
- hash-matching resume and output non-overwrite behavior.

After focused tests pass, run the complete existing suite and the small local
smoke. Only then cancel the pending Slurm job and start full N3. N3 and every N4
bundle are accepted only from verified manifests, never from process exit
status alone.

## Cost Expectation

N3 performs roughly 0.4-0.8 billion neural proposals before monitoring and
objective work. The five formal bundles require at least 8.1 billion neural
proposals plus traditional, unbiased, objective, and autocorrelation work.
N3 is expected to take hours; N4 may take multiple days even with bounded
two-bundle parallelism. Progress is flushed 10-50 times per round and each
bundle has an independent log, so runtime behavior remains observable.
