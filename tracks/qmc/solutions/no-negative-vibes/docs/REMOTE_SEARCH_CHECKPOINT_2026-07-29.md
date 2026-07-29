# Remote search checkpoint — 2026-07-29

## State

This checkpoint closes the currently authorized search round.  All numerical
and symbolic scientific work ran on WSL or on the CPU machine reached through
WSL.  No scientific computation ran on the local Windows workspace.

No next-round search has been started.  At checkpoint time there are no live
oddcycle dual, path-promotion, or physical-promotion processes.  Existing
results, environments, remote repositories, scripts, manifests, worktrees,
and ignored result directories must be retained.

Shared branch:

`work/zibo/representation-cones`

Local checkpoint commits:

- `823aedb` — record the complete dual-interior frontier scan;
- `29a54f3` — record the exact `cell-4321` theorem and physical promotion.

The private `AGENT_HANDOFF.md` has also been updated through Major Update 7.
It is local-only and must never be staged or uploaded.

## Completed searches

### 1. Oddcycle pair frontier

Frozen family:

`{B(p_low,q,r), B(p_low,q,r)^T, B(p_high,q,r), B(p_high,q,r)^T}`.

Axes:

- `p_low`:
  `1e-5,2e-5,5e-5,1e-4,2e-4,5e-4,1e-3,2e-3,3e-3,5e-3,`
  `7.5e-3,1e-2,1.5e-2,2e-2,3e-2,4e-2,5e-2`;
- `p_high = 0.55 + 0.025 k`, `k=0,...,28`;
- `q,r = 0.9,0.95,1.0,1.05,1.1`.

Settings:

- 12,325 deterministic cells;
- determinant words through depth six;
- CLARABEL with validation tolerance `1e-7`;
- time-orientation tolerance `1e-7`;
- 76 virtual shards, executed in WSL waves of at most 14 processes;
- one BLAS thread per process.

Resolved result:

- 6,266 path-metric survivors;
- 6,059 joint-common-metric controls;
- zero unresolved cells after four CLARABEL operational errors were retried
  with SCS;
- active-wave wall time about 167 seconds, or 73.8 cells/s.

There was no RNG and therefore no random seed.  Cell ordering and virtual
sharding are deterministic from the frozen Cartesian axes.  The run-spec
SHA-256 is
`fb53bb4d8571f56d447480de603846f45a773921ebd45c7b05bee4bee1b4c8a1`.

WSL result root:

`/home/zibojin/code/nnv-final-verify/tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729`

Full-scan summary:

`summary.json`

SHA-256:

`39f2ce18a48f6801b54f25f3e796c02a7b58aaeec578ee364a60561af1b51275`

### 2. Dual-interior ranking

All 6,266 survivors were ranked by the two independent objectives

1. path-metric margin;
2. minimum eigenvalue of a normalized Gordan--Stiemke dual.

Settings:

- CLARABEL;
- `objective_seed=-1`, a fixed objective selector, not an RNG seed;
- floating rational denominator zero;
- qualifying thresholds `min_eig>1e-8` and residual `<1e-7`;
- 14 processes and one BLAS thread per process;
- deterministic 1,024-cell stratified pilot followed by the remaining
  5,242 cells;
- exact top-five replay at denominator `10^8`.

Result:

- 6,266 unique merged records;
- 4,302 solver successes;
- 1,964 explicit `SolverError` records, retained as operationally
  inconclusive rather than mathematical failures;
- 4,183 qualifying floating dual interiors;
- 118 Pareto fronts, with 37 cells on front one;
- top five exact replays passed exact cancellation, trace normalization one,
  and all four multiplier PSD gates.

The remaining 5,242 cells completed in 26.26 seconds, or 199.63 cells/s.
There was no random sampling or RNG seed.

WSL artifact root:

`/home/zibojin/code/nnv-final-verify/tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/dual-interior-ranking-v1`

Important hashes:

- `merged-records.jsonl`:
  `f6011ae5623b28c354c000cb82a8b3f66ffdfe853d132a80446eb323e75d9eea`;
- `pareto-ranking.jsonl`:
  `bc6219f741cd00b87eccc394769a10fbf2a168ffd2e1ff087ba11e43b48acdcb`;
- `top5-exact.jsonl`:
  `7cf00b71abef42f23c39d17930334247cf546cbe84cbdd883851458e5e6d1ee0`;
- `dual-ranking-summary.json`:
  `30d8b09fc840c5213e6377adbfc572ee3a1161ef1db966b2bc78d4cb57468020`.

All 14 original shard files remain in this directory.

### 3. Exact promotion of cell-4321

Exact points:

`(p_low,q,r)=(1/2000,11/10,9/10)` and
`(p_high,q,r)=(49/40,11/10,9/10)`.

WSL path/orientation promotion:

