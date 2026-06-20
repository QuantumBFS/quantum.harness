# TRIQS API + Examples Reference

**TRIQS** = *Toolbox for Research on Interacting Quantum Systems*. Open-source (GPLv3) C++/Python library for quantum many-body / strongly-correlated electron physics, with a strong focus on **dynamical mean-field theory (DMFT)** and **quantum impurity solvers**. Core abstractions: Green's-function containers on arbitrary meshes, a second-quantized operator algebra, multidimensional arrays, a generic Monte Carlo engine, and a uniform HDF5 interface. Most objects are written in C++ and exposed to Python, so the same object round-trips between languages and HDF5 files written from either side share one format.

- Library paper: Parcollet, Ferrero, Ayral, Hafermann, Krivenko, Messio, Seth, *Comput. Phys. Commun.* **196**, 398 (2015), arXiv:1504.01952. Cite this in any work using TRIQS (directly or via a TRIQS-based application).
- Companion applications distributed alongside the core: **cthyb** (CT-HYB hybridization-expansion continuous-time QMC impurity solver), **dft_tools** (DFT↔DMFT interface), **maxent** / analytic-continuation tools.

**Note on imports.** Modern TRIQS (≥ 2.x / 3.x) uses the `triqs.*` and `h5` namespaces shown throughout this card (e.g. `from triqs.gf import *`, `from h5 import HDFArchive`). The 1.2-era release paper uses the older `pytriqs.*` namespace (e.g. `from pytriqs.operators.operators import ...`, `from pytriqs.archive import *`). The semantics are identical; prefer the modern names for new code.

---

## What TRIQS does

| Component | Purpose |
|---|---|
| **Green's functions** (`triqs.gf`) | Containers on imaginary/real frequency & time, Legendre, DLR, Brillouin-zone meshes; matrix/tensor/scalar-valued; block-diagonal (`BlockGf`); arithmetic via expression templates; Fourier transforms (FFTW); high-frequency tail handling. |
| **Operators** (`triqs.operators`) | Second-quantized fermionic algebra: `c`, `c_dag`, `n`; build model Hamiltonians and observables as polynomials of operators, stored in normal order. Utilities for Kanamori / Slater / density-density interactions. |
| **CT-HYB solver** (`triqs_cthyb`) | Hybridization-expansion continuous-time QMC quantum impurity solver. Takes a non-interacting `G0_iw` + a local Hamiltonian `h_int`; returns `G_tau`, `G_iw`, `Sigma_iw`. MPI-parallel. |
| **Lattice tools** (`triqs.lattice`) | `BravaisLattice`, `TightBinding`/`TBLattice`, `BrillouinZone`; dispersions, DOS, k-meshes. |
| **HDF5** (`h5`) | `HDFArchive` — dict-like portable persistence for arrays, Green's functions, operators; same format from C++ and Python. |
| **Monte Carlo / det_manip / arrays** (C++) | `mc_generic` Metropolis engine, fast determinant updates (Sherman-Morrison/Woodbury), multidimensional arrays with BLAS/LAPACK. Mostly used when *writing* solvers in C++. |

---

## Key API — Green's functions (`triqs.gf`)

```python
from triqs.gf import (Gf, BlockGf,
                      MeshImFreq, MeshImTime, MeshReFreq, MeshReTime,
                      MeshDLR, MeshBrZone, MeshLegendre,
                      iOmega_n, SemiCircular, Wilson, Flat, Omega,
                      inverse, make_gf_from_fourier, make_hermitian)
```

### Meshes

| Mesh | Constructor (key args) | Domain |
|---|---|---|
| `MeshImFreq` | `MeshImFreq(beta, statistic, n_iw)` — `statistic='Fermion'`/`'Boson'` | Matsubara frequencies `iωₙ` |
| `MeshImTime` | `MeshImTime(beta, statistic, n_tau)` | imaginary time `τ ∈ [0, β]` |
| `MeshReFreq` | `MeshReFreq(window=(w_min, w_max), n_w=...)` | real frequency `ω` |
| `MeshReTime` | `MeshReTime(window=(t_min, t_max), n_t=...)` | real time `t` |
| `MeshDLR` | `MeshDLR(beta, statistic, w_max, eps)` | Discrete Lehmann Representation (compact) |
| `MeshLegendre` | `MeshLegendre(beta, statistic, n_l)` | Legendre coefficients `Gₗ` |
| `MeshBrZone` | `MeshBrZone(bz, n_k)` (or `(bz, [nx,ny,nz])`) | Brillouin zone `k` |

