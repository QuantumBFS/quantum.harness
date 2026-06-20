# QuTiP API + Examples Reference

**QuTiP** (Quantum Toolbox in Python) is an open-source framework for representing
quantum states and operators as a unified `Qobj` class and for simulating closed-
and open-system dynamics (Schrödinger equation, Lindblad master equation, quantum
trajectories). Built on NumPy/SciPy with sparse + dense backends.

**What it does well**
- Unified quantum-object algebra (kets, bras, operators, super-operators).
- Hamiltonian assembly from tensor products of small operators — natural for
  small spin chains, cavity-QED, qubit-cavity, trapped-ion models.
- Eigensolving / ground states for small dense Hamiltonians (ED of modest size).
- **Open-system / time dynamics** is the flagship: `mesolve` (Lindblad master
  equation with collapse operators), `sesolve` (unitary), `mcsolve` (Monte-Carlo
  quantum trajectories), `steadystate`.
- Entropy / entanglement measures, expectation values, Wigner functions.

**Scope limit.** QuTiP is a *dense / small-Hilbert-space* tool. The full density
matrix is N² and master-equation super-operators are N²×N²; practical only for
N ≲ 1000 (master equation), larger with `mcsolve` (only the N-element state vector
is stored). It is **not** a large-scale lattice ED or DMRG package — for many-body
lattices beyond a handful of sites use QuSpin / XDiag (ED) or ITensors / TeNPy
(DMRG). See `.knowledge/literature/software/INDEX.md`.

**Note on API version.** Signatures below follow modern QuTiP (v4/v5). The 2011
release paper uses the legacy solver names `odesolve` / `essolve` / `mcsolve`;
these are replaced by `mesolve` / `sesolve` / `mcsolve`. Legacy paper examples are
reproduced verbatim in the "Worked examples (from the release paper)" section with
this caveat.

---

## 1. Qobj basics

`Qobj(inpt=None, dims=None, ...)` — the quantum-object container. Wraps a matrix
plus bookkeeping: type, dims, hermiticity.

```python
from qutip import *
import numpy as np

print(Qobj())
# Quantum object: dims = [[1], [1]], shape = (1, 1), type = bra
# Qobj data =
# [[0.]]

print(Qobj([[1],[2],[3],[4],[5]]))
# Quantum object: dims = [[5], [1]], shape = (5, 1), type = ket
```

### Attributes

| Attribute | Meaning |
|---|---|
| `Q.data` | underlying (sparse) matrix |
| `Q.dims` | list tracking the shapes of individual subsystems of a multipartite space, e.g. `[[2,2],[2,2]]` for a 2-qubit operator |
| `Q.shape` | shape of the flat data matrix, e.g. `(4, 4)` |
| `Q.type` | `'ket'`, `'bra'`, `'oper'`, or `'super'` |
| `Q.isherm` | bool, Hermiticity |

```python
q = destroy(4)
q.dims    # [[4], [4]]
q.shape   # (4, 4)
q.type    # 'oper'
q.isherm  # False
```

### Arithmetic

`+ - *` are defined Qobj⊗Qobj; `+ - * /` are defined Qobj⊗scalar (real/complex).
`**` is matrix power.

```python
q + 5
x * x
q ** 3
x / np.sqrt(2)     # incompatible shapes raise TypeError
```

### Methods

| Method | Purpose |
|---|---|
| `Q.dag()` | adjoint (dagger) |
| `Q.tr()` | trace |
| `Q.norm()` | L2 norm (states) / trace norm (operators) |
| `Q.full()` | dense NumPy array |
| `Q.unit()` | normalized copy |
| `Q.diag()` | diagonal elements |
| `Q.eigenstates()` | `(eigvals, eigvecs)` |
| `Q.eigenenergies()` | eigenvalues only |
| `Q.groundstate()` | `(E0, ψ0)` lowest eigenpair |
| `Q.expm()` | matrix exponential (e.g. propagator `(-1j*H*t).expm()`) |
| `Q.sqrtm()` | matrix square root |
| `Q.ptrace(sel)` | partial trace, keeping subsystem(s) `sel` |

