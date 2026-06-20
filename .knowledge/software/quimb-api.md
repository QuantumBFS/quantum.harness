# quimb — API + Examples Reference

**quimb** (Johnnie Gray, JOSS 2018) is a pure-Python library for **quantum information** and **many-body** calculations, with two complementary halves:

- **`quimb` (dense / sparse)** — interactive linear-algebra-style quantum: build kets/bras/density-operators, Pauli/spin operators, Hamiltonians; compute expectations, entanglement measures, eigenstates; do exact time evolution. Backed by NumPy/SciPy, with optional SLEPc/PETSc for large distributed sparse eigensolves.
- **`quimb.tensor` (qtn)** — large-scale, **contraction-path-optimized tensor networks**: arbitrary `Tensor`/`TensorNetwork` objects whose contraction order is chosen by `opt_einsum` / **cotengra** hyper-optimizers; specialized MPS/MPO/PEPS classes; DMRG, TEBD, simple/full update, and full quantum-circuit simulation. Array backend is dispatched via **autoray**, so the same code runs on NumPy, JAX, PyTorch, TensorFlow, or CuPy (GPU + autodiff).

Design philosophy (5 layers): arrays (autoray) → tensors (labeled arrays) → tensor networks (tracked collections) → specialized networks (MPS/PEPS/…) → high-level algorithms (DMRG/circuits).

Conventional imports:

```python
import quimb as qu          # dense / sparse half
import quimb.tensor as qtn  # tensor-network half
```

---

## Part A — Dense / sparse `quimb`

### A.1 Building states & operators

| Function | Purpose |
|---|---|
| `qu.qu(data, qtype=None, sparse=False, dtype=None, normalized=False)` | Master converter (alias `quimbify`). `qtype` ∈ `"ket"` (col vec), `"bra"` (row vec), `"dop"` (operator / density matrix). Returns a `qarray` (NumPy subclass) or SciPy sparse if `sparse=True`. |
| `qu.ket(data, normalized=False)` | Column vector, shape `(d,1)`. |
| `qu.bra(data)` | Conjugated row vector, shape `(1,d)`. |
| `qu.dop(data, sparse=False)` | Square operator / density matrix. |
| `qu.sparse(data, stype='csr')` | Sparse SciPy representation. |
| `qu.normalize(state)` / `qu.nmlz` | Normalized copy. |
| `qu.expec(a, b)` / `qu.expectation` | ⟨a|b|a⟩ / ⟨a|b⟩ / Tr(ab) — overlap or expectation, dispatched to fast paths. |
| `qu.ptr(state, dims, keep)` / `qu.partial_trace` | Reduced density matrix; `dims` = subsystem dims list, `keep` = kept subsystem indices. |

**Operators on `qarray`/sparse** (monkey-patched): `.H` = Hermitian conjugate (dagger); `@` = matrix/dot product (preferred over `*`); `&` = Kronecker product.

Basis / named states:

| Function | Purpose |
|---|---|
| `qu.up()` / `qu.down()` | Single-qubit |0⟩ / |1⟩. |
| `qu.plus()` / `qu.zplus()` | |+⟩ eigenstate. |
| `qu.basis_vec(i, d)` | Computational basis ket |i⟩ in dim `d`. |
| `qu.computational_state("010")` | Product basis state from a bit string. |
| `qu.bell_state(label)` | One of the four Bell states (`"psi-"`, …). |
| `qu.ghz_state(n)` / `qu.w_state(n)` | n-qubit GHZ / W state. |
| `qu.neel_state(n)` | Antiferromagnetic Néel product state. |
| `qu.thermal_state(H, T)` | Gibbs state ∝ exp(−H/T). |

Tensor products / embedding:

| Function | Purpose |
|---|---|
| `qu.kron(a, b, c, ...)` | Kronecker product of many objects (`a & b & c` is equivalent). |
| `qu.kronpow(a, p)` | `a ⊗ a ⊗ … ` (p copies). |
| `qu.ikron(op, dims, inds)` | **Identity-padded** Kronecker — embed `op` on subsystems `inds`, identities elsewhere. |
| `qu.pkron(op, dims, inds)` | Like `ikron` but **permutes** so `op`'s factors land on (possibly non-contiguous, reordered) `inds`. |

