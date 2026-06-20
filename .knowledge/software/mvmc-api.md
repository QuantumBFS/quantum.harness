# mVMC — API + Examples Reference

**mVMC** (many-variable Variational Monte Carlo) is an open-source solver for interacting **fermion** and **spin** lattice models at zero temperature (Hubbard, Heisenberg, Kondo lattice, and their extensions). It builds a variational wavefunction with **10⁴–10⁵ variational parameters** and optimizes them simultaneously with the **stochastic reconfiguration (SR)** method, then measures observables by Markov-chain Monte Carlo sampling. Because the sampling weight |⟨x|ψ⟩|² is positive-definite, VMC has **no fermion sign problem**.

It is **input-file driven**, not a library: you describe the model in one short text file and run a command-line executable (`vmc.out`). Two interfaces exist:
- **Standard mode** — one ≈10-line `StdFace.def` for canonical models/lattices; mVMC auto-generates everything else.
- **Expert mode** — a set of `*.def` files (listed in a `namelist.def`) defining a fully general one- + two-body Hamiltonian on any lattice.

Language: **C** (core), with **StdFace** helper for input generation and Python helpers in the tutorial samples. External libs: **MPI, BLAS, LAPACK, Pfapack** (Pfaffian eval), **ScaLAPACK** (optional). License: GPL v3. Developed at ISSP, University of Tokyo; UI is designed to interoperate with the ED code **HΦ**.

## Source links

- Manual (master, EN): https://issp-center-dev.github.io/mVMC/doc/master/en/
  - How to use / run: https://issp-center-dev.github.io/mVMC/doc/master/en/start.html
  - Standard-mode input: https://issp-center-dev.github.io/mVMC/doc/master/en/standard.html
  - Tutorial: https://issp-center-dev.github.io/mVMC/doc/master/en/tutorial.html
