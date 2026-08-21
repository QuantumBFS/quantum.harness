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

CROSS_TESTS="$(find tests -type f \( -name '*v9.py' -o -name '*v10.py' -o -name '*v11.py' -o -name '*v12.py' \) -print | sort)"
if [[ -z "${CROSS_TESTS}" ]]; then
  echo "No v9--v12 tests found" >&2
  exit 1
fi
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q ${CROSS_TESTS}
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python verify_cross_mechanism_delivery_v12.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python verify_cross_mechanism_manuscript_v12.py

PAPER1_TESTS="$(find tests -type f -name '*v13.py' -print | sort)"
if [[ -z "${PAPER1_TESTS}" ]]; then
  echo "No Paper I v13 tests found" >&2
  exit 1
fi
# The capsule preserves frozen artifacts and hashes, but not the source repository's
# historical Git object used by one immutable-baseline test.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q ${PAPER1_TESTS} \
  -k 'not tracked_v1_v12_tree_is_byte_sealed'

PAPER2_TESTS="$(find tests -type f -name '*v14.py' -print | sort)"
if [[ -z "${PAPER2_TESTS}" ]]; then
  echo "No Paper II or cross-paper v14 tests found" >&2
  exit 1
fi
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q ${PAPER2_TESTS}

cd "${SOLUTION_DIR}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q test_verify_two_paper_capsule.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python verify_two_paper_capsule.py
