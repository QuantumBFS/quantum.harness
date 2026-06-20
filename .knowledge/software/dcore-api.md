# DCore — Integrated DMFT software for correlated electrons

API + examples reference. DCore is an INI-file + command-line-tool driven Python package
that wraps several external quantum-impurity solvers into a turnkey dynamical mean-field
theory (DMFT) self-consistency loop, for multi-orbital Hubbard models and one-shot
DFT+DMFT (the latter via Wannier90).

- Docs: https://issp-center-dev.github.io/DCore/master/index.html
- GitHub: https://github.com/issp-center-dev/DCore (License GPL-3.0; ~97% Python)
- Release paper: Shinaoka, Otsuki, Kawamura, Takemori, Yoshimi, *SciPost Phys.* **10**, 117 (2021),
  arXiv:2007.00901, DOI 10.21468/SciPostPhys.10.5.117
- Local rendered paper: `.knowledge/literature/software/2007.00901_*.md`

> Note on versions: the **paper** (2020/2021) describes a single post-processor `dcore_post`
> and a `[tool]` block. The **current docs** split post-processing into `dcore_anacont`
> (analytic continuation) + `dcore_spectrum` (spectra), and replace the `[tool]` block with
> `[post]`, `[post.anacont]`, `[post.anacont.pade]`, `[post.spectrum]`, `[post.check]`. Both
> idioms appear below; prefer the `[post.*]` form for current DCore. `dcore_post` is retained
> as a wrapper in some versions but the split tools are canonical now.

---

## 1. What DCore does

DCore solves a tight-binding multi-orbital Hubbard model with periodic boundary conditions:

```
H = Σ_k Σ_{s,s'} Σ_{αβ} H^{αβ}_{ss'}(k) c†_{ksα} c_{ks'β}  +  Σ_{R,s∈corr} H_int(R,s)
H_int(R,s) = (1/2) Σ_{αβγδ} U_{αβγδ}(s) c†_{Rsα} c†_{Rsβ} c_{Rsδ} c_{Rsγ}
```

via the DMFT self-consistency cycle (local self-energy approximation):

```
G(k,iωₙ)        = [ iωₙ + μ − H(k) − Σ(iωₙ) + Σ_DC ]⁻¹     (lattice Green's fn)
G_loc(iωₙ,s)    = P_s ⟨G(k)⟩_k                              (k-average → correlated shell s)
G₀⁻¹(iωₙ,s)     = G_loc⁻¹ + Σ(iωₙ,s)                        (Weiss / bath)
Σ_imp(iωₙ,s)    ← solve impurity model (G₀, U)              (the expensive step)
Σ_new = σ_mix·Σ_imp + (1−σ_mix)·Σ_old                       (linear mixing, Eq. 14)
```

- **Two input modes for the one-body part H(k):**
  - **Predefined lattices** — `chain`, `square`, `cubic`, `bethe` with hoppings `t`, `t'`.
  - **Wannier90** — `lattice = wannier90` reads `seedname_hr.dat`; this is how DFT codes
    (QE, VASP, WIEN2k, ABINIT, SIESTA, OpenMX, FLEUR …) feed DCore (one-shot DFT+DMFT).
    `external` mode lets experts inject the `dft_input` HDF5 group directly.
- **Several impurity solvers** behind one interface: TRIQS/cthyb (CT-HYB QMC),
  ALPS/CT-HYB and ALPS/CT-HYB-SEGMENT (CT-HYB QMC), TRIQS/hubbard-I, pomerol (ED /
  Hubbard-I), scipy/sparse (ED), `null` (non-interacting). HΦ is also usable as an ED solver.
- **Outputs:** local self-energy Σ(iωₙ) convergence, density of states A(ω), and
  momentum-resolved spectral function A(k,ω) (correlated band structure) after analytic
  continuation (Padé or sparse-modeling).
- **Limitations:** intra-shell, local interactions only; **one-shot** DFT+DMFT (no charge
  self-consistency); analytic continuation by Padé is sensitive to QMC noise.

---

## 2. Installation

Pure-Python; depends on **TRIQS** and **TRIQS/DFTTools** (paper: TRIQS 3.0.x, Python 3).

