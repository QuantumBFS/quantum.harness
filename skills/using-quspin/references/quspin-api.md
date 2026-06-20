# QuSpin API + Examples Reference

QuSpin is an open-source Python package for **exact diagonalization (ED) and
quantum dynamics** of arbitrary **spin, fermion, and boson** lattice many-body
systems, with built-in support for **lattice symmetries** (translation, parity,
spin-inversion, particle-number/magnetization) that block-diagonalize the
Hilbert space. Operators are stored as SciPy sparse matrices (Cython core), so
the package interoperates cleanly with NumPy/SciPy.

Typical uses: ground-state and full-spectrum ED, real and imaginary time
evolution, quantum quenches, Floquet/periodically-driven systems, entanglement
entropy, ETH/MBL studies, spin-photon (cavity-QED) models.

- Homepage / docs: https://quspin.github.io/QuSpin/
- Example scripts: https://quspin.github.io/QuSpin/example_scripts.html
- Basis API: https://quspin.github.io/QuSpin/basis.html
- Operators API: https://quspin.github.io/QuSpin/operators.html
- Tools API: https://quspin.github.io/QuSpin/tools.html
- Paper: Weinberg & Bukov, SciPost Phys. 2, 003 (2017), arXiv:1610.03042
  (Part I, spins) and arXiv:1804.06782 (Part II, fermions/bosons/general basis).

---

## 1. The core convention: operator strings + coupling (site-coupling) lists

This is the single thing users get wrong most often. A many-body operator
`J · O^{μ₁}_{i₁} O^{μ₂}_{i₂} … O^{μₙ}_{iₙ}` is specified by **two pieces that must
line up by position**:

1. an **operator string** `"μ₁μ₂…μₙ"` — one character per site operator;
2. a **coupling list** (a.k.a. site-coupling list) `[[J, i₁, i₂, …, iₙ], …]` —
   the coupling `J` followed by exactly `n` site indices, in the **same order**
   as the characters in the operator string.

So the k-th character of the string acts on the k-th index in each row. The
operator string `"+-"` with row `[J, i, j]` means `J · S⁺_i S⁻_j`.

### Operator-string characters

| Type | Characters | Meaning |
|------|-----------|---------|
| Spin | `"x" "y" "z"` | `Sˣ Sʸ Sᶻ` (or `σˣ σʸ σᶻ` if `pauli=True`) |
| Spin ladder | `"+" "-"` | `S⁺ S⁻` |
| Identity | `"I"` | identity (often omittable) |
| Boson | `"n" "+" "-" "I"` | number `n=a†a`, create `a†` (`+`), annihilate `a` (`-`) |
| Spinless fermion | `"n" "+" "-" "z" "I"` | `n`, `c†` (`+`), `c` (`-`), `z` parity-string aware |
| Spinful fermion | use `"|"` to separate spin-up block from spin-down block, e.g. `"n|n"`, `"+-|"`, `"|+-"` |
| Photon (`photon_basis`) | `"|"` separates spin (left) from photon (right): `"x|"`, `"|n"`, `"-|+"` |

Notes that bite people:
- **`pauli` flag** on spin bases: `pauli=False` → `Sᵅ` operators (eigenvalues
  ±½); `pauli=True` (default for `spin_basis_1d`) → Pauli `σᵅ = 2Sᵅ`. A factor
  of 2 per operator. Set `pauli=False` for textbook spin-½ Hamiltonians.
- Hermiticity: for `S⁺_i S⁻_j` (`"+-"`) you must **also add the conjugate**
  `S⁻_i S⁺_j` (`"-+"`), or use `"xx"`+`"yy"`. QuSpin will raise a Hermiticity
  error otherwise (unless checks are disabled).
- Indices are **0-based**: sites run `0 … L-1`.
- **Open boundary (OBC):** loop `for i in range(L-1)`, bond `[J,i,i+1]`.
- **Periodic boundary (PBC):** loop `for i in range(L)`, bond `[J,i,(i+1)%L]`.

```python
# spin-1/2 Heisenberg nearest-neighbor, OBC:
J_zz = [[1.0, i, i+1] for i in range(L-1)]
J_xy = [[0.5, i, i+1] for i in range(L-1)]   # 0.5 so that xy + h.c. = S+S- + S-S+
h_z  = [[hz, i] for i in range(L)]
static = [["+-", J_xy], ["-+", J_xy], ["zz", J_zz], ["z", h_z]]
```

Common operator strings: `"zz"` (Ising/ΔSᶻSᶻ), `"+-"`/`"-+"` (XY hopping/flip),
`"xx"`,`"yy"`, `"nn"` (density-density), `"+-"` for fermion/boson hopping
`c†_i c_j`, three-site `"zxz"`, `"zyy"` etc.

