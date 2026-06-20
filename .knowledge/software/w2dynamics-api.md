# w2dynamics — API & Usage Reference

Multi-orbital continuous-time hybridization-expansion quantum Monte Carlo (CT-HYB) impurity solver with a full dynamical-mean-field-theory (DMFT) self-consistency loop. Computes one- and two-particle Green's functions for the Anderson impurity model and Hubbard-like lattice models. Python + Fortran 90 + C++11; configuration-file driven (`Parameters.in`), HDF5 output.

- **Repo:** <https://github.com/w2dynamics/w2dynamics>
- **Wiki / tutorials:** <https://github.com/w2dynamics/w2dynamics/wiki> · <https://github.com/w2dynamics/w2dynamics/wiki/Tutorials>
- **Release paper (primary docs):** Wallerberger et al., *Comput. Phys. Commun.* **235**, 388 (2018), arXiv:1801.10209, doi:10.1016/j.cpc.2018.09.007
- **License:** GPLv3. Mailing list: `w2dynamics-users@list.tuwien.ac.at`

> Provenance: parameter names/defaults below are *Literal* from the repo's `w2dyn/auxiliaries/configspec` (the file holding every parameter's type + default) and from the paper's Tables 1, 3, 4. Config examples are verbatim from the wiki tutorials. Verify defaults against your installed version's `configspec`, since the parameter set evolves between releases.

---

## 1. What it does

Solves the generalized single-impurity Anderson model (SIAM)

  H = H_loc[c,c†] + H_hyb[c,c†,f,f†] + H_bath[f,f†]

by stochastically sampling the hybridization expansion of the partition function Z in powers of the hybridization Δ (CT-HYB). The local trace uses a matrix-vector technique in the eigenbasis of H_loc with superstate / state sampling. On top of the solver, a Python DMFT loop maps a Hubbard-like lattice onto a self-consistent SIAM:

  G_loc(iν) = (1/N_k) Σ_k [ (iν+μ)1 − H(k) − Σ(iν) − Σ_DC ]⁻¹     (k-integrated Dyson eq.)

Distinctive features: arbitrary one- and two-particle (4-point) Green's functions, local susceptibilities and vertices via **worm sampling**, improved (symmetric) estimators for Σ, retarded interactions (screening), off-diagonal hybridization, multiple inequivalent atoms, and a wannier90 / DFT interface (DFT+DMFT).

---

## 2. Install & run workflow

### Build (CMake)

```
$ git clone https://github.com/w2dynamics/w2dynamics.git
$ mkdir build && cd build
$ cmake .. [FURTHER_FLAGS_GO_HERE]
$ make
$ make test                                   # optional unit tests
$ cmake .. -DCMAKE_INSTALL_PREFIX=/path && make install   # optional
```
Requirements: Python ≥2.6, Fortran 90 + C++11 compilers, CMake ≥3.18, BLAS, LAPACK. Auto-installed if missing: numpy ≥1.10, scipy ≥0.10, h5py, mpi4py, configobj, NFFT3/FFTW3, HDF5. Hint flags like `-DNFFT_ROOT=/path`, `-DPYTHON_EXECUTABLE=/path/to/python` when auto-detection fails (Python 3 is preferred over 2 if both present).

### Entry points

| Command | Purpose |
|---|---|
| `DMFT.py [Parameters.in]` | Run the DMFT self-consistency loop (the usual driver). |
| `cthyb [Parameters.in]` | Single-shot impurity solve (no outer self-consistency). |
| `Maxent.py` | Maximum-entropy analytic continuation (G(iν)/G(τ) → spectral function A(ω)). |
| `hgrep (file\|latest) quantity [index ...]` | Extract / tabulate / plot quantities from the HDF5 output. |
| `cfg_converter.py` | Convert legacy config files to current format. |
| `cprun` | Copy input files into another directory. |

`Parameters.in` is the default config name in the CWD; pass another path as the argument. MPI parallelization (Monte Carlo is trivially parallel — error bars are computed across cores):

