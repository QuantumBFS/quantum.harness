---
name: using-itensors
description: Use when choosing or running ITensors.jl or ITensorMPS.jl for DMRG, TEBD, MPS calculations, tensor-network checks, or ITensors setup failures.
---

# ITensors

Use ITensors / ITensorMPS for the harness's canonical 1D and quasi-1D tensor-network workflows.

## Sources

- Stack contract: `skills/using-itensors/stack.toml`
- Method cards: `skills/method-mps/SKILL.md`, `skills/method-ltrg/SKILL.md`
- Install target: `make install itensors`
- Smoke test: `julia --project=julia-env -e 'using ITensors, ITensorMPS, KrylovKit, MPSKit'`

## Workflow

1. Consult `stack.toml` before setup and run `/setup-julia` first when Julia is not usable.
2. Pin lattice, boundary, conserved quantum numbers, bond dimension, sweeps, cutoff, initialization, and convergence observable.
3. Record energy, variance or residual proxy, discarded weight, and bond-dimension convergence.
4. Use cluster execution when bond dimension, cylinder width, or scans exceed the local threshold.

## Parameter setup

Use this section as the source for ITensors / MPS-specific reproduction knobs unless the paper or official code fixes a value. The `## Knobs` table below gives concrete starting points; the method card supplies the conceptual notation.

- System/operator: site type (`S=1/2`, `Electron`, etc.), length/width, boundary, conserved quantum numbers, MPO convention, long-range terms, and whether PBC forces a larger bond dimension.
- Algorithm: DMRG for ground states; imaginary-time TEBD when the paper uses a preparation/evolution route; real-time TEBD only when the target is dynamics.
- Accuracy: `maxdim`/bond-dimension schedule, sweep count, cutoff, noise schedule if needed, TEBD time step and total time, and Krylov/Trotter settings.
- Initialization: paper-stated state, product state in the target sector, random MPS, warm start, and seed policy.
- Measurements: observable, normalization, correlation range, measurement cadence, and whether edge effects require a bulk window.
- Validation: energy convergence vs sweep and `chi`, variance/residual proxy, discarded weight, `tau` extrapolation for TEBD, and small-size ED check when feasible.

## Knobs

Concrete starting points for the knobs in Parameter setup. DMRG and TEBD share the bond-dimension / cutoff controls.

### DMRG

| Knob | Effect | Starting point |
|---|---|---|
| `maxdim` schedule | Maximum bond dimension per sweep. Drives accuracy and cost. | Grow gently from ~10. Targets: 50–200 (1D chains), 200–1000 (cylinders), 1000+ (frustrated 2D). |
| `cutoff` | SVD truncation threshold. | `1e-10` for entry/medium accuracy; tighten for critical points or if variance is non-zero at convergence. |
| `nsweeps` | Number of sweeps. | 10–30; stop when the energy stops changing within accuracy goal. |
| Initial state | Random MPS or a product state in the target sector. | Product state for sectors (e.g., Néel for `S^z = 0`). Random for sectors without a clear product-state representative. |
| `noise` | Adds noise to break stuck states (older API). | Use only if convergence stalls. |

### TEBD

| Knob | Effect | Starting point |
|---|---|---|
| `τ` (Trotter step) | Trotter error scales as `τ^2` (2nd order). Smaller is more accurate but slower. | `0.05–0.1` for entry; reduce if energy not converged. |
| `T_total` | Imaginary-time evolution length. Need `T_total ≫ 1/Δ`. | Start at 10–20 (units where largest coupling = 1); extend until energy stops dropping. |
| `maxdim` | MPS bond dimension cap. | 50–200 for 1D entry-level. |
| `cutoff` | SVD truncation per gate application. | `1e-10`. |

## Code shape

### DMRG (ITensors.jl)

```julia
using ITensors, ITensorMPS

# 1. Build site indices
sites = siteinds("S=1/2", N; conserve_qns=true)   # use conserve_qns to pin S^z sector

# 2. Build the Hamiltonian as an MPO via OpSum
ampo = OpSum()
for j in 1:N-1
    ampo += "Sz", j, "Sz", j+1
    ampo += 0.5, "S+", j, "S-", j+1
    ampo += 0.5, "S-", j, "S+", j+1
end
H = MPO(ampo, sites)

# 3. Initial state — pick a state in the target sector
psi0 = MPS(sites, n -> isodd(n) ? "Up" : "Dn")     # Néel-like, S^z_total = 0 for even N

# 4. Sweep schedule (grow bond dimension)
nsweeps = 20
maxdim = [10, 20, 50, 100, 200, 200]
cutoff = [1e-10]

# 5. Run
energy, psi = dmrg(H, psi0; nsweeps, maxdim, cutoff, outputlevel=1)

# 6. Observables
sz = expect(psi, "Sz")
SiSj = correlation_matrix(psi, "Sz", "Sz")
```

