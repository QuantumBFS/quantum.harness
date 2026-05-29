---
name: using-itensors
description: Use when choosing or running ITensors.jl or ITensorMPS.jl for DMRG, TEBD, MPS calculations, tensor-network checks, or ITensors setup failures.
---

# ITensors

Software-stack skill for ITensors.jl / ITensorMPS.jl — the harness's canonical 1D and quasi-1D tensor-network workflows. It owns the **software layer**: run mechanics, **software parameters (step 3)**, and the **time estimate (feeds step 4)**. It is the **step-2 handoff target** from `/method-mps` (DMRG/TEBD) and `/method-ltrg`.

It does **not** own method selection or the method algorithm / "why" — the DMRG, TEBD, and LTRG algorithms and their convergence criteria live in `/method-mps` and `/method-ltrg` (`## Details`); model choice → `.knowledge/models/`; paper figure facts → `/reproduce-paper`. This card carries the ITensors API surface and parameter values to *express* those methods, not the methods themselves.

## Sources

- Stack contract: `skills/using-itensors/stack.toml`
- Method cards: `skills/method-mps/SKILL.md`, `skills/method-ltrg/SKILL.md`
- Install target: `make install itensors`
- Smoke test: `julia --project=julia-env -e 'using ITensors, ITensorMPS, KrylovKit, MPSKit'`
- Official docs (verify the current API here — there is no in-repo software paper): `https://docs.itensor.org/ITensors/dev/`, ITensorMPS.jl `https://github.com/ITensor/ITensorMPS.jl`

## What ITensors is — step 2 (the handoff target)

What `/method-mps` and `/method-ltrg` route here for, and what to confirm before running.

- **The library.** ITensors.jl with ITensorMPS.jl — a Julia tensor-network library (the ITensor collaboration; Fishman, White, Stoudenmire). Typed indices with automatic contraction matching, block-sparse storage when quantum numbers are conserved, BLAS-backed dense contraction. ITensorMPS.jl carries the MPS/MPO/DMRG/TEBD layer.
- **Canonical for** DMRG ground states, imaginary-/real-time TEBD, and MPS measurements; the official docs ship a large worked-example ecosystem (DMRG, TEBD, DMRG-X, quantum-number conservation).
- **Efficiency.** Dense contraction via BLAS; large speedups from block-sparse tensors when `conserve_qns` is on; first-run Julia precompilation is setup time, not physics time.
- **Features to confirm fit the target** before routing here: a built-in site type (`S=1/2`, `Electron`, …), quantum-number conservation, `OpSum` → `MPO` Hamiltonian build, `dmrg` / `apply`, and `svd` with `maxdim` / `cutoff`. Confirm the current spelling against the official docs in *Sources* — the ITensors / ITensorMPS split moved several names.

## Run mechanics

