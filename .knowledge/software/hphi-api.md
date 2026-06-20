# HΦ (HPhi) — input-file API & usage reference

HΦ ("aitch-phi") is a C/Fortran exact-diagonalization (ED) and finite-temperature
solver for quantum lattice models. It is **driven by input files**, not a library
API — so "API" here means the *input-file parameter set* + *run workflow* +
*example inputs*. It runs on PCs through massively parallel machines (MPI + OpenMP).

## What HΦ does

- **Models:** Hubbard (itinerant fermions), Heisenberg / general quantum spin
  (incl. Kitaev, Dzyaloshinskii–Moriya, single-ion anisotropy), Kondo lattice
  (itinerant electrons coupled to local spins), t-J, spinless fermions. Spin can be
  S = 1/2, 1, 3/2, … and mixed-spin per site.
- **Methods:** Lanczos (ground / few excited states), LOBPCG/LOBCG ("CG", multiple
  eigenstates), full diagonalization (all eigenpairs, small systems), and
  **thermal pure quantum (TPQ)** states for finite-temperature properties without
  ensemble averaging — its distinguishing feature, good for frustrated systems that
  defeat sign-problem-bound QMC. Also dynamical Green's functions and real-time
  evolution.
- **Outputs:** energy, doublon density, magnetization, one-/two-body equal-time
  Green's functions (→ charge/spin structure factors), and for TPQ the inverse
  temperature, energy, and energy variance at each step.
- **Restrictions (rule of thumb):** ≲ 20 sites for itinerant electrons, ≲ 40 sites
  for local-spin systems. Memory is set by the Hilbert-space dimension (see Pitfalls).

## Links

- Manual (master, EN): https://issp-center-dev.github.io/HPhi/manual/master/en/html/
- Repository: https://github.com/issp-center-dev/HPhi
- Samples: https://github.com/issp-center-dev/HPhi/tree/master/samples
- Release paper: M. Kawamura et al., *Comput. Phys. Commun.* **217**, 180 (2017),
  arXiv:1703.03637 — local render at
  `.knowledge/literature/software/1703.03637_quantum-lattice-model-solver-h.md`.

---

## Run workflow

Two modes differing only in input-file format:

- **Standard mode** — one short file (`StdFace.def`, conventionally `stan.in` in
  samples) of `keyword = value` lines. HΦ auto-generates the Expert-mode `.def`
  files, then runs.
- **Expert mode** — you supply all `.def` files yourself (arbitrary lattices /
  interactions); `namelist.def` lists them.

```bash
# Standard mode
$ Path/HPhi -s StdFace.def
$ mpiexec -np <nproc> Path/HPhi -s StdFace.def      # with MPI

# Expert mode
$ Path/HPhi -e namelist.def
$ mpiexec -np <nproc> Path/HPhi -e namelist.def

# Generate Expert-mode .def files from a Standard file WITHOUT running
# (dry run — do NOT use MPI here); then edit the .def files and run with -e
$ Path/HPhi -sdry StdFace.def

# Print version
$ Path/HPhi -v
```

**Parallelism.**
- OpenMP threads: `export OMP_NUM_THREADS=16` before launch.
- MPI process count is constrained:
  - Hubbard / Kondo: nproc must be a power of 4 (4ⁿ).
  - Spin: nproc must be (2S+1)ⁿ (e.g. 2ⁿ for S = 1/2).
  - nproc = 1 always works.
- Hybrid MPI + OpenMP is the intended large-scale mode.

**Output location.** Results and logs go to an auto-created `output/` directory in
the working dir. Build the executable with CMake (`cmake $PathTohphi && make`, exe at
`src/HPhi`) or `bash HPhiconfig.sh <gcc|intel|sekirei|fujitsu>; make HPhi`. Needs a C
compiler + BLAS/LAPACK; MPI optional. Visualize geometry with
`gnuplot lattice.gp` (HΦ writes `lattice.gp`).

---

## Standard-mode input parameters

