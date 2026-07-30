# Source provenance

Access date for web sources: 30 July 2026.

## Challenge statement

- QuantumBFS, quantum.harness Issue #35:
  <https://github.com/QuantumBFS/quantum.harness/issues/35>
  - Used for the stated scientific motivation, AI-agent objective, and intended
    deliverable.

## Foundations

- Baroni et al., DFPT review: <https://doi.org/10.1103/RevModPhys.73.515>
  - Static Kohn-Sham response, Sternheimer formulation, and lattice dynamics.
- Gonze, adiabatic DFPT: <https://doi.org/10.1103/PhysRevA.52.1096>
  - Formal adiabatic DFPT foundations.
- Giustino, electron--phonon review:
  <https://doi.org/10.1103/RevModPhys.89.015003>
  - Definitions of electron--phonon matrix elements and many-body context.
- Hedin, many-body equations: <https://doi.org/10.1103/PhysRev.139.A796>
  - Self-energy, screened interaction, polarization, and vertex closure.
- Nambu, gauge invariance: <https://doi.org/10.1103/PhysRev.117.648>
  - Ward-identity/gauge-invariance foundation.
- Marini, Ponce, and Gonze:
  <https://doi.org/10.1103/PhysRevB.91.224310>
  - Consistent many-body perturbation theory starting from DFT.

## Evidence and counterexamples

- Cai et al., uniform electron liquid:
  <https://arxiv.org/html/2512.19382v2>
  - Equations corresponding to the quasiparticle vertex and the DFPT-like local
    kernel, and the numerical comparison over momenta up to `2 k_F`.
  - This is a recent preprint. Its finite-momentum agreement is treated as a
    benchmark result, not an exact Ward theorem.
- Abramovitch et al., correlated metals:
  <https://doi.org/10.1103/467t-z5b2> and
  <https://arxiv.org/html/2505.03958v2>
  - Static and frequency-dependent DFT+DMFT electron--phonon vertices for
    SrVO3 and doped CaCuO2.
- Zhou et al., DFPT+U:
  <https://doi.org/10.1103/PhysRevLett.127.126404>
  - Standard-DFPT failure in a correlated insulator and a first-principles
    correction route.
- Li et al., GW perturbation theory:
  <https://doi.org/10.1103/PhysRevLett.122.186402>
  - Derivative of a nonlocal, energy-dependent self-energy and an established
    beyond-DFT linear-response route.
- Nomura and Arita, constrained DFPT:
  <https://doi.org/10.1103/PhysRevB.92.245108>
  - Low-energy downfolding and separation of screening channels.
- Grilli and Castellani, correlations and electron--phonon coupling:
  <https://doi.org/10.1103/PhysRevB.50.16880>
  - Earlier theory showing that correlation effects can be momentum- and
    channel-dependent.

## Verification notes

- DOI metadata were retrieved through Crossref DOI content negotiation and
  checked against the publisher DOI pages.
- The electron-gas preprint title and author list were checked against arXiv
  metadata.
- Equations in the proposal distinguish exact identities, established method
  definitions, literature numerical observations, and the new working
  hypothesis. Appendix D records that status explicitly.
