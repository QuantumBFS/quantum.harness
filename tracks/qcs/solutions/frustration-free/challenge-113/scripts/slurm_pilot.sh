#!/usr/bin/env bash
#SBATCH --job-name=c113-p80-pilot
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

cd "${CHALLENGE113_DEPLOYMENT}"
export PATH="$(dirname "${CHALLENGE113_UV}"):${PATH}"
export JAX_ENABLE_X64=1
export JAX_PLATFORMS=cpu
export CHALLENGE113_JAX_PLATFORM=cpu
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=${SLURM_CPUS_PER_TASK}"

test "$(<.source-revision)" = "${CHALLENGE113_EXPECTED_REVISION}"
"${CHALLENGE113_UV}" sync --frozen --group dev
"${CHALLENGE113_UV}" run python scripts/verify_deployment.py \
  --root "${CHALLENGE113_DEPLOYMENT}" \
  --archive "${CHALLENGE113_ARCHIVE_PATH}" \
  --expected-revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --expected-archive-sha256 "${CHALLENGE113_ARCHIVE_SHA256}" \
  --expected-evidence-revision "${CHALLENGE113_EVIDENCE_REVISION}"
"${CHALLENGE113_UV}" run python -c 'import jax; assert jax.config.x64_enabled; assert jax.devices()[0].platform == "cpu"; print({"jax_platform": "cpu", "x64": True}, flush=True)'
mkdir -p "${CHALLENGE113_RUN_ROOT}"
/usr/bin/time -v "${CHALLENGE113_UV}" run python -u run.py trial \
  --kind production --system two_qubit --segments 20 --gap 0.05 --shots exact \
  --perturbation-seed 0 --method model_hessian --dimension 4 \
  --model-seed 5 --seed 0 \
  --output "${CHALLENGE113_RUN_ROOT}/pilot"
"${CHALLENGE113_UV}" run python -u run.py validate --output "${CHALLENGE113_RUN_ROOT}/pilot"
