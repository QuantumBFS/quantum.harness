#!/usr/bin/env bash
# QMCPACK Slater-Jastrow/DMC over twists; consumes QE-generated ESHDF orbitals.
# Adapt executable paths, MPI flags, K_POINTS, pseudopotentials, and XML files
# to the active project before running.
set -euo pipefail

: "${QMCPACK_COMPLEX_BIN:?set QMCPACK_COMPLEX_BIN to qmcpack_complex}"

MPIRUN="${MPIRUN:-mpirun}"
MPI_FLAGS="${MPI_FLAGS:-}"
PARALLEL_TWISTS="${PARALLEL_TWISTS:-1}"
QMC_NP="${QMC_NP:-1}"
QMC_MPI_FLAGS="${QMC_MPI_FLAGS:---bind-to none}"
TWIST_LIST="${TWIST_LIST:-00}"
FORCE_QMC="${FORCE_QMC:-0}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-false}"

run_qmc() {
  local xml=$1
  local out=${xml%.xml}.out
  if [[ "$FORCE_QMC" != "1" && -s "$out" ]] && grep -q "QMCPACK execution completed successfully" "$out"; then
    echo "[skip] $xml already completed"
    return 0
  fi
  # shellcheck disable=SC2206
  local qmc_flags=( ${QMC_MPI_FLAGS} )
  if [[ "$QMC_NP" -gt 1 ]]; then
    "$MPIRUN" "${qmc_flags[@]}" -np "$QMC_NP" "$QMCPACK_COMPLEX_BIN" "$xml" > "$out"
  else
    "$QMCPACK_COMPLEX_BIN" "$xml" > "$out"
  fi
  grep -q "QMCPACK execution completed successfully" "$out"
}

echo "[job] QMCPACK_COMPLEX_BIN=$QMCPACK_COMPLEX_BIN"
echo "[job] PARALLEL_TWISTS=$PARALLEL_TWISTS QMC_NP=$QMC_NP OMP_NUM_THREADS=$OMP_NUM_THREADS"
echo "[job] MPI_FLAGS=$MPI_FLAGS QMC_MPI_FLAGS=$QMC_MPI_FLAGS"

declare -a batch_pids=()
declare -a batch_xmls=()
slot=0
for twist in $TWIST_LIST; do
  xml="sj_vmc_dmc_tw${twist}.xml"
  test -s "$xml"
  ( run_qmc "$xml" ) &
  batch_pids+=( "$!" )
  batch_xmls+=( "$xml" )
  slot=$((slot + 1))

  if [[ "$slot" -ge "$PARALLEL_TWISTS" ]]; then
    for idx in "${!batch_pids[@]}"; do
      if ! wait "${batch_pids[idx]}"; then
        echo "[error] ${batch_xmls[idx]} failed" >&2
        exit 1
      fi
    done
    batch_pids=()
    batch_xmls=()
    slot=0
  fi
done

for idx in "${!batch_pids[@]}"; do
  if ! wait "${batch_pids[idx]}"; then
    echo "[error] ${batch_xmls[idx]} failed" >&2
    exit 1
  fi
done

echo "[done] QMCPACK run completed"
