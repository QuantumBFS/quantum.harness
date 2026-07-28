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
