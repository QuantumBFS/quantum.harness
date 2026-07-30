#!/usr/bin/env bash
#SBATCH --job-name=rdp-phase7
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH --gres=gpu:1
#SBATCH --mem=42G
#SBATCH --time=04:00:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the clean Phase 7 checkout}"
: "${ROUTE_D_PLUS_RUN_ROOT:?set the isolated Phase 7 run root}"
: "${ROUTE_D_PLUS_RUN_ID:?set the Phase 7 run ID}"
: "${ROUTE_D_PLUS_PHASE6_RUN:?set the Phase 6 source run}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
solution_root="${repo_root}/tracks/qmc/solutions/BOTS-848"
run_root="${ROUTE_D_PLUS_RUN_ROOT}"
python="${repo_root}/.venv/bin/python"
capacity_protocol="${solution_root}/route_d_plus/future/phase7-capacity-protocol.json"
architecture="${ROUTE_D_PLUS_PHASE6_RUN}/architecture.json"
dispatch="${run_root}/phase7-dispatch.json"
integrals="${run_root}/shared/coulomb-integrals.npz"
stage_gate="${run_root}/phase7-stage-gate.json"
aggregate="${run_root}/phase7-aggregate.json"

mkdir -p "${run_root}/shared"
cd "${solution_root}"

nvidia-smi \
  --query-gpu=index,name,uuid,driver_version \
  --format=csv,noheader
test -n "${CUDA_VISIBLE_DEVICES:-}"

"${python}" -m route_d_plus.phase7 authorize \
  --repo-root "${repo_root}" \
  --run-root "${run_root}" \
  --run-id "${ROUTE_D_PLUS_RUN_ID}" \
  --architecture "${architecture}" \
  --checkpoint "${ROUTE_D_PLUS_PHASE6_RUN}/seeds/seed-848/checkpoint.json" \
  --checkpoint "${ROUTE_D_PLUS_PHASE6_RUN}/seeds/seed-1848/checkpoint.json" \
  --checkpoint "${ROUTE_D_PLUS_PHASE6_RUN}/seeds/seed-2848/checkpoint.json" \
  --capacity-protocol "${capacity_protocol}"

"${python}" -m route_d_plus.phase7 prepare-integrals \
  --output "${integrals}"

"${python}" -m route_d_plus.future.verify preflight \
  --dispatch "${dispatch}" \
  --repo-root "${repo_root}"

mapfile -t task_rows < <(
  "${python}" -m route_d_plus.future.verify list-tasks \
    --dispatch "${dispatch}"
)
if [[ "${#task_rows[@]}" -ne 7 ]]; then
  echo "Phase 7 requires exactly seven isolated tasks" >&2
  exit 2
fi

export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2
pids=()
for row in "${task_rows[@]}"; do
  IFS=$'\t' read -r task_id run_dir <<<"${row}"
  mkdir -p "${run_dir}"
  srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task=2 \
    "${python}" -m route_d_plus.phase7 worker \
    --repo-root "${repo_root}" \
    --dispatch "${dispatch}" \
    --task-id "${task_id}" \
    --run-dir "${run_dir}" \
    --integrals "${integrals}" \
    >"${run_dir}/stdout.log" 2>"${run_dir}/stderr.log" &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    status=1
  fi
done
if [[ "${status}" -ne 0 ]]; then
  exit "${status}"
fi

for row in "${task_rows[@]}"; do
  IFS=$'\t' read -r task_id run_dir <<<"${row}"
  "${python}" -m route_d_plus.future.verify verify-task \
    --dispatch "${dispatch}" \
    --task-id "${task_id}"
done

"${python}" -m route_d_plus.phase7 finalize \
  --dispatch "${dispatch}" \
  --stage-gate "${stage_gate}"

"${python}" -m route_d_plus.future.verify aggregate \
  --dispatch "${dispatch}" \
  --stage-gate "${stage_gate}" \
  --repo-root "${repo_root}" \
  --output "${aggregate}"

sha256sum \
  "${dispatch}" \
  "${stage_gate}" \
  "${aggregate}" \
  "${run_root}"/tasks/*/domain-certificate.json \
  "${run_root}"/tasks/*/task-certificate.json
