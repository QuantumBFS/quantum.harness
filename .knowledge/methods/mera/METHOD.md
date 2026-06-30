<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Multiscale Entanglement Renormalization Ansatz (MERA)

Scale-invariant tensor network with disentanglers; the method of choice for extracting CFT data (scaling dimensions, central charge) from 1D critical ground states.

## Method card

### What it is

MERA represents the ground state as a layered tensor network of two types of tensors: disentanglers (unitary tensors that remove short-range entanglement before coarse-graining) and isometries (that perform the actual coarse-graining step). The layers form a discrete scale transformation, and the fixed-point layer encodes the scale-invariant structure of the ground state. Unlike MPS or PEPS, MERA can represent the logarithmic entanglement entropy of 1D critical (CFT) ground states at finite bond dimension χ because the disentanglers explicitly remove the short-range entanglement that would otherwise require exponentially large χ. The RG superoperator defined by the fixed-point layer has eigenvalues that give the scaling dimensions and central charge of the underlying CFT.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Ground-state energy of critical systems · scaling dimensions of primary operators · central charge c (CFT data) from the RG superoperator spectrum · entanglement entropy S ~ (c/3) ln L at finite χ · correlation functions | CFT data extraction is MERA's primary strength and the quantity no other efficient method provides directly in the thermodynamic limit. |
| M2 regime | T=0 ground state (primary) | Finite-T and real-time variants exist but are uncommon; primary use is critical GS. |
| M3 accuracy class | Controlled-bias (finite-χ truncation at each layer), deterministic; variational upper bound on energy | Bias → 0 as χ → ∞; optimization is variational so energy is an upper bound at fixed χ. |
| M4 dimension fit (A1) | 1D (primary); some 2D MERA constructions exist but are much more expensive | 2D MERA costs up to O(χ¹⁶), making it impractical at χ large enough to be accurate; 1D is the natural home. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / fermion (fermionic MERA with parity structure) | Local dimension d enters via the base-layer tensors; standard implementations fix d=2 (spin-½ or qubit). |
| M6 entanglement regime (B5) | Criticality / scale invariance — its reason to exist: reproduces the log entanglement S ~ (c/3) ln L of 1D CFTs at finite χ via disentanglers | Area-law states are better served by MPS at lower cost; volume-law states are inaccessible. MERA is the unique method that handles the area+log critical regime efficiently in the thermodynamic limit. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; no sign problem regardless of frustration or doping. |
| M8 symmetry exploitation (C9/C10) | Global symmetry (U(1), SU(2), Z₂) enforced via symmetric disentanglers and isometries | Symmetric MERA implementations reduce cost and improve convergence; translation symmetry exploited by the coarse-graining structure. |
| M9 time complexity | O(χ⁹) binary 1D; O(χ⁸) ternary 1D; O(χ⁷) modified-binary 1D; 2D up to ~O(χ¹⁶) | Cost dominated by the contraction of disentangler environments; binary/ternary costs from [@evenbly_2007_algorithms]; modified-binary O(χ⁷) from [@evenbly_2011_class] (Evenbly–Vidal 2011), which reduces cost while retaining scale invariance. |
| M10 memory | O(χ⁴) per layer (storing disentangler and isometry tensors) | Number of layers grows as log₂(N) for a finite system; thermodynamic limit uses a fixed periodic (scale-invariant) layer structure. |
| M11 control knob | Bond dimension χ (number of states kept after each isometry truncation) | Increasing χ captures more entanglement and improves both energy accuracy and CFT-data precision; convergence checked by energy and scaling-dimension stability vs χ. |
| M12 scale frontier | Thermodynamic limit directly (via scale-invariant fixed-point layer); finite systems at N ~ 10²–10³ routine in 1D | The scale-invariant (infinite) MERA defines a fixed-point RG map valid at all length scales, giving direct thermodynamic-limit CFT data. |
| M13 primary approximation / bias | Finite-χ truncation (controlled): the isometries restrict the number of states retained at each scale; disentanglers are constrained to be unitary | Bias is systematic and controlled; energy and CFT data converge monotonically with χ. |
| M14 hard blocker / failure mode | 2D: cost up to O(χ¹⁶) makes large-χ calculations impractical; gapped (area-law) systems: MERA is overkill — MPS is cheaper; volume-law phases and real-time dynamics are inaccessible | MERA is purpose-built for criticality; applying it to gapped systems wastes cost relative to MPS. |

### Cost & scaling

- Time: O(χ⁹) binary 1D; O(χ⁸) ternary 1D; O(χ⁷) modified-binary 1D; 2D MERA up to ~O(χ¹⁶)
- Memory: O(χ⁴) per layer; log₂(N) layers for finite system; O(χ⁴) total for scale-invariant (infinite) MERA
- Control knob: bond dimension χ — controls truncation error and CFT-data accuracy
- Scale frontier: thermodynamic limit directly via scale-invariant fixed point; finite 1D chains up to N ~ 10³

