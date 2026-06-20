# ALF — API + Usage Reference

**ALF** (Algorithms for Lattice Fermions) is an open-source Fortran (2003/2008) code for
**auxiliary-field (determinant) quantum Monte Carlo** of interacting fermions, in both the
**finite-temperature** grand-canonical formulation and the **projective** (ground-state,
canonical) formulation. It is the Blankenbecler-Scalapino-Sugar (BSS) algorithm: imaginary
time is Trotter-discretized, the two-body interaction is decoupled into free fermions moving
in a fluctuating space-time field (Hubbard-Stratonovich for "perfect-square" terms, plus
optional Ising fields), and the fermions are integrated out into a determinant that is sampled
by Monte Carlo. It scales **O(β·N³)** (β = inverse temperature, N = lattice volume) — linear in
β, cubic in volume.

ALF is **general**: any Hamiltonian writable as a sum of one-body terms, squares of one-body
terms, and one-body terms coupled to an Ising field can be simulated by filling the
`Hamiltonian` template — no need to touch the Monte Carlo core. It ships predefined models
(Hubbard, SU(N)-Hubbard, t-V, Kondo, long-range Coulomb, Z₂ gauge-matter, spin-Peierls)
selectable by name. It is **sign-problem aware**: the average sign ⟨sign⟩ is reweighted and
reported, and many bipartite / SU(N) / symmetry-protected formulations are sign-problem-free.
It supports **MPI** (and OpenMP) for massively parallel runs, plus parallel tempering.

**pyALF** is the Python front-end: it fetches/compiles the Fortran source, writes the
`parameters` file, runs ALF, and post-processes the binned Monte Carlo data into a pandas
DataFrame of observables with Jackknife error bars. The recommended workflow is
`ALF_source → Simulation → compile → run → analysis → get_obs`.

> Note on versions: the local rendered paper is **release 1.0** (arXiv:1704.00131); the current
> code (ALF ≥ 2.x, GitHub `ALF-QMC/ALF`) keeps the same template architecture but renamed a
> few things — executable `Prog/Examples.out` → `Prog/ALF.out`, analysis `analysis.sh` →
> `Analysis/ana.out` / pyALF analysis, and added the projective algorithm, HDF5 output, and
> the `Hubbard`/`tV`/`Kondo`/`LRC`/`Z2_Matter`/`Spin_Peierls` predefined Hamiltonians. The
> namelist parameter names below match the current code as exercised through pyALF.

## Source links

- Project home: https://alf.physik.uni-wuerzburg.de/
- PDF documentation (authoritative, kept current): https://alf.physik.uni-wuerzburg.de/doc.pdf
- ALF GitHub: https://github.com/ALF-QMC/ALF
- pyALF GitHub: https://github.com/ALF-QMC/pyALF
- pyALF documentation: https://gitpages.physik.uni-wuerzburg.de/ALF/pyALF · mirror https://alf.physik.uni-wuerzburg.de/pyalf-doc/
- Original GitLab instance (issues, wiki): https://git.physik.uni-wuerzburg.de/ALF/ALF · https://git.physik.uni-wuerzburg.de/ALF/pyALF
- Release 1.0 paper: arXiv:1704.00131, DOI 10.21468/SciPostPhys.3.2.013
- Release 2.0 / 2.4 papers (full parameter reference, projective + LRC + Z₂): arXiv:2012.11914
- Local rendered paper: `.knowledge/literature/software/1704.00131_the-alf-algorithms-for-lattice-fermions-project-release-1-0.md`
- Contact: alf@physik.uni-wuerzburg.de
- License: GPL v3 (code) with attribution terms; docs CC-BY-SA 4.0.

---

## What ALF computes

For the general Hamiltonian (sum of one-body, perfect-square two-body, and Ising-coupled
one-body terms), ALF computes thermodynamic expectation values via the single-particle Green
function and Wick's theorem:

