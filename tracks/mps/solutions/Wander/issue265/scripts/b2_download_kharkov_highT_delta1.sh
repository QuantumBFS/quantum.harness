#!/usr/bin/env bash
set -euo pipefail

# Route B2: download Kharkov et al. public high-T Δ=1 domain-wall dataset
#
# Source repository (public): https://github.com/yourball/pde-many-body
# File: domain_wall_xxz/data/highT_delta=1.npy  (binary numpy .npy; contains a Python dict via np.save)
#
# Why this script exists:
#   - The dataset is small (~3 MB) and can be pulled directly on a laptop (Apple Silicon OK).
#   - We avoid depending on git-lfs etc.
#
# Usage:
#   bash scripts/b2_download_kharkov_highT_delta1.sh
#   # or customize output path:
#   OUT=data/highT_delta1.npy bash scripts/b2_download_kharkov_highT_delta1.sh
#
# Notes:
#   - This is a binary file; GitHub "Raw" URL is used.
#   - We store with a filename WITHOUT '=' to avoid shell pitfalls.
#
OUT="${OUT:-data/highT_delta1.npy}"
URL="https://github.com/yourball/pde-many-body/raw/refs/heads/main/domain_wall_xxz/data/highT_delta%3D1.npy"

mkdir -p "$(dirname "$OUT")"

echo "[B2] Downloading Δ=1 high-T domain-wall data ..."
echo "     URL = $URL"
echo "     OUT = $OUT"
curl -L --fail --retry 3 --retry-delay 2 -o "$OUT" "$URL"

echo "[B2] Done. File info:"
ls -lh "$OUT"

echo "[B2] Tip: you can verify integrity with:"
echo "     python scripts/b2_inspect_kharkov_npy.py --npy $OUT"