```
$ DMFT.py [Parameters.in]
$ cthyb [Parameters.in]
$ mpiexec -n 10 DMFT.py [Parameters.in]
$ mpirun  -np 4  DMFT.py
```

Output is a self-describing HDF5 archive named `RunIdentifier-Timestamp.hdf5` (prefix set by `FileNamePrefix`). Read it with `hgrep`, jupyter, MATLAB, or `h5py`.

---

## 3. The `Parameters.in` config file

INI-style `key = value` (parsed by `configobj`; defaults live in `w2dyn/auxiliaries/configspec`). Three sections: **`[General]`** (lattice, DMFT loop, μ, β), **`[Atoms]`** with one numbered subsection `[[1]]`, `[[2]]`, … per inequivalent atom (interaction + orbital count), and **`[QMC]`** (Monte Carlo solver controls). Optional `[CI]` (discrete-bath fit / config-interaction) and `[EDIPACK]` (ED solver backend) sections also exist.

### 3.1 `[General]` — lattice, DMFT loop, chemical potential

| Parameter | Default | Meaning / typical |
|---|---|---|
| `DOS` | `Bethe` | Lattice / bath source. `Bethe` (semicircular DOS, set `half-bandwidth`); `ReadIn` (read H(k) from `HkFile`, spin-independent); `ReadInSO` (spin-dependent H(k), e.g. with field/SO); `flat`/`semicirc`; `readDelta` (read Δ from `deltatau`/`deltaiw`); `EDcheck` (discrete bath `epsk`,`vk`); `nano` (finite leads); `Bethe_in_tau`. |
| `HkFile` | `None` | Path to wannier90-format H(k) (needed for `ReadIn`/`ReadInSO`). |
| `beta` | `100.` | Inverse temperature β (1/T). |
| `mu` | `0.0` | Chemical potential (used directly when `EPSN=0`). |
| `EPSN` | `0.0` | μ-search tolerance vs `totdens`; `0` → fixed μ (no search). |
| `totdens` | `0.` | Target total electrons per atom (used when `EPSN>0`). |
| `mu_search` | `nloc` | μ-search strategy (`nloc` or `kappa`). |
| `half-bandwidth` | `2.` | Half-bandwidth D of the Bethe DOS. |
| `NAt` | `1` | Number of atoms per unit cell = number of `[[…]]` subsections. |
| `magnetism` | `para` | `para` (spin-symmetrized / spin-averaged), `ferro` (no spin averaging), `antiferro`. |
| `DMFTsteps` | `1` | Number of DMFT self-consistency iterations. |
| `StatisticSteps` | `0` | Extra "statistics" iterations (re-solve at fixed Σ for better stats). |
| `WormSteps` | `0` | Number of worm-sampling iterations (for 2-particle quantities). |
| `mixing` | `0.0` | Self-energy mixing: 0 → use 100% new Σ, 1 → keep old Σ. Raise (e.g. 0.5–0.75) to stabilize oscillating loops. |
| `mixing_strategy` | `linear` | `linear` or `diis` (Pulay/DIIS acceleration). |
| `SelfEnergy` | `dyson` | How Σ is obtained: `dyson`, `improved`, `improved_worm`, `symmetric_improved_worm`. |
| `FTType` | `legendre` | Fourier transform of G: `legendre`, `plain`, `none`, `none_worm`. |
| `FileNamePrefix` | `''` | Output filename prefix (timestamp appended). |
| `readold` | `0` | Continue from iteration n of an old file; `0` new run, `-1` last iteration. |
| `fileold` | `None` | HDF5 file to continue from. |
| `dc` | `anisimov` | Double-counting scheme for DFT+DMFT: `anisimov`,`fll`,`amf`,`trace`,`siginfbar`,`sigzerobar`. |
| `equiv`/`EPSEQ` | `None`/`1e-6` | Equivalence pattern / tolerance for auto-detecting equivalent atoms. |
| `solver` | `CTHYB` | Impurity solver backend: `CTHYB` or `EDIPACK` (exact diagonalization). |
| `GW`, `Uw` | `0` | Enable GW self-energy / dynamical U(ω) interfaces (experimental). |

