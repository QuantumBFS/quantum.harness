#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${1:-$(cd "${script_dir}/../../.." && pwd)}"
test_root="${script_dir}/tests"

umask 022
cd "${repo_root}"

python3 "${script_dir}/make_geometric_eth_theory_inputs_v14.py"
python3 "${script_dir}/make_geometric_eth_theory_figures_v14.py"

PYTHONPATH="${script_dir}${PYTHONPATH:+:${PYTHONPATH}}" \
python3 -m pytest -q \
  "${test_root}/test_geometric_eth_channel_theory_v14.py" \
  "${test_root}/test_chiral_kernel_parent_v14.py" \
  "${test_root}/test_chiral_kernel_runner_v14.py" \
  "${test_root}/test_chiral_kernel_analysis_v14.py" \
  "${test_root}/test_geometric_eth_effective_channels_v14.py" \
  "${test_root}/test_geometric_eth_inputs_v14.py" \
  "${test_root}/test_geometric_eth_theory_figures_v14.py" \
  "${test_root}/test_geometric_eth_theory_manuscript_v14.py" \
  "${test_root}/test_geometric_eth_theory_delivery_v14.py"

python3 "${script_dir}/verify_geometric_eth_theory_v14.py" --repo-root "${repo_root}"