A Standard file is plain `keyword = value` lines (strings quoted). Below, "—" means
no fixed default (often computed or mandatory). Specifying a forbidden combination
(e.g. `t` in a Spin model, `2Sz` in a GC model) makes HΦ stop.

### Calculation type

| Keyword | Meaning / allowed values |
|---|---|
| `model` | Target model. `"Fermion Hubbard"` (canonical), `"Spin"`, `"Kondo Lattice"`, grand-canonical variants `"Fermion HubbardGC"`, `"SpinGC"`, `"Kondo LatticeGC"`, and `"SpinGCCMA"` (faster GC spin, restricted feature set). Short forms `"Hubbard"`, `"Kondo"` are accepted in samples. |
| `method` | `"Lanczos"` (one eigenstate), `"CG"` (LOBCG, multiple eigenstates), `"Full Diag"` (all eigenpairs), `"TPQ"` (finite-T), `"Time Evolution"` (real-time). |
| `lattice` | `"Chain Lattice"`, `"Square Lattice"`, `"Triangular Lattice"`, `"Honeycomb Lattice"`, `"Kagome"`, `"Ladder"`. Short forms (`"chain"`, `"square"`, `"triangular"`, `"Honeycomb"`) accepted. |

GC ("grand-canonical") models do **not** conserve particle number / Sz; canonical
models do (and require `nelec` / `2Sz`).

### Lattice geometry

Specify the supercell **either** by `W`/`L`/`Height` **or** by the lattice-vector
integers `a0W,a0L,a1W,a1L` (+ `a2W,a2L` in 3D). Using both → HΦ stops.

| Keyword | Meaning |
|---|---|
| `L` | Chain length; linear extent (also tetragonal/triangular/honeycomb/kagome). |
| `W` | Second linear extent (number of ladders for `Ladder`). |
| `Height` | Third extent (3D). |
| `a0W, a0L` | Components of 1st superlattice vector **a₀** = a0W·**e**_W + a0L·**e**_L (integers). |
| `a1W, a1L` | Components of 2nd superlattice vector **a₁**. |
| `a2W, a2L` | Components of 3rd superlattice vector (3D). |
| `Wsub, Lsub, Hsub` | Sublattice / cell-restriction extents (advanced; restrict the cell). |
| `phase0, phase1` | Boundary hopping phase (degrees) across a₀ / a₁ — twisted/anti-periodic BC; default 0 (periodic). |

The supercell area set by **a₀**, **a₁** gives the number of sites (see the
triangular example: `a0W=3,a0L=-1,a1W=-2,a1L=4` → 10 sites). Standard mode lattices
are periodic; phases tune the boundary.

### Conserved quantities (canonical only)

| Keyword | Meaning | Notes |
|---|---|---|
| `nelec` | Number of valence electrons (Hubbard/Kondo canonical). | Forbidden for GC models. |
| `2Sz` | Twice the total Sz sector (e.g. 0 for Sz = 0). | Forbidden for GC models. Restricts the Hilbert space → much smaller. |
| `2S` | Twice the local spin per site (1 = S½, 2 = S1, …). | Default 1. Spin models / local spins in Kondo. |

### Hamiltonian parameters

Sign / normalization conventions follow the paper's Eqs. (2)–(6); cross-check against
`.knowledge/conventions.md` before trusting a number.

**Hubbard / Kondo (itinerant):**

| Keyword | Meaning | Default |
|---|---|---|
| `mu` | Chemical potential (site potential). | 0 |
| `U` | On-site Coulomb interaction. | 0 |
| `t` | Nearest-neighbor hopping (simplified, complex allowed; non-ladder). | 0 |
| `t0, t1, t2` | Direction-resolved NN hopping (all lattices, incl. ladder). | 0 |
| `t', t0', …` | 2nd-NN hopping (non-ladder). | 0 |
| `t'', …` | 3rd-NN hopping (non-ladder). | 0 |
| `V` | NN off-site Coulomb (simplified). | 0 |
| `V0, V1, V2` | Direction-resolved NN off-site Coulomb. | 0 |
| `V', V''` (+ indexed) | 2nd-/3rd-NN off-site Coulomb. | 0 |
| `J` (Kondo) | Kondo coupling between itinerant and local spins (sets Jx=Jy=Jz=J). | 0 |
| `Jx, Jy, Jz` (Kondo) | Anisotropic Kondo coupling components. | 0 |
| `Jxy, Jyx, Jxz, Jzx, Jyz, Jzy` (Kondo) | Off-diagonal Kondo couplings. | 0 |

