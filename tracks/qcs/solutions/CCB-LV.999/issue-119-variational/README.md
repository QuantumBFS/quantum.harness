# Issue #119 classical variational audit

This directory executes the pinned `PLAN.md` with the source-audited Anderson
ordering amendment documented in `SOURCE_AUDIT.md`.

Current local result: the independently reloaded M=1500 GA-ordered saved MPS
has E = −62.26005366939074 Eₕ, 3.371840994 mEₕ below the verified SKQD
anchor. See `RESEARCH_REPORT.md` for scope and limitations and
`artifacts/anderson-ga-m1500/` for the compact committed result bundle.

## Confirmed setup

- 2Fe–2S: 20 spatial orbitals, 30 electrons, `MS2=0`, SU(2) singlet, Fiedler
  ordering, local M=250→500 calibration.
- Four-impurity Anderson: 32 spatial orbitals, 32 electrons, `MS2=0`, SU(2)
  singlet, CCSD natural-orbital FCIDUMP, local M=100 Fiedler/GA comparison.
- The headline is always the direct expectation value of a saved finite-M MPS.
  Discarded-weight extrapolations, if later added, remain auxiliary.

## Environment

```bash
conda create -y -p .venv python=3.12
conda run -p .venv python -m pip install uv==0.11.32
conda run -p .venv uv sync --all-groups
```

## Local workflow

Run from this solution directory:

```bash
RUN_DIR=../../../results/issue-119-local/anderson-ga-m1500
conda run -p .venv uv run python -m src.fetch_instances \
  --instance anderson --run-dir "$RUN_DIR"
conda run -p .venv uv run python -m src.rhf_check \
  --fcidump "$RUN_DIR/inputs/anderson_impurity_model_4i_28b_32e.fcidump" \
  --output "$RUN_DIR/anderson-rhf.json"
conda run -p .venv uv run python -m src.dmrg_runner \
  --config configs/anderson-ga-m1500-local.toml --run-dir "$RUN_DIR"
conda run -p .venv uv run python -m src.verify_checkpoint \
  --run-dir "$RUN_DIR"
conda run -p .venv uv run python -m src.render_convergence \
  --run-dir "$RUN_DIR"
```

Each ordering probe uses a separate run directory and independently verifies
its input before starting the solver.

## Artifacts

Every calculation writes `run.json`, `config.toml`, `ordering.json`,
`sweeps.csv`, `result.json`, `checkpoint-verification.json`, and the block2
checkpoint below `tracks/qcs/results/<run-id>/`. Full results and checkpoints
are gitignored. The compact M=1500 result, verification record, numerical
tables, and figures are copied to `artifacts/anderson-ga-m1500/`.

Tests:

```bash
conda run -p .venv uv run pytest -q
```

## Slurm continuation

The checkpointed SCNet-ready wrapper, resource estimate, preflight command, and
restart procedure are in [`cluster/README.md`](cluster/README.md). The wrapper
can cap a job at any exact M in the production ladder and independently reloads
the final saved MPS before declaring the stage complete.
