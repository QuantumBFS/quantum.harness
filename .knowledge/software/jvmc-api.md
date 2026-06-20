# jVMC — API + Examples Reference

GPU-accelerated, autodiff variational Monte Carlo (VMC) for neural quantum states (NQS), built on JAX + Flax. Computes ground states (via Stochastic Reconfiguration, SR) and real/imaginary-time dynamics (via the time-dependent variational principle, TDVP) for lattice many-body systems. Also handles open-system (Lindblad) dynamics through a POVM formulation.

- **What it is.** A NQS represents log ψ_θ(s) = f_θ(s) with a neural network f_θ. jVMC gives you the three core building blocks of any NQS algorithm: (1) evaluate/differentiate the network (`jVMC.vqs.NQS`), (2) sample p_θ(s) = |ψ_θ(s)|²/⟨ψ|ψ⟩ (`jVMC.sampler`), (3) evaluate operators on the fly (`jVMC.operator`). The `jVMC.util` module wires these into the SR/TDVP linear solve and ODE time-stepping.
- **Install.** `pip install jVMC` (pulls JAX, Flax, mpi4py, h5py). GPU build of JAX must be installed separately to use accelerators.
- **Math basics.** Ground state: minimize E(θ) = ⟨ψ|H|ψ⟩/⟨ψ|ψ⟩. SR update: θ⁽ⁿ⁺¹⟩ = θ⁽ⁿ⁾ − τ S⁻¹ ∂E (S = real part of quantum Fisher / Fubini-Study metric, S_kk' = ⟪(O_k)* O_k'⟫_c, O_k(s) = ∂_θk log ψ_θ(s)). SR = imaginary-time TDVP. Real-time TDVP: [[S]] θ̇ = −[[iF]], F_l = ⟪E_loc (O_l)*⟫_c. Both need regularized inversion of an ill-conditioned S.

Source: paper `2108.03409` (SciPost Phys. Codebases 2, DOI 10.21468/SciPostPhysCodeb.2) and live docs/source (see "Source links").

---

## Setup / global config

```python
import jax
jax.config.update("jax_enable_x64", True)   # ALWAYS do this first, before other jVMC imports
import jVMC
```

- 64-bit must be enabled at program start (SR/TDVP linear algebra is numerically sensitive — 32-bit gives unstable S inversions).
- `jVMC.global_defs.tCpx` / `tReal` — the complex/real dtypes used internally (use these in custom operators/nets).
- `export XLA_PYTHON_CLIENT_PREALLOCATE=false` — avoid JAX grabbing all GPU memory when several processes share a GPU.
- `jVMC.set_pmap_devices(...)` — choose which local devices each MPI process uses.
- **Data layout convention.** All arrays crossing the jVMC API carry two leading dimensions: a *device* dimension (D, for pmap across local accelerators) then a *batch* dimension (B). Custom net/operator functions are written for a **single** configuration; jVMC vectorizes them automatically.

---

## jVMC.vqs — variational quantum state

### `NQS` — wrapper around a Flax network

```python
jVMC.vqs.NQS(net, logarithmic=True, batchSize=1000, seed=1234,
             orbit=None, avgFun=avgFun_Coefficients_Exp)
```

Wraps a Flax Linen module (or a `(netReal, netImag)` tuple of two modules for separate amplitude/phase networks) into the interface the rest of jVMC uses. `net` encodes log ψ_θ(s).

- `net` — a `flax.linen.Module` (or tuple of two). For a single network either: holomorphic complex net (complex params + holomorphic activations), or non-holomorphic real net with 2 real outputs → log ψ = f⁽¹⁾ + i f⁽²⁾.
- `batchSize` — mini-batch size for evaluation; pick as large as memory allows (compute-bound regime). Fixed at construction.
- `seed` — PRNG seed for parameter init.

| Method | Purpose |
|---|---|
| `psi(s)` / `__call__(s)` | Return log ψ_θ(s) for a batch of configs (auto-vectorized; input has D×B leading dims). |
| `gradients(s)` | Logarithmic gradients O_k(s) = ∂_θk log ψ_θ(s). |
| `gradients_dict(s)` | Same, returned as a parameter-tree dictionary. |
| `get_parameters()` | Flat vector of all variational parameters. |
| `set_parameters(P)` | Overwrite all parameters with flat vector `P`. |
| `update_parameters(deltaP)` | Add `deltaP` to current parameters. |
| `get_sampler_net()` | Function evaluating Re part of NQS (used by the sampler). |

