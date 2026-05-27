---
name: cpmc-lab
description: Use when installing, smoke-testing, locating, or invoking the official CPMC-Lab Matlab package; covers MATLAB path setup, package-root discovery, addpath setup, batch execution, download/license handling, and package output extraction.
---

# CPMC-Lab

Use this as a software stack skill only. It owns package mechanics: where CPMC-Lab is installed, how Matlab finds it, how to run it non-interactively, and where package outputs land.

It does not own model choice, QMC method design, paper figure facts, estimator normalization, or physics validation. `/method-qmc` chooses when this package is the backend; model and paper skills choose the scientific parameters.

## Sources

- Stack contract: `skills/cpmc-lab/stack.toml`
- Official package page: `https://cpmc-lab.wm.edu/`
- Install target: `make install cpmc-lab`
- Smoke test: `make install cpmc-lab`

## Workflow

1. Consult `stack.toml` for the install command, smoke command, docs URL, and runtime profile.
2. Install with `make install cpmc-lab`; it downloads the official package into ignored local storage under `.external/cpmc-lab/`.
3. Locate the extracted package root by finding `CPMC_Lab.m`.
4. Run non-interactively through `matlab -batch`, falling back to the full Matlab app path when `matlab` is not on `PATH`.
5. Generate drivers that only encode parameters supplied by the caller. Do not infer scientific defaults in this skill.
6. Save package outputs under the active run directory, including `.mat` files, logs, and any derived text/CSV summaries.
7. Read `.mat` outputs with Matlab or Python `scipy.io.loadmat`; never treat console output as the only result record.

## Caller Contract

The caller must supply all scientific choices: model, lattice, couplings, sectors, method parameters, estimator definitions, sweep grid, figure mapping, and validation target. This skill only turns those choices into a reproducible CPMC-Lab invocation.

If a requested value is missing, return to the routing skill instead of filling it here.

## Time estimate

Estimate runtime only after the caller supplies the package run parameters.

- Use a short non-production timing probe when the run size is uncertain; it should measure package step rate only and produce no scientific claim.
- Multiply the measured rate by the caller-specified parameter grid and repeat count.
- Route to `/slurm` when the estimate exceeds local exploratory budget or when independent points can run as an array.

## Usage Notes

- Prefer MATLAB over Octave for this package. Octave is a possible compatibility experiment, not the canonical route.
- The package license is the Computer Physics Communications Non-Profit Use License; do not vendor the downloaded package into git.
- On this macOS machine, MATLAB is available at `/Applications/MATLAB_R2026a.app/bin/matlab` even when `matlab` is not on `PATH`.
- To put MATLAB on `PATH`, create a shell-visible symlink such as `ln -s /Applications/MATLAB_R2026a.app/bin/matlab /opt/homebrew/bin/matlab`.
