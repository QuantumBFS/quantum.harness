---
name: build-apptainer-image
description: Use when a student needs a reproducible software environment for cluster jobs and must build + validate an Apptainer/Singularity container (.sif) for the harness stack before submitting — covers writing a pinned definition file, building with --fakeroot, validating Julia/Python/GPU inside the image, and proving it on a compute node. Triggers on "build a container", "make a Singularity/Apptainer image", "containerize the stack", "set up a reproducible env for the cluster".
---

# Build Apptainer Image

## Overview

A container gives every student a byte-identical software stack that runs the
same on the login node and every compute node, with no per-job installs. This
skill guides building one `.sif` image and **proving it works on a compute
node** — not just on the login node, where GPU and node-class differences hide.

**Core principle:** a build that succeeds is not a build that works. The image
is validated only when a job *inside it* ran on a compute node and produced
correct output. (Same rule as `/cluster-jobs`: scheduler success ≠ evidence.)

This is a build-and-validate guide; it does not prebuild images for students.

## When to use

- Setting up the summer-school / course software environment on an HPC cluster.
- "Works on my machine" / version-drift across students.
- Compute nodes need a fixed stack (even where they have internet, N× installs are wasteful and non-reproducible).
- Before first submit with the cluster sbatch templates (`skills/using-slurm/profiles/templates/<cluster>/`).

Not for: installing tools on your own laptop (use the `/using-*` / `/setup-julia` skills); jobs that already have a working image (go straight to `/cluster-jobs`).

## Workflow

Drive it one step at a time; preview every heavy or destructive action and confirm before running it.

0. **Probe the cluster before committing to versions.** Two facts you cannot
   guess and must check first:
   - **Registry reachability.** On a mainland-China cluster, Docker Hub
     (`docker.io`) pulls often fail mid-build (`connection reset`). Pull base
     images through a mirror, e.g. `From: docker.m.daocloud.io/library/alpine:3.19`
     instead of `From: alpine:3.19`. (Verified on HKUST-GZ: direct `docker.io`
     resets; the daocloud mirror builds fine.)
   - **GPU driver → max CUDA** (GPU images only). The host driver caps the CUDA
     toolkit you can pin. Run `srun -p debug --gres=gpu:a40:1 -t 1 nvidia-smi`
     (or any GPU partition) and read the "CUDA Version:" — pin a base image CUDA
     ≤ that. Do this **before** the ~30-min build, not after.
1. **Pick the stack and write a pinned definition file.** Pin the base image
   tag, the language version, and the dependency lockfiles. Unpinned = not
   reproducible. Start from the example below and add only what the curriculum
   needs. **Julia Manifest is not chicken-and-egg:** generate it once locally
   (`julia --project -e 'using Pkg; Pkg.resolve()'`) and commit it — that is the
   reproducible path. If you ship only `Project.toml`, `%post`'s `instantiate`
   resolves a *fresh* Manifest at build time (works, but the versions are
   whatever resolves that day). For Python, pin exact versions in a
   `requirements.txt` (GPU wheels are version-sensitive — see the GPU section).
2. **Choose where to build.** Set scratch explicitly — `$SCRATCH` is **not**
   guaranteed to be defined on every cluster (HKUST-GZ uses `~/scratch`); an
   unset `$SCRATCH` silently writes to `/`. Use `export SCRATCH=$HOME/scratch`
   then `APPTAINER_TMPDIR=$SCRATCH/atmp`. A CUDA+Python+Julia image is **~8–15 GB**
   — on a near-full `$HOME` (HKUST-GZ home is ~97% full) it will not fit, so
   store the `.sif` on scratch by default; `$HOME/containers/` only for a small
   CPU-only image.
3. **Build with `--fakeroot`** (no root on a cluster):
   `module load apptainer-1.4.5 && apptainer build --fakeroot $SCRATCH/containers/qmb.sif qmb.def`.
   `--fakeroot` works even with no `/etc/subuid` entry when unprivileged user
   namespaces are enabled — Apptainer falls back to a root-mapped namespace
   (verified working on HKUST-GZ). If you instead get "user namespace" errors,
   build the `.sif` where you have root (or a CI builder) and copy it over.
   A full CUDA+Julia+conda build can exceed login-node limits — if killed, build
   inside an allocation on the **CPU workhorse partition** (long wall), e.g.
   `salloc -p i64m512u -t 02:00:00 -c 8 --mem=16G`; do **not** use `debug` (its
   30-min cap is too short for a full build). (`apptainer` and the
   `singularity-ce` module are command-compatible; this guide uses `apptainer-1.4.5`.)
4. **Validate inside the image** (versions + a real import + a tiny compute):
   ```bash
   apptainer exec qmb.sif julia --project=/opt/project -e \
     'using Pkg; Pkg.status(); using ITensors; @show ITensors.version()'
   apptainer exec qmb.sif python -c 'import sys; print(sys.version)'   # if Python in image
   ```
5. **GPU validation — on a GPU compute node, never the login node.** Submit a
   short job and confirm the device is visible. Fastest path is the `debug`
   partition, but **`debug` GPUs are A40**, while the `gpu.sbatch` template
   defaults to A800 — so for a debug validation run, change both flags to
   `--partition=debug --gres=gpu:a40:1` (without an explicit `--gres` you may
   land on a CPU-only debug node and the check silently runs without a GPU).
   First confirm the host driver supports your image's CUDA, then that the
   device is visible to each framework:
   ```bash
   apptainer exec --nv qmb.sif nvidia-smi          # "CUDA Version:" here must be >= the image's CUDA toolkit
   apptainer exec --nv qmb.sif python -c 'import jax; print(jax.devices())'   # expect [cuda:0, ...]
   apptainer exec --nv qmb.sif julia --project=/opt/project -e 'using CUDA; @show CUDA.functional()'
   ```
   (CUDA.jl ships its own toolkit via artifacts, so Julia GPU works once `--nv`
   injects the host driver — the base image's CUDA toolkit is only needed by the
   Python/JAX side.)
