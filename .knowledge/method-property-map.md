# Method ↔ Property Map

The link between numerical methods and the model properties defined in
`.knowledge/model-property-checklist.md` (axes referenced as A1–D16). Three views:

1. **Per-method profile** — for each method, the property values that make it
   applicable, the ones that block or inflate it, and its key cost lever.
2. **Property → method gate** — for each property value, which methods it favors
   or rules out.
3. **Quick reference** — the consensus "which method when" table + decision
   heuristic.

Methods (harness skills): **ED** · **MPS** (DMRG/TEBD/TDVP) · **PEPS** (2D TN) ·
**QMC** (SSE / AFQMC-DQMC) · **VMC**/NQS · **MF**/HF · **LTRG** (finite-T TN) ·
**MCRG** (critical exponents) · **QCS** (circuit sim) · **PolyOpt** (certified
bounds, NCTSSOS).

---

## 1. Per-method profile

### ED — Exact Diagonalization (`method-ed`)
- **Applicable when:** small `N` (Hilbert dim ≲ 10⁷–10⁸ after symmetry); any
  A1 dimension/geometry; need full spectrum, excited states, level statistics, or
  exact finite-cluster dynamics. The universal cross-check / oracle.
- **Helped by:** C9, C10 (block-diagonalize sectors — the biggest free win);
  small A3 `d`.
- **Blocked / expensive by:** large `N` and large A3 `d` (the `d^N` wall);
  thermodynamic limit (finite cluster only).
- **Cost lever:** symmetry-reduced block dimension; number of eigenpairs.

### MPS — DMRG / TEBD / TDVP (`method-mps`)
- **Applicable when:** A1 1D or quasi-1D; B5 area law or area+log; B6 gapped
  (cheap) or 1D-critical (χ-hungry but converges); D13 ground state, finite-T
  (purification/METTS), or short-time dynamics. Near-exact in 1D.
- **Helped by:** C9 U(1)/SU(2) (quantum-number-conserving tensors).
- **Blocked / expensive by:** A1 wide-2D / 3D (cut entanglement `∝ W` →
  `χ ∼ e^{cW}`, the "2D wall"); B5 volume law; A4 long-range (TEBD fails, use
  TDVP); D13 long-time real-time (`χ ∼ e^t`, the entanglement barrier).
- **Cost lever:** bond dimension `χ` (cost `∝ d·χ³` per site).

### PEPS — 2D tensor networks (`method-peps`)
- **Applicable when:** A1 2D; B5 2D area law; D13 ground state; classical
  partition functions. Built to satisfy the 2D area law at fixed bond dimension.
- **Blocked / expensive by:** A1 1D (MPS is better); exact contraction is
  #P-hard → approximate via CTMRG/boundary-MPS; D13 dynamics.
- **Cost lever:** virtual bond `D`, environment bond `χ_env`.

### QMC — SSE / AFQMC-DQMC (`method-qmc`)
- **Applicable when:** C12 sign-free (B8 unfrustrated, C9 particle-hole at
  half-filling, A3 spins/bosons); large `N`; D13 finite-T and ground state.
  Numerically exact at scale when sign-free.
- **Blocked / expensive by:** C12 sign-ful (B8 frustration, D14 doping, D13
  real-time). Workaround = constrained-path / phaseless AFQMC (controlled but
  *biased*).
- **Cost lever:** samples / sweeps / walkers; inverse temperature `β`.

### VMC / NQS — variational & neural quantum states (`method-vmc`)
- **Applicable when:** B8 frustrated or C12 sign-ful regimes where QMC is blocked
  and tensor networks are geometry-biased; A1 2D; comparing ansatz families.
  Variational **upper** bound with stochastic error bars.
- **Blocked / expensive by:** need for rigorous **lower** bounds (use PolyOpt);
  A1 1D (MPS cheaper/more accurate); small clusters (ED is exact); non-convex
  optimization (local minima).
- **Cost lever:** ansatz size / architecture; samples per step; optimization steps.

### MF / HF — mean field (`method-mf`)
- **Applicable when:** fast baseline / phase-diagram sketch; A1 high-dimension or
  large `Z` (fluctuation corrections `∼ 1/Z`); seeding trial states for correlated methods.
- **Blocked / expensive by:** A1 1D (Mermin–Wagner → false transitions);
  B8 frustration; any need for correlation, entanglement, or fluctuations.
- **Cost lever:** SCF iterations (negligible compute).

### LTRG — finite-T tensor RG (`method-ltrg`)
- **Applicable when:** D13 finite-temperature thermodynamics (free energy,
  specific heat, susceptibility); A1 1D / quasi-1D / 2D. Sign-free even in 2D
  (maps `d`-dim quantum → `(d+1)`-dim classical tensor network).
