#!/usr/bin/env bash

: "${CHALLENGE113_DEPLOYMENT:?set extracted immutable source directory}"
: "${CHALLENGE113_RUN_ROOT:?set revision/run-ID output directory}"
: "${CHALLENGE113_EXPECTED_REVISION:?set canonical source revision}"
: "${CHALLENGE113_ARCHIVE_PATH:?set current source archive path}"
: "${CHALLENGE113_ARCHIVE_SHA256:?set current source archive SHA256}"
: "${CHALLENGE113_DEPLOYMENT_METADATA:?set external deployment metadata path}"
: "${CHALLENGE113_DEPLOYMENT_METADATA_SHA256:?set expected deployment metadata SHA256}"
: "${CHALLENGE113_EVIDENCE_REVISION:?set measured evidence revision}"
: "${CHALLENGE113_SIF_PATH:?set immutable Apptainer SIF path}"
: "${CHALLENGE113_SIF_SHA256:?set expected SIF SHA256}"
: "${CHALLENGE113_PYPROJECT_SHA256:?set expected pyproject.toml SHA256}"
: "${CHALLENGE113_UV_LOCK_SHA256:?set expected uv.lock SHA256}"
: "${CHALLENGE113_CLUSTER_PROFILE:?set approved cluster profile}"
if [[ -z "${CHALLENGE113_APPTAINER:-}" ]]; then
  module load apptainer/1.3.4
fi
APPTAINER="${CHALLENGE113_APPTAINER:-apptainer}"

test "${CHALLENGE113_CLUSTER_PROFILE}" = "lasg02-cpu-v1"
ARCHIVE_BASENAME="${CHALLENGE113_ARCHIVE_PATH##*/}"
EXPECTED_ARCHIVE_BASENAME="challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.tar.gz"
if [[ ! "${ARCHIVE_BASENAME}" =~ ^challenge-113-[0-9a-f]{7}\.tar\.gz$ ]] \
  || [[ "${ARCHIVE_BASENAME}" != "${EXPECTED_ARCHIVE_BASENAME}" ]]; then
  echo "archive basename is unsafe or does not bind the revision" >&2
  exit 2
fi
CONTAINER_ARCHIVE="/${ARCHIVE_BASENAME}"
test "$(<"${CHALLENGE113_DEPLOYMENT}/.source-revision")" = "${CHALLENGE113_EXPECTED_REVISION}"
test "$(sha256sum "${CHALLENGE113_SIF_PATH}" | awk '{print $1}')" = "${CHALLENGE113_SIF_SHA256}"
test "$(sha256sum "${CHALLENGE113_ARCHIVE_PATH}" | awk '{print $1}')" = "${CHALLENGE113_ARCHIVE_SHA256}"
test "$(sha256sum "${CHALLENGE113_DEPLOYMENT}/pyproject.toml" | awk '{print $1}')" = "${CHALLENGE113_PYPROJECT_SHA256}"
test "$(sha256sum "${CHALLENGE113_DEPLOYMENT}/uv.lock" | awk '{print $1}')" = "${CHALLENGE113_UV_LOCK_SHA256}"
test "$(sha256sum "${CHALLENGE113_DEPLOYMENT_METADATA}" | awk '{print $1}')" = "${CHALLENGE113_DEPLOYMENT_METADATA_SHA256}"
test -x "${CHALLENGE113_DEPLOYMENT}/.venv/bin/python"
test -f "${CHALLENGE113_DEPLOYMENT}/.runtime/task10c-ready.json"
mkdir -p "${CHALLENGE113_RUN_ROOT}"

CONTAINER_ARGS=(
  exec
  --no-home
  --cleanenv
  --net
  --network none
  --bind "${CHALLENGE113_DEPLOYMENT}:/workspace"
  --bind "${CHALLENGE113_RUN_ROOT}:/output"
  --bind "${CHALLENGE113_ARCHIVE_PATH}:${CONTAINER_ARCHIVE}:ro"
  --bind "${CHALLENGE113_DEPLOYMENT_METADATA}:/challenge113-deployment.json:ro"
  --env JAX_ENABLE_X64=1
  --env JAX_PLATFORMS=cpu
  --env OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
  --env UV_OFFLINE=1
  "${CHALLENGE113_SIF_PATH}"
)

"${APPTAINER}" "${CONTAINER_ARGS[@]}" python3 /workspace/scripts/verify_deployment.py \
  --root /workspace \
  --archive "${CONTAINER_ARCHIVE}" \
  --deployment-metadata /challenge113-deployment.json \
  --expected-revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --expected-archive-sha256 "${CHALLENGE113_ARCHIVE_SHA256}" \
  --expected-evidence-revision "${CHALLENGE113_EVIDENCE_REVISION}" \
  --expected-sif-sha256 "${CHALLENGE113_SIF_SHA256}" \
  --expected-deployment-metadata-sha256 "${CHALLENGE113_DEPLOYMENT_METADATA_SHA256}" \
  --expected-pyproject-sha256 "${CHALLENGE113_PYPROJECT_SHA256}" \
  --expected-uv-lock-sha256 "${CHALLENGE113_UV_LOCK_SHA256}" \
  --expected-cluster-profile "${CHALLENGE113_CLUSTER_PROFILE}"
"${APPTAINER}" "${CONTAINER_ARGS[@]}" /workspace/.venv/bin/python \
  /workspace/scripts/pre_submit_gate.py \
  --root /workspace \
  --deployment-metadata /challenge113-deployment.json \
  --expected-deployment-metadata-sha256 "${CHALLENGE113_DEPLOYMENT_METADATA_SHA256}" \
  --check-marker /workspace/.runtime/task10c-ready.json
