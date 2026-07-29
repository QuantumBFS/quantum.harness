#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}" && git rev-parse --show-toplevel)"
requirements="${script_dir}/requirements.in"

: "${ROUTE_D_PLUS_RUN_DIR:?set ROUTE_D_PLUS_RUN_DIR under tracks/qmc/results/}"
: "${JAX_PROFILE:?set JAX_PROFILE to cpu, cuda12, or cuda13}"

python_bin="${PYTHON_BIN:-python3.11}"
venv_dir="${ROUTE_D_PLUS_VENV:-${repo_root}/.venv}"
run_dir="${ROUTE_D_PLUS_RUN_DIR}"
mode="${ROUTE_D_PLUS_MODE:-all}"

case "${mode}" in
  all|install|validate) ;;
  *)
    echo "unsupported ROUTE_D_PLUS_MODE=${mode}; choose all, install, or validate" >&2
    exit 2
    ;;
esac

case "${JAX_PROFILE}" in
  cpu)
    jax_requirement="jax"
    required_platform="cpu"
    ;;
  cuda12)
    jax_requirement="jax[cuda12]"
    required_platform="gpu"
    ;;
  cuda13)
    jax_requirement="jax[cuda13]"
    required_platform="gpu"
    ;;
  *)
    echo "unsupported JAX_PROFILE=${JAX_PROFILE}; choose cpu, cuda12, or cuda13" >&2
    exit 2
    ;;
esac

case "${run_dir}" in
  "${repo_root}"/tracks/qmc/results/*) ;;
  *)
    echo "ROUTE_D_PLUS_RUN_DIR must be below ${repo_root}/tracks/qmc/results/" >&2
    exit 2
    ;;
esac

if [[ "${mode}" != "validate" ]]; then
  "${python_bin}" -m venv "${venv_dir}"
  "${venv_dir}/bin/python" -m pip install --upgrade pip setuptools wheel
  "${venv_dir}/bin/python" -m pip install --upgrade "${jax_requirement}"
  "${venv_dir}/bin/python" -m pip install --requirement "${requirements}"

  mkdir -p "${run_dir}"
  "${venv_dir}/bin/python" -m pip freeze --all > "${run_dir}/requirements-lock.txt"
fi

if [[ "${mode}" == "install" ]]; then
  exit 0
fi

if [[ ! -x "${venv_dir}/bin/python" ]]; then
  echo "validated environment does not exist: ${venv_dir}" >&2
  exit 2
fi

if [[ ! -f "${run_dir}/requirements-lock.txt" ]]; then
  echo "validated dependency lock does not exist under ${run_dir}" >&2
  exit 2
fi

"${venv_dir}/bin/python" "${script_dir}/capture_manifest.py" \
  --repo-root "${repo_root}" \
  --lock-file "${run_dir}/requirements-lock.txt" \
  --output "${run_dir}/environment-manifest.json" \
  --require-platform "${required_platform}"
