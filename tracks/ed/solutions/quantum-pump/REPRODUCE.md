# Reproducing the interacting RMH Thouless-pump benchmark

The final answer is
[t73_rmh_response_submission_final.pdf](t73_rmh_response_submission_final.pdf).
This file gives the shortest auditable route from a fresh checkout to the
archived checks and new calculations.

## 1. Fetch the pinned full delivery

The official PR keeps only the final answer and this reproduction guide.
Source code, data, figures, and Slurm files are pinned at commit
`8bb3c643b918fb8348217b41a0f29c4cb9bc60da` in the contributor repository:

```bash
git clone https://github.com/yt641798730/quantum.harness.git
cd quantum.harness
git checkout 8bb3c643b918fb8348217b41a0f29c4cb9bc60da
cd RMH
```

Directory map:

- `project/`: ED implementation, tests, plotting scripts, and Slurm jobs.
- `benchmark_data/`: compact CSV/JSON tables used in the final response.
- `project/results/`: complete `L=6,8` data and extension scans.
- `project/revision_results/`: high-resolution `L=10` server output.
- `submission/`: TeX source; `reports/figures/submission_final/`: its figures.

## 2. Recreate the numerical environment

The archived run used Python 3.14.4, NumPy 2.4.4, SciPy 1.17.1, and
Matplotlib 3.10.8:

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
PY=.venv/bin/python
```

On Windows PowerShell use:

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
$PY = (Resolve-Path .venv\Scripts\python.exe).Path
```

## 3. Validate the delivered numbers and ED implementation

```bash
$PY project/verify_delivery.py
$PY project/test_rmh_ed.py
```

Expected final lines:

```text
PASS topology: C_MB changes from 2 to 0
PASS critical points: L=6 and L=8
PASS dense FHS brackets: L=6 and L=8
PASS real time: L=6, Tt=160
PASS extensions: interaction-induced and U-V scans
All archived benchmark checks passed.
All RMH ED tests passed.
```

These checks cover basis dimensions, Hermiticity, the current finite
difference, noninteracting topology, norm preservation, the dense Chern
transition, critical gaps, real-time charge, and both extension scans.

## 4. Recompute the four core observables

The Hamiltonian convention is
`t=1`, `delta(phi)=0.5 cos(phi)`, `Delta(phi)=sin(phi)`, at half filling
`N_up=N_down=L/2`. Here `theta` is the boundary twist and `phi` is the
Rice-Mele pump parameter.

Run the quick end-to-end calculation:

```bash
$PY project/run_benchmark.py \
  --mode quick \
  --output project/results/reproduced_quick
```

Use `--mode full` for the production grids. The command computes:

1. low-energy spectra `E_n(phi)` and the full-torus minimum gap;
2. the gauge-invariant FHS many-body Chern number;
3. Wilson/Resta polarization and adiabatic pumped charge;
4. finite-time, twist-averaged pumped charge.

## 5. Recompute the dense transition scan

```bash
$PY project/run_transition_scan_dense.py \
  --coarse-file benchmark_data/transition_scan.csv \
  --data-dir project/results/reproduced_transition_dense
```

The scan uses `L=6: U/t=2.95:0.025:3.30` and
`L=8: U/t=3.10:0.025:3.50`. Expected FHS brackets are:

| Size | Last `C_MB=2` | First `C_MB=0` |
|---|---:|---:|
| `L=6` | `U/t=3.100` | `U/t=3.125` |
| `L=8` | `U/t=3.275` | `U/t=3.300` |

Direct gap minimization gives
`U_c(L=6)/t=3.115519739`,
`U_c(L=8)/t=3.288084365`, and
`U_c(L=10)/t=3.390599703`.

## 6. Recompute phase maps and extensions

The `21 x 21` `U-phi` multi-observable map is produced with:

```bash
$PY project/run_phase_map_multiobservable_test.py \
  --output project/results/reproduced_phase_map_21x21 \
  --length 6 --n-u 21 --n-phi 21 --n-theta 8
```

The restartable `L=10` benchmark and the two extension scans are submitted
from `project/`:

```bash
bash server/submit_all.sh
bash server_extensions/submit_extensions.sh
```

Extension 1 uses `lccount` and searches for interaction-induced pumping.
Extension 2 uses `hccount` and maps the `17 x 17` `U-V` plane.

## 7. Headline values to compare

| Quantity | Delivered value |
|---|---:|
| `C_MB(U=0)` | `2` |
| `C_MB(U=4,8)` | `0` |
| `Q_real-time(L=6,U=0,Tt=160)` | `2.00859155` |
| `Q_real-time(L=6,U=4,Tt=160)` | `0.00693293` |
| `Q_real-time(L=6,U=8,Tt=160)` | `0.00421660` |
| reliable interaction-induced paths | `12` |
| reliable points in the `U-V` scan | `79 / 289` |

The final PDF has 19 A4 pages and SHA-256:

```text
B43289589992733B183BBA1EF747D20C7AA0E459F10BF75CCBA70D3F3784BDFA
```