```python
basis(5, 3).dag()
# dims = [[1], [5]], type = bra,  data = [[0. 0. 0. 1. 0.]]

(basis(4, 2) + basis(4, 1)).unit()
# (1/√2)(|1⟩ + |2⟩)
```

---

## 2. Operators & states catalog

### State constructors

| Call | Purpose |
|---|---|
| `basis(N, n)` / `fock(N, n)` | Fock/number basis ket \|n⟩ in N levels |
| `fock_dm(N, n)` | density matrix \|n⟩⟨n\| |
| `ket2dm(ket)` | ket → density matrix \|ψ⟩⟨ψ\| |
| `coherent(N, alpha)` | coherent state ket (displacement α) |
| `coherent_dm(N, alpha)` | coherent-state density matrix |
| `thermal_dm(N, n_th)` | thermal density matrix with mean occupation n_th |

```python
vac = basis(5, 0)
ket = (basis(5, 0) + basis(5, 1)).unit()   # (1/√2)(|0⟩+|1⟩)
spin1 = basis(2, 0)                          # |↑⟩
spin2 = basis(2, 1)                          # |↓⟩
two_spins = tensor(spin1, spin2)
```

### Operator constructors

| Call | Purpose |
|---|---|
| `qeye(N)` / `identity(N)` | identity on N levels |
| `destroy(N)` / `create(N)` | bosonic â / â† (N-level truncation) |
| `num(N)` | number operator â†â |
| `position(N)` / `momentum(N)` | x̂ / p̂ (harmonic oscillator) |
| `displace(N, alpha)` | displacement D(α) |
| `squeeze(N, xi)` | squeezing S(ξ) |
| `sigmax()`, `sigmay()`, `sigmaz()` | Pauli σˣ, σʸ, σᶻ (2-level) |
| `sigmap()`, `sigmam()` | spin raising σ⁺ / lowering σ⁻ |
| `jmat(j, which)` | spin-j operators; `which` ∈ `'x','y','z','+','-'` |
| `spin_Jx(j)`, `spin_Jy`, `spin_Jz` | convenience wrappers around `jmat` |

```python
a = destroy(5); c = create(5)
n = num(5)
print(sigmaz())             # [[1, 0], [0, -1]]
d = displace(5, 1j)
print(d * vac)              # coherent state from vacuum
```

Note: for S=½ the spin operators are S = σ/2, so `jmat(1/2,'z') == sigmaz()/2`.

---

## 3. Tensor products — composite systems & spin chains

`tensor(op1, op2, ...)` or `tensor([op1, op2, ...])` — Kronecker product; result is
a Qobj with `dims` encoding each subsystem. **Ordering matters**: the leftmost
argument is subsystem 0.

```python
print(tensor(basis(2, 0), basis(2, 0)))
# dims = [[2, 2], [1, 1]], shape = (4, 1), type = ket

print(tensor(sigmaz(), identity(2)))   # σᶻ on qubit 0 only
# dims = [[2, 2], [2, 2]], shape = (4, 4), type = oper
```

To place a single-site operator `O` at site `i` of an L-site chain, tensor it with
identities everywhere else (the standard embedding idiom):

```python
def op_at(O, i, L, d=2):
    """Embed single-site operator O at site i of an L-site chain."""
    ops = [qeye(d)] * L
    ops[i] = O
    return tensor(ops)
```

### Hamiltonian assembly — example chains

**Two/three coupled qubits** (from the QuTiP guide, verbatim):

```python
H = tensor(sigmaz(), identity(2)) + tensor(identity(2), sigmaz()) + 0.05 * tensor(sigmax(), sigmax())

H = (tensor(sigmaz(), identity(2), identity(2)) +
     tensor(identity(2), sigmaz(), identity(2)) +
     tensor(identity(2), identity(2), sigmaz()) +
     0.5 * tensor(sigmax(), sigmax(), identity(2)) +
     0.25 * tensor(identity(2), sigmax(), sigmax()))
```

**Jaynes-Cummings model** (atom + N-level cavity, verbatim from guide):

