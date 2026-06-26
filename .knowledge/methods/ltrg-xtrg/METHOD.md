<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Linearized / Exponential Thermal Tensor RG (LTRG / XTRG)

Thermal tensor-network renormalization group methods that map a d-dimensional quantum lattice model at finite T to a (d+1)-dimensional classical tensor network and contract it via tensor RG; XTRG doubles β each step (O(log β) steps to low T).

## Method card

### What it is

LTRG and XTRG represent the thermal density matrix `ρ(β) = e^{-βH}` as a tensor network by Trotter-decomposing the imaginary-time evolution into a layered (d+1)-dimensional classical tensor network. The rows of this network correspond to imaginary-time slices (each slice a product of local tensors from `e^{-τH}`), and the rows are successively contracted and truncated via tensor renormalization group (TRG/HOSVD) techniques. **LTRG** adds slices linearly: `K = β/τ` layers, each contributing `O(τ²)` Trotter error; cost scales linearly with `β`. **XTRG** exploits the composition law `ρ(2β) = ρ(β)·ρ(β)` to double the inverse temperature at each step — starting from a high-T MPO, squaring it `log₂(β/τ)` times reaches low T in only **`O(log β)`** steps, dramatically improving low-T accuracy and efficiency. The thermal entanglement is controlled by the retained bond dimension `Dc` at each RG step.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Free energy · internal energy · specific heat `C_v` · magnetic susceptibility · thermal correlations · thermal phase transitions | Primary use case is finite-T thermodynamics; XTRG excels at low-T approach curves where LTRG would require many linear layers. |
| M2 regime | Finite-T thermodynamics (D13) | Equilibrium thermal properties across all T; XTRG most advantageous at low T where `O(log β)` beats LTRG's `O(β/τ)` layers. |
| M3 accuracy class | Controlled, deterministic | Two controllable sources of error: Trotter discretization `τ` (`O(τ²)` per layer) and RG truncation `Dc`; XTRG's squaring accumulates errors multiplicatively but requires fewer steps. |
| M4 dimension fit (A1) | **1D, quasi-1D AND 2D** — **sign-free for frustrated spin/boson models even in 2D** | Maps `d`-dim quantum at finite T → `(d+1)`-dim classical TN; the classical TN is sign-free for frustrated spin and boson models (B8, C12 sign-ful); fermionic models need care (Jordan–Wigner strings can introduce complex/negative entries). The key advantage over QMC is for frustrated 2D magnets. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / any local dim `d` | Local dim `d` enters the Trotter-gate tensors; per-step cost polynomial in `d`; no fundamental barrier from statistics (no sign). |
| M6 entanglement regime (B5) | Moderate at high T; grows as T→0 → `Dc` must increase | Thermal entanglement of the layered TN sets the required `Dc`; at high T, states are product-like (small `Dc`); at low T, thermal entanglement approaches GS entanglement (large `Dc`). |
| M7 sign-problem dependence (C12) | **Sign-immune for frustrated spin and boson models (B8); fermionic LTRG/XTRG needs care** | Sign-free for frustrated spin and boson models (B8); fermionic LTRG/XTRG needs care — Jordan–Wigner strings can give complex/negative tensor entries in the contraction. The sign-free advantage over QMC applies to frustrated magnets and bosonic models. |
| M8 symmetry exploitation (C9/C10) | Conserved-charge (U(1)) block structure in the MPO/TN tensors | Symmetry reduces the effective tensor dimensions and speeds up contraction. |
| M9 time complexity | **LTRG:** polynomial in `d` and `Dc` per layer × `K=β/τ` layers, Trotter error `O(τ²)`; **XTRG:** higher cost per step (squaring a TN) but only **`O(log β)`** steps to reach low T | XTRG reaches `β=100` in ~7 squaring steps from `τ=1`; LTRG needs 100/τ layers. At low T, XTRG's lower step count dominates the comparison. |
| M10 memory | `O(Dc²)` per TN row (MPO or boundary MPS) | The dominant memory is the contracted boundary object; 2D requires 2D boundary contraction (heavier than 1D). |
| M11 control knob | Trotter step `τ` (Trotter error `O(τ²)`) + retained bond dim `Dc` (RG truncation error) | Both must be converged; XTRG additionally requires checking that squaring errors accumulate controllably. |
| M12 scale frontier | 1D: `N~1000` sites routine; quasi-1D and 2D: thermodynamic limit via transfer-matrix / iPEPS-row contraction | 2D: infinite systems via row-to-row contraction with boundary-MPS or CTMRG; not limited to small clusters. |
| M13 primary approximation / bias | Trotter `O(τ²)` discretization (controlled) + finite-`Dc` RG truncation (controlled) | Both biases are convergence parameters; XTRG has multiplicative error accumulation from squaring steps but requires far fewer of them. |
| M14 hard blocker / failure mode | Low-T thermal entanglement growth → large `Dc` needed; 3D classical TN contraction (extremely expensive); models with complex local interactions that resist Trotter decomposition | 2D quantum → 3D classical TN is the heaviest case; exponentially hard for 3D quantum models. |