**Spin models:**

| Keyword | Meaning | Default |
|---|---|---|
| `J` | NN isotropic exchange (sets Jx=Jy=Jz=J). | 0 |
| `Jx, Jy, Jz` | NN diagonal exchange components (all bonds). | 0 |
| `Jxy, Jyx, Jxz, Jzx, Jyz, Jzy` | NN off-diagonal (anisotropic / DM-like) exchange. | 0 |
| `J0*, J1*, J2*` (e.g. `J0x`, `J1y`, `J2z`, …) | **Bond-resolved** NN exchange: J0/J1/J2 = the 1st/2nd/3rd bond *direction* of the lattice (used for Kitaev: x/y/z bonds). | 0 |
| `J'`, `J'x … J'zy` | 2nd-NN exchange (all lattices). | 0 |
| `J''`, `J''x …` | 3rd-NN exchange (1D/2D). | 0 |
| `h` | Longitudinal magnetic field (−h·ΣSᶻ). | 0 |
| `Gamma` | Transverse magnetic field (−Γ·ΣSˣ). | 0 |
| `D` | Single-site (single-ion) anisotropy D·Σ(Sᶻ)² (not in SpinGCCMA). | 0 |

Note the two different uses of the `J0/J1/J2` prefix: in spin models the trailing
component letters (`J0x`, `J0y`, `J0z`, off-diagonals like `J0xy`) give the full
exchange tensor on bond direction 0/1/2 — this is how the Kitaev model is built
(`J0x`, `J1y`, `J2z` only). For Kondo, `Jx/Jy/Jz` instead mean the impurity coupling.

### Numerical conditions

| Keyword | Meaning | Default |
|---|---|---|
| `Lanczos_max` | Max iterations for Lanczos / LOBCG / BiCG and TPQ steps. | 2000 |
| `exct` | Number of eigenvectors (lowest states) to obtain. | 1 |
| `LanczosEps` | Eigenvalue convergence tolerance = 10^(−value). | 14 |
| `LanczosTarget` | Target eigenstate index for convergence test (1 = ground state). | 2 |
| `initial_iv` | Initial-vector seed / index for the eigensolver (random if <0). | -1 |
| `InitialVecType` | `"C"` (complex) or `"R"` (real) initial vector. | "C" |
| `NumAve` | **TPQ:** number of independent random-vector runs to average (→ error bars). | 5 |
| `ExpecInterval` | **TPQ:** step interval at which correlation functions are computed. | 20 |
| `LargeValue` | **TPQ:** energy-shift constant *l* in (l − ℋ/Nₛ); default = Σ|coeff|/Nₛ. | computed |
| `OutputMode` | Correlation-function output: `"none"`, `"correlation"`, `"full"`. | "correlation" |
| `EigenVecIO` | Eigenvector file I/O: `"None"`, `"Out"`, `"In"`. | "None" |
| `HamIO` | (Full Diag) Hamiltonian matrix I/O: `"None"`, `"Out"`, `"In"`. | "None" |
| `OutputExcitedVec` | Output excited vector: `"None"`, `"Out"`. | "None" |
| `Restart` | Restart control: `"None"`, `"Restart_out"`, `"Restart_in"`, `"Restart"` (both). | "None" |

Dynamical-Green's-function knobs (`CalcSpec` mode): `NOmega`, `OmegaMax`, `OmegaMin`,
`OmegaIm` (broadening η), plus `SpectrumType`/`SpectrumQW`,`SpectrumQL`. Time-evolution
knobs live under `Parameters_for_time-evolution`.

