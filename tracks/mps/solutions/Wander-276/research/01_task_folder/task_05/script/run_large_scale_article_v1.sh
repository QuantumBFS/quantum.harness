#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ARTICLE_DIR="$REPO_ROOT/overleaf_sync/geometric_eth_large_scale"
OUTPUT_DIR="$SCRIPT_DIR/output"

cd "$SCRIPT_DIR"
python run_physical_ensemble_v1.py
python run_covariance_model_v1.py
python run_rank_scaling_v1.py
python run_statistical_analysis_v1.py
python make_large_scale_figures_v1.py
python validate_citations_v1.py

for stem in \
  figure_1_physical_law_v1 \
  figure_2_scale_hierarchy_v1 \
  figure_3_atom_crossover_v1 \
  figure_4_finite_size_v1 \
  figure_5_covariance_mechanism_v1
do
  cp "$OUTPUT_DIR/$stem.pdf" "$ARTICLE_DIR/figures/$stem.pdf"
done
cp "$OUTPUT_DIR/generated_numbers_v1.tex" \
  "$ARTICLE_DIR/generated/generated_numbers_v1.tex"
cp "$OUTPUT_DIR/generated_tables_v1.tex" \
  "$ARTICLE_DIR/generated/generated_tables_v1.tex"

cd "$ARTICLE_DIR"
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
cp main.pdf \
  "$OUTPUT_DIR/from_local_repulsion_to_global_geometry_v1.pdf"

cd "$SCRIPT_DIR"
python -m pytest -q tests | tee "$OUTPUT_DIR/pytest_v1.txt"
python verify_large_scale_article_v1.py
