<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Variational Monte Carlo & Neural Quantum States (VMC-NQS)

Parameterized-wavefunction ansatz sampled with Monte Carlo; energy minimized by stochastic reconfiguration or natural-gradient descent — sign-immune, no sign problem.

## Method card

### What it is

VMC-NQS represents the many-body wavefunction as a parameterized ansatz (Jastrow, RBM, deep network, transformer…) and evaluates the energy expectation value by Monte Carlo sampling of the amplitude distribution `|ψ_θ(x)|²`. The energy and its gradient are estimated from `N_s` samples; parameters θ are updated by stochastic reconfiguration (SR) / natural gradient — equivalent to imaginary-time evolution projected onto the ansatz manifold. Neural quantum states (NQS) use expressive deep networks as the ansatz, enabling in principle arbitrary entanglement structure. The method returns a variational upper bound on the ground-state energy together with all expectation values computable from the sampled wavefunction.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | GS energy (variational upper bound) · variational observables (correlations, structure factors, order parameters) · excited states via symmetry sectors or energy-penalty methods · real-time dynamics via time-dependent VMC (t-VMC, extra cost, growing error) | Gives an upper bound only — pair with PolyOpt/SDP for a rigorous energy bracket. |
| M2 regime | T=0 (ground state); real-time via t-VMC | Finite-T via VMC sampling of the thermal density matrix is possible but non-standard. |
| M3 accuracy class | Variational upper bound, stochastic | Statistical error bars `∝1/√N_s`; bias set by ansatz expressiveness (uncontrolled but variational — cannot go below the true GS). |
| M4 dimension fit (A1) | Any dimension (1D, 2D, 3D) | No geometric constraint — the key advantage over tensor-network methods in 2D/3D. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion (with sign structure in ansatz) | Fermions require encoding the sign/phase structure in the ansatz; large local dim `d` raises `c_eval` but does not cause an exponential wall. |
| M6 entanglement regime (B5) | Volume-law tolerated (no bond-dimension wall) | NQS can in principle represent volume-law states; quality depends on the ansatz, not a hard truncation. |
| M7 sign-problem dependence (C12) | Sign-immune | No sign problem — the sign/phase is encoded in the (complex) ansatz amplitude. Thrives where QMC fails: B8 frustration, C12 sign-ful, 2D. |
| M8 symmetry exploitation (C9/C10) | U(1), SU(2), translation, point-group can be imposed as constraints on the ansatz or via symmetry-projected sampling | Symmetry projection reduces variance and targets correct quantum-number sectors. |
| M9 time complexity | `O(N_s·c_eval)` per optimization step; SR/natural-gradient adds `O(N_p²)`–`O(N_p³)` (exact) or `O(N_s·N_p)` (iterative/minSR) | `c_eval` = amplitude + local energy cost (`O(N)`–`O(N²)` Jastrow/RBM; network forward pass for deep NQS). |
| M10 memory | `O(N_p)` for parameters + `O(N_s·N_p)` for the SR matrix (or `O(N_s)` minSR) | Deep-network ansätze can have `N_p ~ 10⁴`–`10⁶`; SR matrix can dominate memory. |
| M11 control knob | `N_s` (samples per step) → statistical error `∝1/√N_s`; ansatz size / depth → ansatz bias | No single knob fully controls the variational bias — convergence studies vary ansatz architecture. |
| M12 scale frontier | Thousands of sites feasible with shallow RBM/Jastrow; hundreds of sites with deep NQS; thermodynamic limit via ansatz in the TD limit | Scales far beyond ED/FCI; quality limited by ansatz not system size. |
| M13 primary approximation / bias | Ansatz bias — variational error is set by the expressiveness of the chosen ansatz (uncontrolled but variational) | Cannot go below the true GS; paired with a lower bound (SDP/PolyOpt) it brackets the energy. |
| M14 hard blocker / failure mode | Optimization landscape (local minima, barren plateaus for deep networks); autocorrelation in MC sampling; SR matrix ill-conditioning | Real-time t-VMC accumulates gauge error; strongly correlated regimes with poor ansatz overlap fail quietly (low-quality local minimum). |

### Cost & scaling