- CLARABEL `optimal`;
- denominator `10^9` passed on the first attempt;
- verified margin `2.2173353992083533e-5`;
- exact inertias 4/4 and exact Stein gaps 16/16;
- four exact time-like vectors and 16/16 future-preserving transitions;
- all four letter determinants equal eight;
- runtime 1.336 seconds;
- no RNG or random seed.

Path artifact:

`/home/zibojin/code/nnv-final-verify/tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/cell-4321-path-promotion-v1`

Hashes:

- `path-promotion-summary.json`:
  `edb6ef0ba9bbda6e86668a4d979c6cd71a9f07d0183d7eecb3d6309ae369b46c`;
- `promotion.py`:
  `a1b54b982f6bdf56c2ae3d9881cc967de17acbdd0ce50f25bd68027b6252ac47`.

CPU physical promotion:

- exact 32-dimensional Fock lift;
- minimum strict row-dominance shift `c=37`;
- row margin at `c=36`: `-2051/10000`;
- row margin at `c=37`: `7949/10000`;
- positive field coefficients `(37,1,1,1,1)/41`;
- four exact Descartes zero-sign-change real-log certificates;
- 58 non-Gaussian grade-two mismatch entries, first `(0,0)=4/41`;
- no RNG; `PYTHONHASHSEED=0`, one process, and one BLAS thread.

CPU source commit:

`84d757e4a5c40e96126b37fe2b4d6694b37f9856`

CPU artifact root:

`/home/jzb/code/nnv-longadv-hp-2ae03be/tracks/qmc/results/no-negative-vibes/cell-4321-physical-v1`

Hashes:

- `result.json`:
  `4661a61dc8c5d0779cdb8ca80880d1cc883d0e59b3a68d69488637656651877f`;
- restored, not re-executed `replay.py`:
  `a5ebff0684d2ad325f74e92c54cf3647ac52ce52a0f6cc1109d9ae5c3bf9084d`.

`RESUME.md`, `result.json.sha256`, and `replay.py.sha256` are preserved in
the same CPU directory.  Four pre-existing untracked oracle files remain in
that CPU repository and were neither removed nor used as experiment
dependencies.

### 4. Non-induced exterior-grade pilot

The deterministic 256-cell WSL pilot produced:

- 228 `structural-compound-failed`;
- 28 `known-tn-or-minor-failed`;
- zero compute errors;
- zero promoted hits;
- mean 0.237 s/cell.

No RNG was used.  The coarse 51,840-cell grid was intentionally not started.
The saved decision is to use an adaptive minor-boundary search only after an
explicit future `继续` instruction.

Tracked result:

`protocols/tp-exterior-extension-v1/pilot-result.json`

## Failure and recovery lessons

Scientific and operational outcomes must remain separate.

- Four frontier CLARABEL errors were operational.  Retrying only those cells
  with SCS classified all four as joint-common-metric controls.
- The dual scan retained 1,964 CLARABEL `SolverError` records as
  inconclusive; they are not no-go evidence.
- Ranking only by the primal path margin sent exact arithmetic to three
  candidates whose rationalized dual multipliers failed PSD.  Ranking by
  dual interior exposed five exact certificates immediately.
- The WSL promotion first failed before solver start because `1/2000` was
  sent directly to `float`, and a later Windows/WSL launch acquired `\r` in
  the script path.  Parse exact strings through `Fraction` and avoid nested
  shell launches.
- The CPU promotion had a symbolic matrix-sum initializer error and then
  used two same-named SymPy symbols with different assumptions.  Use an
  explicit zero matrix and one canonical symbolic variable.
- The CPU payload was initially executed through stdin without saving its
  source.  The exact final successful payload has now been restored as
  `replay.py` without executing it, and a `RESUME.md` was added.
- GitHub HTTPS intermittently timed out or reset.  Do not move or delete
  local commits or remote evidence while synchronization is pending.

## Read-only verification commands

These commands verify preserved evidence; they do not launch a search.

On WSL:

```bash
cd /home/zibojin/code/nnv-final-verify
sha256sum \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/summary.json \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/dual-interior-ranking-v1/merged-records.jsonl \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/dual-interior-ranking-v1/pareto-ranking.jsonl \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/dual-interior-ranking-v1/top5-exact.jsonl \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/dual-interior-ranking-v1/dual-ranking-summary.json \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/cell-4321-path-promotion-v1/path-promotion-summary.json \
  tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729/cell-4321-path-promotion-v1/promotion.py
```

From WSL, verify the CPU artifacts:

```bash
ssh -i /home/zibojin/.ssh/cpu_worker_ed25519 \
  -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=12 \
  jzb@162.105.145.128 \
  'cd /home/jzb/code/nnv-longadv-hp-2ae03be &&
   sha256sum \
   tracks/qmc/results/no-negative-vibes/cell-4321-physical-v1/result.json \
   tracks/qmc/results/no-negative-vibes/cell-4321-physical-v1/replay.py &&
   cat \
   tracks/qmc/results/no-negative-vibes/cell-4321-physical-v1/result.json.sha256 \
   tracks/qmc/results/no-negative-vibes/cell-4321-physical-v1/replay.py.sha256'
```

