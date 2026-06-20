# TensorCircuit-NG — API + Examples Reference

Differentiable, JIT-compilable, **tensor-network-based** quantum circuit simulator for
variational quantum algorithms (VQE/QAOA/QML), noisy simulation, and large-scale circuits.
Built on top of JAX / TensorFlow / PyTorch (and NumPy for debugging), so circuits compose
with autodiff (`grad`/`value_and_grad`), `jit`, and `vmap` exactly like ordinary ML code.
Simulation modes: ideal (`Circuit`), noisy density-matrix (`DMCircuit`), approximate MPS
(`MPSCircuit`), plus Clifford/qudit/analog/symmetric/fermionic variants.

- Import name is `tensorcircuit` (PyPI package `tensorcircuit-ng`): `import tensorcircuit as tc`.
- The backend object is `tc.backend` (commonly aliased `K = tc.set_backend("jax")`); it exposes
  a full ML-framework API (`K.real`, `K.ones`, `K.jit`, `K.grad`, `K.value_and_grad`, `K.vmap`, …).
- TensorCircuit-NG is a drop-in replacement for the original TensorCircuit (same `tensorcircuit` namespace).

Whitepaper / refs: arXiv:2205.10091 (original), arXiv:2602.14167 (NG). See **Source links** at the end.

---

## 1. Backend, dtype, and contractor setup

**Set these BEFORE building any circuit** — backend and dtype are global numerical state.

```python
import tensorcircuit as tc

K = tc.set_backend("jax")        # "jax" | "tensorflow" | "pytorch" | "numpy"
tc.set_dtype("complex128")        # "complex64" (default) | "complex128"
tc.set_contractor("greedy")       # "greedy" (default) | "cotengra" | "custom" | "auto" ...
```

| Call | Purpose |
|---|---|
| `tc.set_backend(name) -> K` | Choose autodiff/array backend; returns the backend object `K` (also `tc.backend`). |
| `tc.set_dtype("complex64" \| "complex128")` | Global precision. `complex64`→`float32`/`int32`, `complex128`→`float64`. |
| `tc.set_contractor(name, optimizer=..., preprocessing=...)` | Tensor-network contraction-path strategy. `preprocessing=True` fuses 1-qubit gates into entanglers. |
| `tc.get_backend("pytorch")` | Get a backend object without making it global. |
| `tc.about()` | Print version/backend/dtype diagnostics. |

Dtype string globals: `tc.dtypestr` (e.g. `"complex64"`), `tc.rdtypestr` (real), `tc.idtypestr` (int).

**Scoped overrides** (do not touch global state):

```python
with tc.runtime_backend("tensorflow"):
    with tc.runtime_dtype("complex128"):
        m = tc.backend.eye(2)

@tc.set_function_backend("tensorflow")
@tc.set_function_dtype("complex128")
def f():
    return tc.backend.eye(2)
```

**Cotengra contractor** for large/deep circuits (path search separate from execution time):

```python
import cotengra as ctg
optr = ctg.ReusableHyperOptimizer(
    methods=["greedy", "kahypar"], parallel=True, minimize="flops",
    max_time=120, max_repeats=4096, progbar=True,
)
tc.set_contractor("custom", optimizer=optr, preprocessing=True)
# shorthand presets also exist, e.g. tc.set_contractor("cotengra-30-10")
```

---

## 2. Circuit construction

```python
n = 5
c = tc.Circuit(n)                       # n qubits, initialized to |0...0>

import numpy as np
w = np.array([1, 0, 0, 1]) / np.sqrt(2)
c = tc.Circuit(2, inputs=w)             # custom input statevector (length 2**n)

c = tc.Circuit(n, mps_inputs=mps)       # input as an MPS (tc.quantum.QuVector)
c = tc.Circuit(n, inputs=tc.backend.eye(2**n))  # feed identity -> extract full unitary
```

Constructor: `tc.Circuit(nqubits, inputs=None, mps_inputs=None, split=None)`.
Other circuit classes share the gate/measurement API:
`tc.DMCircuit(n)` / `tc.DMCircuit2(n)` (density matrix), `tc.MPSCircuit(n)` (approximate MPS),
`tc.StabilizerCircuit(n)` (Clifford), `tc.QuditCircuit(...)`, `tc.U1Circuit(...)`.