---

## Expert mode — the `.def` files

When `-s` is run (or `-sdry`), these are generated; in Expert mode you write them.
`namelist.def` (the "List" file) maps keyword → filename for every file below.

| File (keyword) | Specifies |
|---|---|
| `CalcMod` | Calculation mode: method (Lanczos/CG/FullDiag/TPQ/…), model class (Hubbard/Spin/Kondo), canonical vs GC, output flags. |
| `ModPara` | Basic parameters: number of sites, electrons, 2Sz, Lanczos_max, exct, eps, NumAve, ExpecInterval, file-head names, etc. |
| `LocSpin` | Which sites are localized spins and their 2S (Kondo / mixed-spin systems). |
| `Trans` | One-body terms tᵢⱼ (hopping, chemical potential, magnetic field) — generalized transfer integrals. |
| `InterAll` | Fully general two-body interaction I_{iσ jσ' kσ'' lσ'''} (anything not covered by the specialized files below). |
| `CoulombIntra` | On-site Coulomb U·nᵢ↑nᵢ↓. |
| `CoulombInter` | Off-site Coulomb V·nᵢnⱼ. |
| `Hund` | Hund coupling (parallel-spin density interaction). |
| `Exchange` | Spin-exchange Sᵢ⁺Sⱼ⁻ + h.c. terms. |
| `Ising` | Ising SᵢᶻSⱼᶻ terms. |
| `PairHop` | Pair-hopping processes. |
| `PairLift` | Pair-lift (pair-creation/annihilation-like) terms. |
| `OneBodyG` | List of one-body Green operators ⟨cᵢσ†cⱼσ'⟩ to output. |
| `TwoBodyG` | List of two-body Green operators ⟨cᵢσ†cⱼσ'cₖσ''†cₗσ'''⟩ to output. |
| `SingleExcitation` | Excitation operator for single-particle dynamical Green's functions. |
| `PairExcitation` | Excitation operator for pair dynamical Green's functions. |

Editing the auto-generated `.def` files (after `-sdry`) is the standard route for
models/lattices that Standard mode does not support.

---

## Output files (in `output/`)

| File | Contents |
|---|---|
| `zvo_energy.dat` | Ground/excited energies. Three labeled values per state: `Energy`, `Doublon` (= (1/Nₛ)Σ⟨nᵢ↑nᵢ↓⟩), `Sz` (= ⟨Sᶻ⟩). CG writes one block per state. |
| `zvo_Lanczos_Step.dat` | Energy vs Lanczos iteration (convergence trace). |
| `zvo_Eigenvalue.dat` | Eigenvalues (Full Diag). |
| `zvo_phys_*.dat` | Physical quantities (energy, doublon, Sz, …) — Full Diag / per-state. |
| `SS_rand??.dat` | **TPQ**, one per random sample `??`. Columns: `inv_temp` (β=1/kT), `⟨ℋ⟩` energy, `⟨ℋ²⟩`, doublon Σ⟨nᵢ↑nᵢ↓⟩, particle number ⟨n̂⟩, step index. Energy variance = ⟨ℋ²⟩−⟨ℋ⟩². |
| `Norm_rand??.dat` | **TPQ** norm of each (unnormalized) TPQ state per step. |
| `Flct_rand??.dat` | **TPQ** fluctuations (particle-number / Sz variance) per step. |
| `Time_TPQ_Step.dat` | TPQ step timing. |
| `zvo_cisajs*.dat` | One-body Green's function ⟨cᵢσ₁†cⱼσ₂⟩. Columns: `i  σ₁  j  σ₂  Re  Im` (σ: 0=up, 1=down). |
| `zvo_cisajscktalt*.dat` | Two-body Green's function ⟨cᵢσ₁†cⱼσ₂cₖσ₃†cₗσ₄⟩ (8 int + Re + Im). |
| `zvo_eigenvec_*.dat` | Eigenvector coefficients (binary; for restart / post-processing). |
| `zvo_Ham.dat` | Hamiltonian matrix elements (small systems, `HamIO=Out`). |
| `CHECK_*.dat` | Echo of parsed terms (Chemi, CoulombIntra, Hund, InterAll, INTER_U) — sanity check. |
| `CHECK_Memory.dat` | Estimated memory. |
| `CalcTimer.dat`, `TimeKeeper.dat` | Detailed / overall timing. |
| `WarningOnTransfer.dat` | Warnings about transfer-integral input. |
| `zvo_DynamicalGreen.dat`, `zvo_TMcomponents.dat`, `residual.dat` | Dynamical Green's function spectrum + tridiagonal components + residuals. |