- **Scalar observables** (`Obs_vec` type): kinetic energy `Kin`, potential energy `Pot`,
  particle number `Part`, total energy `Ener`.
- **Equal-time correlation functions** (`Obs_Latt` type, suffix `_eq`): Green function `Green`,
  spin-spin `SpinZ`/`SpinXY`, density-density `Den`. Fourier-transformed to k-space.
- **Time-displaced correlation functions** (suffix `_tau`, when `Ltau=1`): same channels,
  S(k, τ), used for gaps, spectral functions, dynamics.

It is limited to: two-body interactions only (no 3-body); discrete fields (no electron-phonon,
no continuous HS / long-range Coulomb in the perfect-square sense — but short-range terms like
(nᵢ+nⱼ−2)² are fine); Hamiltonian-based (no retarded interactions); correlation functions with
at most two distinct imaginary times.

### General Hamiltonian form

```
Ĥ = Ĥ_T + Ĥ_V + Ĥ_I + Ĥ_{0,I}
Ĥ_T = Σ_{k=1..MT}  Σ_{s=1..Nfl} Σ_{σ=1..Ncol} Σ_{x,y} c†_{xσs} T^{(ks)}_{xy} c_{yσs}     (one-body / hopping)
Ĥ_V = Σ_{k=1..MV}  U_k [ Σ_s Σ_σ Σ_{x,y} c†_{xσs} V^{(ks)}_{xy} c_{yσs} + α_{ks} ]²      (perfect-square two-body)
Ĥ_I = Σ_{k=1..MI}  Ẑ_k [ Σ_s Σ_σ Σ_{x,y} c†_{xσs} I^{(ks)}_{xy} c_{yσs} ]                (one-body coupled to Ising spin Ẑ_k)
Ĥ_{0,I}  = user-specified Ising-spin dynamics (enters via function S0)
```

- `Nfl` = number of fermion flavors (block-diagonal after HS). `Ncol ≡ N_SUN` = number of
  colors; Hamiltonian is SU(Ncol)-symmetric (determinant raised to power Ncol).
- `N_dim = N_unit_cell · N_orbital` = total spatial vertices. T, V, I are N_dim × N_dim
  Hermitian matrices, flavor-dependent but color-independent.
- Imaginary-time discretization β = Δτ·L_Trotter introduces an O(Δτ²) Trotter error.

---

## Workflow A — via pyALF (recommended)

### Installation

```sh
pip install pyALF
```

You also need the ALF Fortran prerequisites (a Fortran compiler, LAPACK/BLAS, make, git, and —
for HDF5 output — HDF5; pyALF can build HDF5 for you on first compile). On Debian/Ubuntu:

```sh
sudo apt-get install gfortran liblapack-dev python3 make git
```

`ALF_source` will `git clone` the ALF source automatically if `$ALF_DIR` (or `./ALF`) is absent.

### Minimal complete example — finite-T Hubbard model (verbatim from `Notebooks/minimal_ALF_run.ipynb`)

Runs the canonical Hubbard model on the default 6×6 square lattice, U=4, β=5.

```python
from py_alf import ALF_source, Simulation  # Interface with ALF

alf_src = ALF_source(branch='master')      # Obtain/clone ALF source code

sim = Simulation(
    alf_src,
    "Hubbard",                    # Name of Hamiltonian
    {                             # Dictionary overwriting default parameters
        "Lattice_type": "Square"
    },
    machine='GNU'  # Change to "intel", or "PGI" if gfortran is not installed
)

sim.compile()   # Compile ALF (first time also builds HDF5, ~15 min)
sim.run()       # Run the Monte Carlo simulation
sim.analysis()  # Jackknife error analysis of the binned data
obs = sim.get_obs()   # pandas DataFrame: one row per simulation, params + observables
obs
```

Read a specific observable (internal energy and average sign, with errors):

