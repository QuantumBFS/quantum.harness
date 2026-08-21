# L=32 runtime profile

Locked cell: `sigma=1.75`, `Gamma=1.560`, `K=24`, `alpha=0.5`,
`r_fit=2048`, and `chi_max=128`.

| Phase | Wall time | Sweeps | Maximum MPS chi |
|---|---:|---:|---:|
| MPO/model setup | 1.37 s | - | - |
| Even-sector ground calculation | 193.26 s | 14 | 128 |
| Full C(r), S(0), S(k_min), xi, R_xi | 4.67 s | - | 128 |
| Odd-sector excitation calculation | 200.63 s | 15 | 128 |

The state-calculation rows time the current `_run_sector` wrapper, which
includes TeNPy's DMRG call and the final variance contraction. TeNPy's sweep
statistics report 196.38 s for the even state and 204.01 s for the odd state;
their internal clock is not directly subtractable from the wrapper's
`perf_counter` measurement.

## Tensor structure

- Site conservation: `conserve="parity"`.
- Charge information: one Z2 charge with modulus 2 and two physical charge
  blocks.
- MPO tensors are charge-aware TeNPy arrays with total charge zero.
- Actual MPO bond dimensions:
  `[2, 50, ..., 50, 2]`; the maximum bulk dimension is 50.
- No MPO compression routine is called.
- Three of the 24 fitted coefficients are exactly zero. Removing only those
  dead direct/wrapped channel pairs would reduce the exact graph from
  `2K+2=50` to 44 without changing any Hamiltonian coefficient.

## Measured diagnostics

- Even variance: `1.4906618162058294e-9`.
- Even maximum discarded weight: `8.20702739217239e-11`.
- Odd variance: `1.6671037883497775e-9`.
- Odd maximum discarded weight: `5.103194004095448e-10`.
- Gap: `0.15309921006374339`.

## Optimization candidates

1. Prune exactly zero exponential coefficients before constructing the graph.
   This is algebraically exact and should be validated by dense-MPO and
   coefficient-reconstruction tests before production.
2. Warm-start neighboring Gamma cells from a checkpointed MPS in the same
   parity sector. Keep the Gamma grid fixed and run a reverse-direction
   bracket check to detect continuation bias.
3. Checkpoint converged even and odd MPS states so variance, correlations, and
   higher-chi refinement do not repeat lower-chi sweeps.
4. Compute only independent distances `0...L/2` and mirror them. The current
   full periodic loop evaluates the same unordered pair products again at
   `L-r`; this can nearly halve correlation work while preserving full C(r).
5. Benchmark a staged chi schedule against the current immediate `chi=128`
   run. Both profiled states reached chi 128 from the first recorded sweep, so
   cheap low-chi preconditioning may reduce early-sweep cost.
6. Do not apply approximate numerical MPO compression before a dedicated
   Hamiltonian- and observable-level K/compression validation. TeNPy does not
   currently receive an MPO-compression request in this workflow.