- GitHub: https://github.com/issp-center-dev/mVMC (samples under `samples/`)
- Tutorial repo: https://github.com/issp-center-dev/mVMC-tutorial
- Release paper: Misawa et al., *Comput. Phys. Commun.* **235**, 447 (2019), arXiv:[1711.11418](https://arxiv.org/abs/1711.11418); local render: `.knowledge/literature/software/1711.11418_mvmc-open-source-software-for-many-variable-variational-mont.md`

---

## 1. Build

```
$ tar xzvf mVMC-x.y.z.tar.gz
$ cmake mVMC-x.y.z/
$ make
```
Or select a compiler config: `cmake -DCONFIG=$Config $PathTomvmc && make`, where `$Config` ∈ `gcc` | `intel` | `sekirei` | `fujitsu`. Without CMake: `bash mVMCconfig.sh gcc-openmpi && make mVMC`. The executable `vmc.out` (and `vmcdry.out`) land in `src/mVMC/`. Pre-installed in MateriApps LIVE!.

Version check: `vmc.out -v` / `vmcdry.out -v`.

---

## 2. Run workflow

mVMC runs in **two stages**: first optimize the variational parameters (`NVMCCalMode = 0`), then re-run to **measure physical observables** with the optimized wavefunction (`NVMCCalMode = 1`). The measurement run is a separate execution — you must edit the mode and run again; the optimization run does **not** produce correlation functions.

### Standard mode (recommended start)
Runs StdFace to generate all input files, then optimizes:
```
$ mpiexec -np <nproc> Path/vmc.out -s StdFace.def
```
Generate the expert `*.def` files **without** computing (dry run):
```
$ Path/vmcdry.out StdFace.def
```

### Expert mode
All `*.def` files prepared (or produced by `vmcdry.out`); listed in `namelist.def`:
```
$ mpiexec -np <nproc> Path/vmc.out -e namelist.def
```

### Two-stage: optimize → measure
1. **Optimize** (`NVMCCalMode = 0`, the default). Produces `output/zqp_opt.dat` (optimized parameters) and `output/zvo_out_*.dat` (energy/variance per step).
2. **Measure**: set `NVMCCalMode = 1` (in `StdFace.def`, uncomment the `//NVMCCalMode = 1` line; or in expert mode edit `modpara.def`), then re-run feeding the optimized parameters:
   ```
   $ Path/vmc.out -e namelist.def output/zqp_opt.dat
   ```
   This produces one- and two-body Green functions (`zvo_cisajs_*.dat`, `zvo_cisajscktalt_*.dat`).
3. **Post-process** (2D): Fourier-transform to structure factors and plot:
   ```
   $ fourier namelist.def geometry.dat
   $ corplot output/zvo_corr.dat
   ```
   `geometry.dat` is auto-generated in Standard mode. Display the cell with `gnuplot lattice.gp`.

### Parallelism
- **MPI**: `mpiexec -np <nproc>` — Monte Carlo samplers are distributed across MPI processes; SR linear solve uses ScaLAPACK (or the matrix-free CG path, `NSRCG=1`).
- **OpenMP**: `export OMP_NUM_THREADS=16` before launching. Hybrid MPI/OpenMP is supported.

---

## 3. Standard-mode parameters (`StdFace.def`)

One `key = value` per line; strings in quotes; `//` comments a line. Spaces around `=` optional. Below: meaning + default/typical value (from manual `standard.html`).

### Model & lattice
| key | meaning | values / notes |
|---|---|---|
| `model` | model family (required) | `"Hubbard"`/`"FermionHubbard"`, `"Spin"`, `"Kondo"`/`"KondoLattice"`. Add `GC` (`"HubbardGC"`, `"SpinGC"`, `"KondoGC"`) for **Sᶻ-non-conserved** (grand-canonical in Sᶻ only; particle number still conserved in v1.0). |
| `lattice` | lattice (required) | `"chain"`, `"square"`/`"tetragonal"`, `"triangular"`, `"honeycomb"`, `"kagome"`, `"ladder"` (names case-insensitive; `"Square Lattice"` etc. also accepted) |

### Geometry
| key | meaning | default |
|---|---|---|
| `L` | length (y / chain direction) | — |
| `W` | width (x direction); ladder width | — (1 for chain) |
| `Height` | 3rd dimension (3D lattices) | 1 |
| `a0W,a0L,a1W,a1L` | unit-cell vectors in fractional coords (tilted/oblique cells, e.g. a 20-site cell) | — |
| `Lsub,Wsub` | **sublattice** size for variational params; e.g. `2×2` reduces fᵢⱼ count from O(Nₛ²)→O(Nₛ) | default = L, W |
| `a0Wsub,a0Lsub,a1Wsub,a1Lsub` | sublattice cell vectors | match primary |
| `phase0,phase1` | boundary hopping phase per direction, **degrees** (e.g. 180 ⇒ anti-periodic) | 0.0 |

The sublattice limits ordering wavevectors to those commensurate with it: a 2×2 sublattice allows only (π,π),(0,π),(π,0),(0,0). Use a larger sublattice (or none) for long-period orders.

### Hamiltonian couplings
| key | meaning | default |
|---|---|---|
| `t`, `t'`, `t''` | 1st/2nd/3rd-neighbor hopping (complex allowed); bond forms `t0,t1,t2` | 0 |
| `U` | on-site Coulomb | 0 |
| `V`, `V'`, `V''` | off-site Coulomb (1st/2nd/3rd); bond forms `V0,V1,V2` | 0 |
| `mu` | chemical potential | 0 |
| `J`, `J'`, `J''` | isotropic exchange (Spin/Kondo). For Kondo, `J` is the Kondo coupling | 0 |
| `Jx,Jy,Jz`, `Jxy,...` | anisotropic exchange; bond/direction forms `J0x … J2zy` (Kitaev etc.) | 0 |
| `h`, `Gamma`, `D` | longitudinal field, transverse field Γ, single-ion anisotropy D (Spin) | 0 |

Hamiltonian forms (paper Eqs. 9–18): Hubbard `H = −μΣnᵢσ − Σtᵢⱼc†c + UΣnᵢ↑nᵢ↓ + ΣVᵢⱼnᵢnⱼ`; Spin `H = −hΣSᶻ − ΓΣSˣ + DΣ(Sᶻ)² − ΣJᵢⱼᵅSᵢᵅSⱼᵅ`; Kondo adds `(J/2)Σ[S⁺c†↓c↑ + S⁻c†↑c↓ + Sᶻ(n↑−n↓)]`.

### Filling / sector
| key | meaning | default |
|---|---|---|
| `nelec` | total electron number (canonical) | — |
| `ncond` | total conduction electrons (alias used in tutorials, esp. Kondo) | — |
| `2Sz` | 2·Sᶻ of the conserved sector | 0 |
| `NUp,NDown` | up/down counts (alternative to nelec+2Sz) | — |

### Variational ansatz & projection controls
| key | meaning | default |
|---|---|---|
| `NMPTrans` | number of momentum/translation projection elements (= cell count to project; 1 = no momentum projection). Larger ⇒ stronger symmetrization, more cost | 1 |
| `NSPGaussLeg` | Gauss–Legendre mesh for the **total-spin (S²) projection** integral over Euler angle β; set >1 to enable spin projection (e.g. 8) | 8 for 2Sz=0 |
| `NSPStot` | target total spin S of the spin projection | 0 |
| `ComplexType` | 0 = real fᵢⱼ, 1 = complex variational parameters (needed for complex hopping / Sz-non-conserved) | 0 (Sz-conserved), 1 (GC) |

### SR optimization
| key | meaning | default |
|---|---|---|
| `NVMCCalMode` | 0 = optimize parameters; 1 = compute Green functions/observables | 0 |
| `NSROptItrStep` | total number of SR optimization steps | 1000 |
| `NSROptItrSmp` | number of final steps over which optimized params are averaged | NSROptItrStep/10 |
| `DSROptStepDt` | SR imaginary-time step Δτ (learning rate). Typical 1e-2 | 0.02 |
| `DSROptStaDel` | diagonal stabilization δ added to S-matrix (Tikhonov) | 0.02 |
| `DSROptRedCut` | truncation cutoff for small S-matrix eigenvalues (redundant-direction cut) | 0.001 |
| `NSRCG` | 1 = matrix-free conjugate-gradient SR solver (no explicit S; needed for ≳10⁵ params, cuts memory) | 0 |
| `NStore` | 1 = store O-matrix products to accelerate two-body expectations | 1 |
| `NLanczosMode` | 0 = none; 1 = first-step power-Lanczos (energy only); 2 = power-Lanczos + correlation functions | 0 |

### Monte Carlo sampling
| key | meaning | default |
|---|---|---|
| `NVMCSample` | number of MC samples for each expectation value | 1000 |
| `NVMCWarmUp` | warm-up (thermalization) sweeps discarded | 10 |
| `NVMCInterval` | sampling interval, in units of Nsite local updates | 1 |

### Output / bookkeeping
| key | meaning | default |
|---|---|---|
| `NDataIdxStart` | starting index for output file numbering (`_001`, ...) | 1 |
| `NDataQtySmp` | number of independent measurement sets (only NVMCCalMode=1); gives statistical error bars | 1 |
| `CDataFileHead` | prefix for correlation/output files | `"zvo"` |
| `CParaFileHead` | prefix for optimized-parameter files | `"zqp"` |
| `RndSeed` | RNG seed (Mersenne twister) | 123456789 |
| `OutputMode` | which Green-function components to output: `"none"` / `"correlation"` (default set) / `"full"` (all) | `"correlation"` |

---

## 4. Variational wavefunction

Form: **|ψ⟩ = P · L · |φ_Pf⟩** (paper Eq. 30) — correlation factors P, quantum-number projectors L, acting on a pair-product (Pfaffian) state.

### Pair-product (Slater/Pfaffian) part `|φ_Pf⟩`
The core fermionic state, parameterized by pair orbitals fᵢⱼ (Eq. 31–32). The Pfaffian generalizes the Slater determinant and can describe fixed-particle-number superconducting states. This is the dominant parameter count, O(Nₛ²), reduced to O(Nₛ) by `Lsub`/`Wsub` sublattices. Enabled by default; expert keyword `Orbital`/`OrbitalAntiParallel` (anti-parallel, the usual 2Sz=0 case), `OrbitalParallel`, or `OrbitalGeneral`. Initial state can be random or from the included **UHF** (unrestricted Hartree–Fock) solver — UHF starts converge much faster (paper Fig. 7).

### Correlation factors `P` (Gutzwiller–Jastrow + doublon-holon)
`P = P_G · P_J · P_d-h^(2) · P_d-h^(4)` (Eq. 55):
- **Gutzwiller** P_G = exp(Σ gᵢ nᵢ↑nᵢ↓) — penalizes/encourages double occupancy. Taking gᵢ = −∞ projects out doublons → describes spin-½ local spins (this is how Heisenberg/Kondo local spins are realized). Expert: `Gutzwiller`.
- **Jastrow** P_J = exp(½ Σ vᵢⱼ(nᵢ−1)(nⱼ−1)) — density-density; long-range Jastrow is essential for Mott insulators. Expert: `Jastrow` (and `SpinJastrow` for vˢᵢⱼ).
- **Doublon-holon** 2-site / 4-site correlation factors. Expert: `DH2`, `DH4`.

### Quantum-number projectors `L`
`L = L_S · L_K · L_P` (Eq. 39): total-spin projector L_S (Gauss–Legendre over Euler β; `NSPGaussLeg`,`NSPStot`), momentum projector L_K and point-group projector L_P (`NMPTrans`; expert `TransSym` / `qptransidx.def`). Projection restores symmetry of the trial state and improves accuracy; cost scales with the number of projection elements.

### RBM correlator (newer versions)
A restricted-Boltzmann-machine correlation factor: visible-layer aᵢσ, hidden-layer hₖ, coupling Wᵢσₖ. Expert keywords `GeneralRBM_PhysLayer`, `GeneralRBM_HiddenLayer`, `GeneralRBM_PhysHidden` (with `In…` initial-value variants).

### Power-Lanczos refinement
`NLanczosMode=1,2` applies |ψ₁⟩ = (1+α₁H)|ψ⟩ and optimizes α₁ by energy minimization — systematically improves accuracy (paper §3.4).

---

## 5. Expert-mode files

Listed in `namelist.def` as `Keyword filename`. By prefixing `In` (e.g. `InOrbital`, `InGutzwiller`, `InJastrow`) you supply **initial** variational-parameter values.

### Basic
| keyword | typical file | defines |
|---|---|---|
| `ModPara` | `modpara.def` | basic params: Nsite, Nelectron, NVMCCalMode, sampling/SR knobs, Lanczos step |
| `LocSpin` | `locspn.def` | locations of localized spins (which sites are spin-only) |

### Hamiltonian (H = H_T + H_I)
| keyword | file | defines |
|---|---|---|
| `Trans` | `trans.def` | transfer integrals tᵢⱼ (H_T) |
| `CoulombIntra` | `coulombintra.def` | on-site U (H_U) |
| `CoulombInter` | `coulombinter.def` | off-site V (H_V) |
| `Hund` | `hund.def` | Ising Hund coupling (H_H) |
| `Exchange` | `exchange.def` | exchange interaction (H_E) |
| `PairHop` | — | pair-hopping (H_P) |
| `InterAll` | — | fully general two-body interaction Iᵢⱼₖₗ (H_I) |

### Pair orbital (Pfaffian)
| keyword | file | defines |
|---|---|---|
| `Orbital` / `OrbitalAntiParallel` | `orbitalidx.def` | anti-parallel-spin pair orbital fᵢⱼ |
| `OrbitalParallel` | — | parallel-spin pair orbital |
| `OrbitalGeneral` | — | general (Sz-non-conserved) pair orbital |

### Correlation-factor indices
| keyword | file | defines |
|---|---|---|
| `Gutzwiller` | `gutzwilleridx.def` | gᵢ to optimize |
| `Jastrow` | `jastrowidx.def` | vᵢⱼ to optimize |
| `SpinJastrow` | `spinjastrow.def` | spin Jastrow vˢᵢⱼ |
| `DH2` / `DH4` | — | 2-/4-site doublon-holon factors |
| `TransSym` | `qptransidx.def` | momentum + point-group projection operators |
| `GeneralRBM_PhysLayer/HiddenLayer/PhysHidden` | — | RBM correlator parameters aᵢσ / hₖ / Wᵢσₖ |

### Observable selection
| keyword | file | defines |
|---|---|---|
| `OneBodyG` | `greenone.def` | components of ⟨c†ᵢc_j⟩ to output |
| `TwoBodyG` | `greentwo.def` | components of ⟨c†ᵢc_j c†ₖc_l⟩ to output |

---

## 6. Output files (`output/`)

| file | contents |
|---|---|
| `zvo_out_NNN.dat` | per-bin: ⟨H⟩ (complex), ⟨H²⟩, variance (⟨H²⟩−⟨H⟩²)/⟨H⟩², ⟨Sᶻ⟩, ⟨(Sᶻ)²⟩ |
| `zqp_opt.dat` | all optimized parameters + ⟨H⟩,⟨H²⟩, then gᵢ, vᵢⱼ, vˢᵢⱼ, α, fᵢⱼ — fed into the measurement run |
| `zvo_var_NNN.dat` | running average ± deviation of parameters and energy at each SR step (convergence trace) |
| `zvo_SRinfo.dat` | SR diagnostics per step: param count, S-matrix dim, diagonal min/max, max parameter change, solver status |
| `zvo_time_NNN.dat` | sampling number, hopping/exchange acceptance ratios, trial counts, timestamps |
| `gutzwiller_opt.dat`, `jastrow_opt.dat`, `orbital_opt.dat` | optimized factors in expert-file format (restartable) |
| `zvo_cisajs_NNN.dat` | one-body Green functions ⟨c†_{iσ₁}c_{jσ₂}⟩: site_i, spin_i, site_j, spin_j, Re, Im |
| `zvo_cisajscktalt_NNN.dat` | two-body Green functions ⟨c†c c†c⟩: 8 site/spin indices, Re, Im |
| `zvo_corr.dat` | Fourier-transformed structure factors (after `fourier`): n_σ(k), N(k), S(k), Sˣʸ(k), Sᶻ(k) |

Convergence check = `zvo_out`/`zvo_var` energy flattening over the last steps + small variance. NDataQtySmp>1 (measurement) gives error bars.

---

## 7. Worked examples (verbatim from `samples/`)

### A. Hubbard, square lattice — optimization (`samples/Standard/Hubbard/square/StdFace.def`)
```
W = 4
L = 2
Wsub = 2
Lsub = 2
model = "FermionHubbard"
lattice = "Tetragonal"
t = 1.0
U = 4.0
nelec = 8
NSROptItrStep = 500
2Sz = 0
//NVMCCalMode = 1
```
Run optimization, then measure:
```
$ mpiexec -np 4 vmc.out -s StdFace.def          # NVMCCalMode=0, optimize
# uncomment NVMCCalMode = 1, then:
$ vmc.out -e namelist.def output/zqp_opt.dat     # measure Green functions
```
The 4×4 half-filled version (`W=4 L=4 nelec=16 NMPTrans=4`) reaches relative energy error η ≈ 10⁻⁴ vs ED; with first-step power-Lanczos the best case hits ~10⁻⁴ (paper Table 3, E/Nₛ = −0.85136 from ED).

### B. Heisenberg, square lattice (`samples/Standard/Spin/HeisenbergSquare/StdFace.def`)
```
L = 4
W = 4
Lsub = 2
Wsub = 2
model = "Spin"
lattice = "tetragonal"
J = 1.0
NSROptItrStep = 200
2Sz = 0
//NVMCCalMode = 1
```
4×4 reference E/Nₛ = −0.70178020 (ED); mVMC(4×4 sublattice) matches to η ≈ 10⁻⁸ (paper Table 4).

### C. Heisenberg chain with full SR/projection knobs (`samples/tutorial_2.1/stan_spin_S0.in`)
```
L = 8
Lsub = 2
model = "Spin"
lattice = "chain"
J = 1
NSPGaussLeg = 8
2Sz = 0
NSPStot = 0
NSROptItrStep =  600
NSROptItrSmp  =  100
NVMCSample    =  1000
DSROptRedCut  = 1e-8
DSROptStaDel  = 1e-2
DSROptStepDt  = 1e-2
//NVMCCalMode = 1
```

### D. 1D Kondo lattice (`samples/Standard/Kondo/Chain/StdFace.def`)
```
L = 4
model = "Kondolattice"
lattice = "chain"
t = 1.0
J = 4.0
nelec = 4
NSROptItrStep = 300
//NVMCCalMode = 1
2Sz = 0
```
Spin-gap workflow (singlet vs triplet sector, `samples/tutorial_2.1/run.sh`): optimize an S=0 and an S=1 input, read `output/zqp_opt.dat` first column (energy) of each, Δs = E₁ − E₀.

### E. Kitaev honeycomb (anisotropic, Sz-non-conserved) (`samples/Standard/Spin/Kitaev/StdFace.def`)
```
W = 2
L = 3
model = "SpinGC"
lattice = "Honeycomb"
J0x = -1.0
J0y =  0.0
J0z =  0.0
J1x =  0.0
J1y = -1.0
J1z =  0.0
J2x =  0.0
J2y =  0.0
J2z = -1.0
nmptrans = 6
NSROptItrStep = 1000
//NVMCCalMode = 1
```
Note `SpinGC` (no Sz conservation) ⇒ complex parameters; bond-direction-dependent `J0,J1,J2` give the Kitaev x/y/z bonds.

### F. Heisenberg chain, tutorial two-stage (manual)
```
L = 16
Lsub = 4
model = "Spin"
lattice = "chain lattice"
J = 1.0
2Sz = 0
NMPtrans = 1
```
```
$ Path/vmcdry.out StdFace.def            # generate locspn.def, trans.def, modpara.def, namelist.def, ...
$ mpiexec -np <n> vmc.out -e namelist.def   # optimize  → output/zqp_opt.dat, zvo_out_001.dat
# edit modpara.def: NVMCCalMode 0 → 1
$ vmc.out -e namelist.def output/zqp_opt.dat   # measure → zvo_cisajs_001.dat, zvo_cisajscktalt_001.dat
```

---

## 8. Pitfalls

- **Two-stage is mandatory.** Optimization (`NVMCCalMode=0`) yields **no** correlation functions. You must set `NVMCCalMode=1` and re-run feeding `output/zqp_opt.dat`. Forgetting this = "where are my observables?"
- **SR stabilization.** If parameters diverge or energy oscillates: lower `DSROptStepDt` (Δτ), raise `DSROptStaDel` (diagonal shift δ), or raise `DSROptRedCut` to trim redundant directions. Too-aggressive `DSROptRedCut` can also wash out real directions — tune both.
- **Sample count vs noise.** SR gradients are noisy; too-small `NVMCSample` makes the S-matrix ill-conditioned and stalls optimization. Increase `NVMCSample`, then average over `NSROptItrSmp` final steps. For final observables, use `NDataQtySmp>1` to get error bars.
- **Initial state matters.** Random fᵢⱼ converges slowly; seed from the included UHF solver for much faster, more reliable convergence (paper Fig. 7).
- **Sublattice constrains order.** `Lsub`/`Wsub` cuts parameters but restricts allowed ordering wavevectors to those commensurate with the sublattice (2×2 ⇒ only (π,π),(0,π),(π,0),(0,0)). Use a larger sublattice / none to test long-period order; expect higher cost and slight overestimate of the order parameter at large L.
- **Complex vs real.** Complex hopping, Sz-non-conserved (`*GC`), or twisted boundaries require `ComplexType=1` (doubles parameter memory). Real (`ComplexType=0`) is faster when the physics allows it.
- **Projection cost.** Momentum (`NMPTrans`) and total-spin (`NSPGaussLeg`,`NSPStot`) projection improve accuracy but multiply sampling cost by the number of projection elements / quadrature points. Start modest, increase if accuracy is insufficient.
- **Memory for many parameters.** Explicit SR stores the S-matrix, O(N_p²). For ≳10⁵ parameters set `NSRCG=1` (matrix-free CG) to fit in memory; SR-CG is favorable when N_MC < N_p.
- **Power-Lanczos near-exact states.** For tiny systems where the variational state is already near-exact (variance ≈ 0), `NLanczosMode` becomes numerically unstable — skip it there.