```python
obs.iloc[0][['Ener_scal0', 'Ener_scal0_err', 'Ener_scal_sign', 'Ener_scal_sign_err']]
```

Refine: calling `run` again **resumes** the chain and adds bins, shrinking the error. To start
fresh, delete the Monte Carlo run directory (`sim.sim_dir`) first.

```python
sim.run()
sim.analysis()
obs2 = sim.get_obs()
obs2.iloc[0][['Ener_scal0', 'Ener_scal0_err']]
```

Discovery helpers:

```python
alf_src.get_ham_names()              # -> ['Kondo','Hubbard','Hubbard_Plain_Vanilla','tV','LRC','Z2_Matter','Spin_Peierls']
alf_src.get_default_params('Hubbard')  # full default parameter dict for the Hamiltonian
help(alf_src); help(Simulation)
```

### Fuller parameter dictionary — projective + Mz Hubbard (verbatim from `Notebooks/projective_algorithm.ipynb`)

Shows the projective (ground-state) algorithm: `Projector=True` + `Theta`. Loops Θ to study
convergence to the ground state.

```python
import numpy as np
from py_alf import ALF_source, Simulation

alf_src = ALF_source(branch='master')

sims = []
for theta in [0.5, 1, 1.5, 3, 5, 10]:    # Values of Theta (projection time)
    sim = Simulation(
        alf_src,
        'Hubbard',                       # Hamiltonian
        {
        'Model': 'Hubbard',              #    Base model
        'Lattice_type': 'N_leg_ladder',  #    Lattice type
        'L1': 4,                         #    Lattice length along first unit vector
        'L2': 1,                         #    Lattice length along second unit vector
        'Checkerboard': False,           #    Whether checkerboard decomposition is used
        'Symm': True,                    #    Whether symmetrization takes place
        'Projector': True,               #    Use the projective (ground-state) algorithm
        'Theta': theta,                  #    Projection parameter
        'ham_T': 1.0,                    #    Hopping parameter
        'ham_U': 4.0,                    #    Hubbard interaction
        'ham_Tperp': 0.0,                #    For bilayer systems
        'beta': 0.5,                     #    Inverse temperature (measurement interval in projective)
        'Ltau': 0,                       #    '1' for time-displaced Green functions; '0' otherwise
        'NSweep': 600,                   #    Number of sweeps per bin
        'NBin': 50,                      #    Number of bins
        'Dtau': 0.05,                    #    Ltrot = beta/Dtau (or Theta/Dtau projective)
        'Mz': True,                      #    Mz-Hubbard: Nfl=2, N_SUN=1, HS couples to S^z
        },
    )
    sims.append(sim)

sims[0].compile()          # Compile once
for sim in sims:
    sim.run()              # Run each

ener = np.empty((len(sims), 2))
for i, sim in enumerate(sims):
    sim.analysis()
    obs = sim.get_obs()
    ener[i] = obs.iloc[0][['Ener_scal0', 'Ener_scal0_err']]
```

### t-V model of spinless fermions (verbatim from `Notebooks/tV_model.ipynb`)

```python
from py_alf import ALF_source, Simulation

alf_src = ALF_source()

sim = Simulation(
    alf_src,
    "tV",                     # Hamiltonian
    {
    "Model": "tV",            # t-V model
    "Lattice_type": "Square", # Lattice type
    "N_SUN": 1,               # spinless fermions
    "Dtau": 0.05,             # Ltrot = Beta/Dtau
    "Nwrap": 5},              # Stabilization: recompute Green fct from scratch every Nwrap*Dtau
)
```

### MPI / parallel tempering

Pass MPI options to `Simulation`. For **parallel tempering**, replace `sim_dict` with a *list of
dicts* (one per replica); this implies MPI:

```python
sim = Simulation(
    alf_src, 'Hubbard',
    [{
        'L1': 4, 'L2': 4, 'Ham_U': U,
        'Nbin': 20, 'mpi_per_parameter_set': 2
    } for U in [2.5, 3.5]],
    mpi=True, n_mpi=4, mpiexec='orterun',
    mpiexec_args=['--oversubscribe'],
)
```