```python
N = 6
omega_a = 1.0; omega_c = 1.25; g = 0.75
a  = tensor(identity(2), destroy(N))
sm = tensor(destroy(2), identity(N))
sz = tensor(sigmaz(), identity(N))
H = 0.5 * omega_a * sz + omega_c * a.dag() * a + g * (a.dag() * sm + a * sm.dag())
```

**Heisenberg / transverse-field-Ising spin chain via tensor products + ground state**
(harness-assembled using the `op_at` idiom above; not verbatim from the docs):

```python
from qutip import *
import numpy as np

L = 8
Jx = Jy = Jz = 1.0
sx, sy, sz = sigmax(), sigmay(), sigmaz()

def op_at(O, i, L):
    ops = [qeye(2)] * L; ops[i] = O
    return tensor(ops)

# Heisenberg chain, open boundary:  H = Σ_i J·(SxSx + SySy + SzSz)
H = 0
for i in range(L - 1):
    H += (Jx * op_at(sx, i, L) * op_at(sx, i+1, L)
        + Jy * op_at(sy, i, L) * op_at(sy, i+1, L)
        + Jz * op_at(sz, i, L) * op_at(sz, i+1, L))

E0, psi0 = H.groundstate()      # ground energy + ground state ket
print("E0 =", E0)

# Transverse-field Ising:  H = -Σ Jz SzSz - h Σ Sx
h = 1.0
H_tfi = 0
for i in range(L - 1):
    H_tfi += -Jz * op_at(sz, i, L) * op_at(sz, i+1, L)
for i in range(L):
    H_tfi += -h * op_at(sx, i, L)
E0_tfi = H_tfi.eigenenergies(eigvals=1)[0]
```

### Partial trace

`Q.ptrace(sel)` — `sel` is the subsystem index (or list) to **keep**; everything
else is traced out. Always returns a density matrix.

```python
psi = tensor(basis(2, 0), basis(2, 1))
psi.ptrace(0)   # keep qubit 0  → [[1,0],[0,0]]
psi.ptrace(1)   # keep qubit 1  → [[0,0],[0,1]]

psi = tensor((basis(2, 0) + basis(2, 1)).unit(), basis(2, 0))
psi.ptrace(0)   # → [[0.5,0.5],[0.5,0.5]]   (reduced state of qubit 0)
```

---

## 4. Eigensolving / ground state

```python
evals, evecs = H.eigenstates()        # all eigenpairs (dense)
E = H.eigenenergies()                 # eigenvalues only
E_low = H.eigenenergies(eigvals=k)    # k lowest (sparse Lanczos)
E0, psi0 = H.groundstate()            # lowest eigenpair
```

`groundstate(sparse=False, tol=0, maxiter=100000)` uses a sparse eigensolver when
`sparse=True` (memory-friendly for the lowest state of large sparse H).

---

## 5. Expectation values

`expect(oper, state)` — ⟨O⟩ for a single state, or an array of ⟨O⟩ over a list of
states (e.g. a time series from a solver). Accepts kets or density matrices.

```python
vac = basis(5, 0); N = num(5)
expect(N, vac)                          # 0.0

states = [(create(5)**k * vac).unit() for k in range(5)]
expect(N, states)                       # array([0., 1., 2., 3., 4.])

up = basis(2, 0)
expect(sigmaz(), up)                    # 1.0
```

---

## 6. Closed dynamics — `sesolve`

Solves the Schrödinger equation iħ d|ψ⟩/dt = H|ψ⟩.

```python
sesolve(H, psi0, tlist, e_ops=[], args={}, options=None)
```

- `H` — Qobj (static) or time-dependent format (Sec. 8).
- `psi0` — initial ket.
- `tlist` — array of times.
- `e_ops` — list of operators; if non-empty, the result holds ⟨e_op⟩(t) instead of
  full states. If empty, full states are returned.

Returns a `Result` with `.times`, `.expect` (list of arrays, one per `e_op`),
`.states` (list of Qobj), `.e_data` (dict keyed by operator name).

```python
H = 2*np.pi * 0.1 * sigmax()
psi0 = basis(2, 0)
times = np.linspace(0.0, 10.0, 100)
result = sesolve(H, psi0, times, e_ops=[sigmaz(), sigmay()])

import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot(result.times, result.expect[0])
ax.plot(result.times, result.expect[1])
ax.set_xlabel('Time'); ax.set_ylabel('Expectation values')
ax.legend(("Sigma-Z", "Sigma-Y"))
plt.show()
```

