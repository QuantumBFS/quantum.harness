#!/usr/bin/env bash
#SBATCH --job-name=c113-production
#SBATCH --account=giggleliu
#SBATCH --qos=user_jiangweiqi
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=12:00:00
set -euo pipefail

: "${CHALLENGE113_DEPLOYMENT:?set immutable deployment directory}"
: "${CHALLENGE113_RUN_ROOT:?set revision/run-ID output directory}"
: "${CHALLENGE113_EXPECTED_REVISION:?set canonical git revision}"
: "${CHALLENGE113_ARCHIVE_PATH:?set immutable deployment archive path}"
: "${CHALLENGE113_ARCHIVE_SHA256:?set deployed archive SHA256}"
: "${CHALLENGE113_EVIDENCE_REVISION:?set measured evidence revision}"
: "${CHALLENGE113_UV:?set deployed uv executable}"
: "${SLURM_ARRAY_TASK_ID:?submit this script as a Slurm array}"
test "${CHALLENGE113_ACK_PRODUCTION:-}" = "1"

cd "${CHALLENGE113_DEPLOYMENT}"
export PATH="$(dirname "${CHALLENGE113_UV}"):${PATH}"
export JAX_ENABLE_X64=1
export JAX_PLATFORMS=cpu
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=${SLURM_CPUS_PER_TASK}"

test "$(<.source-revision)" = "${CHALLENGE113_EXPECTED_REVISION}"
"${CHALLENGE113_UV}" run python scripts/verify_deployment.py \
  --root "${CHALLENGE113_DEPLOYMENT}" \
  --archive "${CHALLENGE113_ARCHIVE_PATH}" \
  --expected-revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --expected-archive-sha256 "${CHALLENGE113_ARCHIVE_SHA256}" \
  --expected-evidence-revision "${CHALLENGE113_EVIDENCE_REVISION}"
"${CHALLENGE113_UV}" run python -c 'import jax; assert jax.config.x64_enabled; assert jax.devices()[0].platform == "cpu"'
mkdir -p "${CHALLENGE113_RUN_ROOT}"
"${CHALLENGE113_UV}" run python -u run.py sweep \
  --kind production \
  --shard-index "${SLURM_ARRAY_TASK_ID}" \
  --shard-count 9500 \
  --output "${CHALLENGE113_RUN_ROOT}/production"
