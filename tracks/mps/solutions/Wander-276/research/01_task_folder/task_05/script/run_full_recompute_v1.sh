#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

bash run_large_scale_article_v1.sh
bash run_spectral_silence_article_v2.sh
FULL_RECOMPUTE=1 bash run_geometric_eth_topology_article_v3.sh
python make_release_manifest_v1.py
python verify_release_contract_v1.py
