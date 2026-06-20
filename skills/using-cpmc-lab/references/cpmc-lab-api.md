# CPMC-Lab API + Examples Reference

A MATLAB package implementing the ground-state **constrained-path auxiliary-field
quantum Monte Carlo (CPMC / AFQMC)** method for the single-band repulsive Hubbard
model. It returns the ground-state total energy `E ± standard error` for finite
supercells in 1D / 2D / 3D, under periodic or twist-averaged boundary conditions.
It is a *pedagogical* package (~2850 lines, well-commented) meant for learning the
method and as a template for a production AFQMC code — not a production code itself.

This reference is extracted verbatim from the source at
`CPMC_Lab_20160129/` (package v1.0, 2014; authors Huy Nguyen, Hao Shi, Jie Xu,
Shiwei Zhang). The source `.m` files are authoritative.

## Source links

- Webpage: https://cpmc-lab.wm.edu/
- Tarball: https://cpmc-lab.wm.edu/CPMC_Lab2.0.tar.gz
- Paper: *CPMC-Lab: A Matlab Package for Constrained Path Monte Carlo Calculations*,
  Nguyen, Shi, Xu, Zhang, Comput. Phys. Commun. (2014) — arXiv:1408.4845.
- License: Computer Physics Communications Non-Profit Use License
  (http://cpc.cs.qub.ac.uk/licence/licence.html). Do not vendor into git.

## What it does

- **Model**: single-band repulsive Hubbard, `H = -Σ t cᵢ†cⱼ + U Σ nᵢ↑ nᵢ↓`, on an
  `Lx × Ly × Lz` lattice with per-axis hopping `tx, ty, tz`. `U ≥ 0` only.
- **Boundary conditions**: twist-averaging (TABC) with twist angle `θ = π·k` per
  axis; `k = 0` is periodic. The twist enters `H_K` as a complex phase `exp(±iπk)`
  on the wrap-around hops.
- **Algorithm (all fixed in the code)**: discrete Hirsch spin Hubbard-Stratonovich
  transformation; second-order Trotter split `e^{-Δτ K/2} e^{-Δτ V} e^{-Δτ K/2}`;
  importance-sampled open-ended random walk of Slater-determinant walkers;
  constrained-path approximation (walkers with non-positive overlap ratio are
  killed); modified Gram-Schmidt (QR) stabilization; simple-combing population
  control; energy via the **mixed estimator**.
- **Trial wavefunction**: a single free-electron (restricted-Hartree-Fock) Slater
  determinant, built automatically by diagonalizing the kinetic Hamiltonian and
  filling the lowest `N_up` / `N_dn` orbitals. The constrained-path bias is set by
  this trial; it is not user-selectable without editing the code.

## Setup / run

Two ways to drive it:

1. **Edit a sample script and run it.** Open `sample.m`, change the parameter
   block at the top, then in an interactive MATLAB session `cd` to the package
   directory and type `sample`. (`sample1.m` is the same with a different Δτ /
   measurement interval; `batchsample.m` loops over a parameter list.)
2. **Call `CPMC_Lab` directly** with 21 positional arguments (see signature
   below), e.g. from a custom driver run via `matlab -batch`.
3. **GUI**: `GUI.m` launches a standalone interactive interface (requires MATLAB
   R2010b+). It is self-contained and duplicates the QMC routines; ignore it for
   batch / scripted runs.

There is no built-in multi-axis sweep beyond `batchsample.m`; to vary a parameter
loop `CPMC_Lab` externally.

### Entry-point signature

```matlab
[E_ave,E_err,savedFileName] = CPMC_Lab( ...
    Lx,Ly,Lz,N_up,N_dn,kx,ky,kz,U,tx,ty,tz, ...   % model
    deltau,N_wlk,N_blksteps,N_eqblk,N_blk, ...     % run / sampling
    itv_modsvd,itv_pc,itv_Em,suffix);              % intervals + output tag
```

### User input parameters

Variable names are exactly as they appear in `CPMC_Lab.m` / `sample.m`. The
"Constraint" column is enforced by `validation.m` (a violation prints an error and
returns; some only warn).

**Model slots**

| Variable | Meaning | Constraint | Typical |
|---|---|---|---|
| `Lx` | sites in x | positive integer | 2–16 |
| `Ly` | sites in y | positive integer | 1 (1D), up to ~4 (2D) |
| `Lz` | sites in z | positive integer | 1 |
| `N_up` | spin-up electron count | non-neg int; warns if `> 2·Lx·Ly·Lz` (trial WF actually needs `≤ N_sites`) | half-filling: `N_sites/2` |
| `N_dn` | spin-down electron count | non-neg int; same cap | half-filling: `N_sites/2` |
| `kx` | x twist angle `θ = π·kx` | in `(−1, 1]` | 0 (PBC), or random for TABC |
| `ky` | y twist angle | in `(−1, 1]` | 0 |
| `kz` | z twist angle | in `(−1, 1]` | 0 |
| `U` | on-site repulsion | `U ≥ 0` (repulsive only) | 2–8 |
| `tx` | x hopping | `≥ 0` | 1 (energy unit) |
| `ty` | y hopping | `≥ 0` | 1 |
| `tz` | z hopping | `≥ 0` | 1 |

A `1` axis collapses: its hopping and twist contribute nothing (the `H_K` loop
skips that axis when `L==1`).

**Run / sampling slots**

| Variable | Meaning | Constraint | Typical |
|---|---|---|---|
| `deltau` | imaginary-time step Δτ | `> 0`; warns if `> 1` | 0.01–0.1 (Trotter error ∝ Δτ²) |
| `N_wlk` | number of random walkers | positive int | 100–5000 |
| `N_blksteps` | random-walk steps per block | positive int | 40 |
| `N_eqblk` | equilibration (burn-in) blocks | non-neg int | 2–30 |
| `N_blk` | measurement blocks (= sample count) | positive int | 20–150 |
| `itv_modsvd` | re-orthonormalization (QR) interval | positive int; warns + disables if `> N_blksteps` | 1–5 |
| `itv_pc` | population-control interval | positive int; warns + disables if `> N_blksteps` | 5–40 |
| `itv_Em` | energy-measurement interval within a block | positive int `≤ N_blksteps` | 20–40 |
| `suffix` | string appended to the saved `.mat` filename | must be a char string | timestamp / run-id |

Cost-warning heuristic (validation.m): if
`N_wlk·N_blksteps·(N_eqblk+N_blk)·Lx·Ly·(N_up+N_dn) > 1e11`, it warns the run may
take more than a day.

## Output

`CPMC_Lab` returns:

- `E_ave` — ground-state total energy (mean of per-block energies). Printed.
- `E_err` — standard error, `std(E)/sqrt(N_blk)`. Printed.
- `savedFileName` — name of the saved `.mat` file.

It also prints each block energy as `E(i)=...` during the measurement phase, and
the wall time `time`. The `.mat` file (read with MATLAB `load` or Python
`scipy.io.loadmat`) holds:

| Saved variable | Meaning |
|---|---|
| `E` | array of per-block energies |
| `E_ave`, `E_err` | mean energy and standard error |
| `time` | total wall-clock time (s) |
| `E_nonint_v` | non-interacting single-particle energy levels |
| `Phi_T` | trial wavefunction (Slater-determinant matrix) |
| `H_k` | one-body kinetic Hamiltonian |
| all input parameters | `Lx … itv_Em` echoed back |

The energy is in units of `t` (when `t=1`); the mixed estimator is exact for the
energy but biased for observables that do not commute with `H`.

## Key functions

Each source file's signature and one-line purpose.

| File | Signature | Purpose |
|---|---|---|
| `CPMC_Lab.m` | `[E_ave,E_err,savedFileName] = CPMC_Lab(Lx,Ly,Lz,N_up,N_dn,kx,ky,kz,U,tx,ty,tz,deltau,N_wlk,N_blksteps,N_eqblk,N_blk,itv_modsvd,itv_pc,itv_Em,suffix)` | Main driver: equilibration + measurement loops; calls stepwlk/stblz/pop_cntrl; computes E_ave/E_err; saves `.mat`. |
| `initialization.m` | *(script, not a function)* — uses the caller's workspace variables | Runs validation; sets `N_sites`, `N_par`; builds `H_k`, `Proj_k_half = expm(-0.5·deltau·H_k)`, trial WF `Phi_T`, initial walkers `Phi`, weights `w`, overlaps `O`, Hirsch `gamma`/`aux_fld`, `fac_norm`, and `savedFileName`. |
| `validation.m` | *(script)* | Checks every input for type/range; prints errors (returns) and warnings (large run, disabled stabilization/pop-control, Δτ>1). |
| `H_K.m` | `H = H_K(Lx,Ly,Lz,kx,ky,kz,tx,ty,tz)` | Build the one-body kinetic Hamiltonian (`N_sites × N_sites`) with twist phases `exp(±iπk)` on wrap-around bonds. |
| `stepwlk.m` | `[phi,w,O,E,W] = stepwlk(phi,N_wlk,N_sites,w,O,E,W,H_k,Proj_k_half,flag_mea,Phi_T,N_up,N_par,U,fac_norm,aux_fld)` | One random-walk step over all walkers: halfK → V (site-by-site) → halfK; optionally measure energy and accumulate `E`, `W`. |
| `halfK.m` | `[phi,w,O,invO_matrix_up,invO_matrix_dn] = halfK(phi,w,O,Proj_k_half,Phi_T,N_up,N_par)` | Propagate one walker by `exp(-Δτ K/2)`; update overlap; enforce constrained-path (kill if overlap ratio ≤ 0). |
| `V.m` | `[phi,O,w,invO_matrix_up,invO_matrix_dn] = V(phi,phi_T,N_up,N_par,O,w,invO_matrix_up,invO_matrix_dn,aux_fld)` | Importance-sample the Hirsch auxiliary field on one site and propagate by `exp(-Δτ V)`; Sherman-Morrison overlap update. |
| `measure.m` | `e = measure(H_k,phi,Phi_T,invO_matrix_up,invO_matrix_dn,N_up,N_par,U)` | Mixed-estimator energy of one walker via the single-particle Green's function. |
| `stblz.m` | `[Phi,O] = stblz(Phi,N_wlk,O,N_up,N_par)` | Modified Gram-Schmidt (QR) re-orthonormalization of every walker; rescale overlaps by the R determinants. |
| `pop_cntrl.m` | `[Phi,w,O] = pop_cntrl(Phi,w,O,N_wlk,N_sites,N_par)` | Simple-combing population control: resample walkers proportional to weight, reset all weights to 1. |
| `sample.m` | *(script)* | Set parameters and run one CPMC calculation; plots E vs τ. |
| `sample1.m` | *(script)* | Same as sample.m with `deltau=0.05`, `N_blk=15`, `itv_Em=2`. |
| `batchsample.m` | *(script)* | Loop `CPMC_Lab` over a list of parameters (e.g. `N_wlk=[100;200;500]`); errorbar plot of E vs the looped knob. |
| `GUI.m` | *(standalone)* | Interactive GUI; self-contained, independent of the other files. |

### How the driver wires them together (`CPMC_Lab.m`)

```matlab
initialization;                 % validation + H_k, Phi_T, walkers, aux_fld, fac_norm
% Equilibration: N_eqblk blocks × N_blksteps steps
for i_blk=1:N_eqblk
    for j_step=1:N_blksteps
        [Phi,w,O,E,W] = stepwlk(...);
        if mod(j_step,itv_modsvd)==0, [Phi,O]=stblz(...);    end
        if mod(j_step,itv_pc)==0,     [Phi,w,O]=pop_cntrl(...); end
    end
end
% Measurement: N_blk blocks; measure every itv_Em steps; update fac_norm (E_T)
for i_blk=1:N_blk
    for j_step=1:N_blksteps
        flag_mea = (mod(j_step,itv_Em)==0);
        [Phi,w,O,E_blk(i_blk),W_blk(i_blk)] = stepwlk(...);
        if mod(j_step,itv_modsvd)==0, [Phi,O]=stblz(...);    end
        if mod(j_step,itv_pc)==0,     [Phi,w,O]=pop_cntrl(...); end
        if flag_mea
            fac_norm=(real(E_blk(i_blk)/W_blk(i_blk))-0.5*U*N_par)*deltau;
        end
    end
    E_blk(i_blk)=E_blk(i_blk)/W_blk(i_blk);
end
E_ave=mean(real(E_blk));
E_err=std(real(E_blk))/sqrt(N_blk);
```

## Worked example (verbatim from `sample.m`)

A 2-site (1D dimer) Hubbard run, `1↑1↓`, `U=4`, `t=1`, small twist `kx=0.0819`.
This is the shipped functional smoke test.

```matlab
%% system parameters:
Lx=2; % The number of lattice sites in the x direction
Ly=1; % The number of lattice sites in the y direction
Lz=1; % The number of lattice sites in the z direction

N_up=1; % The number of spin-up electrons
N_dn=1; % The number of spin-down electrons

kx=+0.0819; % The x component of the twist angle in TABC (twist-averaging boundary condition)
ky=0; % The y component of the twist angle in TABC
kz=0; % The z component of the twist angle in TABC

U=4.0; % The on-site repulsion strength in the Hubbard Hamiltonian
tx=1; % The hopping amplitude between nearest-neighbor sites in the x direction
ty=1; % The hopping amplitude between nearest neighbor sites in the y direction
tz=1; % The hopping amplitude between nearest neighbor sites in the z direction

%% run parameters:
deltau=0.01; % The imaginary time step
N_wlk=100; % The number of random walkers
N_blksteps=40; % The number of random walk steps in each block
N_eqblk=2; % The number of blocks used to equilibrate the random walk before energy measurement takes place
N_blk=20; % The number of blocks used in the measurement phase
itv_modsvd=5; % The interval between two adjacent modified Gram-Schmidt re-orthonormalization of the random walkers. No re-orthonormalization if itv_modsvd > N_blksteps
itv_pc=10; % The interval between two adjacent population controls. No population control if itv_pc > N_blksteps
itv_Em=20; % The interval between two adjacent energy measurements
suffix=datestr(now,'_yymmdd_HHMMSS'); % time stamp for the saved *.mat filename. Can be changed to any desired string

%% invoke the main function
[E_ave,E_err,savedFile]=CPMC_Lab(Lx,Ly,Lz,N_up,N_dn,kx,ky,kz,U,tx,ty,tz,deltau,N_wlk,N_blksteps,N_eqblk,N_blk,itv_modsvd,itv_pc,itv_Em,suffix);

%% post-run:
% load saved data into workspace for post-run analysis:
load (savedFile);
% plot energy vs imaginary time
figure;
plot (N_blksteps*(1:N_blk)*deltau,E);
xlabel ('tau');
ylabel ('E');
```

Run it (interactive MATLAB, from the package directory):

```matlab
>> sample
```

Or non-interactively:

```bash
matlab -batch "cd('/path/to/CPMC_Lab_20160129'); sample"
```

The post-run block plots block energy `E` vs imaginary time
`τ = N_blksteps · i · Δτ`, the convergence/equilibration plot to inspect.

### Batch example (verbatim from `batchsample.m`)

Loop over walker counts and plot E vs `N_wlk` with error bars:

```matlab
N_wlk=[100;200;500]; % The number of random walkers
N_blk=[10;20;30];    % The number of blocks used in the measurement phase
% ... (other params as in sample.m) ...
N_run=length(N_wlk);
E_ave=zeros(N_run,1);
E_err=zeros(N_run,1);
for i=1:N_run
    suffix=strcat('_Nwlk',int2str(N_wlk(i)));
    [E_ave(i),E_err(i),savedFile]=CPMC_Lab(Lx,Ly,Lz,N_up,N_dn,kx,ky,kz,U,tx,ty,tz,deltau,N_wlk(i),N_blksteps,N_eqblk,N_blk(i),itv_modsvd,itv_pc,itv_Em,suffix);
end
figure;
errorbar(N_wlk,E_ave,E_err);
xlabel ('N_{wlk}'); ylabel ('E');
```

## Pitfalls

- **Constrained-path bias / trial wavefunction.** The CP energy is non-variational
  and biased; the bias size is set by the single free-electron (RHF) trial
  determinant, which is the only trial the package builds. Better / multi-determinant
  trials (which reduce the bias) are not provided — they require code changes.
  Removing the bias entirely needs release / free-projection, not implemented.
- **Δτ Trotter error.** Second-order split gives error ∝ Δτ². Run several Δτ values
  (e.g. 0.025, 0.05, 0.1) and extrapolate Δτ → 0; production work used 0.01.
  `validation.m` only warns at Δτ > 1.
- **Walker number & population control.** Too few walkers → population-control bias
  (sweep `N_wlk` ≈ 100/200/500 and check convergence). `pop_cntrl` resets all
  weights to 1 each comb; `itv_pc` and `itv_modsvd` are *tuned*, not fixed —
  setting either `> N_blksteps` silently disables that stabilization step (only a
  warning is printed). Authors used `itv_pc` 5–40 and `itv_modsvd` 1–5 across systems.
- **Equilibration / thermalization.** Burn-in time `τ_eq = deltau·N_blksteps·N_eqblk`
  must exceed the projection-to-ground-state time. Read `τ_eq` off the E-vs-τ plot;
  too-short equilibration biases the energy.
- **Block decorrelation.** Each block is one sample; `N_blksteps` must be ≥ the
  autocorrelation time so blocks are independent, else `E_err` is underestimated.
  Error bar scales as 1/√N_blk.
- **Pedagogical scope / small systems only.** MATLAB, single-core (no MPI / GPU /
  threads). Slower than a production FORTRAN code by ≈32× (4×4) down to ≈2.5×
  (128×1). The cost-warning heuristic flags runs likely > 1 day. Use it for small
  supercells and learning; parallelism comes only from farming independent runs
  (twists, sizes, Δτ values).
- **Repulsive single-band Hubbard only** (`U ≥ 0`). Other Hamiltonians, attractive
  `U`, or multi-orbital models need code changes.
- **Energy only, mixed estimator.** The program outputs the total ground-state
  energy. Observables that do not commute with `H` are biased by the mixed
  estimator (need back-propagation, not built in).
