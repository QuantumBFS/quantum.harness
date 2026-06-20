# NetKet API + Examples Reference

NetKet is a Python library for **machine-learning-driven quantum many-body physics**, built on
**JAX** (autodiff + JIT + GPU/TPU). Its core job is **Variational Monte Carlo (VMC) with
neural-network wavefunctions (neural quantum states, NQS)**: you define a lattice Hilbert space and a
Hamiltonian, pick a variational ansatz (RBM, CNN, GCNN, autoregressive net, …), sample
configurations with a Markov-chain sampler, and minimize the energy with a gradient optimizer
(usually + Stochastic Reconfiguration / natural gradient). It also covers excited states, finite-T,
steady states of open systems, real/imaginary-time dynamics, and continuous-space (first-quantized)
problems.

Everything is exposed under the top-level alias `import netket as nk`. Models are Flax modules
(either `flax.linen` or the newer `flax.nnx`); optimizers wrap **optax**.

- Docs index: <https://netket.readthedocs.io/en/stable/>
- Getting-started tutorial (used for the worked examples below): <https://netket.readthedocs.io/en/stable/tutorials/gs-ising.html>
- Project site: <https://www.netket.org>

---

## 1. Hilbert spaces — `nk.hilbert`

The Hilbert space defines the local degrees of freedom and the number of sites. It is required by
operators, samplers, and variational states.