### 3.2 `[Atoms]` → `[[i]]` — interaction & orbitals (per inequivalent atom)

| Parameter | Default | Meaning / typical |
|---|---|---|
| `Nd` | `None` | Number of correlated bands (orbitals) on this atom — required. |
| `Np`, `Nlig` | `0` | Number of uncorrelated / ligand ("p") orbitals (non-interacting, zero Σ). |
| `Hamiltonian` | `Density` | Local interaction parametrization (see table below). |
| `Udd` | `0.0` | Intra-orbital Hubbard repulsion U. |
| `Jdd` | `0.0` | Hund's coupling J. (Including J in `Density` breaks SU(2).) |
| `Vdd` | `0.0` | Inter-orbital interaction V. |
| `F0`,`F2`,`F4`(`,F6`) | `None` | Slater integrals (for `Hamiltonian=Coulomb`, full d-shell). |
| `umatrix` | `u_matrix.dat` | Path to U-tensor for `ReadUmatrix`/`ReadNormalUmatrix`. |
| `QuantumNumbers` | `auto` | Conserved quantities → block structure of H_loc (see §6). |
| `crystalfield` | `None` | Band centers / crystal-field splittings. |
| `Upp,Jpp,Vpp,Udp,Jdp` | `0.0` | d-p / p-p interactions (only with `DOS=ReadIn`, explicit ligands). |
| `Screening` | `0` | Enable retarded interaction W(τ) (density-density only). |

**Interaction types (`Hamiltonian=`)** — from paper Table 1:

| Value | Params | Form | Conserves |
|---|---|---|---|
| `Density` | Udd, Jdd, Vdd | Density-density only: U n↑n↓ + (V−Jδ) n n. Breaks SU(2) when J≠0. | N, Sz, n_iσ (use `QuantumNumbers = Nt Szt Azt`) |
| `Kanamori` | Udd, Jdd, Vdd | Density-density + spin-flip + pair-hopping (rotationally invariant). | N, Sz, PS (use `QuantumNumbers = Nt Szt Qzt`) |
| `Coulomb` | F0, F2, F4 | Full d-shell Slater–Coulomb in spherical harmonics → crystal-field basis. | N, Sz, Lz |
| `ReadNormalUmatrix` | `umatrix` | Read U_ijkl (4 orbital indices), spin-independent / orbital-dependent dd. | N, Sz |
| `ReadUmatrix` | `umatrix` | Read U with 4 orbital + 4 spin indices (general, e.g. cRPA). | N, Sz |

### 3.3 `[QMC]` — Monte Carlo solver controls