```python
dims = [2] * 10                     # 10 qubits
X = qu.pauli("X")
op = qu.ikron(X, dims, inds=[3, 4]) # I⊗I⊗I⊗X⊗X⊗I…
ZIX = qu.pkron(qu.pauli("X") & qu.pauli("Z"), [2]*3, inds=[2, 0])
```

Gates & spin operators:

| Function | Purpose |
|---|---|
| `qu.pauli(label)` | Pauli `"X"/"Y"/"Z"/"I"` (cached, immutable; `pauli('Z') is pauli('Z')`). |
| `qu.spin_operator(label, S=1/2)` | Spin matrices Sx/Sy/Sz (= Pauli/2 for S=½). |
| `qu.hadamard()`, `qu.phase_gate(angle)`, `qu.controlled(U)` | Single-qubit / controlled gates. |
| `qu.CNOT()`/`cX()`, `cY()`, `cZ()`, `swap()`, `iswap()`, `fsim(theta, phi)` | Two-qubit gates. |

Hamiltonian builders (dense/sparse):

| Function | Purpose |
|---|---|
| `qu.ham_heis(n, j=1.0, b=0.0, cyclic=False, sparse=False)` | Heisenberg chain (XX+YY+ZZ + field). `j` may be a scalar or `(jx,jy,jz)`. |
| `qu.ham_j1j2(n, j1=1.0, j2=0.5, ...)` | J₁–J₂ chain (NN + NNN). |
| `qu.ham_ising(n, jz=1.0, bx=...)` | Transverse-field Ising. |
| `qu.ham_mbl(n, dh, j=1.0, ...)` | Many-body-localization chain with random field strength `dh`. |

Random objects (all accept `seed=…`, may use `qu.set_rand_bitgen(...)`):
`qu.rand_ket(d)`, `qu.rand_rho(d)`, `qu.rand_herm(d, sparse=False)`, `qu.rand_uni(d)`.

### A.2 Quantities & entanglement measures

| Function | Purpose |
|---|---|
| `qu.tr(A)` | Trace. |
| `qu.fidelity(a, b)` | State fidelity. |
| `qu.entropy(rho, base=2)` | Von Neumann entropy. |
| `qu.entropy_subsys(psi, dims, sysa)` | Entropy of a subsystem of a pure state (no explicit ptr needed). |
| `qu.mutinf(rho)` / `qu.mutual_information`, `qu.mutinf_subsys(psi, dims, sysa, sysb)` | Mutual information. |
| `qu.logneg(rho, dims)` / `qu.logneg_subsys(rho, dims, sysa, sysb)` | Logarithmic negativity (PT-based). |
| `qu.negativity(...)`, `qu.partial_transpose(rho, dims, sysa)` | Negativity / partial transpose. |
| `qu.concurrence(rho)` | Two-qubit concurrence. |
| `qu.schmidt_gap(psi, dims, sysa)` | Gap of the Schmidt (entanglement) spectrum. |
| `qu.correlation(p, A, B, i, j, dims)`, `qu.pauli_correlations(...)` | Two-site correlation functions. |
| `qu.trace_distance(a, b)`, `qu.quantum_discord(...)`, `qu.purify(rho)` | Distinguishability / discord / purification. |
| `qu.approx_spectral_function(A, f, tol=...)` | Stochastic-Lanczos estimate of Tr f(A) for huge sparse A. |

### A.3 Eigensolving & linear algebra

Full (NumPy):

```python
qu.eig(A)       qu.eigh(A)        # general / Hermitian eigensystem
qu.eigvals(A)   qu.eigvalsh(A)    # eigenvalues only
qu.eigvecs(A)   qu.eigvecsh(A)    # eigenvectors only
qu.svd(A)
el, ev = qu.eigh(H, autoblock=True)   # exploit abelian-symmetry block structure (large speedup)
```