1. Consult `stack.toml` before setup and run `/setup-julia` first when Julia is not usable.
2. Pin lattice, boundary, conserved quantum numbers, bond dimension, sweeps, cutoff, initialization, and the convergence observable (the values come from *Parameters*; the convergence *criteria* are the method card's).
3. Record energy, variance or residual proxy, discarded weight, and bond-dimension convergence.
4. Use cluster execution (`/using-slurm`) when bond dimension, cylinder width, or scans exceed the local threshold.

### DMRG

```julia
using ITensors, ITensorMPS

sites = siteinds("S=1/2", N; conserve_qns=true)        # conserve_qns pins the S^z sector

ampo = OpSum()                                          # Hamiltonian as an MPO
for j in 1:N-1
    ampo += "Sz", j, "Sz", j+1
    ampo += 0.5, "S+", j, "S-", j+1
    ampo += 0.5, "S-", j, "S+", j+1
end
H = MPO(ampo, sites)

psi0 = MPS(sites, n -> isodd(n) ? "Up" : "Dn")          # initial state in the target sector

nsweeps = 20
maxdim  = [10, 20, 50, 100, 200, 200]                   # grow the bond dimension per sweep
cutoff  = [1e-10]
energy, psi = dmrg(H, psi0; nsweeps, maxdim, cutoff, outputlevel=1)

sz   = expect(psi, "Sz")
SiSj = correlation_matrix(psi, "Sz", "Sz")
```

For Hubbard / fermion problems use `siteinds("Electron", N; conserve_qns=true)` and operators `"Cdagup"`, `"Cup"`, `"Cdagdn"`, `"Cdn"`, `"Nup"`, `"Ndn"`.

### TEBD

```julia
using ITensors, ITensorMPS

sites = siteinds("S=1/2", N; conserve_qns=true)

function trotter_gates(sites, J, τ)                     # 2nd-order Trotter: half-step forward + reverse
    gates = ITensor[]
    for j in 1:N-1
        s1, s2 = sites[j], sites[j+1]
        hj = J * (op("Sz", s1) * op("Sz", s2)
                + 0.5 * op("S+", s1) * op("S-", s2)
                + 0.5 * op("S-", s1) * op("S+", s2))
        push!(gates, exp(-τ/2 * hj))
    end
    append!(gates, reverse(gates))
    return gates
end

psi   = MPS(sites, n -> isodd(n) ? "Up" : "Dn")
gates = trotter_gates(sites, J, τ)
for step in 1:round(Int, T_total / τ)
    psi = apply(gates, psi; cutoff=1e-10, maxdim=200)
    normalize!(psi)
end
energy = inner(psi', H, psi)
```

### LTRG primitives

The LTRG algorithm — build local transfer tensors, then repeatedly absorb a layer into the boundary, SVD-truncate to `Dc`, normalize, and accumulate log scale factors — is owned by `/method-ltrg` (`## Details`). ITensors supplies the primitives to express it; keep index tags explicit, write convergence data incrementally, and record the normalization convention with the output.

```julia
using ITensors

s1, s2 = Index(q, "site1"), Index(q, "site2")           # typed local-basis indices, primed for adjacent layers
gate   = exp(-tau * h)                                   # imaginary-time gate from local h(s1,s2,s1',s2')
U, S, V = svd(T, (s1, s2); maxdim = Dc, cutoff = 1e-12)  # truncate the boundary to Dc
```

## Parameters — step 3 (software)

The source for ITensors / MPS-specific reproduction knobs unless the paper or official code fixes a value. Starting points are software practice, not paper-anchored: begin from each, then converge it — the convergence check (`maxdim`/bond dimension, `cutoff`, sweep count), not the starting number, is what makes the result trustworthy.

What to pin:

- **System / operator:** site type, length / width, boundary, conserved quantum numbers, MPO convention, long-range terms, and whether PBC forces a larger bond dimension.
- **Algorithm:** DMRG for ground states; imaginary-time TEBD for a preparation / evolution route; real-time TEBD only for dynamics.
- **Accuracy:** `maxdim` schedule, sweep count, `cutoff`, noise schedule if needed, TEBD time step and total time, Krylov/Trotter settings.
- **Initialization:** paper-stated state, product state in the target sector, random MPS, warm start, seed policy.
- **Measurements:** observable, normalization, correlation range, cadence, and whether edge effects require a bulk window.
- **Convergence diagnostics the tool exposes:** energy vs sweep and `chi`, variance / residual proxy, discarded weight, `tau` extrapolation for TEBD. The *criteria* for "converged" are the method card's.

Concrete starting points (DMRG and TEBD share the bond-dimension / cutoff controls):

### DMRG

| Knob | Effect | Starting point |
|---|---|---|
| `maxdim` schedule | Maximum bond dimension per sweep. Drives accuracy and cost. | Grow gently from ~10. Targets: 50–200 (1D chains), 200–1000 (cylinders), 1000+ (frustrated 2D). |
| `cutoff` | SVD truncation threshold. | `1e-10` for entry/medium accuracy; tighten for critical points or if variance is non-zero at convergence. |
| `nsweeps` | Number of sweeps. | 10–30; stop when the energy stops changing within the accuracy goal. |
| Initial state | Random MPS or a product state in the target sector. | Product state for sectors (e.g. Néel for `S^z = 0`); random when there is no clear product-state representative. |
| `noise` | Adds noise to break stuck states (older API). | Use only if convergence stalls. |

### TEBD

| Knob | Effect | Starting point |
|---|---|---|
| `τ` (Trotter step) | Trotter error scales as `τ^2` (2nd order). Smaller is more accurate but slower. | `0.05–0.1` for entry; reduce if energy not converged. |
| `T_total` | Imaginary-time evolution length. Need `T_total ≫ 1/Δ`. | Start at 10–20 (units where the largest coupling = 1); extend until energy stops dropping. |
| `maxdim` | MPS bond dimension cap. | 50–200 for 1D entry-level. |
| `cutoff` | SVD truncation per gate application. | `1e-10`. |

## Caller Contract

The scientific values — model, lattice, sectors, observable, bond-dimension target, convergence criteria, validation target — are caller-supplied; resolve open ones via the step-4 brainstorm, deferring the method algorithm / "why" and the convergence criteria to `/method-mps` or `/method-ltrg` and model physics to the model card. This skill turns agreed values into a runnable ITensors script; it does not originate them.

## Time estimate — feeds step 4

Estimate from length `L`, local dimension `d`, bond dimension `chi`, sweeps / time steps, and whether symmetries are used; the result feeds `/reproduce-paper`'s step-4 resource confirmation.

- DMRG wall time scales roughly as `sweeps · L · chi^3` times the local MPO/site factor; memory roughly `L · chi^2` tensors, with a dtype and conserved-sector factor.
- TEBD wall time scales as `time_steps · gates · chi^3`; memory follows the same `L · chi^2` pattern.
- First-run Julia precompilation is setup time, not physics time; report it separately.
- For uncertain cases, a tiny probe may time a few low-`chi` sweeps or TEBD steps, then extrapolate to the paper `chi` and the largest local-PC-in-15-min setting.
