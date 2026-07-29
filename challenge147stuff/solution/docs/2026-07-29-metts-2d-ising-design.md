# Design Spec — METTS for 2D Finite-Temperature Transverse-Field Ising

- **Challenge:** #147 (PEPS-based algorithm), released by Wei Li, ITP CAS.
- **Date:** 2026-07-29
- **Status:** Approved by user (architecture, two-version split, staged file outputs).
- **Hardware context:** laptop = 8 cores / 3.7 GB RAM; a supercomputer will be available later. So we deliver a low-perf **v0** (runs on the laptop) and a higher-requirement **v1** (prepared for the supercomputer), sharing core code.

## 1. Objective

Implement a **METTS**-based finite-temperature tensor-network method for the transverse-field Ising model (TFIM) on an Lx×Ly square lattice with open boundaries,

$$H = -J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z - h\sum_i\sigma_i^x,\quad J=1,$$

near the quantum critical point $h_c/J\approx 3.044$. Compute thermodynamics over $\beta J\in[0.1,1.0]$: free-energy density $f=-\ln Z/(\beta N)$, internal energy density $u=\langle H\rangle/N$, specific heat $C=\beta^2(\langle H^2\rangle-\langle H\rangle^2)/N$, and (bonus) uniform susceptibility $\chi=\frac{\beta}{N}\sum_{i,j}(\langle\sigma_i^z\sigma_j^z\rangle-\langle\sigma_i^z\rangle\langle\sigma_j^z\rangle)$. Validate against QMC (mandatory), compare against a tanTRG/MPO-LTRG baseline (bonus).

## 2. Two versions (selected by config, not by rewriting code)

| | **v0 — laptop test** | **v1 — real / supercomputer** |
|---|---|---|
| METTS geometry | snake map → 1D MPS (Lx·Ly sites) | true 2D PEPS + boundary-MPS cluster contraction |
| Lattice | 4×4 → 6×6 (ED-anchored), 8×8 sanity | 10×10 (scalable) |
| Bond dim / samples | small D, few samples, short sweeps | large D, many samples, full sweeps |
| βJ grid | ~6 points, h/J=3.0 | ~10 points, h/J∈{2.5,3.0,3.5} |
| Bonuses | χ on small lattice; 4×4 ED as pseudo-baseline | χ on 10×10; independent MPO-LTRG/tanTRG baseline |
| Runtime per stage | minutes (≤10 min) | minutes–hours (supercomputer) |

Design property: **v0 and v1 share `core/`, `qmc/`, and the observable contract**; only the METTS geometry and the baseline differ. v0 validates physics + pipeline on the laptop; v1 swaps in heavier engines for the real benchmark.

## 3. File / module layout

```
challenge147stuff/solution/
├── core/           # model.py, lattice.py, observables.py, io.py
├── ed/             # exact diagonalization (gold anchor, ≤4×4)
├── qmc/            # Swendsen-Wang QMC (mandatory reference truth)
├── metts/          # METTS engine: v0 snake-MPS, v1 2D-PEPS
├── baseline_tantrg/# MPO-LTRG baseline (bonus)
├── scripts/        # run_*.py drivers + run_all.sh + validate.py + plot.py
├── data/           # CSV outputs + JSON run manifests
├── figures/        # PNG plots
└── docs/           # REPORT_zh.md, REPORT_en.md, this design spec
```

Each module: single responsibility, independently testable, communicates through well-defined interfaces.

### Module responsibilities

- **`core/model.py`** — TFIM Hamiltonian construction, σˣ/σᶻ operators. Exploit Z₂ spin-flip symmetry where it reduces cost.
- **`core/lattice.py`** — square lattice with open BC + snake-mapping index (row-major serpentine).
- **`core/observables.py`** — unified `u, C, f, χ` interface every engine implements; estimators are engine-agnostic.
- **`core/io.py`** — CSV read/write + JSON run manifest (records lattice size, h, β grid, bond dim, sample count, runtime, peak memory, actual-vs-requested size for OOM fallback).
- **`ed/`** — dense/sparse exact diagonalization for ≤4×4; outputs u, C, f. Gold-standard anchor.
- **`qmc/`** — TFIM → (2+1)D classical Ising; Swendsen-Wang cluster updates; outputs u, C, f, χ with statistical error bars (binning/SEM).
- **`metts/`** — v0: snake-MPS, σˣ-basis METTS sampling, Trotter imaginary-time evolution; v1: 2D PEPS + cluster contraction. Outputs u, C, f, χ + convergence data.
- **`baseline_tantrg/`** — simplified MPO-LTRG (tangent-space-free LTRG as a stand-in for tanTRG); outputs accuracy/time/memory.
- **`scripts/`** — one `run_*.py` per engine; `run_all.sh` one-command reproduction; `validate.py` aggregates relative errors vs QMC; `plot.py` renders figures.

