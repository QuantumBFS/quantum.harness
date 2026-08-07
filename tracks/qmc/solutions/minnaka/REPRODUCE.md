# Reproduction instructions

Run all commands from the repository root.  Define the solution location once:

```bash
SOLUTION="$(cd tracks/qmc/solutions/minnaka && pwd)"
```

The compact 4x4 figure generator requires Python 3, NumPy, and Matplotlib.
The full 2x2 pattern analysis additionally requires SciPy and pandas.  The C++
enumerator/replayer uses Intel oneAPI and sequential MKL; Eigen and OpenBLAS
are not required.

## 1. Recreate the two 4x4 report figures

The two figures are generated directly from the committed path table:

```bash
python3 "$SOLUTION/scripts/make_report_figures.py"
```

Expected final line:

```text
figures generated: paths=976 worst=10 rho=-0.933099
```

The script independently reconstructs the worst one percent and refuses to
write a successful result if the sample IDs or correlation disagree with the
committed summary.

## 2. Build and test the 2x2 C++ path auditor

```bash
source /opt/intel/oneapi/setvars.sh
make -C "$SOLUTION/test/cpmc_path_audit" clean all test
/usr/bin/python3 -m unittest discover \
  -s "$SOLUTION/test/cpmc_path_audit/tests" \
  -p 'test_*.py' -v
```

Run a small exact enumeration:

```bash
"$SOLUTION/test/cpmc_path_audit/run.sh" 4 \
  "$SOLUTION/test/cpmc_path_audit/results/m4-check"
```

The full six-slice calculation used in Figure 1 enumerates $2^{24}$ paths for
each of the three trials.  The complete figure workflow also uses the
four-slice run to construct matched controls:

```bash
AUDIT="$SOLUTION/test/cpmc_path_audit"
"$AUDIT/run.sh" 4 "$AUDIT/results/m4-reproduction"
"$AUDIT/run.sh" 6 "$AUDIT/results/m6-reproduction" \
  --proposals site --orders row
/usr/bin/python3 -u "$AUDIT/run_pattern_analysis.py" \
  --m6-results "$AUDIT/results/m6-reproduction" \
  --m4-results "$AUDIT/results/m4-reproduction" \
  --output "$AUDIT/results/m6-reproduction/pattern_analysis" \
  --cpmc-audit "$AUDIT/build/cpmc_audit" \
  --progress-updates 20
cp "$AUDIT/results/m6-reproduction/pattern_analysis/figures/weight_vs_efficiency.pdf" \
  "$SOLUTION/figures/exhaustive_2x2_weight_efficiency.pdf"
cp "$AUDIT/results/m6-reproduction/pattern_analysis/figures/weight_vs_efficiency.png" \
  "$SOLUTION/figures/exhaustive_2x2_weight_efficiency.png"
```

The committed figure was generated from run `m6-primary-v2`; the reproduction
commands use new output directories and do not overwrite that source run.
The exact selection counts are in
`data/exhaustive_2x2_selection_summary.csv`.

## 3. Test the ALF-to-CP bridge

The portable unit suite uses the bundled pinned ALF parameter template.  It
skips one real-executable integration check when ALF has not yet been built:

```bash
/usr/bin/python3 -m unittest discover \
  -s "$SOLUTION/test/pqmc_cp_bridge/tests" \
  -p 'test_*.py' -v
```

For the full integration suite, first clone, patch, and compile the pinned ALF
2.4 source, then run the bridge smoke test:

```bash
"$SOLUTION/test/alf_hirsch_binary/scripts/build.sh"
"$SOLUTION/test/pqmc_cp_bridge/scripts/test.sh"
```

Together these check the C++ replay, path archive format, trial-orbital
contract, field ordering, ALF binary-Hirsch patch, and bridge statistics.

The fixed 4x4 physical configuration is:

