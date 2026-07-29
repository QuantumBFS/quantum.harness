#!/bin/bash
set -euo pipefail

usage_error() {
    echo "$1" >&2
    exit 64
}

if (( $# != 4 )); then
    usage_error "usage: download_pilot.sh <ssh-host> <absolute-remote-root> <absolute-local-root> <absolute-python>"
fi

SSH_HOST="$1"
REMOTE_ROOT="$2"
LOCAL_ROOT="$3"
PYTHON="$4"

if [[ -z "${SSH_HOST}" ]]; then
    usage_error "ssh-host must not be empty"
fi
if [[ "${REMOTE_ROOT}" != /* ]]; then
    usage_error "remote root must be an absolute path"
fi
if [[ "${LOCAL_ROOT}" != /* ]]; then
    usage_error "local root must be an absolute path"
fi
if [[ "${PYTHON}" != /* || ! -f "${PYTHON}" || ! -x "${PYTHON}" ]]; then
    echo "python must be an absolute path to a regular executable" >&2
    exit 66
fi

SOURCE_ID="${SSH_HOST}:${REMOTE_ROOT%/}"
STATE_ROOT="${LOCAL_ROOT}.download-state"
CLAIM_ROOT="${LOCAL_ROOT}.download-claim"
LEGACY_SOURCE="${LOCAL_ROOT}.download-source"
EXPECTED_VERIFICATION='{"cells": 96, "status": "verified", "trajectories": 96}'

LOCAL_PARENT="$(dirname -- "${LOCAL_ROOT}")"
if [[ -L "${LOCAL_PARENT}" || ! -d "${LOCAL_PARENT}" ]] || \
   [[ "$(realpath -s -- "${LOCAL_PARENT}")" != "$(realpath -e -- "${LOCAL_PARENT}")" ]]; then
    echo "local root parent must be an existing real non-symlink directory" >&2
    exit 73
fi
umask 077
if ! mkdir -- "${CLAIM_ROOT}" 2>/dev/null; then
    echo "another or stale Pilot download invocation claim exists: ${CLAIM_ROOT}" >&2
    exit 75
fi
CLAIM_ID="$(stat -c '%d:%i' -- "${CLAIM_ROOT}")"
CLAIM_OWNED=1

release_claim() {
    local current_id=""
    if (( CLAIM_OWNED == 0 )); then
        return 0
    fi
    if [[ -L "${CLAIM_ROOT}" || ! -d "${CLAIM_ROOT}" ]]; then
        echo "owned invocation claim changed; preserving it for diagnosis" >&2
        return 1
    fi
    current_id="$(stat -c '%d:%i' -- "${CLAIM_ROOT}")"
    if [[ "${current_id}" != "${CLAIM_ID}" ]]; then
        echo "owned invocation claim identity changed; preserving it for diagnosis" >&2
        return 1
    fi
    if ! rmdir -- "${CLAIM_ROOT}"; then
        echo "owned invocation claim is not empty; preserving it for diagnosis" >&2
        return 1
    fi
    CLAIM_OWNED=0
}

fail_closed() {
    local status="$1"
    shift
    echo "$*" >&2
    release_claim || true
    exit "${status}"
}

publish_file() {
    local destination="$1"
    local payload="$2"
    local temporary="${destination}.new.$$.${RANDOM}"
    if [[ -L "${destination}" || -e "${destination}" ]]; then
        fail_closed 73 "refusing to replace existing state file: ${destination}"
    fi
    if ! (set -o noclobber; printf '%s' "${payload}" > "${temporary}"); then
        fail_closed 73 "could not exclusively create temporary state file"
    fi
    chmod 0444 -- "${temporary}"
    if ! ln -- "${temporary}" "${destination}"; then
        fail_closed 73 "could not atomically publish state file: ${destination}"
    fi
    rm -- "${temporary}"
}

if [[ -L "${LOCAL_ROOT}" || ( -e "${LOCAL_ROOT}" && ! -d "${LOCAL_ROOT}" ) ]]; then
    fail_closed 73 "local root must be a directory, not a file or symlink"
fi
if [[ -L "${STATE_ROOT}" || ( -e "${STATE_ROOT}" && ! -d "${STATE_ROOT}" ) ]]; then
    fail_closed 73 "download state root must be a real directory"
fi
if [[ ! -e "${STATE_ROOT}" ]] && ! mkdir -- "${STATE_ROOT}"; then
    fail_closed 73 "could not exclusively create download state root"
fi
if [[ -L "${STATE_ROOT}" || ! -d "${STATE_ROOT}" ]]; then
    fail_closed 73 "download state root must be a real directory"
fi

SOURCE_FILE="${STATE_ROOT}/source"
COMPLETION_FILE="${STATE_ROOT}/verified"
LOG_ROOT="${STATE_ROOT}/logs"

for state_file in "${SOURCE_FILE}" "${COMPLETION_FILE}"; do
    if [[ -L "${state_file}" ]]; then
        fail_closed 73 "state files must not be symlinks: ${state_file}"
    fi
    if [[ -e "${state_file}" && ! -f "${state_file}" ]]; then
        fail_closed 73 "state files must be regular files: ${state_file}"
    fi
done
if [[ -L "${LOG_ROOT}" || ( -e "${LOG_ROOT}" && ! -d "${LOG_ROOT}" ) ]]; then
    fail_closed 73 "transfer log root must be a real directory"
fi

BOOTSTRAP_EXISTING=0
if [[ -d "${LOCAL_ROOT}" ]]; then
    shopt -s nullglob dotglob
    EXISTING_ENTRIES=("${LOCAL_ROOT}"/*)
    shopt -u nullglob dotglob
else
    EXISTING_ENTRIES=()
fi

if [[ -e "${SOURCE_FILE}" ]]; then
    if [[ "$(<"${SOURCE_FILE}")" != "${SOURCE_ID}" ]]; then
        fail_closed 73 "local root is marked for a different Pilot source"
    fi
elif (( ${#EXISTING_ENTRIES[@]} != 0 )); then
    if [[ -L "${LEGACY_SOURCE}" || ! -f "${LEGACY_SOURCE}" ]] || \
       [[ "$(<"${LEGACY_SOURCE}")" != "${SOURCE_ID}" ]]; then
        fail_closed 73 "refusing an unmarked nonempty local root"
    fi
    publish_file "${SOURCE_FILE}" "${SOURCE_ID}"$'\n'
    BOOTSTRAP_EXISTING=1
else
    publish_file "${SOURCE_FILE}" "${SOURCE_ID}"$'\n'
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOLUTION_ROOT="$(dirname -- "${SCRIPT_DIR}")"

verify_local_root() {
    local output=""
    if ! output="$(
        cd "${SOLUTION_ROOT}"
        PYTHONPATH="${SOLUTION_ROOT}/src" "${PYTHON}" scripts/run_pilot.py verify \
            --run-spec "${LOCAL_ROOT%/}/run_spec.json"
    )"; then
        return 1
    fi
    if [[ "${output}" != "${EXPECTED_VERIFICATION}" ]]; then
        echo "semantic verifier did not report exactly 96 cells and trajectories" >&2
        return 1
    fi
    printf '%s\n' "${output}"
}

if [[ -e "${COMPLETION_FILE}" ]]; then
    EXPECTED_COMPLETION="${SOURCE_ID}"$'\n'"${EXPECTED_VERIFICATION}"
    if [[ "$(<"${COMPLETION_FILE}")" != "${EXPECTED_COMPLETION}" ]]; then
        fail_closed 73 "verified completion state does not match this source"
    fi
    if ! verify_local_root; then
        fail_closed 74 "completed Pilot root failed semantic re-verification"
    fi
    release_claim || exit 73
    exit 0
fi

if (( BOOTSTRAP_EXISTING == 1 )); then
    if ! verify_local_root; then
        fail_closed 74 "legacy Pilot root failed semantic verification"
    fi
    publish_file \
        "${COMPLETION_FILE}" \
        "${SOURCE_ID}"$'\n'"${EXPECTED_VERIFICATION}"$'\n'
    release_claim || exit 73
    exit 0
fi

if [[ ! -e "${LOG_ROOT}" ]] && ! mkdir -- "${LOG_ROOT}"; then
    fail_closed 73 "could not exclusively create transfer log root"
fi
if [[ -L "${LOG_ROOT}" || ! -d "${LOG_ROOT}" ]]; then
    fail_closed 73 "transfer log root must be a real directory"
fi
shopt -s nullglob dotglob
LOG_ENTRIES=("${LOG_ROOT}"/*)
shopt -u nullglob dotglob
for log_entry in "${LOG_ENTRIES[@]}"; do
    if [[ -L "${log_entry}" ]]; then
        fail_closed 73 "transfer logs must not be symlinks: ${log_entry}"
    fi
done
TRANSFER_LOG="${LOG_ROOT}/transfer-$$-${RANDOM}.log"
set -o noclobber
if ! exec {TRANSFER_LOG_FD}> "${TRANSFER_LOG}"; then
    set +o noclobber
    fail_closed 73 "could not exclusively create transfer log"
fi
set +o noclobber

mkdir -- "${LOCAL_ROOT}" 2>/dev/null || [[ -d "${LOCAL_ROOT}" ]] || \
    fail_closed 73 "could not create local root"
if ! rsync \
    --archive \
    --checksum \
    --partial \
    --itemize-changes \
    "${SSH_HOST}:${REMOTE_ROOT%/}/" \
    "${LOCAL_ROOT%/}/" 2>&1 | tee "/dev/fd/${TRANSFER_LOG_FD}"; then
    fail_closed 74 "Pilot transfer failed; resumable state was preserved"
fi
exec {TRANSFER_LOG_FD}>&-

if ! verify_local_root; then
    fail_closed 74 "downloaded Pilot root failed semantic verification"
fi
publish_file \
    "${COMPLETION_FILE}" \
    "${SOURCE_ID}"$'\n'"${EXPECTED_VERIFICATION}"$'\n'
release_claim || exit 73
