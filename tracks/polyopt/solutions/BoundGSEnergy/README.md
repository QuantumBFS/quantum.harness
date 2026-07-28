# BoundGSEnergy — coarse-grained NPA certification for quantum spin systems

> **2026-07-27 — work moved.** With the organizers' blessing, this team's
> research now lives in the standalone repo
> [**wangfh5/BoundGSEnergy**](https://github.com/wangfh5/BoundGSEnergy)
> (scripts, results, survey library, plan; skills pinned via Ion remote
> deps). This folder keeps only the registration README and PLAN.md.

## Team

| | |
|---|---|
| **Team name** | BoundGSEnergy |
| **Members** | Fo-Hong Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Combine the NPA hierarchy of SDP relaxations with renormalization-group coarse-graining (PRX 14, 021008, Sec. III-D-2) plus the structure-exploiting techniques of arXiv:2604.01555, to push *certified* ground-state-energy lower bounds for spin-1/2 Heisenberg systems to larger sizes and tighter accuracy — going beyond the reproduction of the published structured-NPA bounds. |
| **Catalog issue** | Addresses #49 — released by Jie Wang (AMSS-CAS). |
| **Track** | `polyopt` — from the issue's `Method` field ("Noncommutative polynomial optimization/Quantum bootstrap"), normalized onto the seven tracks. |

## Plan (seed)

Targets are graded as a ladder, one new concept per rung:

1. 1D Heisenberg chain: certified lower bounds up to 200 spins, accuracy 10⁻⁵.
2. 1D J₁–J₂ Heisenberg chain: up to 100 spins, accuracy 10⁻³.
3. 2D square Heisenberg: up to 16×16, accuracy 10⁻³.
4. 2D J₁–J₂: up to 10×10, accuracy 10⁻²; address the arXiv:2602.21468 controversy.

Starting assets: a completed reproduction of the arXiv:2604.01555 Table 8
bounds (beginner-tier, L = 4, 6, 8) with the public QMBCertify.jl — including
the finding that the shipped code reproduces the PRX-2024-era ("old") column
exactly but not the 2026 "new" column — and a 34-reference survey library at
`.knowledge/literature/polynomial-optimization/` with a NOTES.md field map.

Scripts land in this folder; data and plots go to
`tracks/polyopt/results/<run>/` (gitignored).
