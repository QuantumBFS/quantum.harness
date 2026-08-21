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

**Overall challenge status: `gate-pending`.** Stage 4 passed its small-system
validation gate. The later Stage 5 checkpoint adds matrix-free ED, scaling, and
iPEPS ground-state scaffolding, but does not yet implement mixed-iPEPS overlap
contraction or an iPEPS FHS Berry-curvature production pipeline. See
`STAGE5_REPORT.md`.

### Stage 4 (2026-07-29): Pure-NumPy PEPS-FHS engine

Core engine (`peps_fhs.py`) provides:
- Dense TFIM Hamiltonian with Kolodrubetz rotation $H(\theta,\Omega) = R_x(\theta) H_0 R_x^\dagger(\theta)$
- Exact diagonalization for small systems (up to $N=9$, dim=512)
- MPS decomposition with bond-dimension truncation (snake-path PEPS proxy)
- FHS Berry curvature: $F_{12} = -\arg(U_1 U_2 U_1^* U_2^*) / (d\theta \cdot d\Omega)$
- 1D JW chain oracle for cross-validation

Test suite (`test_peps_fhs.py`): 9/9 passing.  
CLI sweep (`run_stage4.py`): CSV output compatible with C++ `scan_berry_square`.

Validated properties:
- $H(\theta)$ rotation identity: machine precision
- $F_{12}$ is $\theta$-independent (physical)
- MPS $D \ge 4$ matches ED to $10^{-14}$ for $L=2$
- Near-critical curvature enhancement visible

Limitations: quimb unavailable (network); MPS uses 1D bonds only. Full 2D PEPS with vertical virtual bonds and SimpleUpdate optimization requires quimb — planned for Stage 5.

### Stage 5 (2026-07-29): large-ED and iPEPS readiness

- Matrix-free complex Lanczos extends the square-lattice ED oracle through
  `N=16`; a finite-size scaling script and Rydberg laser-phase parameterization
  are present.
- PEPSKit/TensorKit scripts provide iPEPS ground-state and `D, chi` convergence
  scaffolding.
- Remaining software gate: normalized mixed-iPEPS overlaps and the four-link
  FHS plaquette observable have not been connected to the optimized iPEPS
  states. No iPEPS curvature production result exists yet.

See `STAGE4_REPORT.md` for full details.
