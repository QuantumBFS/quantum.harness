# Rydberg PXP

Constrained Rydberg-blockade chain: each atom is a two-level (ground/Rydberg) qubit, and the infinite nearest-neighbor blockade forbids two adjacent excitations. The PXP limit hosts quantum many-body scars — a non-thermal tower of states giving long-lived coherent revivals from the period-2 |Z₂⟩ state.

Distinct from `transverse-field-ising`: the same `σ^x` drive, but the kinetic term is dressed by blockade projectors `P = |g⟩⟨g|`, which restrict the Hilbert space (no two neighboring excitations) and make the model non-integrable with weak ergodicity breaking.

## Physics card

### Hamiltonian

$$ H = \Omega \sum_i P_{i-1}\, \sigma^x_i\, P_{i+1} \;-\; \Delta \sum_i n_i $$

Conventions: per-atom two-level system `{|g⟩,|r⟩}`; `n_i = |r⟩⟨r|_i` is the Rydberg-excitation number; `σ^x_i = |g⟩⟨r|_i + |r⟩⟨g|_i` drives the `g↔r` transition; `P_i = |g⟩⟨g|_i = 1 - n_i` projects neighbor `i` onto its ground state. The flanking projectors `P_{i-1} P_{i+1}` encode the infinite Rydberg blockade — a spin can only flip if both neighbors are in `|g⟩`, so no two adjacent Rydberg excitations are allowed. `Ω` is the Rabi frequency (energy unit `Ω = 1`); `Δ` the laser detuning (`Δ > 0` favors excitations). The pure PXP point is `Δ = 0`. The unprojected model is the Rydberg/Ising-with-blockade Hamiltonian; the projected PXP is the strong-blockade (constrained-Hilbert-space) limit. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`); also 2D arrays (square / other tweezer geometries) | The 1D chain is the canonical scar platform; 2D PXP also shows scarring. |
| A2 boundary conditions | OBC (tweezer chain / DMRG) · PBC (ED, clean momentum sectors) | Revival fidelity and the scar tower are cleanest with translation symmetry (PBC). |
| A3 statistics & local dim | spin-1/2 / two-level atom; `d = 2` per site, but a **constrained** Hilbert space (no two adjacent excitations) | Constraint → Fibonacci-dimensional space, `dim ∼ φ^N`, `φ = (1+√5)/2` (golden ratio), not `2^N`. |
| A4 interaction range | short-range (NN blockade + on-site drive in the PXP limit) | Physical van-der-Waals tail is `1/r^6`; the PXP limit keeps only the NN hard constraint. |
| B5 entanglement scaling | volume law for generic eigenstates (ETH bulk) · **sub-thermal / anomalously low** entanglement for the scar-tower states | The scar subspace is the exception that makes MPS capture the revival dynamics to long times. |
| B6 spectral gap | no protecting gap (non-integrable chaotic spectrum); the scar tower sits at ≈ equal energy spacing inside the bulk | Scars are special excited states embedded in a thermal continuum, not a low-energy gap structure. |
| B7 ground-state order | disordered (paramagnetic) at small/negative `Δ` · **Z₂ (period-2) ordered** "antiferromagnetic" phase at suitable `Δ > 0` | The detuned ground state breaks translation by one site (⟨Z₂⟩ order); the scar physics is a dynamical, not ground-state, phenomenon. |
| B8 frustration | none (constraint, not competing couplings) | The blockade is a kinematic constraint rather than frustrated exchange. |
| C9 global symmetry | `Z_2` (spatial inversion / reflection); particle-hole-like spectral reflection of the PXP spectrum | No U(1): the drive does not conserve excitation number (`Δ=0` PXP). |
| C10 spatial symmetry | translation (`k`), inversion/parity | Scar states carry definite momentum (`k=0` and `k=π`); used to resolve the tower in ED. |
| C11 integrability | **non-integrable** (level repulsion, ETH for the bulk) — but hosts **quantum many-body scars** (weak ergodicity breaking, ETH violated only in the scar subspace) | The scarred subspace is approximately decoupled from the thermal bulk (an approximate `su(2)` "spectrum-generating" algebra). |
| C12 sign problem | n/a — this is a real-time-dynamics / ED-MPS target, not a QMC target | Quench dynamics from `|Z₂⟩` is the workhorse calculation; no Monte Carlo sampling. |
| D13 regime | **real-time quench dynamics** (revivals from `|Z₂⟩`) is the defining regime; also full-spectrum (ED) and ground state (detuned phase) | `|Z₂⟩` is an infinite-temperature state for the constrained ensemble, yet shows periodic revivals. |
| D14 filling / doping | n/a (spin/qubit model; detuning `Δ` plays the role of a chemical potential for excitations) | Tuning `Δ` drives the disordered ↔ Z₂-ordered transition. |
| D15 disorder | clean (translation-invariant) by default | Site/detuning disorder can be added (tweezer arrays), tuning toward localization. |
| D16 hermiticity | Hermitian / closed (unitary quench) | Dissipation (atom loss, spontaneous emission) is a separate open-system extension. |

### Phases & order parameters

- Disordered / paramagnetic (small or negative `Δ`) : no broken symmetry; short-range correlations.
- Z₂ (period-2 "antiferromagnetic") ordered phase (suitable `Δ > 0`) : staggered Rydberg density `⟨n_i⟩ = n̄ ± δ(-1)^i`, order parameter `⟨Z₂⟩` (structure-factor peak at `q=π`); the ground state is close to the `|•◦•◦…⟩` pattern. The disordered→Z₂ transition is in the (1+1)D Ising universality class.
- Quantum many-body scars (dynamical, all `Δ≈0`) : a tower of ≈ equally-spaced special eigenstates with anomalously large overlap on `|Z₂⟩`; diagnosed by long-lived revivals of the `|Z₂⟩` autocorrelation/fidelity and by the sub-thermal entanglement of the tower states.

### Canonical observables

- Quench from `|Z₂⟩`: return probability / fidelity `|⟨Z₂|ψ(t)⟩|²`, domain-wall or staggered-magnetization dynamics, entanglement-entropy growth.
- Eigenstate diagnostics: overlap `|⟨Z₂|E_n⟩|²` vs energy (the scar tower), entanglement entropy vs energy (scars are outliers), level-spacing statistics (Wigner-Dyson for the bulk → non-integrable).
- Ground-state (detuned) phase: staggered density / `⟨Z₂⟩` order parameter; Hilbert-space dimension growth `∼ φ^N`.

### Recommended methods

- Primary: **ED** — small constrained chains (`N ≲ 32`, Fibonacci-reduced dimension after symmetry) give the full spectrum, the scar tower, level statistics, and exact quench dynamics; the universal oracle here (per `method-property-map.md` §ED, A3/C10).
- Primary (longer times / larger `N`): **MPS / TDVP** — the scar subspace's sub-thermal entanglement keeps the bond dimension manageable out to many revival periods (§MPS, D13); standard TEBD/TDVP for the constrained chain.
- Cross-check: **QCS** (circuit / state-vector simulation) for the same quench; reproduce against Rydberg-array experimental revivals.

### Key reference

[@serbyn_2020_quantum] — pedagogical Nature Physics review of quantum many-body scars and weak ergodicity breaking; works the PXP model explicitly (Eq. 1, the projector-dressed drive), the `|Z₂⟩`-quench revivals, the scar tower of special eigenstates with enhanced `|Z₂⟩` overlap, the approximate spectrum-generating algebra, and the MPS/TDVP analysis — the best single downloadable all-details source. (The defining theory paper is Turner-Michailidis-Abanin-Serbyn-Papić, arXiv:1711.03528; this review subsumes and contextualizes it.)
Rendered: `./2011.09486_quantum-many-body-scars-and-weak-breaking-of-ergodicity.md`.

### Benchmarks

- Constrained Hilbert-space dimension grows as the Fibonacci sequence, `dim ∼ φ^N` with `φ = (1+√5)/2 ≈ 1.618` (PBC: `dim = L_N` Lucas number; OBC: Fibonacci) — the kinematic signature of the infinite blockade [@serbyn_2020_quantum].
- `|Z₂⟩` quench shows periodic revivals of the return probability with period `T_rev ≈ 2π/(1.3–1.5 Ω)` (i.e. an effective frequency slightly above the bare `Ω`) — the original observation in Rydberg arrays [@serbyn_2020_quantum].
- Scar-tower eigenstates are approximately equally spaced in energy (spacing `≈ ΔE_scar`, the inverse revival period), with anomalously large `|⟨Z₂|E_n⟩|²` standing out against the thermal continuum [@serbyn_2020_quantum].

## How it is studied / Operational

**Canonical defaults (Diagnose):** two-level atoms, infinite blockade (pure PXP, `Ω = 1`, `Δ = 0`), `N = 22–26` constrained chain, target the `|Z₂⟩` quench return probability `|⟨Z₂|ψ(t)⟩|²` out to several revival periods, plus the eigenstate-overlap scar tower from ED. If only "PXP / Rydberg blockade" is given, propose the `Δ=0` quench-from-`|Z₂⟩` calculation and offer a `Δ`-scan for the disordered→Z₂ ground-state transition.

| Regime | Method | Card |
|---|---|---|
| Full spectrum, scar tower, level statistics (`N ≲ 32`, constrained) | ED | `skills/method-ed/SKILL.md` |
| `|Z₂⟩` quench dynamics / revivals, longer times | MPS (TDVP/TEBD) | `skills/method-mps/SKILL.md` |
| Detuned ground state, Z₂ order, `Δ`-scan | DMRG | `skills/method-mps/SKILL.md` |
| Circuit / state-vector quench cross-check | QCS | `skills/method-qcs/SKILL.md` |

Verification pointers:

- Hilbert-space dimension must equal the Fibonacci/Lucas count for the chosen `N` and boundary (`∼ φ^N`) — a direct check that the blockade constraint is correctly imposed.
- The bulk level-spacing statistics should be Wigner-Dyson (non-integrable); the scar states are the outliers in the entanglement-vs-energy and overlap-vs-energy scatter.
- The `|Z₂⟩` quench should revive with period `≈ 2π/(1.3–1.5 Ω)`; a thermalizing initial state (e.g. a random product state) should *not* revive — the negative control for scarring.
- Convergence: ED is exact in the constrained basis; for MPS, sweep bond dimension and confirm the revival fidelity is stable to the target time. For the Z₂ transition or its Ising criticality, hand off to `criticality`.