The single-input `__call__` of a custom net goes from 0/1 to ±1 spins itself if desired (`s = 2*s - 1`). For **autoregressive** sampling, the Flax module must also implement a `sample(self, numSamples, key)` member returning configurations — then `MCSampler` automatically does direct sampling instead of MCMC.

---

## jVMC.nets — network architectures

Pre-defined Flax modules (general design templates, meant to be extended). Pass the instance to `NQS`.

| Class | Constructor (key args) | Type | Autoregr. |
|---|---|---|---|
| `RBM` | `(numHidden=2, bias=False)` | real | no |
| `CpxRBM` | `(numHidden=2, bias=False)` | **complex** | no |
| `FFN` | `(layers=(10,), bias=False, actFun=elu)` | real | no |
| `CNN` | `(F=(8,), channels=(10,), strides=(1,), actFun=elu, bias=True, periodicBoundary=...)` | real | no |
| `CpxCNN` | `(F=(8,), channels=(10,), strides=(1,), actFun=poly6, bias=True)` | **complex** | no |
| `RNN1DGeneral` | `(L=10, hiddenSize=10, depth=1, inputDim=2, cell='RNN', realValuedOutput=..., realValuedParams=...)` | real/cpx | **yes** |
| `RNN2DGeneral` | `(L=10, hiddenSize=10, depth=1, inputDim=2, cell='RNN')` | real/cpx | **yes** |
| `SymNet` | `(orbit, net, avgFun=...)` | wraps any net | inherits |