### Gate set

Gates are methods on the circuit; qubit indices are positional, parameters are keyword.
Most gate names work in upper or lower case (`c.H(0)` == `c.h(0)`). Index args accept
ranges / lists for broadcasting (`c.h(range(n))`, `c.cx(range(n-1), range(1, n))`).

**Fixed single-qubit:** `h, x, y, z, s, t, sd, td, i` (`c.H(0)`, `c.x(1)`, …)
**Fixed multi-qubit:** `cnot`/`cx`/`CX`, `cz`, `cy`, `swap`, `iswap`, `toffoli` (CCX), `fredkin` (CSWAP)

```python
c.H(0); c.X(1); c.Z(2)
c.cnot(0, 1)          # == c.cx(0, 1)
c.cz(0, 1); c.swap(0, 1)
c.toffoli(0, 1, 2); c.fredkin(0, 1, 2)
```

**Parameterized single-qubit** (rotation = `exp(-i θ/2 · P)`):

```python
c.rx(0, theta=0.5)    # e^{-iθ/2 X}
c.ry(1, theta=0.3)
c.rz(2, theta=0.7)
c.r(0, theta=θ, alpha=0.5, phi=0.8)   # general single-qubit rotation
c.u(0, theta=θ, phi=φ, lbd=λ)         # IBM U gate
c.phase(0, theta=θ)                   # phase gate
```

**Parameterized two-qubit:** `rxx, ryy, rzz` (Ising-type), `crx, cry, crz` (controlled rotations), `cr`.

```python
c.rzz(0, 1, theta=0.4)     # e^{-iθ/2 Z⊗Z}
c.crx(0, 1, theta=0.2)     # controlled-RX
```

**Hamiltonian / exponential gates** (the key primitives for time evolution & Ising ansätze):

| Method | Math | Notes |
|---|---|---|
| `c.exp1(*idx, unitary=U, theta=θ)` | `e^{-iθ U}` | **Fast path requiring U²=I** (Paulis, ZZ, …). Use for Trotter/Ising layers. |
| `c.exp(*idx, unitary=U, theta=θ)` | `e^{-iθ U}` | General matrix exponential, no U²=I assumption. |
| `c.any(*idx, unitary=U)` | apply `U` | Apply an arbitrary unitary matrix directly. |
| `c.multicontrol(*idx, unitary=U, ctrl=[...])` | multi-controlled `U` | |
| `c.mpo(*idx, mpo=quop)` | apply MPO | Apply a `tc.quantum.QuOperator` as a gate. |

```python
import numpy as np
c.exp1(0, 1, unitary=tc.gates._zz_matrix, theta=θ)   # e^{-iθ ZZ}, built-in ZZ matrix
c.exp1(0, unitary=np.array([[0, 1], [1, 0]]), theta=0.2)  # e^{-iθ X}
c.any(0, 1, unitary=my_4x4_unitary)
```

Gate matrices (for `c.expectation`, custom gates) live in `tc.gates`: `tc.gates.x()`, `.y()`, `.z()`,
`.h()`, `.cnot()`, … plus `tc.gates.Gate(array)` to wrap a raw array, and `tc.gates._zz_matrix`.

### Circuit utilities

```python
c2 = c.copy()                 # independent copy (via internal IR)
qir = c.to_qir()              # list of dicts describing each gate
qc = c.to_qiskit()            # export to Qiskit
c = tc.Circuit.from_qiskit(qc, n=2, binding_parameters={"theta": 0.5})
tex = c.vis_tex(); c.draw()   # LaTeX / Qiskit visualization
```

---

## 3. Outputs and measurements

```python
c = tc.Circuit(2); c.H(0); c.cnot(0, 1)

c.state()                 # full statevector, shape (2**n,)  [alias: c.wavefunction()]
c.amplitude("01")         # single amplitude <01|psi> for a bitstring
c.probability()           # vector of measurement probabilities, shape (2**n,)
```

### Expectations