For Hubbard / fermion problems, use `siteinds("Electron", N; conserve_qns=true)` and operators `"Cdagup"`, `"Cup"`, `"Cdagdn"`, `"Cdn"`, `"Nup"`, `"Ndn"`.

### TEBD (ITensors)

```julia
using ITensors, ITensorMPS

# 1. Sites + Hamiltonian (as ops or MPO)
sites = siteinds("S=1/2", N; conserve_qns=true)

# 2. Build Trotter gates (2nd-order Trotter shown)
function trotter_gates(sites, J, τ)
    gates = ITensor[]
    for j in 1:N-1
        s1, s2 = sites[j], sites[j+1]
        hj = J * (op("Sz", s1) * op("Sz", s2)
                + 0.5 * op("S+", s1) * op("S-", s2)
                + 0.5 * op("S-", s1) * op("S+", s2))
        push!(gates, exp(-τ/2 * hj))
    end
    append!(gates, reverse(gates))   # 2nd-order: half step forward, half backward
    return gates
end

# 3. Initial state
psi = MPS(sites, n -> isodd(n) ? "Up" : "Dn")

# 4. Imaginary-time sweep
gates = trotter_gates(sites, J, τ)
T_total = 20.0
n_steps = round(Int, T_total / τ)
for step in 1:n_steps
    psi = apply(gates, psi; cutoff=1e-10, maxdim=200)
    normalize!(psi)
end

# 5. Energy
energy = inner(psi', H, psi)
```

### LTRG (ITensors.jl)

The exact index layout and ITensor constructor details should be checked against the installed ITensors docs before writing a production script. The geometry is fixed by the caller's model and Trotter decomposition; the harness-level shape is:

```julia
using ITensors

# 1. Build local basis indices and primed copies for adjacent imaginary-time
#    layers. Use explicit tags so contractions are auditable.
s1 = Index(q, "site1")
s2 = Index(q, "site2")
s1p = prime(s1)
s2p = prime(s2)

# 2. Build a local Hamiltonian tensor h on the chosen local term and exponentiate
#    the imaginary-time gate.
h = ITensor(s1, s2, s1p, s2p)
# fill h from the caller's local Hamiltonian convention
gate = exp(-tau * h)

# 3. Interpret gate matrix elements as a local transfer tensor.
T = gate

# 4. If the chosen network geometry requires a local factorization, reshape and
#    SVD the transfer tensor into local factors.
U, S, V = svd(T, (s1, s2); maxdim = q^2)

# 5. Repeatedly absorb transfer tensors into the current boundary tensor network,
#    SVD-compress to Dc, normalize, and append log scale factors.
log_scales = Float64[]
for layer in 1:K
    # boundary = absorb_layer(boundary, local_factors)
    # boundary, spectrum = compress_boundary(boundary; maxdim = Dc)
    # scale = normalize_boundary!(boundary)
    # push!(log_scales, log(scale))
end

# 6. Contract the remaining boundary and combine it with log_scales to obtain
#    the partition function or free energy in the chosen normalization.
```

This is a shape, not a reusable library function. Production scripts should keep index tags explicit, write intermediate convergence data incrementally, and record the normalization convention alongside the output.

## Time estimate

Estimate from length `L`, local dimension `d`, bond dimension `chi`, number of sweeps or time steps, and whether symmetries are used.

- DMRG wall time scales roughly as `sweeps * L * chi^3` times the local MPO/site factor; memory scales roughly as `L * chi^2` tensors, with a factor for dtype and conserved-sector overhead.
- TEBD wall time scales as `time_steps * gates * chi^3`; memory follows the same MPS `L * chi^2` pattern.
- First-run Julia precompilation is setup time, not physics time; report it separately when estimating.
- For uncertain cases, a tiny probe may time a few low-`chi` sweeps or TEBD steps, then extrapolate to the paper `chi` and the largest local-PC-in-15-min setting.
