> **Main work & results: see [`SYNTHESIS_REPORT.md`](SYNTHESIS_REPORT.md)**
> (中文版 [`SYNTHESIS_REPORT_ZH.md`](SYNTHESIS_REPORT_ZH.md)) ·
> PR deliverable: [`FINAL_REPORT.md`](FINAL_REPORT.md) ·
> reproduction: [`REPRODUCE.md`](REPRODUCE.md)

## Team

| | |
|---|---|
| **Team name** | its-a-trap |
| **Members** | Yan-Bai Zhang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Certify ground-state properties of quantum spin-1/2 systems by combining the NPA hierarchy of SDP relaxations with renormalization-group coarse-graining maps, and layering on the structure-exploiting techniques of arXiv:2604.01555 — going beyond plain NPA, whose SDP sizes explode well before the target system sizes are reachable. |
| **Catalog issue** | `Addresses #49` — *Certifying ground-state properties of quantum 1/2-spin systems via the coarse-grained NPA hierarchy*, released by 王杰 (Jie Wang), AMSS-CAS. |
| **Track** | `polyopt`. The issue names no solution folder, so the track comes from its `Method` field, *Noncommutative polynomial optimization / Quantum bootstrap*. |

## Targets from the issue

The issue asks for **lower** bounds on ground-state energies:

| Model | Size | Accuracy |
|---|---|---|
| 1D Heisenberg | up to 200 spins | 10⁻⁵ |
| 1D J₁–J₂ Heisenberg | up to 100 spins | 10⁻³ |
| 2D Heisenberg | up to 16×16 spins | 10⁻³ |
| 2D J₁–J₂ Heisenberg | up to 10×10 spins | 10⁻², plus the controversy in arXiv:2602.21468v4 |

## Tooling named by the issue

[QMBCertify](https://github.com/wangjie212/QMBCertify) · [NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl) · [NCTSSOS](https://github.com/wangjie212/NCTSSOS)

Work lands on this branch as it goes: scripts under this folder, data and plots under
`tracks/polyopt/results/<run>/` (out of git).