```python
# Generic: pass (gate_matrix, [qubits]) tuples — products are multiplied together
c.expectation((tc.gates.z(), [0]))                       # <Z_0>
c.expectation((tc.gates.z(), [0]), (tc.gates.z(), [1]))  # <Z_0 Z_1>
c.expectation((h, []))                                   # h = dense/sparse matrix observable

# Pauli-string shorthand (preferred for Hamiltonian terms): x=/y=/z= take qubit lists
c.expectation_ps(z=[0])              # <Z_0>
c.expectation_ps(z=[0, 1])           # <Z_0 Z_1>
c.expectation_ps(z=[0], x=[1], y=[2])# <Z_0 X_1 Y_2>
c.expectation_ps(z=[0, n-1], reuse=False)  # reuse=False: independent contraction (big/TN circuits)
```

`reuse=True` (default) caches the contracted wavefunction across calls; set `reuse=False` for
very large tensor-network circuits where you never want to materialize the full state.
Expectations are complex — wrap in `K.real(...)` before differentiating a (real) energy.

### Sampling

```python
c.sample(batch=1024, allow_state=True, format="count_dict_bin")  # dict {"01": 500, ...}
c.sample(batch=100)                                              # measurement results
c.perfect_sampling()                                            # (bitstring, amplitude), exact TN sampling
c.measure(0, 1)                                                 # collapse-measure given qubits
c.measure(0, 1, with_prob=True)                                 # (result, prob)
c.measure_jit(0, 1)                                             # jittable measurement
```

`format`/`format_` options include `"count_dict_bin"`, `"sample_bin"`, etc.

### Shot-based / readout-error expectations (hardware-like)

```python
c.sample_expectation_ps(z=[0, 1], shots=1000)        # finite-shot estimate of <Z_0 Z_1>
c.sample_expectation_ps(z=[0, 1, 2],
    readout_error=[[0.9, 0.75], [0.4, 0.7], [0.7, 0.9]])  # per-qubit [p(0|0), p(1|1)]
```

### Hamiltonians and template measurements

```python
# Weighted Pauli-string sum -> sparse (COO) operator
structures = [[3,0,0],[0,3,0],[1,1,0]]   # 0=I,1=X,2=Y,3=Z per qubit
weights    = [1.0, 1.0, 0.5]
h = tc.quantum.PauliStringSum2COO(structures, weights)      # sparse BCOO matrix
mvp = tc.quantum.PauliStringSum2MVP(structures, weights)    # matrix-free H|psi> function

# Build a per-qubit Pauli structure from a dict
tc.quantum.xyz2ps({"z": [0, 1]}, n=3)    # -> [3, 3, 0]

# Expectation of a (dense or sparse) operator against a circuit
energy = tc.templates.measurements.operator_expectation(c, h)
# Model Hamiltonians:
g = tc.templates.graphs.Line1D(n, pbc=False)
h = tc.quantum.heisenberg_hamiltonian(g, hzz=1.0, hxx=1.0, hyy=1.0, sparse=False)
# MPO observable:
tc.templates.measurements.mpo_expectation(c, mpo)
```

---

## 4. Autodiff, JIT, vmap

The backend object `K` provides the differentiation/compilation primitives — backend-agnostic.

| Call | Purpose |
|---|---|
| `K.grad(f, argnums=0)` | Gradient function of `f`. |
| `K.value_and_grad(f, argnums=0)` | Returns `(value, grad)` in one pass — the VQE workhorse. |
| `K.jit(f, static_argnums=...)` | Compile `f`. Non-tensor args (e.g. `n`) must be `static_argnums`. |
| `K.vmap(f, vectorized_argnums=0)` | Vectorize `f` over a batch axis (parameter sweeps, MC trajectories). |
| `K.jvp / K.vjp / K.hessian` | Forward/reverse JVP-VJP and Hessian. |
| `K.value_and_grad(f, has_aux=True)` | When `f` returns `(loss, aux)`. |
| `K.implicit_randn(shape) / K.implicit_randu(shape)` | Backend-managed random normal / uniform tensors. |
| `K.set_random_state(key) / K.get_random_state(seed) / K.random_split(key)` | RNG control (JAX needs explicit keys under jit/vmap). |
| `tc.array_to_tensor(x)` / `tc.num_to_tensor(x)` | Promote Python/NumPy scalars/arrays to backend tensors of the global dtype. |

