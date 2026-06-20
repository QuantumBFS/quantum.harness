# Many-body computation software — survey notes

Built by `/survey` on 2026-06-20. Scope: popular open-source software for quantum many-body lattice computation (ground-state and finite-temperature). References use BibTeX cite keys; see `INDEX.md` for the catalog and `../ref.bib` for full entries.

## Field landscape

The open-source ecosystem clusters by method family. Within each, one or two codes dominate, with a clear recent trend toward **Julia + automatic differentiation** (ITensors.jl, MPSKit/TensorKit.jl, PEPSKit.jl, SmoQyDQMC.jl) and **Python + JAX** (NetKet, jVMC) replacing or wrapping older C++/Fortran cores.

- **Tensor networks / DMRG (1D)** — the most mature cluster. ITensor [@fishman_2020_itensor] (C++ and Julia) and TeNPy [@hauschild_2024_tensor] (Python) are the general-purpose workhorses; quimb [@gray_2018_quimb] adds large-scale contraction; block2 [@zhai_2023_block] targets high-performance / quantum-chemistry DMRG. TensorKit.jl [@devos_2025_tensorkit] is the symmetric-tensor backend under the Julia TN stack. A 2025 review [@sehlstedt_2025_software] surveys the whole DMRG-codes landscape.
- **PEPS / 2D tensor networks** — younger, AD-driven. PEPSKit.jl with the iPEPS-via-AD methodology [@naumann_2023_introduction] (CTMRG + reverse-mode AD) is the current Julia reference.
- **Exact diagonalization** — QuSpin [@weinberg_2016_quspin] (Python) is the most-used for spin/boson/fermion lattices and dynamics; XDiag [@wietek_2025_xdiag] (C++/Julia) pushes large symmetry-adapted ED; HΦ [@kawamura_2017_quantum] adds thermal-pure-quantum finite-T; QuTiP [@johansson_2011_qutip] covers small-system ED and open-system dynamics.
- **Quantum Monte Carlo** — ALPS [@bauer_2011_alps] is the historical meta-framework (loop/SSE/worm). ALF [@bercx_2017_alf] (auxiliary-field/determinant QMC), SmoQyDQMC.jl [@cohenstead_2023_smoqydqmc] (DQMC with electron-phonon), and DSQSS [@motoyama_2020_dsqss] (worldline) cover the main flavors.
- **Variational MC / neural quantum states** — NetKet [@vicentini_2021_netket] and jVMC [@schmitt_2021_jvmc] are the JAX-based NQS toolboxes; mVMC [@misawa_2017_mvmc] is the established many-variable VMC code for fermions.
- **DMFT / impurity solvers** — TRIQS [@parcollet_2015_triqs] is the dominant toolbox; w2dynamics [@wallerberger_2018_dynamics] and iQIST [@huang_2014_open] provide CT-HYB solvers; DCore [@shinaoka_2020_dcore] integrates DMFT with DFT front-ends.

**Temporal trend.** C++/Fortran cores (ALPS 2011, TRIQS 2015, HΦ 2017, mVMC 2017) gave way to Julia/Python+AD packages from ~2020 on (ITensors.jl, NetKet 3, jVMC, PEPSKit.jl, SmoQyDQMC.jl, XDiag, TensorKit.jl), with publication increasingly through SciPost Physics Codebases.

## Key open problems

- **2D / PEPS robustness** — PEPS optimization (gauge fixing, CTMRG convergence, AD stability) is far less turnkey than 1D DMRG; few codes, still research-grade [@naumann_2023_introduction].
- **Interoperability** — codes use incompatible Hamiltonian/lattice/symmetry representations; no common exchange format, so cross-method validation is manual.
- **Fermion-sign-free coverage** — QMC packages remain restricted to sign-problem-free regimes; doped/frustrated models stay out of reach [@bercx_2017_alf].
- **NQS expressivity vs. cost** — neural-quantum-state codes [@vicentini_2021_netket] are flexible but lack the reliability guarantees and convergence diagnostics of variational tensor networks.

## Key bottlenecks

- **Scaling walls** — DMRG bond dimension χ (memory ~χ²L), ED Hilbert-space size, QMC autocorrelation/sign; each method's bottleneck is intrinsic, not just implementation.
- **GPU/HPC maturity gap** — JAX/Julia codes get GPU acceleration cheaply; legacy C++/Fortran cores need substantial porting effort.
- **Sustainability** — many packages are single-group academic projects; long-term maintenance and documentation quality vary widely (the DMRG-landscape review [@sehlstedt_2025_software] flags this directly).
- **Reproducibility/citation hygiene** — several widely-used codes (MPSKit.jl, peps-torch, pomerol) lack a standalone release paper, complicating citation and provenance.