Older positional signature still seen in docs: `MeshImFreq(beta=40, S='Fermion', n_max=1000)`.

### `Gf` — single Green's function

```python
Gf(mesh=<Mesh>, target_shape=[m, n], indices=...)
```

- `mesh` — one of the mesh objects above (or a `MeshProduct` for multivariable GFs).
- `target_shape` — matrix/tensor dimensions of the value at each mesh point (e.g. `[1,1]` scalar-like, `[3,3]` three orbitals). Use `target_shape=[]` for a scalar-valued Gf.
- `indices` — optional labels for the target indices.

Construction + filling (CLEF-style `<<` assignment fills every mesh point):

```python
from triqs.gf import Gf, MeshImFreq, iOmega_n, inverse, SemiCircular

g = Gf(mesh=MeshImFreq(beta=10, statistic='Fermion', n_iw=1000),
       target_shape=[1, 1])

g << inverse(iOmega_n + 0.5)          # G(iωₙ) = 1/(iωₙ + μ)
g << SemiCircular(half_bandwidth=1.0) # Bethe-lattice semicircular DOS
# iOmega_n, Omega, SemiCircular(D), Wilson(D), Flat(D) are GF "descriptors"
```

**Indexing / slicing.** `g[i, j]` selects a target matrix element (returns a scalar-valued Gf). `g.data` is the underlying NumPy array (shape `(n_mesh, *target_shape)`); `g.mesh` is the mesh. Evaluate at a mesh point by iterating `for w in g.mesh: g[w]`.

**Arithmetic.** `+ - * /`, `inverse(g)`, scalar scaling — all carry the high-frequency tail consistently. `g.copy()` deep-copies; `g << other` assigns in place.

### `BlockGf` — block-diagonal Green's function

A named collection of `Gf` blocks (e.g. spin/orbital sectors). This is the object every solver consumes/produces.

```python
from triqs.gf import BlockGf

G = BlockGf(name_list=['up', 'down'],
            block_list=[g_up, g_down],
            make_copies=True)          # copy the blocks in (vs share refs)

# Iterate over blocks
for name, g in G:
    g << inverse(iOmega_n - 0.3)

# Access a block
G['up'] << inverse(iOmega_n + 0.5)
```

The **block structure** is described by `gf_struct` — a list of `(block_name, block_size)` pairs, e.g. `[('up', 1), ('down', 1)]` for one orbital per spin, `[('up', 3), ('down', 3)]` for a 3-orbital problem. (In some newer APIs the size is a list of inner indices.)

### Fourier transforms

```python
from triqs.gf import make_gf_from_fourier

g_iw = make_gf_from_fourier(g_tau)          # τ → iωₙ
g_tau = make_gf_from_fourier(g_iw)          # iωₙ → τ  (uses known high-freq tail)
g_iw.set_from_fourier(g_tau)                # in-place variant
```

The Fourier transform uses the Green's function's **high-frequency tail** to treat the `1/iωₙ` discontinuity correctly; without an accurate tail the τ-transform develops spurious oscillations near `τ = 0, β`.

### Density and tail

```python
rho = g.density()        # occupation matrix  n = (1/β) Σₙ G(iωₙ) eⁱᵒ⁺ , per target block
# trace(rho) is the total filling for that block
```

Tail / high-frequency moments (for accurate FT and frequency sums):

```python
from triqs.gf import fit_hermitian_tail, make_zero_tail

known_moments = make_zero_tail(g, n_moments=4)   # template for moments G ~ Σ mₖ/(iω)ᵏ
tail, err = fit_hermitian_tail(g, known_moments) # fit the asymptotic moments (Hermitian-constrained)
```

`density()`, frequency sums, and Fourier transforms all rely on a correct tail; for noisy QMC data fit the tail (or replace the high-ω part) before transforming.

### Plotting

```python
from triqs.plot.mpl_interface import oplot, plt
oplot(g['up'].imag, '-o', name='Im G_up', x_window=(0, 10))
plt.show()
```

---

## Key API — Operators (`triqs.operators`)

