# DSQSS — API & Examples Reference

**DSQSS** (Discrete Space Quantum Systems Solver) is an open-source program package for
finite-temperature quantum Monte Carlo (QMC) of quantum lattice models. It uses the
**continuous-time path-integral (worldline) QMC** with a **directed-loop algorithm (DLA)**,
covering **quantum spin-S** and **Bose-Hubbard** models on arbitrary lattices, as long as the
model is **sign-problem-free** (non-frustrated spins, bosons). It can output static
observables *and* imaginary-time correlation functions (for dynamic structure factors via
analytic continuation).

- Languages: C++ (solver) + Python (preprocessing / postprocessing). License: GPL v3.
- Reference: Y. Motoyama, K. Yoshimi, A. Masaki-Kato, T. Kato, N. Kawashima,
  *DSQSS: Discrete Space Quantum Systems Solver*, Comput. Phys. Commun. **264** (2021) 107944,
  arXiv:2007.11329 (rendered locally at
  `.knowledge/literature/software/2007.11329_dsqss-discrete-space-quantum-systems-solver.md`).

## Two subpackages

| Subpackage | Algorithm | Use case | Main tools |
|---|---|---|---|
| **DSQSS/DLA** | on-the-fly directed-loop algorithm (single worm) | general models / arbitrary lattices; the everyday workflow | `dla`, `dla_pre`, `dla_*gen`, `dla_alg` |
| **DSQSS/PMWA** | parallelized multiple-worm algorithm (domain decomposition) | extreme system sizes on massively parallel machines; **S=1/2 XXZ** or **hard-core boson** only | `pmwa_H`, `pmwa_B`, `pmwa_pre` |

**Most usage = DSQSS/DLA.** PMWA is for very large lattices and requires a finite transverse
field Γ (or boson source) that must be extrapolated to Γ→0.

---

## 1. Installation

```
$ mkdir dsqss.build
$ cd dsqss.build
$ cmake ../
$ make
$ make test          # verify the binaries
$ make install
```

Requires a C++ compiler, CMake ≥ 2.8.12, MPI (optional, for parallel runs), and Python ≥ 3.6
with `numpy`, `scipy`, `toml`. Default install prefix `/usr/local`; override with
`cmake -DCMAKE_INSTALL_PREFIX=/path/to/install ../`.

Install puts executables in `bin/`, samples in `share/dsqss/VERSION/samples/`, and the Python
package `dsqss` in `lib/`. **Before running, source the env file** so the tools and Python
package are on `PATH`/`PYTHONPATH`:

```
$ source <prefix>/share/dsqss/dsqssvars-VERSION.sh
```

---

## 2. DSQSS/DLA run workflow

A DLA calculation is three stages: **(i) prepare input files → (ii) run `dla` → (iii) analyze
results.** Inputs come in two flavors:

- **Simple mode** — one TOML file (`std.toml`) with predefined models (spin / boson) and
  predefined lattices (hypercubic / triangular). `dla_pre` expands it into all solver inputs.
  This covers the large majority of calculations.
- **Standard mode** — you hand-write lattice / Hamiltonian definition files (`lattice.toml`,
  `hamiltonian.toml`, lattice `.dat`) for custom models/lattices, then `dla_alg` builds the
  solver XML. Use only when a model/lattice is not predefined (e.g. SU(N) Heisenberg,
  multi-body interactions).

### Solver input files (consumed by `dla`)

`dla` itself reads a **parameter file** (`param.in`) which points to the other XML files:

| File | Contents |
|---|---|
| `param.in` | temperature, MC settings, RNG seed, output filenames; references the XML files below |
| `lattice.xml` | lattice geometry (sites, bonds, coordinates) |
| `algorithm.xml` | vertex structure, scattering probability matrices, post-scattering state tables |
| `wv.xml` | wavevectors (k-points) for staggered magnetization, S(k,ω), momentum Green's functions |
| `disp.xml` | relative coordinates for real-space temperature Green's functions |

In simple mode you never edit these by hand; `dla_pre` generates them.

### Simple-mode workflow (the common path)

```
$ dla_pre std.toml          # std.toml -> param.in, lattice.xml, algorithm.xml, wv.xml, disp.xml
$ dla param.in              # run the QMC
$ grep ene sample.log       # read results
```

