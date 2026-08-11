#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
julia --project="${project_root}/julia" -e \
  'using Pkg; Pkg.resolve(); Pkg.instantiate(); Pkg.precompile()'
julia --project="${project_root}/julia" -e \
  'using UniformTEMPO, OrdinaryDiffEq, JSON3; println("UniformTEMPO environment ready")'
