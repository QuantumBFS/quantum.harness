#!/usr/bin/env bash
#SBATCH --job-name=q66-build-env
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=build-env-%j.out
#SBATCH --error=build-env-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
venv_dir=${project_root}/.venv-q66-v1

module load anaconda3/2023.09
pushd "${project_root}/environment" >/dev/null
sha256sum --check wheels.sha256
popd >/dev/null
python3 -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install \
    --no-cache-dir \
    --no-index \
    --find-links "${project_root}/environment/wheels" \
    --require-hashes \
    --requirement "${project_root}/environment/requirements.lock"
"${venv_dir}/bin/python" -m pip check
"${venv_dir}/bin/python" -m pip freeze --all