Partial / sparse (key kwargs: `k` = #eigenpairs, `which` ∈ `"SA"/"LA"/"SM"/"LM"`, `sigma` = shift for interior, `backend` ∈ `'scipy'/'numpy'/'lobpcg'/'slepc'/'slepc-nompi'/'AUTO'`):

```python
qu.eigh(A, k=5)                  # 5 extremal eigenpairs
qu.eigvalsh(A, k=5)
qu.eigvecsh(A, k=1, which="SA")  # ground state
qu.groundstate(H)               # alias of eigvecsh(H, k=1, which="SA")
qu.groundenergy(H)              # ground-state energy only
qu.eigh(A, k=5, sigma=2.5)       # interior eigenpairs near 2.5 (shift-invert; SLEPc recommended)
qu.eigh_window(A, k=5, w_0=0.5, w_n=10)  # relative-window interior solve
qu.svds(A, k=10)                # partial SVD
qu.rsvd(A, k)                   # fast randomized SVD
```

Functions of operators: `qu.expm(A)`, `qu.sqrtm(A)`, `qu.expm_multiply(A, v)`.

### A.4 Time evolution — `qu.Evolution`

```python
qu.Evolution(p0, ham, t0=0, method='integrate', compute=None,
             int_stop=None, int_small_step=False, progbar=False)
```

- `p0` — initial ket or density matrix; `ham` — (sparse) matrix or callable `t → H(t)`.
- `method`: `'integrate'` (ODE; large systems, pure/mixed, time-dependent H); `'solve'` (diagonalize once, then any-time access; small systems); `'expm'` (single matrix-exp action; large + MPI, pure only).
- `compute` — callable `(t, pt) → value` or dict of them; results collected in `.results`.
- Methods/props: `.update_to(t)` advance; `.at_times(ts)` generator over states; `.pt` current state; `.t` current time.

```python
import quimb as qu

p0  = qu.rand_ket(2**10)
h   = qu.ham_heis(10, sparse=True)
evo = qu.Evolution(p0, h)

evo.update_to(1)          # evolve to t=1
state = evo.pt

for pt in evo.at_times([2, 3, 4]):   # snapshots
    print(qu.expec(pt, p0))
```

Observables along the way (dict form → `.results` keyed by name):

```python
compute = {"energy": lambda t, p: qu.expec(p, h),
           "z0":     lambda t, p: qu.expec(p, qu.ikron(qu.pauli('Z'), [2]*10, 0))}
evo = qu.Evolution(p0, h, compute=compute, progbar=True)
evo.update_to(5)
evo.results["energy"]    # list over recorded times
```

---

## Part B — Tensor networks `quimb.tensor`

### B.1 `Tensor` and `TensorNetwork`

```python
qtn.Tensor(data, inds, tags=None, left_inds=None)
```

- `inds` — tuple of string labels, one per axis. **Sharing an index name = an implicit bond / contraction** (indices are hyper-edges; an index on 3+ tensors is a hyper-edge).
- `tags` — arbitrary labels for grouping/selecting tensors (orthogonal to indices).

Tensor methods (inplace variants end in `_`): `.H` (conj), `.transpose('k1','k0')`, `.reindex({old:new})`, `.retag({old:new})`, `.fuse({new:[i,j]})`, `.split(left_inds, max_bond=, cutoff=)` (SVD factorization → 2-tensor TN), `.norm()`, `.new_ind(name, size=)`, `.new_bond(other, size=)`, `.modify(data=, inds=, tags=)`, `ta @ tb` (contract over shared inds).

```python
data = qu.bell_state("psi-").reshape(2, 2)
ket  = qtn.Tensor(data, inds=("k0", "k1"), tags=["KET"])
X    = qtn.Tensor(qu.pauli("X"), inds=("k0", "b0"), tags=["X"])
TN   = ket.H & X                       # & builds a (copying) TensorNetwork
```

`TensorNetwork`:

```python
qtn.TensorNetwork(tensors)             # copies inputs
tn = ta | tb | tc                      # | builds a *virtual* TN (views, edits propagate)
```

Selection / access: `tn.select(tags, which='all'|'any')`, `tn["TAG"]`, `tn[2, 3]` (lattice types), iterate `for t in tn:`. Modify: `tn.add_tensor(t)`, `tn.reindex({...})`, `tn.retag({...})`.

### B.2 Contraction with path optimization

```python
qtn.tensor_contract(*tensors, optimize='auto', output_inds=None, backend=None)
tn.contract(tags=..., optimize='auto', backend=None)
tn ^ ...        # contract whole network to a scalar
tn ^ "TAG"      # contract only tensors carrying a tag
```

`optimize` controls the contraction-tree search. String presets: `'auto'` (one-off), `'auto-hq'` (repeated), `'greedy'` (fast), `'optimal'` (small TNs only), `'random-greedy'` (large). Or pass an `opt_einsum.PathOptimizer` or a **cotengra** optimizer:

```python
import cotengra as ctg

# one-shot hyper-optimizer
opt = ctg.RandomGreedyOptimizer(max_repeats=1024)
val = tn.contract(optimize=opt)

# reusable: caches the path across many contractions of same-shaped TNs
opt = ctg.ReusableHyperOptimizer(
    minimize="combo",          # balance FLOPs and memory ('flops'|'size'|'write'|'combo')
    max_repeats=128,
    reconf_opts={},            # subtree reconfiguration
    progbar=False,
    directory=True,            # persist cache to disk
)
val = tn.contract(optimize=opt)
```

Inspect cost/memory **before** running (essential for large TNs):

```python
tree  = tn.contraction_tree(optimize='greedy')
tree.print_contractions(); tree.describe()      # 'log10[FLOPs]=… log2[SIZE]=…'
cost  = tn.contraction_cost(optimize='greedy')   # scalar operations (FLOPs)
width = tn.contraction_width(optimize='greedy')  # log2 of largest intermediate (memory)
path  = tn.contraction_path(optimize='greedy')
tree.plot_rubberband()                           # visualize the tree
```

Partial / structured contraction: `tn.contract_tags(tag)`, `tn.contract_between(t1, t2)`, `tn.contract_ind(ix)`, `tn.contract_cumulative(tags)`.

**Backend** is auto-dispatched by autoray from the array type of the tensors (NumPy / JAX / CuPy / Torch); you can also force it with `backend=` on `contract`.

```python
val = tn.contract(optimize=opt, backend='jax')   # run the contraction with JAX
```

### B.3 MPS / MPO and 1D algorithms

MPS constructors:

```python
qtn.MPS_rand_state(L, bond_dim, cyclic=False, dtype='float64', seed=None)
qtn.MPS_computational_state("0101")     # product state from bit string
qtn.MPS_neel_state(L)
qtn.MPS_product_state(arrays)
```

Key MPS methods: `.gate(G, where, contract='swap+split'|'split-gate'|True|'lazy', max_bond=, cutoff=)` (apply operator), `.H @ psi` (overlap/norm²), `.expec(...)`, `.entropy(i)`, `.schmidt_gap(i)`, `.magnetization(i)`, `.correlation(A, B, i, j)`, `.compress(max_bond=, cutoff=)`, `.normalize()`, `.left_canonize()`/`.right_canonize()`, `.bond_size(i, j)` / `.max_bond()`, `.show()` (ASCII), `.draw()`.

MPO constructors: `qtn.MPO_rand_herm(L, bond_dim)`, `qtn.MPO_ham_heis(L, j=1.0, bz=0.0, cyclic=False)`, `qtn.MPO_ham_ising(L, j, bx)`, `qtn.MPO_ham_XY(...)`, `qtn.MPO_identity(L)`. Custom Hamiltonians via the `qtn.SpinHam1D(S=1/2)` builder.

**DMRG** (`DMRG1`, `DMRG2`, `DMRGX` for excited states):

```python
qtn.DMRG2(ham, bond_dims=[...], cutoffs=1e-10, p0=None)
dmrg.solve(tol=1e-9, max_sweeps=10, cutoffs=..., verbosity=0)
dmrg.energy    # converged ground-state energy
dmrg.state     # converged MPS
```

**TEBD** (real or imaginary time):

```python
qtn.TEBD(psi0, H, dt=None, t0=0.0, split_opts=None)   # H is a LocalHam1D
tebd.split_opts["cutoff"] = 1e-12
tebd.update_to(T=3, tol=1e-3)        # evolve to time T
for psit in tebd.at_times(ts, tol=1e-3): ...   # snapshots
tebd.pt                               # current state
```

Local Hamiltonians for TEBD: `qtn.ham_1d_heis(L, j=1.0, bz=0.0)`, `qtn.ham_1d_ising(...)`, `qtn.LocalHam1D(L, H2=, H1=)`, or `SpinHam1D(...).build_local_ham(L)`.

### B.4 2D / PEPS

```python
qtn.PEPS.rand(Lx, Ly, bond_dim, seed=None)
qtn.LocalHam2D(Lx, Ly, H2=..., H1=None)     # 2-site + 1-site terms, auto-grouped
```

`TensorNetwork2D` / PEPS helpers: `peps.site_ind(x,y)`, `peps.site_tag(x,y)`, `peps[x, y]`, `tn.contract_boundary_(max_bond=, cutoff=, layer_tags=)` (boundary-MPS contraction managing bond growth), `peps.compute_local_expectation(terms, max_bond=, normalized=True)`.

Imaginary-time ground states:

```python
qtn.SimpleUpdate(psi0, ham, chi=32, compute_energy_every=10, keep_best=True)  # cheap, product env
qtn.FullUpdate(psi0=psi, ham=ham, chi=32, compute_energy_every=1, keep_best=True)  # boundary env, ALS fit
su.evolve(n_steps, tau=0.1)
su.best['state']; su.best['energy']; su.energies
```

### B.5 Circuit simulation — `qtn.Circuit`

```python
qtn.Circuit(N, psi0=None, gate_opts=None, tags=None)
# variants: qtn.CircuitMPS(N, ...)  qtn.CircuitPermMPS(N, ...)
```

Apply gates: `circ.apply_gate("H", 0)`, `circ.apply_gate("CX", 0, 1)`, `circ.apply_gate("RZ", 1.234, 2)` (`(name, *params, *qubits)`); per-gate kwargs `gate_round=`, `contract='auto-split-gate'` (default), `parametrize=True` (makes a trainable `PTensor`). Gate set (47+): `H,X,Y,Z,S,T,RX,RY,RZ,CX,CY,CZ,SWAP,ISWAP,CCX/CCNOT,FSIM,RXX,RYY,RZZ,U3,…`. Load OpenQASM with `qtn.Circuit.from_qasm(...)` / `from_qasm_file(...)`.

Outputs (all take cotengra `optimize=` and `simplify_sequence='ADCRS'`):

```python
circ.psi                                   # full state TN
circ.uni                                   # the unitary TN (no |0…0⟩)
amp = circ.amplitude("0101010101")         # single amplitude
for b in circ.sample(100): ...             # sample bit strings
circ.local_expectation(qu.pauli("Z") & qu.pauli("Z"), where=(4, 5))
psi_dense = circ.to_dense()                # 2^N vector (small N only)
```

Cost rehearsal before contracting (preview width/cost without computing):

```python
rehs  = circ.amplitude_rehearse()
tree  = rehs["tree"]
W = tree.contraction_width()      # log2 max intermediate (memory)
C = tree.contraction_cost(log=10) # log10 FLOPs
```

### B.6 Gradient optimization — `qtn.TNOptimizer`

```python
qtn.TNOptimizer(tn, loss_fn, norm_fn=None, loss_constants=None, loss_kwargs=None,
                autodiff_backend="jax",      # 'jax'|'torch'|'tensorflow'|'autograd'
                optimizer="l-bfgs-b",        # any scipy.optimize.minimize method, or 'adam'
                tags=None, constant_tags=None, shared_tags=None)
psi_opt = tnopt.optimize(n_iterations)       # returns optimized TN (numpy)
tnopt.plot()
```

---

## Worked examples (verbatim from docs)

### Dense time evolution (Evolution)

```python
import quimb as qu

p0  = qu.rand_ket(2**10)
h   = qu.ham_heis(10, sparse=True)
evo = qu.Evolution(p0, h)

# Single time step
evo.update_to(1)
state = evo.pt

# Multiple times
for pt in evo.at_times([2, 3, 4]):
    print(qu.expec(pt, p0))
```

### MPS DMRG ground state — periodic Heisenberg (300 sites)

```python
from quimb import *
from quimb.tensor import *

H = MPO_ham_heis(300, cyclic=True)
E_exact = heisenberg_energy(300)

dmrg = DMRG2(H)
dmrg.solve(max_sweeps=4, verbosity=1, cutoffs=1e-6)

(dmrg.energy - E_exact) / abs(E_exact)   # relative error
gs = dmrg.state
gs.max_bond()
```

### TEBD time evolution of an MPS

```python
import numpy as np
import quimb as qu
import quimb.tensor as qtn

L = 44
zeros  = "0" * ((L - 2) // 3)
binary = zeros + "1" + zeros + "1" + zeros
psi0 = qtn.MPS_computational_state(binary)

H = qtn.ham_1d_heis(L)

tebd = qtn.TEBD(psi0, H)
tebd.split_opts["cutoff"] = 1e-12

ts = np.linspace(0, 80, 101)
mz_t_j = []
be_t_b = []
sg_t_b = []

for psit in tebd.at_times(ts, tol=1e-3):
    mz_j = []
    be_b = []
    sg_b = []

    info = {"cur_orthog": None}
    mz_j += [psit.magnetization(0, info=info)]

    for j in range(1, L):
        mz_j += [psit.magnetization(j, info=info)]
        be_b += [psit.entropy(j, info=info)]
        sg_b += [psit.schmidt_gap(j, info=info)]

    mz_t_j += [mz_j]
    be_t_b += [be_b]
    sg_t_b += [sg_b]
```

### Tensor-network contraction with a cotengra optimizer

```python
import quimb.tensor as qtn
import cotengra as ctg

tn = qtn.TensorNetwork([...])

# inspect cost/memory of a chosen path first
width = tn.contraction_width(optimize='greedy')   # log2 max intermediate
cost  = tn.contraction_cost(optimize='greedy')    # FLOPs

# reusable hyper-optimizer (caches the path)
opt = ctg.ReusableHyperOptimizer(
    minimize="combo",
    max_repeats=128,
    reconf_opts={},
    progbar=False,
)
result = tn.contract(optimize=opt)
```

### Variational MPS (TNOptimizer) — minimize Heisenberg energy

```python
import quimb as qu
import quimb.tensor as qtn

psi = qtn.MPS_rand_state(L=64, bond_dim=16, cyclic=True)
ham = qtn.MPO_ham_heis(L=64, cyclic=True)

def norm_fn(psi):
    nfact = (psi.H @ psi) ** 0.5
    return psi.multiply(1 / nfact, spread_over="all")

def loss_fn(psi, ham):
    b, h, k = qtn.tensor_network_align(psi.H, ham, psi)
    energy_tn = b | h | k
    return energy_tn ^ ...

tnopt = qtn.TNOptimizer(
    psi, loss_fn=loss_fn, norm_fn=norm_fn,
    loss_constants={"ham": ham},
    optimizer="adam", autodiff_backend="jax",
)
psi_opt = tnopt.optimize(1000)
tnopt.plot()
```

### Quantum circuit simulation

```python
import quimb as qu
import quimb.tensor as qtn

circ = qtn.Circuit(N=10)
circ.apply_gate("H", 0)
for i in range(1, 10):
    circ.apply_gate("CX", 0, i)
circ.apply_gate("RZ", 1.234, 2)

amp = circ.amplitude("0" * 10)          # single amplitude
for b in circ.sample(10):               # sample bit strings
    print(b)

circ.local_expectation(qu.pauli("Z") & qu.pauli("Z"), where=(4, 5))
```

### 2D ground state via simple update (PEPS)

```python
import quimb as qu
import quimb.tensor as qtn

Lx, Ly = 4, 4
ham  = qtn.LocalHam2D(Lx, Ly, H2=qu.ham_heis(2))
psi0 = qtn.PEPS.rand(Lx, Ly, bond_dim=4, seed=666)

su = qtn.SimpleUpdate(psi0, ham, chi=32, compute_energy_every=10, keep_best=True)
for tau in [0.3, 0.1, 0.03, 0.01]:
    su.evolve(100, tau=tau)

psi_gs = su.best['state']
energy = su.best['energy'] / (Lx * Ly)
```

---

## Installation & backends

```bash
pip install quimb            # or: uv pip install quimb
conda install -c conda-forge quimb
pip install -U git+https://github.com/jcmgray/quimb.git   # latest
```

Optional dependencies:

| Package | Purpose |
|---|---|
| **cotengra** | Tensor-network contraction-path hyper-optimization (essential for large/2D TNs and circuits). |
| **kahypar** | Hypergraph partitioner used by cotengra for high-quality paths. |
| **opt_einsum** | Lower-level path finder (cotengra builds on it). |
| **slepc4py + petsc4py** | Fast distributed partial eigensolve / SVD / exponentiation for huge sparse matrices. |
| **mpi4py** (≥2.1) | MPI distributed compute (with the `'expm'`/`'slepc'` backends). |
| **autoray** | Backend-agnostic array dispatch — same TN code on NumPy / JAX / PyTorch / TensorFlow / CuPy. |
| **jax / torch / tensorflow** | Autodiff backends for `TNOptimizer`; GPU. |
| **cupy** | GPU arrays (drop-in via autoray). |
| **numba** | JIT acceleration of inner kernels. |
| **matplotlib, networkx, (pygraphviz)** | TN visualization (`.draw()`, tree plots). |

**autoray dispatch:** quimb never hardcodes NumPy — the array library is inferred from the tensor data type, so feeding JAX/CuPy/Torch arrays makes the whole tensor-network pipeline run on that backend (you can also pass `backend=` to `contract`).

---

## Pitfalls

- **Dense vs tensor-network path.** Dense `quimb` (`ham_heis`, `Evolution`, `eigh`) costs O(2ⁿ) memory — fine to ~20–22 spins for full ED, more with sparse partial eigensolves. Beyond that, switch to `quimb.tensor` (MPS/DMRG/TEBD/PEPS). Don't build a dense `2**n` operator when an MPO + DMRG would do.
- **Contraction path = memory, not just time.** For any non-trivial TN, check `contraction_width` (log2 of the largest intermediate → RAM) *before* contracting. A bad path can need terabytes; a good cotengra path can make the same contraction feasible. Use `ReusableHyperOptimizer` when contracting many same-shaped networks so the expensive path search is paid once.
- **`optimize='optimal'` only for tiny TNs** — it is exponential in the number of tensors. Use `'auto'`/`'greedy'`/cotengra for anything real.
- **Backend gotchas (autoray).** Mixing NumPy and JAX/CuPy arrays in one TN can trigger silent host↔device copies or errors. Keep a TN on one backend. JAX needs `float64` enabled (`jax.config.update("jax_enable_x64", True)`) for physics-grade precision. Autodiff in `TNOptimizer` requires a differentiable backend (`jax`/`torch`/`tensorflow`/`autograd`), not plain NumPy.
- **DMRG/TEBD truncation.** Bond-dimension schedule (`bond_dims`) and `cutoffs` set accuracy; too-small bonds give variationally-high energies. For TEBD, `split_opts["cutoff"]` plus the Trotter step `dt`/`tol` control the error — sweep both.
- **MPS `.gate` mode matters.** `contract='swap+split'` keeps exact MPS structure (best for canonical algorithms); `True` (eager) grows tensor rank; `'lazy'` defers contraction. Pick deliberately.
- **Random seeds & threads.** `seed=` makes dense random objects reproducible only at fixed thread count unless `OMP_NUM_THREADS` is pinned.
- **Large sparse eigensolves.** Install `slepc4py`/`petsc4py` and use `backend='slepc'`; interior eigenvalues (`sigma=`) need shift-invert and are much harder than extremal ones.

---

## Source links

- Docs home / TOC: https://quimb.readthedocs.io/en/latest/
- Installation: https://quimb.readthedocs.io/en/latest/installation.html
- Matrix (dense) — Basics: https://quimb.readthedocs.io/en/latest/matrix/matrix-basics.html
- Matrix — Generating objects: https://quimb.readthedocs.io/en/latest/matrix/matrix-generate.html
- Matrix — Calculating quantities: https://quimb.readthedocs.io/en/latest/matrix/matrix-calculating%20quantities.html
- Matrix — Linear algebra / eigensolve: https://quimb.readthedocs.io/en/latest/matrix/matrix-solving%20systems.html
- Matrix — Dynamics & evolution: https://quimb.readthedocs.io/en/latest/matrix/matrix-dynamics%20and%20evolution.html
- Tensor — Basics: https://quimb.readthedocs.io/en/latest/tensor/tensor-basics.html
- Tensor — Contraction: https://quimb.readthedocs.io/en/latest/tensor/tensor-contraction.html
- Tensor — Optimization: https://quimb.readthedocs.io/en/latest/tensor/tensor-optimization.html
- Tensor — 1D algorithms (MPS/MPO/DMRG/TEBD): https://quimb.readthedocs.io/en/latest/tensor/tensor-1d.html
- Tensor — 2D algorithms / PEPS: https://quimb.readthedocs.io/en/latest/tensor/tensor-2d.html
- Tensor — Quantum circuits: https://quimb.readthedocs.io/en/latest/tensor/tensor-circuit.html
- Example — Periodic DMRG: https://quimb.readthedocs.io/en/latest/examples/ex_dmrg_periodic.html
- Example — TEBD evolution: https://quimb.readthedocs.io/en/latest/examples/ex_TEBD_evo.html
- API reference (autoapi): https://quimb.readthedocs.io/en/latest/autoapi/index.html
- Source: https://github.com/jcmgray/quimb
- JOSS paper (Gray 2018): https://doi.org/10.21105/JOSS.00819
