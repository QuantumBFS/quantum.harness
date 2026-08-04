#!/usr/bin/env bash
set -euo pipefail

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SOLUTION_DIR}/research/01_task_folder/task_05/script"
PYTHONDONTWRITEBYTECODE=1 bash run_quick_verify_v1.sh

V7_TESTS="$(find tests -type f -name '*v7.py' -print | sort)"
if [[ -z "${V7_TESTS}" ]]; then
  echo "No v7 tests found" >&2
  exit 1
fi
# Test paths are repository-controlled and contain no whitespace.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q ${V7_TESTS}
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python verify_susy_hodge_delivery_v7.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python verify_susy_hodge_manuscript_v7.py