6. **Register the image path** so the templates find it: `export QMB_IMAGE=...`
   (add to `~/.bashrc`), or edit `IMAGE=` in the cluster sbatch templates.
7. **Prove it end-to-end.** Submit a trivial script through the CPU template via
   `/cluster-jobs`, fetch the output, confirm it ran *in the container on a
   compute node*. Only now is the image validated.

## Example definition file (Julia + ITensors, CPU)

```
Bootstrap: docker
From: julia:1.10.9-bookworm        # PIN the tag — never :latest

%files
    Project.toml /opt/project/Project.toml
    Manifest.toml /opt/project/Manifest.toml   # commit this lockfile for reproducibility

%post
    export JULIA_DEPOT_PATH=/opt/julia
    # Generic CPU target so the image runs on every node class (i64/a128/i96).
    # Without this, precompiled code can hit "illegal instruction" on a
    # different microarchitecture than the build host.
    export JULIA_CPU_TARGET="generic;sandybridge,clone_all;skylake-avx512,clone_all"
    julia --project=/opt/project -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

%environment
    export JULIA_DEPOT_PATH=/opt/julia
    export JULIA_CPU_TARGET="generic;sandybridge,clone_all;skylake-avx512,clone_all"

%runscript
    exec julia --project=/opt/project "$@"
```

## Combined Julia + Python + CUDA (GPU)

The GPU case is more involved: the base is a CUDA image (not a Julia image), so
you install Julia yourself and add a pinned Python layer.

```
Bootstrap: docker
From: docker.m.daocloud.io/nvidia/cuda:12.4.0-cudnn-runtime-ubuntu22.04   # mirror (step 0); PIN; CUDA <= GPU-node driver

%files
    Project.toml     /opt/project/Project.toml
    Manifest.toml    /opt/project/Manifest.toml       # generated + committed locally (step 1)
    requirements.txt /opt/project/requirements.txt    # exact pins, see caveat below

%post
    set -eux
    export DEBIAN_FRONTEND=noninteractive
    apt-get update && apt-get install -y --no-install-recommends wget ca-certificates git && rm -rf /var/lib/apt/lists/*
    # Julia: install the same version as the cluster module (here 1.10.9) from the official tarball
    wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.10/julia-1.10.9-linux-x86_64.tar.gz -O /tmp/j.tgz
    tar -xzf /tmp/j.tgz -C /opt && ln -s /opt/julia-1.10.9/bin/julia /usr/local/bin/julia && rm /tmp/j.tgz
    export JULIA_DEPOT_PATH=/opt/julia
    export JULIA_CPU_TARGET="generic;sandybridge,clone_all;skylake-avx512,clone_all"
    julia --project=/opt/project -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
    # Python via miniconda (pinned installer), then pinned wheels
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-py311_24.5.0-0-Linux-x86_64.sh -O /tmp/mc.sh
    bash /tmp/mc.sh -b -p /opt/conda && rm /tmp/mc.sh
    /opt/conda/bin/pip install --no-cache-dir -r /opt/project/requirements.txt

%environment
    export JULIA_DEPOT_PATH=/opt/julia
    export JULIA_CPU_TARGET="generic;sandybridge,clone_all;skylake-avx512,clone_all"
    export PATH=/opt/conda/bin:/opt/julia-1.10.9/bin:$PATH
```

**Version caveat (this is the hard part):** the `jax[cuda12]` wheel must match
both the base image's CUDA and the GPU-node driver, and `netket` must match
`jax`. Pin exact versions in `requirements.txt`, e.g.
`jax[cuda12]==0.4.<x>` + `netket==3.<y>`, and **verify the trio works at build
time and on a GPU node (step 5)** — do not assume a given combination is
compatible. Check the GPU-node driver's supported CUDA with `nvidia-smi` first
(step 5); the image CUDA must be ≤ that.

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| `From: docker.io/...` on a China cluster | build dies "connection reset" mid-pull | pull via a mirror, e.g. `docker.m.daocloud.io/library/...` |
| Pin CUDA tag without checking the driver | image's CUDA > host driver → no GPU on the node | `srun nvidia-smi` first (step 0); image CUDA ≤ driver's |
| Build on login node, default tmpdir | OOM / "no space left" | `APPTAINER_TMPDIR=$SCRATCH/atmp`; build in `salloc -p i64m512u` if killed |
| No `--fakeroot` | "permission denied" / needs root | always `apptainer build --fakeroot` |
| Unpinned base / deps (`:latest`, no Manifest) | image differs per student | pin tag + commit `Manifest.toml` / version-locked pip |
| No `JULIA_CPU_TARGET` | "illegal instruction" on some nodes | set a multi-target generic value (example above) |
| Validate GPU on login node | "no CUDA device" or false pass | validate `--nv` inside an sbatch job on a GPU node |
| Image in tight `$HOME` | quota errors mid-build | build/store on scratch; check `du -sh` and quota |
| Forget `--bind`/`--pwd` | results vanish / wrong cwd | run with `--bind "$PWD" --pwd "$PWD"` (templates do this) |
| "It built, so it works" | breaks at submit time | not validated until a job ran in it on a compute node |

## Composition

- `/setup-cluster` provides the cluster profile + module names this skill uses.
- `/cluster-jobs` submits the validated image via the cluster sbatch templates.
- The per-cluster templates live in `skills/using-slurm/profiles/templates/<cluster>/{cpu,gpu}.sbatch`.