**Canonical pattern — jit the value-and-grad step:**

```python
K = tc.set_backend("jax")

def energy(params, n):
    c = tc.Circuit(n)
    for i in range(n):
        c.rx(i, theta=params[0, i])
        c.rz(i, theta=params[1, i])
    e = 0.0
    for i in range(n):
        e += c.expectation_ps(z=[i])
    return K.real(e)

vgf = K.jit(K.value_and_grad(energy), static_argnums=1)   # n is static
params = K.implicit_randn([2, n])
loss_val, grad_val = vgf(params, n)
```

Decorator form (compose `jit` outside `value_and_grad`):

```python
@K.jit
@K.value_and_grad
def objective(params):
    c = tc.Circuit(3)
    c.rx(range(3), theta=params)        # broadcast over qubits
    return K.real(c.expectation_ps(z=[0]))

value, grad = objective(K.ones([3]))
```

**vmap — batched parameters / trajectories:**

```python
def single(param):
    c = tc.Circuit(2)
    c.rx(0, theta=param[0]); c.ry(1, theta=param[1])
    return K.real(c.expectation_ps(z=[0]))

results = K.vmap(single)(K.ones([10, 2]))   # shape (10,)
```

**JAX RNG under jit/vmap** (TF's implicit RNG does NOT translate):

```python
key = K.get_random_state(42)
@K.jit
def r(key):
    K.set_random_state(key)
    return K.implicit_randn()
key1, key2 = K.random_split(key)
print(r(key1), r(key2))    # distinct values
```

**Optimizer loop (JAX + optax):**

```python
import optax
optimizer = optax.adam(1e-2)
opt_state = optimizer.init(params)
for step in range(200):
    loss, grads = vgf(params, n)
    updates, opt_state = optimizer.update(grads, opt_state)
    params = optax.apply_updates(params, updates)
```

**SciPy optimizer interface** (small smooth problems, L-BFGS):

```python
from scipy import optimize
f_scipy = tc.interfaces.scipy_optimize_interface(loss, shape=[2, n])  # returns (val, grad)
res = optimize.minimize(f_scipy, np.zeros([2 * n]), method="L-BFGS-B", jac=True)
```

**ML-framework layers / interfaces:** `tc.KerasLayer(f, weight_shapes)`,
`tc.TorchLayer(f, weight_shapes, use_vmap=True, vectorized_argnums=[...])`,
`tc.interfaces.torch_interface(f, jit=True)`, `tc.interfaces.jax_interface(f, jit=True, enable_dlpack=True)`.

**Persisting jitted functions:** TF — `tc.keras.save_func/load_func`; JAX —
`tc.experimental.jax_jitted_function_save/_load`.

---

## 5. Noise and density matrix

Two ways to simulate noise:
- **`DMCircuit`** — exact density-matrix evolution (doubles effective qubit count, deterministic).
- **`Circuit`** — Monte-Carlo trajectories (statevector + `status`/RNG per channel; average many runs).

```python
c = tc.DMCircuit(2)
c.h(0); c.cx(0, 1)
c.depolarizing(1, px=0.1, py=0.1, pz=0.1)   # convenience channel methods
dm = c.state()                               # density matrix, shape (2**n, 2**n)
c.expectation_ps(z=[0])                      # same measurement API as Circuit
```

**Convenience noise methods** (on `Circuit` and `DMCircuit`):
`depolarizing(i, px=, py=, pz=)`, `generaldepolarizing(i, p=, num_qubits=)`,
`amplitudedamping(i, gamma=, p=)`, `phasedamping(i, gamma=)`, `reset(i)`,
`thermalrelaxation(i, t1=, t2=, time=, method="ByChoi", excitedstatepopulation=0)`.

**Apply an arbitrary Kraus channel** (the general primitive):

```python
c.apply_general_kraus(tc.channels.phasedampingchannel(0.15), i)
```

**Channel constructors** in `tc.channels` (return Kraus operator lists):

| Function | Purpose |
|---|---|
| `depolarizingchannel(px, py, pz)` | Asymmetric depolarizing. |
| `isotropicdepolarizingchannel(p, num_qubits)` | Equal-weight depolarizing. |
| `generaldepolarizingchannel(p, num_qubits)` | Multi-qubit depolarizing (`p` float or per-Pauli list). |
| `amplitudedampingchannel(gamma, p)` | Energy dissipation (T1-like). |
| `phasedampingchannel(gamma)` | Dephasing without energy loss. |
| `resetchannel()` | Reset to \|0⟩. |
| `thermalrelaxationchannel(t1, t2, time, method, excitedstatepopulation)` | Combined T1/T2. |
| `composedkraus(k1, k2)` | Sequentially compose two channels. |

Conversions: `kraus_to_choi`, `choi_to_kraus`, `kraus_to_super`, `super_to_kraus`,
`kraus_identity_check`. Quantum-info on density matrices: `tc.quantum.entropy(dm)`,
`entanglement_entropy(dm, [0])`, `entanglement_negativity(dm, [0])`, `log_negativity`,
`fidelity(rho, sigma)`, `trace_distance(rho, sigma)`, `reduced_density_matrix(state, cut=)`.

---

## 6. MPSCircuit — large, low-entanglement circuits

Approximate simulation with bond-dimension truncation. Same gate/measurement API as `Circuit`;
accuracy controlled by `max_singular_values` (bond dim χ). Estimated fidelity `c._fidelity`
is a good proxy for true fidelity while it stays above ~50%.

```python
c = tc.MPSCircuit(n)
c.set_split_rules({"max_singular_values": chi})   # cap bond dimension χ
c.H(1); c.CNOT(0, 1); c.rx(2, theta=tc.num_to_tensor(1.0))
c.exp1(i, i + 1, theta=θ, unitary=tc.gates._zz_matrix)
c.expectation((tc.gates.z(), [2]))
c.expectation_ps(z=[0])
s = c.state()              # dense state (only for small n / validation)
fid = c._fidelity          # estimated truncation fidelity
```

Constructor: `tc.MPSCircuit(nqubits, center_position=None, tensors=None, wavefunction=None, split=None, dim=None)`.
Truncation can also be passed per-gate via `split={"max_singular_values": chi}` (or `max_truncation_err`,
`relative_err`). Useful methods: `get_bond_dimensions()`, `get_tensors()`, `position(site)`,
`normalize()`, `measure(*idx, with_prob=)`, `reduced_density_matrix(keep)`, `copy()`, `conj()`.

For tight memory on deep homogeneous stacks, apply layers state-in/state-out and reuse the
state (or `jax.lax.scan`) instead of holding the whole graph; record `max_singular_values` so the
function stays jittable (static shapes).

---

## 7. Worked examples (verbatim)

### 7.1 Bell state, expectation, sampling (README quick demo)

```python
import tensorcircuit as tc
c = tc.Circuit(2)
c.H(0)
c.CNOT(0,1)
c.rx(1, theta=0.2)
print(c.wavefunction())
print(c.expectation_ps(z=[0, 1]))
print(c.sample(allow_state=True, batch=1024, format="count_dict_bin"))
```

### 7.2 Autodiff + jit on a single parameter (README quick demo)

```python
def forward(theta):
    c = tc.Circuit(2)
    c.R(0, theta=theta, alpha=0.5, phi=0.8)
    return tc.backend.real(c.expectation((tc.gates.z(), [0])))

g = tc.backend.grad(forward)
g = tc.backend.jit(g)
theta = tc.array_to_tensor(1.0)
print(g(theta))
```

### 7.3 Sparse Pauli-sum Hamiltonian + expectation (README quick demo)

```python
n = 6
pauli_structures = []
weights = []
for i in range(n):
    pauli_structures.append(tc.quantum.xyz2ps({"z": [i, (i + 1) % n]}, n=n))
    weights.append(1.0)
for i in range(n):
    pauli_structures.append(tc.quantum.xyz2ps({"x": [i]}, n=n))
    weights.append(-1.0)
h = tc.quantum.PauliStringSum2COO(pauli_structures, weights)
print(h)
# BCOO(complex64[64, 64], nse=448)
c = tc.Circuit(n)
c.h(range(n))
energy = tc.templates.measurements.operator_expectation(c, h)
# -6
```

### 7.4 Complete VQE: TFIM, jit + value_and_grad, sparse vs matrix-free (examples/mvp_vqe.py)

```python
"""
VQE using mvp method to evaluate Hamiltonian expectation
"""

import time
import jax
import jax.numpy as jnp
import tensorcircuit as tc

# Configuration
tc.set_backend("jax")
tc.set_dtype("complex128")

n = 18  # Qubit number
nlayers = 4

# TFIM Hamiltonian parameters
j, h = 1.0, -1.0


def ansatz(param, n, nlayers):
    c = tc.Circuit(n)
    for i in range(nlayers):
        for j in range(n):
            c.rx(j, theta=param[i, j, 0])
            c.rz(j, theta=param[i, j, 1])
        for j in range(n - 1):
            c.cnot(j, j + 1)
    return c


# 1. Prepare Hamiltonian structures and weights
structures = []
weights = []

# Transverse field: sum h * Z_i
for i in range(n):
    s = [0] * n
    s[i] = 3  # Z
    structures.append(s)
    weights.append(h)

# Ising interaction: sum j * X_i X_{i+1}
for i in range(n - 1):
    s = [0] * n
    s[i] = 1  # X
    s[i + 1] = 1  # X
    structures.append(s)
    weights.append(j)

# Prepare Sparse Matrix for operator_expectation
hamiltonian_sparse = tc.quantum.PauliStringSum2COO(structures, weights)

# Generate MVP function
mvp_func = tc.quantum.PauliStringSum2MVP(structures, weights)

# 2. Define Loss Functions


def loss_sparse(param):
    c = ansatz(param, n, nlayers)
    return tc.templates.measurements.operator_expectation(c, hamiltonian_sparse)


def loss_mvp(param):
    c = ansatz(param, n, nlayers)
    psi = c.state()
    h_psi = mvp_func(psi)
    # <psi|H|psi>
    return jnp.real(jnp.vdot(psi, h_psi))


# 3. Benchmarking function
def benchmark(loss_fn, param, name):
    # JIT the value and grad
    vag_fn = jax.jit(jax.value_and_grad(loss_fn))

    print(f"\nBenchmarking {name}...")

    # Warmup / Compilation
    t0 = time.time()
    v, g = vag_fn(param)
    jax.block_until_ready(v)
    t_compile = time.time() - t0
    print(f"Compile time: {t_compile:.4f} s")

    # Running time
    t0 = time.time()
    iterations = 50
    for _ in range(iterations):
        v, g = vag_fn(param)
        jax.block_until_ready(v)
    t_run = (time.time() - t0) / iterations
    print(f"Running time (avg of {iterations} iterations): {t_run*1000:.4f} ms")

    return v, g, t_run


if __name__ == "__main__":
    param = jax.random.normal(jax.random.PRNGKey(42), shape=(nlayers, n, 2))

    # Compare correctness and performance
    res_sparse, grad_sparse, t_sparse = benchmark(
        loss_sparse, param, "Sparse Matrix (COO)"
    )
    res_mvp, grad_mvp, t_mvp = benchmark(loss_mvp, param, "Matrix-Free MVP")

    print("\n--- Results Comparison ---")
    print(f"Energy (Sparse): {res_sparse:.8f}")
    print(f"Energy (MVP):    {res_mvp:.8f}")

    diff_val = jnp.abs(res_sparse - res_mvp)
    diff_grad = jnp.linalg.norm(grad_sparse - grad_mvp)

    print(f"Energy Diff:     {diff_val:.2e}")
    print(f"Gradient Norm Diff: {diff_grad:.2e}")

    speedup = t_sparse / t_mvp
    print(f"Speedup: {speedup:.2f}x")

    if diff_val < 1e-5 and diff_grad < 1e-4:
        print("\nSUCCESS: Results match between methods.")
    else:
        print("\nFAILURE: Significant discrepancy detected.")
```

### 7.5 Batched VQE-style energy (jit + value_and_grad), backend-agnostic (quickstart)

```python
import tensorcircuit as tc

K = tc.set_backend("tensorflow")

def loss(params, n):
    c = tc.Circuit(n)
    for i in range(n):
        c.rx(i, theta=params[0, i])
    for i in range(n):
        c.rz(i, theta=params[1, i])
    loss = 0.0
    for i in range(n):
        loss += c.expectation([tc.gates.z(), [i]])
    return K.real(loss)

vgf = K.jit(K.value_and_grad(loss), static_argnums=1)
params = K.implicit_randn([2, n])
loss_val, grad_val = vgf(params, n)
```

### 7.6 Noisy simulation: DM vs Monte-Carlo trajectory cross-check (examples/mcnoise_check.py)

```python
"""
Cross check the correctness of the density matrix simulator and the Monte Carlo trajectory state simulator.
"""

import os

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
# cpu is fast for small scale circuit simulation
import sys

sys.path.insert(0, "../")

from tqdm import tqdm
import jax
import tensorcircuit as tc

tc.set_backend("jax")

n = 5
nlayer = 3
mctries = 100  # 100000

print(jax.devices())


def template(c):
    # dont jit me!
    for i in range(n):
        c.H(i)
    for i in range(n):
        c.rz(i, theta=tc.num_to_tensor(i))
    for _ in range(nlayer):
        for i in range(n - 1):
            c.cnot(i, i + 1)
        for i in range(n):
            c.rx(i, theta=tc.num_to_tensor(i))
        for i in range(n):
            c.apply_general_kraus(tc.channels.phasedampingchannel(0.15), i)
    return c.state()


@tc.backend.jit
def answer():
    c = tc.DMCircuit2(n)
    return template(c)


rho0 = answer()

print(rho0)


@tc.backend.jit
def f(key):
    if key is not None:
        tc.backend.set_random_state(key)
    c = tc.Circuit(n)
    return template(c)


key = jax.random.PRNGKey(42)
f(key).block_until_ready()  # build the graph

rho = 0.0

for i in tqdm(range(mctries)):
    key, subkey = jax.random.split(key)
    psi = f(subkey)  # [1, 2**n]
    rho += (
        1
        / mctries
        * tc.backend.reshape(psi, [-1, 1])
        @ tc.backend.conj(tc.backend.reshape(psi, [1, -1]))
    )

print(rho)
print("difference\n", tc.backend.abs(rho - rho0))
print("difference in total\n", tc.backend.sum(tc.backend.abs(rho - rho0)))
print("fidelity", tc.quantum.fidelity(rho, rho0))
print("trace distance", tc.quantum.trace_distance(rho, rho0))
```

### 7.7 MPS vs exact, bond-dimension sweep (examples/mpsvsexact.py, abridged)

```python
import tensorcircuit as tc

tc.set_backend("tensorflow")
tc.set_dtype("complex128")

def tfi_energy(c, n, j=1.0, h=-1.0):
    e = 0.0
    for i in range(n):
        e += h * c.expectation((tc.gates.x(), [i]))
    for i in range(n - 1):
        e += j * c.expectation((tc.gates.z(), [i]), (tc.gates.z(), [(i + 1) % n]))
    return e

def energy(param, mpsd=None):
    if mpsd is None:
        c = tc.Circuit(n)
    else:
        c = tc.MPSCircuit(n)
        c.set_split_rules({"max_singular_values": mpsd})
    for i in range(n):
        c.H(i)
    for j in range(nlayers):
        for i in range(n - 1):
            c.exp1(i, (i + 1) % n, theta=param[2 * j, i], unitary=tc.gates._zz_matrix)
        for i in range(n):
            c.rx(i, theta=param[2 * j + 1, i])
    e = tc.backend.real(tfi_energy(c, n))
    fidelity = c._fidelity if mpsd is not None else None
    return e, c.state(), fidelity

n, nlayers = 15, 20
param = tc.backend.implicit_randu([2 * nlayers, n])
e0, s0, _ = energy(param)
for mpsd in [2, 5, 10, 20, 50, 100]:
    e1, s1, f1 = energy(param, mpsd=mpsd)   # compare e1 to exact e0; track f1 = estimated fidelity
```

### 7.8 Density matrix + quantum information (README quick demo)

```python
c = tc.DMCircuit(2)
c.h(0)
c.cx(0, 1)
c.depolarizing(1, px=0.1, py=0.1, pz=0.1)
dm = c.state()
print(tc.quantum.entropy(dm))
print(tc.quantum.entanglement_entropy(dm, [0]))
print(tc.quantum.entanglement_negativity(dm, [0]))
print(tc.quantum.log_negativity(dm, [0]))
```

### 7.9 Large-scale tensor-network expectation, no full state (README quick demo)

```python
# tc.set_contractor("cotengra-30-10")
n = 500
c = tc.Circuit(n)
c.h(0)
c.cx(range(n - 1), range(1, n))
c.expectation_ps(z=[0, n - 1], reuse=False)   # reuse=False -> never materialize 2**500 state
```

---

## 8. Pitfalls

- **Set backend and dtype FIRST.** `tc.set_backend(...)` / `tc.set_dtype(...)` are global. Build
  circuits only after; switching mid-run changes numerics and can desync cached tensors.
- **`complex64` vs `complex128`.** Default is `complex64` (fast, ~1e-3–1e-4 accuracy). VQE energies,
  gradients, and literature comparisons usually need `tc.set_dtype("complex128")`. Dtype mismatches
  trigger errors or silent precision loss.
- **JIT tracing constraints.** Non-tensor args (qubit count `n`, layer count) must be marked
  `static_argnums`. Changing tensor **shape or dtype** recompiles. Don't use Python control flow on
  traced values; keep `max_singular_values` fixed so MPS splits stay static-shape and jittable.
- **`expectation_ps` returns complex** — wrap energies in `K.real(...)` before differentiating.
  `expectation_ps(x=[...], y=[...], z=[...])` takes qubit-index lists, not matrices; use
  `expectation((gate, [q]), ...)` when you need a non-Pauli/dense/sparse observable.
- **`reuse=` on expectations.** Default `reuse=True` caches the wavefunction; for huge
  tensor-network circuits pass `reuse=False` so the full state is never materialized.
- **RNG under jit/vmap.** JAX requires explicit keys (`get_random_state`/`random_split`/`set_random_state`);
  TensorFlow's implicit RNG does not carry through jit/vmap. For noise channels pass an explicit
  `status=` / `random` value and `vmap` over it for Monte-Carlo trajectories.
- **`exp1` requires U²=I** (Paulis, ZZ, …); use `exp` for general matrix exponentials.
- **Don't jit circuit-building helpers that mutate a passed-in circuit** (see `mcnoise_check.py`'s
  `template` "dont jit me") — jit the top-level pure function that returns the state/expectation.