---

## 2. Basis construction

Import from `quspin.basis`. Two families:

- **1d bases** (`*_basis_1d`): built-in 1d symmetries selected by keyword block
  arguments (`kblock`, `pblock`, `zblock`, …).
- **general bases** (`*_basis_general`): **user-defined symmetries** for any
  lattice/dimension, passed as `blockname=(permutation_array, sector)`.

### 1d basis classes

```python
spin_basis_1d(L, Nup=None, m=None, S="1/2", pauli=True,
              a=1, kblock=None, pblock=None, zblock=None,
              zAblock=None, zBblock=None, pzblock=None, ...)
boson_basis_1d(L, Nb=None, nb=None, sps=None, a=1, kblock=..., pblock=..., ...)
spinless_fermion_basis_1d(L, Nf=None, nf=None, a=1, kblock=..., pblock=..., ...)
spinful_fermion_basis_1d(L, Nf=None, nf=None, a=1, kblock=..., ...)
```

Particle-number / magnetization conservation (reduces Hilbert space):

| kwarg | basis | meaning |
|-------|-------|---------|
| `Nup` | spin | number of up-spins (fixes total Sᶻ sector). `Nup=L//2` → Sᶻ=0 |
| `m`   | spin | magnetization density (alternative to `Nup`) |
| `S`   | spin | total spin per site, e.g. `"1/2"`, `"1"`, `"3/2"` |
| `Nb`  | boson | total boson number; `sps` = states-per-site (e.g. `sps=2` hard-core) |
| `nb`  | boson | boson density |
| `Nf`  | fermion | total fermion number; for spinful pass tuple `(Nup,Ndown)` |

Symmetry block arguments (each restricts to one symmetry sector):

| kwarg | symmetry | values |
|-------|----------|--------|
| `kblock=int` | translation; momentum `k = 2π·int/(L/a)` | integer 0…L-1 |
| `a=int` | sites per unit cell for translation | default 1 |
| `pblock=±1` | parity (reflection about chain center) | +1 / −1 |
| `zblock=±1` | global spin inversion (Z₂) | +1 / −1 |
| `zAblock`,`zBblock=±1` | sublattice A / B spin inversion | +1 / −1 |
| `pzblock=±1` | combined parity × spin-inversion | +1 / −1 |

Consistency rule: **only request a symmetry block if the Hamiltonian actually has
that symmetry**, and conservation laws must be mutually compatible. For total
momenta `k ≠ 0, π`, translation does not commute with parity — QuSpin then uses
real semi-momentum states automatically when both `kblock` and `pblock` are set.
A disorder field breaks parity and translation, so drop `pblock`/`kblock` there.

```python
basis = spin_basis_1d(L, pauli=False, Nup=L//2, pblock=1)  # Sz=0, +parity
print(basis)            # display the basis states
basis.Ns                # Hilbert-space (sector) dimension
```

### General basis classes (any dimension, user-defined symmetries)

```python
spin_basis_general(N, Nup=None, m=None, S="1/2", pauli=True, **blocks)
boson_basis_general(N, Nb=None, nb=None, sps=None, **blocks)
spinless_fermion_basis_general(N, Nf=None, nf=None, **blocks)
spinful_fermion_basis_general(N, Nf=None, nf=None, **blocks)
```

Here `N` is the number of sites; each symmetry is passed as
`blockname=(perm, sector)` where `perm` is an integer array giving the image of
each site under the symmetry transformation, and `sector` selects the
eigenvalue/quantum number. For Z-type (sign-flip) symmetries the permutation
uses negative-encoded indices `Z = -(s+1)`.

```python
# 2D Lx×Ly lattice site labels s = x + Lx*y
s = np.arange(N_2d); x = s % Lx; y = s // Lx
T_x = (x+1)%Lx + Lx*y          # translation along x
T_y = x + Lx*((y+1)%Ly)        # translation along y
P_x = x + Lx*(Ly-y-1)          # reflection in y
P_y = (Lx-x-1) + Lx*y          # reflection in x
Z   = -(s+1)                   # global spin inversion
basis_2d = spin_basis_general(N_2d,
    kxblock=(T_x,0), kyblock=(T_y,0),
    pxblock=(P_x,0), pyblock=(P_y,0), zblock=(Z,0))
```

### Combining / specialized bases