```python
from triqs.operators import c, c_dag, n, dagger, Operator
```

- `c(block, index)` — fermionic annihilation operator (e.g. `c('up', 0)`).
- `c_dag(block, index)` — creation operator.
- `n(block, index)` — number operator `= c_dag * c`.
- `dagger(op)` — Hermitian conjugate of an operator expression.
- `Operator` — the algebra type; supports `+`, `-`, `*`, scalar multiplication; stored in **normal order** with automatic simplification (e.g. an expression that vanishes becomes `0`). `op.is_zero()` tests for zero.

Block/index labels can be strings or integers and must match the solver's `gf_struct` block names and inner indices.

### Building Hamiltonians

```python
# Hubbard atom, half-filled — four equivalent forms
U = 1.0
Sp = c_dag('up', 0) * c('dn', 0)            # S₊
Sm = c_dag('dn', 0) * c('up', 0)            # S₋
Sz = 0.5 * (n('up', 0) - n('dn', 0))        # S_z
S2 = Sz*Sz + (Sp*Sm + Sm*Sp)/2             # S²

H1 = -U/2*(n('up',0) + n('dn',0)) + U*n('up',0)*n('dn',0)
H2 = U*(n('up',0) - 0.5)*(n('dn',0) - 0.5) - U/4
H3 = -2.0*U*Sz*Sz
H4 = -2.0/3.0*U*S2
assert (H1-H2).is_zero() and (H2-H3).is_zero() and (H3-H4).is_zero()
```

### Interaction-Hamiltonian utilities (`triqs.operators.util`)

```python
from triqs.operators.util import (h_int_kanamori, h_int_density, h_int_slater,
                                   U_matrix, U_matrix_kanamori)
```

- `h_int_density(spin_names, orb_names, U, Uprime, off_diag=None, map_operator_structure=None)` — density–density interaction Σ Uₐᵦ nₐ nᵦ.
- `h_int_kanamori(spin_names, orb_names, U, Uprime, J_hund, off_diag=None, map_operator_structure=None)` — rotationally invariant Kanamori interaction (density–density + spin-flip + pair-hopping).
- `h_int_slater(spin_names, orb_names, U_matrix, off_diag=None, ...)` — full Slater interaction from a 4-index U tensor.
- `U_matrix_kanamori(n_orb, U_int, J_hund)` → `(U, Uprime)` matrices for the Kanamori form.
- `U_matrix(l, U_int, J_hund, ...)` — build the 4-index Coulomb tensor for angular momentum `l`.

```python
spin_names = ['up', 'down']
orb_names = [0, 1, 2]
U_mat, Uprime_mat = U_matrix_kanamori(n_orb=3, U_int=4.0, J_hund=0.6)
H = h_int_kanamori(spin_names, orb_names, U_mat, Uprime_mat, J_hund=0.6, off_diag=True)
```

---

## Key API — CT-HYB solver (`triqs_cthyb.Solver`)

```python
from triqs_cthyb import Solver
```

