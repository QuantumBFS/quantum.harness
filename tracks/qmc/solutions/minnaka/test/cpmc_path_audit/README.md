# CPMC auxiliary-field path audit

This directory contains the dedicated C++17/oneMKL test program for the
2×2 periodic, half-filled repulsive Hubbard model at `t=1`, `U=8`. It
enumerates the real Hirsch auxiliary fields and records, for every path:

- the signed PQMC contribution and `log|D(X)|`;
- the constrained-path generation probability `log Q(X)`;
- the final and minimum intermediate walker weights;
- a full-slice, linear-detrended bottleneck that is invariant to a constant
  reference-energy shift;
- the minimum trial overlap and first rejected substep.

The primary right initial determinant is the same RHF-x, RHF-y, or UHF
determinant used as the left importance trial. The exact 36-dimensional
fixed-sector oracle is separate: it verifies the discrete HS sum and direct
Trotter projection and constructs the exact dominant discrete-time guide.
The path evaluator itself contains no exact-diagonalization dependency, so it
can replay selected 4×4 PQMC paths.

## Build and test

```bash
source /opt/intel/oneapi/setvars.sh
make -C /home/minnaka/code/QuanHarness/test/cpmc_path_audit clean all test
/usr/bin/python3 -m unittest discover \
  -s /home/minnaka/code/QuanHarness/test/cpmc_path_audit/tests \
  -p 'test_*.py' -v
```

No Eigen or OpenBLAS installation is needed. `run.sh` loads the oneAPI
environment itself. oneAPI prepends its legacy Python 3.7 to `PATH`, so the
pattern-analysis scripts and tests explicitly use `/usr/bin/python3`
(Python 3.10 with NumPy/SciPy/pandas/Matplotlib).

## Export the shared 4×4 UHF trial

The bridge workflow reads the free determinant exported by ALF, maps it
explicitly into the C++ row-major site order, solves the collinear Néel UHF
problem, fixes each spin-sector overlap gauge, and maps the result back to
ALF order:

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
build/cpmc_audit export-uhf \
  --lx 4 --ly 4 --t 1 --u 4 --dt 0.05 --n-up 8 --n-down 8 \
  --initial-up trial_I_up.dat --initial-down trial_I_down.dat \
  --site-map site_map.dat --output-dir exported-trial
```

The command writes `trial_T_up.dat`, `trial_T_down.dat`, and
`uhf_metadata.json`. The bridge bootstrap script combines these files with
the original ALF free orbitals and records their SHA-256 digests in a single
immutable manifest.

## Enumerate

The full M=4 comparison is:

```bash
/home/minnaka/code/QuanHarness/test/cpmc_path_audit/run.sh 4 \
  /home/minnaka/code/QuanHarness/test/cpmc_path_audit/results/m4-full
```

The primary M=6 run can be restricted to the three trials and row-major
site-by-site proposal:

```bash
/home/minnaka/code/QuanHarness/test/cpmc_path_audit/run.sh 6 \
  /home/minnaka/code/QuanHarness/test/cpmc_path_audit/results/m6-primary \
  --proposals site --orders row
```

The bit string is chronological: slice-major, then site-major. `+1` is bit 1,
`−1` is bit 0, and the earliest field is the most-significant used bit. This
makes depth-first prefix traversal produce ascending `config_id`.

Each run writes versioned `paths_*.bin` files plus `metadata.json`,
`validation.json`, `guide_validation.json`, `summary.csv`,
`top_under_sampled.csv`, and
`top_bottlenecks.csv`. The binary format is fixed at a 128-byte header and
64-byte records; `summarize.py` is the reference reader.

## Replay a selected path

```bash
source /opt/intel/oneapi/setvars.sh
/home/minnaka/code/QuanHarness/test/cpmc_path_audit/build/cpmc_audit replay \
  --lx 2 --ly 2 --u 8 --dt 0.1 --slices 6 \
  --trial uhf --proposal site --order row --config-id 12345 \
  --output /home/minnaka/code/QuanHarness/test/cpmc_path_audit/results/trace.csv
```

For paths longer than 64 fields, including later 4×4 calculations, use a text
file containing whitespace-separated `+1` and `-1` values:

```bash
.../build/cpmc_audit replay \
  --lx 4 --ly 4 --u 8 --dt 0.1 --n-up 8 --n-down 8 --slices M \
  --trial uhf --proposal site --order row \
  --fields-file selected_path.txt --output trace.csv
```

The replay metadata must use the same lattice, Δτ, HS convention, site order,
trial construction, and field ordering as the external PQMC path.
Replay applies thin-QR stabilization every five slices by default; change it
with `--stabilize-every N` or use `0` only for short-path diagnostics.

## Batch replay with one-body diagnostics

The pattern analysis writes one manifest per trial with columns
`path_id,role,case_id,config_id,fields_file,score,log_d_over_mean,weight_bin`.
Each row sets either `config_id` or `fields_file`, never both:

```bash
source /opt/intel/oneapi/setvars.sh
/home/minnaka/code/QuanHarness/test/cpmc_path_audit/build/cpmc_audit \
  batch-replay --lx 2 --ly 2 --u 8 --dt 0.1 --slices 6 \
  --trial rhf_x --proposal site --order row \
  --manifest manifest_rhf_x.csv \
  --steps-output steps_rhf_x.csv \
  --masks-output mask_predictions_rhf_x.csv \
  --progress-updates 20
```

The step table separates the selected heat-bath probability `q`, branching
factor `C`, cumulative walker weight, principal angles, normalized Slater
overlap, orbital scale, mixed local densities, and direct/determinant-lemma
field ratios. For 2×2 it also ranks all 16 possible next-slice masks by
near-orthogonality. A 4×4 external field path receives the same step
diagnostics but uses the greedy one-body mask predictor rather than expanding
all `2^16` possible next slices.

## Run the complete pattern analysis

Use the system Python explicitly so loading oneAPI for compilation does not
select Intel Python 3.7:

```bash
source /opt/intel/oneapi/setvars.sh
make -C /home/minnaka/code/QuanHarness/test/cpmc_path_audit all
cd /home/minnaka/code/QuanHarness/test/cpmc_path_audit
/usr/bin/python3 -u run_pattern_analysis.py \
  --m6-results results/m6-primary-v2 \
  --m4-results results/m4-full-v2 \
  --output results/m6-primary-v2/pattern_analysis \
  --cpmc-audit build/cpmc_audit \
  --progress-updates 20
```

The runner loads oneMKL only for its C++ child processes, keeps every source
binary read-only, writes stage metadata, exports representative full traces,
and verifies exact counts, determinant-lemma residuals, figure files, and
input SHA-256 checksums.
