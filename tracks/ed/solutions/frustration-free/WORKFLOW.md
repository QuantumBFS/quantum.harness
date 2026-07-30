# Reproducible Workflow

## Two layers

The root `src/`, `scripts/`, `configs/`, and `results/` form the canonical
pipeline for `36.md`: fixed-sector Rice-Mele-Hubbard ED, FHS `C_MB`, minimum
gap, adiabatic charge, and real-time charge. This code owns the production
Hamiltonian sign, twist, basis ordering, cache keys, and output schema.

`experiments/` contains the imported partner implementations. It adds useful
coverage (sector-resolved spin/charge gaps, delta-crossing dynamics,
correlations, SSH and single-hole/spinon-holon baselines) without duplicating
or replacing the canonical solver. See `experiments/README.md` and
`experiments/provenance.yaml` for the registry and source commit.

## Local commands

Use the project environment and a domestic PyPI mirror when dependencies are
not already installed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/run.py benchmark --config configs/default.yaml
```

Imported experiment tests are run from their own directory so their historical
`src` packages cannot shadow the canonical one:

```bash
cd experiments/rmh_gap_landscape && python -m pytest -q tests
cd ../baseline-ed && python -m pytest -q tests
```

Do not run full scans as a validation step. Reuse compatible files in
`results/` and run only the requested missing or failed units.

## Results and audit trail

All maintained outputs belong below the repository-level `results/` directory.
The canonical pipeline uses deterministic names and manifests; imported
families retain their own schemas under a named namespace. A result is
reusable only when its manifest records the model convention, sector, grid,
solver, source commit, and parameter values. The imported source had no
tracked results, so this merge does not claim additional numerical results.

## Cluster templates

The existing `cluster/launch.sh` and `cluster/*.slurm` are the canonical
restartable workflow. Run them in a named `tmux` session with the environment
variables documented in `README.md`. Imported Slurm files under
`experiments/` are provenance templates from another environment; set the
partition/account/interpreter/project path for the target machine before use.
Never place credentials, private keys, or machine-specific absolute paths in
the repository.
