# Software API references

Extracted API + worked-example references for quantum many-body codes surveyed in
`articles/2026-06-20-many-body-software-review.typ`. Each file pairs the package's
official documentation with its rendered release paper in
`.knowledge/literature/software/`, and links back to the upstream docs.

These cover the **survey tools that have no `using-*` skill yet**. Codes that are
installed/skilled in the harness are documented next to their skill instead, at
`skills/using-<tool>/references/<tool>-api.md` (ITensors, MPSKit/TensorKit, PEPSKit,
XDiag, TeNPy, NetKet, QuSpin, …).

## Tensor networks (DMRG / MPS / PEPS)

- [quimb](quimb-api.md) — Python quantum-info + high-performance, contraction-path-optimized tensor networks (MPS/DMRG/TEBD/PEPS/circuits).
- [block2](block2-api.md) — production DMRG framework; quantum chemistry, finite-T (ancilla), and dynamics via the `DMRGDriver` API.

## Exact diagonalization

- [HΦ (HPhi)](hphi-api.md) — input-file ED + thermal-pure-quantum finite-T for Hubbard/Heisenberg/Kondo lattices.
- [QuTiP](qutip-api.md) — `Qobj` quantum objects, small-system ED, and closed/open (Lindblad) dynamics.

## Quantum Monte Carlo

- [ALPS](alps-api.md) — historical meta-framework: loop/SSE/worm QMC + ED + DMRG via a shared model/lattice layer and `pyalps`.
- [ALF](alf-api.md) — finite-T and projective auxiliary-field (determinant) QMC for fermions; `pyALF` front-end.
- [SmoQyDQMC.jl](smoqydqmc-api.md) — Julia determinant QMC for Hubbard and electron–phonon (Holstein/SSH) models.
- [DSQSS](dsqss-api.md) — worldline / directed-loop QMC for spin-S and Bose-Hubbard systems at finite T.

## Variational Monte Carlo / neural quantum states

- [jVMC](jvmc-api.md) — JAX, GPU, autodiff VMC/NQS for ground states and TDVP dynamics.
- [mVMC](mvmc-api.md) — many-variable VMC for fermions (10⁴⁺ parameters via stochastic reconfiguration); input-file driven.

## DMFT / impurity solvers

- [TRIQS](triqs-api.md) — Green's-function toolbox + DMFT + CT-HYB impurity solver (`triqs_cthyb`).
- [w2dynamics](w2dynamics-api.md) — multi-orbital CT-HYB solver with a full DMFT loop; one- and two-particle quantities.
- [iQIST](iqist-api.md) — CT-HYB and Hirsch–Fye quantum impurity solvers (segment + general-matrix components).
- [DCore](dcore-api.md) — turnkey DMFT integrating several impurity solvers + DFT front-ends (Wannier90), INI-driven.
