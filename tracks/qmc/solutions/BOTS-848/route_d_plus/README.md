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

The Phase 1 environment gate has passed on a remote RTX 3090 allocation. Its
contract consists of:

- `environment/phase1.toml` freezes the physical and numeric conventions;
- `environment/requirements.in` declares wheel-only Python dependencies;
- `environment/requirements-source.in` pins the isolated source dependency;
- `environment/bootstrap.sh` selects exactly one JAX CPU/CUDA profile;
- `environment/capture_manifest.py` enforces Python 3.11, JAX x64, and the
  requested device before writing a manifest;
- `environment/manifest.schema.json` defines the recorded evidence;
- `environment/phase1.sbatch` is a profile-neutral Slurm entry point.

Phase 2 adds the one-particle LLL layer:

- `lll.py` implements the fixed spinor gauge, normalized monopole orbitals,
  the closed reproducing kernel, sphere quadrature, and LLL reconstruction;
- `phase2.schema.json` defines the machine-readable one-particle certificate;
- `certify_phase2.py` measures spinor, overlap, kernel-sum, and off-grid
  reconstruction errors against the fixed `1e-12` gate;
- `phase2.sbatch` runs the certificate in the pinned remote environment.

Phase 3 adds projected one-particle tensor algebra:

- `tensor.py` constructs Hilbert--Schmidt-normalized canonical unit tensors,
  spin-representation rotations, the continuous-coordinate one-body kernel,
  and a quadrature-calibrated generic one-body action;
- `phase3.schema.json` defines the tensor-algebra certificate;
- `certify_phase3.py` measures orthonormality, spherical Hermiticity, finite
  rotation covariance, quadrature reconstruction, kernel equality, and
  one-body action error;
- `phase3.sbatch` runs the Phase 3 gate only after a Phase 2 certificate is
  supplied.

Phase 4 adds the analytic many-body mothers:

- `mother.py` evaluates the Laughlin state without regularizing nodes and
  applies the rank-two projected density through the calibrated quadrature
  proof backend to produce all five `Phi_(2M)` components;
- `phase4.schema.json` defines the analytic-mother certificate;
- `certify_phase4.py` checks mother exchange, degree, and SU(2) invariance,
  tower non-vanishing, exchange and degree, rank-two ladder identities,
  finite rotations, and equal component norms;
- `phase4.sbatch` runs the Phase 4 gate only after a Phase 3 certificate is
  supplied.

Phase 5 adds normal-ordered scalar dressing:

- `scalar.py` implements the density-product proof backend, the direct
  normal-ordered pair backend, coupled-pair channel extraction, and covariance
  whitening;
- `phase5.schema.json` defines the scalar-generator certificate;
- `certify_phase5.py` verifies LLL closure, Hermiticity, scalarity, backend
  agreement, coupled-channel degeneracy, and mother/tower centering and
  whitening in the first nontrivial `N=4`, `2Q=9` certification space,
  retaining two directions after the prescribed algebraic redundancy cutoff;
- `phase5.sbatch` runs the Phase 5 gate only after a Phase 4 certificate is
  supplied.

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