---

## pyALF API reference (`from py_alf import ALF_source, Simulation`)

### class `ALF_source`

Points at a folder of ALF source code (cloning it if absent) and parses the available
Hamiltonians and their default parameters.

```python
ALF_source(alf_dir=None, branch=None, url='https://github.com/ALF-QMC/ALF.git')
```

| arg | default | meaning |
|---|---|---|
| `alf_dir` | `$ALF_DIR` or `'./ALF'` | directory with the source; cloned from `url` if it does not exist |
| `branch` | `None` | git branch/tag/commit to check out (e.g. `'master'`) |
| `url` | GitHub ALF | clone URL when `alf_dir` is absent |

Methods:

- `get_ham_names()` → list of predefined Hamiltonian names.
- `get_default_params(ham_name, include_generic=True)` → full default parameter dict.
- `get_params_names(ham_name, include_generic=True)` → list of legal parameter names
  (used by `Simulation` to validate `sim_dict` keys; an unknown key raises `TypeError`).

### class `Simulation`

One ALF run (or a tempering set). Holds the chosen Hamiltonian, the parameter overrides, and
the compile/run configuration. Run directory `sim.sim_dir` is derived from the parameters under
`sim_root` (default `ALF_data/`) unless `sim_dir` is given.

```python
Simulation(alf_src, ham_name, sim_dict, **kwargs)
```

| arg / kwarg | default | meaning |
|---|---|---|
| `alf_src` | — | an `ALF_source` instance |
| `ham_name` | — | Hamiltonian name, e.g. `"Hubbard"`, `"tV"`, `"Kondo"`, `"LRC"`, `"Z2_Matter"`, `"Spin_Peierls"` |
| `sim_dict` | — | dict overriding default parameters (keys validated against the Hamiltonian). A **list of dicts** ⇒ parallel tempering (forces `mpi=True`) |
| `sim_dir` | auto | explicit run directory name |
| `sim_root` | `"ALF_data"` | parent directory prepended to `sim_dir` |
| `sim_dir_hash` | `False` | experimental short hashed dir names |
| `mpi` | `False` | run under MPI |
| `parallel_params` | `False` | run independent parameter sets in parallel (tempering machinery, no exchange); needs list `sim_dict` |
| `n_mpi` | `2` | MPI process count when `mpi=True` |
| `n_omp` | `1` | OpenMP threads per process (sets `OMP_NUM_THREADS`) |
| `mpiexec` | `"mpiexec"` | MPI launcher (`'orterun'`, `'mpiexec.hydra'`, …) |
| `mpiexec_args` | `[]` | extra launcher args, e.g. `['--hostfile','/path']` |
| `machine` | `"GNU"` | compiler/env: `"GNU"`, `"INTEL"`, `"PGI"`, or a name defined in `configure.sh` |
| `stab` | `''` | stabilization scheme: `"STAB1"`, `"STAB2"`, `"STAB3"`, `"LOG"` |
| `devel` | `False` | compile with debug flags |
| `hdf5` | `True` | compile with HDF5 (required for full postprocessing) |

Methods:

- `compile(verbosity=0)` — compile ALF with the configured options. Needed once per
  `(machine, stab, mpi, hdf5, …)` configuration; multiple `Simulation`s sharing source/config
  compile once.
- `run(copy_bin=False, only_prep=False, bin_in_sim_dir=False)` — write the `parameters` file
  into `sim_dir` and execute `Prog/ALF.out` (under `mpiexec` if `mpi`). Re-running **resumes /
  appends bins**. `only_prep=True` just writes the input files without running.
- `analysis(python_version=True, **kwargs)` — Jackknife error analysis of the binned data,
  writing results into the run directory (`res/`, `res.pkl`). The Python analysis supports all
  postprocessing (incl. time-displaced); the Fortran path (`python_version=False`) is legacy.
