---
name: using-jax
description: Use when choosing or setting up JAX as a CPU/GPU backend for NetKet, TensorCircuit-NG, differentiable simulation, or JAX device/setup failures.
---

# JAX

Use JAX as the backend layer for Python simulation stacks such as NetKet and TensorCircuit-NG.

## Sources

- Stack contract: `skills/using-jax/stack.toml`
- QCS interview notes: `docs/qcs/interview.html`
- QCS review notes: `docs/qcs/review.html`
- CPU install target: `make install jax EXTRA=cpu`
- Smoke test: `.venv/bin/python -c 'import jax; print(jax.devices())'`

## Workflow

1. Consult `stack.toml` and choose CPU or GPU before installing downstream packages.
2. For GPU, smoke-test inside the same compute allocation that will run the job.
3. Record JAX devices, platform, Python environment, and CUDA extra/module path.
4. Do not silently fall back to CPU when a GPU run was selected.

## Parameter setup

Use this section as the source for JAX backend knobs used by NetKet, TensorCircuit-NG, or other JAX-based method skills. QCS notes separate backend setup from the physics method: choose the device, dtype, compilation boundary, and timing convention before judging performance.

- Platform: CPU for debug/local preview, single GPU for serious JAX runs, or distributed GPU when the downstream skill declares data/model parallelism.
- Devices: visible devices, process count, memory/preallocation behavior, install extra/module path, target allocation, and whether CPU fallback is forbidden.
- Numeric mode: default single precision for performance; enable double precision for accuracy-sensitive observables, gradients, or paper baselines.
- Compilation: JIT boundary, static argument choices, shape stability, cache policy, and expected first-compile latency.
- Validation: `jax.devices()` output, a backend smoke test in the target environment, and downstream package import.

### Surface to the user — device & JIT boundary

JAX has few knobs; surface these two, built from the user's own situation — don't pick silently.

- **Device.** Ask what they have and how heavy the run is. CPU is fine for debugging and small/local runs; GPU pays off for large vectorized runs (many walkers, big lattices) but needs a compute allocation and an in-allocation smoke test. No GPU → default CPU and say so.
- **JIT boundary.** Usually `jit` the whole compute-heavy function once — fastest steady state, one compile — rather than many small `jit`s (per-call dispatch overhead) or none (slow). Flag the first-compile latency.

> Present these as a short choice in plain language, adapted to their setup (e.g. ask whether they have a GPU), with the trade-off shown — let the user feel it.

## Time estimate

Estimate JAX-backed runs as two separate costs: compile time and steady-state execution time.

- Compile time depends on function shape, static arguments, backend, and dtype; it may dominate tiny reproductions and must not be reported as warm runtime.
- Steady-state time comes from the downstream method skill's cost model after compilation, using the selected device rate.
- GPU estimates require a smoke test inside the compute allocation; login-node device checks are not authoritative.
- If timing is uncertain, a probe should compile and run a tiny representative function once, then report compile and post-compile rates separately. A fair comparison must match task, hardware, gradient method, observable format, and compile/path-search accounting.