| Class | Purpose | Key constructor args |
|---|---|---|
| `nk.hilbert.Spin(s, N, *, total_sz=None, ...)` | Tensor product of N spin-`s` sites. | `s` (e.g. `1/2`, `1`), `N` (#sites), `total_sz` (fix magnetization sector) |
| `nk.hilbert.Fock(n_max=None, N=1, n_particles=None)` | N bosonic modes, each with occupations `0..n_max`. | `n_max` (max occupation), `N`, `n_particles` (fix total particle number) |
| `nk.hilbert.Qubit(N)` | N qubits (= Spin-½ relabeled 0/1). | `N` |
| `nk.hilbert.TensorHilbert(*spaces)` | Tensor product of heterogeneous sub-spaces. | the sub-spaces |
| `nk.hilbert.SpinOrbitalFermions(n_orbitals, s=None, n_fermions=None)` | 2nd-quantized fermions with spin `s` over `n_orbitals`. | `n_orbitals`, `s`, `n_fermions` |
| `nk.hilbert.Particle(...)` *(experimental)* | N particles in continuous space (with/without PBC). | particle count, geometry |

Common members (all discrete Hilbert spaces):

- `hi.size` — number of sites/DoF.
- `hi.n_states` — total Hilbert-space dimension (only for finite spaces; the quantity ED scales with).
- `hi.all_states()` — enumerate every basis configuration (array of shape `(n_states, size)`).
- `hi.random_state(key, n)` — `n` random basis configurations from a JAX PRNG key.
- Hilbert spaces compose with `*` (tensor product) and `**` (power): `nk.hilbert.Spin(1/2)**10`.

```python
import netket as nk
import jax

N = 20
hi = nk.hilbert.Spin(s=1/2, N=N)
hi.random_state(jax.random.key(0), 3)   # 3 random spin configs
```

---

## 2. Graphs / lattices — `nk.graph`

A graph supplies lattice connectivity (edges) for graph-based operators (`Ising`, `Heisenberg`) and
the symmetry groups used by symmetric ansätze.

| Class | Purpose | Key constructor args |
|---|---|---|
| `nk.graph.Chain(length, *, pbc=True)` | 1D chain. | `length`, `pbc` |
| `nk.graph.Hypercube(length, n_dim=1, pbc=True)` | Hypercubic lattice, same `length` on every axis. | `length`, `n_dim`, `pbc` |
| `nk.graph.Grid(extent, *, pbc=True)` | Hypercubic lattice with per-axis extents, e.g. `[4, 6]`. | `extent` (list), `pbc` |
| `nk.graph.Square(length, *, pbc=True)` | 2D square lattice. | `length`, `pbc` |
| `nk.graph.Cube(length, *, pbc=True)` | 3D cubic lattice. | `length`, `pbc` |
| `nk.graph.Triangular(extent, *, pbc=True)` | Triangular lattice. | `extent` |
| `nk.graph.Honeycomb(extent, *, pbc=True)` | Honeycomb lattice (2-site basis). | `extent` |
| `nk.graph.Kagome(extent, *, pbc=True)` | Kagome lattice. | `extent` |
| `nk.graph.Pyrochlore(extent, *, pbc=True)` | Pyrochlore lattice. | `extent` |
| `nk.graph.BCC / FCC / Diamond(extent, ...)` | Body-/face-centered cubic, diamond. | `extent` |
| `nk.graph.Lattice(basis_vectors, site_offsets, extent, pbc, ...)` | General Bravais lattice from a unit cell. | basis vectors, offsets, extent |
| `nk.graph.Graph(edges=...)` | Arbitrary graph from an edge list. | `edges` |
| `nk.graph.Edgeless(n_nodes)` | N disconnected vertices (no couplings). | `n_nodes` |
| `nk.graph.DoubledGraph(graph)` | Doubled graph for density-matrix / open-system Hilbert spaces. | `graph` |

Common members:

- `g.n_nodes` — number of sites (use as `N` for the Hilbert space).
- `g.edges()` — list of `(i, j)` site pairs (the bonds).
- `g.translation_group()` — translation symmetry group (feed to `DenseSymm`/`GCNN`/`RBMSymm`).
- `g.automorphisms()` — full graph-automorphism group.
- `g.space_group()` — space group (lattices only).

```python
graph = nk.graph.Chain(length=N, pbc=True)
graph.translation_group()           # translations for symmetric ansätze
graph.edges()                       # bonds, e.g. for correlation operators
```

---

## 3. Operators — `nk.operator`

Operators represent Hamiltonians and observables. NetKet ships JAX-backed (`...Jax`) and Numba
(`...Numba`) backends; the plain names (`Ising`, `Heisenberg`, `LocalOperator`, `PauliStrings`,
`BoseHubbard`) dispatch to a sensible default (JAX). For VMC you mostly want the JAX backend.

### 3.1 Predefined Hamiltonians

**Transverse-field Ising** — `nk.operator.Ising(hilbert, graph, h, J=1.0, dtype=None)`

Convention (verbatim from docs):

> H = −h Σᵢ σᵢˣ + J Σ⟨i,j⟩ σᵢᶻ σⱼᶻ

i.e. **negative** sign on the transverse field `h`, **positive** sign on the `J` coupling, summed over
graph edges `⟨i,j⟩`.

```python
H = nk.operator.Ising(hilbert=hi, graph=graph, h=1.0, J=1.0)
```

**Heisenberg** — `nk.operator.Heisenberg(hilbert, graph, J=1.0, sign_rule=None, dtype=None, *, acting_on_subspace=None)`

- `J` — coupling; a float, or a sequence of floats for multi-colored graphs (e.g. J₁–J₂).
- `sign_rule` — apply Marshall's sign rule; **defaults to `True` on bipartite lattices, `False`
  otherwise**. This rotates the sign of the off-diagonal terms (helps sign-positive ansätze); be
  explicit when reproducing a paper.
- `acting_on_subspace` — map graph nodes onto a subset of Hilbert sites.

```python
H = nk.operator.Heisenberg(hilbert=hi, graph=graph, J=1.0)
```

**Bose-Hubbard** — `nk.operator.BoseHubbard(hilbert, graph, U, J=1.0, V=0.0, mu=0.0)` — bosonic
hopping `J`, on-site `U`, nearest-neighbor `V`, chemical potential `mu` (needs a `Fock` Hilbert space).

**Fermi-Hubbard / fermions** — `nk.operator.FermiHubbardJax(...)`, `nk.operator.FermionOperator2nd(...)`
for second-quantized fermionic Hamiltonians (needs `SpinOrbitalFermions`).

### 3.2 Single-site building blocks

Build any Hamiltonian by summing local operators. Import from the submodules:

```python
from netket.operator.spin import sigmax, sigmay, sigmaz, sigmap, sigmam   # sigmap=σ⁺, sigmam=σ⁻
from netket.operator.boson import create, destroy, number, proj
```

Each takes `(hilbert, site)`: e.g. `sigmaz(hi, 3)`. Compose with `+`, `-`, scalar `*`, and `@`
(operator product on the same Hilbert space). This is the canonical "custom Hamiltonian" path:

```python
Gamma = -1
H = sum([Gamma * sigmax(hi, i) for i in range(N)])
V = -1
H += sum([V * sigmaz(hi, i) @ sigmaz(hi, (i + 1) % N) for i in range(N)])   # PBC Ising, by hand
```

### 3.3 `LocalOperator`

`nk.operator.LocalOperator(hilbert, operators=[], acting_on=[], constant=0.0, dtype=None)` — a sum of
dense matrices acting on small subsets of sites. The result of summing `sigmax`/`sigmaz`/… terms *is*
a `LocalOperator`. You can also pass explicit matrices:

```python
import numpy as np
# σ_z on site 2 via an explicit 2x2 matrix
op = nk.operator.LocalOperator(hi, operators=np.array([[1, 0], [0, -1]]), acting_on=[2])
```

### 3.4 `PauliStrings`

`nk.operator.PauliStrings(hilbert, operators, weights, *, cutoff=1e-10, dtype=None)` — build a
Hamiltonian directly from Pauli-string labels and coefficients. `operators` is a list of strings over
`{"I","X","Y","Z"}` (one char per site), `weights` the matching coefficients.

```python
# 0.3 * X0 X1  +  0.5 * Z0 Y1   on a 2-qubit space
hi2 = nk.hilbert.Qubit(N=2)
H = nk.operator.PauliStrings(hi2, ["XX", "ZY"], [0.3, 0.5])
```

### 3.5 Converting / inspecting operators

- `H.to_sparse()` — SciPy sparse matrix (use for small-size exact diagonalization cross-checks).
- `H.to_dense()` — dense NumPy array (tiny systems only).
- `H @ psi` — apply to a state vector; combine with `scipy.sparse.linalg.eigsh` for ED reference:

```python
from scipy.sparse.linalg import eigsh
sp_h = H.to_sparse()                 # shape (2**N, 2**N)
eig_vals, eig_vecs = eigsh(sp_h, k=2, which="SA")
E_gs = eig_vals[0]
```

---

## 4. Ansätze / models — `nk.models`

Models are **Flax modules** that map a batch of configurations `x` (shape `(..., N)`) to **log-amplitudes**
`log ψ(x)` (a scalar per sample). Most accept a `param_dtype` to choose real vs complex parameters.

| Model | Purpose | Key args |
|---|---|---|
| `nk.models.RBM` | Restricted Boltzmann Machine; the default workhorse NQS. | `alpha` (hidden-unit density = hidden/visible), `param_dtype`, `use_hidden_bias`, `use_visible_bias`, `activation` |
| `nk.models.RBMModPhase` | RBM with **real** params encoding modulus + phase separately. | `alpha`, `param_dtype` |
| `nk.models.RBMSymm` | Symmetrized RBM over a symmetry group (uses `DenseSymm`). | `symmetries`, `alpha`, `param_dtype` |
| `nk.models.RBMMultiVal` | RBM for large local Hilbert spaces (multi-valued sites). | `alpha`, `n_classes` |
| `nk.models.Jastrow` | Pairwise Jastrow `ψ(s)=exp(Σ_{i≠j} sᵢ Wᵢⱼ sⱼ)`. | `param_dtype` |
| `nk.models.MLP` | Multi-layer perceptron. | `hidden_dims`, `param_dtype`, `activation` |
| `nk.models.GCNN` | Group-CNN; output invariant/equivariant under a symmetry group — strong for frustrated 2D. | `symmetries`, `layers`, `features`, `param_dtype` |
| `nk.models.DeepSetMLP` | Permutation-invariant (DeepSets) architecture. | `features` |
| `nk.models.NDM` | Neural density matrix (mixed states / open systems). | — |
| `nk.models.Slater2nd` | Slater determinant for fermionic 2nd-quantization. | orbitals |
| `nk.models.LogStateVector` | Stores the **full** log-wavefunction exactly (tiny systems / debugging). | `hilbert` |
| Autoregressive: `nk.models.ARNNDense`, `FastARNNConv1D`, `ARNNConv2D`, … | Normalized autoregressive NQS → use with `ARDirectSampler` for i.i.d. sampling (no autocorrelation). | `layers`, `features` |
| RNN (experimental): `LSTMNet`, `FastLSTMNet`, `GRUNet1D` | Recurrent autoregressive ansätze. | — |

```python
model = nk.models.RBM(alpha=4, param_dtype=complex)   # 4× hidden units, complex amplitudes
```

Symmetric layers live in `nk.nn`: `nk.nn.DenseSymm(symmetries=graph.translation_group(), features=...)`
and `nk.nn.DenseEquivariant(...)` are the building blocks behind `RBMSymm`/`GCNN`. You can also write
your **own** Flax module (linen or nnx); it just needs `__call__(x) -> log ψ`.

---

## 5. Samplers — `nk.sampler`

Samplers draw configurations distributed as `|ψ(x)|²`. Most are Metropolis-Hastings with different
proposal rules. `n_chains` controls the number of parallel Markov chains; `sweep_size` controls the
number of proposed moves between recorded samples (decorrelation).

| Sampler | Purpose | Key args |
|---|---|---|
| `nk.sampler.MetropolisLocal(hilbert, *, n_chains=16, sweep_size=None, ...)` | Flip one local DoF per move. General-purpose default. | `n_chains`, `n_chains_per_rank`, `sweep_size`, `dtype` |
| `nk.sampler.MetropolisExchange(hilbert, *, graph, d_max=1, n_chains=16, ...)` | Swap two sites along bonds — **conserves magnetization / particle number**. Use in fixed-`total_sz` sectors. | `graph`, `d_max`, `n_chains` |
| `nk.sampler.MetropolisHamiltonian(hilbert, *, hamiltonian, n_chains=16)` | Propose moves from the Hamiltonian's off-diagonal connections. | `hamiltonian`, `n_chains` |
| `nk.sampler.MetropolisGaussian(hilbert, *, sigma, n_chains)` | Continuous-space Gaussian proposal on all particle positions. | `sigma`, `n_chains` |
| `nk.sampler.MetropolisAdjustedLangevin(hilbert, *, dt, n_chains)` | Langevin (gradient-informed) proposal for continuous space. | `dt`, `n_chains` |
| `nk.sampler.ExactSampler(hilbert)` | Exact i.i.d. samples by enumerating `|ψ|²` (small systems only). | `hilbert` |
| `nk.sampler.ARDirectSampler(hilbert)` | Direct, autocorrelation-free sampling for autoregressive models. | `hilbert` |

Transition rules can be composed manually with `nk.sampler.MetropolisSampler(hilbert, rule, ...)`
using `nk.sampler.rules.LocalRule()`, `ExchangeRule(graph)`, `HamiltonianRule(op)`, etc.

```python
sampler = nk.sampler.MetropolisLocal(hi, n_chains=16)
# magnetization-conserving alternative for a fixed total_sz sector:
# sampler = nk.sampler.MetropolisExchange(hi, graph=graph, d_max=2, n_chains=16)
```

Numba variants (`MetropolisLocalNumba`, …) exist but convert numpy↔jax each step — avoid on GPU.

---

## 6. Variational states — `nk.vqs`

The variational state ties together (sampler, model, #samples) and is what you call `.expect()` on.

**Monte-Carlo state**

```python
nk.vqs.MCState(
    sampler,                 # an nk.sampler.*
    model,                   # a Flax module (RBM, GCNN, custom, ...)
    *,
    n_samples=1008,          # total MC samples per expectation (rounded to a multiple of n_chains)
    n_samples_per_rank=None, # alternatively set per-MPI/JAX-rank count
    n_discard_per_chain=None,# burn-in samples discarded per chain (default: ~sweep)
    chunk_size=None,         # split the sample batch into chunks of this size to cap memory
    seed=None,               # PRNG seed for parameter init
    sampler_seed=None,       # PRNG seed for the sampler chains
    variables=None,          # provide pre-existing parameters
)
```

Key knobs:

- `vstate.n_samples` — settable after construction; raise it for low-variance observable measurements.
- `vstate.n_samples_per_chain` / `n_chains` — derived from `sampler.n_chains` and `n_samples`.
- `vstate.chunk_size` — caps peak memory (samples processed `chunk_size` at a time); essential for large
  models / many samples on GPU. Does not change results, only memory/speed.
- `vstate.parameters`, `vstate.n_parameters` — the trainable params and their count.
- `vstate.init_parameters()` — re-initialize parameters.

**Full-summation state** (no sampling; sums over the whole Hilbert space — exact, small systems only):

```python
nk.vqs.FullSumState(hilbert, model, *, seed=None, chunk_size=None)
```

**Computing expectation values & gradients**

```python
E = vstate.expect(H)                       # Stats object
E.mean            # ⟨H⟩  (complex)
E.error_of_mean   # statistical error bar on the mean
E.variance        # sample variance of the local energy
E.R_hat           # Gelman-Rubin split-R̂ convergence indicator (want ≈ 1)
E.tau_corr        # integrated autocorrelation time

E, E_grad = vstate.expect_and_grad(H)      # energy + parameter gradient (PyTree)
```

```python
vstate = nk.vqs.MCState(sampler, model, n_samples=512)
E = vstate.expect(H)
print("Mean:", E.mean, "Error:", E.error_of_mean, "Variance:", E.variance, "R_hat:", E.R_hat)
```

---

## 7. Optimizers & Stochastic Reconfiguration — `nk.optimizer`

Optimizers wrap **optax** (capitalized names, NetKet argument order).

| Optimizer | Args |
|---|---|
| `nk.optimizer.Sgd(learning_rate)` | plain SGD |
| `nk.optimizer.Adam(learning_rate, b1=0.9, b2=0.999)` | Adam |
| `nk.optimizer.Momentum(learning_rate, beta=0.9)` | momentum SGD |
| `nk.optimizer.RmsProp(learning_rate, ...)` | RMSProp |
| `nk.optimizer.AdaGrad(learning_rate)` | AdaGrad |

**Stochastic Reconfiguration (natural gradient)** — almost always improves NQS convergence:

```python
nk.optimizer.SR(
    qgt=None,            # which QGT implementation (default: QGTAuto)
    *,
    diag_shift=0.01,     # regularization added to the QGT diagonal (the key stability knob)
    diag_scale=None,     # scale-relative shift (shift ∝ diagonal), often better than a flat shift
    solver=...,          # linear solver, e.g. nk.optimizer.solver.cholesky / svd / pinv_smooth
    holomorphic=False,   # set True only for genuinely holomorphic complex ansätze
)
```

Quantum Geometric Tensor (the metric SR inverts) — pick automatically or override:

- `nk.optimizer.qgt.QGTAuto` — auto-select the best representation (default).
- `nk.optimizer.qgt.QGTJacobianPyTree` — Jacobian stored as a PyTree (semi-lazy).
- `nk.optimizer.qgt.QGTJacobianDense` — dense Jacobian (fast for moderate #params).
- `nk.optimizer.qgt.QGTOnTheFly` — matrix-free (forward/backward AD); best when #params is huge.

Solvers (`nk.optimizer.solver.*`): `cholesky`, `cholesky_with_fallback`, `LU`, `svd`, `pinv`,
`pinv_smooth`, `cg`, `solve`.

```python
optimizer = nk.optimizer.Sgd(learning_rate=0.01)
sr = nk.optimizer.SR(diag_shift=0.1)
```

---

## 8. Drivers & the run loop — `nk.driver`

| Driver | Purpose | Key args |
|---|---|---|
| `nk.driver.VMC(hamiltonian, optimizer, *, variational_state, preconditioner=None)` | Ground-state energy minimization by VMC. | pass `preconditioner=SR(...)` for natural gradient |
| `nk.driver.VMC_SR(hamiltonian, optimizer, *, variational_state, diag_shift=..., ...)` | VMC with built-in SR / minSR ("kernel-trick") — recommended for large param counts. | `diag_shift` |
| `nk.driver.SteadyState(lindbladian, optimizer, *, variational_state, preconditioner=None)` | Steady state of an open system (minimizes L†L). | — |

Top-level alias: `nk.VMC == nk.driver.VMC`.

**`.run()` signature**

```python
driver.run(
    n_iter,              # number of optimization steps
    out=None,            # logger(s): a filename prefix, an nk.logging.* object, or a tuple of them
    obs=None,            # dict {name: operator} of extra observables logged each step
    step_size=1,         # log every step_size iterations
    show_progress=True,  # tqdm progress bar
    callback=None,       # callable(step, logdata, driver) -> bool; return False to stop early
)
```

```python
gs = nk.VMC(H, optimizer, variational_state=vstate, preconditioner=sr)
log = nk.logging.RuntimeLog()
gs.run(n_iter=300, out=log, obs={"Sx": Sx_operator})
```

---

## 9. Loggers — `nk.logging`

Pass via `out=` to `.run()`.

| Logger | Purpose | Key args |
|---|---|---|
| `nk.logging.RuntimeLog()` | Keep history in memory; read via `log.data["Energy"]`. | — |
| `nk.logging.JsonLog(output_prefix, save_params_every=50, write_every=50)` | Write metrics to `<prefix>.log` (JSON) + params to `<prefix>.mpack`. | `output_prefix`, `save_params_every`, `write_every` |
| `nk.logging.TensorBoardLog(path)` | Live TensorBoard logging. | `path` |
| `nk.logging.StateLog(...)` | Serialize the variational-state variables during the run. | — |
| `nk.logging.HDF5Log(path)` | Write outputs to HDF5. | `path` |

Passing a **string** to `out=` is shorthand for `JsonLog(that_string)`.

Reading logged data:

```python
log = nk.logging.RuntimeLog()
gs.run(n_iter=300, out=log)
data = log.data
data["Energy"].iters      # iteration indices
data["Energy"].Mean       # mean energy per iteration
data["Energy"].Sigma      # error bar per iteration

# from a JsonLog file:
import json
d = json.load(open("output.log"))
energy   = d["Energy"]["Mean"][-1]
variance = d["Energy"]["Variance"][-1]
```

---

## 10. Worked examples (verbatim from the official getting-started tutorial)

Source: <https://netket.readthedocs.io/en/stable/tutorials/gs-ising.html>

### 10.1 Setup: Hilbert space, lattice, transverse-field Ising Hamiltonian (built by hand)

```python
import netket as nk
import jax
import jax.numpy as jnp

N = 20
hi = nk.hilbert.Spin(s=1 / 2, N=N)

graph = nk.graph.Chain(length=N, pbc=True)

from netket.operator.spin import sigmax, sigmaz

Gamma = -1
H = sum([Gamma * sigmax(hi, i) for i in range(N)])

V = -1
H += sum([V * sigmaz(hi, i) @ sigmaz(hi, (i + 1) % N) for i in range(N)])
```

### 10.2 Exact-diagonalization reference (small-size cross-check)

```python
sp_h = H.to_sparse()
sp_h.shape  # (1048576, 1048576)

from scipy.sparse.linalg import eigsh
eig_vals, eig_vecs = eigsh(sp_h, k=2, which="SA")
E_gs = eig_vals[0]
```

### 10.3 Variational state + expectation values (here with a tiny mean-field model)

```python
sampler = nk.sampler.MetropolisLocal(hi)
vstate = nk.vqs.MCState(sampler, mf_model, n_samples=512)

E = vstate.expect(H)
print("Mean                  :", E.mean)
print("Error                 :", E.error_of_mean)
print("Variance              :", E.variance)
print("Convergence indicator :", E.R_hat)
print("Correlation time      :", E.tau_corr)

vstate.expect_and_grad(H)
```

### 10.4 Full VMC run with a driver (SGD), then check vs ED

```python
vstate.init_parameters()

optimizer = nk.optimizer.Sgd(learning_rate=0.05)

gs = nk.driver.VMC(H, optimizer, variational_state=vstate)

gs.run(n_iter=300)

mf_energy = vstate.expect(H)
error = abs((mf_energy.mean - eig_vals[0]) / eig_vals[0])
print("Optimized energy and relative error: ", mf_energy, error)
```

### 10.5 Adding Stochastic Reconfiguration + a logger (more expressive ansatz)

```python
model = JasShort(rngs=nnx.Rngs(1))                 # a short-range Jastrow ansatz
vstate = nk.vqs.MCState(sampler, model, n_samples=1008)

optimizer = nk.optimizer.Sgd(learning_rate=0.01)

gs = nk.driver.VMC(
    H,
    optimizer,
    variational_state=vstate,
    preconditioner=nk.optimizer.SR(diag_shift=0.1),
)

log = nk.logging.RuntimeLog()
gs.run(n_iter=300, out=log)

jas_energy = vstate.expect(H)
error = abs((jas_energy.mean - eig_vals[0]) / eig_vals[0])
print(f"Optimized energy : {jas_energy}")
print(f"relative error   : {error}")
```

Reading & plotting the logged trajectory:

```python
data_jastrow = log.data

from matplotlib import pyplot as plt
plt.errorbar(
    data_jastrow["Energy"].iters,
    data_jastrow["Energy"].Mean,
    yerr=data_jastrow["Energy"].Sigma,
)
plt.xlabel("Iterations")
plt.ylabel("Energy")
```

### 10.6 A symmetry-equivariant ansatz (translation symmetry via `DenseSymm`)

```python
import flax.linen as nn
import netket.nn as nknn
from flax import nnx

class SymmModel(nnx.Module):
    def __init__(self, N: int, alpha: int = 1, *, rngs: nnx.Rngs):
        self.alpha = alpha
        dense_symm_linen = nknn.DenseSymm(
            symmetries=graph.translation_group(),
            features=alpha,
            kernel_init=nn.initializers.normal(stddev=0.01),
        )
        self.linear_symm = nnx.bridge.ToNNX(dense_symm_linen, rngs=rngs).lazy_init(
            jnp.ones((1, 1, N))
        )

    def __call__(self, x: jax.Array):
        x = x.reshape(-1, 1, x.shape[-1])
        x = self.linear_symm(x)
        x = nnx.relu(x)
        return jnp.sum(x, axis=(-1, -2))

model = SymmModel(N=N, alpha=4, rngs=nnx.Rngs(2))
vstate = nk.vqs.MCState(sampler, model, n_samples=1008)
vstate.n_parameters  # 84  (parameter count reduced by enforcing symmetry)

optimizer = nk.optimizer.Sgd(learning_rate=0.1)
gs = nk.driver.VMC(
    H,
    optimizer,
    variational_state=vstate,
    preconditioner=nk.optimizer.SR(diag_shift=0.1),
)
log = nk.logging.RuntimeLog()
gs.run(n_iter=600, out=log)
```

(For production 2D frustrated problems use `nk.models.GCNN(symmetries=graph.space_group(), ...)` —
same idea, deeper group-equivariant network.)

### 10.7 Measuring an additional observable (correlation function), with more samples

```python
corr = sum([sigmax(hi, i) @ sigmax(hi, j) for (i, j) in graph.edges()])

vstate.n_samples = 400000        # raise samples for a low-error measurement
vstate.expect(corr)

psi = eig_vecs[:, 0]
exact_corr = psi @ (corr @ psi)  # ED cross-check
print(exact_corr)
```

### 10.8 Using a predefined Hamiltonian instead of building by hand

The hand-built Ising above is equivalent (up to the stated sign convention) to:

```python
H = nk.operator.Ising(hilbert=hi, graph=graph, h=1.0, J=1.0)   # H = -h Σσˣ + J Σσᶻσᶻ
# Heisenberg ground-state skeleton:
H = nk.operator.Heisenberg(hilbert=hi, graph=graph, J=1.0)
model = nk.models.RBM(alpha=4, param_dtype=complex)
sampler = nk.sampler.MetropolisExchange(hi, graph=graph, n_chains=16)  # conserves total Sz
vstate = nk.vqs.MCState(sampler, model, n_samples=4096, chunk_size=4096)
gs = nk.VMC(H, nk.optimizer.Sgd(0.01), variational_state=vstate,
            preconditioner=nk.optimizer.SR(diag_shift=0.01))
gs.run(n_iter=300, out="heisenberg")
```

---

## 11. Pitfalls

- **`n_samples` vs `n_chains`.** `n_samples` is the *total* MC budget per expectation; `n_chains`
  (set on the sampler) is how many parallel chains produce it. NetKet rounds `n_samples` up to a
  multiple of `n_chains`. More chains ⇒ better parallelism and a meaningful `R_hat`, but each chain
  contributes fewer (more correlated) samples. Watch `E.R_hat` (want ≈ 1) and `E.tau_corr`.

- **SR regularization (`diag_shift`).** The QGT is often near-singular; `diag_shift` (e.g. `0.01–0.1`)
  is added to its diagonal so the linear solve is stable. Too small → noisy/unstable updates; too
  large → SR degrades toward plain gradient descent. A common recipe is to start larger and **anneal
  it down** during training, or use `diag_scale` (a shift proportional to the diagonal) instead of a
  flat shift.

- **`chunk_size` for memory.** With large models or large `n_samples`, the forward/backward pass and
  the QGT can blow up GPU memory. Set `vstate.chunk_size` (e.g. `=n_chains` or a few thousand) to
  process samples in chunks — same numerical result, lower peak memory, slightly more overhead.

- **Complex vs real parameters.** Ground states generally need complex amplitudes/phases. Use
  `param_dtype=complex` (e.g. `nk.models.RBM(alpha=4, param_dtype=complex)`), or an ansatz that
  encodes a phase (`RBMModPhase`). Real-only params silently restrict you to a positive (Marshall-sign)
  wavefunction — fine for unfrustrated bipartite Heisenberg with `sign_rule=True`, wrong otherwise.
  `holomorphic=True` in `SR` is only valid for genuinely holomorphic complex models.

- **JAX 64-bit precision.** JAX defaults to **float32/complex64**. For accurate energies enable double
  precision *before any array is created*:
  ```python
  import netket as nk
  nk.config.netket_enable_x64 = True     # or set env NETKET_ENABLE_X64=1
  # equivalently: from jax import config; config.update("jax_enable_x64", True)
  ```
  Set this at the very top of the script.

- **Sampler ↔ conservation law.** In a fixed-magnetization / fixed-particle sector
  (`Spin(..., total_sz=0)`, `Fock(..., n_particles=...)`), use `MetropolisExchange` (or a Hilbert-aware
  rule), **not** `MetropolisLocal` — local flips break the conserved quantity and leave the sector.

- **`Heisenberg` `sign_rule` default flips with bipartiteness.** It defaults to `True` on bipartite
  lattices and `False` otherwise; this changes off-diagonal signs and therefore which ansätze converge.
  Set it explicitly when matching a reference.

- **Numba vs JAX backends.** Plain names default to JAX. The `...Numba` operator/sampler variants
  convert numpy↔jax every step and are slow on GPU — avoid them in JAX/GPU workflows.

---

## 12. Source links

- Docs index — <https://netket.readthedocs.io/en/stable/>
- Install — <https://netket.readthedocs.io/en/stable/docs/install.html>
- Getting-started / ground-state Ising tutorial — <https://netket.readthedocs.io/en/stable/tutorials/gs-ising.html>
- Hilbert API — <https://netket.readthedocs.io/en/stable/api/hilbert.html>
- Graph API — <https://netket.readthedocs.io/en/stable/api/graph.html>
- Operator API — <https://netket.readthedocs.io/en/stable/api/operator.html>
- Models API — <https://netket.readthedocs.io/en/stable/api/models.html>
- Sampler API — <https://netket.readthedocs.io/en/stable/api/sampler.html>
- Variational-state (vqs) API — <https://netket.readthedocs.io/en/stable/api/vqs.html>
- Optimizer / SR / QGT API — <https://netket.readthedocs.io/en/stable/api/optimizer.html>
- Driver API — <https://netket.readthedocs.io/en/stable/api/drivers.html>
- Logging API — <https://netket.readthedocs.io/en/stable/api/logging.html>
- `Heisenberg` reference — <https://netket.readthedocs.io/en/stable/api/_generated/operator/netket.operator.Heisenberg.html>
- Examples (GitHub) — <https://github.com/netket/netket/tree/master/Examples>
