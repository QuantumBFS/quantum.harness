#!/usr/bin/env bash
set -euo pipefail

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SOLUTION_DIR}/research/01_task_folder/task_05/script"
PYTHONDONTWRITEBYTECODE=1 bash run_quick_verify_v1.sh
