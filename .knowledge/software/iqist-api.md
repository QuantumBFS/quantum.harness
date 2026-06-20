# iQIST — API + Usage Reference

**iQIST** (interacting Quantum Impurity Solver Toolkit) is an open-source Fortran +
Python package of **continuous-time hybridization-expansion quantum Monte Carlo
(CT-HYB / CT-QMC)** impurity solvers, plus a Hirsch–Fye QMC (HF-QMC) solver, an
atomic eigenvalue solver, and pre/post-processing tools. It is *configuration-file
driven*: you write a `solver.ctqmc.in` text file, optionally provide input data files,
run a solver executable (MPI-parallel), and read plain-text output files. A Python
scripting layer (`u_ctqmc.py` config writer + `pyiqist`/`iqist` solver bindings) lets
you drive self-consistent loops programmatically.

iQIST is an **impurity solver**, not a lattice solver. Its main role is as the
inner kernel of a **dynamical mean-field theory (DMFT)** loop: DMFT maps a correlated
lattice model onto an Anderson impurity model whose bath (hybridization function
Δ(iωₙ)) is determined self-consistently, and iQIST solves that impurity model at each
iteration. You supply (or iterate to) the bath; iQIST returns G, Σ, occupations, etc.

- **Repository:** https://github.com/huangli712/iQIST
- **Current docs (manual):** https://huangli712.github.io/projects/iqist_new/index.html
- **Legacy gitbook manual:** https://huangli712.gitbooks.io/iqist/content/
- **Release paper (v1):** Huang et al., *Comput. Phys. Commun.* **195**, 140 (2015),
  arXiv:1409.7573, doi:10.1016/j.cpc.2015.04.020
- **v0.7 paper:** arXiv:1708.07453
- **License:** GPL v3. **Language:** Fortran 90/2008 (~96%) + Python. **Parallelism:** MPI + OpenMP.
- Local rendered v1 paper: `.knowledge/literature/software/1409.7573_*.md`.

> Naming note. The **original release** ships ten named components (AZALEA, GARDENIA,
> NARCISSUS, BEGONIA, LAVENDER, PANSY, MANJUSHAKA = CT-HYB; DAISY = HF-QMC; JASMINE =
> atomic solver; HIBISCUS = tools). The **modern reorganized iQIST** (`iqist_new`,
> v0.8.x) consolidates the CT-HYB family down to two production solvers — **NARCISSUS**
> (segment) and **MANJUSHAKA** (general matrix) — plus JASMINE. Both naming sets share
> the same config-file API (`solver.ctqmc.in`, `atom.cix`, …). This card documents the
> shared API and flags version-specific names.

---

## 1. Solver components — what distinguishes them

The central algorithmic choice is **segment representation** vs **general matrix
formalism**, driven by the form of the local Coulomb interaction.

| Interaction form | Trace algorithm | Solver | atom.cix needed? |
|---|---|---|---|
| **Density-density only** ([nα, H_loc]=0, H_loc diagonal in occupation basis) | **Segment** (fast) | AZALEA, GARDENIA, **NARCISSUS** | No |
| **General** (Slater/Kanamori spin-flip, pair-hopping, SOC) | **General matrix** (subspaces, divide-and-conquer) | BEGONIA, LAVENDER, PANSY, **MANJUSHAKA** | **Yes** (from JASMINE) |

**Segment solvers** (density-density). H_loc is diagonal, so the impurity trace
reduces to overlapping/empty time "segments" per flavor — extremely fast; cost grows
mildly with orbitals. Self-energy and vertex via the *improved estimator* are available
here.

- **AZALEA** — minimal segment solver, fastest, fewest observables (prototype/testing).
- **GARDENIA** — AZALEA + orthogonal-polynomial (Legendre/Chebyshev) measurement,
  improved-estimator self-energy, two-particle correlators, spin/orbital correlations.
- **NARCISSUS** — like GARDENIA, **plus frequency-dependent (retarded/screened)
  interactions** U(iν) → handles the **Hubbard–Holstein model** and **extended-DMFT**.
  *The modern default segment solver.*

**General-matrix solvers** (any interaction, SOC, crystal field). H_loc is
diagonalized first by JASMINE → `atom.cix`; the impurity trace is evaluated over
symmetry subspaces (good quantum numbers N, Sz, Jz, or PS) with divide-and-conquer,
sparse F-matrices, lazy trace evaluation, and dynamical truncation.

