# CPMC-Lab Figure 4(a-c) reproduction

This directory contains the MATLAB wrapper used to reproduce the approved
integer-grid points (`U/t = 0, 1, ..., 8`) from Figure 4 of Nguyen *et al.*,
*CPMC-Lab: A Matlab Package for Constrained Path Monte Carlo Calculations*.

The official package itself remains under ignored `.external/` storage and is
not vendored here. The downloaded archive is labeled 2.0, while the checked
source banner identifies itself as version 1.0; reports retain both facts rather
than silently choosing one label. Run one point with MATLAB R2025a:

```matlab
addpath('tracks/qmc/solutions/Plasma-Team/cpmc_lab_fig4');
run_cpmc_fig4_point(run_dir, package_dir, "smoke", 20260728);
```

Each point writes its official MAT output, `summary.csv`, block energies, and a
`DONE.json` completion marker below `<run_dir>/raw/<point>/`. The completion
marker is deliberately written before MATLAB shutdown because the local R2025a
installation can crash during DDUX cleanup after valid output has been saved.
Any MATLAB exception writes `FAILED.json`, removes a stale success marker, and
is rethrown so batch MATLAB exits nonzero.

For deterministic runs, `initialization.m` is a path shim: it executes the
official initialization script unchanged, then restores the approved fixed seed
immediately before propagation. This changes no model, propagation, or
measurement logic and avoids modifying or vendoring the licensed package.

Panels (b) and (c) follow the paper's Hellmann-Feynman route rather than the
biased mixed estimators of the separate terms.  The finalizer uses local
five-point, unit-spaced quartic derivatives to calculate
`E_V = U dE/dU`, total double occupancy `dE/dU`, and `E_K = E - E_V`.
The unit spacing and edge stencils are recorded as an explicit operational
choice because the paper does not print them. Cross-U statistical errors are
propagated independently; a shared seed is not treated as proof of pairing. The
absolute difference from a local three-point derivative is reported as a
finite-difference systematic uncertainty.

`mc_diagnostics.csv` records IID and blocked standard errors, lag-one
autocorrelation, effective sample size, and split-half drift. The most
conservative reported/blocking standard error is used. Digitized ED values and
their extraction trail live in `ed_digitized_fig4.csv` and
`ed_digitized_fig4.provenance.json`; they are comparison data, not a fresh ED
calculation.

After all nine production point directories contain `DONE.json`, finalize the
plots and update the run's single source of truth:

```powershell
C:\Python314\python.exe -X utf8 tracks\qmc\solutions\Plasma-Team\cpmc_lab_fig4\finalize_cpmc_fig4abc.py <run-dir>
```

Use `--check-only` for a read-only scientific gate. A normal finalization
regenerates all three nine-point SVGs, diagnostics, `run.json`, and the SHA-256
artifact manifest. A failed comparison exits nonzero and never creates
`FINALIZED.txt`.

For a long unattended run, `monitor_and_finalize.ps1` waits for all nine
production sentinels, stops on any failure marker or timeout, then performs the
same finalization and report render automatically. Only after all stages succeed
does it create `FINALIZED.txt`; use `-OpenReport` to open the HTML explicitly.