```python
tensor_basis(*basis_list)     # tensor-product Hilbert space (e.g. ladders, mixtures);
                              #   operator strings use "|" to address each factor
photon_basis(basis_class, Nph=..., Ntot=...)  # couple a spin/fermion chain to one
                              #   photon (HO) mode; "|" separates matter (left)/photon (right)
user_basis(basis_dtype, N, op_dict, ...)      # fully user-defined basis / constraints
```

### Basis methods (work on any basis)

| Method | Purpose |
|--------|---------|
| `basis.Ns` | dimension of the (symmetry-reduced) Hilbert space |
| `basis.Op(opstr, indx, J, dtype)` | build a single operator as sparse matrix arrays |
| `basis.index(state)` | basis index of a many-body Fock state |
| `basis.int_to_state` / `basis.state_to_int` | state ↔ integer conversions |
| `basis.ent_entropy(state, sub_sys_A=..., density=..., return_rdm=..., alpha=1.0)` | entanglement entropy of a state (or batch of states) for subsystem `sub_sys_A`; returns dict with key `"Sent_A"` |
| `basis.partial_trace(state, sub_sys_A=...)` | reduced density matrix |
| `basis.expanded_state` / `basis.get_vec(v)` | map a symmetry-sector vector back to the full Hilbert space |
| `basis.Op_shift_sector(other_basis, op_list, v)` | apply an operator that maps between symmetry sectors |

---

## 3. The `hamiltonian` class (operators)

Import from `quspin.operators`.

```python
hamiltonian(static_list, dynamic_list, N=None, basis=None, shape=None,
            dtype=numpy.complex128,
            static_fmt=None, dynamic_fmt=None,
            copy=True, check_symm=True, check_herm=True, check_pcon=True,
            **basis_args)
```

- **`static_list`** — time-independent terms:
  `[[opstr, coupling_list], …]`, e.g. `[["zz", J_zz], ["+-", J_xy], ["z", h_z]]`.
- **`dynamic_list`** — time-dependent terms, each carries a scalar drive function
  `f(t, *args)` and its args:
  `[[opstr, coupling_list, func, func_args], …]`, e.g.
  `[["zz", J_nn, drive, [Omega]]]`. The matrix multiplied by `f(t,*args)` is
  summed; QuSpin auto-combines terms sharing the same function.
- **`basis`** — a basis object (carries the symmetry sectors). Alternatively pass
  `N=` and basis kwargs and QuSpin builds a default basis.
- **`dtype`** — `np.float64` for real Hamiltonians, `np.complex128` (default) when
  matrix elements are complex (e.g. `"y"`/`"+-"` with momentum phases, kick
  operators). Forcing real on a complex operator raises an error.
- **`check_herm`** — verify Hermiticity. **`check_symm`** — verify the operator
  respects the basis's requested symmetries. **`check_pcon`** — verify
  particle-number / magnetization conservation. Disable selectively for
  non-Hermitian or sector-changing operators:
  `no_checks = dict(check_symm=False, check_herm=False, check_pcon=False)`.

`hamiltonian` objects support arithmetic: `H1 + H2`, `2.0*H`, `0.5*hamiltonian(...)`.

### Diagonalization

| Method | Purpose |
|--------|---------|
| `H.eigh(time=0.0)` | **dense** full eigensystem → `(E, V)`, columns of `V` are eigenvectors |
| `H.eigvalsh(time=0.0)` | dense eigenvalues only → `E` |
| `H.eigsh(k=6, which="SA"/"LA"/"BE", sigma=None, maxiter=..., return_eigenvectors=True, **kw)` | **sparse** (Lanczos/ARPACK) for a few eigenpairs |

`eigsh` keywords: `k` = number of eigenpairs; `which="SA"` smallest-algebraic
(ground state), `"LA"` largest, `"BE"` both ends; `sigma=E_star` shift-invert to
find states nearest energy `E_star`; `return_eigenvectors=False` for values only.
Choose dense `eigh` when the sector fits in memory (`8·Ns²` bytes); use sparse
`eigsh` for ground state / few states of large sectors.

```python
E       = H.eigvalsh()                 # full spectrum
E, V    = H.eigh()                     # full eigensystem
Emin,Emax = H.eigsh(k=2, which="BE", maxiter=1e4, return_eigenvectors=False)
E0, psi0  = H.eigsh(k=1, which="SA")   # ground state
psi0    = psi0.ravel()
```

### Time evolution

```python
H.evolve(v0, t0, times, iterate=False, solver_name="dop853",
         stack_state=False, verbose=False, imag_time=False,
         rtol=1e-9, atol=1e-9, **solver_args)
```
Solves the (possibly time-dependent) Schrödinger equation from `t0` over `times`.
- `times` may be a single time or an array; returns the state(s).
- `iterate=True` → returns a **generator** yielding the state at each time
  (memory-friendly; feed straight into `obs_vs_time`).
