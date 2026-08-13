#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

./scripts/fetch-occam-data.sh
cargo build --quiet --release -p occam71_rust
julia ./scripts/verify-oracles.jl
