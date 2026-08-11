#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="${CEFFFLOW_PROJECT_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
DEPENDENCY_ROOT="${CEFFFLOW_DEPENDENCY_ROOT:-${PROJECT_ROOT}/.deps}"

if [[ -z "${CEFFFLOW_PYTHON:-}" ]]; then
  if type module >/dev/null 2>&1; then
    module load anaconda3/2023.09
  fi
  CEFFFLOW_PYTHON=$(command -v python3 || command -v python)
fi

mkdir -p "${DEPENDENCY_ROOT}"
"${CEFFFLOW_PYTHON}" -m pip install \
  --disable-pip-version-check \
  --only-binary=:all: \
  --target "${DEPENDENCY_ROOT}" \
  numpy==2.2.6 \
  scipy==1.15.3 \
  pydantic==2.12.5 \
  matplotlib==3.10.8 \
  'pytest>=8,<10'

PYTHONPATH="${DEPENDENCY_ROOT}" "${CEFFFLOW_PYTHON}" -c '
import sys
import numpy
import pydantic
import scipy

assert sys.version_info >= (3, 11)
assert numpy.__version__ == "2.2.6"
assert scipy.__version__ == "1.15.3"
assert pydantic.__version__ == "2.12.5"
'