- `imag_time=True` → imaginary-time evolution (e.g. ground-state projection).
- `rtol`/`atol` control the ODE solver accuracy.

```python
psi_t = H.evolve(psi_i, 0.0, t_vals, iterate=True, rtol=1e-9, atol=1e-9)
```

### Other operator methods

| Method | Purpose |
|--------|---------|
| `H.dot(v, time=0.0)` / `H.rdot(v)` | matrix–vector product `H·v` / `v·H` |
| `H.expt_value(v, time=0.0)` | expectation value `⟨v|H|v⟩` (handles batches) |
| `H.matrix_ele(u, v, time=0.0)` | matrix element `⟨u|H|v⟩` |
| `H.rotate_by(other, generator=False, a=1.0)` | similarity transform; `generator=True` → `exp(a·B†)·H·exp(a·B)` |
| `H.tocsr(time=0.0)` / `H.todense(time=0.0)` / `H.toarray()` | export to SciPy/NumPy matrix |
| `H.aslinearoperator(time=0.0)` | wrap as `scipy.sparse.linalg.LinearOperator` |
| `H.trace(time=0.0)` | trace |
| `H.update_matrix_formats(...)`, `H.astype(dtype)` | format / dtype management |

### Related operator classes

```python
quantum_operator(input_dict, ...)        # parameter-dependent operator: pre-build named
                                         #   terms, then H(params=dict(...)) plugs in couplings
quantum_LinearOperator(static_list, basis=..., dtype=...)  # matrix-free; applies operator
                                         #   to a state without storing the matrix — large systems + eigsh
exp_op(O, a=1.0, start=None, stop=None, num=None, endpoint=None, iterate=False)
                                         # matrix exponential exp(a·O); exp_op(B,a=z).dot(A) = exp(zB)·A.
                                         #   With start/stop/num builds a grid of exponentials (e.g. evolution steps)
```

---

## 4. Tools / measurements

Import from `quspin.tools.measurements`, `quspin.tools.Floquet`,
`quspin.tools.evolution`, `quspin.tools.block_tools`.

| Function | Signature (key args) | Purpose |
|----------|---------------------|---------|
| `obs_vs_time` | `obs_vs_time(psi_t, times, Obs_dict, return_state=False, Sent_args=None, enforce_pure=False)` | expectation values of each observable in `Obs_dict={"name":H_obs}` along a trajectory `psi_t` (array of states, a tuple `(psi,E,V)`, or a generator); returns a dict keyed by observable name, plus `"Sent_time"` if `Sent_args` given |
| `ent_entropy` | `ent_entropy(system_state, basis, chain_subsys=None, density=True, alpha=1.0, return_rdm=None)` | entanglement (Rényi-α) entropy; **deprecated** in favor of `basis.ent_entropy`. Returns dict with key `"Sent"` |
| `diag_ensemble` | `diag_ensemble(N, system_state, E2, V2, Obs=..., Sd_Renyi=..., Srdm_Renyi=..., Srdm_args=..., densities=True, alpha=1.0)` | infinite-time / diagonal-ensemble averages of observables and entropies given an eigenbasis `(E2,V2)` |
| `ED_state_vs_time` | `ED_state_vs_time(psi, E, V, times, iterate=False)` | evolve a state with a precomputed eigenbasis (constant H) |
| `project_op` | `project_op(Obs, proj, dtype=...)` | project an observable onto a symmetry-reduced subspace |
| `evolve` | `evolve(v0, t0, times, f, solver_name="dop853", real=False, imag_time=False, ...)` | integrate a user-defined first-order ODE `dv/dt = f(t,v)` (e.g. Gross–Pitaevskii) |
| `expm_multiply_parallel` | `expm_multiply_parallel(A, a=1.0, dtype=...)` then `.dot(v, work_array=...)` | OpenMP-parallel `exp(a·A)·v` without forming the exponential — large-system real-time evolution |
| `Floquet` | `Floquet(evo_dict, HF=False, UF=False, thetaF=False, VF=False, n_jobs=1)` | exact Floquet spectrum/states. `evo_dict` is one of `{"H","t_list","dt_list"}`, `{"H","T"}`, or `{"H_list","dt_list"}`. Reads off `.EF` (quasienergies), `.VF`, `.HF`, `.UF` |
| `Floquet_t_vec` | `Floquet_t_vec(Omega, N_const, len_T=100, N_up=0, N_down=0)` | time grid for driven systems; attributes `.vals`, `.T`, `.i`, `.strobo.vals`, `.strobo.inds` |
| `block_diag_hamiltonian` / `block_ops` | `(blocks, static, dynamic, basis_con, basis_args, dtype, ...)` | build/evolve a Hamiltonian block-diagonal across a list of symmetry sectors (e.g. for states not in one sector) |

