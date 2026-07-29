# Route D+ implementation

This directory implements the physics-first Route D+ workflow for Challenge
#15. The implementation is deliberately phase-gated:

1. establish a Python 3.11/JAX `complex128` environment and record a manifest;
2. implement and certify the one-particle LLL layer;
3. add projected tensor algebra and analytic `L=0`/`L=2` mothers;
4. add scalar generators, the shared operator network, and VMC/SR;
5. reveal ED only after the oracle-free checkpoint is frozen.

No later phase may claim a certificate until every gate in the preceding phase
has passed in the target compute allocation.

## Current status

Only the Phase 1 environment contract has been added. It is intended to run on
a remote compute allocation, not on the local WSL2 checkout:

- `environment/phase1.toml` freezes the physical and numeric conventions;
- `environment/requirements.in` declares non-JAX Python dependencies;
- `environment/bootstrap.sh` selects exactly one JAX CPU/CUDA profile;
- `environment/capture_manifest.py` enforces Python 3.11, JAX x64, and the
  requested device before writing a manifest;
- `environment/manifest.schema.json` defines the recorded evidence;
- `environment/phase1.sbatch` is a profile-neutral Slurm entry point.

The generated virtual environment, dependency lock, and manifest are runtime
artifacts. They must remain outside Git under `tracks/qmc/results/`.

## Execution boundary

Do not run `bootstrap.sh`, the sbatch entry point, tests, training, or ED on the
local development host. Before a remote run:

1. select an active cluster profile;
2. probe and ratify a GPU partition;
3. ship a committed source revision;
4. execute the JAX device smoke inside the allocation;
5. read back and validate the manifest before starting Phase 2.

