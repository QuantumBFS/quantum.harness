# Method Property Checklist

A taxonomy of the intrinsic properties of a quantum many-body (QMB) *computational
method*. Each property is a single axis you can read off a method; together they
say **what** the method computes, **where** it applies, **how much** it costs, and
**what** limits it.

This is the method-side companion to `.knowledge/model-property-checklist.md`
(the model axes A1–D16). The two are linked: a method's applicability axes
(M4–M8) are stated as gates on the *model* axes (A1, A3, B5, C12, C9/C10). The
inverse mapping — given a model, which method? — lives in
`.knowledge/method-property-map.md`; the per-method prose catalog (with cost
derivations and citations) is `.knowledge/method-survey.md`.

Use it as a per-method card: fill in the value for each axis M1–M14, then the card
states the recommended models/regimes. Cost symbols follow the
`method-survey.md` legend (`N` sites, `d` local dim, `D_H=d^N`, `D_blk` largest
symmetry block, `χ`/`D` bond dims, `χ_env` environment bond, `M` #moments,
`N_s` #samples, `N_w` #walkers, `β` inverse temp, `⟨s⟩` average sign, `k` SDP
level, `N_kept` retained states, `n` qubits, `N_p` #parameters, `N_c` cluster size).

---

## M-I. Capability — what the method computes

### M1 — Tasks / outputs
- **Values:** the quantities the method natively returns — ground-state energy ·
  full spectrum / level statistics · few excited states & gaps · finite-`T`
  thermodynamics · real-time dynamics · spectral / dynamical function
  `S(q,ω)`/`A(ω)` · critical exponents & CFT data · order parameters &
  correlations · entanglement entropy / spectrum · certified energy bounds.
- **Why it matters:** the first filter — a method that returns only a variational
  energy cannot give you a spectral function, and a critical-exponent extractor
  is not a ground-state solver. Match the task to the method before anything else.

### M2 — Regime
- **Values:** ground state (`T=0`) · finite temperature (thermal equilibrium) ·
  real-time dynamics. (The same three values as the model axis D13.)
- **Why it matters:** ground-state, thermal, and real-time each need different
  machinery; many methods cover only one (e.g. DMRG ground state vs TEBD dynamics
  vs purification finite-`T`). Real-time additionally triggers the entanglement
  barrier and the dynamical sign problem.

### M3 — Accuracy class & guarantee
- **Values:** numerically exact (within machine/statistical error) · variational
  **upper** bound · certified **lower** bound · controlled-bias (a systematically
  improvable approximation with a convergence parameter) · uncontrolled
  approximation. Orthogonally: **deterministic** vs **stochastic** (carries
  statistical error bars `∝1/√N_s`).
- **Why it matters:** sets what the number *means*. A variational energy is only an
  upper bound; pairing it with a certified lower bound (SDP) brackets the truth.
  An uncontrolled mean field can be qualitatively wrong with no internal warning.

---

## M-II. Applicability gates (keyed to the model axes A1–D16)

### M4 — Dimensionality / geometry fit (model A1)
- **Values:** 1D · quasi-1D (ladders / width-`W` cylinders) · 2D · 3D ·
  infinite-dimensional (`Z→∞`) · any; with a note on **where it wins** and
  **where it walls**.
- **Why it matters:** dimension is the master gate. MPS is near-exact in 1D and
  walls in 2D (`χ~e^{cW}`); PEPS is built for 2D; DMFT is exact only as `Z→∞`;
  sign-free QMC works in any dimension. The wrong-dimension method is the most
  common misapplication.

### M5 — Statistics & local dimension (model A3)
- **Values:** which statistics it supports — spin / hard-core boson / soft-core
  boson / fermion / anyon — and its sensitivity to the local dimension `d`
  (e.g. ED `d^N` wall; MPS per-site `∝d·χ³`; NRG `N_kept`↑ with #channels).
- **Why it matters:** fermions reintroduce the sign (QMC) or need parity tensors
  (fPEPS); large `d` (spin-1, Hubbard `d=4`, soft-core bosons) shrinks ED reach
  and raises tensor-network cost.

### M6 — Entanglement regime handled (model B5)
- **Values:** area-law only · area+log (1D critical, `χ` grows polynomially) ·
  volume-law: no hard entanglement gate (ED is the exact full-Hilbert
  representation; sign-free QMC has no entanglement restriction; VMC/NQS impose no
  bond-dimension wall **but** carry an ansatz bias that can be large for generic
  volume-law states).
- **Why it matters:** the decisive gate for tensor networks — required bond
  dimension `χ≳e^S`. Volume-law (generic excited, thermal, long-time) states push
  you off tensor networks onto ED (small), equilibrium QMC, or VMC/NQS.

### M7 — Sign-problem dependence (model C12)
- **Values:** requires sign-free (Monte Carlo blocked otherwise) · controls the
  sign by a (biased) constraint (fixed-node / constrained-path / phaseless) ·
  sign-immune (not a Monte Carlo method — tensor networks, ED, VMC, SDP).
- **Why it matters:** the gate for the QMC family. Sign-free → numerically exact at
  scale; sign-ful → cost `∝1/⟨s⟩²~e^{2βNΔf}` or a controlled bias. Sign-immune
  methods are the fallback in frustrated / doped / real-time regimes.

### M8 — Symmetry exploitation (model C9/C10)
- **Values:** how the method uses conserved quantities — U(1)/SU(2)/Z₂/PH block
  structure, translation/point-group (`k`, irreps) — to cut cost; "none" if it
  cannot.
- **Why it matters:** the cheapest available speedup. Symmetry block-diagonalizes
  ED and shrinks the SDP (PolyOpt); gives quantum-number-conserving tensors (MPS,
  ~10× at fixed accuracy); particle-hole at half-filling makes QMC sign-free.

---

## M-III. Cost & scaling

### M9 — Time complexity (leading)
- **Values:** the leading time scaling in the controlling sizes (e.g. ED full
  `O(D_blk³)`; DMRG `O(N·w·d·χ³)`; iPEPS `O(χ_env³D⁶)`–`O(D¹⁰⁻¹²)`; HOTRG
  `O(χ^{4d−1})`; DQMC `O(βN³)`; AFQMC `O(N³N_wN_steps)`; CCSD `O(N⁶)`).
- **Why it matters:** sets the feasible problem size and which sizes you can scale.
  Use the survey's web-verified exponents (note HOTRG is `O(χ^{4d−1})`, *not*
  ATRG's `O(χ^{2d+1})`).

### M10 — Memory (leading)
- **Values:** the leading memory scaling (e.g. ED full `O(D_blk²)`, Lanczos
  `O(D_blk)`; MPS `O(d·χ²)`; DQMC `O(N²N_τ)`; state-vector circuit `O(2ⁿ)`).
- **Why it matters:** memory, not time, is often the first wall (dense ED, KPM
  `O(D_H)`, state-vector simulation `O(2ⁿ)`).

### M11 — Control knob
- **Values:** the convergence parameter and the error it controls — bond dim `χ`/`D`
  (truncation), #samples `N_s`/walkers `N_w` (statistical `1/√N_s`), inverse temp
  `β` & Trotter step `Δτ` (`O(Δτ^p)`, `p=2` standard / `p=4` higher-order
  Suzuki–Trotter), #moments `M` (spectral resolution), SDP
  level `k` (bound tightness), `N_kept` (NRG truncation), bath/cluster size.
- **Why it matters:** what you turn to converge and report a convergence study. A
  method without an exposed knob (uncontrolled mean field) cannot be systematically
  improved.

### M12 — Scale frontier
- **Values:** the practical reachable system size (e.g. ED ~20 dense / 48–50
  Lanczos with full symmetry; FCI ~18–20 orbitals routine, ~10¹² determinants at
  the frontier; DMRG large 1D / narrow cylinders; sign-free QMC thousands of sites;
  state-vector circuits ~40–50 qubits).
- **Why it matters:** the honest "how big can I go" — distinguishes finite-cluster
  oracles (ED) from thermodynamic-limit methods (iPEPS, iDMRG, DiagMC, DMFT).

---

## M-IV. Limits

### M13 — Primary approximation / bias
- **Values:** what is approximated and whether the bias is controlled — finite-`χ`
  truncation (controlled) · trial-state / nodal constraint (controlled bias) ·
  ansatz bias (VMC, uncontrolled but variational) · series truncation order ·
  single-reference assumption (CC) · neglect of spatial correlations (DMFT) ·
  "none — numerically exact".
- **Why it matters:** every approximate method fails somewhere; naming the bias
  tells you the failure direction and whether a knob (M11) removes it.

### M14 — Hard blocker / failure mode
- **Values:** the property value that makes the method inapplicable or blows up its
  cost — volume-law entanglement (tensor networks) · sign problem (QMC) · `d^N`
  wall (ED) · 2D for MPS (`χ~e^{cW}` for a width-`W` cylinder) · strong static
  correlation / frustration (CC, mean field) ·
  the entanglement barrier `χ(t)~e^{S(t)}` (real-time TN) · #channels (NRG) ·
  3D / SDP blow-up (PolyOpt).
- **Why it matters:** the single fact that rules the method out for a given model —
  read it against the model's A1–D16 card before committing.

---

## Cross-cutting study choices

Not intrinsic method properties, but recorded alongside the card:

- **Owning harness skill** — which `/method-*` (and `/using-*`) skill executes it.
- **Cross-check partner** — the independent method that validates its result
  (e.g. ED oracle for DMRG/VMC/QMC; VMC upper + SDP lower bracket).
- **Target accuracy** — absolute vs relative energy, acceptable error bar.

---

## How to use this card

1. For a given method, fill in the value for each axis M1–M14.
2. The decisive clusters: **M1+M2** say what/which-regime it computes; **M4+M6+M7**
   gate applicability (dimension, entanglement, sign); **M9–M12** set the cost and
   reachable size; **M3+M13+M14** say how much to trust it and where it breaks.
3. To go the other way — from a model's A1–D16 card to a method — use
   `.knowledge/method-property-map.md`. For cost derivations and citations, see
   `.knowledge/method-survey.md`.