| Parameter | Default | Meaning / typical |
|---|---|---|
| `Nwarmups` | `10000` | Thermalization (warm-up) steps discarded before measuring. Set ~10–100× NCorr; **too small → wrong results**. Use 1e5–3e7 in production. |
| `Nmeas` | `10000` | Number of measurement steps. Statistical error ∝ 1/√Nmeas. 1e5–1e7 typical. |
| `NCorr` | `100` | Sweeps between successive measurements (decorrelation). Aim ≈ renewal time ⟨k⟩/R_rem. Set badly → only perf loss. |
| `NSeed` | `43890` | Random-number seed. |
| `NBin` | `1` | Bins per core. |
| `Ntau` | `1000` | Imaginary-time bins for the 1-particle G(τ). |
| `Nftau` | `5000` | τ-points for the hybridization function (require Nftau > 2·Niw). |
| `Niw` | `2000` | Number of positive Matsubara frequencies for G(iν). |
| `NLegMax` | `100` | Number of Legendre coefficients measured for G. |
| `NLegOrder` | `100` | Legendre order used in the DMFT loop. |
| `TaudiffMax` | `-1.0` | Sliding-window max τ-distance for pair insert/remove; `-1` → auto-calibrate. |
| `PercentageGlobalMove` | `0.005` | Fraction of attempted global moves (spin-flip / symmetry / random permutations) — restores degeneracies across phase-space barriers. |
| `PercentageTauShiftMove` | `0.005` | Fraction of τ-shift moves. |
| `MeasDensityMatrix` | `1` | Measure 1- and 2-particle density matrices (→ `rho1`, `rho2`). |
| `MeasGiw` | `0` | Direct Matsubara G measurement (`giw-meas`). |
| `MeasSusz` | `0` | Measure local spin/charge susceptibility (`sztau-sz0`, `ntau-n0`). |
| `Gtau_mid_step` | `0` | Per-step τ∈[0.4β,0.6β] G-average (`gtau-mid-step`) — thermalization check. |
| `Eigenbasis` | `1` | Work in the eigenbasis of H_loc (matrix-vector trace). |
| `statesampling` | `0` | Sample individual eigenstates (faster, may affect sign) vs superstate (default). |
| `offdiag` | `0` | Allow real off-diagonal hybridization / hoppings (inter-orbital). |
| `flavourchange_moves` | `0` | Use flavor-change moves instead of 4-operator moves (off-diag + Kanamori). |
| `Percentage4OperatorMove` | `0.0` | Fraction of 4-operator moves (off-diag + non-density-density interactions). |
| `segment` | `0` | Segment representation (density-density only; fast). |

---

## 4. Two-particle quantities (susceptibilities & vertex)

Two ways to measure the 4-point Green's function G⁽²⁾(iν,iν',iω) and related vertices:

- **Partition-function ("Z") sampling** — set `FourPnt=4` and `N4iwf`,`N4iwb` (output `g4iw`). Limited to diagrams present in the Z-expansion.
- **Worm sampling** (recommended for general / multi-orbital, insulating, off-diagonal cases) — set `WormSteps>0` in `[General]`, then in `[QMC]` enable the worm estimator flag and the box sizes. Worm reaches *all* components, including those absent in Z-sampling, and gives improved estimators and vertex asymptotics.

Key worm controls (`[QMC]`): `PercentageWormInsert` (worm insert proposal, e.g. 0.3), `PercentageWormReplace` (0.1), `WormEta`/`WormSearchEta` (balance worm↔Z space; `WormSearchEta=1` auto-tunes), `Nwarmups2Plus` (warm-up for the eta search), `WormComponents` (list of flavor components to sample; omit → all (2·nbands)⁴), `WormPHConvention`, `G4ph`/`G4pp` (which Fourier transform of `g4iw-worm` to do — particle-hole / particle-particle).

Worm estimator flags (each `=1` enables one observable; from paper Table 3 and `configspec`):