- **BEGONIA** — direct matrix mult + divide-and-conquer + sparse F; good to ~3 bands.
- **LAVENDER** — BEGONIA + orthogonal polynomials + some two-particle quantities; ~1–3 bands.
- **PANSY** — good-quantum-number (GQN) subspaces + divide-and-conquer; ~1–5 bands.
- **MANJUSHAKA** — PANSY + lazy trace evaluation + dynamical truncation + skip-list +
  orthogonal polynomials. High efficiency at **low T** and up to **7 bands**.
  *The modern default general-matrix solver.*

**Auxiliary components:**
- **JASMINE** — atomic eigenvalue solver. Builds and diagonalizes H_loc = H_int + H_cf +
  H_soc (Kanamori *or* Slater U; diagonal/off-diagonal crystal field; SOC λ for 3/5/7
  bands), writes eigenvalues, indices, and F-matrix into **`atom.cix`**. Required before
  any general-matrix solver. Serial (not MPI).
- **DAISY** — Hirsch–Fye QMC (HF-QMC) solver (discrete-time auxiliary-field; density-
  density only). Legacy; superseded by CT-HYB for most uses.
- **HIBISCUS** — pre/post tools: maximum-entropy analytic continuation, stochastic
  analytic continuation, Padé approximant, Kramers–Kronig, Gaussian-polynomial Σ fit,
  plus the Python config helpers. (Modern docs recommend the separate **ACFlow** toolkit
  for analytic continuation.)

---

## 2. Run workflow

Standard recipe for one impurity solve (the inner step of a DMFT loop):

1. **Choose a solver** by interaction type (segment vs general matrix — table above).
2. **Write `solver.ctqmc.in`** (the config file; see §3). A blank file is valid — every
   parameter has a default.
3. **(General interaction only) Generate `atom.cix`** with JASMINE from an
   `atom.config.in`/`solver.umat.in` describing U, J, CF, SOC.
4. **Provide optional input data** (else defaults are used):
   - `solver.hyb.in` — hybridization function Δ(iωₙ) (the DMFT bath).
   - `solver.eimp.in` — impurity energy levels Eαβ.
   - `solver.umat.in` — interaction matrix (segment solvers).
   - `solver.ktau.in` — retarded interaction kernel K(τ) (NARCISSUS screened case).
   - `solver.anydos.in` — custom density of states (built-in mini DMFT engine).
5. **Run the executable** (MPI):
   ```bash
   mpiexec -n 4 ctqmc          # modern unified driver, or:
   mpiexec -n 4 narcissus.x    # segment (modern default)
   mpiexec -n 4 manjushaka.x   # general matrix (modern default)
   mpiexec -n 4 azalea.x       # minimal segment (v1)
   mpiexec -n 4 begonia.x      # general matrix (v1)
   jasmine.x                   # atomic solver (serial)
   ```
6. **Read outputs** (§5): `solver.grn.dat` (G), `solver.sgm.dat` (Σ), etc.

**Running modes** are set by `isscf`:
- `isscf = 1` — **one-shot**: solve a fixed impurity model once (you provide
  `solver.hyb.in`). Used for measuring two-particle quantities on a converged bath.
- `isscf = 2` — **self-consistent**: iQIST runs its built-in DMFT engine for the Bethe
  lattice (Δ = t²G) for `niter` iterations. For any other lattice you must implement the
  self-consistency yourself (script the solver, or use the Python API in §6).

**MPI strategy:** each rank does independent MC sampling; the master averages at the
end. Near-linear speedup. Fix `nsweep` per rank and add ranks for more statistics.

---

## 3. `solver.ctqmc.in` — configuration parameters

Format: `key = value` or `key : value`, one per line. Text after `#` or `!` is a
comment. Keys are case-insensitive. Omitted keys take defaults. **iQIST does not check
parameter consistency** — e.g. you must keep `norbs = 2*nband` and `ncfgs = 2**norbs`
yourself.

### Running mode / DMFT engine
| Param | Meaning | Default |
|---|---|---|
| `isscf` | 1 = one-shot solve; 2 = self-consistent (built-in Bethe-lattice DMFT) | 2 |
| `isbin` | 1 = no data binning; 2 = with binning (error bars) | 1 |
| `niter` | number of DMFT self-consistent iterations (isscf=2) | 20 |
| `alpha` | linear mixing factor for the self-consistency, Gₙₑw = α·G + (1−α)·G_old | 0.7 |

