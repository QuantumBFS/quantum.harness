# Exactly-Solvable Models Catalog — Index

This is the harness's verification-oracle layer: for each entry below, an
`ORACLE.md` card states the exact result(s) a numerical run (ED / DMRG / QMC /
VMC) can be checked against, with provenance. It sits alongside the model zoo
(`.knowledge/models/`) and the method zoo (`.knowledge/methods/`) as a third
knowledge layer — cross-linked to both where a physics card or a method exists
for the same model.

**Tiers** (what is exactly known):

| Tier | Meaning |
|---|---|
| **A** | Full solution — complete spectrum and/or all correlators |
| **B** | Integrable — Bethe ansatz / Yang–Baxter: exact GS energy, gap, some correlators, TBA thermodynamics |
| **C** | Exact ground state / exact eigenstates only |
| **D** | Exact in a limit |

**Script flags** (oracle-script coverage):

| Flag | Meaning |
|---|---|
| **S** | Full oracle script — all card quantities computable via `oracle.py` |
| **P** | Partial script — a subset of the exact results is scriptable; the rest are tabulated |
| **T** | No oracle script — tabulated literature values only |

**Running an oracle:**

```
cd .knowledge/solvable && uv run python <card>/oracle.py --help
```

**Running the full self-test suite** (from repo root):

```
make test-oracles
```