`basis.ent_entropy(state, sub_sys_A=..., density=True, return_rdm=None, alpha=1.0)`
is the current recommended entanglement-entropy entry point and returns a dict
with key `"Sent_A"`.

---

## 5. Worked examples (verbatim)

### 5.1 Ground-state / full-spectrum ED of the XXZ chain (Example 0)

Source: https://quspin.github.io/QuSpin/examples/example0.html

```python
#####################################################################
#                            example 0                              #
#    In this script we demonstrate how to use QuSpin's exact        #
#    diagonlization routines to solve for the eigenstates and       #
#    energies of the XXZ chain.                                     #
#####################################################################
from quspin.operators import hamiltonian  # Hamiltonians and operators
from quspin.basis import spin_basis_1d  # Hilbert space spin basis
import numpy as np  # generic math functions

#
##### define model parameters #####
L = 12  # system size
Jxy = np.sqrt(2.0)  # xy interaction
Jzz_0 = 1.0  # zz interaction
hz = 1.0 / np.sqrt(3.0)  # z external field
#
##### set up Heisenberg Hamiltonian in an external z-field #####
# compute spin-1/2 basis
# basis = spin_basis_1d(L,pauli=False)
# basis = spin_basis_1d(L,pauli=False,Nup=L//2) # zero magnetisation sector
basis = spin_basis_1d(
    L, pauli=False, Nup=L // 2, pblock=1
)  # and positive parity sector
# define operators with OBC using site-coupling lists
J_zz = [[Jzz_0, i, i + 1] for i in range(L - 1)]  # OBC
J_xy = [[Jxy / 2.0, i, i + 1] for i in range(L - 1)]  # OBC
h_z = [[hz, i] for i in range(L)]
# static and dynamic lists
static = [["+-", J_xy], ["-+", J_xy], ["zz", J_zz], ["z", h_z]]
dynamic = []
# compute the time-dependent Heisenberg Hamiltonian
H_XXZ = hamiltonian(static, dynamic, basis=basis, dtype=np.float64)
#
##### various exact diagonalisation routines #####
# calculate entire spectrum only
E = H_XXZ.eigvalsh()
# calculate full eigensystem
E, V = H_XXZ.eigh()
# calculate minimum and maximum energy only
Emin, Emax = H_XXZ.eigsh(k=2, which="BE", maxiter=1e4, return_eigenvectors=False)
# calculate the eigenstate closest to energy E_star
E_star = 0.0
E, psi_0 = H_XXZ.eigsh(k=1, sigma=E_star, maxiter=1e4)
psi_0 = psi_0.reshape((-1,))
```

### 5.2 Quench / Floquet time evolution + entanglement entropy (Example 2)

Source: https://quspin.github.io/QuSpin/examples/example2.html — periodically
driven transverse-field Ising chain with a parallel field; uses a `dynamic` list
with a step-drive function, `kblock`/`pblock` symmetry, `evolve` + `obs_vs_time`
for time-dependent energy and entanglement entropy, plus the `Floquet` and
`diag_ensemble` tools. Shows multi-spin operator strings (`"zxz"`).