Console final line (canonical example):
`i= 0 Energy=-11.228483 N= 16.000000 Sz= 0.000000 Doublon= 0.000000`.

---

## Worked examples (verbatim from samples)

### 1. Heisenberg square lattice, ground state (CG/Lanczos)

`samples/old/CG/Heisenberg/stan.in`:

```
model = "Spin"
method = "CG"
lattice = "square"
W = 4
L = 4
J = 1.0
2Sz = 0
```

S = ½ antiferromagnetic Heisenberg on a 4×4 = 16-site square lattice, total-Sz = 0
sector, ground state by LOBCG. Switch `method = "Lanczos"` for a single-state Lanczos
run. The minimal Heisenberg-chain example from the paper:

```
L = 4
W = 4
model = "Spin"
method = "Lanczos"
lattice = "square lattice"
J = 1.0
2Sz = 0
```

### 2. Spin-1 Heisenberg chain, full diagonalization

`samples/tutorial_1.1/stan1.in`:

```
L = 2
model = "Spin"
method = "FullDiag"
lattice = "chain"
J = 0.5
2Sz = 0
2S  = 1
```

`2S = 1` makes each site S = 1; FullDiag returns the whole spectrum (use only for
tiny systems). `Doublon`/`Sz` reported in `zvo_energy.dat`.

### 3. Finite-temperature TPQ (Kitaev model on honeycomb)

`samples/old/TPQ/Kitaev/stan.in`:

```
W = 2
L = 3
model = "SpinGC"
method = "TPQ"
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
2S=1
```

Kitaev model = Ising-like exchange but on a *different spin component per bond
direction*: x-bonds couple Sˣ (`J0x`), y-bonds Sʸ (`J1y`), z-bonds Sᶻ (`J2z`).
`SpinGC` (grand-canonical: no Sz conservation) + `method="TPQ"` gives T-dependent
energy and specific heat. Read `SS_rand0.dat`, `SS_rand1.dat`, … (`NumAve` of them):
column 1 = β, column 2 = ⟨ℋ⟩; average across the random samples and take the spread
as the error bar. Specific heat C = (⟨ℋ²⟩−⟨ℋ⟩²)/(Nₛ T²) from columns 2–3. Raise
`NumAve` (default 5) for tighter error bars. To run more TPQ steps (lower T), raise
`Lanczos_max`.

### 4. Hubbard square lattice (canonical, half-filling)

`samples/old/CG/Hubbard/stan.in`:

```
model = "Hubbard"
method = "CG"
lattice = "square"
a0W = 2
a0L = 2
a1W = -2
a1L = 2
t = 1.0
U = 8.0
nelec = 8
2Sz = 0
exct = 1
```

8-site tilted square cell, U/t = 8, half-filling (`nelec = 8`), Sz = 0.

### 5. Kondo lattice (triangular)

`samples/old/CG/Kondo/stan.in`:

```
model = "Kondo"
method = "CG"
lattice = "Triangular"
a0W = 3
a0L = 0
a1W = -1
a1L = 2
t = 1.0
J = 1.0
nelec = 6
2Sz = 0
exct = 1
```

`t` = conduction hopping, `J` = Kondo coupling to the local spins.

---

## Pitfalls