### Model / Hilbert space
| Param | Meaning | Default |
|---|---|---|
| `nband` | number of correlated orbitals (bands) | 1 |
| `nspin` | number of spin components (always 2) | 2 |
| `norbs` | number of spin-orbitals = `nband × nspin` | 2 |
| `ncfgs` | size of local Hilbert space = `2**norbs` | 4 |
| `nzero` | number of atomic states kept after truncation (general-matrix solvers) | 128 |

### Interaction & chemical potential
| Param | Meaning | Default |
|---|---|---|
| `Uc` | intra-orbital Coulomb U | 4.0 |
| `Uv` | inter-orbital Coulomb U′ | 4.0 |
| `Jz` | Hund z-component (Ising) exchange Jz | 0.0 |
| `Js` | spin-flip exchange Js | 0.0 |
| `Jp` | pair-hopping Jp | 0.0 |
| `mune` | chemical potential μ (μ = U/2 + ... for half filling) | 2.0 |
| `beta` | inverse temperature β = 1/T | 8.0 |
| `part` | hopping/bandwidth parameter t for built-in Bethe DMFT (Δ = part²·G) | 0.5 |
| `lc` | electron-phonon / screening coupling strength (NARCISSUS, screened) | 1.0 |
| `wc` | screening/phonon frequency ωc (NARCISSUS, screened) | 1.0 |

### Frequency / imaginary-time grids
| Param | Meaning | Default |
|---|---|---|
| `mfreq` | number of Matsubara frequency points for G/Σ output | 8193 |
| `nfreq` | number of low frequencies sampled directly (high freq filled by tail) | 128 |
| `ntime` | number of imaginary-time slices on [0,β] | 1024 |
| `nffrq` | number of fermionic Matsubara freqs for two-particle quantities | 32 |
| `nbfrq` | number of bosonic Matsubara freqs for two-particle quantities | 8 |
| `mkink` | maximum perturbation (kink) order allowed in the configuration | 1024 |

### Measurement flags
| Param | Meaning | Default |
|---|---|---|
| `isort` | 1 = standard estimator; 2/3 = Legendre; 4/5/6 = Chebyshev orthogonal-poly measurement of G/Σ | 1 |
| `issus` | bitmask: measure spin-spin / orbital-orbital susceptibilities χ(τ), χ(iω) | 1 |
| `isvrt` | bitmask: measure two-particle Green's function & vertex / pair susceptibility (e.g. 8) | 1 |
| `isscr` | screening mode (NARCISSUS): 1 = static, >1 = various retarded U(iν) models | 1 |
| `isspn` | spin symmetry constraint (1 = enforce paramagnetic / spin symmetrization) | 1 |
| `lemax`,`legrd` | max Legendre order and Legendre grid size (when isort uses Legendre) | 32, 20001 |
| `chmax`,`chgrd` | max Chebyshev order and Chebyshev grid size | 32, 20001 |

### Monte Carlo controls
| Param | Meaning | Default |
|---|---|---|
| `ntherm` | thermalization sweeps before measurement | 200000 |
| `nsweep` | total Monte Carlo sweeps per MPI rank | 20000000 |
| `nwrite` | write intermediate results every this many sweeps | 2000000 |
| `nclean` | rebuild/clean MC matrices (numerical refresh) every this many sweeps | 100000 |
| `nmonte` | measure single-particle observables every `nmonte` sweeps (autocorrelation control) | 10 |
| `ncarlo` | measure G(τ) every `ncarlo` sweeps | 10 |
| `nflip` | attempt a global spin/flavor swap every `nflip` sweeps (avoids trapping) | 20000 |

> Defaults above follow the iQIST docs/source (`ctqmc_control.f90`); some defaults
> differ slightly between solver components and versions. When precision matters, check
> the parameter pages under
> https://huangli712.github.io/projects/iqist_new/ch04/parameters.html or the component's
> source. Speed-tuning knobs in the general-matrix solvers — `ifast`, `itrun`, `mstep`,
> `nvect`, `nleja`, `npart`, `nsing` — control truncation, Lanczos/Krylov time evolution,
> and divide-and-conquer partitioning.

---

## 4. Input data files (optional; defaults used if absent)

