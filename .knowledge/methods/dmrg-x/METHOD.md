<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# DMRG-X (DMRG for Excited Eigenstates / MBL)

DMRG variant that targets individual highly-excited eigenstates of many-body localized (MBL) Hamiltonians by selecting the renormalized basis state with maximum overlap; works only because MBL excited states obey an area law.

## Method card

### What it is

DMRG-X adapts the standard DMRG sweep to target interior excited eigenstates rather than the ground state. At each local diagonalization step, instead of selecting the lowest eigenvalue, the algorithm selects the eigenstate with maximum overlap to the current MPS guess — thereby "tracking" a specific excited state through the sweep. This selection is valid precisely because MBL eigenstates (D15) have low entanglement (area law rather than the volume law of generic excited states), so the required bond dimension `χ` remains bounded and the MPS ansatz is faithful. The full local-diagonalization variant (Khemani et al. 2016) costs `O(L·χ⁶)` due to the environment density-matrix construction for an interior state; a k-eigenstate-near-target variant that avoids the full diagonalization costs approximately `O(L·χ³)`.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Individual highly-excited eigenstates · eigenstate energies and gaps · local observables in excited eigenstates · l-bit structure and l-bit correlators · eigenstate entanglement entropy and spectrum across the MBL phase | The ability to obtain individual eigenstates (not just averages) at arbitrary energy density is unique to DMRG-X among polynomial-cost methods. |
| M2 regime | Highly-excited eigenstates at finite energy density (an MBL-specific regime gated by D15, not one of D13's ground-state/finite-T/dynamics values) | Not a finite-T method; targets a single eigenstate at a chosen energy density, which is a T=∞ analog only in the MBL phase. |
| M3 accuracy class | Controlled, deterministic | MPS truncation at `χ` is the only approximation; energy and observables converge as `χ→∞`; residual `‖H|ψ⟩−E|ψ⟩‖` provides a convergence check. |
| M4 dimension fit (A1) | 1D; quasi-1D (ladders) feasible; **2D only if MBL survives (debated)** | MBL in 2D is theoretically controversial and numerically difficult; DMRG-X is primarily applied to 1D disordered chains (A1=1D, D15=MBL). |
| M5 statistics & local dim (A3) | Spin / hard-core boson / fermion / any | Same as standard DMRG; per-site cost `∝d·χ³` (targeted variant) or `∝d·χ⁶` (full diag variant); fermions need Jordan–Wigner or parity tensors. |
| M6 entanglement regime (B5) | **Area-law only** — works ONLY because MBL (D15) keeps excited-state entanglement area-law | This is the decisive gate: thermal (ETH) excited states have volume-law entanglement → `χ~e^N` → DMRG-X fails; MBL area law → `χ` bounded → DMRG-X works. |
| M7 sign-problem dependence (C12) | Sign-immune | Tensor-network method; no sign problem. |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂ block structure (though disorder breaks translation symmetry) | Symmetry still reduces effective `χ` and improves convergence; translation is absent (disorder breaks it), but spin-rotation or parity may be conserved. |
| M9 time complexity | **`O(L·χ⁶)`** for the full local-diagonalization variant; **`~O(L·χ³)`** for the k-eigenstate-near-target variant | The `χ⁶` scaling (vs standard DMRG `χ³`) comes from the environment density-matrix construction for interior states; the cheaper `O(Lχ³)` variant uses a targeted projection. |
| M10 memory | `O(L·χ²)` for the MPS; environment blocks `O(χ²)` per bond | Same memory as standard DMRG; does not require storing multiple eigenstates simultaneously. |
| M11 control knob | Bond dim `χ` (truncation error) | The single convergence parameter; monitor residual `‖H|ψ⟩−E|ψ⟩‖ < ε`; convergence is typically fast when MBL area law holds. |
| M12 scale frontier | 1D MBL chains `L~100–200` sites routine; `L~500–1000` with optimized codes | Far exceeds exact-diagonalization reach for excited states (ED limited to `L~20–24`); the practical limit set by `χ` required for convergence at the target disorder strength. |
| M13 primary approximation / bias | Finite-`χ` SVD truncation (controlled) | Only approximation; controlled by increasing `χ`; the method is exact in `χ→∞` limit; must verify that the tracked state does not jump to a different eigenstate. |
| M14 hard blocker / failure mode | **Works ONLY because MBL (D15) keeps `χ` bounded**: thermal (ETH, B6 gapless) excited states have volume-law entanglement → DMRG-X completely fails; 2D MBL debated (may not exist thermodynamically); tracking instability (jumping to wrong eigenstate) at weak disorder | The MBL area law is the sole reason DMRG-X is feasible; any regime without it (ETH phase, finite-T thermal states) kills the method. |

### Cost & scaling

- Time: `O(L·χ⁶)` full local-diagonalization variant; `~O(L·χ³)` k-eigenstate-near-target variant
- Memory: `O(L·χ²)` for MPS + environment blocks
- Control knob: `χ` (truncation error; also monitor `‖H|ψ⟩−E|ψ⟩‖`)
- Scale frontier: `L~100–200` routine; `L~500–1000` optimized codes

### Accuracy & guarantees

- Class: controlled, deterministic
- Primary approximation & its control: finite-`χ` MPS truncation; residual `‖H|ψ⟩−E|ψ⟩‖` provides a variational-like convergence metric
- Error scaling: truncation error decreases as `χ→∞`; in the MBL phase, convergence is rapid (area law ensures small entanglement spectrum tail)

### Tasks it computes

- Individual highly-excited eigenstates at arbitrary energy density in the MBL phase (D15)
- Eigenstate energy `E_n` and gaps `δE`
- Local observables `⟨O_i⟩_n` and two-point correlators in excited eigenstates
- Entanglement entropy `S_A(n)` and entanglement spectrum of excited eigenstates (area-law verification)
- L-bit structure: extract l-bit operators and their interactions from the excited eigenstates
- Eigenstate observables across the MBL phase as disorder `W` is varied

### Recommended for (models / regimes)

- **MBL systems (D15) in 1D:** random-field Heisenberg chain, random XXZ, random Hubbard chain — the primary use case and the only regime where DMRG-X is valid
- **Probing the MBL–ETH transition:** compute `S(n)` as disorder `W` is varied; area-law → volume-law crossover marks the transition (DMRG-X fails as ETH sets in → marks the transition)
- **L-bit extraction:** individual eigenstates needed to construct l-bit Hamiltonians and verify MBL phenomenology
- **Beyond ED reach for excited states:** `L~100–500` replaces expensive shift-invert ED (`L≤24`) for individual excited-state studies in the MBL phase
- Per `method-property-map.md` (DMRG-X profile): applicable when D15 = MBL (area-law excited states); inapplicable when D15 absent (ETH phase)

### Key reference

[@khemani_2016_obtaining] — introduces DMRG-X, proves applicability based on MBL area law, and benchmarks the `O(L·χ⁶)` local-diagonalization variant on random-field Heisenberg chains.
Rendered: `./1509.00483_obtaining-highly-excited-eigenstates-of-many-body-localized.md` _(downloaded: `1509.00483_obtaining-highly-excited-eigenstates-of-many-body-localized.md`)_.

### Benchmarks

- Random-field Heisenberg chain (`L=100`, `W/J=5`, `χ=64`): `‖H|ψ⟩−E|ψ⟩‖ < 10⁻⁸`; entanglement entropy `S~0.3` (area law confirmed) [@khemani_2016_obtaining].
- MBL–ETH comparison: DMRG-X converges at `χ=64` for `W/J=5`; fails to converge (requires `χ→∞`) for `W/J=1` (ETH phase) — method-survey.md §5.6.
- `O(L·χ⁶)` vs `O(L·χ³)` crossover: targeted variant (`O(Lχ³)`) reaches same accuracy as full-diag variant at `χ≤64` for strong MBL (method-survey.md §5.6).

## How it is used / Operational

**Owning skill:** `/method-mps` (primary); tool skills `/using-tenpy`, `/using-itensors`, `/using-mpskit`.

**Default workflow:**
1. Choose target energy density `ε = (E−E_min)/(E_max−E_min)` (typically `ε~0.5` for infinite-temperature window).
2. Initialize MPS guess: random MPS or product state at target energy.
3. Run DMRG sweeps selecting the eigenstate with **maximum overlap** to current guess at each local diagonalization.
4. Monitor residual `‖H|ψ⟩−E|ψ⟩‖` and entanglement entropy `S_A`; converge in `χ`.
5. Verify area law: `S_A` must be `O(1)` (not `O(L)`) — if it grows, the eigenstate is in the ETH phase and DMRG-X is invalid.
6. Repeat for an ensemble of disorder realizations to average observables.

**Verification pointers:**
- Area-law check: `S_A ∝ const` across bonds (not growing with subsystem size).
- Residual norm `< 10⁻⁸` for `χ` convergence.
- Energy variance `(⟨H²⟩−⟨H⟩²)/⟨H⟩² < 10⁻⁸` (should vanish for a true eigenstate; relative form consistent with Khemani residual-norm benchmark).
- Cross-check with shift-invert ED (Lanczos) for `L≤20` to verify state identity.

**Cross-links:**
- Survey: `method-survey.md` §5.6 (DMRG-X)
- Model↔method gate: `method-property-map.md` (DMRG-X profile)
- Complementary methods: ED Lanczos + shift-invert (oracle for small `L`), TEBD (MBL dynamics, slow entanglement growth), full ED (level statistics for ETH/MBL diagnosis)
