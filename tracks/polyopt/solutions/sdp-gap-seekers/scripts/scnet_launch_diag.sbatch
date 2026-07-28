#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=scnet-diag
#SBATCH --time=00:02:00
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=1000M
#SBATCH --output=slurm-diag-%j.out
#SBATCH --error=slurm-diag-%j.err
#
# Minimal Slurm batch-launch diagnostic (lead review of SCNet submission,
# 2026-07-28). Isolates batch launch from the application: runs ONLY shell
# built-ins / standard commands (hostname, date, env) -- no Julia, no Mosek,
# no checksums. Output goes to the submit dir itself (~/quantum.harness) so a
# missing output subdir cannot itself cause a launch cancellation.
#
# If this job SUCCEEDS, Slurm batch launch on xhacnormalb is healthy and the
# failed smoke jobs (22986072, 22986104) failed for an application/script
# reason (leading hypothesis: their --output=results/... dir did not exist at
# launch time). If this job also exits 0:53 CANCELLED with no output file,
# the launch problem is a Slurm/node/support issue.

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

echo "[diag] start   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[diag] host    $(hostname)"
echo "[diag] job     ${SLURM_JOB_ID}"
echo "[diag] part    ${SLURM_JOB_PARTITION}"
echo "[diag] cpus    ${SLURM_CPUS_PER_TASK:-unset}"
echo "[diag] submit  ${SLURM_SUBMIT_DIR}"
echo "[diag] pwd     $(pwd)"
echo "[diag] user    $(whoami)"
echo "[diag] selected-env:"
env | LC_ALL=C sort | grep -E '^(SLURM|PATH|HOME|LD_LIBRARY|MOSEK|JULIA)=' | head -40
echo "[diag] finish  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[diag] OK"
