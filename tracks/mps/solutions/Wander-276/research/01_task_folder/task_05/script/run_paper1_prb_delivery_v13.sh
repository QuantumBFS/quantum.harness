#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${1:-$(cd "${script_dir}/../../.." && pwd)}"
test_root="${script_dir}/tests"

umask 022
cd "${repo_root}"

python3 "${script_dir}/build_paper1_evidence_registry_v13.py"
python3 "${script_dir}/make_paper1_prb_assets_v13.py"
python3 "${script_dir}/make_paper1_protection_mixing_figure_v13.py"
python3 "${script_dir}/make_paper1_evidence_figures_v13.py" \
  --repo-root "${repo_root}" \
  --record-reviewed

PYTHONPATH="${script_dir}${PYTHONPATH:+:${PYTHONPATH}}" \
python3 -m pytest -q \
  "${test_root}/test_paper1_evidence_registry_v13.py" \
  "${test_root}/test_paper1_figures_v13.py" \
  "${test_root}/test_paper1_manuscript_v13.py" \
  "${test_root}/test_paper1_delivery_v13.py"

python3 "${script_dir}/verify_paper1_prb_v13.py" --repo-root "${repo_root}"
