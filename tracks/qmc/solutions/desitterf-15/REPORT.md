# Challenge 15 finite-sphere benchmark report

Computed on 2026-11-05 with the default commands in [README.md](README.md). The calculation uses the LLL-projected chord-distance Coulomb Hamiltonian, flux 2Q = 3(N−1), and energy units e²/(εℓB).

## Main results

| N | 2Q | M = 0 dimension | L = 0 copies | L = 2 copies | E₀ | E₂ | Δ from Rayleigh energies |
|---|---|---|---|---|---|---|---|
| 4 | 9 | 18 | 2 | 2 | 1.8711384121 | 2.0029951671 | 0.1318567549 |
| 5 | 12 | 73 | 2 | 4 | 2.8055532158 | 2.9317252796 | 0.1261720638 |
| 6 | 15 | 338 | 6 | 11 | 3.8716349140 | 4.0033233260 | 0.1316884120 |

These are total electron–electron energies. The uniform-background shift −N²/(2√Q) is common to both states at each size. The reported gaps agree with full-M-block, L-labelled exact diagonalization to 1.2 × 10⁻¹⁵ in this run. For the printed results, a conservative numerical reporting floor of 10⁻¹² accommodates floating-point linear algebra and cancellation. This is a reporting convention rather than a rigorous interval bound.

The selected states were also measured with fresh MC draws. The table retains additional digits for comparing the sampled estimate with the exact expectation of the same trained wavefunction.

| N | MC estimate of Δ | MC standard error | ED reference Δ | Signed variational gap bias |
|---|---|---|---|---|
| 4 | 0.131856754927012 | 5.83 × 10⁻¹⁵ | 0.131856754927025 | −1.11 × 10⁻¹⁵ |
| 5 | 0.126172063856482 | 5.25 × 10⁻¹² | 0.126172063847541 | 0.00 at displayed precision |
| 6 | 0.131688411965092 | 1.86 × 10⁻¹⁷ | 0.131688411965091 | +8.88 × 10⁻¹⁶ |

Each state uses 262144 independent occupation-basis Born draws. Ground and excited measurements use different seeds. The gap error is the quadrature sum of their one-standard-error uncertainties. These columns describe sampling fluctuations only. In particular, the N = 6 sampling SE falls below double-precision numerical accuracy as the local energy approaches a constant. The numerical reporting floor governs meaningful digits in that regime.

The exact Rayleigh difference for N = 5 is 0.126172063847541. Its sampled difference lies 1.70 MC standard errors higher. The signed variational gap bias is defined as (E₂−E₂,ED)−(E₀−E₀,ED) and can have either sign. Differences at the 10⁻¹⁵ level are consistent with numerical roundoff.

## Ansatz and training

The wavefunction is a neural combination of antisymmetric LLL Slater determinants through fixed SO(3) intertwiners. Highest-weight states are obtained from the kernel of L₊ and lowered into the full multiplet. A Casimir-subspace projection after each lowering step suppresses high-L floating-point contamination while retaining the multiplicity gauge. One shared width-16 tanh MLP generates normalized coefficient vectors for the L = 0 and L = 2 sectors of each N.

The parameter counts are 82, 116, and 235 for N = 4, 5, and 6. Both sector inputs use the same hidden and output layers. Coefficients are independent of M. The finite-sector parameterization covers the complete real multiplicity spaces needed for the real Coulomb matrices in this convention.

Every seed receives 4000 Adam updates using 4096 independent Born draws per sector per update. The learning rate is 0.02[0.02 + 0.98(1−step/4000)²], with Adam β₁ = 0.9, β₂ = 0.999, and ε = 10⁻⁸. The VMC covariance gradient includes the n/(n−1) finite-sample correction and the analytic contribution of any exact discrete nodes. Finite differences check the neural gradient, and a dedicated regression checks nodal directions.

Seeds 11, 23, and 37 are trained independently for every N. The lowest exact state-averaged Rayleigh energy selects the checkpoint within a run and then the seed. All three selected seed energies agree within 1.4 × 10⁻¹⁵ for these systems. Seed 11 is selected at each size. Monitoring and checkpoint selection enumerate the finite basis. The stochastic gradients drive the optimization. ED eigenvectors and energies are computed after training for validation.

| N | Ground-state residual ‖Hψ₀−E₀ψ₀‖ | Excited-state residual ‖Hψ₂−E₂ψ₂‖ | Ground variance | Excited variance |
|---|---|---|---|---|
| 4 | 1.30 × 10⁻¹² | 2.68 × 10⁻¹² | 1.70 × 10⁻²⁴ | 7.19 × 10⁻²⁴ |
| 5 | 8.62 × 10⁻¹⁰ | 2.55 × 10⁻⁹ | 7.43 × 10⁻¹⁹ | 6.49 × 10⁻¹⁸ |
| 6 | 9.77 × 10⁻¹⁵ | 4.60 × 10⁻¹⁵ | 9.54 × 10⁻²⁹ | 2.11 × 10⁻²⁹ |

