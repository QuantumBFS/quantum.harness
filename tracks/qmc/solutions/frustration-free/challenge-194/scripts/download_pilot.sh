#!/bin/bash
set -euo pipefail

if (( $# != 4 )); then
    echo "usage: download_pilot.sh <ssh-host> <absolute-remote-root> <absolute-local-root> <absolute-python>" >&2
    exit 64
fi

SSH_HOST="$1"
REMOTE_ROOT="$2"
LOCAL_ROOT="$3"
PYTHON="$4"

if [[ -z "${SSH_HOST}" ]]; then
    echo "ssh-host must not be empty" >&2
    exit 64
fi
if [[ "${REMOTE_ROOT}" != /* ]]; then
    echo "remote root must be an absolute path" >&2
    exit 64
fi
if [[ "${LOCAL_ROOT}" != /* ]]; then
    echo "local root must be an absolute path" >&2
    exit 64
fi
if [[ "${PYTHON}" != /* || ! -f "${PYTHON}" || ! -x "${PYTHON}" ]]; then
    echo "python must be an absolute path to a regular executable" >&2
    exit 66
fi
if [[ -L "${LOCAL_ROOT}" || ( -e "${LOCAL_ROOT}" && ! -d "${LOCAL_ROOT}" ) ]]; then
    echo "local root must be a directory, not a file or symlink" >&2
    exit 73
fi

SOURCE_ID="${SSH_HOST}:${REMOTE_ROOT%/}"
SOURCE_MARKER="${LOCAL_ROOT}.download-source"
TRANSFER_LOG="${LOCAL_ROOT}.transfer.log"

if [[ -e "${SOURCE_MARKER}" ]]; then
    if [[ ! -f "${SOURCE_MARKER}" || -L "${SOURCE_MARKER}" ]] || \
       [[ "$(<"${SOURCE_MARKER}")" != "${SOURCE_ID}" ]]; then
        echo "local root is marked for a different Pilot source" >&2
        exit 73
    fi
elif [[ -d "${LOCAL_ROOT}" ]]; then
    shopt -s nullglob dotglob
    EXISTING_ENTRIES=("${LOCAL_ROOT}"/*)
    shopt -u nullglob dotglob
    if (( ${#EXISTING_ENTRIES[@]} != 0 )); then
        echo "refusing an unmarked nonempty local root" >&2
        exit 73
    fi
fi

mkdir -p -- "$(dirname -- "${LOCAL_ROOT}")"
mkdir -- "${LOCAL_ROOT}" 2>/dev/null || [[ -d "${LOCAL_ROOT}" ]]
if [[ ! -e "${SOURCE_MARKER}" ]]; then
    printf '%s\n' "${SOURCE_ID}" > "${SOURCE_MARKER}"
fi

rsync \
    --archive \
    --checksum \
    --partial \
    --itemize-changes \
    "${SSH_HOST}:${REMOTE_ROOT%/}/" \
    "${LOCAL_ROOT%/}/" | tee -a "${TRANSFER_LOG}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOLUTION_ROOT="$(dirname -- "${SCRIPT_DIR}")"
cd "${SOLUTION_ROOT}"
PYTHONPATH="${SOLUTION_ROOT}/src" "${PYTHON}" scripts/run_pilot.py verify \
    --run-spec "${LOCAL_ROOT%/}/run_spec.json"