### Cost & scaling

- Time: LTRG: `O(β/τ)` layers × polynomial in `d·Dc` per layer; XTRG: **`O(log β)`** squaring steps × higher per-step cost
- Memory: `O(Dc²)` per MPO / boundary row
- Control knob: Trotter `τ` (error `O(τ²)`) + retained `Dc` (RG truncation error)
- Scale frontier: 1D `N~1000`; 2D thermodynamic limit via infinite-system row contraction

### Accuracy & guarantees

- Class: controlled, deterministic
- Primary approximation & its control: Trotter `O(τ²)` + finite-`Dc` RG truncation; both are systematically improvable
- Error scaling: Trotter error total `O(τ² · K) = O(τ · β)` for LTRG; XTRG's multiplicative squaring reduces total steps dramatically at low T

### Tasks it computes

- Free energy `F(T)` and partition function `Z(β)` via TN trace
- Internal energy `U(T)`, specific heat `C_v(T)`, entropy `S(T)`
- Magnetic susceptibility `χ(T)`, thermal correlation functions
- Thermal phase transitions and crossover temperatures in 1D, quasi-1D, and 2D models

### Recommended for (models / regimes)

- **Frustrated 2D quantum magnets (B8, C12 sign-ful):** sign-free even in 2D — the primary advantage; QMC fails here; LTRG/XTRG succeeds
- **Low-T thermodynamics (XTRG):** XTRG's `O(log β)` scaling is far superior to LTRG's linear `K` at low T; use XTRG when `βJ ≳ 10`
- **1D and quasi-1D models at all T:** competitive with or better than mps-finite-t for 1D at intermediate T; natural thermodynamic-limit access
- **Any model where QMC has a sign problem (C12 sign-ful):** LTRG/XTRG provide the sign-free finite-T route
- Per `method-property-map.md` (LTRG/XTRG profile): preferred finite-T method when QMC sign problem is present and 2D geometry is needed

### Key references

[@chen_2018_exponential] — introduces XTRG (exponential doubling `ρ→ρ·ρ`), demonstrates `O(log β)` scaling, and benchmarks frustrated 2D magnets; the primary XTRG reference.
Rendered: `../../literature/ltrg/1801.00142_exponential-thermal-tensor-network-approach-for-quantum-latt.md` _(reused: `../../literature/ltrg/1801.00142_exponential-thermal-tensor-network-approach-for-quantum-latt.md`)_.

[@li_2010_linearized] — original LTRG paper introducing the linearized (layer-by-layer) thermal TRG for quantum lattice models.
Rendered: `../../literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md` _(reused: `../../literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md`)_.

### Benchmarks

- XTRG for spin-½ Heisenberg chain: specific heat converged to < 0.1% at `T/J=0.05` with `Dc=64`, `τ=0.1` in 7 squaring steps [@chen_2018_exponential].
- XTRG for frustrated `J₁-J₂` square lattice (sign-ful QMC): thermal susceptibility peak resolved at `T/J≈0.4`, `Dc=64` (method-survey.md §5.5).
- LTRG vs XTRG accuracy at `βJ=20`: XTRG 2–3 orders of magnitude more accurate at same `Dc` and total compute time (method-survey.md §5.5).

## How it is used / Operational

**Owning skill:** `/method-ltrg`.

**Default workflow (XTRG):**
1. Build the Trotter-decomposed MPO for `e^{-τH}` at a small initial `τ` (high T starting point).
2. Iteratively square the MPO: `ρ(2τ) ← ρ(τ) · ρ(τ)`, compressing via SVD/TRG at each step to retain `Dc` states.
3. After `log₂(β/τ)` squaring steps, compute thermal observables as traces: `⟨O⟩_β = Tr(ρ(β)O)/Tr(ρ(β))`.
4. Converge in `Dc` (increase until observables change < threshold) and `τ` (decrease until Trotter error is sub-dominant).
5. For 2D: contract the 2D TN row by row using boundary MPS or CTMRG with bond dim `Dc_env`.

**Default workflow (LTRG, for moderate T):**
1. Build the Trotter-decomposed MPO for `e^{-τH}`.
2. Apply `K = β/τ` layers sequentially, compressing at each layer to `Dc`.
3. Compute observables after reaching target `β`.

**Verification pointers:**
- High-T limit: `⟨H⟩ → 0`, `C_v → const`; compare with exact high-T expansion.
- Low-T limit: energy → GS energy (compare with DMRG or ED).
- XTRG: check that successive squaring steps converge (residual change < `10⁻⁶`).
- `Dc` convergence: increase `Dc` by 2× and check that all observables change < 1%.

**Cross-links:**
- Survey: `method-survey.md` §5.5 (LTRG/XTRG — thermal tensor RG)
- Model↔method gate: `method-property-map.md` (LTRG/XTRG profile)
- Complementary methods: mps-finite-t (1D sign-free, purification/METTS), QMC (sign-free at scale), TRG-HOTRG (zero-T / classical TN contraction)