```bash
pip3 install dcore           # system site-packages
pip3 install dcore --user    # user site-packages (no root)
pip3 show -f dcore           # locate installed executables
```

Ensure the executables `dcore`, `dcore_pre`, … are on `PATH`. At runtime **at least one
external impurity solver must be installed and on `PATH`** (TRIQS/cthyb, ALPS/CT-HYB,
ALPS/CT-HYB-SEGMENT, pomerol, …) — DCore itself ships no QMC/ED engine for interacting runs.
Install instructions per solver: https://issp-center-dev.github.io/DCore/master/impuritysolvers.html

---

## 3. Run workflow (the command-line tools)

One INI file is read by all tools; each block is relevant only to some tools (Table below).

```bash
dcore_pre     input.ini              # 1. build model HDF5 (seedname.h5)
dcore         input.ini --np 4       # 2. run DMFT loop  → seedname.out.h5
dcore_check   input.ini              # 3. convergence diagnostics → check/
dcore_anacont input.ini              # 4. analytic continuation Σ(iωₙ)→Σ(ω) → post/sigma_w.npz
dcore_spectrum input.ini --np 4      # 5. A(ω), A(k,ω) → post/dos.dat, post/akw.dat
```

(Legacy: a single `dcore_post input.ini --np 4` did steps 4+5 together.)

| Tool | Reads blocks | Produces |
|---|---|---|
| `dcore_pre` | `[model]` | `seedname.h5` (groups `dft_input`, `Dcore`: U-tensor, local potential) |
| `dcore` | `[model] [system] [impurity_solver] [control] [mpi]` | `seedname.out.h5` (group `dmft_out`); `work/imp_shell#_iter#/` temp solver files |
| `dcore_check` | `[model] [system] [post.check]` | `check/` text+PNG: `sigma.dat`, `iter_mu.*`, `iter_sigma-ish#.*`, `iter_occup-ish#.*`, `iter_spin-ish#.*` |
| `dcore_anacont` | `[model] [system] [post.anacont]` | `post/sigma_w.npz` (real-frequency Σ) |
| `dcore_spectrum` | `[model] [system] [post.spectrum] [mpi]` | `post/dos.dat`, `post/akw.dat`, `post/akw.gp`, `post/momdist.dat` |

**MPI.** Each DCore command is launched as a *single* process; `--np N` is the number of MPI
processes DCore spawns *internally* (for the k-average and for MPI-parallel CT-QMC solvers).
`dcore` and `dcore_spectrum` accept `--np`; `dcore_pre`/`dcore_check`/`dcore_anacont` do not.
The `[mpi]` block's `command` template controls how the MPI job is launched (`#` → N).

---

## 4. INI configuration blocks

### 4.1 `[model]` — what to solve (read by `dcore_pre`)

| Param | Type | Default | Meaning / typical |
|---|---|---|---|
| `seedname` | str | `dcore` | Base name; model file is `seedname.h5`. e.g. `square` |
| `lattice` | str | `chain` | `chain`/`square`/`cubic`/`bethe`/`wannier90`/`external` |
| `t` | float | 1.0 | Nearest-neighbor hopping. **Set `t = -1.0`** for the square Hubbard to put the band minimum at Γ |
| `t'` | float | 0.0 | Second-neighbor hopping |
| `norb` | str | 1 | Orbitals per inequivalent shell; comma list for multiple shells, e.g. `norb = 3, 3` |
| `nelec` | float | 1.0 | Electrons **per unit cell** (half-filling 1 orbital → `nelec = 1.0`); scales with cell size |
| `ncor` | int | 1 | Number of correlated shells in the unit cell (wannier90 mode) |
| `corr_to_inequiv` | str | None | Map correlated→inequivalent shells, e.g. `0, 1, 1, 0` (shells 0,3 share a self-energy; 1,2 share) |
| `spin_orbit` | bool | False | Spin-orbit coupling → dense spin-block (spin-off-diagonal) Σ, G |
| `nk` | int | 8 | k-points per axis (predefined lattices) → nk×nk×… grid; bethe uses `nk` virtual-axis points |
| `nk0`,`nk1`,`nk2` | int | 0 | Per-axis k counts (wannier90/external; current square tutorial uses `nk0=8 nk1=8 nk2=1`) |
| `bvec` | str | identity 3×3 | Reciprocal lattice vectors |
| `interaction` | str | `kanamori` | `kanamori`/`slater_uj`/`slater_f`/`respack`/`file` |
| `kanamori` | str | None | Per shell `[(U, U', J), ...]`; for 1 band only U matters, e.g. `[(4.0, 0.0, 0.0)]` |
| `slater_uj` | str | None | `[(l, U, J), ...]`; DCore builds Slater integrals F internally (l=2 → d, l=3 → f) |
| `slater_f` | str | None | `[(l, F0, F2, F4, F6), ...]` — all four F's required |
| `slater_basis` | str | `cubic` | Basis of the Slater interaction |
| `density_density` | bool | False | Restrict U to density-density terms (needed for segment CT-HYB when J≠0; *changes the model*) |
| `interaction_file` | str | None | Files with U tensor per inequivalent shell (`interaction = file`) |
| `local_potential_matrix` | str | None | Dict `{ish: 'file'}` of local potential matrices |
| `local_potential_factor` | str | 1.0 | Prefactor on the local potential |

