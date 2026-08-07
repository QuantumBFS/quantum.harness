#!/usr/bin/env bash
#SBATCH --job-name=occ71-build-eslim
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/logs/build-eslim-%j.out

set -euo pipefail
umask 027

readonly PROJECT_ROOT="/home/user_milksang/private/homefile/quantum_harness/issue71_occam"
readonly TOOLS_ROOT="${PROJECT_ROOT}/results/occam71/tools"
readonly ARCHIVE="${TOOLS_ROOT}/eSLIM-51e9f774.tar.gz"
readonly WHEEL_DIR="${TOOLS_ROOT}/wheels-cp313"
readonly RUN_ROOT="${TOOLS_ROOT}/eslim-build-51e9f774"
readonly RUN_DIR="${RUN_ROOT}/job-${SLURM_JOB_ID}"
readonly SOURCE_DIR="${RUN_DIR}/eSLIM"
readonly BUILD_DIR="${SOURCE_DIR}/src/bindings/build"
readonly VENV_DIR="${RUN_DIR}/venv"
readonly CADICAL_DIR="${SOURCE_DIR}/src/bindings/cadical"

mkdir -p "${RUN_DIR}"
{
  printf 'job_id=%s\n' "${SLURM_JOB_ID}"
  printf 'node=%s\n' "$(hostname)"
  printf 'start_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'source_commit=%s\n' "51e9f77429627473db623058157b66a1192cbb59"
  printf 'seed=%s\n' "42"
  printf 'python=%s\n' "$(python3 --version 2>&1)"
  printf 'cmake=%s\n' "$(cmake --version | head -n 1)"
  printf 'compiler=%s\n' "$(g++ --version | head -n 1)"
} > "${RUN_DIR}/metadata.txt"

sha256sum "${ARCHIVE}" "${WHEEL_DIR}"/*.whl \
  > "${RUN_DIR}/input_sha256.txt"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install \
  --no-index \
  --find-links "${WHEEL_DIR}" \
  pybind11==3.0.4 \
  bitarray==3.9.2

tar -xzf "${ARCHIVE}" -C "${RUN_DIR}"
# The Windows checkout used for transport has CRLF text and no Unix execute
# metadata. Normalize every CaDiCaL build shell script plus its makefile
# template/version file; source bytes remain pinned by the archived hash.
sed -i 's/\r$//' \
  "${CADICAL_DIR}/configure" \
  "${CADICAL_DIR}/makefile.in" \
  "${CADICAL_DIR}/VERSION" \
  "${CADICAL_DIR}/scripts/"*.sh
chmod 0755 \
  "${CADICAL_DIR}/configure" \
  "${CADICAL_DIR}/scripts/make-build-header.sh" \
  "${CADICAL_DIR}/scripts/get-git-id.sh"
readonly PYBIND11_CMAKE="$("${VENV_DIR}/bin/python" -m pybind11 --cmakedir)"

cmake \
  -S "${SOURCE_DIR}/src/bindings" \
  -B "${BUILD_DIR}" \
  -DCMAKE_BUILD_TYPE=Release \
  -Dpybind11_DIR="${PYBIND11_CMAKE}" \
  -DPYTHON_EXECUTABLE="${VENV_DIR}/bin/python"
cmake --build "${BUILD_DIR}" --parallel "${SLURM_CPUS_PER_TASK}"

for module in aiger cadical relationSynthesiser; do
  module_path="$(find "${BUILD_DIR}" -maxdepth 1 -type f \
    -name "${module}*.so" -print -quit)"
  test -n "${module_path}"
  cp "${module_path}" "${SOURCE_DIR}/src/bindings/"
done

(
  cd "${SOURCE_DIR}/src"
  "${VENV_DIR}/bin/python" -c \
    'from bindings import aiger, cadical, relationSynthesiser; import bitarray; print("IMPORT_OK", bitarray.__version__)'
)

sha256sum "${SOURCE_DIR}/src/bindings/"*.so \
  > "${RUN_DIR}/built_modules_sha256.txt"
printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "${RUN_DIR}/metadata.txt"
printf 'SUCCESS\n' > "${RUN_DIR}/BUILD_READY"