- `get_obs(python_version=True)` — return a **pandas DataFrame**, one row per simulation
  directory, columns = parameters + analyzed observables (e.g. `Ener_scal0`,
  `Ener_scal0_err`, `Ener_scal_sign`, …). Read with `obs.iloc[0][['Ener_scal0', ...]]`.
  Multiple `res.pkl` files are merged via `py_alf.load_res(...)`.
- `get_directories()` — list of run directories (one, or one per tempering replica).
- `print_info_file()` — print the ALF `info` file (precision, acceptance, timing).

`sim.sim_dir` is the directory holding `parameters`, the bin files, `info`, and analysis output.

### Command-line front-end

pyALF also ships UNIX CLI scripts mirroring the API: `alf_run` (prepare + run), and analysis
helpers. Run `alf_run -h`. The script `minimal_ALF_run` reproduces the minimal example above
and is a setup smoke test.

---

## Workflow B — directly (Fortran, no Python)

Quick start (from the ALF README, Debian/Ubuntu):

```sh
git clone -b master https://github.com/ALF-QMC/ALF.git
cd ALF
source configure.sh GNU noMPI      # set compiler/env; use "GNU MPI" for parallel, INTEL/PGI for other compilers
make clean
make all                           # builds Libraries, Analysis, and Prog/ALF.out
cp -r ./Scripts_and_Parameters_files/Start ./Run && cd ./Run/
$ALF_DIR/Prog/ALF.out              # run; needs `parameters` and `seeds` present
$ALF_DIR/Analysis/ana.out Ener_scal   # error analysis of the energy
cat Ener_scalJ                     # Jackknife mean & error
```

In release 1.0 the executable was `Prog/Examples.out`, compilation was a bare `make`, and error
analysis was `source ./setenv.sh; ./analysis.sh`. The architecture is otherwise unchanged.

### Directory layout

| dir | contents |
|---|---|
| `Prog/` | main program (`main.f90`/`ALF.out`) and the `Hamiltonian` module |
| `Libraries/` | math routines (linear algebra, lattice, observables, …) |
| `Analysis/` | Jackknife/rebinning error-analysis programs |
| `Examples/` (1.0) / `Hamiltonians/` (2.x) | predefined / example Hamiltonians |
| `Start/` (1.0) / `Scripts_and_Parameters_files/` (2.x) | template `parameters`, `seeds`, scripts |

### Input / output files (per run directory)

| file | role |
|---|---|
| `parameters` | Fortran namelist: lattice, model, QMC controls, error-analysis controls (see below) |
| `seeds` | integer RNG seeds; presence ⇒ start from scratch |
| `confin_<thread>` | (optional) input HS/Ising field configuration to restart from |
| `info` | written on completion: parameters, acceptance rate, wall time, **precision** diagnostics |
| `X_scal` | binned scalar observables; `X ∈ {Kin, Pot, Part, Ener}` |
| `Y_eq`, `Y_tau` | binned equal-time / time-displaced correlation functions; `Y ∈ {Green, SpinZ, SpinXY, Den}` |
| `confout_<thread>` | output field configuration (use `out_to_in.sh` to chain runs) |
| `X_scalJ`, `Y_eqJR`/`Y_eqJK`, … | Jackknife analysis output (real-/k-space; `_AutoN` for autocorrelation) |

---

## Key parameters (the `parameters` namelist / pyALF `sim_dict`)

Names are case-insensitive in pyALF. Defaults below are the common template values; query exact
defaults with `alf_src.get_default_params(ham_name)`.

### Model / lattice