---

## 7. Open dynamics — `mesolve`, collapse operators

Solves the Lindblad master equation
ρ̇ = −i[H, ρ] + Σₙ ( Cₙ ρ Cₙ† − ½{Cₙ†Cₙ, ρ} ),
where collapse operators Cₙ = √γₙ Aₙ encode dissipation/decoherence.

```python
mesolve(H, rho0, tlist, c_ops=[], e_ops=[], args={}, options=None)
```

- `rho0` — initial state (ket or density matrix; a ket is promoted).
- `c_ops` — list of collapse operators (Qobj or time-dependent). **Empty `c_ops`
  ⇒ mesolve falls back to unitary Schrödinger evolution.**
- `e_ops`, return `Result` — same as `sesolve`.

```python
# qubit precession + relaxation
H = 2*np.pi * 0.1 * sigmax()
psi0 = basis(2, 0)
times = np.linspace(0.0, 10.0, 100)
result = mesolve(H, psi0, times, [np.sqrt(0.05) * sigmax()],
                 e_ops=[sigmaz(), sigmay()])
plt.plot(times, result.expect[0], times, result.expect[1])
```

**Collapse-operator idiom for thermal bath** (relaxation + excitation), as used in
the cavity/qubit examples:

```python
n_th = 0.75
c_ops = []
c_ops.append(np.sqrt(kappa * (1 + n_th)) * a)        # decay
c_ops.append(np.sqrt(kappa * n_th)       * a.dag())  # thermal excitation
c_ops.append(np.sqrt(gamma)              * sm)        # atom relaxation
```

`options` is a dict, e.g. `mesolve(..., options={"matrix_form": True})` keeps ρ as
an n×n matrix instead of vectorizing to n² (memory-friendly for larger systems);
other common keys: `store_states`, `atol`, `rtol`, `nsteps`, `progress_bar`.

---

## 8. Time-dependent Hamiltonians

Internally a `QobjEvo`. Three equivalent ways to build H(t):

**List format** (most common): `H = [H0, [H1, coeff], [H2, coeff2], ...]`, where
each `coeff` is a function `f(t, args)`, a string expression, or a NumPy array.

```python
# function coefficient
def H1_coeff(t, A, sigma):
    return A * np.exp(-(t / sigma)**2)
H = [sigmaz(), [sigmax(), H1_coeff]]
args = {'A': 9, 'sigma': 5}
result = mesolve(H, psi0, tlist, c_ops, e_ops, args=args)

# string coefficient (compiled; sin/cos/exp/sqrt, np, scipy.special as spe)
H = QobjEvo([H0, [H1, "A * exp(-(t / sigma)**2)"]], args=args)

# array coefficient (spline-interpolated on tlist)
times = np.linspace(-sigma*5, sigma*5, 500)
coeff = A * np.exp(-(times / sigma)**2)
H = QobjEvo([H0, [H1, coeff]], tlist=times)
```

**Function-based** and **coefficient-based** forms:

```python
H_t = QobjEvo(lambda t: num(N) + (destroy(N) + create(N)) * np.sin(t))

coeff = coefficient(lambda t: np.sin(t))
H_t = num(N) + (destroy(N) + create(N)) * coeff
```

`args` is a dict of named constants passed to coefficients; values can be updated at
call time: `qevo(1, {"A": 5, "sigma": 0.2})` or `qevo(1, A=5)`.

---

## 9. Monte-Carlo trajectories — `mcsolve`

Quantum-jump (Monte-Carlo wave function) unraveling of the master equation. Same
arguments as `mesolve` except `psi0` must be a **ket**, and stores only the N-element
state vector per trajectory (vastly more memory-efficient than ρ for large N).

```python
mcsolve(H, psi0, tlist, c_ops=[], e_ops=[], ntraj=500, args={}, options=None)
```