- **Blocked / expensive by:** D13 ground state (use DMRG/PEPS); A1 3D; very low
  `T` (Trotter + truncation error accumulate; XTRG variant improves).
- **Cost lever:** Trotter step `τ` (error `∼ τ²`); retained SVD dimension `Dc`.

### MCRG — Monte Carlo renormalization group (`method-mcrg`)
- **Applicable when:** extracting **critical exponents** near a fixed point
  (B6 criticality); classical lattice spin models; any A1 dimension; large
  lattices near `T_c`.
- **Blocked / expensive by:** ground-state energies / non-critical observables;
  thermodynamic-limit observables (gives fixed-point exponents, not them).
- **Cost lever:** lattice size `L`; block-spin rule; operator basis size.

### QCS — quantum circuit simulation (`method-qcs`)
- **Applicable when:** parameterized circuits / VQE; differentiable circuit
  optimization; circuit-contraction benchmarking. Classical simulation only.
- **Blocked / expensive by:** large state vectors (`2^n` memory); hardware
  execution.
- **Cost lever:** qubit count `n`; circuit depth; Hamiltonian representation
  (dense vs Pauli-sum vs MPO).

### PolyOpt — certified bounds / NCTSSOS (`method-polyopt`)
- **Applicable when:** **certified lower bound** on ground-state energy
  (complements variational upper bounds); A1 1D/2D; any algebra (Pauli / fermion /
  boson / projector). Useful precisely in C12 sign-ful / frustrated regimes where
  you want rigor.
- **Helped by:** C9 symmetry (automatic block-diagonalization of the SDP).
- **Blocked / expensive by:** need for the wavefunction/entanglement (returns
  bounds + moments, not a state); A1 3D (SDP size explodes); thermodynamic limit;
  D13 finite-T.
- **Cost lever:** SDP relaxation order `d`; operator-basis range.

---

## 2. Property → method gate

### A1 Dimensionality & geometry
- 1D → **MPS** (near-exact); ED; sign-free QMC.
- quasi-1D (width `W`) → **MPS/iDMRG** cylinders up to `W ≈ 8–12`.
- 2D bipartite → sign-free **QMC**, **PEPS/iPEPS**, DMRG cylinders, LTRG (finite-T).
- 2D frustrated → **DMRG + PEPS + VMC** cross-checked (QMC sign-blocked) — hardest.
- 3D → QMC (sign-free), cluster-DMFT/DCA; DMRG/PEPS impractical.
- `Z → ∞` → **DMFT exact**; classical MF exact. High `Z` → MF accurate (corrections `∼1/Z`).

### A2 Boundary conditions
- cylinder → DMRG default; cost set by width `W` (`χ ∼ e^{cW}`).
- torus → needed for topological ground-state degeneracy; harder to contract.
- infinite → iDMRG / iPEPS / VUMPS (direct thermodynamic limit).

### A3 Statistics & local dim `d`
- fermion / anyon → QMC sign + fermionic-parity tensors (fPEPS) / fusion tensors.
- large `d` → raises ED `d^N` wall and MPS per-site cost (`∝ d·χ³`); bosons need
  converged `n_max`.

### A4 Interaction range
- long-range → area-law violation possible; needs many-term/exp-sum MPOs (TDVP,
  not TEBD); denser ED matrix.

### B5 Entanglement scaling
- area law → tensor networks cheap (**MPS/PEPS**).
- area + log (1D critical) → MPS with `χ ∼ L^{c/3}`; finite-entanglement scaling.
- volume law (excited / thermal / long-time) → tensor networks fail → **ED**
  (small), **QMC** (finite-T equilibrium), **VMC/NQS**.

### B6 Spectral gap
- gapped → cheap for MPS/PEPS (constant `χ`).
- gapless / critical → inflates `χ`, slows convergence; **MCRG** for exponents.

### B7 Order type
- SSB → measure order parameter (any method).
- SPT → entanglement-spectrum degeneracy / string order (**MPS** native).
- topological → minimally-entangled-state protocol + TEE + degeneracy
  (**DMRG** on cylinders / **ED** on torus).

### B8 Frustration
- geometric / fermionic → **QMC blocked** → **DMRG + VMC/NQS + ED**;
  **PolyOpt** for a rigorous bound.

### C9 / C10 Symmetry
- U(1)/SU(2)/Z₂/PH → block-diagonalize: biggest free win for **ED** and **MPS**;
  PH at half-filling → sign-free **QMC**; symmetry → smaller **PolyOpt** SDP.
- translation (k) / point group → `∼N×` **ED** reduction; irrep labels.

