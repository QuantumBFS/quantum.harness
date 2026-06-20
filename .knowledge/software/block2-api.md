# block2 — API + Examples Reference

High-performance DMRG / matrix-product-state (MPS) framework. C++11 header-only core
(exposed to Python via pybind11) with a high-level pure-Python driver. Strong focus on
*ab initio* quantum chemistry, but equally usable for model lattice Hamiltonians, finite
temperature, and real/imaginary-time dynamics.

- **Docs:** https://block2.readthedocs.io/en/latest/
- **Source (GitHub):** https://github.com/block-hczhai/block2-preview
- **Example scripts/data:** https://github.com/hczhai/block2-example-data
- **Release paper:** Zhai et al., *J. Chem. Phys.* 159, 234110 (2023), arXiv:2310.03920,
  DOI 10.1063/5.0180424. Local copy:
  `.knowledge/literature/software/2310.03920_block2-a-comprehensive-open-source-framework-to-develop-and.md`

> **Package name vs repo name.** The GitHub repo is `block2-preview`, but the pip package
> is **`block2`** (OpenMP-only) or **`block2-mpi`** (hybrid OpenMP + MPI). Install exactly
> one of the two. Do not `pip install block2-preview`. Development builds come from an
> extra index, see Installation.

---

## What block2 does

- **Ground-state DMRG** for *ab initio* electronic-structure Hamiltonians (one- and
  two-electron integrals) and for arbitrary custom/model Hamiltonians.
- **Excited states** via state-averaging, projected orthogonalization, level-shift, and
  harmonic Davidson.
- **General operators / MPO construction** from a symbolic expression builder: arbitrary
  parity-preserving Hamiltonians (n-body terms), bosonic operators, Pauli strings,
  non-Hermitian / anti-Hermitian operators.
- **Observables:** expectation values, N-particle reduced density matrices (1/2/3/4-PDM and
  transition PDMs), spin-spin and general correlation functions, entanglement entropy,
  CSF/determinant coefficients.
