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

## Current quantitative certificate

The public snapshot contains two independent chains at each of `N=4` and
`N=8`. The independent `N=8` coordinate-tangent and stochastic one-mode
estimators agree within `0.264` combined standard errors. Median bridge
fractions are `0.704760` and `0.747675`, and median tangent-overlap IATs are
`1.38222` and `0.99293` for `N=4` and `N=8`, respectively.

The registered 80-chain `N=10,12` array expands this same contract across 40
seeds per size. Its automatic finalizer publishes every terminal scheduler
outcome, preserving a direct path from raw computation to the final scaling
classification.

## Public entry points

- [research repository](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/tree/codex/neural-graviton-paper)
- [Neural Graviton Landscape manuscript](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/paper/neural-graviton-microscope/neural-graviton-landscape.pdf)
- [technical delivery report](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/docs/final-technical-report.md)
- [machine-readable scaling summary](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/results/fermion_scaling/summary.json)

Together these artifacts bind the algorithmic advances, numerical
certificates, and reproducibility record into one self-contained public
delivery.
