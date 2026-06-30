<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Slave-particle / Parton Mean Field (slave-boson, Schwinger boson, Abrikosov fermion, Gutzwiller) (slave-particle)

Mean-field theory on an enlarged parton Hilbert space that builds in fractionalization from the outset, targeting spin-liquid, Mott-insulating, and fractionalized phases that single-particle (Hartree–Fock) mean field cannot reach.

## Method card

### What it is

Slave-particle methods fractionalize the physical electron (or spin) into partons — e.g. a spinon (Abrikosov fermion or Schwinger boson) carrying spin and a holon (slave boson) carrying charge — subject to a local constraint enforcing the physical Hilbert space. A mean-field decoupling of the constraint (saddle-point approximation) gives a tractable HF-like problem on the enlarged parton space; the resulting spinon/holon band structure encodes candidate fractionalized phases. Gutzwiller projection then maps the mean-field parton state back to the physical Hilbert space; the energy is evaluated by variational Monte Carlo (VMC). The method returns candidate spin-liquid and fractionalized ansätze, their energies, mean-field phase diagrams, and spinon/holon dispersions.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Candidate spin-liquid / fractionalized ansätze and their energies · mean-field phase diagrams · spinon/holon dispersions | Primary use: map out fractionalized phases (Z₂ / U(1) spin liquids, Mott physics) inaccessible to HF. |
| M2 regime | T=0 (thermal Schwinger-boson extensions possible) | Finite-T generalization exists for Schwinger-boson MF but less common. |
| M3 accuracy class | Uncontrolled, deterministic (MF saddle point); Gutzwiller-projected states are variational-upper via VMC | Beyond the saddle point, fluctuations require gauge-field theory — no small expansion parameter in general; Gutzwiller-VMC branch is variational. |
| M4 dimension fit (A1) | 2D and 3D; works in any dimension at MF level | Gauge fluctuations (corrections beyond MF) depend strongly on dimension; 1D is often handled better by bosonization or DMRG. |
| M5 statistics & local dim (A3) | Fermions (Abrikosov/slave-boson partons) and bosons (Schwinger bosons / slave bosons); spins and Hubbard-model electrons | Local dim `d` enters only the parton-space HF step; cost independent of `d`. |
| M6 entanglement regime (B5) | Mean-field parton state = product (zero entanglement in parton space); Gutzwiller projection introduces physical-space correlations | Parton MF carries no entanglement barrier; VMC evaluation of Gutzwiller-projected state does not impose a bond-dimension wall but carries ansatz bias. |
| M7 sign-problem dependence (C12) | Sign-immune (MF / parton saddle point is deterministic); Gutzwiller-VMC may carry a sign problem for fermionic partons | Parton MF: deterministic. VMC branch: sign problem possible but mitigated by the Gutzwiller projector structure. |
| M8 symmetry exploitation (C9/C10) | Lattice translation, point-group, and spin-rotation symmetries used to classify the parton ansatz (PSG — projective symmetry group) | Projective symmetry group (Wen) classifies distinct mean-field spin-liquid ansätze; symmetry reduces the parton Hamiltonian to k-space blocks. |
| M9 time complexity | Self-consistent parton MF: `O(N³)` per SCF iteration (HF-like, where `N` = system size / #parton flavors); Gutzwiller-projected VMC: `O(N_s · N²)` per sample | Cost is dominated by VMC if the Gutzwiller route is taken; the MF step alone is cheap. |
| M10 memory | `O(N²)` (parton density matrix / Fock matrix); VMC: `O(N²)` for the Slater-determinant update | Cheap at the MF level. |
| M11 control knob | None at the MF saddle-point level (uncontrolled); VMC branch: `N_s` samples control statistical error `∝1/√N_s` | Gauge fluctuations beyond MF are in principle a systematic expansion but are rarely carried out beyond the Gaussian level. |
| M12 scale frontier | MF: `N ~ 10³–10⁵` sites (no bottleneck); Gutzwiller-VMC: up to `N ~ 10²–10³` sites (limited by VMC) | MF phase diagrams thermodynamic; VMC limited by the cost of Slater-determinant evaluation. |
| M13 primary approximation / bias | Mean-field (saddle-point) decoupling of the parton constraint — no fluctuations, no dynamical gauge field, no entanglement | Uncontrolled: can predict a spin liquid that is destabilized by gauge fluctuations; quality assessed only by comparison with VMC energetics or QMC. |
| M14 hard blocker / failure mode | Gauge fluctuations may gap or confine the parton excitations, invalidating the MF ansatz; no convergence parameter signals this within MF; fails to capture Luttinger-liquid physics in 1D | Breakdown is silent — a "spin-liquid" MF solution may be a confined phase in reality. Requires cross-check with VMC / QMC / DMRG. |

### Cost & scaling

- Time: `O(N³)` per SCF iteration at the parton MF level (HF-like); `O(N_s · N²)` for Gutzwiller-VMC
- Memory: `O(N²)` (parton density matrix)
- Control knob: none at MF level (uncontrolled); VMC branch: `N_s` samples, error `∝1/√N_s`
- Scale frontier: MF thermodynamic; VMC up to `N ~ 10²–10³`

### Accuracy & guarantees

- Class: uncontrolled, deterministic (MF saddle point); variational-upper via Gutzwiller-VMC
- Primary approximation & its control: mean-field decoupling of the parton constraint; fluctuation corrections require gauge-field theory — no small parameter in general
- Error scaling: no systematic expansion at MF level; VMC branch converges statistically as `1/√N_s`

### Tasks it computes

- Candidate spin-liquid and fractionalized phase ansätze (Z₂, U(1), chiral spin liquids)
- Mean-field phase diagrams (Mott insulator / spin liquid / metallic phase boundaries)
- Spinon and holon dispersions (parton band structures)
- Fractionalized excitation spectra at the MF level
- Gutzwiller-projected variational energies (via VMC, variational upper bound)

### Recommended for (models / regimes)

- **Spin-liquid / fractionalized phases (B7):** triangular / kagome / honeycomb Heisenberg and Hubbard models where HF yields trivial order
- **Mott transition:** half-filled Hubbard model near the Mott point where charge and spin degrees of freedom decouple
- **Ansatz generation:** Gutzwiller-projected parton states as trial wavefunctions for VMC (the VMC energy then constitutes a variational upper bound)
- Per `method-property-map.md`: the method of choice when the target phase is B7 fractionalized and HF/DMRG cannot resolve the spin-liquid ansatz structure

### Key reference

[@kotliar_1986_new] — introduced the slave-boson functional-integral approach and showed that the Gutzwiller approximation emerges as its saddle point; the foundational paper for slave-boson MF on strongly correlated lattice models.
Rendered: _(none — bib stub)_.

### Benchmarks

- Slave-boson MF reproduces the Brinkman–Rice metal-insulator transition in the half-filled Hubbard model at `U_c = 8t` (exact Gutzwiller in `d→∞`; deviates in 2D) [@kotliar_1986_new].
- Schwinger-boson MF on the triangular Heisenberg antiferromagnet predicts a Z₂ spin liquid at `J₂/J₁ > 0.08`; VMC energetics partially support this (see `method-survey.md` §7.3).
- Gutzwiller-VMC energies on the Heisenberg kagome lattice are within 1–2% of DMRG benchmarks for accessible cluster sizes.

## How it is used / Operational

**Owning skill:** `/method-mf`.

**Default workflow:**
1. Choose the parton decomposition (slave-boson for charge fluctuations, Schwinger boson or Abrikosov fermion for spin; specify the ansatz by its projective symmetry group class).
2. Impose the parton constraint at mean-field level (Lagrange multiplier / saddle-point condition).
3. Diagonalize the parton Hamiltonian self-consistently; extract the parton band structure (spinon/holon dispersions) and gap structure.
4. Classify the mean-field state (gapped Z₂ vs gapless U(1) spin liquid, etc.) from the parton topology and gauge structure.
5. Optionally: Gutzwiller-project the parton Slater determinant and evaluate the variational energy by VMC (owning skill `/method-mf` or `/method-vmc` for the VMC step).

**Verification pointers:**
- Cross-check MF energetics against VMC (Gutzwiller-projected) or DMRG (small systems).
- Check whether the mean-field spin liquid survives gauge fluctuations at the Gaussian level (compute the gauge-boson mass; if zero, the state may be a U(1) liquid with algebraic correlations rather than a gapped Z₂ liquid).
- Compare spinon dispersion to INS/spectral-function data where available.

**Cross-links:**
- Survey: `method-survey.md` §7.3 (Slave-particle / parton mean field)
- Model↔method gate: `method-property-map.md` (slave-particle profile, B7 fractionalized row)
- Complementary methods: VMC/NQS (variational upper bound with Gutzwiller trial state), DMRG (1D benchmarks), DQMC/SSE (sign-free spin models for cross-check)
