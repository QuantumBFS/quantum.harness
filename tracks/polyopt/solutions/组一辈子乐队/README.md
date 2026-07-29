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

## Research direction: MPS-guided bootstrap

The useful interface is asymmetric: an MPS supplies a problem-adapted coarse-graining map, while the bootstrap remains an outer relaxation and supplies the certified lower bound.

1. Obtain a uniform MPS tensor `A[D,d,D]` from VUMPS/DMRG. Its variational energy is the upper endpoint `E_MPS ≥ E₀`; it must not be imposed as a lower-bound constraint.
2. Freeze `A` before solving the SDP. Contracting `m` copies gives a linear map `W_m` from `m` physical spins to two virtual bonds. Compress the interior of an `m`-site RDM by `ω^(m) = (I_d ⊗ W_{m-2} ⊗ I_d) ρ^(m) (I_d ⊗ W_{m-2}† ⊗ I_d)`. Thus `ω^(m)` is a `d²D² × d²D²` PSD matrix, independent of `m`; no isometry or truncation-error assumption is needed.
3. Replace the exponential RDM hierarchy by `ρ^(3) ⪰ 0`, `ω^(m) ⪰ 0` for `m = 4,…,n`, and the linear left/right consistency equations induced by `W₂`, `L_A`, and `R_A` (PRX Eq. 14). Every physical locally translation-invariant state maps to a feasible tuple for any fixed `A`, so minimizing over this larger feasible set remains a rigorous lower bound. Memory scales as `O(n d⁴D⁴)`.
4. Couple this to structured NPA through shared Pauli moments. Expand every entry of `ρ^(3)` and `ω^(m)` as a linear functional of Pauli words; add their PSD and consistency equations to the existing Pauli-normal-form moment SDP. This is safer than replacing the NPA moment matrix: the original moment/SOHS blocks, RDM positivity, and state-optimality constraints remain valid, while the MPS channel contributes additional coarse PSD blocks whose coefficients are fixed contractions of `A`.
5. Exploit symmetry only after constructing the coarse blocks. A generic learned tensor can break spin, reflection, or translation covariance even when the Hamiltonian has it. Either learn a symmetry-adapted tensor and prove the induced maps intertwine the group action, or retain only symmetries verified directly on the assembled SDP coefficients.
6. Keep tensor learning outside the certificate. Alternating SDP solves with updates of `A` may tighten the bound, but the final solve must freeze one explicit tensor. Rationalize `A` (or use interval-enclosed coefficients), then project and verify the dual Gram matrices independently; otherwise the output is a numerical lower estimate, not an exact certificate.

The strictness boundary is whether information is discarded from the *constraints* or from the *physical state space*. Congruence compression `ρ ↦ WρW†` only observes part of a PSD constraint; a poor `W` makes the bound looser but cannot exclude a physical state. In contrast, imposing `ρ = PρP`, fixing moments to their MPS values, or replacing `H` by `PHP` restricts the state space and does not certify the original Hamiltonian unless an explicit operator inequality such as `H ⪰ H̃ − εI` is proved. A Schmidt discarded weight alone is not such an error bound.

Adding coarse blocks also changes the dual certificate. QMBCertify's current exact post-processing reconstructs its standard structured-NPA Gram identity; it cannot certify the augmented SDP unchanged. The implementation therefore needs dual multipliers for every coarse PSD/consistency constraint, exact or interval-enclosed channel coefficients, reconstruction of the full fixed-basis identity, and a rigorous correction for residual coefficients and negative Gram eigenvalues.

### First executable experiment

Start with the periodic `N = 12` spin-½ antiferromagnetic Heisenberg chain, `H = Σ_i S_i·S_{i+1}`, total `Sᶻ = 0`, and energy density as the objective. This instance is small enough for an ED reference with exactly the same Hamiltonian and boundary convention. After ratifying this setup, compare:

- plain structured NPA at one fixed order and basis;
- the same SDP plus one frozen MPS-guided coarse level with `D = 1,2,4`;
- the same frozen map plus successive nested coarse levels.

For every point report the bracket `E_lb(A,D,n) ≤ E_ED ≤ E_MPS(D)`, primal/dual residuals, minimum Gram eigenvalue, and the rational/interval correction to both endpoints. Acceptance requires: `D = 1` reproduces a hand-constructed product map; dropping coarse blocks reproduces plain structured NPA; each augmented feasible set retains all preceding constraints and hence cannot weaken the lower bound beyond solver tolerance; every corrected lower bound stays below ED; and the ascending/descending contractions satisfy their adjoint identity numerically before exact reconstruction. Only after this end-to-end certificate passes should the study compare `D = 2,4,8` and depths `n = 4,8,16,…` at equal largest-PSD-block or scalar-variable cost.

Sources: [Kull et al., Phys. Rev. X 14, 021008 (2024), arXiv:2212.03014](https://doi.org/10.1103/PhysRevX.14.021008), especially Eqs. 11–14; [Cho et al., JHEP 02 (2026) 222, arXiv:2412.07837](https://doi.org/10.1007/JHEP02(2026)222), especially Eqs. 2.13–2.17 and the coarse-grained equilibrium constraints; and [QMBCertify certification helpers](https://github.com/wangjie212/QMBCertify/tree/main/src/certification) for the existing DMRG upper endpoint and rational dual post-processing.

Work lands on this branch as it proceeds: scripts under this folder, with data and plots under `tracks/polyopt/results/<run>/` (outside Git).