| File | Contents | Used by |
|---|---|---|
| `solver.ctqmc.in` | the config file above (§3) | all CT-HYB solvers |
| `solver.hyb.in` | hybridization function Δ(iωₙ) — the DMFT bath; columns: index, ωₙ, Re Δ, Im Δ (per flavor block) | all (the bath input) |
| `solver.eimp.in` | impurity energy levels Eαβ (one per flavor) | all |
| `solver.umat.in` | Coulomb interaction matrix U(α,β) | segment solvers |
| `solver.ktau.in` | retarded interaction kernel K(τ) and its derivative | NARCISSUS (screened) |
| `solver.anydos.in` | custom non-interacting density of states for built-in DMFT | built-in DMFT engine |
| `atom.cix` | atomic eigenvalues, F-matrix, subspace indices (from JASMINE) | **general-matrix solvers** (BEGONIA/LAVENDER/PANSY/MANJUSHAKA) |
| `atom.config.in` | JASMINE config: nband, norbs, ncfgs, U, J, CF, SOC | JASMINE |

To reuse a converged bath for a one-shot run: copy `solver.hyb.dat` (an output) to
`solver.hyb.in`.

---

## 5. Output files & observables

Plain-text, written to the run directory. (Modern docs use `solver.green.dat` /
`solver.weiss.dat` / `solver.hybri.dat`; the v1 paper used `solver.grn.dat` /
`solver.wss.dat` / `solver.hyb.dat`. Same data, renamed.)

| File | Observable |
|---|---|
| `solver.grn.dat` / `solver.green.dat` | impurity Green's function G(iωₙ) **and** G(τ) |
| `solver.sgm.dat` | self-energy Σ(iωₙ) (Dyson or improved estimator) |
| `solver.wss.dat` / `solver.weiss.dat` | Weiss field / bare bath Green's function G₀(iωₙ) |
| `solver.hyb.dat` / `solver.hybri.dat` | hybridization function Δ(iωₙ) (used as next-iteration `solver.hyb.in`) |
| `solver.hist.dat` | histogram of perturbation expansion order k (→ kinetic energy E_kin = −⟨k⟩/β) |
| `solver.nmat.dat` | orbital occupation ⟨nα⟩ and double occupation ⟨nα nβ⟩ |
| `solver.prob.dat` / `solver.diag.dat` | atomic-state probabilities p_Γ = ⟨|Γ⟩⟨Γ|⟩ |
| `solver.kmat.dat` | ⟨k⟩, ⟨k²⟩ — kinetic energy & fluctuations |
| `solver.szsz.dat` | spin-spin correlation χ_ss(τ) = ⟨Sz(τ)Sz(0)⟩ (→ μ_eff) |
| `solver.ochi.dat` | orbital-orbital correlation χⁿⁿ_αβ(τ) |
| `solver.twop.dat` | two-particle Green's function χ(ω,ω′,ν) |
| `solver.vrt.dat` | local irreducible vertex Γ(ω,ω′,ν) and pair susceptibility |
| `solver.status.dat` | MC configuration snapshot (restart / checkpoint) |

Key derived/measured observables: single-particle G(τ) & G(iωₙ); self-energy Σ(iωₙ);
two-particle correlator χ and vertex Γ (inputs for diagrammatic extensions: dual
fermions, DΓA); occupations ⟨nα⟩, double occupations ⟨nα nβ⟩, charge fluctuation
⟨N²⟩−⟨N⟩²; spin- and orbital-correlation functions; kinetic & potential energy; atomic
state probabilities; expansion-order histogram; autocorrelation time.

---

## 6. Worked examples (verbatim from the docs/paper)

### 6.1 Single-band half-filled Hubbard model, Bethe lattice, self-consistent DMFT

Parameters: U = 6.0, μ = 3.0, T = 0.1 (β = 10), t = 0.5. Built-in Bethe DMFT (Δ = t²G),
density-density → segment solver, no `atom.cix` needed.

`solver.ctqmc.in`:
```
# file name: solver.ctqmc.in
isscf = 2 ! control the running mode, self-consistent calculation
isbin = 1 ! control the running mode, no data binning
Uc = 6.0 ! Coulomb interaction
mune = 3.0 ! chemical potential
beta = 10.0 ! inversion of temperature
```

Run (4 MPI ranks, ~2 min); choose any segment solver:
```
$ mpiexec -n 4 iqist/bin/azalea.x
# gardenia.x / narcissus.x are drop-in replacements
```
Result: impurity G(iωₙ) in `solver.grn.dat` — insulating behavior at U=6.

### 6.2 Two-band Hubbard, rotationally-invariant (general) interaction

Parameters: U = 6.0, J = 1.0, μ = 6.5, β = 10, t = 0.5. General interaction →
**must** build `atom.cix` with JASMINE first, then a general-matrix solver.