```text
Lx=Ly=4, PBC, t=1, U=4, Nup=Ndown=8
real binary Hirsch spin HS, dt=0.05
Theta=10, Beta=1, 420 slices, 6720 fields/path
ALF boundaries: free/UHF; CP constraint: the same Ueff=4 UHF
```

## 4. Reproduce the 4x4 cluster workflow

The tracked Slurm scripts preserve the production commands:

The copied Slurm scripts resolve `test/`, `runs/`, and `results/` from their
submission directory, so submit them from the solution root.  First create the
pinned patched ALF checkout with
`test/alf_hirsch_binary/scripts/build.sh` on a compatible oneAPI system (or
apply the five bundled patches to the pinned commit on the cluster).  Then use
explicit `afterok` dependencies; the pilot replay creates
`results/archive_stride.json`, and the selection job creates the production
replay manifest:

```bash
(
  cd "$SOLUTION"
  mkdir -p results/cluster_build_green results/cluster_cpmc_build \
    results/cluster_calibration_bin128_nwrap5 results/cluster_archive
  alf_build_id="$(sbatch --parsable \
    test/pqmc_cp_bridge/cluster/build_alf_serial.slurm)"
  cpmc_build_id="$(sbatch --parsable \
    test/pqmc_cp_bridge/cluster/build_cpmc_audit.slurm)"
  calibration_id="$(sbatch --parsable \
    --dependency="afterok:${alf_build_id}" \
    test/pqmc_cp_bridge/cluster/calibrate_alf.slurm)"
  pilot_id="$(sbatch --parsable \
    --dependency="afterok:${calibration_id}" \
    test/pqmc_cp_bridge/cluster/archive_pilot.slurm)"
  pilot_replay_id="$(sbatch --parsable \
    --dependency="afterok:${pilot_id}:${cpmc_build_id}" \
    test/pqmc_cp_bridge/cluster/replay_archive_pilot.slurm)"
  production_id="$(sbatch --parsable \
    --dependency="afterok:${pilot_replay_id}" \
    test/pqmc_cp_bridge/cluster/archive_production.slurm)"
  selection_id="$(sbatch --parsable \
    --dependency="afterok:${production_id}" \
    test/pqmc_cp_bridge/cluster/prepare_production_replay.slurm)"
  replay_id="$(sbatch --parsable \
    --dependency="afterok:${selection_id}" \
    test/pqmc_cp_bridge/cluster/replay_archive_production.slurm)"
  sbatch --dependency="afterok:${replay_id}" \
    test/pqmc_cp_bridge/cluster/analyze_archive_replay.slurm
)
```

For the direct ratio-of-sums energy calculation:

```bash
(
  cd "$SOLUTION"
  mkdir -p direct_reweight_1920x50/logs
  production_id="$(sbatch --parsable \
    test/pqmc_cp_bridge/cluster/direct_reweight_1920x50.slurm)"
  sbatch --dependency="afterok:${production_id}" \
    test/pqmc_cp_bridge/cluster/merge_direct_reweight_1920x50.slurm
)
```

The direct-reweight job assumes that the ALF build, C++ build, and calibration
chain above completed successfully, because it consumes their binary and
`selected_projection.json` outputs.

Cluster paths and scheduler options are site-specific and should be edited in a
copy of each Slurm script.  The statistical contract is not site-specific:
1,920 independent chains, 50 paths per chain, and numerator/denominator summed
across chains within each common bin before forming the 50 ratios.

## 5. Run the focused public checks

```bash
python3 -m json.tool "$SOLUTION/data/direct_reweight_summary.json" >/dev/null
python3 -m json.tool "$SOLUTION/data/sampling_efficiency_summary.json" >/dev/null
python3 "$SOLUTION/scripts/make_report_figures.py"
git diff --check
```

Large 6,720-bit archives and raw Monte Carlo output are not committed.  Their
format, generators, replay implementation, checksums, and compact derived
evidence are included so that a fresh production run can be compared field by
field.
