## Team

| | |
|---|---|
| **Team name** | 组一辈子乐队 |
| **Members** | 季恺昕、李文韬、夏轩哲 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Certify ground-state properties of quantum spin-½ systems by combining the NPA hierarchy of semidefinite-programming relaxations with renormalization-group coarse-graining and structure-exploiting methods, going beyond the scalability of plain NPA relaxations. |
| **Catalog issue** | Addresses #49 — “Certifying ground-state properties of quantum 1/2-spin systems via the coarse-grained NPA hierarchy,” released by 王杰（Jie Wang）, AMSS-CAS. |
| **Track** | `polyopt` — from the issue’s Method field, “Noncommutative polynomial optimization/Quantum bootstrap.” |

## Targets from the issue

Certified lower bounds on ground-state energies:

| Model | Size | Accuracy |
|---|---:|---:|
| 1D Heisenberg | up to 200 spins | 10⁻⁵ |
| 1D J₁–J₂ Heisenberg | up to 100 spins | 10⁻³ |
| 2D Heisenberg | up to 16×16 spins | 10⁻³ |
| 2D J₁–J₂ Heisenberg | up to 10×10 spins | 10⁻², plus the controversy in arXiv:2602.21468v4 |

## Tooling named by the issue

[QMBCertify](https://github.com/wangjie212/QMBCertify) · [NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl) · [NCTSSOS](https://github.com/wangjie212/NCTSSOS)

Work lands on this branch as it proceeds: scripts under this folder, with data and plots under `tracks/polyopt/results/<run>/` (outside Git).
