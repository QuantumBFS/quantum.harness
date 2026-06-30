# Method Zoo — Index

36 quantum-many-body computational-method cards, one per distinct method in
`.knowledge/method-survey.md`. Each `METHOD.md` carries a structured **M1–M14**
property table (axes defined in `../method-property-checklist.md`), cost & accuracy
classes, recommended models, one key reference, and verified benchmarks.

- **Axis schema:** `../method-property-checklist.md` (M1–M14, four groups).
- **Card template:** `_TEMPLATE.md`.
- **Shared bibliography:** `ref.bib` (reused entries carry their
  `../literature/ref.bib` cite keys verbatim; fresh downloads appended).
- **Prose catalog & cost derivations:** `../method-survey.md`.
- **Model → method gate:** `../method-property-map.md`.

Accuracy class abbreviations: **exact** = numerically exact (to machine/statistical
error); **upper** = variational upper bound; **lower** = certified lower bound;
**controlled** = systematically improvable (convergence knob); **uncontrolled** =
no internal convergence parameter; **(stoch)** = carries statistical error bars.

## 1. Exact methods
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Exact diagonalization — full | `ed-full` | exact | `/method-ed` | [@sandvik_2010_computational] |
| Exact diagonalization — Lanczos/Krylov | `ed-lanczos` | exact | `/method-ed` | [@sandvik_2010_computational] |
| Finite-T Lanczos / thermal pure states | `ftlm-tpq` | controlled (stoch) | `/method-ed` | [@jaklic_1994_lanczos] |
| Kernel polynomial method | `kpm` | controlled (stoch) | `/method-ed` | [@weisse_2006_kernel] |
| Full configuration interaction | `fci` | exact | `/method-ed` | [@booth_2009_fermion] |

## 2. Classical Monte Carlo & critical RG
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Metropolis Monte Carlo | `metropolis-mc` | exact (stoch) | classical MC (no dedicated skill) | [@sandvik_2010_computational] |
| Cluster MC / Wang–Landau / parallel tempering | `cluster-mc` | exact (stoch) | classical MC (no dedicated skill) | [@wolff_1989_collective] |
| Monte Carlo renormalization group | `mcrg` | controlled (stoch) | `/method-mcrg` | [@wu_2017_variational] |

## 3. Ground-state tensor networks
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Density-matrix renormalization group | `dmrg` | controlled | `/method-mps` | [@schollwoeck_2010_density] |
| Projected entangled pair states | `peps-ipeps` | controlled | `/method-peps` | [@naumann_2023_introduction] |
| Tensor RG (TRG / HOTRG) | `trg-hotrg` | controlled | `/method-peps` | [@xie_2012_coarse] |
| Multiscale entanglement renormalization | `mera` | controlled | specialized (no dedicated skill) | [@evenbly_2007_algorithms] |

## 4. Tensor-network dynamics & finite-T
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Time-evolving block decimation | `tebd` | controlled | `/method-mps` | [@vidal_2003_efficient] |
| Time-dependent variational principle | `tdvp` | controlled | `/method-mps` | [@haegeman_2016_unifying] |
| MPS finite-T (purification / METTS) | `mps-finite-t` | controlled (+stoch) | `/method-mps` | [@paeckel_2019_timeevolution] |
| Linearized / exponential thermal tensor RG | `ltrg-xtrg` | controlled | `/method-ltrg` | [@chen_2018_exponential] |
| DMRG-X (excited / MBL eigenstates) | `dmrg-x` | controlled | `/method-mps` | [@khemani_2016_obtaining] |

## 5. Quantum Monte Carlo
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Variational MC & neural quantum states | `vmc-nqs` | upper (stoch) | `/method-vmc` | [@carleo_2016_solving] |
| Stochastic series expansion / worldline | `sse` | exact (stoch) | `/method-qmc` | [@syljuasen_2002_quantum] |
| Determinant QMC (BSS) | `dqmc` | exact (stoch) | `/method-qmc` | [@bercx_2017_alf] |
| Auxiliary-field QMC / constrained-path | `afqmc-cpmc` | controlled (stoch) | `/method-qmc` | [@zhang_2019_auxiliary] |
| Projector / diffusion MC + fixed-node | `dmc-gfmc` | controlled (stoch) | `/method-qmc` | [@becca_2017_quantum] |
| Path-integral Monte Carlo | `pimc` | exact (stoch) | `/method-qmc` | [@ceperley_1995_path] |
| Diagrammatic Monte Carlo | `diagmc` | controlled (stoch) | `/method-qmc` | [@prokofev_1998_polaron] |

## 6. Quantum embedding & perturbative
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Dynamical mean-field theory | `dmft` | controlled (exact `Z→∞`) | outside core harness | [@georges_1996_dynamical] |
| Density-matrix embedding | `dmet` | controlled | outside core harness | [@knizia_2012_density] |
| Numerical renormalization group | `nrg` | controlled | outside core harness | [@bulla_2007_numerical] |
| Functional renormalization group | `frg` | controlled | outside core harness | [@metzner_2011_functional] |
| Coupled cluster | `coupled-cluster` | controlled | outside core harness | [@bartlett_2007_coupled] |
| Many-body perturbation theory (GW/RPA/GF2) | `mbpt-gw` | uncontrolled | outside core harness | [@golze_2019_gw] |

## 7. Mean-field, circuit, certified
| Method | Card | Accuracy | Owning skill | Key ref |
|---|---|---|---|---|
| Hartree–Fock / UHF (+ DFT baseline) | `hartree-fock` | uncontrolled | `/method-mf` | [@arovas_2022_hubbard] |
| Linear spin-wave / large-S | `spin-wave` | controlled (`1/S`) | `/method-mf` | [@toth_2015_linear] |
| Slave-particle / parton mean field | `slave-particle` | uncontrolled (MF) | `/method-mf` | [@kotliar_1986_new] |
| Cluster mean field / VCA | `vca-cluster-mf` | controlled | `/method-mf` | [@maier_2004_quantum] |
| Quantum-circuit simulation | `circuit-sim` | exact / controlled | `/method-qcs` | [@markov_2008_simulating] |
| Certified bounds — SDP / NCTSSOS | `sdp-nctssos` | lower (certified) | `/method-polyopt` | [@wang_2024_certifying] |

---

**References (55 entries):** see `ref.bib`. Reference full text is rendered next to
each card (`<id>_<slug>.md`) for fresh downloads, or linked into
`../literature/<family>/` for reused entries. Bib stubs (no reachable PDF):
`fci` (Booth et al., paywalled), `cluster-mc` (Wolff PRL / Swendsen–Wang PRL),
`coupled-cluster` (Bartlett–Musiał RMP), `slave-particle` (Kotliar–Ruckenstein PRL).
