# Challenge 113: frustration-free sim-to-real control

This directory contains the pinned JAX implementation, restartable artifact
store, paired analysis, publication figures, and guarded production runners for
Challenge 113. Generated outputs belong under `results/` and are never tracked.

## Local verification and development

```bash
uv sync --frozen --group dev
uv run python -m pytest -q
CHALLENGE113_DEVELOPMENT_OUTPUT="$PWD/results/development-task10a" \
  bash scripts/run_development.sh
uv run python run.py validate --output results/development-task10a
```

The development runner explicitly selects JAX CPU with x64 enabled and writes
only to `results/development`. Override the device only by setting
`CHALLENGE113_JAX_PLATFORM` to the exact platform expected from JAX.

## Production safety gate

The approved runtime is the immutable LASG02 SIF
`uv-0.9.9-python3.12-bookworm-slim.sif`, SHA256
`2405a769d520e6d0f680c0f1dff0d9f92083724f1ffd85ea0c26b5e36defa323`.
It provides Python 3.12.12, uv 0.9.9, and glibc 2.36. The unchanged lock
resolves JAX/JAXLIB 0.11.0, NumPy 2.5.1, and SciPy 1.18.0.

Create a revision archive and external metadata from a clean challenge checkout:

```bash
export CHALLENGE113_EXPECTED_REVISION="$(git rev-parse HEAD)"
RUNTIME_DIR="$(mktemp -d)"
export CHALLENGE113_ARCHIVE_PATH="${RUNTIME_DIR}/challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.tar.gz"
export CHALLENGE113_DEPLOYMENT_METADATA="${RUNTIME_DIR}/deployment.json"
git archive --format=tar.gz -o "${CHALLENGE113_ARCHIVE_PATH}" \
  "${CHALLENGE113_EXPECTED_REVISION}" \
  tracks/qcs/solutions/frustration-free/challenge-113
uv run python scripts/write_deployment_metadata.py \
  --root . \
  --archive "${CHALLENGE113_ARCHIVE_PATH}" \
  --revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --output "${CHALLENGE113_DEPLOYMENT_METADATA}"
export CHALLENGE113_DEPLOYMENT_METADATA_SHA256="$(
  sha256sum "${CHALLENGE113_DEPLOYMENT_METADATA}" | awk '{print $1}'
)"
export CHALLENGE113_ACK_PRODUCTION=1
export CHALLENGE113_ARCHIVE_SHA256="$(sha256sum "${CHALLENGE113_ARCHIVE_PATH}" | awk '{print $1}')"
export CHALLENGE113_CHECK_ONLY=1
export CHALLENGE113_CLUSTER_PROFILE=lasg02-cpu-v1
export CHALLENGE113_EVIDENCE_REVISION=dd16192953c130d738716238525760de73343e09
export CHALLENGE113_JAX_PLATFORM=cpu
export CHALLENGE113_PRODUCTION_OUTPUT="${RUNTIME_DIR}/production"
export CHALLENGE113_PYPROJECT_SHA256=a51151c7947bc44ded698c9081df99b1b84a60ea51fcb041553c7cbfd60e4ecc
export CHALLENGE113_SIF_SHA256=2405a769d520e6d0f680c0f1dff0d9f92083724f1ffd85ea0c26b5e36defa323
export CHALLENGE113_UV_LOCK_SHA256=1d16a82284cebf3ae050ee79bcba4f2c9166820cf5fcae6a277334e1614a35dc
bash scripts/run_production.sh
```

The production plan contains 9,500 canonical trials. `run.py sweep` also
accepts `--shard-index I --shard-count N`; each shard binds the complete plan
but runs only positions whose canonical zero-based index is congruent to `I`
modulo `N`. Task 8 claims and atomic publication make retries restartable.

## LASG02 Apptainer gate

`scripts/calibrate_pilot.py` measures the representative two-qubit, 80-parameter
setup with a bounded 20–100-query sample. The current canonical local evidence
was measured from source revision
`dd16192953c130d738716238525760de73343e09`:

```bash
JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu \
  uv run python scripts/calibrate_pilot.py --queries 20 \
  --output results/task10a-dd16192/calibration.raw.json
uv run python run.py validate --output results/task10a-dd16192/pilot
uv run python -m pytest tests/test_evidence.py -q
```

Compact, tracked summaries and hashes are under `evidence/task10a/`; bulky raw
results remain ignored. Stage the current source into a new revision directory;
the old `ch113-runtime-d15818c` source tree must not be reused. The already
verified SIF may be referenced only by its exact path and hash:

```bash
scp "${CHALLENGE113_ARCHIVE_PATH}" lasg02-student090:~/.scratch/
scp "${CHALLENGE113_DEPLOYMENT_METADATA}" \
  "lasg02-student090:~/.scratch/challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.deployment.json"
ssh lasg02-student090
export CHALLENGE113_EXPECTED_REVISION=REVISION_FROM_LOCAL_GIT
export CHALLENGE113_ARCHIVE_PATH="$HOME/.scratch/challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.tar.gz"
export CHALLENGE113_DEPLOYMENT_METADATA="$HOME/.scratch/challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.deployment.json"
export CHALLENGE113_DEPLOYMENT_METADATA_SHA256="$(
  sha256sum "${CHALLENGE113_DEPLOYMENT_METADATA}" | awk '{print $1}'
)"
export CHALLENGE113_DEPLOYMENT="$HOME/.scratch/ch113-runtime-${CHALLENGE113_EXPECTED_REVISION:0:7}/tracks/qcs/solutions/frustration-free/challenge-113"
mkdir -p "$HOME/.scratch/ch113-runtime-${CHALLENGE113_EXPECTED_REVISION:0:7}"
tar -xzf "${CHALLENGE113_ARCHIVE_PATH}" \
  -C "$HOME/.scratch/ch113-runtime-${CHALLENGE113_EXPECTED_REVISION:0:7}"
printf '%s\n' "${CHALLENGE113_EXPECTED_REVISION}" \
  > "${CHALLENGE113_DEPLOYMENT}/.source-revision"
export CHALLENGE113_SIF_PATH="$HOME/.scratch/ch113-runtime-d15818c/uv-0.9.9-python3.12-bookworm-slim.sif"
export CHALLENGE113_SIF_SHA256=2405a769d520e6d0f680c0f1dff0d9f92083724f1ffd85ea0c26b5e36defa323
export CHALLENGE113_ARCHIVE_SHA256="$(sha256sum "${CHALLENGE113_ARCHIVE_PATH}" | awk '{print $1}')"
export CHALLENGE113_PYPROJECT_SHA256=a51151c7947bc44ded698c9081df99b1b84a60ea51fcb041553c7cbfd60e4ecc
export CHALLENGE113_UV_LOCK_SHA256=1d16a82284cebf3ae050ee79bcba4f2c9166820cf5fcae6a277334e1614a35dc
export CHALLENGE113_EVIDENCE_REVISION=dd16192953c130d738716238525760de73343e09
export CHALLENGE113_CLUSTER_PROFILE=lasg02-cpu-v1
export CHALLENGE113_ACK_NETWORKED_PREPARE=1
bash "${CHALLENGE113_DEPLOYMENT}/scripts/prepare_apptainer_runtime.sh"
```

Preparation first verifies every source/runtime hash, then requires the explicit
acknowledgement above for the sole network-enabled container command:
`uv sync --frozen --group dev --project /workspace`. That command uses
`--no-home --cleanenv` but intentionally does not create a network namespace;
it runs no qcontrol, smoke, analysis, scheduler, or physics code. This is a
one-time frozen networked preparation, not a wheelhouse or offline preparation.
uv 0.9.9 verifies distributions against the hashes in the unchanged frozen
lock; `uv sync` has no separate sync-level `--require-hashes` option.

The immediately following runtime smoke and all pilot/array calls are
strictly network-isolated and no-sync, use
`apptainer exec --no-home --cleanenv --net --network none`, bind source
explicitly, and fail unless `.venv` plus the hash-bound pre-submit marker are
current. LASG02 Apptainer 1.3.4 accepted this unprivileged network namespace in
a hash-verified Python 3.12.12 no-physics probe on 2026-07-30.
The separate scheduler profile is `scripts/lasg02_profile.env`:
account `chenkun2025`, QOS `user_student090`, partition `ihicnormal`.

```bash
# Future Task 10C pilot only; do not submit the array before this validates.
export CHALLENGE113_RUN_ROOT="$HOME/.scratch/ch113-runs/${CHALLENGE113_EXPECTED_REVISION:0:7}/pilot-001"
sbatch "${CHALLENGE113_DEPLOYMENT}/scripts/slurm_pilot.sh"

# Production remains withheld pending pilot timing/resource review:
# CHALLENGE113_ACK_PRODUCTION=1 sbatch --array=0-9499%MEASURED_CONCURRENCY \
#   "${CHALLENGE113_DEPLOYMENT}/scripts/slurm_production_array.sh"
```

No mutable image tag, source directory, package resolution, or platform
fallback is accepted by these gates.