| parameter | typical | meaning |
|---|---|---|
| `Model` | `"Hubbard"` | base model selector (`"Hubbard"`, `"tV"`, …) within the Hamiltonian |
| `Lattice_type` | `"Square"` | Bravais lattice: `"Square"`, `"Honeycomb"`, `"N_leg_ladder"`, `"Bilayer_square"`, `"Bilayer_honeycomb"`, … |
| `L1`, `L2` | 6, 6 | lattice extent along unit vectors a₁, a₂ (cells); torus / periodic BC. `L2=1` ⇒ chain/ladder |
| `N_SUN` | 2 | number of colors Ncol (SU(N) symmetry). `1` = spinless / Mz |
| `N_FL` | 1 | number of flavors Nfl (e.g. 2 for the Mz decoupling) |
| `Checkerboard` | `False`/`True` | checkerboard decomposition of the hopping (faster, slightly larger Trotter error) |
| `Symm` | `True` | symmetric Trotter decomposition (reduces Trotter error) |

### Interaction / model couplings

| parameter | typical | meaning |
|---|---|---|
| `Ham_T` (`ham_T`) | 1.0 | nearest-neighbor hopping t (sets the energy scale) |
| `Ham_U` (`ham_U`) | 4.0 | Hubbard on-site interaction U (U>0 repulsive) |
| `Ham_chem` | 0.0 | chemical potential μ (μ=0 ⇒ half filling on bipartite lattices) |
| `Ham_Tperp` (`ham_Tperp`) | 0.0 | inter-layer / rung hopping (bilayer / ladder) |
| `Ham_V` | — | nearest-neighbor density-density V (t-V model) |
| `Ham_J`, `Ham_JK` | — | Heisenberg / Kondo couplings (SU(N)-Heisenberg, Kondo lattice) |
| `Mz` | `True`/`False` | **HS decoupling choice for Hubbard.** `True`: field couples to Sᶻ (Nfl=2, N_SUN=1; Sᶻ conserved, no sign problem at μ=0, but breaks SU(2) per config). `False`: SU(2)-symmetric density decoupling (Nfl=1, N_SUN=2; manifest SU(2) but worse sign problem at finite doping) |

### Imaginary time / ensemble

| parameter | typical | meaning |
|---|---|---|
| `Dtau` | 0.1 / 0.05 | Trotter step Δτ. L_Trotter = β/Δτ (or Θ/Δτ projective). Smaller ⇒ less Trotter error, more cost. **Extrapolate Δτ→0.** |
| `Beta` (`beta`) | 5.0 | inverse temperature β (finite-T). In projective mode it is the symmetric measurement window around τ=Θ |
| `Projector` | `False` | `False` = finite-temperature grand-canonical; `True` = projective ground-state (canonical) algorithm |
| `Theta` | 10.0 | projection time Θ (projective only). **Extrapolate Θ→∞** for ground state |

### Monte Carlo controls

| parameter | typical | meaning |
|---|---|---|
| `NSweep` (`Nsweep`) | 500–600 | sweeps per bin (one sweep = each field visited twice, up+down in τ) |
| `NBin` (`Nbin`) | 2–50 | number of bins written to disk; each bin = average over NSweep sweeps. More bins ⇒ better error estimate |
| `NWarm` / warm-up | — | warm-up sweeps (legacy); current code keeps all bins and drops `n_skip` at analysis time |
| `Nwrap` | 10 | stabilization interval: Green function recomputed from scratch every Nwrap·Δτ. Smaller ⇒ more stable, more cost |
| `Ltau` | 0 | `1` ⇒ also measure time-displaced correlation functions (S(k,τ)); `0` ⇒ equal-time only |
| `LOBS_ST`, `LOBS_EN` | — | imaginary-time window [start,end] in which equal-time observables are measured (improved estimator via τ-translation) |
| `Propose_S0` | `False` | if true, propose Ising moves according to e^{−S₀,I} (bare Ising dynamics) |
| `CPU_MAX` | — | wall-time budget; stop cleanly when reached |

### Error-analysis controls (read by the analysis step)