63 models total, organized by solution technique (T1–T7) — the technique
determines what is computable and what the script looks like. Tier and
script-coverage are tag columns, not groupings. Status marks build wave
(`.knowledge/solvable/`'s implementation phasing, spec §8); Card links to the
built `ORACLE.md` where available.

## T1 Quadratic / free-particle

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `tfim-chain` | A | S | ✓ wave 1 | [ORACLE](./tfim-chain/ORACLE.md) |
| `xy-chain` | A | S | ✓ wave 1 | [ORACLE](./xy-chain/ORACLE.md) |
| `kitaev-chain` | A | S | ✓ wave 1 | [ORACLE](./kitaev-chain/ORACLE.md) |
| `long-range-kitaev` | A | S | ✓ wave 1 | [ORACLE](./long-range-kitaev/ORACLE.md) |
| `ssh-chain` | A | S | ✓ wave 1 | [ORACLE](./ssh-chain/ORACLE.md) |
| `kitaev-honeycomb` | A | S | ✓ wave 1 | [ORACLE](./kitaev-honeycomb/ORACLE.md) |
| `p-ip-superconductor` | A | S | ✓ wave 1 | [ORACLE](./p-ip-superconductor/ORACLE.md) |
| `tight-binding-lattices` | A | S | ✓ wave 1 | [ORACLE](./tight-binding-lattices/ORACLE.md) |
| `hofstadter-harper` | A | S | ✓ wave 1 | [ORACLE](./hofstadter-harper/ORACLE.md) |
| `haldane-chern` | A | S | ✓ wave 1 | [ORACLE](./haldane-chern/ORACLE.md) |
| `anderson-1d` | A | S | ✓ wave 1 | [ORACLE](./anderson-1d/ORACLE.md) |
| `harmonic-chain` | A | S | ✓ wave 1 | [ORACLE](./harmonic-chain/ORACLE.md) |
| `bogoliubov-bose-gas` | A/D | S | ✓ wave 1 | [ORACLE](./bogoliubov-bose-gas/ORACLE.md) |

## T2 2D classical / transfer matrix

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `ising-2d-onsager` | A | S | ✓ wave 2 | [ORACLE](./ising-2d-onsager/ORACLE.md) |
| `ising-triangular` | A | S | ✓ wave 2 | [ORACLE](./ising-triangular/ORACLE.md) |
| `dimer-kasteleyn` | A | S | ✓ wave 2 | [ORACLE](./dimer-kasteleyn/ORACLE.md) |
| `six-vertex` | B | S | ✓ wave 2 | [ORACLE](./six-vertex/ORACLE.md) |
| `eight-vertex` | B | P | ✓ wave 2 | [ORACLE](./eight-vertex/ORACLE.md) |
| `hard-hexagons` | B | P | ✓ wave 2 | [ORACLE](./hard-hexagons/ORACLE.md) |

## T3 Bethe ansatz / Yang–Baxter

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `heisenberg-xxx` | B | S | ✓ wave 2 | [ORACLE](./heisenberg-xxx/ORACLE.md) |
| `xxz-chain` | B | S | ✓ wave 2 | [ORACLE](./xxz-chain/ORACLE.md) |
| `xyz-chain` | B | P | ✓ wave 2 | [ORACLE](./xyz-chain/ORACLE.md) |
| `zamolodchikov-fateev-spin1` | B | T | ✓ wave 2 | [ORACLE](./zamolodchikov-fateev-spin1/ORACLE.md) |
| `haldane-shastry` | B | S | ✓ wave 2 | [ORACLE](./haldane-shastry/ORACLE.md) |
| `inozemtsev-chain` | B | T | ✓ wave 2 | [ORACLE](./inozemtsev-chain/ORACLE.md) |
| `hubbard-1d-lieb-wu` | B | S | ✓ wave 2 | [ORACLE](./hubbard-1d-lieb-wu/ORACLE.md) |
| `susy-t-j` | B | P | ✓ wave 2 | [ORACLE](./susy-t-j/ORACLE.md) |
| `lieb-liniger` | B | S | ✓ wave 2 | [ORACLE](./lieb-liniger/ORACLE.md) |
| `tonks-girardeau` | A | S | ✓ wave 2 | [ORACLE](./tonks-girardeau/ORACLE.md) |
| `yang-gaudin` | B | S | ✓ wave 2 | [ORACLE](./yang-gaudin/ORACLE.md) |
| `calogero-sutherland` | B | P | ✓ wave 2 | [ORACLE](./calogero-sutherland/ORACLE.md) |
| `kondo-bethe` | B | T | ✓ wave 2 | [ORACLE](./kondo-bethe/ORACLE.md) |
| `anderson-impurity-bethe` | B | T | ✓ wave 2 | [ORACLE](./anderson-impurity-bethe/ORACLE.md) |
| `richardson-pairing` | B | S | ✓ wave 2 | [ORACLE](./richardson-pairing/ORACLE.md) |
| `gaudin-central-spin` | B | S | ✓ wave 2 | [ORACLE](./gaudin-central-spin/ORACLE.md) |
| `chiral-potts` | B | T | ✓ wave 2 | [ORACLE](./chiral-potts/ORACLE.md) |

## T4 Commuting projector / stabilizer

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `toric-code` | A | S | ✓ wave 1 | [ORACLE](./toric-code/ORACLE.md) |
| `quantum-double` | A | P | ✓ wave 1 | [ORACLE](./quantum-double/ORACLE.md) |
| `string-net` | A | P | ✓ wave 1 | [ORACLE](./string-net/ORACLE.md) |
| `color-code` | A | S | ✓ wave 1 | [ORACLE](./color-code/ORACLE.md) |
| `x-cube` | A | S | ✓ wave 1 | [ORACLE](./x-cube/ORACLE.md) |
| `haah-code` | A | P | ✓ wave 1 | [ORACLE](./haah-code/ORACLE.md) |
| `cluster-spt` | A | S | ✓ wave 1 | [ORACLE](./cluster-spt/ORACLE.md) |

## T5 Frustration-free / exact eigenstates

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `aklt-chain` | C | S | wave 3 | — |
| `aklt-honeycomb` | C | P | wave 3 | — |
| `majumdar-ghosh` | C | S | wave 3 | — |
| `shastry-sutherland-dimer` | C | S | wave 3 | — |
| `rk-quantum-dimer` | C | S | wave 3 | — |
| `motzkin-fredkin` | C | S | wave 3 | — |
| `eta-pairing-hubbard` | C | S | wave 3 | — |
| `pxp-scars` | C | S | wave 3 | — |

## T6 Collective / large-N / random

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `lmg` | A | S | wave 3 | — |
| `dicke-tavis-cummings` | B | S | wave 3 | — |
| `jaynes-cummings` | A | S | wave 3 | — |
| `quantum-rabi` | B | S | wave 3 | — |
| `syk` | D | P | wave 3 | — |
| `curie-weiss-tfim` | D | S | wave 3 | — |
| `random-matrix-stats` | A | S | wave 3 | — |
| `falicov-kimball-dinf` | D | T | wave 3 | — |

## T7 Dualities & solvable dynamics

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `kramers-wannier` | A | S | wave 3 | — |
| `jw-duality-dictionary` | — | T | wave 3 | — |
| `dual-unitary-circuits` | A | S | wave 3 | — |
| `kicked-ising-floquet` | A | S | wave 3 | — |

## Totals

63 models — 43 built (wave 1 complete: 20 T1 + T4 cards; wave 2
complete: 23 of 23 T2 + T3 cards), 20 wave 3 rows remaining (T5 + T6 +
T7). Script-flag totals: **46 S · 10 P · 7 T**.
