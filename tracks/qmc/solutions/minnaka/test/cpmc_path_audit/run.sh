#!/usr/bin/env bash
set -eo pipefail

audit_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${MKLROOT:-}" ]]; then
    source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
fi
set -u

slices="${1:-4}"
result_dir="${2:-${audit_root}/results/m${slices}-full}"
shift "$(( $# >= 2 ? 2 : $# ))"

make -C "${audit_root}" all
mkdir -p "${result_dir}"

set +e
{
    /usr/bin/time -v "${audit_root}/build/cpmc_audit" enumerate \
        --lx 2 --ly 2 --t 1 --u 8 --dt 0.1 \
        --n-up 2 --n-down 2 --slices "${slices}" \
        --output "${result_dir}" "$@"
} 2>&1 | tee "${result_dir}/run.log"
run_status="${PIPESTATUS[0]}"
set -e
if [[ "${run_status}" -ne 0 ]]; then
    exit "${run_status}"
fi

python3 "${audit_root}/summarize.py" --results "${result_dir}"
"${audit_root}/build/cpmc_audit" verify --results "${result_dir}"
