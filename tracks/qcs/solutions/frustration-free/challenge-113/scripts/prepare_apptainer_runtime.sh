#!/usr/bin/env bash
set -euo pipefail

: "${CHALLENGE113_DEPLOYMENT:?set extracted immutable source directory}"
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

verify_sha256_file() {
  local name="$1"
  local path="$2"
  local expected="${!name}"
  local actual
  if [[ ! "${expected}" =~ ^[0-9a-f]{64}$ ]]; then
    echo "${name} must be exactly 64 lowercase hex: expected=64-lowercase-hex actual=${expected}" >&2
    return 2
  fi
  if [[ ! -f "${path}" || -L "${path}" ]]; then
    echo "${name} path must be a regular non-symlink file: ${path}" >&2
    return 2
  fi
  actual="$(sha256sum -- "${path}" | awk '{print $1}')"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "${name} mismatch: expected=${expected} actual=${actual} path=${path}" >&2
    return 2
  fi
}

test "${CHALLENGE113_CLUSTER_PROFILE}" = "lasg02-cpu-v1"
ARCHIVE_BASENAME="${CHALLENGE113_ARCHIVE_PATH##*/}"
EXPECTED_ARCHIVE_BASENAME="challenge-113-${CHALLENGE113_EXPECTED_REVISION:0:7}.tar.gz"
if [[ ! "${ARCHIVE_BASENAME}" =~ ^challenge-113-[0-9a-f]{7}\.tar\.gz$ ]] \
  || [[ "${ARCHIVE_BASENAME}" != "${EXPECTED_ARCHIVE_BASENAME}" ]]; then
  echo "archive basename is unsafe or does not bind the revision" >&2
  exit 2
fi
CONTAINER_ARCHIVE="/${ARCHIVE_BASENAME}"
SOURCE_REVISION_PATH="${CHALLENGE113_DEPLOYMENT}/.source-revision"
if [[ ! -f "${SOURCE_REVISION_PATH}" || -L "${SOURCE_REVISION_PATH}" ]]; then
  echo "source revision path must be a regular non-symlink file: ${SOURCE_REVISION_PATH}" >&2
  exit 2
fi
ACTUAL_SOURCE_REVISION="$(<"${SOURCE_REVISION_PATH}")"
if [[ "${ACTUAL_SOURCE_REVISION}" != "${CHALLENGE113_EXPECTED_REVISION}" ]]; then
  echo "source revision mismatch: expected=${CHALLENGE113_EXPECTED_REVISION} actual=${ACTUAL_SOURCE_REVISION}" >&2
  exit 2
fi
verify_sha256_file CHALLENGE113_SIF_SHA256 "${CHALLENGE113_SIF_PATH}"
verify_sha256_file CHALLENGE113_ARCHIVE_SHA256 "${CHALLENGE113_ARCHIVE_PATH}"
verify_sha256_file CHALLENGE113_PYPROJECT_SHA256 "${CHALLENGE113_DEPLOYMENT}/pyproject.toml"
verify_sha256_file CHALLENGE113_UV_LOCK_SHA256 "${CHALLENGE113_DEPLOYMENT}/uv.lock"
verify_sha256_file CHALLENGE113_DEPLOYMENT_METADATA_SHA256 "${CHALLENGE113_DEPLOYMENT_METADATA}"
if [[ "${CHALLENGE113_ACK_NETWORKED_PREPARE:-}" != "1" ]]; then
  echo "set CHALLENGE113_ACK_NETWORKED_PREPARE=1 for the one-time frozen sync" >&2
  exit 2
fi

ISOLATED_CONTAINER_ARGS=(
  exec
  --no-home
  --cleanenv
  --net
  --network none
  --bind "${CHALLENGE113_DEPLOYMENT}:/workspace"
  --bind "${CHALLENGE113_ARCHIVE_PATH}:${CONTAINER_ARCHIVE}:ro"
  --bind "${CHALLENGE113_DEPLOYMENT_METADATA}:/challenge113-deployment.json:ro"
  --env JAX_ENABLE_X64=1
  --env JAX_PLATFORMS=cpu
  "${CHALLENGE113_SIF_PATH}"
)
NETWORKED_SYNC_ARGS=(
  exec
  --no-home
  --cleanenv
  --bind "${CHALLENGE113_DEPLOYMENT}:/workspace"
  "${CHALLENGE113_SIF_PATH}"
)

"${APPTAINER}" "${ISOLATED_CONTAINER_ARGS[@]}" python3 /workspace/scripts/verify_deployment.py \
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
"${APPTAINER}" "${NETWORKED_SYNC_ARGS[@]}" uv sync \
  --frozen --group dev --project /workspace
"${APPTAINER}" "${ISOLATED_CONTAINER_ARGS[@]}" /workspace/.venv/bin/python \
  /workspace/scripts/pre_submit_gate.py \
  --root /workspace \
  --deployment-metadata /challenge113-deployment.json \
  --expected-deployment-metadata-sha256 "${CHALLENGE113_DEPLOYMENT_METADATA_SHA256}" \
  --write-marker /workspace/.runtime/task10c-ready.json
