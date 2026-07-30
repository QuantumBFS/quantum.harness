# Route D+ Phase 6 job 23019458

## Outcome

Slurm job `23019458` did not enter any D+0 training seed. Ruff passed and all
58 scoped tests passed, but the certificate process aborted while
`jax.devices()` initialized the GPU because its job environment omitted the
already certified CUDA-wheel and compatibility-library `LD_LIBRARY_PATH`.
No checkpoint or Phase 6 certificate was produced, and no ED module ran.

## Identity and resources

- Source revision: `70e0d7d9bb80f86528c405a29ea1e64e8d680b7e`
- Run ID: `route-d-plus-phase6-20260730-01`
- Cluster and partition: `xhcs3`, `xhhgnormal`
- Node and accelerator: `e01r04`, one RTX 3080
- Allocation: four CPUs, 12 GiB memory
- Slurm state and exit code: `FAILED`, `6:0`
- Runtime: 78 seconds

## Successful pre-training gates

```text
All checks passed!
..........................................................               [100%]
58 passed in 39.80s
```

## Failure

```text
Unable to load any of {libcudnn_graph.so.9.5.0, libcudnn_graph.so.9.5,
libcudnn_graph.so.9, libcudnn_graph.so}
Invalid handle. Cannot load symbol cudnnCreate
```

The failure matches the loader condition previously diagnosed and corrected
in Phase 1. The Phase 1 passing job prepended the pinned compatibility
directory and all installed CUDA 12 wheel `lib` directories to
`LD_LIBRARY_PATH`; the initial Phase 6 script did not carry that runtime
contract forward.

## Correction

The Phase 6 entry point now:

1. verifies the pinned compatibility `libstdc++.so.6.0.29` SHA-256;
2. prepends the compatibility directory and nine CUDA wheel library
   directories to `LD_LIBRARY_PATH`;
3. exports `JAX_ENABLE_X64=true`;
4. makes the certificate assert both a GPU platform and x64 mode.

## Pinned log hashes

```text
87750d158229f23908a3ae096ca8596625b348b6d01b28ea7e26d44f79a2953d  slurm-23019458.out
b9dac83b80cc95a5cd809ae95a46b4d10eaf86df6debfb5421463d0ff064d187  slurm-23019458.err
```

This job is failure evidence only. It cannot support any training, energy,
gap, checkpoint, or Phase 6 completion claim.