## 4. Data flow

`run_*.py` → `data/*.csv` (+ JSON manifest) → `plot.py` → `figures/*.png` → `validate.py` → `validation_summary.csv` → reports reference these files. **All numerical results persist only as CSV; reports embed tables/figure refs, never hard-coded numbers.**

## 5. Validation chain (mandatory, progressively tightening)

1. **ED self-consistency:** METTS/QMC at 4×4 vs ED — relative error of u and C below threshold.
2. **QMC cross-check:** QMC validated against ED at 4×4, then promoted to the 10×10 ground truth.
3. **METTS vs QMC:** report relative errors of u, C over βJ∈[0.1,1.0] + lowest stable β.
4. **Convergence:** METTS reports convergence in sample count and bond dim D, with binning/SEM statistical error; report samples needed for rel-err < 1% on u and < 3% on C at βJ=0.8.
5. **OOM fallback:** any stage that exceeds memory auto-degrades to the next smaller lattice; the run manifest records the actual size and the report annotates this honestly.

## 6. Staged plan (medium granularity; each stage → concrete file artifacts)

**Stage 0 — Environment & skeleton.** Install numpy/scipy/matplotlib; create the directory tree; stub modules with interfaces. → `solution/` tree, `requirements.txt`, `core/io.py`.

**Stage 1 — Core + ED anchor.** Implement model/lattice/observables/io; ED for 4×4. → `core/*.py`, `ed/ed.py`, `data/ed_4x4_h3.0.csv`.

**Stage 2 — QMC reference.** Swendsen-Wang QMC; validate vs ED at 4×4; run 6×6. → `qmc/qmc.py`, `data/qmc_{Lx}x{Ly}_h{h}.csv`.

**Stage 3 — METTS v0 (snake-MPS).** σˣ-basis METTS + Trotter evolution; validate vs ED(4×4) then QMC(6×6); convergence in D and sample count. → `metts/metts_v0.py`, `data/metts_v0_*.csv`, `figures/convergence_v0.png`.

**Stage 4 — Full curves + validation + χ.** Aggregate f/u/C/χ over βJ grid; `validate.py` relative-error tables; plots. → `figures/thermo_*.png`, `data/validation_summary.csv`.

**Stage 5 — Reports (zh + en).** Pull numbers from CSV/figures; algorithm, contraction strategy, imaginary-time scheme, operation instructions, results. → `docs/REPORT_zh.md`, `docs/REPORT_en.md`.

**Stage 6 — v1 engines + tanTRG baseline (bonus).** 2D-PEPS METTS skeleton + MPO-LTRG baseline; accuracy/time/memory comparison. → `metts/metts_v1.py`, `baseline_tantrg/mpo_ltrg.py`, `data/baseline_compare.csv`.

**Stage 7 — One-command repro.** `run_all.sh` runs the full pipeline end-to-end. → `scripts/run_all.sh`, `README.md`.

Each stage targets v0 first (files produced on the laptop), then promotes to v1 where hardware allows. Stage outputs are committed as files so progress is reviewable at every step.

## 7. Constraints & risk mitigations

- **No MATLAB:** `QSpinTN.ml` is algorithm-reference only; nothing is run from it.
- **3.7 GB RAM:** v0 snake-MPS keeps bond dims small; 2D contractions use boundary-MPS / truncation; OOM auto-degrades lattice size.
- **METTS low-T variance:** reported via binning/SEM; sample-count target stated; honest reporting if not met within budget.
- **Reproducibility:** every run writes a JSON manifest; `run_all.sh` reproduces from clean state.
