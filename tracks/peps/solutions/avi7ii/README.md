# Avi7ii solution for challenge #147

Finite-temperature PEPO for the 10x10 open-boundary transverse-field Ising
model.

## Judge quick start

> **Start with the [GitHub-readable technical report](../../results/issue147-four-figure-deadline/README.md).**

The report leads with the challenge checklist, embeds all four evidence figures,
and links every headline number to CSV data or immutable checkpoint metadata.
For offline reading, download the self-contained
[HTML report](../../results/issue147-four-figure-deadline/report.html). The
validated result is a promising thermodynamic-aware PEPO prototype, not a claim
that the complete beta-range and bond-dimension benchmark has been finished.

## Smoke test

From the repository root after installing the editable package:

```text
.venv\Scripts\python.exe -m qh147.smoke
```

## 4x4 exact calibration

Run the small exact tests locally:

```text
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py tracks/peps/solutions/avi7ii/tests/test_ed.py tracks/peps/solutions/avi7ii/tests/test_run_ed.py tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py -q -W error
```

On SCNet, rehearse all ten sectors before submitting any eigensolver task:

```text
python -u -m qh147.run_ed --config tracks/peps/solutions/avi7ii/configs/ed-4x4.json --run-root tracks/peps/results/issue147-ed --rehearse-all
```

Submit cell 1 (`A1,+`) as the timing probe. Submit the remaining cells only
after the measured cubic wall-time estimate passes the six-hour gate. Assemble
a complete run with:

```text
python -m qh147.ed_thermo --config tracks/peps/solutions/avi7ii/configs/ed-4x4.json --run-root tracks/peps/results/issue147-ed --output tracks/peps/results/issue147-ed/assembled
```

## 10x10 production PEPO chain

The first production comparison fixes the open-boundary Pauli TFIM at
`J=1`, `h=3`, student bond dimension `D=4`, and `delta_beta=0.025`. Inspect the
40-step, two-mode request without constructing the network:

```text
.venv\Scripts\python.exe -m qh147.run dry-run --config tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json --run-root tracks/peps/results/issue147-pepo
```

Do not run the 10x10 evolution locally. On SCNet, time exactly one
thermodynamic step first:

```text
python -u -m qh147.run evolve --config tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json --run-root tracks/peps/results/issue147-pepo --compression-mode thermodynamic --stop-after-steps 1
```

The same command without `--stop-after-steps` resumes from the immutable first
checkpoint. Run the ordinary mode with `--compression-mode ordinary`; it uses
the same `D`, `chi`, optimizer, and iteration cap in a separate directory.

After all 40 checkpoints exist for a mode, measure them independently at both
declared boundary dimensions:

```text
python -u -m qh147.run measure --config tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json --run-root tracks/peps/results/issue147-pepo --compression-mode thermodynamic --chi 16
python -u -m qh147.run measure --config tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json --run-root tracks/peps/results/issue147-pepo --compression-mode thermodynamic --chi 32
```

Repeat the two measurement commands for `ordinary`. Dense 0.025-grid data and
the ten public beta points are written under
`tracks/peps/results/issue147-pepo/measurements/<mode>/chi-<chi>/`.

## h=3 validation arrays on SCNet

Generate the opaque run specs with `scripts/parameter_scan.py plan` using the
JSON files under `configs/scans/`. The resulting cell counts are 480 QMC, two
PEPO evolution, and four PEPO measurement cells. SCNet limits an array to 200
tasks, so submit QMC as the three ranges `1-200`, `201-400`, and `401-480`.

Run `issue147-pepo-probe.sbatch` before either full PEPO evolution cell. It
creates only the first thermodynamic checkpoint in `cell-0002`; the full array
then resumes from it. The live `scnet` endpoint currently exposes only the
`qdagnormal` A800 partition, whose QOS requires `gpu:A800:1` even for QMC.
Use the `qdeshell` resource profile with `HARNESS_SSH_ALIAS=scnet`; PEPO uses
JAX on the allocated GPU. Do not release the 40-step PEPO cells until the
probe's measured wall time and peak memory fit the declared 12-hour,
128-GiB request.

The array scripts intentionally contain no partition. Probe the live queue and
pass the ratified partition at submission time. Use `HARNESS_KIND=pepo-measure`
with `issue147-pepo.sbatch` for the four measurement cells after both evolution
manifests report success.

## Final h=3 evidence assembly

After fetching successful manifests and artifacts, assemble the QMC reference,
both PEPO compression modes, chi convergence, resources, and the optional 4x4
ED diagnostic with one command:

```text
python -m qh147.validate --qmc tracks/peps/results/issue147-qmc --pepo tracks/peps/results/issue147-pepo --pepo-measure tracks/peps/results/issue147-pepo-measure --ed tracks/peps/results/issue147-ed/assembled --output tracks/peps/results/issue147-validation
```

Omit `--ed` when the assembled 4x4 diagnostic is unavailable. The command
rejects rehearsed, failed, missing, or convention-mismatched cells. It writes
`thermodynamics.csv`, `convergence.csv`, `resources.csv`, `summary.json`, and
PNG/PDF comparison and convergence figures. Because the current production
scope fixes `D=4` and `delta_beta=0.025`, those two convergence errors remain
explicitly unassessed rather than being reported as passed.

## Current validated evidence figures

When only the completed two-step PEPO probe and the accepted beta=0.5 QMC run
are available, render the deadline-safe diagnostic figures without inventing a
full thermodynamic comparison:

```text
.venv\Scripts\python.exe -m qh147.current_evidence --pepo tracks/peps/results/issue147-pepo-lazy-nojit-capped-two-step-probe --qmc tracks/peps/results/issue147-qmc-reproducible-production --output tracks/peps/results/issue147-current-evidence
```

The output summary explicitly records that ordinary PEPO, specific heat, the
full beta curve, and PEPO chi, D, and delta-beta convergence were not assessed.