| parameter | typical | meaning |
|---|---|---|
| `n_skip` | a few | number of initial bins discarded (warm-up); ≳ autocorrelation time |
| `N_rebin` | 1 | combine N_rebin bins into one effective bin before analysis; increase until the error stops growing (independence check) |
| `N_Cov` | 0 | `1` ⇒ also compute the covariance matrix of S(k,τ) (needed for correct gap-fit errors) |
| `N_auto` | 0 | `>0` ⇒ compute autocorrelation functions in the QMC-time range [0, N_auto] (expensive; needs many bins) |

### Predefined Hamiltonians (`ham_name`)

`Kondo`, `Hubbard`, `Hubbard_Plain_Vanilla`, `tV`, `LRC` (long-range Coulomb), `Z2_Matter`
(Z₂ lattice gauge theory + matter), `Spin_Peierls`. Each carries its own default parameter set
and `Model`/coupling knobs; `get_default_params(name)` lists them.

---

## Pitfalls & verification

- **Sign problem.** The action is generally complex; ALF reweights by |Re e^{−S}| and reports the
  **average sign** ⟨sign⟩ ∈ [−1,1] (e.g. `Ener_scal_sign` column). Cost to reach fixed error grows
  as e^{2·Δ·N·β}, so a small sign makes large/cold/doped systems exponentially expensive. Rule of
  thumb: usable down to ⟨sign⟩ ≈ 0.1; below that, results are untrustworthy without exploding CPU.
  The decoupling choice matters: for Hubbard, `Mz=True` (Sᶻ coupling) is sign-free at μ=0 on
  bipartite lattices, whereas the SU(2) decoupling has a severe sign problem at finite doping.
- **Trotter (Δτ) error.** Systematic O(Δτ²) bias. Always run several `Dtau` values and extrapolate
  Δτ→0; `Symm=True` reduces the prefactor. `Checkerboard=True` speeds things up at a small Δτ cost.
- **Warm-up / bins / autocorrelation.** Measurements start immediately; discard the first `n_skip`
  bins (≳ autocorrelation time). Bins shorter than the autocorrelation time **underestimate** the
  error — increase `NSweep`/`NBin`, then verify error is stable under `N_rebin` rebinning.
  Autocorrelation times are observable-dependent (e.g. Sᶻ slower than the SU(2)-symmetric
  estimator (Sˣ+Sʸ+Sᶻ)/3 near criticality); check per observable. Set `N_auto>0` to measure them.
- **Stabilization.** The BSS algorithm multiplies many ill-conditioned B matrices; ALF uses
  QR-based stabilization with period `Nwrap`. Judge it from `info`: `Precision Green` and
  `Precision Phase` should be ≲ 10⁻⁸ (means/maxima well below the stochastic error). If poor,
  lower `Nwrap` or switch scheme (`stab="STAB1"|"STAB2"|"STAB3"|"LOG"`). Finite-T needs
  stabilization; the projective algorithm is intrinsically far more stable.
- **Projective vs finite-T.** `Projector=True` (+ `Theta`) gives canonical T=0 ground-state
  properties; extrapolate Θ→∞. `Projector=False` (+ `Beta`) gives grand-canonical finite-T.
  Don't compare them at fixed β/Θ without extrapolation.
- **Time-displaced data.** Need `Ltau=1`; for gap fits also set `N_Cov=1` (omitting the
  covariance underestimates the fit error). Cross-check ED on small lattices
  (`Notebooks/testing_against_ED.ipynb`).

---

## Cross-checks against the harness

- **Limit checks** (`.knowledge/limits.md`): U=0 free fermions; large-Θ projective → ground state;
  half-filled bipartite Hubbard energies vs published BSS-QMC values.
- **ED cross-validation** for small L (pyALF `testing_against_ED`), and Δτ→0 / Θ→∞ extrapolations
  as the primary convergence evidence.
- The **average sign** is a first-class verification signal: report it alongside every observable;
  a collapsing sign invalidates the run before any other check.
