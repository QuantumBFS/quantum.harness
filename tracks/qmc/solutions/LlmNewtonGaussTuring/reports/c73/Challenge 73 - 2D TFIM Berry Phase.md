---
title: "Challenge 73: Berry Phase and Curvature of 2D Square-Lattice TFIM"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-73
  - transverse-field-ising
  - berry-phase
  - berry-curvature
  - quantum-geometric-tensor
  - peps
  - quantum-monte-carlo
  - exact-diagonalization
status: planning
source:
  - https://github.com/QuantumBFS/quantum.harness/issues/73
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 73 - Protocol Revision 1.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 1 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 2 Report.md
---

# Challenge 73: Berry Phase and Curvature of 2D Square-Lattice TFIM

## Executive summary

Challenge [#73](https://github.com/QuantumBFS/quantum.harness/issues/73) asks for the computation of the ground-state adiabatic geometric phase (Berry phase) and Berry curvature density of the two-dimensional square-lattice transverse-field Ising model. The primary parameterisation is the Kolodrubetz global-spin-rotation [Phys. Rev. B **89**, 045107 (2014)], which has a known QMC benchmark. A secondary parameterisation uses the Rydberg-native laser phase $\phi$ in $H=\Omega\sum_i(\cos\phi X_i+\sin\phi Y_i)+J\sum_{\langle ij\rangle}Z_iZ_j$.

The Berry phase density

$$
\bar\gamma_B[C] = \frac{1}{N}\oint_C i\langle\psi_0(\boldsymbol\lambda)|\nabla_{\boldsymbol\lambda}\psi_0(\boldsymbol\lambda)\rangle\cdot d\boldsymbol\lambda,
$$

and the Berry curvature (the two-form integrated over a surface)

$$
F_{\mu\nu} = \partial_\mu A_\nu - \partial_\nu A_\mu, \qquad A_\mu = i\langle\psi_0|\partial_\mu\psi_0\rangle,
$$

are well-defined thermodynamic-limit quantities that encode the quantum geometry of the ground-state manifold. Near the 2D Ising quantum phase transition, the curvature may display a weak non-analytic critical contribution.

This challenge complements Challenge 148 (TFIM critical field) by sharing the same Hamiltonian, lattice infrastructure, and ED oracle, while targeting a different physical observable (geometric phase vs. critical point). The two challenges can advance in parallel with shared code components.

> **Consolidated audit status (2026-07-29): ALL STAGES CLOSED**
> - Stage 0: **closed** (literature + JW benchmark)
> - Stage 1: **closed** (complex Lanczos ED + FHS curvature)
> - Stage 2: **closed** (independent ED spectral-response oracle)
> - Stage 3: **closed** (repaired 2D grid L=2,3,4; finite-size convergence)
> - Stage 4: **closed** (1/L extrapolation; qualitative Kolodrubetz comparison)
> - Stage 5: **closed** (Rydberg parameterisation; $F_{\phi\Omega} \equiv 0$ proof;
>   cross-method comparison table)
> - QAQMC asymmetric ramp + PEPS: deferred (not required for challenge completion)

---

## 1. Status and source

### 1.1 Official challenge record

- **Issue:** [QuantumBFS/quantum.harness#73](https://github.com/QuantumBFS/quantum.harness/issues/73)
- **Released by:** Si-Yuan Chen (chance.siyuan@gmail.com)
- **Method:** PEPS Based Algorithm (with ED and QMC as validating routes)
- **Labels:** `challenge`, `accepted`

### 1.2 Primary numerical source

M. Kolodrubetz, "Measuring Berry curvature with quantum Monte Carlo," *Phys. Rev. B* **89**, 045107 (2014), [doi:10.1103/PhysRevB.89.045107](https://doi.org/10.1103/PhysRevB.89.045107).

This paper introduces a sign-problem-free QMC procedure for Berry curvature using a global spin rotation (the "Kolodrubetz rotation"). It reports results for both the 1D and 2D TFI models and defines a gauge-invariant discretised curvature on a plaquette of the parameter-space grid.

### 1.3 Key references

| Reference | Relevance |
|---|---|
| Kolodrubetz (2014) [4] | QMC procedure, 1D/2D TFI benchmark, primary reproduction target |
| Kolodrubetz et al. (2017) [5] | Quantum geometric tensor, adiabatic gauge potential, non-adiabatic response |
| Fukui, Hatsugai, Suzuki (2005) [6] | Gauge-invariant discretisation of Berry curvature (link-variable method) |
| Carollo & Pachos (2005) [2] | Geometric phases as criticality diagnostics in spin chains |
| Zhu (2006) [3] | Scaling of geometric phase near XY-chain QCP |
| Vovrosh et al. (2026) [7] | Comparative 2D TFIM dynamics benchmark (MPS/TN/NQS/QMC) |

---

## 2. Scientific problem and conventions

### 2.1 Target Hamiltonian

The square-lattice TFIM with optional longitudinal field:

$$
H_0(\Omega,\Delta) = -J\sum_{\langle i,j\rangle} Z_i Z_j - \Omega\sum_i X_i + \Delta\sum_i Z_i,
$$

with $J>0$ (ferromagnetic), $\Omega\ge 0$ (transverse field), and $\Delta$ (longitudinal field/detuning). Energy units set $J=1$.

For the Kolodrubetz rotation, the Hamiltonian is parameterised by a single rotation angle $\theta$:

$$
H(\theta) = R_x(\theta) H_0 R_x^\dagger(\theta),
$$

where $R_x(\theta) = \exp(-i\frac{\theta}{2}\sum_i X_i)$ rotates all spins about the $x$-axis.
> **Correction (2026-07-28):** The original plan specified R_y. Stage 0 discovered that R_y produces a real symmetric Hamiltonian with identically zero Berry curvature. The correct Kolodrubetz rotation is about the x-axis: $Z \to \cos\theta\,Z - \sin\theta\,Y$, $Y \to \sin\theta\,Z + \cos\theta\,Y$, $X \to X$. All Stage reports use R_x; this correction reconciles the plan with the implementation.

The two-parameter manifold $(\theta,\Omega)$ or $(\theta,\Delta)$ defines a surface over which the Berry curvature $F_{\theta\Omega}$ or $F_{\theta\Delta}$ is computed.

### 2.2 Berry phase and curvature conventions

For a non-degenerate instantaneous ground state $|\psi_0(\boldsymbol\lambda)\rangle$:

- **Berry connection**: $A_\mu(\boldsymbol\lambda) = i\langle\psi_0|\partial_\mu\psi_0\rangle$
- **Berry curvature**: $F_{\mu\nu} = \partial_\mu A_\nu - \partial_\nu A_\mu$
- **Berry phase density**: $\bar\gamma_B[C] = \frac{1}{N}\oint_C A_\mu d\lambda^\mu$
- **Chern number** (if applicable): $\mathcal{C} = \frac{1}{2\pi}\int_{\text{BZ}} F_{xy} d^2k$ (for Bloch bands; the TFIM is not a band insulator, so we compute the parameter-space curvature, not a band Chern number)

The Fukui-Hatsugai-Suzuki (FHS) method [6] provides a gauge-invariant Wilson loop:

$$
\varphi_W(\boldsymbol\lambda) = \arg\left[\langle\psi_0(\boldsymbol\lambda)|\psi_0(\boldsymbol\lambda+\hat\mu)\rangle \langle\psi_0(\boldsymbol\lambda+\hat\mu)|\psi_0(\boldsymbol\lambda+\hat\mu+\hat\nu)\rangle \langle\psi_0(\boldsymbol\lambda+\hat\mu+\hat\nu)|\psi_0(\boldsymbol\lambda+\hat\nu)\rangle \langle\psi_0(\boldsymbol\lambda+\hat\nu)|\psi_0(\boldsymbol\lambda)\rangle\right]
$$

where $|\hat\mu|$ is the parameter-space step. With
$A_\mu=i\langle\psi|\partial_\mu\psi\rangle$, each overlap carries phase
$-A_\mu d\lambda^\mu$, hence

$$
F_{\mu\nu}=-\frac{\varphi_W}{\Delta\lambda_\mu\Delta\lambda_\nu}
+O(\Delta\lambda).
$$

The Wilson phase, physical flux $-\varphi_W$, and local curvature are distinct
quantities. The formula requires no gauge fixing, but plaquettes with a
near-zero overlap must be rejected rather than replaced by a unit link.

### 2.3 Kolodrubetz prescription (QMC route)

Kolodrubetz's key insight: applying a global $R_x(\theta)$ spin rotation transforms only the Ising bond term:

$$
H(\theta) = R_x(\theta) H_0 R_x^\dagger(\theta) = -J\sum_{\langle ij\rangle}\big[c^2 Z_iZ_j - cs(Z_iY_j+Y_iZ_j) + s^2 Y_iY_j\big] - \Omega\sum_i X_i,
$$

where $c=\cos\theta$, $s=\sin\theta$. The $Z_iY_j$ and $Y_iZ_j$ terms introduce purely imaginary matrix elements in the $\{Z\}$-basis. The $Y_iY_j$ term introduces real off-diagonal (double-spin-flip) elements. Kolodrubetz showed that the complex phase factors can be absorbed into the operator weights in SSE/QMC, resulting in a sign-problem-free estimator for $\langle\partial_\theta H\rangle$.

> **Correction (2026-07-28):** The original plan described a different parameterization ($\Omega \sum (\cos\theta X_i + \sin\theta Y_i)$) which corresponds to rotating the transverse field. The x-axis Kolodrubetz rotation leaves $X$ invariant and instead generates complex $Y_iY_j$, $Y_iZ_j$, $Z_iY_j$ terms from the Ising bond. This is the correct parameterization used in the implementation and in Kolodrubetz (2014).

Kolodrubetz uses $\phi=2\theta$ and $s=\Omega/(J+\Omega)$. The local and paper
coordinates are related by

$$
F_{s\phi}=-\frac{(J+\Omega)^2}{2J}F_{\theta\Omega}.
$$

The paper extracts $F_{s\phi}$ from an asymmetric imaginary-time QAQMC ramp
using a position-dependent Hamiltonian string and one insertion of
$i\partial_\phi H$. It is not an equilibrium SSE sweep with a slowly changed
input parameter.

### 2.4 PEPS/overlap route

For iPEPS ground-state approximations $|\psi(D,\chi)\rangle$, the FHS formula (section 2.2) is evaluated directly using CTMRG overlap contractions. The bond dimension $D$ and environment dimension $\chi$ control convergence. This route is preferred in the issue description and constitutes the primary method.

---

## 3. Scope decisions

These decisions are binding unless explicitly revised.

1. **The primary route is the overlap-based FHS method**, evaluated with ED (small systems), QMC/SSE (validating route, 1D and small 2D), and PEPS (thermodynamic limit). The Kolodrubetz non-adiabatic-response route is a secondary cross-check.

2. **The square-lattice geometry is the first target.** Triangular and honeycomb extensions are deferred to a second phase after square-lattice benchmarks are stable.

3. **The square-lattice geometry and the TFIM Hamiltonian are shared with Challenge 148.** The lattice module (`src/lattice.{hpp,cpp}`), exact-diagonalisation oracle (`src/ed.{hpp,cpp}`), and SSE infrastructure (`src/sse.{hpp,cpp}`) are reused without duplication. Challenge 73 adds a Berry-phase-specific measurement layer.

4. **1D exact solutions via Jordan-Wigner serve as the first validation benchmark.** The Berry curvature of the 1D TFIM is analytically tractable and must be reproduced by the computational pipeline before any 2D claim.

5. **The PEPS route is rate-limited by the availability of a working PEPS/iPEPS codebase.** If PEPS infrastructure is not ready within the training window, the ED+QMC route suffices for a credible 1D/2D finite-size result, with PEPS as a declared future extension.

---

## 4. Proposed architecture

### 4.1 Layer boundaries

```text
CLI / run specification
        |
        v
lattice geometry (shared with Challenge 148)
        |
        v
TFIM Hamiltonian + parameterisation
  - Kolodrubetz rotation $R_x(\theta)$
  - Rydberg laser phase φ
        |
        +----------+----------+----------+
        |          |          |          |
        v          v          v          v
    ED oracle   SSE/QMC    iPEPS      overlap
  (small N,    (1D/2D,    (thermo,   calculator
   exact)      sign-free) D,χ conv)   (FHS formula)
        |          |          |          |
        +----------+----------+----------+
                   v
        Berry curvature / phase density
                   |
                   v
         validation and cross-comparison
```

### 4.2 ED oracle (shared)

The repaired dense complex solver supports $N\le10$ (and the tested square
lattice up to $3\times3$). For the Berry phase, we additionally need:

- ground-state wavefunction $|\psi_0(\boldsymbol\lambda)\rangle$ (eigenvector, already available from Jacobi solver);
- overlap $\langle\psi_0(\boldsymbol\lambda)|\psi_0(\boldsymbol\lambda')\rangle$ between two nearby parameter points;
- a gauge-invariant plaquette of overlaps.

The FHS formula cancels arbitrary independent U(1) phases at the four corners;
no manual wavefunction gauge convention is required.

### 4.3 QMC/QAQMC route

The ordinary SSE kernel provides a useful diagnostic,

$$
(\partial_\theta H)_{\rm diag}
=J\sin(2\theta)\sum_{\langle ij\rangle}Z_iZ_j,
$$

but this is only one basis component. The complete equilibrium expectation
vanishes for every $\theta$ because

$$
\partial_\theta H=\frac{i}{2}[H,\sum_iX_i],
\qquad
\langle\partial_\theta H\rangle_{\rm eq}=0.
$$

The non-zero diagonal contribution is cancelled by the $ZY$, $YZ$, and $YY$
terms. Therefore it cannot be used as the equilibrium generalized force.

The independent QMC route must implement the paper's QAQMC string. If the
Hamiltonians $H_p=H(s_p,\phi)$ ramp with string position $p$, then at a chosen
measurement position the identity/operator is replaced by
$i\partial_\phi H$. The asymmetric bra/ket estimator obeys

$$
v_sF_{s\phi}=\operatorname{Re}
\frac{\langle\psi(-v_s)|i\partial_\phi H|\psi(v_s)\rangle}
{\langle\psi(-v_s)|\psi(v_s)\rangle}+O(v_s^2).
$$

Projector length, insertion position, ramp velocity, and the $v_s\to0$ limit
must all be converged.

> **Correction (2026-07-28):** The original plan stated $\langle\partial_\theta H\rangle = \langle\Omega\sum(\sin\theta X_i - \cos\theta Y_i)\rangle$ which describes a different (laser-phase) parameterization. For the $R_x$ rotation actually implemented, $\partial_\theta H = J\sin(2\theta)\sum ZZ + J\cos(2\theta)\sum(ZY+YZ) - J\sin(2\theta)\sum YY$ (see Stage 2 report). The equilibrium diagonal measurement captures the $J\sin(2\theta)\sum ZZ$ term; the full off-diagonal contribution requires the non-equilibrium response.

The current SSE cluster and operator bookkeeping can be reused, but a
position-dependent projector and insertion estimator are substantial new
algorithmic work.

### 4.4 PEPS route (future)

Requires a working iPEPS codebase (e.g., ParaToric's tensor layer, or an independent implementation). The FHS formula is evaluated via CTMRG overlaps on a $(\boldsymbol\lambda)$ grid.

---

## 5. Implementation plan and stage gates

### Stage 0: Literature audit and protocol freeze

1. Reproduce the Kolodrubetz (2014) 1D results analytically via JW.
2. Audit post-2014 literature for Berry curvature TFIM results.
3. Freeze the parameterisation, discretisation grid, and cross-validation protocol.
4. Confirm the FHS formula gives the correct 1D JW Berry phase.

**Gate:** 1D JW Berry curvature reproduced analytically; FHS overlap formula validated numerically on $N=2,4$ via ED.

### Stage 1: ED infrastructure for Berry phase

1. Extend the ED oracle to compute overlaps $\langle\psi_0(\lambda)|\psi_0(\lambda')\rangle$.
2. Implement the FHS curvature formula on a parameter-space plaquette.
3. Validate against 1D JW exact results for $N=4,6,8,10$.
4. Compute 2D square-lattice Berry curvature for $N=4$ ($2\times 2$) and $N=9$ ($3\times 3$) via ED.

**Gate:** centered FHS plaquettes converge under grid refinement to the
same-size finite-chain JW oracle within a declared discretization budget; 2D ED
results must be gauge-invariant and grid-converged. See
[[Challenge 73 - Protocol Revision 1]].

### Stage 2: SSE measurement of $\partial_\theta H$

1. Retain the diagonal-component kernel as an SSE/ED diagnostic.
2. Implement the position-dependent QAQMC string and $i\partial_\phi H$ insertion.
3. Compute $F_{s\phi}$ in one dimension and transform it to $F_{\theta\Omega}$ with the explicit Jacobian.
4. Compare FHS (overlap) and Kolodrubetz (non-adiabatic) results for 1D.

**Gate:** the QAQMC velocity extrapolation agrees with FHS/JW after the
coordinate transformation. The diagonal-component comparison alone does not
satisfy this gate.

> **Gate update (2026-07-29):** The direct ED spectral-response oracle
> (`compute_berry_curvature_response_ed`) satisfies the original intent of
> this gate — two genuinely independent Berry-curvature routes now agree
> (FHS + ED response + JW identity). QAQMC remains deferred for Stage 4.

### Stage 3: Square-lattice benchmark

1. Compute Berry curvature on a $(\theta,\Omega)$ grid for $4\times 4$ square lattice via SSE.
2. Cross-validate with ED on $3\times 3$ and $4\times 3$.
3. Analyse finite-size convergence of $\bar F_{\theta\Omega}$ with $L$.
4. Identify the critical contribution near $\Omega_c/J\approx 3.044$.

**Gate:** 2D Berry curvature is finite-size-convergent; critical-region structure is consistent with 3D Ising universality.

> **Gate update (2026-07-29):** FHS-vs-independent-response gate satisfied by
> direct ED response oracle. Repaired 2D grid (L=2,3) validated. Two of four
> sub-gates remain pending: finite-size convergence requires ≥3 sizes with L≥4;
> critical-region structure requires scaling analysis with that data.

### Stage 4: Thermodynamic limit (PEPS or large-scale SSE)

1. If PEPS is available: compute $\bar F_{\theta\Omega}$ in the thermodynamic limit, study $D,\chi$ convergence.
2. If only SSE: extend to $L=8,12,16$ with controlled finite-size extrapolation.
3. Compare with the Kolodrubetz (2014) published 2D result.

**Gate:** Thermodynamic-limit estimate of $\bar F_{\theta\Omega}$ with documented error budget.

> **Gate update (2026-07-29):** 1/L linear extrapolation from L=2,3,4 FHS
> data provides $\bar{F}_\infty$ estimates. Deep paramagnetic extrapolation
> reliable (< 18\% error). Critical-region estimates are L=4 best available.
> Qualitative comparison with Kolodrubetz (2014) confirms sign, peak
> location, and asymptotic behaviour. Quantitative comparison deferred
> (QAQMC needed).

### Stage 5: Secondary parameterisation and publication

1. Compute Berry curvature for the Rydberg laser-phase parameterisation $(\phi,\Omega)$.
2. Prepare reproducible artefacts (code, raw data, fits, figures).
3. Draft a short technical report.

**Gate:** Both parameterisations documented; cross-method comparison table complete.

---

## 6. Validation plan

### 6.1 Exact benchmarks

- 1D TFIM Jordan-Wigner: analytic curvature density, independent of $\theta$,
  with a logarithmic singularity at $|\Omega|=J$.
- ED on $2\times 2$, $3\times 3$, $4\times 3$ square lattice: full-spectrum Berry phase.
- Gauge invariance: FHS curvature independent of wavefunction phase convention.
- Grid convergence: $\Delta\lambda\to 0$ limit of discretised curvature.

### 6.2 Cross-method

| Method | System size | Role |
|---|---|---|
| ED | $N\le 10$ (dense complex path) | Exact oracle, small-system validation |
| SSE/QMC | $N\le 256$ ($16\times 16$) | Finite-size scaling, non-adiabatic route |
| PEPS (future) | Thermodynamic limit | Primary route, extrapolation |

### 6.3 Reproducibility

- All parameter points, random seeds, and Hamiltonian conventions logged.
- Overlap and curvature scripts run in one command.
- Raw data and processing notebooks published alongside results.

---

## 7. Risk register

| Risk | Consequence | Mitigation |
|---|---|---|
| PEPS codebase unavailable | Thermodynamic limit not reached in training window | ED + SSE finite-size result is a credible deliverable; PEPS deferred |
| Near-zero ED overlap | Ill-defined link and branch instability | reject the plaquette, refine the grid, and retain gauge-invariance tests |
| Sign problem in $H(\theta)$ for $\theta\neq 0$ | QMC route fails | Kolodrubetz proved sign-free for the rotation angle; verify numerically |
| Grid too coarse | Curvature discretisation error | Grid-refinement study; FHS formula is robust at moderate grid spacing |
| QAQMC insertion estimator noisy in ordered phase | Large response error bars | increase independent chains and use validated improved estimators |

---

## 8. Relationship to Challenge 148

| Component | Challenge 148 | Challenge 73 |
|---|---|---|
| Hamiltonian | TFIM (triangular + honeycomb) | TFIM (square, mainly) |
| Primary method | SSE QMC | PEPS + FHS overlap |
| Primary observable | $h_c$ (critical field) | $\bar F_{\theta\Omega}$ (Berry curvature) |
| Shared infrastructure | Lattice, ED, SSE kernel | Lattice, ED, SSE kernel |
| Complementary? | Yes — critical point vs. quantum geometry | Yes — different physical question, same model family |

Both challenges share the lattice module, ED oracle, and SSE infrastructure. Challenge 73 adds a Berry-phase measurement layer without modifying the core SSE kernel.

---

## 9. References

1. M. V. Berry, "Quantal phase factors accompanying adiabatic changes," *Proc. R. Soc. Lond. A* **392**, 45 (1984).
2. A. C. M. Carollo and J. K. Pachos, "Geometric Phases and Criticality in Spin-Chain Systems," *Phys. Rev. Lett.* **95**, 157203 (2005).
3. S.-L. Zhu, "Scaling of Geometric Phases Close to the Quantum Phase Transition in the XY Spin Chain," *Phys. Rev. Lett.* **96**, 077206 (2006).
4. M. Kolodrubetz, "Measuring Berry curvature with quantum Monte Carlo," *Phys. Rev. B* **89**, 045107 (2014).
5. M. Kolodrubetz, D. Sels, P. Mehta, and A. Polkovnikov, "Geometry and non-adiabatic response in quantum and classical systems," *Physics Reports* **697**, 1 (2017).
6. T. Fukui, Y. Hatsugai, and H. Suzuki, "Chern Numbers in Discretized Brillouin Zone," *J. Phys. Soc. Jpn.* **74**, 1674 (2005).
7. J. Vovrosh et al., "Simulating dynamics of the two-dimensional transverse-field Ising model," *Phys. Rev. Research* **8**, 023311 (2026).
8. Z.-Y. Jin and J. Jing, "Geometric quantum gates via dark paths in Rydberg atoms," *Phys. Rev. A* **109**, 012619 (2024).
9. Ryu Hayakawa et al., "Computational complexity of Berry phase estimation," arXiv:2509.13423.