```python
##################################################################################
#                            example 1                                           #
#     In this example we show how to use some of QuSpin's tools for studying     #
#     Floquet systems by analysing the heating in a periodically driven          #
#     spin chain. We also show how to construct more complicated multi-spin      #
#     interactions using QuSpin's interface.                                     #
##################################################################################
from quspin.operators import hamiltonian  # Hamiltonians and operators
from quspin.basis import spin_basis_1d  # Hilbert space spin basis
from quspin.tools.measurements import obs_vs_time, diag_ensemble  # t_dep measurements
from quspin.tools.Floquet import Floquet, Floquet_t_vec  # Floquet Hamiltonian
import numpy as np  # generic math functions

#
##### define model parameters #####
L = 14  # system size
J = 1.0  # spin interaction
g = 0.809  # transverse field
h = 0.9045  # parallel field
Omega = 4.5  # drive frequency


#
##### set up alternating Hamiltonians #####
# define time-reversal symmetric periodic step drive
def drive(t, Omega):
    return np.sign(np.cos(Omega * t))


drive_args = [Omega]
# compute basis in the 0-total momentum and +1-parity sector
basis = spin_basis_1d(L=L, a=1, kblock=0, pblock=1)
# define PBC site-coupling lists for operators
x_field_pos = [[+g, i] for i in range(L)]
x_field_neg = [[-g, i] for i in range(L)]
z_field = [[h, i] for i in range(L)]
J_nn = [[J, i, (i + 1) % L] for i in range(L)]  # PBC
# static and dynamic lists
static = [["zz", J_nn], ["z", z_field], ["x", x_field_pos]]
dynamic = [
    ["zz", J_nn, drive, drive_args],
    ["z", z_field, drive, drive_args],
    ["x", x_field_neg, drive, drive_args],
]
# compute Hamiltonians
H = 0.5 * hamiltonian(static, dynamic, dtype=np.float64, basis=basis)
#
##### set up second-order van Vleck Floquet Hamiltonian #####
# zeroth-order term
Heff_0 = 0.5 * hamiltonian(static, [], dtype=np.float64, basis=basis)
# second-order term: site-coupling lists
Heff2_term_1 = [[+(J**2) * g, i, (i + 1) % L, (i + 2) % L] for i in range(L)]  # PBC
Heff2_term_2 = [[+J * g * h, i, (i + 1) % L] for i in range(L)]  # PBC
Heff2_term_3 = [[-J * g**2, i, (i + 1) % L] for i in range(L)]  # PBC
Heff2_term_4 = [[+(J**2) * g + 0.5 * h**2 * g, i] for i in range(L)]
Heff2_term_5 = [[0.5 * h * g**2, i] for i in range(L)]
# define static list
Heff_static = [
    ["zxz", Heff2_term_1],
    ["xz", Heff2_term_2],
    ["zx", Heff2_term_2],
    ["yy", Heff2_term_3],
    ["zz", Heff2_term_2],
    ["x", Heff2_term_4],
    ["z", Heff2_term_5],
]
# compute van Vleck Hamiltonian
Heff_2 = hamiltonian(Heff_static, [], dtype=np.float64, basis=basis)
Heff_2 *= -np.pi**2 / (12.0 * Omega**2)
# zeroth + second order van Vleck Floquet Hamiltonian
Heff_02 = Heff_0 + Heff_2
#
##### set up second-order van Vleck Kick operator #####
Keff2_term_1 = [[J * g, i, (i + 1) % L] for i in range(L)]  # PBC
Keff2_term_2 = [[h * g, i] for i in range(L)]
# define static list
Keff_static = [["zy", Keff2_term_1], ["yz", Keff2_term_1], ["y", Keff2_term_2]]
Keff_02 = hamiltonian(Keff_static, [], dtype=np.complex128, basis=basis)
Keff_02 *= np.pi**2 / (8.0 * Omega**2)
#
##### rotate Heff to stroboscopic basis #####
# e^{-1j*Keff_02} Heff_02 e^{+1j*Keff_02}
HF_02 = Heff_02.rotate_by(Keff_02, generator=True, a=1j)
#
##### define time vector of stroboscopic times with 100 cycles #####
t = Floquet_t_vec(Omega, 100, len_T=1)  # t.vals=times, t.i=init. time, t.T=drive period
#
##### calculate exact Floquet eigensystem #####
t_list = (
    np.array([0.0, t.T / 4.0, 3.0 * t.T / 4.0]) + np.finfo(float).eps
)  # times to evaluate H
dt_list = np.array(
    [t.T / 4.0, t.T / 2.0, t.T / 4.0]
)  # time step durations to apply H for
Floq = Floquet(
    {"H": H, "t_list": t_list, "dt_list": dt_list}, VF=True
)  # call Floquet class
VF = Floq.VF  # read off Floquet states
EF = Floq.EF  # read off quasienergies
#
##### calculate initial state (GS of HF_02) and its energy
EF_02, psi_i = HF_02.eigsh(k=1, which="SA", maxiter=1e4)
psi_i = psi_i.reshape((-1,))
#
##### time-dependent measurements
# calculate measurements
Sent_args = {"basis": basis, "chain_subsys": [j for j in range(L // 2)]}
# meas = obs_vs_time((psi_i,EF,VF),t.vals,{"E_time":HF_02/L},Sent_args=Sent_args)
# """
# alternative way by solving Schroedinger's eqn
psi_t = H.evolve(psi_i, t.i, t.vals, iterate=True, rtol=1e-9, atol=1e-9)
meas = obs_vs_time(psi_t, t.vals, {"E_time": HF_02 / L}, Sent_args=Sent_args)
# """
# read off measurements
Energy_t = meas["E_time"]
Entropy_t = meas["Sent_time"]["Sent"]
#
##### calculate diagonal ensemble measurements
DE_args = {"Obs": HF_02, "Sd_Renyi": True, "Srdm_Renyi": True, "Srdm_args": Sent_args}
DE = diag_ensemble(L, psi_i, EF, VF, **DE_args)
Ed = DE["Obs_pure"]
Sd = DE["Sd_pure"]
Srdm = DE["Srdm_pure"]
```

