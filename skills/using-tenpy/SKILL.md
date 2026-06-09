---
name: using-tenpy
description: Use when choosing or running TeNPy (Python) for MPS calculations — especially iTEBD (the algorithm MPSKit lacks), plus iDMRG, VUMPS, finite DMRG/TEBD, and finite-T purification — including model setup, the tangent-space gradient-norm probe (tangent_projector_test), symmetry via conserve, threading, or TeNPy/numpy-ABI setup failures.
---

# TeNPy

Use TeNPy (Tensor Network Python; Hauschild & Pollmann) as the harness's Python MPS stack. Its decisive role is **iTEBD** — the infinite imaginary-time algorithm MPSKit does not provide — but it also has iDMRG, VUMPS, finite DMRG/TEBD, and finite-temperature purification.

## Sources

- Method card: `skills/method-mps/SKILL.md`
- Install: `make install tenpy` — creates the **isolated** `.venv-tenpy` and installs `physics-tenpy` + matplotlib (TeNPy pins a numpy ABI, so it must not share the main `.venv`/anaconda base or imports hit ABI mismatches). Run scripts with `.venv-tenpy/bin/python scripts/<name>.py`.
- Smoke test (also run by the install target): `.venv-tenpy/bin/python -c "import tenpy; print(tenpy.__version__)"`
- Primary literature: `1701.07035` (VUMPS) in `.knowledge/literature/mps-based-algorithm/`.

## Workflow

1. Confirm the model, geometry (`bc_MPS='infinite'` vs `'finite'`), bond dimension `chi_max`, and `conserve` before code.
2. Choose the algorithm with `/method-mps`: **iTEBD** (`TEBDEngine`, imaginary time) is the usual reason to be in TeNPy; iDMRG / VUMPS also available. For *infinite VUMPS/IDMRG production*, MPSKit is the faster in-stack route — use TeNPy's VUMPS mainly as a cross-check or when staying in Python.
3. Build the model (`SpinChain`, Hubbard, …) and the initial MPS from a product state.
4. Run; converge on the right signal per algorithm — energy plateau **and** τ-refinement for iTEBD, the **tangent-space gradient norm ‖B‖** (`tangent_projector_test`) for VUMPS/iDMRG.
5. Record `chi_max`, `svd_min`, the τ schedule and steps, `conserve`, the numpy/OpenMP thread env, and the final ‖B‖.

## Parameter setup

Use this as the source for TeNPy-specific knobs unless the paper or official code fixes a value.

- **Bond dimension `chi_max`** — in `trunc_params`. The accuracy lever; D-series until energy asymptotes; scale for gapless.
- **Truncation `svd_min`** — singular values below this are dropped (e.g. `1e-14`); the soft floor on the bond.
- **Geometry `bc_MPS`** — `'infinite'` (uniform, with a unit cell set by the lattice `L`) or `'finite'`. Unit cell must hold the order period (2-site for Néel; rotate to 1-site for critical XXZ).
- **Symmetry `conserve`** — `None` (no symmetry, the VUMPS-paper benchmark choice), `'Sz'`, `'parity'`, or `'N'`. Pins the sector and speeds up; match the paper.
- **iTEBD time step τ (`dt`)** — refine in stages (`0.1 → 5e-4`); 2nd-order Trotter error ~τ². Build the gate with `calc_U(order, dt, type_evo='imag')`; evolve with `evolve(N_steps, dt)` (the method is `evolve` in TeNPy 1.1, not `update`). **Run each τ-stage to its energy plateau** — a small τ alone gives tiny per-step ΔE regardless of convergence.
- **Initial state** — `MPS.from_lat_product_state(model.lat, [...])` in the target sector.

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| `chi_max` | dominant accuracy lever; cost ~χ³ | χ-series until energy asymptotes |
| `svd_min` | truncation floor | `1e-14` |
| `bc_MPS` | infinite vs finite; unit cell | `'infinite'`, cell = order period |
| `conserve` | block-diagonalizes → faster, pins sector | `None` to match the VUMPS paper; `'Sz'` for speed |
| τ schedule (`dt`) + `N_steps` | iTEBD Trotter error + convergence | `0.1→5e-4`, each stage to its plateau |
| numpy / OpenMP threads | wall time; benchmark fairness | set `OMP_NUM_THREADS` etc **before importing numpy**; for a benchmark, confirm the count with the user |

## Code shape

Check exact APIs against the installed TeNPy docs before a production script; the harness-level shape:

```python
import os
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[v] = '1'            # set BEFORE importing numpy; '1' for a clean benchmark
import numpy as np
from tenpy.models.spins import SpinChain
from tenpy.networks.mps import MPS
from tenpy.networks.mpo import MPOTransferMatrix
from tenpy.algorithms import tebd
from tenpy.algorithms.vumps import SingleSiteVUMPSEngine

# 1. Model (infinite, 2-site cell, no symmetry).
model = SpinChain({'L':2,'S':0.5,'Jx':1.0,'Jy':1.0,'Jz':2.0,'hz':0.0,
                   'bc_MPS':'infinite','conserve':None})

# 2. Initial product state.
psi = MPS.from_lat_product_state(model.lat, [['up'],['down']])

# 3. iTEBD: refine τ in stages, each to its energy plateau.
eng = tebd.TEBDEngine(psi, model, {'trunc_params':{'chi_max':54,'svd_min':1e-14}})
for dt in [0.1,0.05,0.02,0.01,5e-3,1e-3,5e-4]:
    eng.calc_U(2, dt, type_evo='imag')
    eng.evolve(2000, dt)          # method is evolve(N_steps, dt) in TeNPy 1.1
e_site = float(np.mean(model.bond_energies(psi)))

# 4. Tangent-space gradient norm ‖B‖ via the VUMPS engine's projector test.
p = psi.copy(); p.canonical_form()
veng = SingleSiteVUMPSEngine(p, model, {'trunc_params':{'chi_max':54,'svd_min':1e-14}})
env, _Es, _ = MPOTransferMatrix.find_init_LP_RP(model.H_MPO, veng.psi, calc_E=True)
sL, sR = veng.tangent_projector_test(env)
bnorm = float(np.sqrt(np.mean(np.asarray(sL)**2)))   # per-site RMS, left projector
```

## Time estimate

Cost is `(steps · L_cell · d · χ³) ÷ throughput`.

- iTEBD per layer ∝ unit-cell × physical dim × χ³ (the SVD truncation dominates).
- **iTEBD needs many steps and converges slowly near criticality** — at fixed τ the per-step ΔE shrinks, so convergence is governed by τ-refinement plus total imaginary time, not step count alone. This is why FIG.7's iTEBD curve lags VUMPS, especially in the critical panel.
- Memory modest (O(χ²)); compute is the gate.
- χ in the tens (FIG.7: 54–120) is seconds-to-minutes per τ-stage on a laptop; the full τ schedule for a critical system can run long — bound it.
- **For a wall-time benchmark:** confirm the thread count with the user (Python has no JIT warm-up, but exclude env-build and per-checkpoint measurement time) — reproduce-paper *performance benchmark* rules.

## Use Another Route When

- The target is **infinite VUMPS / IDMRG production** and speed matters → MPSKit (`/using-mpskit`) is the faster in-stack Julia route; use TeNPy here mainly for iTEBD or a Python cross-check.
- The target is genuinely 2D / a wide system → PEPS (`/using-pepskit`).
- A finite Julia/ITensor workflow is preferred, or the paper used runnable official ITensor code → `/using-itensors`.
