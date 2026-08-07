#!/usr/bin/env bash
#SBATCH --job-name=q66-isolation-probe
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=validator-isolation-probe-%j.out
#SBATCH --error=validator-isolation-probe-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
probe_root="${project_root}/results/validator/isolation-probes/${SLURM_JOB_ID}"
mkdir -p "${probe_root}"
report="${probe_root}/report.txt"

{
    printf 'schema=q66-validator-isolation-probe-v1\n'
    printf 'slurm_job_id=%s\n' "${SLURM_JOB_ID}"
    printf 'node=%s\n' "${SLURMD_NODENAME:-unknown}"
    printf 'kernel=%s\n' "$(uname -srmo)"
    printf 'uid=%s\n' "$(id -u)"
    printf 'gid=%s\n' "$(id -g)"
    for command_name in unshare bwrap firejail nsjail prlimit setpriv curl getent; do
        if command -v "${command_name}" >/dev/null 2>&1; then
            printf 'command_%s=%s\n' "${command_name}" "$(command -v "${command_name}")"
        else
            printf 'command_%s=missing\n' "${command_name}"
        fi
    done
    if unshare --user --map-current-user --net true >/dev/null 2>&1; then
        printf 'unshare_user_net=available\n'
    else
        printf 'unshare_user_net=denied\n'
    fi
    if unshare --user --map-current-user --mount true >/dev/null 2>&1; then
        printf 'unshare_user_mount=available\n'
    else
        printf 'unshare_user_mount=denied\n'
    fi
    if unshare --user --map-current-user --pid --fork true >/dev/null 2>&1; then
        printf 'unshare_user_pid=available\n'
    else
        printf 'unshare_user_pid=denied\n'
    fi
    if [[ -r /proc/sys/kernel/unprivileged_userns_clone ]]; then
        printf 'unprivileged_userns_clone=%s\n' "$(</proc/sys/kernel/unprivileged_userns_clone)"
    else
        printf 'unprivileged_userns_clone=unreported\n'
    fi
    if [[ -r /proc/self/cgroup ]]; then
        printf 'cgroup_begin\n'
        sed 's/^/cgroup=/' /proc/self/cgroup
        printf 'cgroup_end\n'
    fi
} >"${report}"

sha256sum "${report}" >"${probe_root}/checksums.sha256"
cat "${report}"
