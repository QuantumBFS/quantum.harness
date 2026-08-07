## Team

| | |
|---|---|
| **Team name** | 卧龙凤雏 |
| **Members** | Xu Tian, Huidan Tan |

## Challenge

| Row | |
|---|---|
| **Challenge** | Reproduce effective central charges in monitored and decohered critical quantum matter, then investigate the open learning-induced metal–insulator transition beyond the known benchmarks. |
| **Catalog issue** | Addresses #122 — *Criticality in open quantum matter*, released by Guo-Yi Zhu, Hong Kong University of Science and Technology (Guangzhou). |
| **Track** | `qmc/` — selected by the team because the issue’s `Method` field spans Monte Carlo sampling and tensor-network contraction. |

## Paper

- [PRB-format paper (PDF)](effective-central-charges-prb-paper.pdf)

## Benchmark

- [Clean Ising central-charge verification](clean-ising/README.md) — Rust
  transfer matrix and Xoshiro256++ Wolff Monte Carlo, with Python analysis and
  an offline report.
- [Ordinary Nishimori central-charge verification](nishimori-ising/README.md) —
  Rust random transfer products with Python finite-size analysis.
- [Weak self-dual central-charge verification](weak-self-dual/README.md) —
  Rust Born-correlated Gaussian Majorana trajectories with Xoshiro256++, plus
  Python bootstrap analysis, plots, and an offline report.
- [Learning-induced metal-insulator transition](learning-mit/README.md) —
  exploratory Rust Born-Gaussian study of the XY validation line and a generic
  DIII cut, with hash-gated Python analysis and bilingual offline reports.
