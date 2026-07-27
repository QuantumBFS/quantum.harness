# Members: 高建鑫、吴国良、许传书

# Challenge: 2D finite-temperature tensor networks (#147)

## Model

Transverse-field quantum Ising model on a $10\times10$ square lattice with open boundary conditions:

$$H = -J\sum_{\langle i,j\rangle} \sigma_i^z\sigma_j^z - h\sum_i \sigma_i^x, \qquad J = 1.$$

Field values near the quantum critical point ($h_c/J \approx 3.044$): $h/J \in \{2.5, 3.0, 3.5\}$.

## Goal

Extend PEPO or METTS to 2D and compute thermodynamics over the quantum critical fan $\beta J \in [0.1, 1.0]$:
- Free energy density $f = -\ln Z/(\beta N)$
- Internal energy density $u = \langle H\rangle/N$
- Specific heat $C = \beta^2(\langle H^2\rangle - \langle H\rangle^2)/N$

## Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Thermodynamic curves $f(T)$, $u(T)$, $C(T)$ over $\beta J \in [0.1,1.0]$ | Mandatory |
| 2 | Convergence analysis (in $D$ or sample count) with plots | Mandatory |
| 3 | Validation against QMC reference data | Mandatory |
| 4 | Source code + technical document + one-command test script | Mandatory |
| 5 | tanTRG comparison: accuracy, timing, memory | Bonus |
| 6 | Uniform susceptibility $\chi(T)$ | Bonus |

## Verification

- **QMC (mandatory):** all quantities validated against SSE/worm QMC on the same $10\times10$ lattice
- **Convergence:** PEPO route: $u$ and $C$ convergence in $D \in \{4,6,8\}$; METTS route: sample-count convergence (relative error < 1% on $u$, < 3% on $C$ at $\beta J = 0.8$)
- **Reproducibility:** open source (Julia/TensorKit), one-command test script