- Time: `O(N_s·c_eval)` per optimization step; SR adds `O(N_p²)`–`O(N_p³)` or `O(N_s·N_p)` with minSR
- Memory: `O(N_p)` parameters; `O(N_s·N_p)` SR matrix (dominant for large `N_p`)
- Control knob: `N_s` (sample size → statistical error `∝1/√N_s`); ansatz depth/width → variational bias
- Scale frontier: thousands of sites (shallow); hundreds (deep NQS); thermodynamic limit possible

### Accuracy & guarantees

- Class: variational upper bound, stochastic
- Primary approximation & its control: ansatz bias; improved by increasing expressiveness (deeper network, larger hidden layer ratio); no systematic convergence parameter for the bias
- Error scaling: statistical part `∝1/√N_s`; variational part converges only if the ansatz family contains the true GS

### Tasks it computes

- Ground-state energy and wavefunction (variational upper bound)
- Expectation values of observables (correlation functions, structure factors, order parameters)
- Excited states: symmetry-sector targeting (run in each sector separately); energy-penalty methods
- Real-time dynamics: time-dependent VMC (t-VMC) — extra computational cost, growing gauge error
- Entanglement entropies from sampled wavefunction (via replica trick or direct estimators)

### Recommended for (models / regimes)

- **Frustrated magnets (B8) and doped Mott insulators (D14):** where SSE/DQMC/worldline QMC fail due to the sign problem; NQS provides a sign-immune upper bound
- **2D/3D systems:** where MPS bond-dimension wall is prohibitive but exact methods are out of reach
- **Benchmarking against AFQMC:** VMC-NQS upper bound + AFQMC constrained energy validates phaseless approximation quality
- **Upper-half of a rigorous energy bracket:** pair with `/method-polyopt` (SDP lower bound) to bracket the GS energy rigorously
- Per `method-property-map.md`: recommended when C12 sign-ful AND A1 2D/3D AND need variational upper bound

### Key reference

[@carleo_2016_solving] — founding NQS paper demonstrating RBM wavefunction solves frustrated 1D/2D spin models with high accuracy; the standard entry-point reference.
Rendered: `../../literature/variational-monte-carlo-neural-quantum-states/1606.02318_solving-the-quantum-many-body-problem-with-artificial-neural.md` _(reused)_.

[@sorella_1998_green] — introduces Green Function Monte Carlo with stochastic reconfiguration; foundational for the SR/natural-gradient optimizer used in VMC.
Rendered: `../../literature/variational-monte-carlo-neural-quantum-states/cond-mat-9803107_green-function-monte-carlo-with-stochastic-reconfiguration.md` _(reused)_.

### Benchmarks

- RBM VMC on frustrated J₁-J₂ Heisenberg chain (`N=80`, `J₂/J₁=0.5`): energy within 0.1% of DMRG [@carleo_2016_solving].
- SR optimizer convergence: stochastic reconfiguration outperforms gradient descent by orders of magnitude in optimization efficiency [@sorella_1998_green].

## How it is used / Operational

**Owning skill:** `/method-vmc` (primary), with tool skill `/using-netket` (NetKet framework for NQS).

**Default workflow:**
1. Choose ansatz architecture (RBM, CNN, transformer) and symmetry constraints (U(1), translation).
2. Initialize parameters; run MC sampling to estimate `E_loc` and the SR matrix `S`.
3. Update parameters via SR: `θ ← θ − η S⁻¹ ∇E` (regularized, `λ` diagonal shift).
4. Monitor energy convergence; vary `N_s` and ansatz size for convergence study.
5. Cross-check GS energy against ED (small `N`) or DQMC (sign-free regime) as oracle.

**Verification pointers:**
- GS energy must be an upper bound: verify `E_VMC ≥ E_ED` on small clusters.
- For frustrated regimes where no oracle exists, pair with PolyOpt SDP lower bound to bracket the truth.
- Check variance of local energy → 0 at convergence (zero variance property: `Var[E_loc]=0` iff `ψ` is an exact eigenstate).

**Cross-links:**
- Survey: `method-survey.md` §4.1 (Variational Monte Carlo & neural quantum states)
- Model↔method gate: `method-property-map.md` (VMC/NQS profile)
- Complementary methods: `/method-polyopt` (SDP lower bound for rigorous bracket); DQMC/AFQMC for fermions in sign-free regimes; ED oracle for small systems
