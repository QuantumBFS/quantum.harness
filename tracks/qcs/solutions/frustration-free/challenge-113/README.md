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

Local production requires a clean checkout, an exact revision match, an
explicit JAX platform, acknowledgement, an exact archive, and external
deployment metadata. The following check-only workflow is executable from this
challenge directory and reaches the final gate without writing into the source
tree:

```bash
export CHALLENGE113_ACK_PRODUCTION=1
export CHALLENGE113_EXPECTED_REVISION="$(git rev-parse HEAD)"
export CHALLENGE113_EVIDENCE_REVISION=dd16192953c130d738716238525760de73343e09
export CHALLENGE113_JAX_PLATFORM=cpu
export CHALLENGE113_CHECK_ONLY=1
RUNTIME_DIR="$(mktemp -d)"
export CHALLENGE113_ARCHIVE_PATH="${RUNTIME_DIR}/challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.tar.gz"
export CHALLENGE113_DEPLOYMENT_METADATA="${RUNTIME_DIR}/deployment.json"
export CHALLENGE113_PRODUCTION_OUTPUT="${RUNTIME_DIR}/production"
git archive --format=tar.gz -o "${CHALLENGE113_ARCHIVE_PATH}" \
  "${CHALLENGE113_EXPECTED_REVISION}" \
  tracks/qcs/solutions/frustration-free/challenge-113
export CHALLENGE113_ARCHIVE_SHA256="$(
  sha256sum "${CHALLENGE113_ARCHIVE_PATH}" | awk '{print $1}'
)"
export CHALLENGE113_EVIDENCE_INDEX_SHA256="$(
  sha256sum evidence/task10a/index.json | awk '{print $1}'
)"
export CHALLENGE113_REPORT_SHA256="$(
  sha256sum REPORT.md | awk '{print $1}'
)"
uv run python - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "archive_name": Path(os.environ["CHALLENGE113_ARCHIVE_PATH"]).name,
    "archive_sha256": os.environ["CHALLENGE113_ARCHIVE_SHA256"],
    "evidence_index_sha256": os.environ["CHALLENGE113_EVIDENCE_INDEX_SHA256"],
    "report_sha256": os.environ["CHALLENGE113_REPORT_SHA256"],
    "revision": os.environ["CHALLENGE113_EXPECTED_REVISION"],
    "schema_version": 1,
}
Path(os.environ["CHALLENGE113_DEPLOYMENT_METADATA"]).write_text(
    json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
)
PY
bash scripts/run_production.sh
```

The production plan contains 9,500 canonical trials. `run.py sweep` also
accepts `--shard-index I --shard-count N`; each shard binds the complete plan
but runs only positions whose canonical zero-based index is congruent to `I`
modulo `N`. Task 8 claims and atomic publication make retries restartable.

## Cluster gate

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
results remain ignored. `scripts/slurm_pilot.sh` runs one full budget-2,000
representative trial. Only after that artifact validates should
`scripts/slurm_production_array.sh` be submitted with an explicitly measured
array concurrency and resource class:

```bash
sbatch --array=0-9499%CONCURRENCY \
  --account=ACCOUNT --qos=QOS --partition=PARTITION \
  --export=ALL,CHALLENGE113_ACK_PRODUCTION=1,CHALLENGE113_DEPLOYMENT=DEPLOYMENT,CHALLENGE113_DEPLOYMENT_METADATA=DEPLOYMENT_METADATA,CHALLENGE113_RUN_ROOT=RUN_ROOT,CHALLENGE113_EXPECTED_REVISION=REVISION,CHALLENGE113_ARCHIVE_PATH=ARCHIVE_PATH,CHALLENGE113_ARCHIVE_SHA256=ARCHIVE_SHA256,CHALLENGE113_EVIDENCE_REVISION=EVIDENCE_REVISION,CHALLENGE113_UV=UV \
  scripts/slurm_production_array.sh
```

Deploy only `git archive` output from a committed revision, then add a
runtime-only canonical `.deployment.json` containing revision, archive,
evidence-index, and report SHA256 bindings. Keep the actual archive available
to every production entry point through `CHALLENGE113_ARCHIVE_PATH`. This local
verification supplies every required value:

```bash
uv run python scripts/verify_deployment.py \
  --root "${CHALLENGE113_DEPLOYMENT}" \
  --archive "${CHALLENGE113_ARCHIVE_PATH}" \
  --deployment-metadata "${CHALLENGE113_DEPLOYMENT_METADATA}" \
  --expected-revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --expected-archive-sha256 "${CHALLENGE113_ARCHIVE_SHA256}" \
  --expected-evidence-revision "${CHALLENGE113_EVIDENCE_REVISION}"
```

Use a revision/run-ID output directory shared by all array elements. Production
entry points reject stale evidence/report/archive metadata. Deployment and
output paths are runtime inputs and are intentionally not committed.