- **Standard vs Expert.** Standard mode only covers the built-in lattices/models;
  anything else (custom geometry, arbitrary InterAll terms) needs Expert mode. Best
  route: `HPhi -sdry StdFace.def` → edit the generated `.def` files → `HPhi -e
  namelist.def`. A forbidden Standard keyword (e.g. `t` in a Spin model, `2Sz` in a
  GC model) aborts the run.
- **Canonical vs grand-canonical / 2Sz conservation.** Canonical models (`"Spin"`,
  `"Hubbard"`, `"Kondo Lattice"`) require `nelec`/`2Sz` and exploit the conserved
  sector → drastically smaller Hilbert space and memory. GC models (`*GC`) do **not**
  conserve Sz/N (full space) — slower/larger but needed for, e.g., transverse-field
  or TPQ where you want the whole space. Make sure the target ground state actually
  lives in the `2Sz` sector you pick.
- **TPQ averaging & error bars.** A TPQ run uses random initial vectors; a single run
  is *noisy*. Run `NumAve` independent samples (`SS_rand0..N`), average the columns,
  and report the standard deviation as the error bar. Noise grows at low T (large
  step). β is *estimated* (β ≈ 2k/(Nₛ(l−uₖ))), not exact — read it from column 1, do
  not assume a uniform grid. `LargeValue` (l) must exceed the spectrum top; the
  default Σ|coeff|/Nₛ is safe — lowering it can break positivity.
- **Memory ~ basis size.** RAM is set by the Hilbert-space dimension D: ~16 bytes
  (double-complex) per amplitude, ×2–3 working vectors (Lanczos/TPQ keep diagonal +
  index vectors; CG/inverse-iteration need more). 40-site S½ GC spin = 2⁴⁰ ≈
  1.1×10¹² states ≈ 17.6 TB — only feasible distributed over many MPI ranks. Estimate
  D *before* running; use `2Sz`/`nelec` to shrink it; check `CHECK_Memory.dat`.
  Full Diag stores the whole matrix (D²) — tiny systems only.
- **MPI process count is constrained:** 4ⁿ (Hubbard/Kondo) or (2S+1)ⁿ (Spin). A wrong
  nproc aborts.
- **Sign convention.** HΦ's H₀ carries an overall minus on hopping (Eq. 2) and the
  spin/field signs follow Eq. (5). Verify against `.knowledge/conventions.md` and a
  trivial limit before trusting energies.

---

## Source links

- Manual index: https://issp-center-dev.github.io/HPhi/manual/master/en/html/
- Basic usage (run modes, MPI/OpenMP): https://issp-center-dev.github.io/HPhi/manual/master/en/html/howtouse/basicusage_en.html
- Standard-mode params index: https://issp-center-dev.github.io/HPhi/manual/master/en/html/filespecification/standardmode_en/index_standardmode_en.html
  - calc type: `.../standardmode_en/Parameters_for_the_type_of_calculation_en.html`
  - lattice: `.../standardmode_en/Parameters_for_the_lattice_en.html`
  - conserved: `.../standardmode_en/Parameters_for_conserved_quantities_en.html`
  - Hamiltonian: `.../standardmode_en/Parameters_for_the_Hamiltonian_en.html`
  - numerical: `.../standardmode_en/Parameters_for_the_numerical_condition.html`
- Expert-mode files: https://issp-center-dev.github.io/HPhi/manual/master/en/html/filespecification/expertmode_en/index_expertmode_en.html
- Output files: https://issp-center-dev.github.io/HPhi/manual/master/en/html/filespecification/outputfiles_en/index_outputfiles_en.html
- Algorithms (Lanczos/FullDiag/TPQ/Dynamical/Realtime): https://issp-center-dev.github.io/HPhi/manual/master/en/html/algorithm/al-index.html
- Samples: https://github.com/issp-center-dev/HPhi/tree/master/samples
- Paper: https://arxiv.org/abs/1703.03637 (DOI 10.1016/j.cpc.2017.04.006)
