#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
ARTICLE_DIR="${REPO_ROOT}/overleaf_sync/geometric_eth_large_scale"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1785283200}"

cd "${SCRIPT_DIR}"

if [[ "${FULL_RECOMPUTE:-0}" == "1" ]]; then
  python run_matrix_element_geometric_eth_v3.py
  python run_topological_holonomy_v3.py --workers "${TOPOLOGY_WORKERS:-4}"
  python make_matrix_element_geometric_eth_figure_v3.py
  python verify_matrix_element_geometric_eth_v3.py
  python make_topological_holonomy_figure_v3.py
  python verify_topological_holonomy_v3.py
  python make_geometric_eth_topology_assets_v3.py
  python verify_matrix_element_topology_theory_v3.py
fi

if [[ "${VALIDATE_CITATIONS:-0}" == "1" ]]; then
  python validate_citations_v1.py
fi
cp output/figure_6_wick_factorization_v3.pdf \
  "${ARTICLE_DIR}/figures/figure_6_wick_factorization_v3.pdf"
cp output/figure_7_topological_holonomy_v3.pdf \
  "${ARTICLE_DIR}/figures/figure_7_topological_holonomy_v3.pdf"

cd "${ARTICLE_DIR}"
latexmk -C main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

cd "${SCRIPT_DIR}"
python verify_geometric_eth_topology_article_v3.py
PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q \
  tests/test_geometric_eth_topology_assets_v3.py \
  tests/test_matrix_element_topology_theory_v3.py \
  tests/test_geometric_eth_topology_article_v3.py
python make_release_manifest_v1.py
python verify_release_contract_v1.py
