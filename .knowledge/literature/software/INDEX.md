# software — many-body computation software catalog

Built by `/survey` (sci-brain) on 2026-06-20 — "popular open-source many-body computation software". Strategy: landscape mapping (WebSearch); full text fetched + rendered via `/download-ref`. Cite keys resolve in `../ref.bib` (tagged `keywords = {..., software}`). `.raw/` (PDFs, S2 JSON) and `.figures/` are gitignored.

## Tensor networks — 1D / MPS

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **ITensor / ITensors.jl** | DMRG/MPS | C++ & Julia | `fishman_2020_itensor` | 2007.14822 | 10.21468/SciPostPhysCodeb.4 | [md](2007.14822_the-itensor-software-library-for-tensor-network-calculations.md) |
| **TeNPy** | DMRG/TEBD/MPS | Python | `hauschild_2024_tensor` | 2408.02010 | 10.21468/SciPostPhysCodeb.41 | [md](2408.02010_tensor-network-python-tenpy-version-1.md) |
| **quimb** | Tensor networks | Python | `gray_2018_quimb` | — | 10.21105/joss.00819 | [md](10-21105-joss-00819.md) |
| **block2** | DMRG/MPS | C++ & Python | `zhai_2023_block` | 2310.03920 | 10.1063/5.0180424 | [md](2310.03920_block2-a-comprehensive-open-source-framework-to-develop-and.md) |
| **TensorKit.jl** | TN backend | Julia | `devos_2025_tensorkit` | 2508.10076 | — | [md](2508.10076_tensorkit-jl-a-julia-package-for-large-scale-tensor-computat.md) |

- **ITensor / ITensors.jl** — General-purpose tensor-network library (DMRG, MPS/MPO).
- **TeNPy** — Tensor-network Python: DMRG, TEBD for 1D/quasi-2D.
- **quimb** — Tensor networks + quantum info; large-scale contraction.
- **block2** — High-performance DMRG; quantum-chemistry, finite-T, dynamics.
- **TensorKit.jl** — Symmetric tensor backend under MPSKit/PEPSKit.

## PEPS / 2D tensor networks

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **PEPSKit.jl** | PEPS/2D TN | Julia | `naumann_2023_introduction` | 2308.12358 | 10.21468/SciPostPhysLectNotes.86 | [md](2308.12358_an-introduction-to-infinite-projected-entangled-pair-state-m.md) |

- **PEPSKit.jl** — Infinite PEPS via CTMRG + AD variational optimization.

## Exact diagonalization

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **QuSpin** | Exact diagonalization | Python | `weinberg_2016_quspin` | 1610.03042 | 10.21468/SciPostPhys.2.1.003 | [md](1610.03042_quspin-a-python-package-for-dynamics-and-exact-diagonalisati.md) |
| **XDiag** | Exact diagonalization | C++ & Julia | `wietek_2025_xdiag` | 2505.02901 | 10.21468/SciPostPhysCodeb.70 | [md](2505.02901_xdiag-exact-diagonalization-for-quantum-many-body-systems.md) |
| **HPhi (HΦ)** | ED / TPQ | C++ | `kawamura_2017_quantum` | 1703.03637 | 10.1016/j.cpc.2017.04.006 | [md](1703.03637_quantum-lattice-model-solver-h.md) |
| **QuTiP** | ED / open systems | Python | `johansson_2011_qutip` | 1110.0573 | 10.1016/j.cpc.2012.02.021 | [md](1110.0573_qutip-an-open-source-python-framework-for-the-dynamics-of-op.md) |

- **QuSpin** — ED and quantum dynamics of spin/boson/fermion lattices.
- **XDiag** — Large-scale symmetry-adapted ED with sublattice coding.
- **HPhi (HΦ)** — Lanczos ED, full diag, thermal-pure-quantum states.
- **QuTiP** — Open-system dynamics; small-system ED/Hamiltonians.

