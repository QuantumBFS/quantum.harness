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

## Collaborator handoff: real U(1) Kull SDP (2026-07-30)

### What is implemented

The current calculation targets the infinite spin-½ XXZ chain

`H = Σᵢ (SᵢˣSᵢ₊₁ˣ + SᵢʸSᵢ₊₁ʸ + Δ SᵢᶻSᵢ₊₁ᶻ)`, with `J = 1` and `Δ = 0.5`.

It uses a two-site U(1)-symmetric uniform MPS with alternating virtual-charge spaces. The VUMPS initial state is constructed with `Float64`, and the optimization remains in the real scalar domain. The frozen MPS tensor is never replaced by `real.(A)`: the adapter verifies that the tensor is real, preserves the U(1) intertwiner, and only removes roundoff-sized imaginary parts from auxiliary transfer-matrix fixed points returned by a generic eigensolver.

For an MPS bond dimension `D`, contraction of `m` tensors defines

`Wₘ : (Cᵈ)^⊗m → Cᴰ ⊗ Cᴰ`, so the paper's coarse dimension is `χ = D²`.

The coarse RDMs are split into U(1) charge sectors and represented by real symmetric PSD blocks. This is equivalent to the complex Hermitian SDP when all Hamiltonian and coarse-map coefficients are real, while avoiding the complex-to-real bridge and its additional structural constraints. The implementation is in:

- `VUMPSProducer.jl`: real two-site U(1) VUMPS;
- `MPSKitAdapter.jl`: freezing, charge checks, and transfer fixed points;
- `KullCGRDM.jl`: U(1)-blocked real symmetric SDP and dual diagnostics;
- `KullCGRDMTests.jl`: regression and scalar-domain tests.

The numerical implementation used for the runs below is commit `eaa15a5ea26c336738d5ac320a013df0727bea7b`. A later local change broadens the accepted termination-status policy as described below; it does not change the SDP.

### Numerical acceptance policy

A result is accepted as numerically clean when all of the following hold:

1. MOSEK terminates with `OPTIMAL` or `SLOW_PROGRESS`;
2. primal and dual solution statuses are both `FEASIBLE_POINT`;
3. the maximum reconstructed constraint residual is at most `10⁻⁷`;
4. the minimum eigenvalue over all PSD blocks is at least `−10⁻⁷`.

The original MOSEK termination status is always retained. In particular, `SLOW_PROGRESS` is not relabeled as `OPTIMAL`. Result files generated before this policy change may contain `clean=false` for an otherwise accepted `SLOW_PROGRESS` point; use the recorded status and residuals to re-evaluate those files.

These are floating-point numerical lower bounds with reconstructed dual diagnostics. They are not yet independent exact certificates: publication-grade certification still requires rational or interval-enclosed channel coefficients, PSD projections, and a rigorous residual correction.

### Results

All energies below are per physical site. `corrected lower` is the numerically reconstructed dual-corrected value.

| D | depth | corrected lower | MOSEK status | primal residual | dual stationarity |
|---:|---:|---:|---|---:|---:|
| 4 | 3 | −0.3819032781 | `OPTIMAL` | 2.28×10⁻⁹ | 2.75×10⁻¹² |
| 4 | 5 | −0.3784997730 | `OPTIMAL` | 2.65×10⁻⁸ | 5.77×10⁻¹³ |
| 4 | 7 | −0.3771269471 | `OPTIMAL` | 1.88×10⁻⁸ | 2.47×10⁻¹² |
| 5 | 3 | −0.3819032781 | `OPTIMAL` | 8.12×10⁻⁹ | 2.33×10⁻¹¹ |
| 5 | 5 | −0.3787683456 | `SLOW_PROGRESS` | 4.20×10⁻⁸ | 7.29×10⁻¹² |
| 5 | 7 | −0.3777799933 | `SLOW_PROGRESS` | 3.61×10⁻⁸ | 9.12×10⁻¹² |
| 6 | 3 | −0.3819032781 | `OPTIMAL` | 4.88×10⁻⁹ | 2.89×10⁻¹² |
| 6 | 5 | −0.3787541702 | `OPTIMAL` | 2.68×10⁻⁸ | 7.11×10⁻¹³ |
| 6 | 7 | −0.3777526932 | `OPTIMAL` | 2.79×10⁻⁸ | 8.44×10⁻¹² |
| 6 | 20 | −0.3772437176 | `OPTIMAL` | 2.90×10⁻⁸ | 7.41×10⁻¹¹ |
| 6 | 25 | −0.3772439823 | `SLOW_PROGRESS` | 3.16×10⁻⁸ | 1.49×10⁻¹¹ |
| 6 | 30 | −0.3772445424 | `SLOW_PROGRESS` | 4.45×10⁻⁸ | 1.49×10⁻¹² |
| 6 | 60 | **−0.3772436555** | `OPTIMAL` | 2.65×10⁻⁸ | 1.48×10⁻¹¹ |

For the common `D = 6` MPS, the depth-20 through depth-60 values agree to about `9×10⁻⁷`; increasing depth beyond 20 gives no resolved improvement at the present numerical accuracy. The paper's `n_eff ≈ 60` statement is an effective depth inferred by comparison with exact LTI data, not evidence that the paper explicitly solved the same `D = 6`, `Δ = 0.5`, depth-60 SDP.

### Scale and resources

The `D = 6`, depth-60 model contains 1,301,413 real scalar variables and 177,975 linear equalities. On SCNet, job `23018083` used:

- 32 allocated CPU cores, with Julia, BLAS, and MOSEK limited to 20 threads;
- 110 GiB requested memory, **23.92 GiB measured peak RSS**;
- 91 s model construction, 4,416 s reported MOSEK time, and 5,621 s solve/post-processing wall time;
- 2 h 12 min total Slurm elapsed time, including first-use package precompilation and VUMPS.

A 32–40 GiB memory request is sufficient for the same depth-60 instance with reasonable headroom. The V100 requested by the batch script was only required by that partition's scheduling policy; the calculation itself is CPU-only.

For comparison, the earlier complex Hermitian formulation used about 93.5 GiB already at `D = 6`, depth 5. Real scalar VUMPS plus real symmetric U(1) PSD blocks therefore changes the resource regime by more than a constant-factor Julia allocation improvement.

### Reproduction and artifacts

From the solution directory, run the regression suite with:

```bash
julia --project=../../../../julia-env KullCGRDMTests.jl
```

The full regression after the termination-policy update passes 214/214 tests. The SCNet high-depth runner accepts a comma-separated depth list through `KULL_DEPTHS`; the depth-60 batch configuration used `KULL_DEPTHS=60`, `D=6`, `internal_D=6`, `k₀=3`, and `MOSEK_NUM_THREADS=20`.

Raw per-cell TSV files and Slurm logs are kept outside Git under:

- `results/scnet-u1-real-grid-2026-07-30/` for `D = 4,5,6`, depth `3,5,7`;
- `results/scnet-u1-real-high-depth-2026-07-30/` for `D = 6`, depth `20,25,30`;
- `results/scnet-u1-real-depth60-2026-07-30/` for `D = 6`, depth `60`.

The depth-60 primary record is `result-D6-m60.tsv`; `slurm-23018083.out` contains the build inventory and final result, while `slurm-23018083.err` contains package precompilation output and nonfatal MPSKit environment warnings.