- **Dynamics:** time-dependent DMRG (real + imaginary time, TST and TDVP), dynamical
  (Green's function) DMRG via correction vectors, Chebyshev DMRG.
- **Finite temperature:** ancilla (purification) imaginary-time approach and
  sum-over-states.
- **Symmetries:** particle-number U(1), total spin SU(2) ("spin-adapted"), projected spin
  Sz, spin-orbital (no spin symmetry), Abelian point groups, and user-defined symmetry
  groups (`SAny`) including Z2/Zn and SU(2) of arbitrary content.
- **Interfaces:** PySCF (integrals, DMRG-CASSCF, NEVPT2), LibDMET, fcdmft (DMFT), Forte,
  OpenMolcas, Qiskit, pyblock3, StackBlock (input-file compatible via `block2main`).

---

## Installation

```
pip install block2          # OpenMP only (most users)
pip install block2-mpi      # hybrid OpenMP/MPI (distributed clusters)
```

Development / pinned versions from the preview index:

```
pip install block2==<version> --extra-index-url=https://block-hczhai.github.io/block2-preview/pypi/
pip install block2-mpi==<version> --extra-index-url=https://block-hczhai.github.io/block2-preview/pypi/
```

Binary wheels: Python 3.8–3.14 on macOS, Linux, Windows. Dependencies: `numpy`, `scipy`
(used by the Python driver), plus MKL or BLAS+LAPACK at the C++ level.

Manual build (when wheels do not fit, e.g. very large bond dimensions or complex/SOC):

```
mkdir build && cd build
cmake .. -DUSE_MKL=ON -DBUILD_LIB=ON -DLARGE_BOND=ON -DMPI=ON
make -j 10
```

Common cmake flags:

| Flag | Purpose |
|---|---|
| `-DUSE_MKL=ON` | Use Intel MKL (else `-DUSE_MKL=OFF -DF77UNDERSCORE=ON/OFF` for BLAS/LAPACK) |
| `-DLARGE_BOND=ON` | Raise max bond dimension to 4294967295 |
| `-DUSE_COMPLEX=ON` | Complex integrals (relativistic / response) |
| `-DUSE_SG=ON` | Spin-orbital / general-spin support (SOC) |
| `-DMPI=ON` | Build MPI parallel version |
| `-DOMP_LIB=INTEL/SEQ/TBB` | Choose OpenMP runtime |
| `-DCMAKE_BUILD_TYPE=Release` | Optimized build |

For a manual build, set the Python path:

```
export PYTHONPATH=/path/to/block2/build:/path/to/block2:${PYTHONPATH}
```

Command-line (StackBlock-compatible) entry point:

```
block2main dmrg.conf > dmrg.out
```

---

## Key API — `DMRGDriver`

The everything-driver lives in `pyblock2.driver.core`:

```python
from pyblock2.driver.core import DMRGDriver, SymmetryTypes, MPOAlgorithmTypes
import numpy as np
```

### Constructor

```python
DMRGDriver(stack_mem=1073741824, scratch='./nodex', clean_scratch=True,
           restart_dir=None, restart_dir_per_sweep=None, mps_dir=None,
           scratch_quota=None, alt_scratch=None, n_threads=None,
           n_mkl_threads=1, symm_type=SymmetryTypes.SU2, mpi=None,
           stack_mem_ratio=0.4, fp_codec_cutoff=1e-16, fp_codec_chunk=1024,
           min_mpo_mem=False, seq_type=None, align_type=0,
           compressed_mps_storage=False)
```

Most-used arguments:

| Argument | Meaning |
|---|---|
| `stack_mem` | Pre-allocated working memory **in bytes** (default 1 GiB). Raise this for large bond dimensions; out-of-memory errors usually mean this is too small. |
| `scratch` | Disk directory for renormalized operators / MPS tensors. Put on fast local disk. |
| `symm_type` | Symmetry mode, see below. `SU2` (spin-adapted) is the default. |
| `n_threads` | Total OpenMP threads. |
| `n_mkl_threads` | Threads inside dense BLAS calls (usually 1, with `n_threads` over blocks). |
| `stack_mem_ratio` | Fraction of `stack_mem` reserved for the "main" stack vs the per-sweep stack. |
| `mpi` | `True` to enable MPI parallelism (requires `block2-mpi`). |

### `SymmetryTypes` — choose the symmetry mode (critical decision)

| `SymmetryTypes.*` | Symmetry | Local dim (electron) | Use when |
|---|---|---|---|
| `SU2` | Particle number U(1) + total spin SU(2) | spatial orbital, d=4 | Default. Spin-adapted; fewer states, exact total-spin labels, best efficiency for spin-pure targets. |
| `SZ` | Particle number U(1) + projected spin Sz | spatial orbital, d=4 | Broken spin symmetry, unrestricted orbitals, when you need Sz-resolved quantities or custom fermionic Hamiltonians. |
| `SGF` | Spin-orbital, no spin symmetry | spin orbital, d=2 | Generalized HF, general-spin, SOC. |
| `SGB` | Qubit / Jordan-Wigner spin model | d=2 | Pauli-string Hamiltonians, spin-½ models. |
| `SAny` | User-defined Abelian groups (`U1`, `Z2`, `Zn`, ...) | custom | Custom model Hamiltonians (Bose-Hubbard, multi-U(1), reflection parity). |
| `SAnySU2` | User-defined with an SU(2) factor | custom | Spin-adapted custom models (e.g. SU(2) t-J). |

Add `^ SymmetryTypes.CPX` to any mode for complex arithmetic.

### `initialize_system`

```python
driver.initialize_system(n_sites, n_elec, spin=0, orb_sym=None,
                         heis_twos=-1, heis_twosz=0, ...)
```

| Argument | Meaning |
|---|---|
| `n_sites` | Number of DMRG sites (orbitals). |
| `n_elec` | Target total electron number (the conserved U(1) sector). |
| `spin` | **Twice** the total spin (SU2) or twice Sz (SZ). `spin=0` → singlet; `spin=2` → triplet. |
| `orb_sym` | List of point-group irrep labels per orbital (from the integral generator); `None` for C1. |
| `heis_twos` | For spin models: twice the on-site spin S (e.g. `1` for S=½ qubit mode). |

For custom-symmetry modes, call `driver.set_symmetry_groups("U1", "U1", ...)` *before*
`initialize_system`, and obtain the quantum-number constructor as `Q = driver.bw.SX`.

---

## Building the Hamiltonian / MPO

### Quantum-chemistry MPO from integrals

```python
mpo = driver.get_qc_mpo(h1e, g2e, ecore=0.0, para_type=None,
                        reorder=None, cutoff=1e-20, integral_cutoff=1e-20,
                        post_integral_cutoff=1e-20, fast_cutoff=1e-20,
                        algo_type=None, normal_order_ref=None, iprint=1)
```

- `h1e` — one-electron integrals (n×n). `g2e` — two-electron integrals (8-fold or 4-fold
  symmetry packed, or full n×n×n×n). `ecore` — constant (nuclear repulsion) energy.
- `algo_type` — MPO construction algorithm (`MPOAlgorithmTypes.Bipartite`,
  `.FastBipartite`, `.SVD`, ...). Bipartite gives the exact, optimal sparse MPO; SVD allows
  bond-dimension compression of the MPO at the cost of small error.
- `integral_cutoff` — drop integral elements below this magnitude before MPO build.

Integrals usually come from PySCF (see Worked example 2) or a FCIDUMP file:

```python
driver.read_fcidump(filename='N2.STO3G.FCIDUMP', pg='d2h')
driver.initialize_system(n_sites=driver.n_sites, n_elec=driver.n_elec,
                         spin=driver.spin, orb_sym=driver.orb_sym)
mpo = driver.get_qc_mpo(h1e=driver.h1e, g2e=driver.g2e, ecore=driver.ecore, iprint=1)
```

### Custom / model Hamiltonian — the expression builder

Three steps: (A) define the local Hilbert space and elementary-operator matrices per site;
(B) declare the system and add Hamiltonian terms symbolically; (C) build the MPO.

```python
driver.ghamil = driver.get_custom_hamiltonian(site_basis, site_ops)
b = driver.expr_builder()
b.add_term(op_string, indices, coeff)          # one call per term family
mpo = driver.get_mpo(b.finalize(adjust_order=True, fermionic_ops="cdCD"),
                     algo_type=MPOAlgorithmTypes.FastBipartite)
```

- `site_basis` — list (per site) of `[(Q(...), multiplicity), ...]`: the quantum numbers and
  degeneracy of each local basis state. `Q = driver.bw.SX`.
- `site_ops` — list (per site) of `{name: matrix}` mapping single-character operator names
  to their dense matrix representation in that local basis. `""` is the identity.
- `b.add_term(op_string, indices, coeff)` — `op_string` concatenates elementary-operator
  characters (e.g. `"cd"` = c†_i c_j); `indices` is a flattened array of site indices, one
  block per operator occurrence; `coeff` is the (scalar) coupling. A common idiom is
  `np.array([[i, i+1, i+1, i] for i in range(L-1)]).ravel()` for nearest-neighbour hopping
  with `op_string="cd"` (two `cd` factors per term → 4 indices/term).
- `b.add_term` may also take a per-term array of coefficients.
- `b.iscale(s)` — multiply all coefficients by `s` (e.g. `1/L` for energy per site).
- `b.finalize(adjust_order=True, fermionic_ops="...")` — reorder operators to a canonical
  form, inserting fermionic sign factors. `fermionic_ops` lists which operator characters
  are fermionic so signs are tracked correctly. **Required for fermionic models.**

The convention used throughout the docs/paper: `c,d` = a†_α, a_α; `C,D` = a†_β, a_β;
`E,F` = bosonic b†, b; `N` = number operator. These names are user-chosen via `site_ops`.

---

## Ground-state DMRG

```python
mps = driver.get_random_mps(tag="KET", bond_dim=250, nroots=1,
                            occs=None, full_fci=True, ...)
energy = driver.dmrg(mpo, mps, n_sweeps=20,
                     bond_dims=[250]*4 + [500]*4,
                     noises=[1e-4]*4 + [1e-5]*4 + [0],
                     thrds=[1e-10]*8,
                     dav_max_iter=30, dav_def_max_size=50,
                     cutoff=1e-20, twosite_to_onesite=None,
                     iprint=2)
```

| Argument | Meaning |
|---|---|
| `mpo`, `mps` | Hamiltonian MPO and the MPS being optimized (modified in place). |
| `n_sweeps` | Max number of sweeps. |
| `bond_dims` | Per-sweep bond-dimension schedule (list). Ramp up gradually. |
| `noises` | Per-sweep perturbative-noise schedule; **must decay to 0** in the final sweeps for a clean variational energy. |
| `thrds` | Per-sweep Davidson convergence thresholds. |
| `dav_max_iter` | Max Davidson iterations per local eigensolve. |
| `cutoff` | Singular-value cutoff in the per-site decomposition. |
| `tol` / `conv_tol` | Sweep-energy convergence criterion (optional). |
| `iprint` | Verbosity (0 silent, 1 per-sweep, 2 per-site). |

`get_random_mps` knobs: `tag` (name on disk), `bond_dim` (initial), `nroots` (number of
states), `occs` (occupancy guess per site to bias the initial quantum numbers).

`driver.dmrg` returns the energy (or array of energies if `nroots > 1`).

### Excited states

State-averaged: request several roots from one MPS.

```python
ket = driver.get_random_mps(tag="GS", bond_dim=250, nroots=3)
energies = driver.dmrg(mpo, ket, n_sweeps=20,
                       bond_dims=[250]*4 + [500]*4,
                       noises=[1e-4]*4 + [1e-5]*4 + [0],
                       thrds=[1e-10]*8, iprint=1)
# energies is the array of the lowest 3 eigenvalues
```

Other strategies available: projected orthogonalization (refine each root as an
independent MPS, projecting out lower states), level-shift (one-by-one with a shifted
Hamiltonian), and harmonic Davidson (interior states).

---

## Observables, expectation values, and RDMs

```python
impo = driver.get_identity_mpo()
normsq = driver.expectation(ket, impo, ket)            # ⟨ket|ket⟩
ener   = driver.expectation(ket, mpo, ket) / normsq    # ⟨ket|H|ket⟩

ssq_mpo = driver.get_spin_square_mpo(iprint=0)
ssq = driver.expectation(ket, ssq_mpo, ket) / normsq   # ⟨S²⟩

# Reduced density matrices
pdm1 = driver.get_1pdm(ket)
pdm2 = driver.get_2pdm(ket).transpose(0, 3, 1, 2)
pdm3 = driver.get_3pdm(ket, iprint=0, npdm_expr="((C+D)0+((C+D)0+(C+D)0)0)0")
```

`driver.expectation(bra, mpo, ket)` evaluates ⟨bra|operator|ket⟩ for any MPO (so it doubles
as a transition expectation when bra ≠ ket). Single-site / building-block MPOs come from
`driver.get_site_mpo(op='D', site_index=i)`.

General N-PDM and correlation functions go through `get_npdm`:

```python
# 1-PDM in SU(2) mode
rdm1 = driver.get_npdm(ket, pdm_type=1, npdm_expr='(C+D)0', max_bond_dim=500)

# Spin-spin correlation ⟨S_i · S_j⟩ (SU(2) mode)
spin_corr = driver.get_npdm(ket, pdm_type=2,
    npdm_expr='((C+D)2+(C+D)2)0',
    mask=(0, 0, 1, 1), max_bond_dim=500) * (-(3 ** 0.5) / 4)

# Restrict one operator to site 0 (cheaper, single reference site)
spin_corr_0 = driver.get_npdm(ket, pdm_type=2,
    npdm_expr='((C+D)2+(C+D)2)0',
    mask=(0, 0, 1, 1),
    index_masks=[[0], [0]] + [range(L)] * 2,
    max_bond_dim=500) * (-(3 ** 0.5) / 4)
```

CSF / determinant coefficients (spin-adapted):

```python
csfs, coeffs = driver.get_csf_coefficients(ket, cutoff=0.05, iprint=1)
mps = driver.get_mps_from_csf_coefficients(csfs, coeffs, tag="CMPS", dot=2)
```

---

## Dynamics

### Time-dependent DMRG

`driver.td_dmrg(mpo, ket, delta_t, target_t, ...)` evolves an MPS by exp(delta_t · MPO).
Imaginary time uses real `delta_t`; real time uses imaginary `delta_t` (`-dt*1j`).

```python
dbra = driver.copy_mps(dket, tag='DBRA')
for it in range(nstep - 1):
    dbra = driver.td_dmrg(mpo, dbra, -dt * 1j, -dt * 1j,
        final_mps_tag='DBRA', hermitian=True, bond_dims=[200], iprint=0)
    rtgf[it + 1] = driver.expectation(dbra, impo, dket)
```

Both time-step targeting (TST) and the time-dependent variational principle (TDVP) sweep
algorithms are supported; the Hamiltonian may be Hermitian or non-Hermitian.

### Dynamical (Green's function) DMRG

Frequency-domain correction-vector approach via `driver.greens_function`:

```python
dmpo = driver.get_site_mpo(op='D', site_index=isite)         # apply annihilation op
dket = driver.get_random_mps(tag="DKET", bond_dim=200)
driver.multiply(dket, dmpo, ket, n_sweeps=10)                # |dket⟩ = D|ket⟩
mpo.const_e -= energy                                        # shift H by -E0

bra = driver.copy_mps(dket, tag="BRA")
gfmat[iw] = driver.greens_function(bra, mpo, dmpo, ket, freq, eta,
    n_sweeps=6, bra_bond_dims=[200], ket_bond_dims=[200],
    thrds=[1E-6] * 10, iprint=0)
```

Real-time td-DMRG + FFT of the autocorrelation function is an alternative route to spectra:

```python
fftinp = -1j * rtgf * np.exp(-eta * dt * np.arange(0, npts))
frq_spectrum = np.fft.fftshift(np.fft.fft(fftinp)) * dt
```

Chebyshev DMRG is also available as an ill-conditioning-free spectral method.

### Finite-temperature DMRG (ancilla)

Ancilla/purification approach: each physical site is paired with an ancilla bath site; the
β=0 thermal MPS is created, then imaginary-time-evolved to inverse temperature β using
`td_dmrg`. Free energies and thermal PDMs are obtained by tracing out the ancillae. For
very low temperature (large β) the sum-over-states approach (DMRG for a few low-lying
eigenstates + a partition-function sum) is more efficient. See paper §II H.

---

## Worked example 1 — Hubbard-Holstein model (custom operators, SZ)

Verbatim from the release paper (Listing 1); ground-state energy = −6.956893.

```python
from pyblock2.driver.core import DMRGDriver, SymmetryTypes, MPOAlgorithmTypes
import numpy as np

N_SITES_ELEC, N_SITES_PH, N_ELEC = 4, 4, 4
N_PH, U, OMEGA, G = 11, 2, 0.25, 0.5
L = N_SITES_ELEC + N_SITES_PH

driver = DMRGDriver(scratch="./tmp", symm_type=SymmetryTypes.SZ, n_threads=4)
driver.initialize_system(n_sites=L, n_elec=N_ELEC, spin=0)

# [Part A] Set states and matrix representation of operators in local Hilbert space
site_basis, site_ops = [], []
Q = driver.bw.SX # quantum number wrapper (n_elec, 2 * spin, point group irrep)

for k in range(L):
   if k < N_SITES_ELEC:
     # electron part
     basis = [(Q(0, 0, 0), 1), (Q(1, 1, 0), 1), (Q(1, -1, 0), 1), (Q(2, 0, 0), 1)] # [0 a b 2]
     ops = {
        "": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]), # identity
        "c": np.array([[0, 0, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 0]]), # alpha+
        "d": np.array([[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1], [0, 0, 0, 0]]), # alpha
        "C": np.array([[0, 0, 0, 0], [0, 0, 0, 0], [1, 0, 0, 0], [0, -1, 0, 0]]), # beta+
        "D": np.array([[0, 0, 1, 0], [0, 0, 0, -1], [0, 0, 0, 0], [0, 0, 0, 0]]), # beta
     }
   else:
     # phonon part
     basis = [(Q(0, 0, 0), N_PH)]
     ops = {
        "": np.identity(N_PH), # identity
        "E": np.diag(np.sqrt(np.arange(1, N_PH)), k=-1), # ph+
        "F": np.diag(np.sqrt(np.arange(1, N_PH)), k=1), # ph
     }
   site_basis.append(basis)
   site_ops.append(ops)

# [Part B] Set Hamiltonian terms in Hubbard-Holstein model
driver.ghamil = driver.get_custom_hamiltonian(site_basis, site_ops)
b = driver.expr_builder()

# electron part
b.add_term("cd", np.array([[i, i + 1, i + 1, i] for i in range(N_SITES_ELEC - 1)]).ravel(), -1)
b.add_term("CD", np.array([[i, i + 1, i + 1, i] for i in range(N_SITES_ELEC - 1)]).ravel(), -1)
b.add_term("cdCD", np.array([[i, i, i, i] for i in range(N_SITES_ELEC)]).ravel(), U)

# phonon part
b.add_term("EF", np.array([[i + N_SITES_ELEC, ] * 2 for i in range(N_SITES_PH)]).ravel(), OMEGA)

# interaction part
b.add_term("cdE", np.array([[i, i, i + N_SITES_ELEC] for i in range(N_SITES_ELEC)]).ravel(), G)
b.add_term("cdF", np.array([[i, i, i + N_SITES_ELEC] for i in range(N_SITES_ELEC)]).ravel(), G)
b.add_term("CDE", np.array([[i, i, i + N_SITES_ELEC] for i in range(N_SITES_ELEC)]).ravel(), G)
b.add_term("CDF", np.array([[i, i, i + N_SITES_ELEC] for i in range(N_SITES_ELEC)]).ravel(), G)

# [Part C] Perform DMRG
mpo = driver.get_mpo(b.finalize(adjust_order=True), algo_type=MPOAlgorithmTypes.FastBipartite)
mps = driver.get_random_mps(tag="KET", bond_dim=250, nroots=1)
energy = driver.dmrg(mpo, mps, n_sweeps=10, bond_dims=[250] * 4 + [500] * 4,
   noises=[1e-4] * 4 + [1e-5] * 4 + [0], thrds=[1e-10] * 8, dav_max_iter=30, iprint=2)
print("DMRG energy = %20.15f" % energy)
```

### Minimal 1D Hubbard chain (from the docs)

```python
from pyblock2.driver.core import DMRGDriver, SymmetryTypes, MPOAlgorithmTypes
import numpy as np

driver = DMRGDriver(scratch="./tmp", symm_type=SymmetryTypes.SZ, n_threads=4)
driver.initialize_system(n_sites=L, n_elec=N_ELEC, spin=0)

# (define site_basis / site_ops as in the Hubbard-Holstein electron block, plus "N")
driver.ghamil = driver.get_custom_hamiltonian(site_basis, site_ops)
b = driver.expr_builder()
b.add_term("cd", np.array([[i, i + 1, i + 1, i] for i in range(L - 1)]).ravel(), -1)
b.add_term("CD", np.array([[i, i + 1, i + 1, i] for i in range(L - 1)]).ravel(), -1)
b.add_term("N", np.array([i for i in range(L)]), U)   # if "N" is the double-occupancy op

mpo = driver.get_mpo(b.finalize(adjust_order=True, fermionic_ops="cdCD"),
                     algo_type=MPOAlgorithmTypes.FastBipartite)
mps = driver.get_random_mps(tag="KET", bond_dim=250, nroots=1)
energy = driver.dmrg(mpo, mps, n_sweeps=10, bond_dims=[250]*4 + [500]*4,
    noises=[1e-4]*4 + [1e-5]*4 + [0], thrds=[1e-10]*8, dav_max_iter=30)
```

---

## Worked example 2 — Quantum-chemistry DMRG (N₂, via PySCF)

```python
from pyblock2.driver.core import DMRGDriver, SymmetryTypes
from pyblock2._pyscf.ao2mo import integrals as itg
from pyscf import gto, scf

# Generate molecule and obtain integrals
mol = gto.M(atom="N 0 0 0; N 0 0 1.1", basis="sto3g", symmetry="d2h")
mf = scf.RHF(mol).run(conv_tol=1E-14)
ncas, n_elec, spin, ecore, h1e, g2e, orb_sym = itg.get_rhf_integrals(
    mf, ncore=0, ncas=None, g2e_symm=8)

# Initialize driver (SU2 spin-adapted)
driver = DMRGDriver(scratch="./tmp", symm_type=SymmetryTypes.SU2, n_threads=4)
driver.initialize_system(n_sites=ncas, n_elec=n_elec, spin=spin, orb_sym=orb_sym)

# Build MPO from integrals and a random MPS
mpo = driver.get_qc_mpo(h1e=h1e, g2e=g2e, ecore=ecore, iprint=1)
ket = driver.get_random_mps(tag="GS", bond_dim=250, nroots=1)

# Run DMRG
bond_dims = [250] * 4 + [500] * 4
noises = [1e-4] * 4 + [1e-5] * 4 + [0]
thrds = [1e-10] * 8
energy = driver.dmrg(mpo, ket, n_sweeps=20, bond_dims=bond_dims,
                     noises=noises, thrds=thrds, iprint=1)
print("DMRG energy = %20.15f" % energy)
```

For SZ (unrestricted) use `itg.get_uhf_integrals(mf, ...)` + `SymmetryTypes.SZ`; for
spin-orbital use `itg.get_ghf_integrals(mf, ...)` + `SymmetryTypes.SGF`.

---

## Worked example 3 — Expectation, ⟨S²⟩, and RDMs

```python
# (after a converged DMRG run producing `ket` with Hamiltonian `mpo`)
impo = driver.get_identity_mpo()
normsq = driver.expectation(ket, impo, ket)
ener   = driver.expectation(ket, mpo, ket) / normsq
print("E   =", ener)

ssq_mpo = driver.get_spin_square_mpo(iprint=0)
print("S^2 =", driver.expectation(ket, ssq_mpo, ket) / normsq)

pdm1 = driver.get_1pdm(ket)          # shape (n, n) [SU2] or (2, n, n) [SZ]
pdm2 = driver.get_2pdm(ket).transpose(0, 3, 1, 2)
print("trace(1pdm) =", np.trace(pdm1))   # should equal n_elec
```

---

## SU(2) t-J model (custom SU(2) symmetry) — operator-string idiom

```python
driver = DMRGDriver(scratch="./tmp", symm_type=SymmetryTypes.SAnySU2, n_threads=4)
driver.set_symmetry_groups("U1Fermi", "SU2")
Q = driver.bw.SX
basis = [(Q(0, 0, 0), 1), (Q(1, 1, 1), 1)]   # empty + singly-occupied (no double occ.)
# ... define site_ops, then:
b.add_term("(C+D)0", indices, -(2 ** 0.5))                       # hopping (SU2 coupled)
b.add_term("((C+D)2+(C+D)2)0", indices, J * -(3 ** 0.5) / 2)     # S·S exchange part
b.add_term("((C+D)0+(C+D)0)0", indices, J * -1 / 2)             # n_i n_j part
```

The parenthesized `(C+D)0`, `(...)2` notation expresses SU(2)-coupled tensor operators of a
given total spin (0 = scalar, 2 = twice spin-1). These same expressions feed `npdm_expr` for
correlation functions.

---

## Bose-Hubbard model (`SAny`, single U(1))

```python
driver = DMRGDriver(scratch="./tmp", symm_type=SymmetryTypes.SAny, n_threads=4)
driver.set_symmetry_groups("U1")
Q = driver.bw.SX

basis = [(Q(i), 1) for i in range(NB_MAX + 1)]      # boson number 0..NB_MAX per site
ops = {
    "": np.identity(NB_MAX + 1),
    "C": np.diag(np.sqrt(np.arange(1, NB_MAX + 1)), k=-1),    # b†
    "D": np.diag(np.sqrt(np.arange(1, NB_MAX + 1)), k=1),     # b
    "N": np.diag(np.arange(0, NB_MAX + 1), k=0),             # number
}
# ... get_custom_hamiltonian, then:
b.add_term("CD", indices, -T)
b.add_term("N",  indices, -(MU + U / 2))
b.add_term("NN", indices, U / 2)
```

(`finalize` needs no `fermionic_ops` here — bosons carry no sign.)

---

## Pitfalls

- **SU2 vs SZ.** Use `SU2` (spin-adapted, default) for spin-pure targets: it is faster, more
  memory-efficient, and labels states by total spin via `spin = 2S`. Use `SZ` when you need
  broken-spin / unrestricted orbitals, Sz-resolved observables, or a custom fermionic
  Hamiltonian written in α/β operators. The two modes need *different* integrals
  (`get_rhf_integrals` vs `get_uhf_integrals`) and a different operator algebra in custom
  Hamiltonians. Mixing them silently gives wrong energies.
- **`spin` is twice the spin.** `initialize_system(spin=...)` takes 2S (SU2) or 2·Sz (SZ).
  `spin=0` singlet, `spin=2` triplet. A frequent off-by-factor-2 bug.
- **Noise schedule must end at 0.** Perturbative noise (`noises`) helps escape local minima
  early but biases the energy; the last sweep(s) must use `noise=0` for a clean variational
  number. Likewise ramp `bond_dims` up over sweeps, do not jump straight to the max.
- **`fermionic_ops` in `finalize`.** For custom fermionic Hamiltonians you must pass the set
  of fermionic operator characters (e.g. `fermionic_ops="cdCD"`) so Jordan-Wigner signs are
  inserted; `adjust_order=True` reorders terms to canonical form. Omitting it yields a wrong
  (sign-scrambled) Hamiltonian.
- **`stack_mem` (memory).** The default 1 GiB working stack is small for production runs;
  large bond dimensions throw stack-allocation errors unless you raise `stack_mem` (bytes).
  MPS / renormalized operators also spill to `scratch` — point it at fast local disk, not a
  network mount.
- **Package name.** Install `block2` or `block2-mpi`, never `block2-preview` (that is only
  the repository name). Install exactly one of the two variants.
- **PDM index conventions.** `get_2pdm` returns chemist-ordered indices; the docs commonly
  `.transpose(0, 3, 1, 2)` to reach the physicist convention. `get_npdm` with `npdm_expr`
  /`mask`/`index_masks` is the general (and only spin-resolved) route, and SU(2) PDMs use
  the coupled `(C+D)0` operator strings, not bare `cd`.
- **MPO algorithm choice.** `MPOAlgorithmTypes.FastBipartite` (exact, optimal sparse MPO) is
  the safe default for models; the `SVD` family compresses the MPO bond dimension (faster
  DMRG for large *ab initio* systems) at the price of a controllable error from the singular
  -value cutoff.

---

## Source links

- Docs index: https://block2.readthedocs.io/en/latest/
- Installation: https://block2.readthedocs.io/en/latest/user/installation.html
- Basic usage / input keywords: https://block2.readthedocs.io/en/latest/user/basic.html
- Quantum-chemistry Hamiltonians (QC DMRG, excited states, FCIDUMP, RDMs):
  https://block2.readthedocs.io/en/latest/tutorial/qc-hamiltonians.html
- Custom Hamiltonians (Hubbard, Hubbard-Holstein, Bose-Hubbard, SU(3) Heisenberg, t-J,
  correlation functions): https://block2.readthedocs.io/en/latest/tutorial/custom-hamiltonians.html
- Green's function & TD-DMRG: https://block2.readthedocs.io/en/latest/tutorial/greens-function.html
- Energy extrapolation: https://block2.readthedocs.io/en/latest/tutorial/energy-extrapolation.html
- Restarting DMRG: https://block2.readthedocs.io/en/latest/tutorial/restarting-dmrg.html
- Spin-orbit coupling: https://block2.readthedocs.io/en/latest/tutorial/dmrg-soc.html
- DMRGDriver API reference: https://block2.readthedocs.io/en/latest/api/pyblock2.html
- GitHub source: https://github.com/block-hczhai/block2-preview
- Example scripts/data: https://github.com/hczhai/block2-example-data
- Release paper (arXiv): https://arxiv.org/abs/2310.03920 — DOI 10.1063/5.0180424
