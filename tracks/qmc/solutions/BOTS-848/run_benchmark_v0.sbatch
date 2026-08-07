#!/usr/bin/env bash
#SBATCH --job-name=bots848-v0
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=12G
#SBATCH --time=00:10:00

set -euo pipefail

: "${BOTS848_REPO_ROOT:?set the clean repository checkout}"
: "${BOTS848_RUN_ROOT:?set the isolated result directory}"

repo_root="$(cd -- "${BOTS848_REPO_ROOT}" && pwd)"
solution_root="${repo_root}/tracks/qmc/solutions/BOTS-848"
python="${repo_root}/.venv/bin/python"
run_root="${BOTS848_RUN_ROOT}"

test -x "${python}"
test -n "${CUDA_VISIBLE_DEVICES:-}"
mkdir -p "${run_root}"

cd "${repo_root}"
git diff --quiet
git diff --cached --quiet
test -z "$(git status --porcelain --untracked-files=no)"
git rev-parse HEAD | tee "${run_root}/source-revision.txt"
git status --porcelain --untracked-files=no >"${run_root}/git-status.txt"

nvidia-smi \
  --query-gpu=index,name,uuid,driver_version \
  --format=csv,noheader |
  tee "${run_root}/gpu.csv"

"${python}" -m pytest \
  "${solution_root}/tests/test_conventions.py" \
  "${solution_root}/tests/test_lll_coulomb.py" \
  "${solution_root}/tests/test_fock_ed.py" \
  "${solution_root}/tests/test_ed_oracle.py" \
  "${solution_root}/tests/test_projected_nqs.py" \
  "${solution_root}/tests/test_nqs_benchmark.py" \
  -q

"${python}" -u "${solution_root}/run_nqs_benchmark.py" \
  --output "${run_root}/run.json" \
  --samples 20000

sha256sum \
  "${run_root}/run.json" \
  "${run_root}/source-revision.txt" \
  "${run_root}/git-status.txt" \
  "${run_root}/gpu.csv" |
  tee "${run_root}/sha256sums.txt"