The residuals in this table use M = L, the trained representative. The JSON records the residual for every excited multiplet component as well. Exact full-basis variance includes residual contributions at any discrete nodes.

## Spin-2 certification

All five components M = −2, −1, 0, 1, 2 have the following common energy to the displayed precision. Each M block is independently diagonalized and labelled with its L² expectation to identify the lowest L = 2 reference.

| N | E₂ for all five M values | Maximum energy spread | Maximum absolute deviation of ⟨L²⟩ from 6 | Maximum Casimir residual ‖(L²−6)ψ‖ |
|---|---|---|---|---|
| 4 | 2.002995167073 | 1.78 × 10⁻¹⁵ | 3.56 × 10⁻¹⁵ | 4.28 × 10⁻¹⁴ |
| 5 | 2.931725279631 | 6.22 × 10⁻¹⁵ | 1.25 × 10⁻¹⁴ | 2.24 × 10⁻¹³ |
| 6 | 4.003323325986 | 7.11 × 10⁻¹⁵ | 9.77 × 10⁻¹⁵ | 5.59 × 10⁻¹³ |

The five independently diagonalized L = 2 reference energies have a maximum spread of 3.56 × 10⁻¹⁵. The largest Frobenius residual of the normalized ladder relation across all tested sizes is 1.89 × 10⁻¹³.

The coordinate-space check rotates each entire electron configuration about an arbitrary axis and compares its full multiplet vector with the Wigner rotation. Eight random configurations and rotations are tested per N, for both L sectors. Particle exchange is checked on the same samples.

| N | Maximum absolute rotation error | Maximum relative rotation error | Maximum relative exchange error |
|---|---|---|---|
| 4 | 1.23 × 10⁻¹⁶ | 1.11 × 10⁻¹² | 0 in this run |
| 5 | 1.35 × 10⁻¹⁷ | 1.45 × 10⁻¹¹ | 0 in this run |
| 6 | 4.58 × 10⁻¹⁷ | 9.57 × 10⁻¹⁰ | 0 in this run |

Relative coordinate errors grow near small wavefunction amplitudes, where determinant sums cancel. The absolute error and the relative error are both retained in the machine-readable output.

## Independent checks and reproducibility

An independent read-only physics review reconstructed the Coulomb pseudopotentials with a Gaunt/Wigner-6j expansion and a separate highest-weight-polynomial quadrature. The beta-integral implementation agrees with the 6j result to 2.3 × 10⁻¹⁶ for all pair channels through flux 15. The quadrature agreement is 1.8 × 10⁻¹³. An independent Slater–Condon reconstruction agrees with the many-body matrices to 4.5 × 10⁻¹⁶ through N = 4. The V₁ parent has a unique singlet zero mode for all supported N = 2,…,6.

The dedicated solution suite contains 14 passing tests. It covers the pair normalization, two-electron spectrum, rotation commutator, Laughlin zero mode, coordinate equivariance, exchange sign, stable lowering, supported size validation, shared-network finite-difference gradient, exact-node gradients, toy-system stochastic convergence, IID energy SE, and the normal command-line entry point. The harness regression suite gives 235 passed and 9 skipped in the local environment.

The benchmark used Python 3.13.14, NumPy 2.5.4, SciPy 1.18.1, SymPy 1.14.0, and Matplotlib 3.11.2. Direct dependencies are pinned in `requirements.txt`. The three system runs took approximately 1.3, 1.7, and 3.2 seconds after imports on the local Apple Silicon machine. The largest dense Hamiltonian has 338² double entries, approximately 0.91 MB. Intermediate angular-momentum matrices and the five M blocks also fit comfortably in local memory.

`results/summary.json` is the source for the generated figure and all reported numerical diagnostics. Raw results and checkpoints stay Git-ignored under the harness rules. The runnable code and this report are committed. The figure command generates a left panel with MC gaps and ED references, and a right panel with 10¹²(E₂,ᴹ−E₂,₂) for the five magnetic components. MC bars are smaller than the marker size on the gap scale. The multiplet panel resolves numerical roundoff.

## Scope and remaining research work

This submission supplies a documented antisymmetric and SO(3)-equivariant NQS, actual stochastic training, MC energy estimates with sampling errors, the finite-size neutral gaps, and explicit L = 2 multiplet checks. The exact angular-momentum basis, Hamiltonian construction, direct Born sampler, and checkpoint monitoring all retain exponential finite-basis costs. The benchmark is limited to N ≤ 6.

Thermodynamic extrapolation remains unresolved with these three small systems, whose gaps already show nonmonotonic finite-size variation. Helicity −2 also remains unmeasured. That requires a specified chiral metric operator and its spectral weights in addition to the total-angular-momentum certification. Liou et al. study these chiral operator responses and distinguish the Coulomb case from the model pseudopotential Hamiltonian. [Liou et al., Phys. Rev. Lett. 123, 146801 (2019)](https://arxiv.org/abs/1904.12231)
