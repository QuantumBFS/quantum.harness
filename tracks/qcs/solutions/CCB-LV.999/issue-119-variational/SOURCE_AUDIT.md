# Source audit and execution amendments

This file records provenance and the two evidence-driven amendments applied while
executing the downloaded `PLAN.md`. The downloaded plan is preserved byte-for-byte.

## Pinned inputs

| Object | Immutable source | Git blob | SHA-256 |
|---|---|---|---|
| `PLAN.md` | `peter0627ustc/quantum.harness@a08e09616fdd83d7d2f1a30090d8b4d02a4794bd` | `b9b16e66daf1c68907b9d21534a42cac2b2823a5` | `dfbd2e1a65428cf54ef35f4dff04864574b2527c4bdfd789e106c5d5abf5df77` |
| 2Fe–2S FCIDUMP | tracker `@e2a2488ceb53344668ac1447f7f96b18703f3524` | `55e0dbab07d4d1754e042e38f98b34b566921f31` | `bd6ef31773f7b082171f73faa6c98924948e2c250b6fbec74504d64361c8c6c7` |
| Anderson FCIDUMP | tracker `@e2a2488ceb53344668ac1447f7f96b18703f3524` | `fe97b1621e4f3fec821d69c275063d3e18992408` | `9c8ceb3faa39ccb9cf2c15632cdc748e449cf26197ee1e8251092a6bb49ce4b6` |

The fetch command verifies file size, SHA-256, `NORB`, `NELEC`, and `MS2` before
the solver sees either input.

## Public numerical anchors

The 2Fe–2S method proof is pinned to
`MonitSharma/qat-2fe2s-submission@d300df87a340123f14321c6812b279fdf6e6f103`.
Its finite-M energies are:

| M | Energy (Eₕ) |
|---:|---:|
| 250 | −116.52623779075185 |
| 500 | −116.53577219230725 |
| 1000 | −116.60505321572569 |
| 1500 | −116.60547665637114 |

For Anderson, the external comparison values are RHF −57.52492815 Eₕ,
CAS(4) −61.63174447 Eₕ, and verified SKQD −62.25668182839704 Eₕ. They are
comparison anchors, never substituted for a locally computed value.

## Amendment 1: orbital representation

The plan's grouped-star and interleaved impurity/bath orderings assume access to
the original star-basis orbitals. The distributed Anderson FCIDUMP instead has
dense one- and two-electron integrals in the CCSD natural-orbital basis used by
the SKQD study. Orbital labels therefore no longer identify four impurities and
their seven physical bath orbitals.

Consequence: the local comparison is Fiedler ordering versus a corrected,
multi-start genetic ordering on the actual FCIDUMP exchange-interaction graph.
A physical grouped-star comparison is deferred unless an audited inverse basis
transformation becomes available.

## Amendment 2: block2 0.5.3 GA selection

`DMRGDriver.orbital_reordering(..., method="gaopt")` in block2 0.5.3 evaluates
each of 64 seeded candidates but returns the lexicographically first unique
permutation. `src/orderings.py` retains the same block2 optimizer and
`OrbitalOrdering.evaluate` objective, but returns the candidate with minimum
evaluated cost. Candidate seeds, permutations, and costs are written to
`ordering.json`.

The public 2Fe–2S proof stores `seed=1234` and calls
`numpy.random.seed(1234)`, but it does not call block2's
`Random.rand_seed`. The research runner seeds both NumPy and the block2 backend;
its low-M trajectory is reproducible but is not presented as a point-by-point
reproduction of the public RNG trajectory.

## Amendment 3: saved-MPS headline

block2's final sweep energy can differ slightly from a fresh expectation value
of the post-truncation MPS on disk. The runner now computes the normalized
saved-MPS expectation after every M stage and uses that value for
`result.json.headline`; the sweep value remains in `sweeps.csv` and
`sweep_energy_hartree`.

For the completed Anderson GA M=200 run, a fresh-process reload shifted the
initial sweep-derived value upward by 9.7692373×10⁻⁵ Eₕ. The final verified
headline is therefore −62.259729630306744 Eₕ, not the lower sweep log value.

## Paper-grounded Anderson ladder

The SKQD paper's classical reference used the CCSD natural-orbital basis,
genetic orbital ordering, SU(2), eight sweeps per bond dimension, and

`M = 100, 200, 400, 600, 800, 1000, 2000, 3000, 4000`.

The local gate first compared M=100 and, because both probes stayed under five
minutes and 12 GiB, extended both orderings to M=200 after the 2Fe–2S
M=250→500 calibration. Production M>200 up to 4000 remains a Slurm phase
because the local machine has only about 15.4 GiB RAM.

## Primary links

- Plan source: <https://github.com/peter0627ustc/quantum.harness/blob/a08e09616fdd83d7d2f1a30090d8b4d02a4794bd/tracks/qcs/solutions/CCB-LV.999/issue-119-variational/PLAN.md>
- Tracker data: <https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/tree/e2a2488ceb53344668ac1447f7f96b18703f3524/data/variational-problems/hamiltonians>
- 2Fe–2S proof: <https://github.com/MonitSharma/qat-2fe2s-submission/tree/d300df87a340123f14321c6812b279fdf6e6f103>
- SKQD paper: <https://arxiv.org/abs/2501.09702>
- block2 0.5.3 driver source: <https://github.com/block-hczhai/block2-preview/blob/v0.5.3/pyblock2/driver/core.py>
