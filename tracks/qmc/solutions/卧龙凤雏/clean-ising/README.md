# Clean Ising central-charge verification

This benchmark verifies the clean-Ising warm-up in challenge #122 by two
independent routes: a deterministic transfer matrix and Wolff Monte Carlo
thermodynamic integration. Rust performs every numerical simulation; Python
only validates records, integrates, fits, bootstraps, plots, and renders the
report.

## Physical convention

The simulated model is the ferromagnetic square-lattice Ising model

```text
H = -Σ_<ij> s_i s_j,    s_i ∈ {-1,+1},
Z(K) = Σ_s exp[-K H(s)].
```

Both directions are periodic on an `L×M` torus with `M=8L`. The critical
coupling is `K_c = 0.5 ln(1+sqrt(2)) = 0.44068679350977147`. Production widths
are `L = 4, 6, 8, 10, 12, 16`.

The transfer matrix gives `g(L)=-ln λ₀`. Monte Carlo integrates the measured
total Hamiltonian from the exact infinite-temperature anchor,

```text
F(K_c) = -N ln 2 + ∫_0^Kc <H>_K dK,    g(L)=F/M.
```

Both routes fit the fixed Casimir form

```text
g(L)/L = f_infinity - π c/(6 L²) + a/L⁴.
```

`L_min=6` is primary; `L_min=4` and `8` are diagnostics.

## Reproduction

```bash
make setup
make test
make run
```

The Monte Carlo generator is
`rand_xoshiro::Xoshiro256PlusPlus` from `rand_xoshiro=0.8.1`. Each chain seed
is the stable SplitMix-style derivation of
`(base_seed, L, K_index, replica)` implemented in `src/rng.rs` and recorded in
the manifest.

The production run uses nine even widths from `L=4` through `L=20`, 129 nested
coupling points, four replicas, 200 burn-in
sweeps, 12,800 measurement sweeps, and 320-sweep blocks. Burn-in first calibrates
an integer number of cluster updates per lattice volume; that count is then
frozen before measurements, avoiding state-dependent stopping-time bias.

## Data contracts

- `raw/exact.jsonl`: one transfer record per width, including `λ₀`, `g(L)`,
  convergence change, residual, and timing.
- `raw/mc_blocks.jsonl`: one record per
  `(L,K_index,replica,block_index)`, including seed, frozen cluster-update
  count, energy sums, and cluster diagnostics.
- `manifest.json`: full configuration, commands, dependency hashes, versions,
  threads, seeds, and stage timings.
- `processed/free_energies.csv`: exact and 65/129-point integrated free energies.
- `processed/central_charge_fits.csv`: all methods and predeclared fit windows.
- `processed/energy_vs_k.csv` and `diagnostics.csv`: integration and chain
  diagnostics.

Generated raw data, processed tables, figures, and the self-contained
`report.html` stay under `tracks/qmc/results/<run-id>/` and are not committed.

## Success gates

- exact `|c-0.5| ≤ 0.005`;
- Monte Carlo `|c-0.5| ≤ 0.03`, with its 95% interval containing `0.5`;
- 65/129-point shift below the 129-point bootstrap standard error;
- declared fit-window, half-chain, and replica checks pass;
- total local runtime below 600 seconds.

The principal limitations are the finite aspect ratio `M/L=8`, Simpson-grid
discretization, finite-size correction ansatz, and statistics deliberately
limited to a ten-minute local budget.
