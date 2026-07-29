# Route D+ Phase 1: environment and convention gate

Date: 2026-07-29

## Fixed physics setup

The implementation follows Challenge #15 and the final Route D+ physics
workflow:

- `N=6`, `2Q=15` for the first benchmark, with `2Q=3(N-1)`;
- fully spin-polarized fermions strictly restricted to the lowest Landau level
  on the Haldane sphere;
- pair-only chord Coulomb estimator
  `sum_{i<j} 1/(2*sqrt(Q)*abs(u_i*v_j-u_j*v_i))`;
- energies in `e^2/(epsilon*l_B)`;
- a shared variational family for the `L=0` ground tower and all five
  components of the `L=2` tower;
- primary observable `Delta_2(N)=E_2(N)-E_0(N)`.

The background term is omitted because it is the same constant for states at
the same `N,2Q` and therefore cancels in the gap.

## Local audit

The development host is Linux x86-64 under WSL2 and has sufficient disk space,
Git, GitHub CLI, and authenticated fork access. It does not have:

- a `python3.11` executable;
- an NVIDIA device visible through `nvidia-smi`;
- an `nvcc` CUDA compiler;
- an active repository cluster profile.

Consequently the local host does not pass Phase 1. No repository code, test,
JAX import, training job, or ED job was executed during this audit.

## Remote gate

Phase 1 is complete only after a remote compute allocation produces
`environment-manifest.json` and all of the following are true:

1. Python is exactly 3.11.x.
2. JAX x64 is enabled.
3. The requested GPU platform is present; CPU fallback is rejected.
4. The source checkout is a clean 40-character Git commit.
5. The exact dependency lock exists and its SHA-256 digest is recorded.
6. The manifest validates against `manifest.schema.json`.

The private active cluster profile now targets `hpccube-xh5`, with remote
project root `/work/home/jiabohan5/quantum.harness-collab`. The default GPU
partition is `xhhgnormal` with one RTX 3080, one node, and conservative
Phase 1 resources. The profile is intentionally excluded from Git because it
contains user-specific cluster paths.

The login environment has no default Python 3 interpreter. Python 3.11 and the
locked environment must therefore be installed under the remote project or
user directory before submission. Phase 2 remains blocked until the Slurm
compute allocation produces and validates the manifest.

The cluster uses glibc 2.17 and its visible CUDA package set ends at cuDNN
9.5. The compatible binary stack is therefore pinned to JAX/JAXLIB/CUDA plugin
0.4.38, NumPy 2.0.2, `ml_dtypes` 0.5.1, and Optax 0.2.4. A pip
`--only-binary=:all:` dry-run resolved the full CUDA 12 dependency graph before
installation. SciPy is pinned to the compatible 1.16.3 wheel. The sole source
dependency, `pywigxjpf==1.13.3`, is installed in a separate transaction only
after the binary environment is complete. Its declared `cffi` build/runtime
dependency is fixed at 2.0.0 in the binary requirements.

For the bandwidth-limited login node, the same requirements may be staged as a
target-specific wheelhouse. `ROUTE_D_PLUS_WHEELHOUSE` switches bootstrap to
`--no-index --find-links`, so installation cannot silently consult a different
package source. The wheelhouse itself is a runtime artifact and is not tracked.
