# Local research report — 2026-07-28

## Result

For the pinned four-impurity Anderson FCIDUMP, corrected multi-start GA
ordering with block2 DMRG reached a saved-MPS expectation

**E(M=1500) = −62.260053669390740 Eₕ.**

The checkpoint was reloaded in a fresh `DMRGDriver`; its norm was
0.9999999999999981 and the independently recomputed normalized expectation
differed from the recorded headline by only 7.1×10⁻¹⁵ Eₕ. This is
3.371840993698 mEₕ below the verified SKQD value −62.25668182839704 Eₕ.

## Confirmed calculation

| Setting | Value |
|---|---|
| Hamiltonian | Tracker Anderson FCIDUMP at commit `e2a2488ceb53344668ac1447f7f96b18703f3524` |
| Input SHA-256 | `9c8ceb3faa39ccb9cf2c15632cdc748e449cf26197ee1e8251092a6bb49ce4b6` |
| Sector | 32 spatial orbitals, 32 electrons, `MS2=0`, SU(2) spin 0 |
| Solver | block2 0.5.3 quantum-chemistry DMRG |
| Ordering | corrected 64-start block2 GA; selected seed 1255 |
| GA cost | 3.6743608609575804 |
| Bond dimensions | 100 → 200 → 400 → 600 → 800 → 1000 → 1500 |
| Sweeps | 8 per M; noise 10⁻⁴ for six sweeps, then zero |
| Davidson thresholds | 10⁻⁶ for six sweeps, then 10⁻⁹ |
| Threads / seed | 8 / 1234 |

## Finite-M production ladder

| M | Saved-MPS E (Eₕ) | E−SKQD (mEₕ) | Discarded weight | Wall | RSS |
|---:|---:|---:|---:|---:|---:|
| 100 | −62.253929578507346 | +2.752249890 | 7.59739×10⁻⁵ | 12.353 s | 337.342 MB |
| 200 | −62.259729630306744 | −3.047801910 | 1.28989×10⁻⁵ | 20.243 s | 548.422 MB |
| 400 | −62.260015739771831 | −3.333911375 | 1.47701×10⁻⁶ | 65.783 s | 772.182 MB |
| 600 | −62.260044743233664 | −3.362914837 | 3.82084×10⁻⁷ | 144.191 s | 1105.883 MB |
| 800 | −62.260050678669316 | −3.368850272 | 1.37043×10⁻⁷ | 243.775 s | 1934.438 MB |
| 1000 | −62.260052579366490 | −3.370750969 | 5.55832×10⁻⁸ | 381.273 s | 3638.252 MB |
| 1500 | **−62.260053669390740** | **−3.371840994** | **9.55300×10⁻⁹** | 888.421 s | 7838.953 MB |

The saved-MPS energy and discarded weight both improve monotonically across
the complete local ladder. Raising M from 1000 to 1500 lowers the saved-state
energy by another 1.090024250 μEₕ.

## Ordering comparison

| Ordering | M | Saved-MPS E (Eₕ) | E−SKQD (mEₕ) | Discarded weight | DMRG wall | RSS |
|---|---:|---:|---:|---:|---:|---:|
| Fiedler | 200 | −62.16912734534762 | +87.554483049 | 1.38125×10⁻⁴ | 29.536 s | 559.395 MB |
| corrected GA | 200 | **−62.259729630306744** | **−3.047801910** | 1.28989×10⁻⁵ | 20.243 s | 548.422 MB |

GA wins every declared selection criterion at M=200: lower saved-state energy,
smaller discarded weight, lower DMRG wall time, and slightly lower measured RSS.
Its 64-start orbital optimization took about 30 seconds locally.

Relative to the external anchors, the M=1500 GA saved-MPS energy is lower by:

- RHF: 4.735125519391 Eₕ;
- CAS(4): 0.628309199391 Eₕ;
- verified SKQD: 0.003371840994 Eₕ.

Because the FCIDUMP bytes and conserved sector are identical, this is direct
classical variational evidence against treating the reported SKQD energy as a
classical intractability boundary for this instance. It is not an estimate of
the exact ground-state energy and does not establish DMRG convergence.

## 2Fe–2S calibration status

The local 2Fe–2S run used the pinned 20-orbital, 30-electron singlet FCIDUMP and
produced a verified saved-MPS expectation −116.55594588546296 Eₕ at M=500.
The energy decreases with M, but the trajectory is lower than the public M=500
point by about 0.0202 Eₕ. The public script records NumPy seed 1234 without
seeding the block2 C++ backend; the present runner seeds both explicitly.

This establishes the input, SU(2), Fiedler, staged-DMRG, checkpoint, and result
pipeline, but it is **not** the plan's G1 point-by-point/M=1500 reproduction.
G1 therefore remains partial.

## Verification and residual uncertainty

Completed:

- immutable input URL, commit, Git blob, size, SHA-256, and FCIDUMP header audit;
- exact two-orbital Hubbard-dimer block2 integration test;
- result schema that forbids an extrapolated headline;
- strict orbital-permutation and corrected GA-selection tests;
- fresh-process checkpoint norm and energy recomputation through M=1500;
- PySCF RHF sign check: −57.524928149365095 Eₕ, within 6.4×10⁻¹⁰ Eₕ of the public anchor.

Not completed:

- the M=1500 final sweep energy change was 8.93×10⁻⁸ Eₕ, so the strict
  10⁻⁹ sweep convergence target was not reached;
- M=2000 and M=4000 were not run;
- independent cross-method validation;
- full 2Fe–2S M=1500 reproduction.

These gaps do not invalidate the independently verified saved M=1500
variational expectation, but they do prevent a strictly converged
ground-state claim. The SKQD source also provides no complete uncertainty
budget, so the supported cross-method statement is “lower variational energy,”
not formal agreement of uncertainty intervals.

## Reproduction

From this directory:

```bash
env UV_CACHE_DIR=/tmp/issue119_uv_cache ./.venv/bin/uv sync --all-groups --frozen
env UV_CACHE_DIR=/tmp/issue119_uv_cache ./.venv/bin/uv run --frozen pytest -q
```

The exact run configuration is `configs/anderson-ga-m1500-local.toml`.
Generated inputs and the restartable MPS checkpoint remain under the
gitignored path
`tracks/qcs/results/issue-119-20260728/anderson-ga-m1500/`. The compact
structured results and figures committed with this solution are under
`artifacts/anderson-ga-m1500/`.
