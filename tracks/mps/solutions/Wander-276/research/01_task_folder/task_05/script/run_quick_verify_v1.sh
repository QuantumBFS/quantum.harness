#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

python verify_release_contract_v1.py
PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q \
  tests/test_independent_core.py \
  tests/test_form_factors_v2.py \
  tests/test_controls_v2.py \
  tests/test_holonomy_v3.py \
  tests/test_wick_channels_v3.py \
  tests/test_matrix_element_topology_theory_v3.py \
  tests/test_release_contract_v1.py
