# Isolated TRIQS/CT-HYB runtime

This runtime is an independent continuous-bath reference. It is not imported by
the Julia purification solver or the Python finite-bath ED oracle.

The tested Linux runtime uses Python 3.12, TRIQS 4.0.0, CT-HYB 4.0.0,
OpenMPI 5, and MPI-enabled HDF5. `conda-linux-64.lock` records exact package
URLs, builds, and MD5 hashes. Bytes are reproducible while those immutable
conda-forge artifacts remain available.

## Bootstrap

Use micromamba 2.8.1-0 for Linux x86-64:

```bash
curl -fL \
  https://github.com/mamba-org/micromamba-releases/releases/download/2.8.1-0/micromamba-linux-64 \
  -o micromamba
echo "9689782d863c05a1bf5d2d371ba527104e7a4eb4310c1637d8653b751aed9c82  micromamba" \
  | sha256sum -c -
chmod 0755 micromamba
```

Create the exact environment in the gitignored results tree:

```bash
export MAMBA_ROOT_PREFIX="$PWD/tracks/mps/results/frustration-free/mamba-root"
./micromamba create --yes \
  --prefix "$PWD/tracks/mps/results/frustration-free/triqs-4.0.0" \
  --file tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock
```

`environment.yml` is the human-readable top-level specification. Re-solving it
may select newer transitive packages; use the explicit lock for reproduction.

## Smoke test

This command is an environment smoke test only. It does not set a physical
hybridization, run Monte Carlo, estimate autocorrelation, or produce a
scientific comparison.

```bash
./micromamba run \
  --prefix "$PWD/tracks/mps/results/frustration-free/triqs-4.0.0" \
  python tracks/mps/solutions/frustration-free/triqs/smoke_test.py
```

The warning `could not identify MPI environment` is expected for a serial smoke
test. Production CT-HYB runs should launch through the environment's `mpirun`
and record MPI ranks, random seeds, warmup/measurement cycles, perturbation
order statistics, and autocorrelation diagnostics.

`cthyb-production.schema.json` is the fail-closed configuration scaffold.
`cthyb-production.example.json` deliberately has `production_ready=false` and
`scientific_comparison=false`; a future production runner must introduce and
validate a new ready schema before it may launch Monte Carlo.

The checked-out TRIQS and CT-HYB repositories under the references results tree
are source references at post-4.0 commits. The executable baseline intentionally
uses the mutually compatible stable conda packages `4.0.0`; source builds are a
separate optimization path, not mixed into this locked environment.
