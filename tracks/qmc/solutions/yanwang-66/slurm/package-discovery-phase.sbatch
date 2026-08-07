#!/usr/bin/env bash
#SBATCH --job-name=q66-package-discovery
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=package-discovery-%j.out
#SBATCH --error=package-discovery-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
array_job_id=${Q66_DISCOVERY_ARRAY_JOB_ID:?Q66_DISCOVERY_ARRAY_JOB_ID is required}
if [[ ! "${array_job_id}" =~ ^[0-9]+$ ]]; then
    printf 'invalid discovery array job ID: %s\n' "${array_job_id}" >&2
    exit 2
fi
phase_root=${project_root}/results/discovery/phase-1
results_root=${phase_root}/${array_job_id}
transfer_root=${project_root}/results/transfers/phase-1
archive=${transfer_root}/phase-1-${array_job_id}.tar
archive_staging=${archive}.staging-${SLURM_JOB_ID}
checksum=${archive}.sha256
if [[ -e "${archive}" || -e "${archive_staging}" || -e "${checksum}" ]]; then
    printf 'archive output already exists: %s\n' "${archive}" >&2
    exit 2
fi
if [[ ! -d "${results_root}" ]]; then
    printf 'discovery result root is missing: %s\n' "${results_root}" >&2
    exit 2
fi

shopt -s nullglob
entries=("${results_root}"/*)
if (( ${#entries[@]} != 280 )); then
    printf 'expected 280 result groups, found %s\n' "${#entries[@]}" >&2
    exit 2
fi
for ((group_index = 0; group_index < 280; group_index++)); do
    group_root=$(printf '%s/group-%03d' "${results_root}" "${group_index}")
    if [[ ! -f "${group_root}/group-manifest.json" ]]; then
        printf 'group manifest is missing: %s\n' "${group_root}" >&2
        exit 2
    fi
done

mkdir -p "${transfer_root}"
tar --sort=name --format=posix -cf "${archive_staging}" \
    -C "${phase_root}" "${array_job_id}"
mv "${archive_staging}" "${archive}"
sha256sum "${archive}" > "${checksum}"
cat "${checksum}"
du -h "${archive}"