Interaction conventions (Kanamori): `V_aaaa = U`, `V_abab = U'`, `V_abba = J`, `V_aabb = J`
(a≠b orbital indices). Slater↔(U,J) formulas in paper Table 2.

### 4.2 `[system]` — thermodynamics & frequency grid (read by `dcore`)

| Param | Type | Default | Meaning / typical |
|---|---|---|---|
| `beta` | float | 1.0 | Inverse temperature β. e.g. `beta = 50.0` |
| `T` | float | -1.0 | Temperature; if set, overwrites `beta = 1/T`. e.g. `T = 0.1` (use one of `T`/`beta`) |
| `n_iw` | int | 2048 | Number of positive Matsubara frequencies (paper examples use 1000) |
| `fix_mu` | bool | False | Fix μ to `mu`; else μ is found by bisection to match `nelec` each step |
| `mu` | float | 0.0 | (Initial / fixed) chemical potential, e.g. `mu = 2.0` for half-filled square (particle-hole sym.) |
| `prec_mu` | float | 1e-4 | Bisection tolerance for μ |
| `with_dc` | bool | False | Apply double-counting correction Σ_DC (DFT+DMFT) |
| `dc_type` | str | `HF_DFT` | `HF_DFT` (default, subtract HF from DFT) / `HF_imp` / `FLL` (fully-localized limit) |
| `dc_orbital_average` | bool | False | Average DC over orbitals in each shell |
| `no_tail_fit` | bool | False | Matsubara sums without high-frequency tail fitting |
| `n_l` | int | — | (with TRIQS/cthyb) number of Legendre polynomials for the Legendre filter |

### 4.3 `[impurity_solver]` — which engine, and its knobs (read by `dcore`)

| Param | Type | Default | Meaning |
|---|---|---|---|
| `name` | str | `null` | Solver: `null`, `TRIQS/cthyb`, `TRIQS/hubbard-I`, `ALPS/cthyb`, `ALPS/cthyb-seg`, `pomerol`, `scipy/sparse` |
| `exec_path{str}` | str | — | Absolute path (or PATH name) of the external solver executable |
| `basis_rotation` | str | None | `Hloc`, `None`, or a file specifying the basis rotation |

Solver-specific parameters carry an explicit **type tag** `{int}`, `{float}`, `{str}` and pass
through to the solver. Key ones by solver:

