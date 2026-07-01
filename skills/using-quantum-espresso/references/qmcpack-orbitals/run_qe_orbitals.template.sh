#!/usr/bin/env bash
# Generic QE -> pw2qmcpack: generate Slater-determinant orbitals (ESHDF) for QMCPACK.
# Adapt executable paths, MPI flags, K_POINTS, pseudopotentials, and XML files
# to the active project before running.
set -euo pipefail

: "${QE_BIN:?set QE_BIN to a pw.x executable from the QE build paired with pw2qmcpack.x}"
: "${PW2QMCPACK:?set PW2QMCPACK to pw2qmcpack.x}"

MPIRUN="${MPIRUN:-mpirun}"
MPI_FLAGS="${MPI_FLAGS:-}"
QE_NP="${QE_NP:-4}"
QE_NPOOL="${QE_NPOOL:-1}"
PW2QMCPACK_NP="${PW2QMCPACK_NP:-1}"
FORCE_QE="${FORCE_QE:-0}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-false}"

run_mpi_or_serial() {
  local np=$1
  shift
  local exe=$1
  shift
  if [[ "$np" -gt 1 ]]; then
    # shellcheck disable=SC2206
    local flags=( ${MPI_FLAGS} )
    "$MPIRUN" "${flags[@]}" -np "$np" "$exe" "$@"
  else
    "$exe" "$@"
  fi
}

echo "[job] QE_BIN=$QE_BIN"
echo "[job] PW2QMCPACK=$PW2QMCPACK"
echo "[job] QE_NP=$QE_NP QE_NPOOL=$QE_NPOOL PW2QMCPACK_NP=$PW2QMCPACK_NP"

mkdir -p qe_tmp

if [[ "$FORCE_QE" == "1" || ! -s qe_tmp/qmc_solid.pwscf.h5 ]]; then
  echo "[run] QE SCF"
  run_mpi_or_serial "$QE_NP" "$QE_BIN" -npool "$QE_NPOOL" -in qe_scf.in > qe_scf.out
  grep -q "JOB DONE." qe_scf.out

  echo "[run] QE NSCF"
  run_mpi_or_serial "$QE_NP" "$QE_BIN" -npool "$QE_NPOOL" -in qe_nscf.in > qe_nscf.out
  grep -q "JOB DONE." qe_nscf.out

  echo "[run] pw2qmcpack"
  run_mpi_or_serial "$PW2QMCPACK_NP" "$PW2QMCPACK" < pw2qmcpack.in > pw2qmcpack.out
  grep -q "JOB DONE." pw2qmcpack.out
  test -s qe_tmp/qmc_solid.pwscf.h5
else
  echo "[reuse] qe_tmp/qmc_solid.pwscf.h5"
fi

echo "[done] QE -> pw2qmcpack orbitals generated"
