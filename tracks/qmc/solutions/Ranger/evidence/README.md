# Ranger evidence pack

This directory is the review-facing map from each headline claim to its
public evidence. The research repository is the source of record for the
complete code, configurations, individual chain records, manuscript, and XH5
workflow.

## Claim-to-evidence map

| Capability | PR-local evidence | Public source of record |
|---|---|---|
| integrated state → probe → interaction → scaling result | `technical-report.md` | [technical delivery report](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/docs/final-technical-report.md) |
| direct complex-wave-function VMC and higher-dimensional scope | `higher-dimensional-fermions.md` | [scientific analysis](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/docs/higher-dimensional-fermion-vmc.md) |
| per-chain outcome-complete contract | `fermion-scaling-chain-v1.schema.json` | [JSON Schema](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/schemas/fermion-scaling-chain-v1.schema.json) |
| hash-verified multi-size aggregation | `fermion-scaling-summary.json` | [machine-readable summary](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/results/fermion_scaling/summary.json) |
| one-row-per-chain review table | `chains.tsv` | [human-readable table](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/results/fermion_scaling/chains.tsv) |
| readable inputs and individual records | — | [records and configurations](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/tree/codex/neural-graviton-paper/results/fermion_scaling) |
| full scientific narrative and figures | — | [16-page APS-style manuscript](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/paper/neural-graviton-microscope/neural-graviton-landscape.pdf) |
| scheduler submission and automatic aggregation | — | [XH5 protocol](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/tree/codex/neural-graviton-paper/hpc/xh5) |

## Terminal quantitative certificate

The final package contains all 84 preregistered chains across
`N=4,8,10,12`: 71 completed estimator paths and 13 recorded eight-hour
scheduler boundaries. Completion is 35/40 at `N=10` and 32/40 at `N=12`.
Median bridge fractions remain `0.718676` and `0.694447`, while median
tangent-overlap IATs remain `1.64475` and `1.84971` at the two XH5 sizes.

Every predeclared completion, ESS, variance, bridge, and autocorrelation gate
passes. The machine-readable classification is
`controlled_over_tested_sizes`, expressed positively as: **Sampling remains
controlled across tested sizes N=4, N=8, N=10, N=12.**

## Public entry points

- [research repository](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/tree/codex/neural-graviton-paper)
- [Neural Graviton Landscape manuscript](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/paper/neural-graviton-microscope/neural-graviton-landscape.pdf)
- [technical delivery report](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/docs/final-technical-report.md)
- [machine-readable scaling summary](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/results/fermion_scaling/summary.json)

Together these artifacts bind the algorithmic advances, numerical
certificates, and reproducibility record into one self-contained public
delivery.