Averaging over `ntraj` trajectories converges to the `mesolve` result as 1/ntraj;
250–500 trajectories typically give few-percent error. Returns `McResult` with
`.expect` / `.average_expect`, `.std_expect`, and jump records `.col_times`,
`.col_which`.

```python
times = np.linspace(0.0, 10.0, 200)
psi0 = tensor(fock(2, 0), fock(10, 8))
a  = tensor(qeye(2), destroy(10))
sm = tensor(destroy(2), qeye(10))
H = 2*np.pi*a.dag()*a + 2*np.pi*sm.dag()*sm + 2*np.pi*0.25*(sm*a.dag() + sm.dag()*a)
data = mcsolve(H, psi0, times, [np.sqrt(0.1) * a],
               e_ops=[a.dag() * a, sm.dag() * sm])
plt.plot(times, data.expect[0], times, data.expect[1])
```

---

## 10. Steady state — `steadystate`

`steadystate(H, c_ops, method='direct', solver=None, ...)` — steady-state ρ_ss of the
Lindblad equation (ρ̇ = 0). `method` ∈ `'direct'`, `'eigen'`, `'power'`, `'svd'`;
`solver` is the linear backend (`'solve'`, `'spsolve'`, `'gmres'`, `'lgmres'`, ...).

```python
N = 20
a = destroy(N)
H = a.dag() * a
kappa = 0.1; n_th_a = 2
c_op_list = []
rate = kappa * (1 + n_th_a)
if rate > 0.0: c_op_list.append(np.sqrt(rate) * a)
rate = kappa * n_th_a
if rate > 0.0: c_op_list.append(np.sqrt(rate) * a.dag())

rho_ss = steadystate(H, c_op_list)
fexpt = expect(a.dag() * a, rho_ss)        # ≈ n_th_a in steady state
```

---

## 11. Entropy & entanglement

```python
entropy_vn(rho, base=np.e, sparse=False)              # Von-Neumann entropy −Tr(ρ ln ρ)
entropy_linear(rho)                                   # linear entropy 1 − Tr(ρ²)
entropy_mutual(rho, selA, selB, base=np.e, sparse=False)   # mutual info S(A:B)
entropy_conditional(rho, selB, base=np.e, sparse=False)    # S(A|B) = S(A,B) − S(B)
entropy_relative(rho, sigma, base=np.e, sparse=False, tol=1e-12)  # S(ρ‖σ)
concurrence(rho)                                      # two-qubit concurrence
negativity(rho, subsys, method='tracenorm', logarithmic=False)   # PPT negativity
entangling_power(U)                                   # entangling power of 2-qubit gate U
```

```python
# entanglement entropy of a bipartition of a ground state
E0, psi0 = H.groundstate()
rhoA = psi0.ptrace(list(range(L // 2)))   # reduce to left half
S_ent = entropy_vn(rhoA)
```

---

## 12. Pitfalls

- **Tensor-product ordering.** The leftmost `tensor` argument is subsystem 0; once
  fixed, keep the same ordering for every operator and the initial state. A
  mismatched embedding silently computes the wrong physics, not an error.
- **`dims` must match.** Two Qobj can only be added/multiplied if their `dims`
  agree. A single-site operator (`dims=[[2],[2]]`) cannot be added to a chain
  operator (`dims=[[2,2,...],[2,2,...]]`) — embed it with identities first.
  `ptrace`/`expect`/`tensor` all rely on `dims`; a Qobj built from a raw matrix may
  need `dims` set explicitly.
- **Hilbert-space size — QuTiP is dense/small.** State dim N ⇒ density matrix N²,
  master-equation super-operator N²×N² (sparse-stored but still heavy). Practical
  master-equation limit N ≲ 1000. For an L-site spin-½ chain N = 2ᴸ, so dense ED of
  the full spectrum is feasible only to ~L ≈ 12–14; `groundstate(sparse=True)` or
  `eigenenergies(eigvals=k)` push a few sites further. Beyond that use a dedicated
  ED/DMRG package.
- **`mcsolve` for big N.** When N is large, `mcsolve` (stores the N-vector, not the
  N² matrix) outperforms `mesolve`; trade memory for trajectory averaging
  (error ∝ 1/ntraj).