Parallel (MPI random-number parallelization — multiplies total samples by #procs, error ~ 1/√Nproc):

```
$ mpiexec -np 4 dla param.in
```

### Preprocessing tools

`dla_pre` is the all-in-one. Individual generators exist if you want to build pieces of a
standard-mode workflow:

| Tool | Purpose | Syntax | Output (default) |
|---|---|---|---|
| `dla_pre` | simple mode: expand `std.toml` into all solver inputs | `dla_pre [-p paramfile] std.toml` | `param.in`, `lattice.xml`, `algorithm.xml`, `wv.xml`, `disp.xml` |
| `dla_latgen` | lattice `.dat`/`.toml`/Gnuplot from `[lattice]` | `dla_latgen [-o lattice.dat] [-t lattice.toml] [-g lat.gp] input` | `lattice.dat` |
| `dla_hamgen` | Hamiltonian `.toml` from `[hamiltonian]` | `dla_hamgen [-o hamiltonian.toml] input` | `hamiltonian.toml` |
| `dla_pgen` | parameter file from `[parameter]` | `dla_pgen [-o param.in] input` | `param.in` |
| `dla_wvgen` | wavevector `.dat` for correlations | `dla_wvgen [-o kpoints.dat] [-s "L1 L2"] input` | `kpoints.dat` |
| `dla_alg` | standard mode: lattice/Ham → solver XML | `dla_alg [-l LAT] [-h HAM] [-L lattice.xml] [-A algorithm.xml] [-k KPOINT] [--kernel KERNEL] ...` | `lattice.xml`, `algorithm.xml`, `wavevector.xml`, `disp.xml` |

`dla_alg` flags of note: `--without_lattice` / `--without_algorithm` skip a stage;
`-k KPOINT` (input k-points), `--wv WV` (output), `--disp DISP` (relative-coords output),
`--distance-only` (group pairs by absolute distance), `--kernel KERNEL` (default `"suwa todo"`).

### Python interface

The same workflow is scriptable — `dla_pre` is callable as a function and `Results` parses
output. This is how the parameter-scan samples (`exec.py`) work:

```python
from dsqss.dla_pre import dla_pre
from dsqss.result import Results

# dla_pre(dict, paramfile): writes param.in + XMLs from in-memory sections
dla_pre({"parameter": parameter, "hamiltonian": hamiltonian, "lattice": lattice}, "param.in")

res = Results("res.dat")        # parses every "R <name> = <mean> <err>" line of the output
res.result["ene"].mean          # expectation value
res.result["ene"].err           # statistical error
res.to_str("xmzu")              # "<mean> <err>"
res.to_str(["ene", "xmzu"])     # space-joined
```

---

## 3. Input parameters (`std.toml`)

Five sections. Only `[hamiltonian]`, `[lattice]`, `[parameter]` are required.

### `[hamiltonian]`

Two predefined models. **`model = "spin"`** — generalized XXZ:

H = − Σ⟨i,j⟩ [ Jz·SᵢᶻSⱼᶻ + (Jxy/2)(Sᵢ⁺Sⱼ⁻ + Sᵢ⁻Sⱼ⁺) ] + D Σᵢ (Sᵢᶻ)² − h Σᵢ Sᵢᶻ

**`model = "boson"`** — Bose-Hubbard:

H = Σ⟨i,j⟩ [ −t(bᵢ†bⱼ + h.c.) + V nᵢnⱼ ] + Σᵢ [ (U/2) nᵢ(nᵢ−1) − μ nᵢ ]

| Key | Model | Meaning | Typical value |
|---|---|---|---|
| `model` | both | `"spin"` or `"boson"` | — |
| `M` | both | local Hilbert-space size − 1. Spin: `M = 2S` (M=1 → S=½, M=2 → S=1). Boson: max occupancy nₘₐₓ (M=1 → hard-core) | `1` |
| `Jz` | spin | Ising coupling. **Sign: Jz<0 ⇒ AFM** in this convention (note minus sign in H) | `-1.0` |
| `Jxy` | spin | transverse (XY) coupling; `Jxy<0` AFM. Heisenberg: `Jz=Jxy` | `-1.0` |
| `h` | spin | longitudinal magnetic field (along z) | `0.0` |
| `D` | spin | single-ion anisotropy (single-spin (Sᶻ)² term) | `0.0` |
| `t` | boson | hopping amplitude | `1.0` |
| `U` | boson | on-site repulsion (ignored if hard-core, M=1) | `1.0` |
| `V` | boson | nearest-neighbor repulsion | `1.0`–`3.0` |
| `mu` | boson | chemical potential | scan |

Couplings may be **per-bond-direction lists**, e.g. `Jxy = [-1.0, 1.0]` (anisotropic / J1-J2-style)
and `bc = [true, false]` per axis.

### `[lattice]`

| Key | Meaning | Typical value |
|---|---|---|
| `lattice` | predefined lattice: `"hypercubic"` (chain/square/cubic) or `"triangular"` | `"hypercubic"` |
| `dim` | spatial dimension | `1`, `2`, `3` |
| `L` | linear size; scalar (same each axis) or list `[L1, L2, …]` | `30`, `[8,8]` |
| `bc` | periodic boundary if `true`, open if `false`; scalar or per-axis list | `true` |

### `[parameter]` (also the `param.in` contents)

| Key | Meaning | Typical value |
|---|---|---|
| `beta` | inverse temperature β = 1/T (sets temperature; **no kB factor**) | `10`–`100` |
| `nset` | number of measurement "sets" (bins); error bars from set-to-set variance | `4`–`10` |
| `npre` | MC steps to estimate the DLA hyperparameter (worm density η) | `10`–`10000` |
| `ntherm` | MC sweeps for thermalization (discarded) | `100`–`1000` |
| `ndecor` | MC sweeps for decorrelation between measurements | `100`–`1000` |
| `nmcs` | MC sweeps for measurement (per set) | `100`–`1000` |
| `seed` | RNG seed | `31415` |
| `outfile` | main results file | `sample.log` |
| `wvfile` | wavevector XML to load | `wv.xml` |
| `dispfile` | relative-coordinate XML to load | `disp.xml` |
| `sfoutfile` / `cfoutfile` / `ckoutfile` | structure-factor / real-space-correlation / k-space-correlation output files | — |

One MC sweep = N_cycle MC cycles, where N_cycle is auto-tuned so the worm-head travel distance
per sweep equals the spacetime volume N_sites·β.

### `[kpoints]` (optional)

`ksteps` — interval (stride) for measurements in wavenumber space.

### `[algorithm]` (optional)

`kernel` — scattering-probability rule for worm heads:

| Kernel | Notes |
|---|---|
| `"suwa todo"` (default) | rejection-minimized, irreversible (no detailed balance); usually best mixing |
| `"reversible suwa todo"` | rejection-minimized with detailed balance |
| `"heat bath"` | Gibbs sampler |
| `"metropolis"` | Metropolis-Hastings |

### Standard-mode helper files

- `hamiltonian.toml` — custom Hamiltonian (e.g. SU(N) Heisenberg, multi-body terms).
- `lattice.toml` / `lattice.dat` — custom unit cell, sites, bonds, coordinates.

Examples of `dla_hamgen` / `dla_latgen` simple-mode snippets:

```toml
# S=1/2 AF Heisenberg
[hamiltonian]
model = "spin"
M = 1
Jz = -1.0
Jxy = -1.0

# Hard-core boson
[hamiltonian]
model = "boson"
M = 1
t = 1.0
V = 1.0

# Soft-core boson (up to n=2)
[hamiltonian]
model = "boson"
M = 2
t = 1.0
U = 1.0
V = 1.0
mu = 1.0
```

```toml
# two-leg ladder 8x2, periodic along leg, open along rung
[lattice]
lattice = "hypercubic"
dim = 2
L = [8, 2]
bc = [true, false]
```

---

## 4. Output & observables (`sample.log`)

Every measured quantity is one line: **`R <label> = <mean> <error>`** — value and statistical
(standard) error. Read with `grep`, or programmatically via `Results`.

```
$ grep ene sample.log
R ene = -3.74380000e-01 5.19493985e-03
```

| Label | Observable |
|---|---|
| `sign` | average sign of the weights (should be ≈1 for sign-free models) |
| `anv` | number of vertices per site |
| `ene` | energy density (energy per site) |
| `spe` | specific heat |
| `som` | specific heat / temperature |
| `len` | mean worm length |
| `xmx` | transverse susceptibility |
| `amzu` | uniform magnetization (τ=0 estimator) |
| `bmzu` | uniform magnetization (τ-averaged estimator) |
| `smzu` | uniform structure factor |
| `xmzu` | uniform longitudinal susceptibility |
| `amzs<K>` / `bmzs<K>` | staggered magnetization at k-point K (τ=0 / τ-averaged) |
| `smzs<K>` | staggered structure factor |
| `xmzs<K>` | staggered longitudinal susceptibility |
| `ds1` | temperature derivative of uniform magnetization |
| `wi2` | winding number (squared) |
| `rhos` | superfluid density (helicity modulus / spin stiffness) |
| `rhof` | superfluid fraction |
| `comp` | compressibility |
| `time` | wall time per MC sweep (seconds) |

Notes on conventions:
- For **boson** models, `amzu`/`bmzu` (the "Sᶻ" diagonal observable) is the **particle number /
  density n** (Sᶻ ↔ nᵢ − ½ mapping); the boson sample reads density from `amzu`.
- **Superfluid density / spin stiffness** is the helicity modulus, computed from winding numbers:
  ρs = ⟨ Σµ Lµ Wµ² ⟩ / (β d V), with V = Lx·Ly·Lz.
- Static structure factor S = N(⟨A₁²⟩ − ⟨A₁⟩²) and susceptibility χ = Nβ(⟨A₂²⟩ − ⟨A₂⟩²) (fluctuation–dissipation).
- Auxiliary correlation files: `sfoutfile` (structure factor), `cfoutfile` (real-space
  imaginary-time Green's function G(r,τ)), `ckoutfile` (k-space G(k,τ)) — the latter feed
  dynamic structure factor S(k,ω) via numerical analytic continuation (a Padé example ships in
  `sample/dla/04_spindynamics`).

---

## 5. Worked examples (verbatim from the samples)

### 5.1 Heisenberg dimer energy — minimal end-to-end (`sample/dla/01_spindimer`)

S=1/2 AFM Heisenberg on 2 sites (open chain), β=100. Exact energy −3|J|/8 = −0.375|J|.

`std.toml`:

```toml
[hamiltonian]
model = "spin"
M =  1                 # S=1/2
Jz = -1.0              # coupling constant, negative for AF
Jxy = -1.0             # coupling constant, negative for AF
h = 0.0                # magnetic field

[lattice]
lattice = "hypercubic" # hypercubic, periodic
dim = 1                # dimension
L = 2                  # number of sites along each direction
bc = false             # open boundary

[parameter]
beta = 100             # inverse temperature
nset = 5               # set of Monte Carlo sweeps
npre = 10              # MCSteps to estimate hyperparameter
ntherm = 10            # MCSweeps for thermalization
nmcs = 100             # MCSweeps for measurement
seed = 31415           # seed of RNG
```

Run:

```
$ dla_pre std.toml
$ dla param.in
$ grep ene sample.log
R ene = -3.74380000e-01 5.19493985e-03
```

−0.3744 ± 0.0052 agrees with the exact −0.375 within error. This is the canonical limit-check
for verifying a fresh install / setup.

### 5.2 Magnetic susceptibility of AF spin chains (`sample/dla/02_spinchain`)

Temperature scan of uniform susceptibility χ(T) = `xmzu` for S=1/2 (M=1) and S=1 (M=2) AFM
Heisenberg chains, L=32 sites (the sample uses L=32; `L=30` also appears in docs), driven by a
Python loop that rebuilds inputs at each T = 1/β. S=1/2 stays gapless (finite χ as T→0); S=1 is
the Haldane chain (χ→0 from the spin gap).

`exec.py` (verbatim):

```python
import subprocess

from dsqss.dla_pre import dla_pre
from dsqss.result import Results

L = 32

lattice = {"lattice": "hypercubic", "dim": 1, "L": L}
hamiltonian = {"model": "spin", "Jz": -1, "Jxy": -1}
parameter = {"nset": 5, "ntherm": 1000, "ndecor": 1000, "nmcs": 1000,
             "wvfile": "wv.xml", "dispfile": "disp.xml"}

name = "xmzu"
Ms = [1, 2]
Ts = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5, 1.75, 2.0]

for M in Ms:
    output = open("{0}_{1}.dat".format(name, M), "w")
    for i, T in enumerate(Ts):
        ofile = "res_{}_{}.dat".format(M, i)
        pfile = "param_{}_{}.in".format(M, i)
        sfoutfile = "sf_{}_{}.dat".format(M, i)
        cfoutfile = "cf_{}_{}.dat".format(M, i)
        ckoutfile = "ck_{}_{}.dat".format(M, i)
        hamiltonian["M"] = M
        parameter["beta"] = 1.0 / T
        parameter["outfile"] = ofile
        parameter["sfoutfile"] = sfoutfile
        parameter["cfoutfile"] = cfoutfile
        parameter["ckoutfile"] = ckoutfile
        dla_pre(
            {"parameter": parameter, "hamiltonian": hamiltonian, "lattice": lattice},
            pfile,
        )
        cmd = ["dla", "param_{0}_{1}.in".format(M, i)]
        subprocess.call(cmd)
        res = Results(ofile)
        output.write("{} {}\n".format(T, res.to_str(name)))
    output.close()
```

Output `xmzu_1.dat` / `xmzu_2.dat` are three columns `T  <χ_mean>  <χ_err>`, ready to plot.
Run with `python exec.py` (after sourcing the env file).

### 5.3 Hard-core bosons on a square lattice (`sample/dla/03_bosesquare`)

Density n vs chemical potential μ for a hard-core (M=1) Bose-Hubbard model with NN repulsion
V=3, t=1 on an 8×8 square lattice, β=10. A plateau near μ≈6 marks the checkerboard solid phase.
Density is read from `amzu`.

`exec.py` (verbatim):

```python
import subprocess

from dsqss.dla_pre import dla_pre
from dsqss.result import Results

V = 3
L = [8, 8]
beta = 10.0

lattice = {"lattice": "hypercubic", "dim": 2, "L": L}
hamiltonian = {"model": "boson", "t": 1, "V": V, "M": 1}
parameter = {"beta": beta, "nset": 4, "ntherm": 100, "ndecor": 100,
             "nmcs": 100, "wvfile": "wv.xml", "dispfile": "disp.xml"}

name = "amzu"
mus = [-4.0, -2.0, 0.0, 2.0, 2.5, 3.0, 6.0, 9.0, 9.5, 10.0, 12.0, 14.0]

output = open("{}.dat".format(name), "w")
for i, mu in enumerate(mus):
    ofile = "res_{}.dat".format(i)
    pfile = "param_{}.in".format(i)
    sfoutfile = "sf_{}.dat".format(i)
    cfoutfile = "cf_{}.dat".format(i)
    ckoutfile = "ck_{}.dat".format(i)

    hamiltonian["mu"] = mu
    parameter["outfile"] = ofile
    parameter["sfoutfile"] = sfoutfile
    parameter["cfoutfile"] = cfoutfile
    parameter["ckoutfile"] = ckoutfile
    dla_pre(
        {"parameter": parameter, "hamiltonian": hamiltonian, "lattice": lattice}, pfile
    )
    cmd = ["dla", pfile]
    subprocess.call(cmd)
    res = Results(ofile)
    output.write("{} {}\n".format(mu, res.to_str(name)))
output.close()
```

### 5.4 Dynamic spin structure factor (`sample/dla/04_spindynamics`)

S=1/2 Heisenberg chain L=32, β=16; measures imaginary-time correlations (`ckoutfile`), then a
provided Padé-approximation script does numerical analytic continuation to get S(k,ω) (recovers
the des Cloizeaux–Pearson mode Ek = (πJ/2)·sin k). Analytic continuation is ill-conditioned, so
it needs high-statistics QMC data.

---

## 6. DSQSS/PMWA (large-scale, S=1/2 XXZ or hard-core boson only)

PMWA needs a finite transverse field Γ (spin) or particle source (boson) for the parallel
multi-worm update; results must be extrapolated to Γ→0. Workflow: `pmwa_pre std.in` →
`pmwa_lattice.xml` + `param.in`, then `mpiexec -np N pmwa_H param.in` (XXZ) or `pmwa_B`
(hard-core boson). The `[Parameter]` block adds spatial/temporal domain divisions `nldiv`,
`nbdiv` for parallelism.

Example `std.in`:

```
[System]
solver = PMWA
[Hamiltonian]
model_type = spin
Jxy = -1.0
Jz = -1.0
Gamma = 0.1
[Lattice]
lattice_type = square
D = 1
L = 8
Beta = 8.0
[Parameter]
runtype = 0
cb = 1
seed = 31415
nset = 10
nmcs = 10000
npre = 10000
ntherm = 10000
ndecor = 10000
latfile = lattice.xml
outfile = sample.log
nldiv = 2
nbdiv = 1
```

PMWA caution: an antiferromagnetic XY-like XXZ model with a *uniform* transverse field has a
sign problem even on a bipartite lattice; use a *staggered* field instead.

---

## 7. Pitfalls

- **Sign problem / applicability.** DLA is exact only for **sign-free** models: non-frustrated
  quantum spins (bipartite AFM, ferromagnets) and bosons. Frustrated AFM (triangular AFM,
  J1-J2 in the frustrated regime), fermions, and uniform transverse fields on AFM XY models are
  *not* covered — `sign` drifting from 1 is the tell. Triangular lattice is predefined but only
  meaningful for sign-free couplings.
- **Sign / coupling convention.** The spin Hamiltonian has an overall **minus sign**, so
  **Jz<0, Jxy<0 ⇒ antiferromagnetic**. This is opposite to the common "+J Sᵢ·Sⱼ" convention —
  set signs deliberately. `h` couples to Sᶻ (longitudinal).
- **Temperature is β = 1/T with no kB.** Low T = large β = longer worldlines = more cost
  (memory/time grow with β). Pick β for the physics, not by habit.
- **Thermalization / bins / autocorrelation.** `ntherm` must discard the burn-in; error bars
  come from `nset` independent sets, so use ≥ ~5–10 sets and `ndecor` large enough that sets are
  uncorrelated. Too-small `nset` gives unreliable error bars; correlated sets understate the
  error. `npre` auto-tunes the worm hyperparameter — keep it nonzero.
- **`M` is the *full* convention.** Spin: `M = 2S` (not S). Boson: `M = nₘₐₓ` (M=1 = hard-core,
  U irrelevant). Mixing these up silently simulates the wrong Hilbert space.
- **Lattice-file generation.** In simple mode let `dla_pre` build the XML; editing `lattice.xml`
  / `algorithm.xml` by hand is error-prone. For custom models go through standard mode
  (`hamiltonian.toml` + `lattice.toml` → `dla_alg`), not hand-edited XML.
- **Dynamic S(k,ω) needs high statistics.** Analytic continuation of imaginary-time data is
  ill-posed; budget far more sampling than for static observables.
- **MPI = more samples, not larger systems.** `mpiexec -np N dla` does random-number
  parallelization (N× samples, error ~1/√N), it does not split the lattice. For lattice
  (domain) parallelism use PMWA.

---

## Source links

- Manual (master, EN): https://issp-center-dev.github.io/dsqss/manual/master/en/
  - DLA intro / tutorial: https://issp-center-dev.github.io/dsqss/manual/master/en/dla/tutorial/intro.html
  - Spin dimer tutorial: https://issp-center-dev.github.io/dsqss/manual/master/en/dla/tutorial/spindimer.html
  - Spin chain tutorial: https://issp-center-dev.github.io/dsqss/manual/master/en/dla/tutorial/spinchain.html
  - Hard-core boson tutorial: https://issp-center-dev.github.io/dsqss/manual/master/en/dla/tutorial/bosesquare.html
  - Input-file generators: https://issp-center-dev.github.io/dsqss/manual/master/en/dla/users-manual/generator.html
  - Output observables: https://issp-center-dev.github.io/dsqss/manual/master/en/dla/users-manual/output.html
- Project page: https://www.pasums.issp.u-tokyo.ac.jp/dsqss/en/
- GitHub: https://github.com/issp-center-dev/dsqss (samples in `sample/dla/`, Python in `tool/dsqss/`)
- Paper: arXiv:2007.11329 — https://arxiv.org/abs/2007.11329 (DOI 10.1016/j.cpc.2021.107944)
- Local rendered paper: `.knowledge/literature/software/2007.11329_dsqss-discrete-space-quantum-systems-solver.md`