- RBM (Eq. 38): log ψ = Σ a_i s_i + Σ log cosh(Σ W_ij s_j + b_j). `CpxRBM` = complex weights (holomorphic).
- `CNN` with `periodicBoundary=True` automatically incorporates translational symmetry (the paper's ground-state example).
- RNN cells: `'RNN'`, `'LSTM'`, `'GRU'`. RNNs are autoregressive → direct, uncorrelated sampling at cost of one net eval per sample (vs O(N) for MCMC).
- `SymNet` — wraps a base net to enforce lattice symmetries; `orbit` is the set of symmetry permutations (see `jVMC.util.symmetries`).

Custom architectures: subclass `flax.linen.Module`, implement `__call__(self, s)` (single config). Example RBM:

```python
class MyRBM(flax.linen.Module):
    numHidden: int = 2
    @flax.linen.compact
    def __call__(self, s):
        s = 2 * s - 1                                    # 0/1 -> +1/-1
        h = flax.linen.Dense(features=self.numHidden,
                             dtype=jVMC.global_defs.tCpx)(s)
        h = jax.numpy.log(jax.numpy.cosh(h))
        vbias = self.param("vbias", jax.nn.initializers.zeros, s.shape)
        return jax.numpy.sum(h) + jax.numpy.dot(vbias, s)
```

---

## jVMC.operator — Hamiltonians & observables

Operators implement on-the-fly matrix-element generation: Ô : s ↦ {s'_j}, {O_{s s'_j}} with O_{s s'_j} = ⟨s|Ô|s'_j⟩ ≠ 0.

### Building Hamiltonians: `BranchFreeOperator`

```python
jVMC.operator.BranchFreeOperator(lDim=2)
```

Composes many-body operators as tensor products of *branch-free* local operators (one nonzero entry per row/column — e.g. Pauli operators). Build by adding operator strings, then it compiles automatically on first use.

| Member | Purpose |
|---|---|
| `add(opDescr)` | Add one operator string (a tuple of single-site operators), or a scaled string from `scal_opstr`. |
| `compile()` | Return the jit-able mapping function (called internally). |
| `get_s_primes(s)` | For a batch s, return connected configs s'_j and matrix elements O_{ss'}. Shapes D×M×(spatial), D×M. |
| `get_O_loc(samples, psi, logPsiS=None, *args)` | Compute local estimator O_loc(s) = Σ_s' ⟨s\|Ô\|s'⟩ ψ(s')/ψ(s) for the batch. Returns D×B complex array. |

### Pre-defined single-site operators (spin-1/2, lDim=2)

`Sx(idx)`, `Sy(idx)`, `Sz(idx)` — Pauli operators σ at site `idx`.
`Sp(idx)`, `Sm(idx)` — raising/lowering S⁺, S⁻.
`number(idx)`, `creation(idx)`, `annihilation(idx)` — occupation / ladder operators.
`Id(idx=0, lDim=2)` — identity.

### Operator-string helper

```python
jVMC.operator.scal_opstr(a, op)   # scale an operator string by prefactor a (scalar or function of t)
```
`op` is a tuple of single-site operators forming a product, e.g. `(Sz(l), Sz(l+1))` for σᶻ_l σᶻ_{l+1}, or `(Sx(l),)` for a single-site term. A function-valued `a` enables time-dependent couplings.

### Example — transverse-field Ising: H = −Σ σᶻ_l σᶻ_{l+1} − g Σ σˣ_l (PBC)

```python
import jVMC.operator as op
hamiltonian = jVMC.operator.BranchFreeOperator()
for l in range(L):
    hamiltonian.add(op.scal_opstr(-1., (op.Sz(l), op.Sz((l + 1) % L))))
    hamiltonian.add(op.scal_opstr(g,  (op.Sx(l), )))
```

### Example — Heisenberg: H = J Σ (σˣσˣ + σʸσʸ + σᶻσᶻ)

```python
H = jVMC.operator.BranchFreeOperator()
for l in range(L - 1):
    H.add(op.scal_opstr(J, (op.Sx(l), op.Sx(l+1))))
    H.add(op.scal_opstr(J, (op.Sy(l), op.Sy(l+1))))
    H.add(op.scal_opstr(J, (op.Sz(l), op.Sz(l+1))))
```

### Custom operators — subclass `Operator`

```python
jVMC.operator.Operator(ElocBatchSize=-1)
```
Implement a `compile(self)` that returns a pure jit-able `get_s_primes(s, *args)` → `(sp, matEls)` acting on a **single** config. Must call `super().__init__()` in the subclass constructor. You then get `get_s_primes`, `get_O_loc`, `get_estimator_function` for free. (Full custom-operator template: `examples/ex1_custom_operator.py`.)

### Open systems — `POVMOperator`

```python
jVMC.operator.POVMOperator(povm, ldim=4, **kwargs)
```
Builds Lindblad time-evolution generators in the POVM (probabilistic) formalism for dissipative dynamics. Helpers: `get_M`, `get_unitaries`, `get_dissipators`, `get_observables`, `matrix_to_povm`, `measure_povm`. Observables are measured differently here (the operator generates the dynamics, not an expectation value). See `examples/ex5_dissipative_Lindblad.py`.

---

## jVMC.sampler — sampling p_θ(s)

Both samplers share a `sample()` returning `(configs, logPsi, probs)`. `probs` is |ψ|² for `ExactSampler`, `None` for `MCSampler` (Metropolis) since p is implicit in the chain.

### `MCSampler` — Metropolis-Hastings or autoregressive direct sampling

```python
jVMC.sampler.MCSampler(net, sampleShape, key, updateProposer=None, numChains=1,
                       updateProposerArg=None, numSamples=100, thermalizationSweeps=10,
                       sweepSteps=10, initState=None, mu=2, logProbFactor=0.5)
```

- `net` — the `NQS` object.
- `sampleShape` — shape of one configuration, e.g. `(L,)` for a chain.
- `key` — a `jax.random.PRNGKey`.
- `updateProposer` — signature `updateProposer(key, config, info)`, returns a proposed config. Pre-defined: `propose_spin_flip`, `propose_spin_flip_Z2` (Z₂-symmetric), `propose_spin_flip_zeroMag` (fixed magnetization), `propose_POVM_outcome`.
- `numChains` — vectorized parallel MCMC chains; ~100 is a good default sweet spot (too few underuses the GPU, too many saturates SMs).
- `numSamples` — total samples to produce (may be slightly exceeded to match array dims).
- `thermalizationSweeps` — burn-in sweeps; `sweepSteps` — proposals per sweep (typically = N, the system size).
- If `net` is autoregressive (has a `sample` member), direct sampling is used automatically and `updateProposer`/burn-in are irrelevant.

| Method | Purpose |
|---|---|
| `sample(parameters=None, numSamples=None, multipleOf=1)` | Draw samples → `(configs, logPsi, None)`. |
| `acceptance_ratio()` | Acceptance ratio of last MCMC call. |
| `get_last_number_of_samples()` | Actual sample count returned last call. |
| `set_number_of_samples(N)` / `set_random_key(key)` | Update defaults. |

### `ExactSampler` — full Hilbert-space enumeration

```python
jVMC.sampler.ExactSampler(net, sampleShape, lDim=2, logProbFactor=0.5)
```
Evaluates the net on **all** basis configs (no MC error; exponential cost). For small systems / debugging / exact dynamics. `sample()` → `(allConfigs, logPsi, probs)`.

---

## jVMC.util — TDVP/SR solver, steppers, drivers

### `TDVP` — the SR / TDVP linear-equation right-hand side

```python
jVMC.util.tdvp.TDVP(sampler, snrTol=2, pinvTol=1e-14, pinvCutoff=1e-8,
                    makeReal='imag', rhsPrefactor=1.j, diagonalShift=0.,
                    crossValidation=False, diagonalizeOnDevice=True)
```

Solves [[S]] θ̇ = −[[ x F]] and returns the (regularized) update θ̇. Callable as an ODE right-hand side — pass it to a stepper.

- `sampler` — `MCSampler` or `ExactSampler` instance.
- **Ground-state (SR)** config: `rhsPrefactor=1.`, `makeReal='real'`, `diagonalShift=ν` (>0, decayed each step), e.g. `svdTol`/`pinvTol≈1e-8`.
- **Real-time** config: `rhsPrefactor=1.j`, `makeReal='imag'`, use `pinvTol`/`snrTol` regularization (no diagonal shift).
- `makeReal` — `'real'` (q = Re, energy-conserving least-action TDVP / SR) or `'imag'` (q = Im).
- `diagonalShift` (ν) — diagonal regularization S̃ = (1 + ν δ) S; for SR only, decayed over steps.
- `pinvTol`/`pinvCutoff` (ε_pinv, ε_SVD) — pseudo-inverse cutoffs; drop S eigenvalues with |λ_j/λ_1| < cutoff.
- `snrTol` (ε_SNR) — signal-to-noise-ratio regularization for noisy TDVP components (real-time stability).
- `crossValidation` — cross-validation check of the TDVP solution (arXiv:2105.01054).
- `diagonalizeOnDevice` — diagonalize S on GPU (True) or CPU (set False if CUDA eigensolver is unstable on ill-conditioned S).

| Accessor | Returns |
|---|---|
| `get_energy_mean()` | Re ⟨E_loc⟩ (= `tdvpEquation.ElocMean0`). |
| `get_energy_variance()` | Var(E_loc) (= `tdvpEquation.ElocVar0`); → 0 in an exact eigenstate. |
| `get_S()` | The S-matrix. |
| `get_residuals()` | `(tdvp_err, solver_residual)`. |
| `get_snr()`, `get_spectrum()`, `get_metadata()` | SNR vector, S spectrum, diagnostics dict. |
| `set_diagonal_shift(δ)` | Update ν (used by the GS driver to decay it). |

### `MinSR` — minimal-step SR (large-parameter regime)

```python
jVMC.util.minsr.MinSR(sampler, pinvTol=1e-14, diagonalShift=0., diagonalizeOnDevice=True)
```
Alternative GS minimizer that works in the sample-space (T-matrix) rather than parameter-space S-matrix — efficient when #parameters ≫ #samples. Same callable/accessor interface as `TDVP`; drop-in for `ground_state_search`.

### Steppers — ODE integrators (`jVMC.util.stepper`)

```python
jVMC.util.stepper.Euler(timeStep=1e-3)
jVMC.util.stepper.AdaptiveHeun(timeStep=1e-3, tol=1e-8, maxStep=1)
jVMC.util.stepper.Heun(timeStep=1e-3)
```
Common interface:
```python
dp, dt = stepper.step(t, f, y, normFunction=jnp.linalg.norm, **rhsArgs)
```
`f` is the `TDVP`/`MinSR` instance; `y = psi.get_parameters()`; `rhsArgs` are forwarded to the TDVP call (`hamiltonian=`, `psi=`, `numSamples=`). `Euler` returns the proposed param update for fixed-step SR; `AdaptiveHeun` adapts `dt` to tolerance `tol` and returns the accepted `dt` (use for real-time). For real-time a Fisher-metric `normFunction` improves step sizing.

### `measure(observables, psi, sampler, numSamples=None)`

Measure expectation values of a dict of operators. `observables = {"name": operator | [op1, op2] | [(op, *args)]}`. Returns `{name: {"mean": [...], "variance": [...], "MC_error": [...]}}`.

### `ground_state_search(psi, ham, tdvpEquation, sampler, numSteps=200, varianceTol=1e-10, stepSize=1e-2, observables=None, outp=None)`

High-level SR driver: internally builds an `Euler(timeStep=stepSize)`, loops up to `numSteps` (or until energy variance < `varianceTol`), decays the diagonal shift by ×0.95/step, and optionally measures `observables` and logs through an `OutputManager`.

### Other utilities
- `jVMC.util.util.init_net(descr, dims, seed=0)` — build a net from a descriptor dict.
- `jVMC.util.symmetries` — returns lattice symmetry permutation sets (orbits) for `SymNet`.
- `jVMC.util.OutputManager` — HDF5 I/O (`write_observables`, `write_metadata`, `write_network_checkpoint`, `get_network_checkpoint`, MPI-safe `print`).
- `jVMC.mpi_wrapper` — distributed-sample reductions: `get_global_mean`, `get_global_variance`, `get_global_covariance`, `get_global_sum`, `distribute_sampling`.

---

## Worked example 1 — ground-state search (verbatim, `examples/ex0_ground_state_search.py`)

```python
import jax
jax.config.update("jax_enable_x64", True)

import jax.random as random
import jax.numpy as jnp
import flax.linen as nn

import numpy as np
import matplotlib.pyplot as plt

import jVMC

L = 10
g = -0.7

# Check whether GPU is available
GPU_avail = ( jax.lib.xla_bridge.get_backend().platform == "gpu" )
# Initialize net
if GPU_avail:
    # reproduces results in Fig. 3 of the paper
    # estimated run_time in colab (GPU enabled): ~26 minutes
    def myActFun(x):
        return 1 + nn.elu(x)
    net = jVMC.nets.CNN(F=(L,), channels=(16,), strides=(1,), periodicBoundary=True, actFun=(myActFun,))
    n_steps = 1000
    n_Samples = 40000
else:
    # may be used to obtain results on Laptop CPUs
    # estimated run_time: ~100 seconds
    net = jVMC.nets.CpxRBM(numHidden=8, bias=False)
    n_steps = 300
    n_Samples = 5000


psi = jVMC.vqs.NQS(net, seed=1234)  # Variational wave function


def energy_single_p_mode(h_t, P):
    return np.sqrt(1 + h_t**2 - 2 * h_t * np.cos(P))


def ground_state_energy_per_site(h_t, N):
    Ps = 0.5 * np.arange(- (N - 1), N - 1 + 2, 2)
    Ps = Ps * 2 * np.pi / N
    energies_p_modes = np.array([energy_single_p_mode(h_t, P) for P in Ps])
    return - 1 / N * np.sum(energies_p_modes)


exact_energy = ground_state_energy_per_site(g, L)
print(exact_energy)

# Set up hamiltonian
hamiltonian = jVMC.operator.BranchFreeOperator()
for l in range(L):
    hamiltonian.add(jVMC.operator.scal_opstr(-1., (jVMC.operator.Sz(l), jVMC.operator.Sz((l + 1) % L))))
    hamiltonian.add(jVMC.operator.scal_opstr(g, (jVMC.operator.Sx(l), )))

# Set up sampler
sampler = jVMC.sampler.MCSampler(psi, (L,), random.PRNGKey(4321), updateProposer=jVMC.sampler.propose_spin_flip_Z2,
                                 numChains=100, sweepSteps=L,
                                 numSamples=n_Samples, thermalizationSweeps=25)

# Set up TDVP
tdvpEquation = jVMC.util.tdvp.TDVP(sampler, rhsPrefactor=1.,
                                   svdTol=1e-8, diagonalShift=10, makeReal='real')

stepper = jVMC.util.stepper.Euler(timeStep=1e-2)  # ODE integrator

res = []
for n in range(n_steps):

    dp, _ = stepper.step(0, tdvpEquation, psi.get_parameters(), hamiltonian=hamiltonian, psi=psi, numSamples=None)
    psi.set_parameters(dp)

    print(n, jax.numpy.real(tdvpEquation.ElocMean0) / L, tdvpEquation.ElocVar0 / L)

    res.append([n, jax.numpy.real(tdvpEquation.ElocMean0) / L, tdvpEquation.ElocVar0 / L])

res = np.array(res)

fig, ax = plt.subplots(2, 1, sharex=True, figsize=[4.8, 4.8])
ax[0].semilogy(res[:, 0], res[:, 1] - exact_energy, '-', label=r"$L=" + str(L) + "$")
ax[0].set_ylabel(r'$(E-E_0)/L$')

ax[1].semilogy(res[:, 0], res[:, 2], '-')
ax[1].set_ylabel(r'Var$(E)/L$')
ax[0].legend()
plt.xlabel('iteration')
plt.tight_layout()
plt.savefig('gs_search.pdf')
```

The same logic via the high-level driver:
```python
tdvpEquation = jVMC.util.tdvp.TDVP(sampler, rhsPrefactor=1., svdTol=1e-8,
                                   diagonalShift=10, makeReal='real')
jVMC.util.ground_state_search(psi, hamiltonian, tdvpEquation, sampler,
                              numSteps=300, stepSize=1e-2)
```

## Worked example 2 — real-time (unitary) dynamics (verbatim, `examples/ex2_unitary_time_evolution.py`)

```python
import os

import jax
jax.config.update("jax_enable_x64", True)

import numpy as np

import time

import jVMC
from jVMC.util import measure
import jVMC.operator as op

import matplotlib.pyplot as plt


L = 6
g = -0.7
h = 0.1

dt = 1e-3  # Initial time step
integratorTol = 1e-4  # Adaptive integrator tolerance
tmax = 2  # Final time

# Set up variational wave function
net = jVMC.nets.CpxRBM(numHidden=10, bias=True)

psi = jVMC.vqs.NQS(net, seed=1234)  # Variational wave function

# Set up hamiltonian
hamiltonian = jVMC.operator.BranchFreeOperator()
for l in range(L):
    hamiltonian.add(op.scal_opstr(-1., (op.Sz(l), op.Sz((l + 1) % L))))
    hamiltonian.add(op.scal_opstr(g, (op.Sx(l), )))
    hamiltonian.add(op.scal_opstr(h, (op.Sz(l),)))

# Set up observables
observables = {
    "energy": hamiltonian,
    "X": jVMC.operator.BranchFreeOperator(),
}
for l in range(L):
    observables["X"].add(op.scal_opstr(1. / L, (op.Sx(l), )))

sampler = None
# Set up exact sampler
sampler = jVMC.sampler.ExactSampler(psi, L)

# Set up TDVP
tdvpEquation = jVMC.util.tdvp.TDVP(sampler, pinvTol=1e-8,
                                   rhsPrefactor=1.j,
                                   makeReal='imag')

t = 0.0  # Initial time

# Set up stepper
stepper = jVMC.util.stepper.AdaptiveHeun(timeStep=dt, tol=integratorTol)

# Measure initial observables
obs = measure(observables, psi, sampler)
data = []
data.append([t, obs["energy"]["mean"][0], obs["X"]["mean"][0]])

plt.ion()
plt.xlim(0, tmax)
plt.ylim(0, 1)
plt.legend()
plt.ylabel(r"Transverse magnetization $\langle X\rangle$")
plt.xlabel(r"Time $\langle Jt\rangle$")

while t < tmax:
    tic = time.perf_counter()
    print(">  t = %f\n" % (t))

    # TDVP step
    dp, dt = stepper.step(0, tdvpEquation, psi.get_parameters(), hamiltonian=hamiltonian, psi=psi)
    psi.set_parameters(dp)
    t += dt

    # Measure observables
    obs = measure(observables, psi, sampler)
    data.append([t, obs["energy"]["mean"][0], obs["X"]["mean"][0]])

    # Write some meta info to screen
    print("   Time step size: dt = %f" % (dt))
    tdvpErr, tdvpRes = tdvpEquation.get_residuals()
    print("   Residuals: tdvp_err = %.2e, solver_res = %.2e" % (tdvpErr, tdvpRes))
    print("    Energy = %f +/- %f" % (obs["energy"]["mean"], obs["energy"]["MC_error"]))
    toc = time.perf_counter()
    print("   == Total time for this step: %fs\n" % (toc - tic))

    # Plot data
    npdata = np.array(data)
    plt.plot(npdata[:, 0], npdata[:, 2], c="red")
    plt.pause(0.05)
```

Note the SR↔TDVP knob differences: GS uses `rhsPrefactor=1., makeReal='real'` + `Euler`; real-time uses `rhsPrefactor=1.j, makeReal='imag'` + `AdaptiveHeun`.

---

## Pitfalls

- **64-bit JAX is mandatory.** `jax.config.update("jax_enable_x64", True)` at the very top, before importing jVMC. 32-bit makes the S-matrix inversion unstable and silently degrades SR/TDVP. Use `jVMC.global_defs.tCpx`/`tReal` in custom code so dtypes stay consistent.
- **S-matrix is ill-conditioned — regularize correctly per task.** GS: diagonal shift `diagonalShift=ν` (start large, e.g. 10, decay ×0.95/step) and/or pseudo-inverse cutoff `pinvTol/svdTol≈1e-8`. Real-time: do **not** use the diagonal shift (it biases the trajectory); use `pinvTol≈1e-8` plus the SNR cutoff `snrTol` (~2) to drop noisy components. Soft cutoffs avoid spurious discontinuities when eigenvalues cross the threshold.
- **Samples vs chains.** `numChains≈100` is the empirical GPU sweet spot — too few underuses the device, too many saturates the streaming multiprocessors and serializes. Set `sweepSteps≈N` and `thermalizationSweeps`≳20 for MCMC. More `numSamples` reduces MC error ∝ 1/√N and also tightens the SNR cutoff. Autoregressive nets (RNNs) give uncorrelated direct samples → skip burn-in entirely.
- **Complex vs real nets.** Three valid ansatz forms: single holomorphic complex net (`CpxRBM`/`CpxCNN`); single non-holomorphic real net with 2 outputs; or two separate real nets `(amp, phase)` passed as a tuple. Holomorphic + `makeReal='real'`/`'imag'` is the clean default. A purely real net cannot represent a sign/phase structure — wrong results for frustrated / dynamical problems.
- **GPU memory / batching.** Set `NQS(batchSize=...)` as large as memory allows to make net evals compute-bound (batching can speed forward passes >100×). On shared GPUs set `XLA_PYTHON_CLIENT_PREALLOCATE=false`. If the CUDA eigensolver chokes on a near-singular S, set `TDVP(..., diagonalizeOnDevice=False)` to diagonalize on CPU.
- **ExactSampler is exponential.** Great for debugging / small-L exact dynamics, useless for production sizes. Switch to `MCSampler` once correctness is established.
- **Verify with convergence diagnostics.** Energy variance Var(E)/N → 0 marks an exact eigenstate (plot it alongside E). In real-time, watch `get_residuals()` (`tdvp_err`, solver residual) — growing residuals signal under-regularization or too few samples.

---

## Source links

- Paper (rendered): `.knowledge/literature/software/2108.03409_jvmc-versatile-and-performant-variational-monte-carlo-levera.md`; arXiv https://arxiv.org/abs/2108.03409 ; DOI https://doi.org/10.21468/SciPostPhysCodeb.2
- Docs index: https://jvmc.readthedocs.io/en/latest/
- Module API pages: https://jvmc.readthedocs.io/en/latest/vqs.html · /operator.html · /sampler.html · /nets.html · /util.html
- Repository: https://github.com/markusschmitt/vmc_jax
- Examples (source): https://github.com/markusschmitt/vmc_jax/tree/master/examples — `ex0_ground_state_search.py/.ipynb`, `ex1_custom_operator.py`, `ex2_unitary_time_evolution.py`, `ex3_custom_net.py`, `ex4_benchmarking.py`, `ex5_dissipative_Lindblad.py`, `ex6_dissipative_Lindblad_2D.py`, `ex7_fermions.ipynb`
- Source modules referenced: `jVMC/util/tdvp.py`, `jVMC/util/minsr.py`, `jVMC/util/stepper.py`, `jVMC/util/util.py`, `jVMC/operator/branch_free.py`, `jVMC/sampler.py`
- Citation: M. Schmitt, M. Reh, *jVMC: Versatile and performant variational Monte Carlo leveraging automated differentiation and GPU acceleration*, SciPost Phys. Codebases 2 (2022).
