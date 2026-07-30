#!/usr/bin/env bash
#SBATCH --job-name=q66-validator-snapshot
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=stage-validator-snapshot-%j.out
#SBATCH --error=stage-validator-snapshot-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
snapshot_id=${Q66_SNAPSHOT_ID:?Q66_SNAPSHOT_ID is required}
matrix_relative=${Q66_SNAPSHOT_MATRIX_RELATIVE:-research/requests/validator/dev-matrix-v1.json}
source_root=${Q66_SNAPSHOT_SOURCE_ROOT:-${project_root}}
if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    printf 'invalid snapshot ID: %s\n' "${snapshot_id}" >&2
    exit 2
fi
if [[ "${matrix_relative}" == /* || "${matrix_relative}" == *..* ]]; then
    printf 'invalid snapshot matrix path: %s\n' "${matrix_relative}" >&2
    exit 2
fi
snapshot_root="${project_root}/results/validator/snapshots/${snapshot_id}"
staging_root="${snapshot_root}.staging-${SLURM_JOB_ID}"
checksums_path="${snapshot_root}.checksums-${SLURM_JOB_ID}"
if [[ -e "${snapshot_root}" || -e "${staging_root}" || -e "${checksums_path}" ]]; then
    printf 'snapshot path already exists: %s\n' "${snapshot_root}" >&2
    exit 2
fi

mkdir -p "${staging_root}/src" "$(dirname "${staging_root}/${matrix_relative}")"
cp -a "${source_root}/src/." "${staging_root}/src/"
cp "${source_root}/pyproject.toml" "${staging_root}/pyproject.toml"
cp "${project_root}/${matrix_relative}" "${staging_root}/${matrix_relative}"
(
    cd "${staging_root}"
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum \
        > "${checksums_path}"
)
mv "${checksums_path}" "${staging_root}/snapshot-checksums.sha256"
mv "${staging_root}" "${snapshot_root}"
sha256sum "${snapshot_root}/snapshot-checksums.sha256"
printf 'snapshot_root=%s\n' "${snapshot_root}"
