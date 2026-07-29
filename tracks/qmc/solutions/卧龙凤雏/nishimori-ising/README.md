# Nishimori central-charge verification

This solution verifies the ordinary quenched central charge
`c_eff ≈ 0.464` of the square-lattice ±J Ising model at the fixed
Nishimori point

- antiferromagnetic-bond probability `p = 0.1092212`;
- `K_N = 0.5 log((1-p)/p) = 1.0493604763025683`;
- cylinder circumferences `L = 4, 6, 8, 10, 12, 14`.

It deliberately does not target the higher-replica/Born-rule value near
`0.522`.

## Numerical method

Rust generates all quenched disorder with `rand_xoshiro = 0.8.1`
(`Xoshiro256++`). Each replica produces one maximum-width bond row, and every
smaller width consumes a prefix of that row. This common-disorder coupling
reduces noise in the finite-size slope.

For every row, the thermal spin sum is exact:

```text
v_(r+1)(s') = exp[K Σ_i τh_i s'_i s'_(i+1)]
              Σ_s exp[K Σ_i τv_i s_i s'_i] v_r(s)
```

The matrix-free application costs `O(L 2^L)`. L1 normalization after each row
accumulates the quenched Lyapunov free energy
`φ_L = E[ln Z]/(M L)`. Python only loads data, bootstraps joint-width vectors,
fits

```text
φ_L = φ_∞ + π c_eff/(6 L²) + a/L⁴,
```

and creates the CSV/JSON results, six plots, and offline HTML report.

## Reproduce

```bash
make setup
make test
make run
```

`make run-test` executes the same artifact pipeline with a tiny non-production
configuration. Production replica files are atomic and resumable; rerunning
with the same explicit run directory validates and reuses completed replicas.

Generated artifacts live under `tracks/qmc/results/`, outside the submitted
solution source. Each run includes:

- `raw/oracles.json` and `raw/replicas/replica-*.json`;
- `processed/summary.json`, `gates.json`, and two CSV data files;
- six PNG figures;
- `manifest.json` with seeds, versions, commands, timings, and SHA-256 hashes;
- a self-contained `report.html`.
