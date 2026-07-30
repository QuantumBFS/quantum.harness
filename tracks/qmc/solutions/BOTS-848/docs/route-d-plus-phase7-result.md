# Route D+ Phase 7 ED reveal and diagnosis

## Outcome

Phase 7 completed on hpccube at clean revision
`9c0e3b1e9a575e840c5e1f371865e49faa8ea5e8`. Five `M` sectors, checkpoint
overlaps, and span ceilings ran concurrently in isolated directories. The
aggregate gate and an independent readback both passed.

The frozen three-seed D+0 family is highly accurate for the ground state but
does not yet meet the intended tower/gap accuracy. Because its span ceiling is
substantially higher than the trained result, the preregistered classification
is `optimization-failure` and the capacity decision is `keep-D+0`.

## Exact N=6 reference

For `N=6`, `2Q=15`, pair-only chord-distance Coulomb:

| Sector | Energy | `<L^2>` | `Var(L^2)` |
| --- | ---: | ---: | ---: |
| `L=0, M=0` | `3.8716349140212514` | `-2.36e-15` | `2.97e-25` |
| `L=2, M=-2` | `4.0033233259863445` | `5.999999999999992` | `0` |
| `L=2, M=-1` | `4.003323325986346` | `5.999999999999998` | `7.11e-15` |
| `L=2, M=0` | `4.003323325986338` | `5.999999999999997` | `7.11e-15` |
| `L=2, M=1` | `4.003323325986342` | `6.000000000000001` | `0` |
| `L=2, M=2` | `4.003323325986342` | `5.999999999999996` | `0` |

The ED neutral gap is `0.1316884119650905`; the fivefold splitting is
`7.99e-15`.

## Frozen D+0 checkpoints

| Seed | Ground energy | Tower energy | Gap | Ground fidelity | Tower fidelity |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 848 | `3.872007717301287` | `4.022232193706449` | `0.15022447640516212` | `0.998277894249858` | `0.7995842296608702` |
| 1848 | `3.8725422869176755` | `4.009002893220704` | `0.1364606063030287` | `0.9954773533833324` | `0.91279738303136` |
| 2848 | `3.872009264698613` | `4.0103733067860485` | `0.13836404208743547` | `0.9984676699340177` | `0.9195470668428426` |

Three-seed means:

- gap `0.1416830415985421`;
- absolute gap error `0.009994629633451574`;
- ground fidelity `0.9974076391890695`;
- tower fidelity `0.8773095598450243`.

The rank-four `krylov_depth=1` variational span reaches ground fidelity
`0.9999615444874744` and mean tower fidelity `0.9780601427938913`, supporting
the optimization-failure diagnosis.

## Slurm and integrity evidence

Producer job `23029855` completed `0:0` in 93 seconds on `e02r04`, using 14
CPUs, 42 GiB, and one GPU. Independent readback job `23030080` completed
`0:0`.

- producer stdout SHA-256:
  `7b736cb697507a029f5d74da048cfecbb7b000127d7d5b826f63f435e5bde241`;
- producer stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`;
- aggregate SHA-256:
  `cb1aa32aff0dc6939117697bd5a449357d48acd6cd50c5bb323b7cc622618ee7`;
- readback stdout SHA-256:
  `8204b69fde82c4bf372303f0e450bff15743e6a721d0e3da7af9ec5dfeb674e2`;
- readback stderr SHA-256:
  `415553893fc89130b1308f07391239398d65911f4ecdafdc4259a92f30fc9527`;
- readback JSON SHA-256:
  `ff71c2294cda09eb4b6ffb525f9041d09c93b96c56363f3623f3029dd3de620b`.

The aggregate verifies the exact task set, isolated directories, schemas,
artifact hashes, prerequisite hashes, GPU Slurm evidence, clean consistent
revision, and stage decision. Its independent readback is archived under
[`submission/`](../submission/).
