# Anderson block2 Slurm package

This package extends the verified local M=200 calculation into a checkpointed
bond-dimension ladder on a Slurm CPU node. It does not submit anything by
itself.

## Pinned scientific setup

| Item | Value |
|---|---|
| Hamiltonian | Tracker four-impurity Anderson FCIDUMP, SHA-256 `9c8ceb3faa39ccb9cf2c15632cdc748e449cf26197ee1e8251092a6bb49ce4b6`; signs, integrals, and core constant are read directly from that file |
| Size | 32 spatial orbitals, 32 electrons |
| MPS geometry | finite open orbital chain after the recorded orbital permutation |
| Sector | `MS2=0`, SU(2) singlet `spin=0` |
| Ordering | corrected 64-start block2 GA ordering; a resumed checkpoint must reuse its saved `ordering.json` |
| Solver | block2 0.5.3 quantum-chemistry DMRG |
| Bond ladder | M=100, 200, 400, 600, 800, 1000 |
| Observable | normalized expectation `⟨ψ_M|H|ψ_M⟩/⟨ψ_M|ψ_M⟩` of the saved finite-M MPS |

The submission must be ratified against this table before a real run.

## Files

- `anderson_block2_preflight.sbatch` — allocation-only input/resource check;
  never starts DMRG.
- `anderson_block2.sbatch` — production entrypoint; writes progress after every
  bond-dimension stage and resumes the same checkpoint on rerun.
- `../configs/anderson-production.toml` — scientific and solver settings.
- `../src/cluster_entrypoint.py` — FCIDUMP/sector/resource preflight, DMRG,
  independent checkpoint reload, and report rendering.

## One-time remote preparation

SCNet exposes glibc 2.17. The universal `uv.lock` includes newer
manylinux_2_28-only NumPy/SciPy wheels, so use the hashed SCNet wheel lock and
forbid source builds:

```bash
cd ~/quantum.harness/tracks/qcs/solutions/CCB-LV.999/issue-119-variational
module load anaconda3/2023.09
test -x .venv/bin/python || conda create -y -p "$PWD/.venv" python=3.12 pip
conda run -p "$PWD/.venv" python -m pip install uv==0.11.32
.venv/bin/uv pip install \
  --python .venv/bin/python \
  --only-binary :all: \
  --require-hashes \
  -r cluster/requirements-scnet.txt

RUN_DIR=../../../results/issue-119-cluster/anderson-ga
.venv/bin/python -m src.fetch_instances \
  --instance anderson \
  --run-dir "$RUN_DIR"
```

The login node may download the pinned FCIDUMP; the compute job has no network
dependency. `fetch_instances` checks the header and SHA-256 before accepting
the file.

The optional `anderson-block2.def` preserves the universal `uv.lock` in a
modern container. The current SCNet account cannot build it because user
namespaces and subordinate UID mappings are disabled; use it only if an
administrator supplies fakeroot access or the image is built elsewhere.

## Resource estimate

The local M=200 GA run took 20.243 s at 8 threads and used 548 MB RSS. A raw
M³ extrapolation over the declared ladder through M=1000 is about 1.27 h at
that measured 8-thread rate; ideal 64-thread scaling would be about 9.5 min.
The M² memory extrapolation to M=1000 is about 13.7 GB. These are planning
estimates, not performance claims.

For the recorded SCNet node, request 32 CPUs, 96 GB, and a 1 h wall limit. The
configured 64 GB block2 stack leaves headroom inside that allocation. The
`dzagnormal` QOS and CPU/GPU binding require
`--gres=gpu:4` for a 32-CPU job, although block2 remains CPU-only and
does not use the allocated GPUs. The job is checkpointed by stage; if it
reaches walltime, submit the same script against the same run directory again.

On 2026-07-28, Slurm `--test-only` estimated 2026-11-17 19:52 for the
32-CPU/4-GPU/1-hour request, versus 2027-02-10 20:29 for the former
64-CPU/8-GPU/2-hour request. The shorter request fits an earlier backfill
window. Ask the cluster administrator for a CPU partition/QOS if a still
earlier start is required.

## Preview and submit through the harness

From the repository root, after probing the queue and ratifying the partition:

```bash
HARNESS_CLUSTER_PROFILE=scnet scripts/harness_slurm.sh precheck
HARNESS_CLUSTER_PROFILE=scnet scripts/harness_slurm.sh probe-partitions

HARNESS_CLUSTER_PROFILE=scnet scripts/harness_slurm.sh submit \
  --test-only \
  --script tracks/qcs/solutions/CCB-LV.999/issue-119-variational/cluster/anderson_block2_preflight.sbatch \
  --partition dzagnormal \
  --time 00:10:00 \
  --cpus 32 \
  --extra '--gres=gpu:4 --mem=96G'
```

After the scheduler preview is accepted, submit the short preflight job with
the same command minus `--test-only`. Only after its log reports
`"status": "ready"` should the production script be submitted:

```bash
HARNESS_CLUSTER_PROFILE=scnet scripts/harness_slurm.sh submit \
  --script tracks/qcs/solutions/CCB-LV.999/issue-119-variational/cluster/anderson_block2.sbatch \
  --partition dzagnormal \
  --time 01:00:00 \
  --cpus 32 \
  --extra '--gres=gpu:4 --mem=96G'
```

The Slurm entrypoint uses the native `.venv` by default. It automatically uses
`$HOME/containers/anderson-block2-py312.sif` when it exists. Set
`APPTAINER_IMAGE` only to override that standard path.

`TARGET_M` defaults to 1000. Direct Slurm users may override it with an exact
member of the configured ladder, for example
`sbatch --export=ALL,TARGET_M=800 .../anderson_block2.sbatch`.

## Evidence and restart

The run directory contains:

- `cluster-job.json` — live allocation, input, sector, target, status, and
  final artifact paths;
- `run.json`, `ordering.json`, `sweeps.csv`, and `result.json`;
- `checkpoints/block2/` — restartable MPS;
- `checkpoint-verification.json` — energy and norm recomputed in a fresh
  block2 driver;
- `convergence.png` and `REPORT.md`.

Rerunning the production script with the same run directory skips completed M
values, reuses the exact saved orbital ordering, and continues from the saved
MPS. A different FCIDUMP, sector, ordering method, or undeclared target M is
rejected before compute.
