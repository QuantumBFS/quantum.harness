# Issue #28 Multi-Cluster Environment Design

## Status and scope

- Date: 2026-07-29
- Branch retained: `challenge/issue28-pure-neural`
- Scope: prepare Huabei and Huazhong environments for later direct Stage 6
  submissions.
- Approved deployment: one hash-pinned Python base SIF plus one frozen Python
  environment per supported device class.
- Non-goals: no Stage 6 science run, no L=45 production, no second RG, no Tc
  evidence, no commit, and no push.

This design does not change the physical model or scientific protocol. It only
establishes reproducible runtime capabilities and proves them on compute nodes.

## Confirmed capabilities

| Site | SSH/profile | Supported Hard Goal capability | Explicitly unsupported |
|---|---|---|---|
| Shandong | `qdeshell` | Existing A800 CUDA/JAX reference | None within the validated reference scope |
| Huabei | `xh5-huabei` | RTX 3090 CUDA/JAX | CPU fallback for GPU-labelled jobs |
| Huazhong | `scnet` | CPU/JAX | Hygon DCU/JAX unless a separate vendor-supported route is later proven |

The persistent active profile remains `qdeshell`. Multi-cluster commands must
set `HARNESS_CLUSTER_PROFILE` explicitly so a job cannot drift to another
site.

## Immutable reference anchors

The common base is the already measured Shandong artifact:

- Python base image: `python:3.12.11-slim-bookworm`
- SIF path: `~/scratch/containers/python-3.12.11-slim-bookworm.sif`
- SIF size: 44,380,160 bytes
- SIF SHA-256:
  `59ebde5239057c558b86ef30ae12f6ffc7a8280e3244120f2dfd6397fa578b6c`
- GPU requirements SHA-256:
  `614dac1c70184b8ddb4a7e9dc50ebd2d6b4399a5a038c43bced5de81b04266f3`
- Shandong GPU freeze SHA-256:
  `61f20c075caf592265e925aa297e7bb23bc1768d625a5781d479d139defcebca`

The GPU package contract remains:

- `numpy==2.4.6`
- `scipy==1.18.0`
- `pytest==9.1.1`
- `numba==0.66.0`
- `jax[cuda12]==0.11.0`

The Huazhong CPU package contract is explicit:

- `numpy==2.4.6`
- `scipy==1.18.0`
- `pytest==9.1.1`
- `numba==0.66.0`
- `jax==0.11.0`
- `jaxlib==0.11.0`

It excludes every CUDA plugin and NVIDIA runtime wheel. Its complete resolved
freeze and SHA-256 are generated once during bootstrap, checked against these
six direct requirements, then bound into the environment manifest before the
CPU smoke is submitted. Huabei must reproduce the complete Shandong GPU freeze,
not merely re-resolve the five direct GPU requirements.

## Remote layout

Both sites use the same stable layout:

```text
~/scratch/containers/python-3.12.11-slim-bookworm.sif
~/scratch/hg3d-venv-gpu-v1/          # Huabei only
~/scratch/hg3d-venv-gpu-v1.freeze.txt
~/scratch/hg3d-venv-cpu-v1/          # Huazhong only
~/scratch/hg3d-venv-cpu-v1.freeze.txt
~/quantum.harness/tracks/mps/DMRG/    # reviewed immutable shipment
~/quantum.harness/results/hard_goal/  # environment smoke artifacts
```

Huabei has a 25 GiB home filesystem. The base SIF, one GPU venv, one source
snapshot, checkpoints, and smoke artifacts must remain below 20 GiB, leaving
at least 5 GiB free. Package caches are disabled or removed after a successful
install. Huazhong also uses `~/scratch` for path consistency even though its
home filesystem is much larger.

## Site-specific runtime

### Huabei CUDA/JAX

- Profile: `xh5-huabei`
- Partition: `xhhgnormal01`
- GPU request: `gpu:NVIDIAGeForceRTX3090:1`
- Runtime: `singularity/3.8.7`
- Container flag: `singularity exec --nv`
- Required JAX platform: `gpu`
- Required numeric mode: x64 enabled
- Preallocation: disabled for the smoke and pilot launchers
- CPU fallback: fatal

The existing A800 wrapper cannot be copied unchanged because it hard-loads and
invokes Apptainer 1.2.4. The shared launcher must receive an explicit runtime
command and must support the equivalent Singularity flags without changing the
scientific entrypoint.

### Huazhong CPU/JAX

- Profile: `scnet`
- Partition: `hx1hdnormal01`
- Runtime: `apptainer/1.3.4`
- Container flag: `apptainer exec`
- Required JAX platform: `cpu`
- Required numeric mode: x64 enabled
- DCU visibility: ignored and never reported as a JAX device
- GPU or DCU claim: fatal unless a separate approved environment contract is
  introduced

DTK modules expose ROCm/HIP-derived interfaces, but no vendor-supported JAX
wheel or PJRT plugin was found. Environment variables such as `ROCM_PATH` and
`HIP_PATH` are not evidence of JAX compatibility. This environment therefore
uses CPU JAX deliberately rather than silently falling back from a failed DCU
initialization.

## Shipment contract

The local worktree is dirty. Broad repository rsync is prohibited. Each site
receives only an immutable package containing:

1. the common SIF and its SHA-256 sidecar;
2. the site requirements file and expected SHA-256;
3. the environment bootstrap and smoke scripts;
4. the exact smoke run specification;
5. the source/config files imported by the smoke;
6. a sorted source inventory mapping relative paths to SHA-256 values.

The remote bootstrap verifies every shipped hash before creating a venv. A
source change requires a new package id and new result directory; it never
mutates evidence from a prior package.

## Launcher contract

The launcher accepts explicit values for:

- container runtime (`apptainer` or `singularity`);
- SIF path and expected SHA-256;
- venv path and expected freeze SHA-256;
- required JAX platform (`gpu` or `cpu`);
- run spec, selector, output path, and source inventory.

It fails before Python when any file, hash, runtime, module, platform, or
selector is missing. Inside Python it fails when:

- JAX reports a platform different from the declared platform;
- a Huabei GPU job reports no CUDA device;
- x64 is disabled;
- any version differs from the environment manifest;
- a JIT result differs from its NumPy reference beyond the declared tolerance;
- checkpoint output cannot be atomically written and re-read.

No launcher performs package installation during a science job.

## Build and install flow

1. Re-probe the selected partition and run the exact request through
   `sbatch --test-only`.
2. Create the stable remote directories and verify available capacity.
3. Transfer the 44.4 MB reference SIF and hash-check it remotely.
4. Transfer only the immutable environment package.
5. Create the site venv with the SIF's Python. Huabei installs the complete
   Shandong GPU freeze; Huazhong installs the six exact CPU requirements and
   rejects any resolved CUDA or NVIDIA distribution. All installs use
   `--no-cache-dir`.
6. Run `pip check`, record `pip freeze --all`, compare it with the declared
   direct requirements and, for Huabei, the reference freeze, then hash the
   freeze and write the immutable environment manifest.
7. Validate imports and versions inside the container on the login node. This
   is setup evidence only, not compute-node evidence.
8. Submit one short compute-node smoke per site.
9. Fetch results and independently verify the terminal manifest and every
   artifact hash.

## Compute-node smokes

### Huabei smoke

- One RTX 3090, 8 CPUs, 16 GiB, 15 minutes, one array cell.
- Record host, GPU model, driver, reported CUDA compatibility, Python, JAX,
  jaxlib, device list, x64 status, SIF/freeze/source hashes, compile time, and
  warm runtime.
- Run a shape-stable x64 JIT kernel and the small paired parallel-tempering
  backend with all exchange edges exercised.
- Require `default_backend == "gpu"` and exactly the allocated visible GPU
  set. Any CPU fallback fails the smoke.

### Huazhong smoke

- CPU-only request, 8 CPUs, 16 GiB, 15 minutes, one array cell.
- Record host, CPU model, Python, JAX, jaxlib, device list, x64 status,
  SIF/freeze/source hashes, compile time, and warm runtime.
- Run the same shape-stable x64 JIT reference and a reduced paired
  parallel-tempering backend.
- Require `default_backend == "cpu"`. The manifest states that no DCU/JAX
  validation was attempted.

## Evidence and readiness markers

Results are isolated by site:

```text
results/hard_goal/env-huabei-gpu-v1/
results/hard_goal/env-huazhong-cpu-v1/
```

Each contains an immutable launch record, resource preview, scheduler record,
terminal manifest, stdout/stderr, environment freeze, and artifact hashes.
An environment is marked `DIRECT_SUBMIT_READY` only when:

1. the scheduler job completed with exit `0:0`;
2. the fetched terminal manifest says `status=complete`;
3. all artifact and source hashes match;
4. the declared JAX platform and x64 checks pass;
5. the tiny JIT and paired-PT checks pass;
6. no CPU fallback or unsupported accelerator claim occurred;
7. the stable runtime paths still resolve to the verified SIF and venv.

The marker is environment evidence only. It is not Stage 6 equilibration,
scientific evidence, production authorization, or Tc evidence.

## Failure and recovery

- Driver incompatible with CUDA wheels: preserve the failed manifest, create a
  new GPU requirements version compatible with the measured driver, and repeat
  only the Huabei environment smoke.
- Singularity cannot execute the reference SIF: preserve the failure and build
  a new pinned Singularity-compatible SIF; never rewrite the reference hash.
- Venv install exceeds Huabei capacity: stop before removing evidence, report
  the measured size, and switch to a self-contained minimized SIF only through
  a new reviewed design revision.
- Huazhong CPU JAX import fails: use the exact supported CPU wheel set for
  Python 3.12.11 and issue a new CPU environment version.
- Queue delay: leave the validated request queued or change partition only
  after a new resource preview; scheduler state alone does not change the
  environment verdict.

## Handoff after readiness

Future Stage 6 jobs select a site explicitly:

```text
HARNESS_CLUSTER_PROFILE=xh5-huabei  # CUDA/JAX cells
HARNESS_CLUSTER_PROFILE=scnet       # CPU/JAX cells
HARNESS_CLUSTER_PROFILE=qdeshell    # A800 reference and existing jobs
```

A temperature ladder remains within one Slurm cell and one site. Independent
disorder samples and seeds may be distributed across sites only when their
environment manifests are `DIRECT_SUBMIT_READY` and the scientific run spec
binds the selected environment manifest SHA-256.