## Quantum Monte Carlo

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **ALPS** | QMC / meta-framework | C++ | `bauer_2011_alps` | 1101.2646 | 10.1088/1742-5468/2011/05/P05001 | [md](1101.2646_the-alps-project-release-2-0-open-source-software-for-strong.md) |
| **ALF** | Auxiliary-field QMC | Fortran | `bercx_2017_alf` | 1704.00131 | — | [md](1704.00131_the-alf-algorithms-for-lattice-fermions-project-release-1-0.md) |
| **SmoQyDQMC.jl** | Determinant QMC | Julia | `cohenstead_2023_smoqydqmc` | 2311.09395 | 10.21468/SciPostPhysCodeb.29 | [md](2311.09395_smoqydqmc-jl-a-flexible-implementation-of-determinant-quantu.md) |
| **DSQSS** | Worldline QMC | C++ & Python | `motoyama_2020_dsqss` | 2007.11329 | 10.1016/j.cpc.2021.107944 | [md](2007.11329_dsqss-discrete-space-quantum-systems-solver.md) |

- **ALPS** — Lattice QMC (loop/SSE/worm), ED, DMRG framework.
- **ALF** — Finite-T & projective determinant (auxiliary-field) QMC.
- **SmoQyDQMC.jl** — DQMC for Hubbard + electron-phonon (incl. anharmonic).
- **DSQSS** — Path-integral / directed-loop QMC for spins & Bose-Hubbard.

## Variational MC / neural quantum states

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **NetKet** | VMC / NQS | Python (JAX) | `vicentini_2021_netket` | 2112.10526 | 10.21468/SciPostPhysCodeb.7 | [md](2112.10526_netket-3-machine-learning-toolbox-for-many-body-quantum-syst.md) |
| **jVMC** | VMC / NQS | Python (JAX) | `schmitt_2021_jvmc` | 2108.03409 | 10.21468/SciPostPhysCodeb.2 | [md](2108.03409_jvmc-versatile-and-performant-variational-monte-carlo-levera.md) |
| **mVMC** | Many-variable VMC | C & Fortran | `misawa_2017_mvmc` | 1711.11418 | 10.1016/j.cpc.2018.08.014 | [md](1711.11418_mvmc-open-source-software-for-many-variable-variational-mont.md) |

- **NetKet** — Neural-quantum-state VMC toolbox.
- **jVMC** — GPU/AD VMC for NQS (ground state + dynamics).
- **mVMC** — VMC for fermions with stochastic reconfiguration.

## DMFT / impurity solvers

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **TRIQS** | DMFT toolbox | C++ & Python | `parcollet_2015_triqs` | 1504.01952 | 10.1016/j.cpc.2015.04.023 | [md](1504.01952_triqs-a-toolbox-for-research-on-interacting-quantum-systems.md) |
| **w2dynamics** | CT-HYB / DMFT | Python & Fortran | `wallerberger_2018_dynamics` | 1801.10209 | 10.1016/j.cpc.2018.09.007 | [md](1801.10209_w2dynamics-local-one-and-two-particle-quantities-from-dynami.md) |
| **iQIST** | CT-HYB impurity | Fortran & Python | `huang_2014_open` | 1409.7573 | 10.1016/j.cpc.2015.04.020 | [md](1409.7573_an-open-source-continuous-time-quantum-monte-carlo-impurity.md) |
| **DCore** | Integrated DMFT | Python | `shinaoka_2020_dcore` | 2007.00901 | 10.21468/SciPostPhys.10.5.117 | [md](2007.00901_dcore-integrated-dmft-software-for-correlated-electrons.md) |

- **TRIQS** — Toolbox for interacting quantum systems / DMFT.
- **w2dynamics** — CT-HYB continuous-time QMC impurity solver + DMFT loop.
- **iQIST** — CT-HYB and Hirsch-Fye QMC impurity solvers.
- **DCore** — Integrated DMFT built on TRIQS with DFT interfaces.

## Meta-reference

| Software | Method | Language | Cite key | arXiv | DOI | Full text |
|---|---|---|---|---|---|:---:|
| **DMRG software landscape (review)** | Meta-reference | — | `sehlstedt_2025_software` | 2506.12629 | 10.1016/j.cpc.2025.109592 | [md](2506.12629_the-software-landscape-for-the-density-matrix-renormalizatio.md) |

- **DMRG software landscape (review)** — Recent survey of the DMRG-codes ecosystem.