- **Time-dependent H formats.** String coefficients are compiled (fast, but limited
  function set: sin/cos/exp/sqrt, `np`, `spe`); function coefficients are flexible
  but slower; array coefficients are spline-interpolated and require passing
  `tlist=`. Pass constants via `args`, never as Python closures over loop variables.
- **`ptrace` returns a density matrix** even from a pure state — downstream code
  must treat the result as ρ, not a ket.
- **Legacy vs modern solver names.** Old QuTiP / the 2011 paper use
  `odesolve`/`essolve`; modern QuTiP uses `mesolve`/`sesolve`. Time-evolution
  function-callback signatures also changed (the list/`QobjEvo` format replaces the
  old `hamiltonian_t(t, args)` callback).

---

## 13. Worked examples (from the release paper, legacy API)

Verbatim from Johansson, Nation & Nori (arXiv:1110.0573). These use the **legacy**
solver names `odesolve` (→ `mesolve`) and `mcsolve` (signature changed); ported
versions use `mesolve` / `sesolve` / `mcsolve` per the sections above. Kept here to
match the paper's text.

**Two-qubit gate with dissipation** (Lindblad, paper §4.1):

```python
H = g * (tensor(sigmax(), sigmax()) +
     tensor(sigmay(), sigmay()))
psi0 = tensor(basis(2,1), basis(2,0))

sm1 = tensor(sigmam(), qeye(2))
sz1 = tensor(sigmaz(), qeye(2))
c_op_list.append(sqrt(g1 * (1+nth)) * sm1)
c_op_list.append(sqrt(g1 * nth) * sm1.dag())
c_op_list.append(sqrt(g2) * sz1)

tlist = linspace(0, T, 100)
rho_list = odesolve(H, psi0, tlist, c_op_list, [])   # modern: mesolve(...)
rho_final = rho_list[-1]

n1 = expect(sm1.dag() * sm1, rho_list)
n2 = expect(sm2.dag() * sm2, rho_list)

U = (-1j * H * pi / (4*g)).expm()
psi_ideal = U * psi0
rho_ideal = psi_ideal * psi_ideal.dag()
f = fidelity(rho_ideal, rho_final)
```

**Heisenberg spin chain** (paper Eq. 10, the benchmark model):

H = −½ Σₙ hₙ σᶻₙ − ½ Σₙ ( Jxₙ σˣₙσˣₙ₊₁ + Jyₙ σʸₙσʸₙ₊₁ + Jzₙ σᶻₙσᶻₙ₊₁ ),
with per-spin dephasing collapse operator √γ σᶻₙ. The paper benchmarks
`odesolve` (master equation), `essolve` (diagonalization), and `mcsolve`
(250 / 500 trajectories) versus Hilbert-space size 2ᴹ — illustrating the dense
N ≲ 1000 practical ceiling.

---

## Source links

- Docs index — https://qutip.readthedocs.io/en/stable/
- Basic operations on Qobj — https://qutip.readthedocs.io/en/stable/guide/guide-basics.html
- States and operators — https://qutip.readthedocs.io/en/stable/guide/guide-states.html
- Tensor products & partial traces — https://qutip.readthedocs.io/en/stable/guide/guide-tensor.html
- Time evolution overview — https://qutip.readthedocs.io/en/stable/guide/guide-dynamics.html
- Master equation (`mesolve`/`sesolve`) — https://qutip.readthedocs.io/en/stable/guide/dynamics/dynamics-master.html
- Monte-Carlo solver (`mcsolve`) — https://qutip.readthedocs.io/en/stable/guide/dynamics/dynamics-monte.html
- Time-dependent Hamiltonians — https://qutip.readthedocs.io/en/stable/guide/dynamics/dynamics-time.html
- Steady-state solutions — https://qutip.readthedocs.io/en/stable/guide/guide-steady.html
- API reference — https://qutip.readthedocs.io/en/stable/apidoc/apidoc.html
- Entropy module source — https://qutip.readthedocs.io/en/v5.1.1/_modules/qutip/entropy.html
- Release paper (local) — `.knowledge/literature/software/1110.0573_qutip-an-open-source-python-framework-for-the-dynamics-of-op.md`