- **`TRIQS/cthyb`** (CT-HYB QMC). `n_cycles{int}` = number of QMC measurement cycles (raise to
  cut noise; scales down with #MPI), `n_warmup_cycles{int}` = thermalization cycles,
  `length_cycle{int}` = sub-cycle length (long enough to kill autocorrelation),
  `move_double{bool}` = needs `True` for multi-band (off-diagonal moves). Cost ∝
  `length_cycle·(n_cycles + n_warmup_cycles)`. Example: `n_warmup_cycles=10000`,
  `n_cycles=100000`, `length_cycle=50`.
- **`ALPS/cthyb`** (matrix CT-HYB QMC, handles full Kanamori incl. exchange). `exec_path{str}` →
  `hybmat`, `timelimit{int}` = wall-seconds per impurity solve (10% used for thermalization).
- **`ALPS/cthyb-seg`** (segment CT-HYB, density-density only). `exec_path{str}` → `alps_cthyb`,
  `MAX_TIME{int}` = wall-seconds, `cthyb.SWEEPS{int}` (very large → run is time-bound),
  `cthyb.THERMALIZATION{int}` (e.g. 100000), `cthyb.N_MEAS{int}` (updates per measurement, e.g. 50),
  `cthyb.TEXT_OUTPUT{int}`, `MEASURE_gw{int}`. Run `alps_cthyb --help` for the full list.
- **`pomerol`** (ED / Hubbard-I via finite bath). `exec_path{str}` → `pomerol2dcore`,
  `n_bath{int}` = number of bath sites (Δ(iωₙ) fit by N_bath poles; z converges for N_bath≳3 on
  square Hubbard but **dynamics need larger N_bath**), `fit_gtol{float}` = hybridization-fit
  tolerance (e.g. 1e-6).
- **`null`** — non-interacting limit (sanity / band-structure check).

### 4.4 `[control]` — the DMFT loop (read by `dcore`)

| Param | Type | Default | Meaning / typical |
|---|---|---|---|
| `max_step` | int | 100 | Max DMFT iterations |
| `sigma_mix` | float | 0.5 | Linear mixing σ_mix∈(0,1] (Eq. 14). Start ~0.5–1.0; lower it if the convergence graph oscillates |
| `converge_tol` | float | 0.0 | Stop when |O[i]−O[i−1]| < tol for μ and renorm factor z (0 → no auto-stop) |
| `n_converge` | int | 1 | Require the criterion met this many times consecutively (use >1 for noisy QMC) |
| `restart` | bool | False | Continue from previous Σ in `seedname.out.h5` (else loop restarts fresh) |
| `initial_self_energy` | str | None | Path to a `sigma.dat`-format file used as the initial Σ (warm-start QMC from a cheaper solver) |
| `initial_static_self_energy` | str | None | Dict `{ish: 'file'}` of static Σ per inequivalent shell — used to seed broken-symmetry (e.g. AFM) states |
| `time_reversal` | bool | False | Spin-average Σ_σ (set Sz=0) — improves QMC statistics in paramagnetic runs |
| `time_reversal_transverse` | bool | False | Symmetrize so Sx=Sy=0 |
| `symmetry_generators` | str | None | Generators for symmetrizing Σ |

### 4.5 Post-processing blocks (read by `dcore_anacont` / `dcore_spectrum` / `dcore_check`)

`[post.anacont]` — analytic continuation Σ(iωₙ) → Σ(ω):

| Param | Type | Default | Meaning |
|---|---|---|---|
| `solver` | str | (algorithm) | `pade` (Padé) or `spm` (sparse-modeling); external AC codes also possible |
| `omega_min` | float | -1.0 | Min real frequency |
| `omega_max` | float | 1.0 | Max real frequency |
| `Nomega` | int | 100 | Number of real-frequency points |

`[post.anacont.pade]` — Padé options:

| Param | Type | Default | Meaning |
|---|---|---|---|
| `n_min` | int | 0 | Lower bound on number of Matsubara freqs used |
| `n_max` | int | 1e8 | Upper bound on Matsubara freqs used |
| `iomega_max` | float | 0.0 | Cutoff Matsubara frequency |
| `eta` | float | 0.01 | Imaginary shift ω→ω+iη to avoid divergence |

`[post.anacont.spm]` — sparse-modeling: `solver` = cvxpy backend.

`[post.spectrum]` — A(k,ω) / A(ω):

| Param | Type | Default | Meaning |
|---|---|---|---|
| `knode` | str | `[(G,0,0,0),(X,1,0,0)]` | Named k-path nodes `[(label, k1,k2,k3), ...]` (fractional coords) |
| `nk_line` | int | 8 | k-points per segment of the path |
| `broadening` | float | 0.0 | Extra Lorentzian δ: ω→ω+iδ. Use δ~T for ED (discrete bath); set 0 for thermodynamic-limit (QMC) solvers |
| `nk_mesh`,`nk0_mesh`,`nk1_mesh`,`nk2_mesh` | int | 0 | k-mesh for A(k,ω) on a full 3D grid |

`[post.check]`: `omega_check` (float) — max frequency for `dcore_check` Σ plots.

**Legacy `[tool]` block** (paper): same keys lived flat — `knode`, `nk_line`,
`omega_min`, `omega_max`, `Nomega`, `broadening`, `omega_check` — read by `dcore_post`.

### 4.6 `[mpi]`

| Param | Type | Default | Meaning |
|---|---|---|---|
| `command` | str | `mpirun -np #` | MPI launch template; `#` is replaced by `--np N`. e.g. `command = '$MPIRUN -np #'` |

---

## 5. Outputs and observables

- **Model file `seedname.h5`** (from `dcore_pre`): groups `dft_input` (H(k), DFTTools layout)
  and `Dcore` (`Umat` interaction tensor, `LocalPotential`).
- **DMFT result `seedname.out.h5`** (from `dcore`): group `dmft_out` holding `iterations`,
  `Sigma_iw` (per iteration/shell, e.g. `/dmft_out/Sigma_iw/ite1/sh0`), `chemical_potential`,
  `dc_energ`, `dc_imp`, `parameters`. Per-iteration temp solver I/O under `work/imp_shell#_iter#/`.
- **Convergence `check/`** (from `dcore_check`): `sigma.dat` (final Σ_imp(iωₙ)); history files
  `iter_mu.dat/png` (μ), `iter_sigma-ish#.dat/png` (renormalization factor
  z_σ = [1 − ImΣ_σ(iω₀)/ω₀]⁻¹, 0<z≤1), `iter_occup-ish#.*` (occupations),
  `iter_spin-ish#.*` (spin moment). `sigma_ave.png` averages Σ over the last ~7 iterations.
  **The right-panel log-scale Δz curve is the convergence proof**; an exponential decay below
  `converge_tol` is what you look for.
- **Spectra `post/`** (from `dcore_anacont`+`dcore_spectrum`): `sigma_w.npz` (real-freq Σ),
  `dos.dat` (k-integrated DOS / A(ω)), `akw.dat` (A(k,ω) along the path) + `akw.gp` gnuplot
  script, `momdist.dat` (momentum distribution).

Read A(k,ω): `cd post && gnuplot akw.gp` (adjust the colorbar range to see the bands). Read DOS:
`plot "post/dos.dat" w l` in gnuplot. Both `.dat` are plain columns and load fine in
numpy/pandas too.

---

## 6. Worked example — square-lattice single-band Hubbard (ED solver `pomerol`)

Single-band Hubbard on a square lattice, H = Σ_k ε_k c†c + U Σ_i n↑n↓, with
ε_k = 2t(cos kx + cos ky) + 4t' sin kx sin ky and t = −1 (band min at Γ). Half-filling
(`nelec = 1.0`), so μ = U/2 = 2.0 is fixed by particle-hole symmetry. Full INI (current
`[post.*]` form, from the official tutorial):

```ini
[model]
seedname = square
lattice = square
norb = 1
nelec = 1.0
t = -1.0
kanamori = [(4.0, 0.0, 0.0)]
nk0 = 8
nk1 = 8
nk2 = 1

[system]
T = 0.1
n_iw = 1000
fix_mu = True
mu = 2.0

[impurity_solver]
name = pomerol
exec_path{str} = pomerol2dcore
n_bath{int} = 3
fit_gtol{float} = 1e-6

[control]
max_step = 100
sigma_mix = 0.5
converge_tol = 1e-5

[post.anacont]
solver = pade
omega_max = 6.0
omega_min = -6.0
Nomega = 401

[post.anacont.pade]
n_min = 20
n_max = 1000
iomega_max = 1e+20
eta = 0.1

[post.spectrum]
knode = [(G,0,0,0),(X,0.5,0,0),(M,0.5,0.5,0),(G,0,0,0)]
nk_line = 100
broadening = 0.4
```

Run the five stages:

```bash
dcore_pre      dmft_square.ini          # → square.h5
dcore          dmft_square.ini --np 1   # DMFT loop → square.out.h5
dcore_check    dmft_square.ini          # convergence figures in check/
dcore_anacont  dmft_square.ini          # Σ(iωₙ)→Σ(ω) → post/sigma_w.npz
dcore_spectrum dmft_square.ini --np 1   # → post/dos.dat, post/akw.dat, post/akw.gp
cd post && gnuplot akw.gp               # view A(k,ω)
```

Reading results: `check/iter_sigma-ish0.png` shows z(iteration) converging (loop stops ~13th
iter when Δz < `converge_tol=1e-5`); z → 0.58 here (matches CT-QMC). With only `n_bath=3`,
A(k,ω) shows *artificial* hybridized features near ω=±1.73 (the discrete bath poles) — fine for
z, **wrong for dynamics**; larger `n_bath` (or a QMC solver) is needed for the spectrum.

**CT-HYB QMC variant** — swap the solver and turn off auto-convergence (QMC noise):

```ini
[impurity_solver]
name = ALPS/cthyb-seg
exec_path{str} = /path/to/alps_cthyb
cthyb.TEXT_OUTPUT{int} = 1
MAX_TIME{int} = 60
cthyb.N_MEAS{int} = 50
cthyb.THERMALIZATION{int} = 100000
cthyb.SWEEPS{int} = 100000000

[control]
max_step = 20
sigma_mix = 0.5
time_reversal = True            # spin-average Σ to improve statistics
# converge_tol omitted — judge convergence visually from dcore_check graphs
# or: converge_tol = 0.002 with n_converge = 5  (tol > statistical noise)
[post.spectrum]
broadening = 0.0                # QMC treats thermodynamic limit → no artificial broadening
```

Run with MPI (`dcore dmft_square.ini --np 8`). Warm-start from the ED `sigma.dat` via
`initial_self_energy = /path/to/check/sigma.dat` to cut QMC iterations.

### Multi-orbital example — t2g (3-band) on a Bethe lattice, ALPS/CT-HYB

Reproduces the spin-freezing transition (ImΣ(iωₙ) ∝ ωₙ^0.5). U=8, U'=U−2J=5.333, J=1.333,
n=1.6, t=1.

```ini
[model]
lattice = bethe
seedname = bethe
nelec = 1.6
t = 1.0
norb = 3
kanamori = [(8.0, 5.3333333, 1.33333)]
nk = 1000          # bethe semicircular DOS on [-2t,2t] discretized along virtual k-axis

[mpi]
command = '$MPIRUN -np #'

[system]
beta = 50.0

[impurity_solver]
name = ALPS/cthyb
timelimit{int} = 300
exec_path{str} = hybmat

[control]
max_step = 40
sigma_mix = 1.0
restart = False
```

```bash
export MPIRUN="mpirun"
dcore_pre dmft_bethe.ini
dcore dmft_bethe.ini --np 24
```

### DFT+DMFT (SrVO3) — sketch

Construct maximally-localized Wannier functions for the t2g manifold with Wannier90 (after a
DFT run), giving `seedname_hr.dat`. Then `[model] lattice = wannier90`, `ncor`/`corr_to_inequiv`
set the correlated-shell structure, `interaction = slater_uj` or `kanamori`, and `[system]
with_dc = True dc_type = HF_DFT` enables the double-counting correction. Same five-stage run.

---

## 7. Pitfalls

- **Impurity solver is an external dependency.** DCore ships none for interacting runs — install
  TRIQS/cthyb, ALPS/CT-HYB(-SEGMENT), or pomerol separately and point `exec_path{str}` at the
  executable (and have it on `PATH`). Segment CT-HYB (`ALPS/cthyb-seg`) handles **density-density
  only**; with finite J it errors out unless you set `density_density = True` — but that *changes
  the model* and results will differ from full-Kanamori solvers (ALPS/CT-HYB, TRIQS/cthyb).
- **β / n_iw grid.** Lower temperature (larger β) needs more Matsubara frequencies `n_iw` and
  longer QMC thermalization; check the expansion-order histogram. Too few `n_iw` truncates the
  high-frequency tail (see `no_tail_fit`).
- **DMFT convergence (`sigma_mix`).** Larger σ_mix converges faster but can oscillate or jump;
  start ~0.5–1.0 and *reduce* if the `dcore_check` z-curve doesn't trend down. For QMC, the
  automatic `converge_tol` check is unreliable (statistical noise) — judge visually, or set
  `converge_tol` above the noise floor with `n_converge = 5`. Use `restart = True` to continue a
  loop that hit `max_step`, and warm-start QMC from a cheaper solver's `sigma.dat` via
  `initial_self_energy`.
- **Broken-symmetry states.** A paramagnetic solution may not be the true ground state (e.g. AFM
  square lattice). Enlarge the unit cell (Wannier90), set `corr_to_inequiv`, and seed with
  `initial_static_self_energy = {0:'init_se_up.txt', 1:'init_se_down.txt'}` (a staggered field).
- **Analytic continuation reliability.** Padé does **not** guarantee causality — A(k,ω) can go
  negative; increasing `broadening` mitigates. Padé is *extremely* sensitive to QMC statistical
  noise (spectra may not even reproduce run-to-run); reduce noise (more MPI / longer `MAX_TIME` /
  more `n_cycles`) or use the sparse-modeling solver (`[post.anacont] solver = spm`). For ED set
  `broadening ~ T`; for thermodynamic-limit (QMC) solvers set `broadening = 0`.
- **Finite-bath ED dynamics.** With pomerol/ED, Δ(iωₙ) is fit by `n_bath` poles. z (static) may
  converge at small `n_bath`, but A(k,ω) shows spurious peaks at the bath-pole energies — raise
  `n_bath` for trustworthy spectra.
- **Double counting (DFT+DMFT).** Required when adding U on top of DFT (`with_dc = True`);
  choose `dc_type` (`HF_DFT` default, `HF_imp`, `FLL`). DCore is **one-shot** only — no charge
  self-consistency (use eDMFT/DMFTwDFT if you need that).
- **MPI launch.** Each tool is one process; `--np` sets the *internal* MPI size (only `dcore`,
  `dcore_spectrum` accept it). If the MPI command is nonstandard, set `[mpi] command`.
- **Sign / energy convention.** For the square Hubbard set `t = -1.0` (band minimum at Γ);
  Wannier90 sign convention is H_ij^W90(R) = H_ij(R) as DCore reads it.

---

## 8. Source links

- Docs index: https://issp-center-dev.github.io/DCore/master/index.html
- Installation: https://issp-center-dev.github.io/DCore/master/install.html
- Tutorials: https://issp-center-dev.github.io/DCore/master/tutorial.html
  - 2D Hubbard (square): https://issp-center-dev.github.io/DCore/master/tutorial/square/square.html
  - Bethe t2g multi-orbital QMC: https://issp-center-dev.github.io/DCore/master/tutorial/bethe-t2g/bethe.html
  - Antiferromagnetic state: https://issp-center-dev.github.io/DCore/master/tutorial/afm/afm.html
  - SrVO3 DFT+DMFT: https://issp-center-dev.github.io/DCore/master/tutorial/srvo3/srvo3.html
- Programs reference: https://issp-center-dev.github.io/DCore/master/reference/programs.html
- Input-file format: https://issp-center-dev.github.io/DCore/master/reference/input.html
- Output-file format: https://issp-center-dev.github.io/DCore/master/reference/output.html
- Impurity solvers: https://issp-center-dev.github.io/DCore/master/impuritysolvers.html
- TRIQS/cthyb solver: https://issp-center-dev.github.io/DCore/master/impuritysolvers/triqs_cthyb/cthyb.html
- Analytic continuation: https://issp-center-dev.github.io/DCore/master/analytic_continuation.html
- GitHub: https://github.com/issp-center-dev/DCore (examples in `examples/`)
- Paper: https://arxiv.org/abs/2007.00901 — DOI https://doi.org/10.21468/SciPostPhys.10.5.117
