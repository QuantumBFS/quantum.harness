#!/usr/bin/env bash
#SBATCH --job-name=anderson-preflight
#SBATCH --output=anderson-preflight-%j.out

set -euo pipefail

cluster_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PREFLIGHT_ONLY=1
exec bash "$cluster_dir/anderson_block2.sbatch"
