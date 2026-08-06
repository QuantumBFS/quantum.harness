# frustration-free - Interacting Thouless Pumps

## Team

| | |
|---|---|
| **Team name** | frustration-free |
| **Members** | 蒋玮琪 ([jiangweiqi001](https://github.com/jiangweiqi001)), 陈硕 ([ChS-YHWH](https://github.com/ChS-YHWH)), 马追景 ([desitterf](https://github.com/desitterf)) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Determine when Hubbard interactions preserve, destroy, or generate quantized Thouless pumping by comparing the many-body Chern number, minimum gap, adiabatic polarization winding, and finite-time transported charge, going beyond static noninteracting topology with exact many-body and real-time diagnostics. |
| **Catalog issue** | Addresses #36, "[challenge]: Exact diagonalization benchmark for interacting Thouless pumps," released by Chen Cheng, Lanzhou University. |
| **Track** | <code>tracks/ed/solutions/frustration-free/</code>, selected from the issue's <code>Method: Exact Diagonalization</code> field. |
| **Report** | [English challenge report](report.md) |

## Rice-Mele-Hubbard Pump ED

This is the canonical structured exact-diagonalization project for the interacting
spinful Rice-Mele pump in `36.md`. It computes and compares

```text
C_MB, Delta_min, Q_adiabatic, Q_real_time(T).
```

The production workflow has one Hamiltonian implementation, one CLI, and no
nested standalone project. Historical and extension experiments imported from
the partner tree live under `experiments/`; they are explicitly isolated from
the canonical solver and documented in `experiments/README.md`.

## Model and conventions

The fixed-sector Hamiltonian is

```text
H = -sum[j,sigma] (t + (-1)^j delta(phi))
      (cdag[j,sigma] c[j+1,sigma] + h.c.)
    + Delta(phi) sum[j,sigma] (-1)^j n[j,sigma]
    + U sum[j] n[j,up] n[j,down],

delta(phi) = delta0 cos(phi),
Delta(phi) = Delta0 sin(phi).
```

Production conventions are centralized in `src/model.py`:

- sites are zero based and use `(-1)^j`;
- `(L-1) -> 0` carries `exp(+i theta)`;
- `0 -> (L-1)` carries `exp(-i theta)`;
- both spins use the same charge twist;
- the boundary current is `dH/dtheta`;
- FHS state arrays use `(theta, phi, basis)` order.

With this orientation, the default U=0 pump gives `C_MB=+2`.

## Structure

```text
hubbard-pump/
|-- src/
|   |-- model.py              # basis, Hamiltonian, boundary current
|   |-- diagonalization.py    # eigensolvers, residuals, Fraction cache, gap
|   |-- topology.py           # FHS Chern and Resta polarization winding
|   |-- dynamics.py           # unitary evolution and finite-time charge
|   |-- batch.py              # complete manifests and Chern checkpoints
|   |-- cluster_workflows.py  # restartable per-key cluster calculations
|   |-- workflows.py          # benchmark and U-scan composition
|   `-- io_utils.py           # YAML and result persistence
|-- scripts/run.py            # benchmark and scan-u CLI
|-- scripts/cluster_worker.py # manifest-strict Slurm worker CLI
|-- tests/                    # consolidated behavioral regression tests
|-- configs/default.yaml
|-- cluster/launch.sh         # retrying run controller
|-- cluster/worker.slurm      # one static/refine/realtime array task
|-- cluster/scan_u.slurm      # small legacy scan wrapper
|-- experiments/               # imported, auditable extension families
|-- results/
`-- requirements.txt
```

`src/` contains source modules only. Scripts never define Hamiltonian terms or
numerical solvers.

## Imported experiments and result merge

The partner tree was fetched from commit `9ebcab9` and merged under
`experiments/` without replacing local files. Its tracked tree contained no
result files, so the existing local `results/` remain the numerical record;
the merge contributes runnable experiment families and their provenance, not
new unverified numbers. Useful additions include sector-resolved
many-body/spin/charge gaps, dimerization-crossing dynamics, current and
coherence observables, and SSH/single-hole/spinon-holon baselines. The partner
FHS and cache implementations remain historical because the canonical code
already contains the corrected twist orientation, Fraction cache reuse,
Hermiticity checks, and residual checks used by `36.md`.

See [`WORKFLOW.md`](WORKFLOW.md) for execution and audit rules, and
[`experiments/README.md`](experiments/README.md) for entrypoints and output
namespaces. Imported Slurm files are environment-specific templates and must
be adapted before cluster submission.

## Installation

Python 3.10 or newer is recommended. When network installation is needed, use
a domestic mirror first:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -r requirements.txt
```

## Local benchmark

From this directory:

```bash
python scripts/run.py benchmark --config configs/default.yaml
```

The command prints one JSON document containing all four observables and their
diagnostics. The default local reference (`L=4`, `U=0`) produces approximately

```text
C_MB             = 2
Delta_min        = 3.6
Q_adiabatic      = 2
Q_real_time(T=10)= 1.9872303617
```

Command-line overrides are intentionally small and explicit:

```bash
python scripts/run.py benchmark --config configs/default.yaml \
  --L 6 --U 0 --period 20 --time-steps 800
```

## U scan

```bash
python scripts/run.py scan-u --config configs/default.yaml \
  --values -8 0 8 --grid-sizes 5 10
```

Grid sizes must be increasing integer multiples. Exact `Fraction` coordinates
ensure that refining `5 -> 10` reuses every old vertex instead of diagonalizing
it again.

Each scan writes:

- `results/scan_summary.json` and `results/scan_summary.csv`;
- one deterministic `results/grid_data/*.npz` file per `(U, grid)`.

NPZ files contain ground states, Berry flux, `E0`, `E1`, gaps, Hermiticity
errors, Ritz residuals, and a JSON parameter record. Ground states are retained
so later checkpoint/cache work can reuse them without changing the physics
modules.

`results/reference/` contains the original L=6 full eigensystem for all 400
eigenvalues plus a sparse matrix snapshot from the later production convention
for a complete element-by-element Hamiltonian comparison.

## Numerical methods

- Low energies use Hermitian `eigsh`; both lowest Ritz residuals are checked.
- Full diagonalization remains available through
  `src.diagonalization.diagonalize_full` for small reference sectors.
- `Delta_min` is scanned on nested periodic `(theta, phi)` grids.
- `C_MB` uses gauge-invariant FHS link variables and principal-branch fluxes.
- `Q_adiabatic` is the many-body polarization winding required by `36.md`,
  evaluated continuously from the twist Wilson loop. It equals `C_MB` over a
  complete gapped cycle.
- `Q_adiabatic_fixed_theta` integrates the Berry curvature along the pump path
  at `theta=0`, using a centered narrow twist strip. It is retained only as a
  finite-size diagnostic and is not used as `Q_adiabatic` in the main figures.
- `Q_real_time(T)` uses midpoint-Magnus sparse Krylov propagation and integrates
  the boundary current.

## Cluster run

The complete L=8 study uses the Cartesian product of 41 interaction values and
11 hopping values (`t=0.5,...,1.5`), or 451 static keys. Every key produces
`C_MB`, the torus-grid `Delta_min`, and `Q_adiabatic`. The real-time manifest
contains 1353 keys for `T=2,10,50`; each key doubles its time steps until the
two latest charges differ by no more than the configured tolerance.

`cluster/launch.sh` must run under tmux with an immutable source snapshot. It
submits missing keys in bounded Slurm arrays and validates outputs after every
submission. A failed `sbatch --wait`, task timeout, or node failure is recorded
and retried with a longer wall limit. It does not publish aggregate files until
all expected static, selected N=20 refinement, and real-time results validate.

Required environment variables are:

```bash
SCAN_RUN_DIR=/absolute/run/directory
SCAN_SOURCE_DIR=/absolute/immutable/source/hubbard-pump
SCAN_SOURCE_COMMIT=<git-commit>
SCAN_PYTHON=/absolute/venv/bin/python
```

An optional `SCAN_LEGACY_DIR` points to reusable schema-v2 N=10 Chern
checkpoints. Launch from a named tmux session with:

```bash
SCAN_RUN_DIR="$SCAN_RUN_DIR" \
SCAN_SOURCE_DIR="$SCAN_SOURCE_DIR" \
SCAN_SOURCE_COMMIT="$SCAN_SOURCE_COMMIT" \
SCAN_PYTHON="$SCAN_PYTHON" \
SCAN_LEGACY_DIR="$SCAN_LEGACY_DIR" \
bash "$SCAN_SOURCE_DIR/cluster/launch.sh"
```

The run directory contains `chern10/`, `static/`, `chern20/`, `realtime/`,
`logs/`, immutable `task_maps/`, and `submissions.log`. A successful run ends
with `aggregate/run_complete.json` and CSV/JSON summaries. The controller state
is always visible in `controller_status.json`; invalid/corrupt results enter an
auditable `ATTENTION_REQUIRED` state instead of being silently skipped.

## Verification

```bash
pytest -q tests
```

The regression suite checks the production Hamiltonian matrix and twist,
`theta=0/2*pi` periodicity, the L=6 dimension and spectrum fingerprint, FHS
orientation and gauge invariance, nested-cache reuse, the U=0 Chern/gap/Resta
benchmarks, and finite-time charge/norm preservation.

## Extension boundary

New interactions belong only in `src/model.py`. New observables should consume
`EDEngine` in a focused source module. New parameter studies should compose
existing observables in `src/workflows.py` and expose options through the same
CLI. This keeps future U/V scans, path optimization, spin diagnostics, or ED to
MPS comparisons from duplicating the Hamiltonian.