### 5.3 General basis (2D) with user-defined symmetries + entanglement entropy (Example 9)

Source: https://quspin.github.io/QuSpin/examples/example9.html — 2D
transverse-field Ising on a 4×4 torus via `spin_basis_general` with translation
(`kxblock`,`kyblock`), reflection (`pxblock`,`pyblock`), and spin-inversion
(`zblock`) symmetries; ground state via `eigsh`, stroboscopic evolution via
`exp_op`, and entanglement entropy via `basis.ent_entropy`.

```python
#####################################################################
#                            example 9                              #
#   In this script we demonstrate how to use QuSpin's               #
#   general basis class to construct user-defined symmetry sectors.#
#   We study thermalisation in the 2D transverse-field Ising model  #
#   with periodic boundary conditions.                              #
#####################################################################
from quspin.operators import hamiltonian, exp_op
from quspin.basis import spin_basis_1d, spin_basis_general
from quspin.tools.measurements import obs_vs_time
from quspin.tools.Floquet import Floquet_t_vec
import numpy as np
import matplotlib.pyplot as plt

###### define model parameters ######
L_1d = 16
Lx, Ly = 4, 4
N_2d = Lx * Ly
Omega = 2.0
A = 2.0

###### setting up user-defined symmetry transformations for 2d lattice ######
s = np.arange(N_2d)
x = s % Lx
y = s // Lx
T_x = (x + 1) % Lx + Lx * y
T_y = x + Lx * ((y + 1) % Ly)
P_x = x + Lx * (Ly - y - 1)
P_y = (Lx - x - 1) + Lx * y
Z = -(s + 1)

###### setting up bases ######
basis_1d = spin_basis_1d(L_1d, kblock=0, pblock=1, zblock=1)
basis_2d = spin_basis_general(
    N_2d,
    kxblock=(T_x, 0),
    kyblock=(T_y, 0),
    pxblock=(P_x, 0),
    pyblock=(P_y, 0),
    zblock=(Z, 0),
)
print("Size of 1D H-space: {Ns:d}".format(Ns=basis_1d.Ns))
print("Size of 2D H-space: {Ns:d}".format(Ns=basis_2d.Ns))

###### setting up operators in hamiltonian ######
Jzz_1d = [[-1.0, i, (i + 1) % L_1d] for i in range(L_1d)]
hx_1d = [[-1.0, i] for i in range(L_1d)]

Jzz_2d = [[-1.0, i, T_x[i]] for i in range(N_2d)] + [
    [-1.0, i, T_y[i]] for i in range(N_2d)
]
hx_2d = [[-1.0, i] for i in range(N_2d)]

Hzz_1d = hamiltonian([["zz", Jzz_1d]], [], basis=basis_1d, dtype=np.float64)
Hx_1d = hamiltonian([["x", hx_1d]], [], basis=basis_1d, dtype=np.float64)
Hzz_2d = hamiltonian([["zz", Jzz_2d]], [], basis=basis_2d, dtype=np.float64)
Hx_2d = hamiltonian([["x", hx_2d]], [], basis=basis_2d, dtype=np.float64)

###### calculate initial states ######
[E_1d_min], psi_1d = Hzz_1d.eigsh(k=1, which="SA")
[E_2d_min], psi_2d = Hzz_2d.eigsh(k=1, which="SA")
psi0_1d = psi_1d.ravel()
psi0_2d = psi_2d.ravel()

###### time evolution ######
nT = 200
t = Floquet_t_vec(Omega, nT, len_T=1)
U1_1d = exp_op(Hzz_1d + A * Hx_1d, a=-1j * t.T / 4)
U2_1d = exp_op(Hzz_1d - A * Hx_1d, a=-1j * t.T / 2)
U1_2d = exp_op(Hzz_2d + A * Hx_2d, a=-1j * t.T / 4)
U2_2d = exp_op(Hzz_2d - A * Hx_2d, a=-1j * t.T / 2)

def evolve_gen(psi0, nT, *U_list):
    yield psi0
    for i in range(nT):
        for U in U_list:
            psi0 = U.dot(psi0)
        yield psi0

psi_1d_t = evolve_gen(psi0_1d, nT, U1_1d, U2_1d, U1_1d)
psi_2d_t = evolve_gen(psi0_2d, nT, U1_2d, U2_2d, U1_2d)

###### compute expectation values of observables ######
Obs_1d_t = obs_vs_time(psi_1d_t, t.vals, dict(E=Hzz_1d), return_state=True)
Obs_2d_t = obs_vs_time(psi_2d_t, t.vals, dict(E=Hzz_2d), return_state=True)
Sent_time_1d = basis_1d.ent_entropy(Obs_1d_t["psi_t"], sub_sys_A=range(L_1d // 2))[
    "Sent_A"
]
Sent_time_2d = basis_2d.ent_entropy(Obs_2d_t["psi_t"], sub_sys_A=range(N_2d // 2))[
    "Sent_A"
]
```

