## Team

| | |
|---|---|
| **Team name** | Do you like Tadej Pogacar? |
| **Members** | Jiansen Zhang, Zimiao Zhang, Jize Xu |

## Challenge

| Row | |
|---|---|
| **Challenge** | Reproduce the Track B validation floor for the long-range transverse-field Ising chain: determine published critical fields with finite-system DMRG, systematic-error audits, and exact anchors. |
| **Catalog issue** | Addresses #86 — “Where does long-range universality end? Three adversarial tests of the σ*=7/4 vs 2 dispute,” released by Kun Chen, Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/mps/` — Track B, DMRG critical-point validation with exact diagonalization and the nearest-neighbour chain as anchors. |

## Scientific scope

This submission evaluates the published critical-point floor at
\(\sigma=1.75\) and \(\sigma=2.0\), with paired sizes through
\((L,2L)=(32,64)\). It records the long-range dynamic exponent \(z\),
\(\gamma/\nu\), the \(\sigma=1.6\) and \(\sigma=1.8\) rows, and larger
\(L\) or \(\chi\) calculations as explicit follow-up work. Consequently,
the report does not claim the complete Track B universality boundary.

The reproducible workflow, analyzer, tests, and result entry points live in
[`../issue-86/`](../issue-86/).

## Current result

The completed school-scale run is labeled
`pipeline validation / finite-size preliminary result`. It reproduces the
two published critical-field intervals at \(\sigma=1.75\) and
\(\sigma=2.0\) within a conservative finite-size error budget, while the
largest crossing brackets and normalized-variance audit remain outside the
formal gates.

The compact public evidence and offline challenge report are available at
[`../issue-86/evidence/partial58-preliminary/`](../issue-86/evidence/partial58-preliminary/).