- **First call is slow = compilation, not a hang.** Time the warm `value_and_grad` step separately
  from the one-off compile and from path search; `block_until_ready()` before timing on JAX.

---

## 9. Source links

- Docs home: https://tensorcircuit-ng.readthedocs.io/
- Quickstart: https://tensorcircuit-ng.readthedocs.io/en/latest/quickstart.html
- Advanced usage (AD/jit/vmap): https://tensorcircuit-ng.readthedocs.io/en/latest/advance.html
- API reference index: https://tensorcircuit-ng.readthedocs.io/en/latest/modules.html
- Circuit API: https://tensorcircuit-ng.readthedocs.io/en/latest/api/circuit.html
- Gates API: https://tensorcircuit-ng.readthedocs.io/en/latest/api/gates.html
- Density matrix API: https://tensorcircuit-ng.readthedocs.io/en/latest/api/densitymatrix.html
- Noise channels API: https://tensorcircuit-ng.readthedocs.io/en/latest/api/channels.html
- MPSCircuit API: https://tensorcircuit-ng.readthedocs.io/en/latest/api/mpscircuit.html
- Backends API: https://tensorcircuit-ng.readthedocs.io/en/latest/api/backends.html
- Measurements templates: https://tensorcircuit-ng.readthedocs.io/en/latest/api/templates/measurements.html
- GitHub repo: https://github.com/tensorcircuit/tensorcircuit-ng
- Examples folder (150+ scripts): https://github.com/tensorcircuit/tensorcircuit-ng/tree/master/examples
  - `examples/mvp_vqe.py`, `examples/mcnoise_check.py`, `examples/mpsvsexact.py` (used above)
- Whitepapers: https://arxiv.org/abs/2205.10091 , https://arxiv.org/abs/2602.14167