### C11 Integrability
- free-fermion / quadratic → **exact `O(N³)`** (no heavy numerics); benchmark.
- Bethe-ansatz → exact spectrum / TBA; analytic benchmark.
- non-integrable → full numerical machinery required.

### C12 Sign problem
- sign-free → **QMC** exact at large size (preferred).
- sign-ful → QMC blocked → **MPS / PEPS / VMC**; **PolyOpt** for certified bounds.

### D13 Regime
- ground state → MPS / PEPS / VMC / QMC / PolyOpt.
- finite-T → **LTRG**, MPS purification/METTS, thermal **QMC**, **DMFT**.
- real-time → short-time **TEBD/TDVP** (capped by `χ ∼ e^t`); QMC blocked
  (dynamical sign problem).

### D14 Filling / doping
- commensurate (half/integer) → Mott physics; bipartite Hubbard sign-free.
- doped → fermion sign problem returns → DMRG/PEPS/VMC + constrained-path QMC.

### D15 Disorder / MBL
- disorder → all methods × realization averaging.
- MBL → excited-state area law → **DMRG-X / MPS** reach long times.

### D16 Hermiticity
- non-Hermitian / open → vectorized density-matrix or quantum-trajectory methods;
  standard variational ground-state methods need reformulation.

---

## 3. Quick reference

### Which method when

| Method  | Dim          | Reachable size            | Regime                         | Hard blocker                          |
|---------|--------------|---------------------------|--------------------------------|---------------------------------------|
| ED      | any          | tiny (`d^N ≲ 10⁸`)        | GS + full spectrum + dynamics  | Hilbert space `d^N`                   |
| MPS     | 1D, quasi-2D | large 1D / narrow cylinder| GS, finite-T, dynamics         | 1D area law (entanglement / `χ`)      |
| PEPS    | 2D           | moderate                  | GS (finite-T harder)           | #P-hard contraction                   |
| QMC     | any          | large                     | GS + finite-T                  | sign problem                          |
| VMC/NQS | any          | large                     | GS (+dynamics)                 | variational / ansatz bias             |
| MF/HF   | any          | unlimited                 | baseline                       | neglects correlation & fluctuations   |
| LTRG    | 1D/2D        | large                     | finite-T thermodynamics        | ground state / 3D                     |
| MCRG    | any (class.) | large near `T_c`          | critical exponents             | non-critical / GS                     |
| QCS     | —            | `n` qubits (`2^n` memory) | variational circuits / VQE     | state-vector memory                   |
| PolyOpt | 1D/2D        | ~100 (1D) / 10×10 (2D)    | certified GS bounds            | 3D / SDP blow-up                      |
| DMFT*   | high / ∞-D   | infinite (local)          | finite-T, Mott, dynamics       | neglects spatial correlations         |

\*DMFT is referenced for completeness; not a standalone harness method skill.

### Decision heuristic

1. **Quadratic / Bethe-integrable (C11)?** → exact (`O(N³)` or BAE/TBA); use ED only to validate.
2. **Dimension (A1)?** 1D → MPS · 2D → PEPS / DMRG-cylinder / sign-free QMC · 3D / local correlations → (cluster-)DMFT · ∞-D → DMFT exact.
3. **Sign-free (C12)?** → QMC, exact at large size. Frustrated / doped / real-time → QMC blocked → MPS / PEPS / VMC.
4. **Entanglement regime (B5)?** area law → tensor networks · volume law → ED (small) / QMC (finite-T equilibrium) / VMC.
5. **Exploit symmetries (C9, C10) always** — block-diagonalization is the cheapest cost reduction.
6. **Topological order (B7)?** → minimally-entangled-state / cylinder protocol + TEE + entanglement-spectrum diagnostics; a unique-ground-state method alone won't characterize it.
7. **Need rigor?** variational **upper** bound (VMC) + certified **lower** bound (PolyOpt) bracket the true energy; cross-method agreement establishes ground truth.

---

## References

Eisert–Cramer–Plenio RMP (area laws, arXiv:0808.3773) · Calabrese–Cardy
(1D criticality, hep-th/0405152) · Hastings (1D area-law theorem, arXiv:0705.2024)
· Troyer–Wiese (sign problem NP-hard, cond-mat/0408370) · Li–Yao (sign-free
classes, arXiv:1805.08219) · Lieb–Wu (1D Hubbard) · Schollwöck (DMRG/MPS,
arXiv:1008.3477) · Orús (tensor networks, arXiv:1306.2164) · Georges et al.
(DMFT, RMP 68, 13) · Carleo–Troyer (NQS, Science 355, 602) · LeBlanc et al. /
Simons (2D Hubbard multi-method benchmark, arXiv:1505.02290).