---

## 6. Pitfalls

- **Operator-string / coupling-list misalignment.** The k-th character of the
  string acts on the k-th site index of each coupling row. `"+-"` with `[J,i,j]`
  is `J·S⁺_i S⁻_j`. Getting the order or the count wrong silently builds the
  wrong operator (or errors on length mismatch).
- **`pauli` factor of 2.** `spin_basis_1d` defaults to `pauli=True` (Pauli
  matrices, σ = 2S). For a textbook spin-½ Hamiltonian in terms of `S`, pass
  `pauli=False`, or expect every coupling effectively scaled.
- **Forgotten Hermitian conjugate.** Ladder hops (`"+-"`, `"-+"`) and complex
  terms need their conjugate partner or `check_herm` raises. Either add both, or
  use `"xx"`+`"yy"` for the XY part.
- **Symmetry block vs. conservation consistency.** Only request a symmetry block
  that the Hamiltonian actually has, and ensure blocks commute. A field along x
  breaks Sᶻ conservation (no `Nup`); disorder breaks translation and parity (no
  `kblock`/`pblock`). `check_symm`/`check_pcon` flag violations — do not blanket-
  disable them to silence a real bug.
- **`dtype` real vs. complex.** Use `np.complex128` whenever matrix elements are
  complex (`"y"`, momentum phases `kblock≠0,π` with parity, kick operators).
  Forcing `np.float64` on a complex operator errors.
- **OBC vs PBC loop range.** OBC bonds: `range(L-1)` with `[J,i,i+1]`. PBC bonds:
  `range(L)` with `[J,i,(i+1)%L]` — PBC adds the `L-1 → 0` wrap bond.
- **Basis size / memory.** Dense `eigh` needs `8·Ns²` bytes (real) for the matrix
  plus eigenvectors; estimate `Ns` after all sectors are fixed. Use symmetry
  sectors and sparse `eigsh` (or `quantum_LinearOperator` / matrix-free
  `expm_multiply_parallel`) for large systems. 1d spins reach ~ L ≤ 32 with
  symmetries; without them dense ED is bounded near `Ns ≈ 2^14–2^15`.
- **`ent_entropy` API drift.** Prefer `basis.ent_entropy(state, sub_sys_A=...)`
  (returns `"Sent_A"`); the standalone `tools.measurements.ent_entropy`
  (returns `"Sent"`, uses `chain_subsys`) is deprecated but still used in older
  examples — watch the differing key/keyword names.
- **`obs_vs_time` input forms.** It accepts (a) a precomputed `(psi, E, V)` tuple
  for constant-H evolution, (b) an array of states, or (c) a generator from
  `H.evolve(..., iterate=True)`. The generator path avoids storing all states
  and scales to larger systems.

---

## 7. Source links

- Homepage / docs index: https://quspin.github.io/QuSpin/
- Example scripts index: https://quspin.github.io/QuSpin/example_scripts.html
- Basis module API: https://quspin.github.io/QuSpin/basis.html
- Operators module API: https://quspin.github.io/QuSpin/operators.html
- Tools module API: https://quspin.github.io/QuSpin/tools.html
- Example 0 (ED of XXZ chain): https://quspin.github.io/QuSpin/examples/example0.html
- Example 2 (driven spin chain, time evolution + entropy): https://quspin.github.io/QuSpin/examples/example2.html
- Example 9 (2D TFIM, general basis + entropy): https://quspin.github.io/QuSpin/examples/example9.html
- user_basis tutorial: https://quspin.github.io/QuSpin/tutorials/user_basis.html
- Parallelization tutorial: https://quspin.github.io/QuSpin/tutorials/parallelization.html
- Paper (Part I, spins): arXiv:1610.03042 — SciPost Phys. 2, 003 (2017)
- In-repo paper render: .knowledge/literature/ed/1610.03042_quspin-a-python-package-for-dynamics-and-exact-diagonalisati.md