## Recorded execution commands

These commands document how the completed work was launched.  They are not
the next action and must not be run merely to resume the project.

Common WSL environment:

```bash
REPO=/home/zibojin/code/nnv-final-verify
PY=/home/zibojin/miniforge3/envs/quantum_harness/bin/python
export PYTHONPATH="$REPO/tracks/qmc/solutions/no-negative-vibes"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
RUN="$REPO/tracks/qmc/results/no-negative-vibes/oddcycle-pair-frontier-v1-20260729"
```

The original frontier used source commit
`0fbfee1c57834541994097ba3b006d459e22c453`.  Its exact worker CLI was:

```bash
"$PY" -m oracle.oddcycle_pair_domain_runner "$RUN/run_spec.json" \
  --workers 1 --worker-index "$i" --worker-count 76
```

Worker indices ran in waves `0..13`, `14..27`, `28..41`, `42..55`,
`56..69`, and `70..75`.  The runner resumes successful manifests by
fingerprint.  Before any future recovery of an incomplete copy, first check:

```bash
test "$(sha256sum "$RUN/run_spec.json" | cut -d' ' -f1)" = \
  fb53bb4d8571f56d447480de603846f45a773921ebd45c7b05bee4bee1b4c8a1
```

The current preserved run is complete, so these worker commands must not be
relaunched.

The dual-ranking source commit was
`8969305f04e0de3c24365749c2354924ed19f8fe`.  Its deterministic worker CLI
was:

```bash
D="$RUN/dual-interior-ranking-v1"
i=0
tag="$(printf '%02d' "$i")"
"$PY" "$D/dual_interior_scan.py" worker \
  "$D/candidates.jsonl" "$D/shards/part-$tag.jsonl" \
  --index "$i" --count 14
```

Indices are `0..13`.  The pilot used the same command with
`pilot-candidates.jsonl` and `pilot-shards/`.  JSONL writes are append,
flush, and fsync; existing cell IDs are reused only after fingerprint
validation.  Nevertheless all 6,266 cells are complete, so this command is
provenance, not a pending resume action.  The one-off top-five exact wrapper
was not persisted; `top5-exact.jsonl` and its SHA-256 are the checkpoint and
must not be regenerated during ordinary resume.

The successful path-promotion launch was:

```bash
P="$RUN/cell-4321-path-promotion-v1"
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONUNBUFFERED=1 \
  "$PY" "$P/promotion.py"
```

This script is an overwrite-style complete replay, not a partial-resume
runner.  Ordinary resume must use `cd "$P" && sha256sum -c SHA256SUMS`
instead of executing it.

The CPU physical replay source is preserved as `replay.py`.  Its equivalent
single-threaded command is:

```bash
cd /home/jzb/code/nnv-longadv-hp-2ae03be
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/jzb/miniforge3/envs/quantum-harness/bin/python \
  tracks/qmc/results/no-negative-vibes/cell-4321-physical-v1/replay.py
```

This is also a complete replay, not a pending job.  On ordinary resume,
verify its two SHA sidecars and do not execute it.

## Resume commands

Do not run these until the user says `继续`.

First synchronize and verify the shared branch:

```bash
git fetch shared work/zibo/representation-cones
git switch work/zibo/representation-cones
git merge --ff-only shared/work/zibo/representation-cones
```

On WSL, after GitHub connectivity is restored, update the preserved clone and
run only the previously pending runner regressions:

```bash
cd /home/zibojin/code/nnv-final-verify
git fetch shared work/zibo/representation-cones
git merge --ff-only shared/work/zibo/representation-cones
cd tracks/qmc/solutions/no-negative-vibes
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -m pytest -q \
  tests/test_oddcycle_pair_domain_runner.py \
  tests/test_tp_exterior_extension.py
```

There are no pending cells in the completed oddcycle frontier or dual scan.
Resume must not repeat them.  A future continuation should start with
read-only SHA audits, the two pending runner regressions, certificate
packaging, and candidate comparison.  Only after that, and only with
explicit authorization, should it choose between:

1. retrying the 1,964 dual `SolverError` points with a secondary solver;
2. launching the preregistered adaptive TP minor-boundary search.

## Recommended next step

Keep the original `(1/1000,4/5,q=r=1)` alphabet as the simple frozen theorem
and use `cell-4321` as an independent exact robustness result.  On
continuation, first version the complete `cell-4321` rational matrices and
dual multipliers in a one-command production certificate, then compare
integer sizes, theorem margins, physical row margins, and paper exposition.
Do not begin another broad scan before that comparison.
