## Team

| | |
|---|---|
| **Team name** | LlmNewtonGaussTuring |
| **Members** | Xeri Chen |

## Challenge

| Row | |
|---|---|
| **Challenge** | Compute the ground-state adiabatic geometric phase (Berry phase) and Berry curvature density of the 2D square-lattice transverse-field Ising model along closed parameter-space loops. Reproduce the Kolodrubetz (2014) QMC benchmark via the global-spin-rotation parameterisation, extend to the quantum critical region, and cross-validate with exact 1D Jordan-Wigner solutions and small-lattice exact diagonalisation. PEPS overlap discretisation (Fukui-Hatsugai-Suzuki gauge-invariant method) provides the primary thermodynamic-limit route. |
| **Catalog issue** | Addresses #73 — "Computing the geometric phase of 2D TFIM", released by Si-Yuan Chen. |
| **Track** | `tracks/peps/solutions/LlmNewtonGaussTuring/` — issue specifies `Method: PEPS Based Algorithm`, with ED and QMC as validating routes. |

## Implementation status

This directory currently contains registration metadata only. No PEPS/iPEPS,
CTMRG environment, tensor-network overlap, bond-dimension convergence, or
thermodynamic-limit Berry-curvature implementation exists here yet. The shared
ED/FHS and SSE diagnostics live under
`tracks/qmc/solutions/LlmNewtonGaussTuring/`; they do not satisfy the PEPS route.