### Accuracy & guarantees

- Class: controlled-bias, deterministic; variational upper bound on energy at fixed χ
- Primary approximation & its control: finite-χ truncation at each isometry; disentanglers required to be unitary (no additional approximation beyond χ); bias → 0 as χ → ∞
- Error scaling: energy error ~ O(ε_trunc); scaling dimensions and central charge converge as a power of χ; modified-binary MERA achieves lower cost exponent without sacrificing accuracy

### Tasks it computes

- Ground-state energy and wavefunction of 1D critical systems
- Scaling dimensions Δ_n of primary operators from the RG superoperator spectrum eigenvalues
- Central charge c from the pattern of scaling dimensions (Kac table / Virasoro representations)
- Entanglement entropy S ~ (c/3) ln L as a function of subsystem size L (directly from Schmidt values)
- Correlation functions ⟨O_i O_j⟩ ~ |i−j|^{−2Δ_O} (power-law decay at criticality)
- CFT operator content: identification of primary and descendant fields

### Recommended for (models / regimes)

- **Primary method for extracting CFT data from 1D critical Hamiltonians** (transverse-field Ising at J_c, XXX Heisenberg chain, quantum clock models): scaling dimensions and c with no finite-size extrapolation needed
- **1D critical ground states where log entanglement is the bottleneck**: MERA achieves finite-χ accuracy where MPS would require χ ~ L^{c/6}
- **Benchmarking RG fixed points**: the scale-invariant MERA layer is a tensor-network realization of the CFT RG fixed point
- Per `method-property-map.md`: optimal when A1=1D, B6=critical/scale-invariant; disfavored for A1=2D (cost), B5=area-law gapped (use MPS), B5=volume-law, D13=real-time

### Key reference

[@evenbly_2007_algorithms] — derives the MERA optimization (alternating optimization of disentanglers and isometries), establishes cost scaling for binary and ternary 1D MERA, and demonstrates CFT data extraction.
Rendered: `./0707.1454_algorithms-for-entanglement-renormalization.md` _(downloaded)_.

### Benchmarks

- 1D transverse-field Ising (J=J_c): central charge c = 0.5 recovered from RG-spectrum; scaling dimension Δ_σ = 0.125 (spin), Δ_ε = 1.0 (energy), both matching Ising CFT exactly at χ ~ 8–16 [survey §3.4; @evenbly_2007_algorithms].
- 1D XXX Heisenberg chain: c = 1 (free boson CFT), Δ_n consistent with SU(2)₁ WZW model at χ ~ 12 [survey §3.4].
- Entanglement entropy S ~ (c/3) ln L = (1/6) ln L (c=1/2 Ising CFT, periodic): reproduced at finite χ, confirming log scaling without finite-size extrapolation [@evenbly_2007_algorithms].

## How it is used / Operational

**Owning skill:** No dedicated harness skill for MERA; it is a specialized scale-invariant tensor network not covered by the current tool suite. The closest available skills are `/method-mps` (for general 1D tensor-network workflows) and `/method-peps` (for 2D tensor-network contractions). MERA-specific implementations include TENPY (partial support) and specialized codes (e.g., Evenbly's TNS library).

**Default workflow:**
1. Write the Hamiltonian in MPO form; identify the critical point J_c (e.g., from a prior DMRG finite-size-scaling study).
2. Initialize MERA tensors (disentanglers = identity, isometries = random or MPS-derived).
3. Optimize by alternating updates: fix isometries, optimize disentanglers by minimizing ⟨H⟩; then fix disentanglers, optimize isometries.
4. Impose scale invariance: after initial finite-system optimization, fix the top layers to a periodic (scale-invariant) form and re-optimize the fixed-point layer.
5. Extract the RG superoperator from the fixed-point layer; diagonalize to obtain scaling dimensions Δ_n.
6. Extract c from the Δ_n pattern (compare to Kac table of the expected CFT).
7. Increase χ and verify convergence of Δ_n and c.

**Verification pointers:**
- Cross-check GS energy against ED Lanczos or DMRG on small systems (same J_c).
- Verify entanglement entropy S ~ (c/3) ln L scaling using the MERA Schmidt values.
- Check that scaling dimensions match known CFT predictions (Ising, SU(2)₁ WZW, etc.) to at least 3 significant figures at the target χ.

**Cross-links:**
- Survey: `method-survey.md` §3.4 (MERA — multiscale entanglement renormalization)
- Model↔method gate: `method-property-map.md` (MERA profile)
- Complementary methods: DMRG/MPS (§3.1 — 1D GS solver, use for gapped systems or finite-size input to MERA), TRG/HOTRG (§3.5 — classical coarse-graining, CFT data from transfer-matrix spectrum), MCRG (Wave B — RG flow from MC configurations, independent CFT check)