`atom.config.in` (JASMINE):
```
# file name: atom.config.in
nband : 2 # number of bands
norbs : 4 # number of orbitals (include spin index)
ncfgs : 16 # number of atomic configurations (= 2**norbs)
nmini : 0 # minmum occupancy
nmaxi : 4 # maximum occupancy
Uc : 6.00 # intraorbital Coulomb interaction
Uv : 4.00 # interorbital Coulomb interaction
Jz : 1.00 # z component of Hund's exchange interaction
Js : 1.00 # spin-flip
Jp : 1.00 # pair-hopping
```
```
$ iqist/bin/jasmine.x        # serial; produces atom.cix (do not edit by hand)
```
`solver.ctqmc.in` (interaction params omitted — they live in atom.cix):
```
# file name: solver.ctqmc.in
isscf : 2 ! control the running mode, self-consistent calculation
isbin : 1 ! control the running mode, no data binning
nband : 2 ! number of bands
norbs : 4 ! number of orbitals (include spin index)
ncfgs : 16 ! number of atomic configurations (= 2**norbs)
mune : 6.50 ! chemical potential for half-filling case
beta : 10.0 ! inversion of temperature
```
```
$ mpiexec -n 4 iqist/bin/begonia.x   # or lavender/pansy/manjushaka
```

### 6.3 One-shot two-particle / vertex measurement

Reuse a converged bath: copy `solver.hyb.dat` → `solver.hyb.in`. One-shot (`isscf=1`),
turn on two-particle measurement (`isvrt = 8`):
```
# file name: solver.ctqmc.in
isscf = 1 # control the running mode, one-shot calculation
isbin = 1 # control the running mode, no data binning
isvrt = 8 # calculate two-particle quantities
Uc = 6.0 # Coulomb interaction
mune = 3.0 # chemical potential
beta = 10.0 # inversion of temperature
nbfrq = 1 # number of bosonic frequencies
nffrq = 128 # number of fermionic frequencies
```
```
$ mpiexec -n 4 iqist/bin/gardenia.x   # segment solver with vertex measurement
```
Output: χ(ω,ω′,ν) and Γ(ω,ω′,ν) in `solver.twop.dat`.

### 6.4 Python API — scripted DMFT loop (Mott transition scan)

The Python layer = `u_ctqmc` (writes `solver.ctqmc.in` via `p_ctqmc_solver`) +
`pyiqist`/`iqist` (the compiled solver bindings: `init_ctqmc`, `exec_ctqmc`,
`get_grnf`, `set_hybf`, `stop_ctqmc`). Single-band Hubbard, U = 1..4, μ = U/2, β = 50,
t = 0.5.

```python
#!/usr/bin/env python
import numpy
import shutil
from mpi4py import MPI
from u_ctqmc import *               # writer for solver.ctqmc.in
from pyiqist import api as ctqmc    # python binding for the solver

comm = MPI.COMM_WORLD
mfreq = 8193
norbs = 2
size_t = mfreq * norbs * norbs
hybf_s = numpy.zeros(size_t, dtype=numpy.complex)

for u in range(1, 5):               # loop over interaction strength
    if comm.rank == 0:              # master writes the config file
        p = p_ctqmc_solver('azalea')
        p.setp(isscf=1, isbin=1)
        p.setp(beta=50.0)
        p.setp(Uc=u, mune=u/2.0)
        p.write()                   # -> solver.ctqmc.in
        del p
    comm.Barrier()

    ctqmc.init_ctqmc(comm.rank, comm.size)
    for i in range(20):             # DMFT self-consistency, 20 iters
        ctqmc.exec_ctqmc(i+1)
        grnf = ctqmc.get_grnf(size_t)
        hybf = (0.25*grnf + hybf_s)/2.0   # Bethe self-consistency Δ = t²G, t=0.5
        hybf_s = hybf
        ctqmc.set_hybf(size_t, hybf)
    ctqmc.stop_ctqmc()
    comm.Barrier()

    if comm.rank == 0:
        shutil.move('solver.grn.dat',  'solver.grn.dat.'  + str(u))
        shutil.move('solver.hist.dat', 'solver.hist.dat.' + str(u))
```
```
$ mpiexec -n 4 ./dmft.py
```
A Mott metal–insulator transition appears between U=2 and U=3; the expansion order in
`solver.hist.dat` decreases as U grows.

Minimal Fortran/Python solver call (from the API section):
```python
from mpi4py import MPI
from pyiqist import api as ctqmc
comm = MPI.COMM_WORLD
ctqmc.init_ctqmc(comm.rank, comm.size)   # initialize
ctqmc.exec_ctqmc(1)                       # run one solve
ctqmc.stop_ctqmc()                        # finalize
```
Modern auxiliary Python tools: `u_ctqmc.py` (config writer), `u_atomic.py` (JASMINE
config), `u_reader.py`/`u_writer.py` (parse/produce data files), `u_movie.py`.

