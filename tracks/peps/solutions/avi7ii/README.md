# Avi7ii solution for challenge #147

Finite-temperature PEPO for the 10x10 open-boundary transverse-field Ising
model.

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