Hybridization-expansion continuous-time quantum Monte Carlo impurity solver. Workflow: construct → set `G0_iw` (the non-interacting impurity Green's function) → `solve(h_int=...)` → read `G_tau` / `G_iw` / `Sigma_iw`.

### Constructor

```python
Solver(beta, gf_struct, n_iw=1025, n_tau=10001, n_l=50, delta_interface=False)
```

| Arg | Purpose |
|---|---|
| `beta` | inverse temperature β. |
| `gf_struct` | block structure, list of `(block_name, size)` pairs, e.g. `[('up',1),('down',1)]`. |
| `n_iw` | number of positive Matsubara frequencies for `G0_iw`/`G_iw`/`Sigma_iw`. |
| `n_tau` | number of imaginary-time points for `G_tau` (and the internal Δ(τ)); should be ≳ `10*n_iw`. |
| `n_l` | number of Legendre coefficients (only used if `measure_G_l=True`). |
| `delta_interface` | if `True`, give the solver `Delta_tau` + `h_loc0` directly instead of `G0_iw`. |

### Inputs / outputs (members)

| Member | Direction | Meaning |
|---|---|---|
| `S.G0_iw` | **input** | non-interacting impurity Green's function `G₀(iωₙ)` (a `BlockGf`); set this before `solve`. |
| `S.G_tau` | output | interacting `G(τ)`. |
| `S.G_iw` | output | interacting `G(iωₙ)` (Fourier of `G_tau`, tail-corrected). |
| `S.Sigma_iw` | output | self-energy via the Dyson equation `Σ = G₀⁻¹ − G⁻¹`. |
| `S.G_l` | output | Legendre-coefficient Green's function (if `measure_G_l=True`). |
| `S.Delta_tau` | output | hybridization Δ(τ) extracted from `G0_iw`. |
| `S.density_matrix` | output | reduced impurity density matrix (if `measure_density_matrix=True`). |
| `S.average_sign` | output | average Monte Carlo sign. |
| `S.average_order` | output | average perturbation (expansion) order; useful to gauge warmup. |

### `solve()` parameters

```python
S.solve(h_int,                      # local interaction Hamiltonian (Operator) — REQUIRED
        n_cycles,                   # number of measured QMC cycles — REQUIRED
        length_cycle=50,            # # of MC moves between two measurements (autocorrelation)
        n_warmup_cycles=5000,       # thermalization cycles (no measurement)
        random_seed=34788+928374*rank,  # RNG seed (per-MPI-rank by default)
        random_name='',             # RNG algorithm name ('' = default)
        max_time=-1,                # wall-clock cap in seconds (-1 = no limit)
        verbosity=...,              # 0..3, log verbosity (3 on master by default)
        move_shift=True,            # enable the segment-shift move
        move_double=False,          # enable double-insertion moves (needed for off-diagonal/J terms)
        measure_G_tau=True,         # measure G(τ)
        measure_G_l=False,          # measure Legendre G_l (smoother, less noisy tail)
        measure_density_matrix=False,   # measure reduced density matrix (static observables)
        measure_pert_order=False,   # histogram of perturbation order
        use_norm_as_weight=False,   # required True to measure density matrix
        partition_method='autopartition',  # Hilbert-space partitioning of the local trace
        imag_threshold=1e-15,       # threshold to drop tiny imaginary parts
        perform_tail_fit=False,     # post-process Sigma_iw with a high-freq tail fit
        fit_max_moment=...,         # max moment order for the tail fit
        fit_min_n=..., fit_max_n=...,   # Matsubara index window for the tail fit
        fit_min_w=..., fit_max_w=...)   # frequency window (alternative to indices)
```

Defaults shown are the canonical TRIQS/cthyb defaults; consult `Solver.solve.__doc__` / the reference page for the exact build's values. `h_int` and `n_cycles` are always required.

---

## Key API — lattice tools (`triqs.lattice`)

```python
from triqs.lattice.tight_binding import TBLattice
from triqs.lattice import BravaisLattice, BrillouinZone
```

- `BravaisLattice(units, orbital_positions)` — lattice vectors + orbital positions.
- `TBLattice(units, hoppings, orbital_positions=..., orbital_names=...)` — tight-binding model; `hoppings` is a dict keyed by displacement tuple → hopping matrix.
- `BrillouinZone(bravais_lattice)`; sample with `MeshBrZone(bz, n_k)`.

```python
import numpy as np
from triqs.lattice.tight_binding import TBLattice

# 2D square lattice, single orbital, nearest-neighbor hopping t = -1
TB = TBLattice(
    units=[(1, 0, 0), (0, 1, 0)],
    hoppings={( 1, 0): [[-1.0]], (-1, 0): [[-1.0]],
              ( 0, 1): [[-1.0]], ( 0,-1): [[-1.0]]},
    orbital_positions=[(0, 0, 0)],
    orbital_names=['s'])

eps_k = TB.dispersion(...)   # band energies on a k-path / k-mesh
dos = TB.dos(...)            # density of states
```

---

## Key API — HDF5 archive (`h5`)

```python
from h5 import HDFArchive
```

Dict-like persistence; stores arrays, scalars, strings, Green's functions, `BlockGf`, operators, and most TRIQS objects. Files are portable and readable from C++, Python, or plain HDF5 tools.

```python
# Write
with HDFArchive('data.h5', 'w') as ar:     # 'w' overwrite, 'a' append, 'r' read-only
    ar['G_iw'] = S.G_iw
    ar['params'] = {'U': 4.0, 'beta': 50}

# Read
with HDFArchive('data.h5', 'r') as ar:
    G = ar['G_iw']
    print(list(ar.keys()))
    if ar.is_group('some_block_gf'):
        ...

# Nested groups via '/'
ar['iter/0/G_iw'] = S.G_iw
```

Always guard writes with `mpi.is_master_node()` so only rank 0 writes the file (see DMFT example).

---

## Worked example 1 — Green's function construction + Fourier (C++, from the release paper)

Listing 3 of arXiv:1504.01952 — canonical Gf construction, CLEF assignment, FFT, block GF, multivariable k-GF, HDF5 write.

```cpp
#include <triqs/gfs.hpp>
using namespace triqs;
using namespace triqs::gfs;
using namespace triqs::lattice;
int main() {

 double beta = 10;
 int n_freq = 1000;

 clef::placeholder<0> iw_;
 clef::placeholder<1> k_;

 // Construction of a 1x1 matrix-valued fermionic gf on Matsubara frequencies.
 auto g_iw = gf<imfreq>{{beta, Fermion, n_freq}, {1, 1}};

 // Automatic placeholder evaluation
 g_iw(iw_) << 1 / (iw_ + 2);

 // Inverse Fourier transform to imaginary time
 auto g_tau = gf<imtime>{{beta, Fermion, 2 * n_freq + 1}, {1, 1}};
 g_tau() = inverse_fourier(g_iw); // Fills a full view of g_tau with FFT result

 // Create a block Green's function composed of three blocks,
 // labeled a,b,c and made of copies of the g_iw functions.
 auto G_iw = make_block_gf({"a", "b", "c"}, {g_iw, g_iw, g_iw});

 // A multivariable gf: G(k,omega)
 auto bz = brillouin_zone{bravais_lattice{{{1, 0}, {0, 1}}}};
 auto g_k_iw = gf<cartesian_product<brillouin_zone, imfreq>>{
   {{bz, 100}, {beta, Fermion, n_freq}}, {1, 1}};

 g_k_iw(k_, iw_) << 1 / (iw_ - 2 * (cos(k_(0)) + cos(k_(1))) - 1 / (iw_ + 2));

 // Writing the Green's functions into an HDF5 file.
 auto f = h5::file("file_g_k_iw.h5", H5F_ACC_TRUNC);
 h5_write(f, "g_k_iw", g_k_iw);
 h5_write(f, "g_iw", g_iw);
 h5_write(f, "g_tau", g_tau);
 h5_write(f, "block_gf", G_iw);
}
```

The high-frequency tail is part of the container and is recomputed in arithmetic ops, so the inverse Fourier transform in line `g_tau() = inverse_fourier(g_iw)` treats the `1/iω` discontinuity correctly without the user supplying asymptotics by hand.

Python equivalent of the construction + FT idiom:

```python
from triqs.gf import Gf, MeshImFreq, MeshImTime, iOmega_n, make_gf_from_fourier
g_iw = Gf(mesh=MeshImFreq(beta=10, statistic='Fermion', n_iw=1000), target_shape=[1, 1])
g_iw << 1.0 / (iOmega_n + 2)
g_tau = make_gf_from_fourier(g_iw)        # iωₙ → τ
```

---

## Worked example 2 — Single-orbital Anderson impurity with CT-HYB (Python, from the cthyb docs)

The canonical `triqs_cthyb` Anderson-impurity-model tutorial — solver construction, set `G0_iw` via `inverse`, define `h_int`, solve, save.

```python
from triqs.gf import *
from triqs.operators import *
from triqs_cthyb import Solver
from h5 import HDFArchive
import triqs.utility.mpi as mpi

# Parameters
D, V, U = 1.0, 0.2, 4.0
e_f, beta = -U/2.0, 50

# Construct the impurity solver with the inverse temperature
# and the structure of the Green's functions
S = Solver(beta = beta, gf_struct = [ ('up',1), ('down',1) ], n_l = 100)

# Initialize the non-interacting Green's function S.G0_iw
for name, g0 in S.G0_iw: g0 << inverse(iOmega_n - e_f - V**2 * Wilson(D))

# Run the solver. The results will be in S.G_tau, S.G_iw and S.G_l
S.solve(h_int = U * n('up',0) * n('down',0),     # Local Hamiltonian
        n_cycles  = 500000,                      # Number of QMC cycles
        length_cycle = 200,                      # Length of one cycle
        n_warmup_cycles = 10000,                 # Warmup cycles
        measure_G_l = True)                      # Measure G_l

# Save the results in an HDF5 file (only on the master node)
if mpi.is_master_node():
    with HDFArchive("aim_solution.h5",'w') as Results:
        Results["G_tau"] = S.G_tau
        Results["G_iw"] = S.G_iw
        Results["G_l"] = S.G_l
```

Plotting the result:

```python
from triqs.gf import *
from h5 import *
from triqs.plot.mpl_interface import oplot

with HDFArchive('aim_solution.h5','r') as ar:
    oplot(ar['G_iw']['up'], '-o', x_window = (0,10))
```

Run in parallel with MPI: `mpirun -np 4 python aim.py`.

---

## Worked example 3 — DMFT self-consistency loop on the Bethe lattice (Python, from the cthyb docs)

The complete single-site DMFT loop: semicircular DOS init, self-consistency `G₀⁻¹ = iωₙ + μ − (t²) G`, solve, per-iteration HDF5 save. This is "DMFT in one page".

```python
from triqs.gf import *
from triqs.operators import *
from h5 import *
import triqs.utility.mpi as mpi
from triqs_cthyb import Solver

# Set up a few parameters
U = 2.5
half_bandwidth = 1.0
chemical_potential = U/2.0
beta = 100
n_loops = 5

# Construct the CTQMC solver
S = Solver(beta = beta, gf_struct = [ ('up',1), ('down',1) ])

# Initalize the Green's function to a semi circular DOS
S.G_iw << SemiCircular(half_bandwidth)

# Now do the DMFT loop
for i_loop in range(n_loops):

    # Compute new S.G0_iw with the self-consistency condition while imposing paramagnetism
    g = 0.5 * (S.G_iw['up'] + S.G_iw['down'])
    for name, g0 in S.G0_iw:
        g0 << inverse(iOmega_n + chemical_potential - (half_bandwidth/2.0)**2 * g)

    # Run the solver
    S.solve(h_int = U * n('up',0) * n('down',0),    # Local Hamiltonian
            n_cycles = 5000,                        # Number of QMC cycles
            length_cycle = 200,                     # Length of a cycle
            n_warmup_cycles = 1000)                 # How many warmup cycles

    # Some intermediate saves
    if mpi.is_master_node():
        with HDFArchive("dmft_solution.h5") as ar:
            ar["G_tau-%s"%i_loop] = S.G_tau
            ar["G_iw-%s"%i_loop] = S.G_iw
            ar["Sigma_iw-%s"%i_loop] = S.Sigma_iw
```

**Loop skeleton in words** (the DMFT idiom every backend reuses):

1. Start from a guess for the local lattice Green's function `G_iw`.
2. **Self-consistency**: compute the bath/Weiss field `G0_iw` from `G_iw` (here `G₀⁻¹ = iωₙ + μ − (D/2)² G` for the Bethe lattice; for a general lattice it is a k-sum `Gₗₒc = Σₖ [iωₙ + μ − εₖ − Σ]⁻¹` then `G₀⁻¹ = Gₗₒc⁻¹ + Σ`).
3. **Solve** the impurity with `S.solve(h_int=...)`.
4. Read `S.Sigma_iw` (Dyson `Σ = G₀⁻¹ − G⁻¹`) and the new `S.G_iw`.
5. Optionally **mix** old/new (`G = α G_new + (1−α) G_old`) and check convergence; repeat.

---

## Worked example 4 — Operator Hamiltonian (Python, from the release paper §8.7)

```python
from triqs.operators import Operator, n, c_dag, c
# (release-paper namespace was: from pytriqs.operators.operators import ...)

# Spin operators
Sp = c_dag("up",0)*c("dn",0)               # S_+
Sm = c_dag("dn",0)*c("up",0)               # S_-
Sz = 0.5*(n("up",0) - n("dn",0))           # S_z
S2 = Sz*Sz + (Sp*Sm + Sm*Sp)/2            # S^2

# The Hamiltonian of a half-filled Hubbard atom: four equivalent forms
U = 1.0
H1 = -U/2*(n("up",0) + n("dn",0)) + U*n("up",0)*n("dn",0)
H2 = U*(n("up",0) - 0.5)*(n("dn",0) - 0.5) - U/4
H3 = -2.0*U*Sz*Sz
H4 = -2.0/3.0*U*S2
print(H1, '\n', H2, '\n', H3, '\n', H4)

# All four forms are indeed equivalent
print((H1-H2).is_zero() and (H2-H3).is_zero() and (H3-H4).is_zero())
```

---

## Pitfalls

- **Matsubara mesh size (`n_iw`, `n_tau`).** Filling/density and Fourier transforms converge only if enough Matsubara frequencies are kept ("filling converges only if enough number of Matsubara frequencies `n_iw` are kept"). Use `n_tau` "as large as possible" (rule of thumb `n_tau ≳ 10·n_iw`); too-small `n_tau` averages over bins and produces unphysical `G(τ)` that "crosses zero". `n_l` Legendre coefficients should be cut once they reach their noise floor (often ~35 suffice).
- **Block structure (`gf_struct`).** Block names and inner indices in `gf_struct`, in `G0_iw`, and in the operators of `h_int` must all match exactly. Off-diagonal-in-block self-energies and Hund's-coupling (spin-flip / pair-hopping) terms generally require `move_double=True`; pure density–density interactions do not.
- **High-frequency tail / Fourier accuracy.** Green's functions carry their high-frequency moments, and Fourier transforms / frequency sums use them to handle the `1/iωₙ` discontinuity. For noisy QMC `G_iw`, fit or impose the tail (`fit_hermitian_tail`, or `perform_tail_fit` on `Sigma_iw`) before transforming or differentiating — otherwise τ-space data oscillates near `τ = 0, β`. Measuring `G_l` (Legendre) gives a smoother, less tail-sensitive estimator.
- **Monte Carlo convergence.** QMC error decays as ~`1/√n_cycles`. Tune `length_cycle` so the autocorrelation time is "of order one" (too long wastes moves; too short correlates consecutive measurements). Estimate `n_warmup_cycles` by setting it to 0 and watching `average_order` saturate; higher β needs substantially more warmup.
- **MPI for the solver.** CT-HYB is MPI-parallel — run with `mpirun -np N python script.py`. Each rank should get a distinct `random_seed` (the default `34788 + 928374*rank` does this). Guard all HDF5 writes with `if mpi.is_master_node():` so only rank 0 writes.
- **Analytic continuation needed for real-frequency spectra.** CT-HYB produces imaginary-time/Matsubara data only. The spectral function `A(ω)` and any real-frequency observable require **analytic continuation** (e.g. MaxEnt via `triqs_maxent`, or Padé) — an ill-conditioned, separate step; do not read a spectrum directly off `G_iw`/`G_tau`.

---

## Source links

- Library paper (rendered locally): `.knowledge/literature/software/1504.01952_triqs-a-toolbox-for-research-on-interacting-quantum-systems.md` — arXiv:1504.01952, *Comput. Phys. Commun.* **196**, 398 (2015), DOI 10.1016/j.cpc.2015.04.023.
- TRIQS docs home: https://triqs.github.io/triqs/latest/
- Green's functions (Python): https://triqs.github.io/triqs/latest/documentation/manual/triqs/gfs/py/contents.html
- Operators (second quantization): https://triqs.github.io/triqs/latest/documentation/manual/triqs/operators/contents.html
- HDF5 / HDFArchive: https://triqs.github.io/triqs/latest/documentation/manual/hdf5/contents.html
- Lattice tools: https://triqs.github.io/triqs/latest/documentation/manual/triqs/lattice_tools/contents.html
- CT-HYB solver home: https://triqs.github.io/cthyb/latest/
- CT-HYB Solver class reference: https://triqs.github.io/cthyb/latest/triqs_cthyb.solver.Solver.html
- CT-HYB Anderson-impurity tutorial: https://triqs.github.io/cthyb/latest/guide/aim.html
- CT-HYB DMFT (Bethe lattice) tutorial: https://triqs.github.io/cthyb/latest/guide/dmft.html
- CT-HYB setting parameters: https://triqs.github.io/cthyb/latest/guide/settingparameters.html
- CT-HYB convergence tests: https://triqs.github.io/cthyb/latest/guide/cthyb_convergence_tests.html
- GitHub: https://github.com/TRIQS/triqs , https://github.com/TRIQS/cthyb