| Flag | Output quantity |
|---|---|
| `WormMeasGiw` / `WormMeasGtau` | 1P G(iν) / G(τ) in worm space (`giw-worm`,`gtau-worm`). |
| `WormMeasGSigmaiw` | Improved estimator ΣG for the self-energy (`gsigmaiw-worm`). |
| `WormMeasG4iw` (+ `FourPnt=8`) | Full 2P G⁽²⁾(iν,iν',iω), ph (`g4iw-worm`). Sizes `N4iwf`,`N4iwb`. |
| `WormMeasG4iw1` / `WormMeasG4iw1PP` | One-frequency 2P GF, ph / pp (`N2iwb`). |
| `WormMeasG4iw2` / `WormMeasG4iw2PP` | Two-frequency 2P GF, ph / pp (`N3iwf`,`N3iwb`). |
| `WormMeasH4iw` | 4-point improved estimator H (`h4iw-worm`). |
| `WormMeasP2iwPH/PP`, `WormMeasP3iwPH/PP` | 2-/3-legged equal-time GFs (susceptibility building blocks). |
| `WormMeasQQ`, `WormMeasQQQQ`, … | Symmetric improved estimators for 1P/2P GF. |

For local DMFT susceptibilities without worm, use `MeasSusz=1` (spin/charge: `sztau-sz0`, `ntau-n0`).

---

## 5. Output / observables (HDF5 layout)

The archive (read via `h5py`, `hgrep`, jupyter) has **hidden meta-groups** and **iteration groups** (paper Tables 4–5):

- Hidden: `.config` (all parameters used), `.environment` (shell env / scheduler), `.axes` (shared `iw`, `tau` grids), `.quantities` (metadata linking quantities → axes).
- Iterations: `start` (non-interacting / initial data), `dmft-001`,`dmft-002`,… (each DMFT iteration), `stat-…` (statistics iterations), `worm-…` (worm iterations), `finish` (HDF5-link to last iteration).
- Inside each iteration: per-inequivalent-atom subgroups `ineq-001`,`ineq-002`,… holding the impurity quantities as `value` (and `error`).

Common quantities and their group path `iteration/ineq-XXX/<name>/value`:

| Quantity name | Meaning |
|---|---|
| `giw`, `gtau` | Impurity Green's function G(iν), G(τ). |
| `siw` | Impurity self-energy Σ(iν). |
| `gleg` | Legendre-basis G. |
| `glocnew`, `g0iw` | Local lattice G and Weiss field G₀(iν). |
| `rho1`, `rho2` | 1- and 2-particle density matrices (occupations / correlations). |
| `occ`, `imp-electrons` | Orbital occupations / impurity electron count. |
| `doubleocc` | Double occupancy ⟨n↑n↓⟩. |
| `mu` | Chemical potential per iteration. |
| `sign` | Average Monte Carlo sign (sign problem diagnostic). |
| `hist`, `hist-glob` | Expansion-order histogram (⟨k⟩). |
| `accept-ins`, `accept-rem` | Acceptance rates (for NCorr tuning). |
| `sztau-sz0`, `ntau-n0` | Spin / density susceptibilities χ(τ) (with `MeasSusz=1`). |
| `g4iw`, `g4iw-worm`, `h4iw-worm` | Two-particle Green's functions / improved estimators. |

### `hgrep` usage

```
$ hgrep [options] (file|latest) quantity [[index] ...]
$ hgrep latest siw 1 1 1 1          # Σ(iν): iter 1, atom 1, orbital 1, spin 1
$ hgrep -p test.hdf5 siw 1:3 1 1,4 1 0:20 field=value-im
#                         ^iters ^atom ^orbs ^spin ^iν-range  ^imag part only
$ hgrep latest mu                   # chemical potential per iteration
$ hgrep latest imp-electrons        # occupation + error per iteration
```
`latest` picks the newest HDF5 in the CWD. FORTRAN-style ranges (`1:3`, `1,4`) supported. `-p` auto-plots. `-1` as the iteration index selects the last/`finish` iteration. See `hgrep.man`. For 2-particle quantities `hgrep` is limited — use `h5py` directly.

### Reading with h5py

```python
import h5py
f  = h5py.File("2p-2018-07-12-Thu-16-18-48.hdf5", "r")
g4 = f["worm-001/ineq-001/g4iw-worm/00001/value"].value   # one 2P component
# discover paths interactively: f["dmft-001/ineq-001"].items()
```

---

## 6. Quantum numbers (block structure of H_loc)

`QuantumNumbers` (per atom) picks conserved quantities that block-diagonalize H_loc; smaller largest block → cheaper local trace. Tokens: `Nt` (total occupation), `Szt` (Sz), `Azt` (occupation per spin-orbital — density-density), `Qzt` (PS / singly-occupiedness per orbital — Kanamori), `Lzt` (orbital Lz — Coulomb), `Jzt` (total Jz), `All`/`auto` (automatic minimal-block partitioning). Defaults per interaction: density-density → `Nt Szt Azt`; Kanamori → `Nt Szt Qzt`; Coulomb → `Nt Szt Lzt`; general → `Nt Szt All`.

---

## 7. Worked examples (verbatim from the wiki)

### 7.1 Single-orbital Bethe-lattice Hubbard DMFT

`Parameters.in`:

```ini
[General]
  DOS = Bethe                   # parse the hamiltonian defined previously
  half-bandwidth = 2.,          # half bandwidth of Bethe DOS
  beta = 50                     # inverse temperature
  NAt = 1                       # no. of atoms; identical to [Atoms] subsections
  mu = 1.0                      # chemical potential
  EPSN = 0.0                    # chemical potential search, 0-> disabled
  DMFTsteps = 2                 # no. of DMFT steps
  magnetism = para              # paramagnetic calculation
  mixing = 0.5                  # mixing of old and new self-energy; 0 means 100% of the new self energy
  FileNamePrefix = U_0.0        # output filename, time stamp appended
  fileold = asdf                # filename of hdf5-file a calculation is continued
  readold = 0                   # iteration where run is continued; 0 -> new run, -1 -> last run
```
```ini
[Atoms]
[[1]]
  Nd = 1
  Hamiltonian = Density         # local interaction (Density,Kanamori,Coulomb)
  Udd = 2.0                     # intra-orbital Coulomb U
  Jdd = 0.0                     # Hund coupling J
  Vdd = 0.0                     # inter-orbital Coulomb V
  QuantumNumbers = Nt Szt Azt   # conserved quantities; Nt = number of electrons,
                                # Szt = spin in z-direction, Azt = density per spin-orbital
```
```ini
[QMC]
  Nwarmups = 100000               # no. of thermalisation steps before measurement
  Nmeas = 100000                  # no. of measurement steps
  NCorr = 30                      # auto-correlation estimate
  PercentageGlobalMove = 0.005    # share of global updates
  Ntau = 50                       # no. of imaginary-time bins for the 1P GF
  Nftau = 2002                    # no. of imaginary-time points for the hybridisation function
  Niw = 1000                      # no. of positive Matsubara frequencies for the 1P GF; note that Nftau > 2*Niw
  NLegMax = 30                    # no. of Legendre coefficient for the 1P GF
  NLegOrder = 30                  # no. of Legendre coefficient for the 1P GF used in DMFT loop
```

Run + check convergence (half-filling at μ=U/2 for one orbital with symmetric DOS):

```bash
mpirun -np 4 DMFT.py
hgrep latest mu
hgrep latest imp-electrons
```
```
# plot last three iterations of Re/Im self-energy
set xrange [-10:10]; set xlabel "iw_n"; set ylabel "{/Symbol S}"
p '< hgrep latest siw 8 1 1 1'  u 5:6 w l lw 3, \
  '< hgrep latest siw 9 1 1 1'  u 5:6 w l lw 3, \
  '< hgrep latest siw 10 1 1 1' u 5:6 w l lw 3, \
  '< hgrep latest siw 8 1 1 1'  u 5:7 w l lw 3, \
  '< hgrep latest siw 9 1 1 1'  u 5:7 w l lw 3, \
  '< hgrep latest siw 10 1 1 1' u 5:7 w l lw 3
```
Convergence tooling: `hist-glob` gives ⟨k⟩, `accept-ins` gives the insert/remove acceptance → renewal time ⟨k⟩/R_rem sets a sane `NCorr`. Set `Gtau_mid_step=1` to verify thermalization (`gtau-mid-step` should plateau vs MC steps). Sweeping U at μ=U/2 traces the Mott transition.

### 7.2 Two-orbital model, Kanamori interaction with a Sz magnetic field (DFT-style H(k))

Generate spin-dependent H(k) in wannier90 format (basis: orb1↑, orb2↑, orb1↓, orb2↓; a Zeeman ±field is added per spin), then:

```ini
#asdf
[General]
  DOS = ReadInSO
  HkFile = hk_sz.dat
  beta = 10
  NAt = 1
  #mu = 1.75
  totdens = 2.0
  magnetism = ferro
  EPSN = 0.001
  DMFTsteps = 3
  FileNamePrefix = dmft_sz
  fileold = dmft_sz-2018-07-01-Sun-15-09-45.hdf5
  readold = 10
  mixing = 0.75
[Atoms]
[[1]]
  Hamiltonian = Kanamori
  QuantumNumbers = Nt Szt Qzt
  Udd = 2.0
  Jdd = 0.5
  Vdd = 1.0
  Nd = 2
[QMC]
  Nwarmups = 200000
  Nmeas = 100000
  NCorr = 50
  Niw = 1000
  Ntau = 100
  NLegMax = 20
  NLegOrder = 20
  TaudiffMax=1
```
Notes: `DOS=ReadInSO` because H(k) is spin-dependent; `magnetism=ferro` keeps spins distinct (no averaging); `mixing` raised to 0.75 to damp unphysical oscillations; `TaudiffMax=1` restricts proposed operator τ-distances (local-update algorithm). The density-density variant is identical except `Hamiltonian = Density` (and the corresponding `QuantumNumbers = Nt Szt Azt`).

### 7.3 Three-orbital two-particle Green's function via worm sampling (single-shot)

```ini
[General]
  DOS = ReadIn
  HkFile = hk_3orb
  beta = 20
  NAt = 1
  mu = 1.75
  magnetism = para
  DMFTsteps = 0
  StatisticSteps = 0
  WormSteps = 1
  FileNamePrefix = 2p

[Atoms]
[[1]]
  Hamiltonian = Kanamori
  QuantumNumbers = Nt Szt Qzt
  Udd = 2.0
  Jdd = 0.5
  Vdd = 1.0
  Nd = 3

[QMC]
  Eigenbasis            = 1
  Nwarmups              = 3e7
  Nmeas                 = 3e6
  NCorr                 = 50
  Ntau                  = 1000
  Niw                   = 2000

  PercentageWormInsert  = 0.3                # worm insertion proposal
  PercentageWormReplace = 0.1                # worm replacement proposal

  WormEta               = 1                  # initial balancing factor
  WormSearchEta         = 1                  # activate automatic balancing
  Nwarmups2Plus         = 3e5                # warmup steps for balancing

  WormMeasG4iw          = 1                  # enable two-particle measurement
  FourPnt               = 8                  # enable two-particle measurement
  WormPHConvention      = 1                  # set PH convention

  N4iwf                 = 60                 # ferimionic frequencies 2*N4iwf
  N4iwb                 = 60                 # bosonic frequencies 2*N4iwb+1

  WormComponents        = 1                  # which flavor component(s) to sample; omit -> all 1296
```
`DMFTsteps=0, StatisticSteps=0, WormSteps=1` → a single-shot worm run (commonly preceded by a converged DMFT run). `WormComponents` lists which of the (2·nbands)⁴ flavor components to measure; omit it to sample all and keep only non-vanishing ones. Read a component:

```python
import h5py, numpy as np
from matplotlib import pyplot as plt
f  = h5py.File("2p-2018-07-12-Thu-16-18-48.hdf5", "r")
g4 = f["worm-001/ineq-001/g4iw-worm/00001/value"].value
plt.pcolormesh(g4[:, :, g4.shape[-1] // 2].real); plt.show()
```
Flavor-index ↔ band-spin pattern conversion uses the bundled helper:

```python
from auxiliaries import compoundIndex as ci
bs, b, s = ci.index2component_general(nbands, noper, index)   # index -> pattern
index    = ci.component2index_general(nbands, noper, b, s)    # pattern -> index
```

---

## 8. Pitfalls

- **Sign problem with off-diagonal hybridization + non-density-density interaction.** Off-diagonal Δ (from real inter-orbital hopping, `offdiag=1`) combined with Kanamori/full-Hubbard introduces spin-flip / pair-hopping configurations not reachable by ordinary pair insert/remove; needs 4-operator moves (`Percentage4OperatorMove`) or flavor-change moves (`flavourchange_moves`). Cluster-DMFT (whole cluster as one impurity) hits a severe sign problem at moderate cluster size — CT-HYB is not the right tool there. Density-density + off-diagonal Δ combines cleanly. Monitor the `sign` output.
- **Matsubara / τ grid sizes.** Require `Nftau > 2·Niw` (hybridization grid must over-resolve the frequency grid). `Ntau` must resolve G(τ) features; too-coarse grids alias. Two-particle boxes (`N4iwf`,`N4iwb`,`N2iwb`,`N3iwf`,`N3iwb`) blow up memory and noise fast — start small.
- **Thermalization & autocorrelation.** Error ∝ 1/√Nmeas. **Too small `Nwarmups` gives wrong (un-thermalized) results** — set it 10–100× `NCorr`; near phase transitions / very low T these estimates are unreliable, so verify with `Gtau_mid_step=1` (the `gtau-mid-step` plateau). `NCorr` only affects efficiency; aim for the renewal time ⟨k⟩/R_rem. Worm estimators with more external legs are noisier (`g4iw-worm` ≫ `g4iw1-worm` ≫ `giw-worm`); time-independent estimators (`rho1`,`rho2`) are noisier than `gtau`.
- **MPI parallelism.** Monte Carlo is trivially parallel; error bars are computed *across cores* (Eq. 13), so `Nwarmups` must be large enough that each core's chain is independently thermalized. Run with `mpiexec/mpirun -n N`.
- **Analytic continuation.** CT-HYB yields imaginary-axis G(iν)/G(τ); real-frequency spectra A(ω) require `Maxent.py` (max-entropy), an ill-posed inversion sensitive to QMC noise — needs good high-frequency statistics (improved/worm estimators help).
- **μ vs filling.** `EPSN=0` → fixed `mu`; `EPSN>0` → root-finds μ to hit `totdens` (the expensive bottleneck for large systems). Don't set both inconsistently.
- **`Hamiltonian` naming.** The interaction is set by the (admittedly confusable) `Hamiltonian` key in `[Atoms]`, not in `[General]`.

---

## Source links

- Repo: <https://github.com/w2dynamics/w2dynamics>
- README: <https://github.com/w2dynamics/w2dynamics/blob/master/README.md>
- Config spec (all parameters + defaults): <https://github.com/w2dynamics/w2dynamics/blob/master/w2dyn/auxiliaries/configspec>
- Wiki home: <https://github.com/w2dynamics/w2dynamics/wiki>
- Tutorials index: <https://github.com/w2dynamics/w2dynamics/wiki/Tutorials>
- Bethe lattice: <https://github.com/w2dynamics/w2dynamics/wiki/Bethe-lattice>
- Density-density vs Kanamori (two-orbital): <https://github.com/w2dynamics/w2dynamics/wiki/Density-density-and-Kanamori-interacting:-a-two-orbital-model>
- Two-orbital with magnetic field: <https://github.com/w2dynamics/w2dynamics/wiki/A-two-orbital-model-with-magnetic-field>
- Two-particle GF (worm sampling): <https://github.com/w2dynamics/w2dynamics/wiki/Two-particle-Green's-function-(Worm-sampling)>
- Two-particle GF (Z sampling): <https://github.com/w2dynamics/w2dynamics/wiki/Two-particle-Green's-function-(Z-sampling)>
- Installation: <https://github.com/w2dynamics/w2dynamics/wiki/Installation>
- Release paper: <https://arxiv.org/abs/1801.10209> · doi:10.1016/j.cpc.2018.09.007 · local: `.knowledge/literature/software/1801.10209_w2dynamics-local-one-and-two-particle-quantities-from-dynami.md`