---

## 7. Pitfalls

- **Pick the right solver by interaction type.** Density-density → segment
  (AZALEA/GARDENIA/NARCISSUS), no `atom.cix`, fast. Spin-flip, pair-hopping, Slater U,
  or SOC → general matrix (BEGONIA/LAVENDER/PANSY/MANJUSHAKA), and you **must** run
  JASMINE to build `atom.cix` first. Using a segment solver on a general interaction
  silently drops the off-diagonal terms.
- **General-interaction cost explodes with orbitals.** The local trace is the bottleneck.
  BEGONIA/LAVENDER ≲3 bands; PANSY ≲5; only MANJUSHAKA (GQN + lazy trace + dynamical
  truncation) reaches 7 bands. The 2-band general example took ~16 min vs ~2 min for the
  segment single-band — budget accordingly, and use the cluster for ≥3 bands / low T.
- **Truncation bias.** Dynamical truncation (`itrun`/`nzero`) and occupation cut-offs
  speed up large multi-orbital traces but can bias results if a frequently-visited state
  is reached through a truncated one. Run convergence tests on the truncation level.
- **Matsubara / τ grid sizes.** `mfreq`/`nfreq` set the frequency resolution of G/Σ;
  `ntime` the imaginary-time resolution. Too-coarse grids distort the tail and the
  subsequent analytic continuation. Two-particle grids `nffrq`/`nbfrq` are memory-heavy —
  vertex measurement is the expensive observable.
- **MC statistics & autocorrelation.** Acceptance in CT-HYB is low (≈1–20%, worse at low
  T). Increase `nsweep` (and MPI ranks) for noise; `nmonte`/`ncarlo` should exceed the
  autocorrelation time so successive measurements are independent. Use the
  orthogonal-polynomial measurement (`isort`) and the improved estimator for clean Σ.
- **This is an impurity solver, not a lattice solver.** For a lattice problem you need a
  DMFT driver: use the built-in Bethe engine (`isscf=2`), or script the self-consistency
  yourself (Python API / external loop) supplying `solver.hyb.in` each iteration. iQIST
  alone does not solve a Hubbard *lattice* model.
- **Self-energy noise & analytic continuation.** Real-frequency spectra A(ω) require
  analytic continuation of G(τ) (max-entropy / stochastic) or Σ(iωₙ) (Padé /
  Gaussian-poly fit). This is ill-conditioned: noisy Matsubara data give unreliable
  spectra. Prefer the improved-estimator Σ and high statistics; modern docs recommend the
  **ACFlow** toolkit for this step.
- **No parameter sanity checks.** iQIST will not verify `norbs = 2*nband`,
  `ncfgs = 2**norbs`, or μ for your target filling — set them consistently yourself.
- **Compiler.** Officially built with the Intel Fortran compiler + MPI; other compilers
  are not guaranteed. Needs BLAS/LAPACK (OpenBLAS / Intel MKL recommended); Python tools
  need numpy/scipy/f2py.

---

## Source links

- Repository: https://github.com/huangli712/iQIST
- Current manual (index): https://huangli712.github.io/projects/iqist_new/index.html
- Solver chapter (ch04): https://huangli712.github.io/projects/iqist_new/ch04/index.html
- Choosing a solver: https://huangli712.github.io/projects/iqist_new/ch04/choose.html
- solver.ctqmc.in parameters: https://huangli712.github.io/projects/iqist_new/ch04/parameters.html
- Input file format pages: ch04/in_ctqmc.html, in_hyb.html, in_umat.html, in_eimp.html, in_atom.html
- Output file pages: ch04/out_grn.html, out_sgm.html (and siblings)
- Getting-started recipes: https://huangli712.github.io/projects/iqist_new/ch03/recipes.html
- Legacy gitbook manual: https://huangli712.gitbooks.io/iqist/content/
- Release paper (v1): https://arxiv.org/abs/1409.7573 — doi:10.1016/j.cpc.2015.04.020
- v0.7 paper: https://arxiv.org/abs/1708.07453
- Analytic continuation companion (ACFlow): https://github.com/huangli712/ACFlow
- Local rendered v1 paper: `.knowledge/literature/software/1409.7573_an-open-source-continuous-time-quantum-monte-carlo-impurity.md`
