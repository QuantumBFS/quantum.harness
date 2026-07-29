include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))

using .AugmentedTEMPO, UniformTEMPO, LinearAlgebra, KrylovKit, SparseArrays, Printf

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]
const I2 = Matrix{ComplexF64}(I, 2, 2)

# M1(a) physics parameters (same as m0_m1_checks.jl) but small N:
# N=6 needs at most χ = 4^3 = 64 → with maxdim ≥ 64 truncation NEVER binds,
# so any deviation from the fine-step ED reference is pure Trotter error.
const N = 6
const J = 0.5; const HX = 0.5; const HZ = 0.3; const A = 1.0; const ωd = 2.5
const T_MAX = 5.0

site_op(op, i, N) = foldl(kron, [j == (N - i + 1) ? op : I2 for j in 1:N])

function sparse_H(N, t)
    H = spzeros(ComplexF64, 2^N, 2^N)
    for i in 1:(N - 1)
        H += J * sparse(site_op(σz, i, N) * site_op(σz, i + 1, N))
    end
    f = HZ + A * cos(ωd * t)
    for i in 1:N
        H += HX * sparse(site_op(σx, i, N)) + f * sparse(site_op(σz, i, N))
    end
    return H
end

h_onsite(t) = HX * σx + (HZ + A * cos(ωd * t)) * σz

# fine ED reference: midpoint rule with fixed absolute substep δref = π/960
const δref = π / 960
function ed_reference()
    nref = round(Int, T_MAX / δref)
    times = (0:nref) .* δref
    sz1 = zeros(nref + 1); E = zeros(nref + 1)
    ψ = zeros(ComplexF64, 2^N); ψ[1] = 1.0
    sz1[1] = 1.0
    E[1] = real(ψ' * sparse_H(N, 0.0) * ψ)
    for s in 1:nref
        tmid = (s - 0.5) * δref
        ψ, = exponentiate(-1im * sparse_H(N, tmid), δref, ψ; tol=1e-13)
        sz1[s + 1] = real(ψ' * site_op(σz, 1, N) * ψ)
        E[s + 1] = real(ψ' * sparse_H(N, s * δref) * ψ)
    end
    return times, sz1, E
end

function run_tebd(δt)
    pt0 = UniformPTMPO(2, δt)
    G_half = bond_superop(exp(-1im * J * kron(σz, σz) * δt / 2))
    n = round(Int, T_MAX / δt)
    # 观测量走 capped-MPS 收缩（N=6 时 maxdim=64 永不截断，残差即纯 Trotter）
    meas(amps, vl, t) = begin
        ts = capped_mps(amps, vl)
        (sz=sz_all(ts), E=energy_ising(ts, h_onsite(t), J))
    end
    times, rec = run_chain(pt0, N, h_onsite, G_half, n; cutoff=1e-13, maxdim=64, measure=meas)
    sz1 = [r.sz[1] for r in rec]
    E = [r.E for r in rec]
    return collect(times), sz1, E
end

tref, szref, Eref = ed_reference()
println("ED reference done (δref = π/960, $((length(tref) - 1)) substeps)"); flush(stdout)

function ref_at(t)
    s = round(Int, t / δref) + 1
    return szref[s], Eref[s]
end

println("\n δt        max|Δ⟨σz_1⟩|   max|ΔE|     ratio(ΔE)  (=4 → pure O(δt²) Trotter)")
prev = nothing
for δt in (π / 60, π / 120, π / 240)
    times, sz1, E = run_tebd(δt)
    dsz = maximum(abs(sz1[i] - ref_at(times[i])[1]) for i in 1:length(times))
    dE = maximum(abs(E[i] - ref_at(times[i])[2]) for i in 1:length(times))
    ratio = prev === nothing ? "     -" : lpad(string(round(prev / dE, digits=2)), 8)
    println(@sprintf(" π/%-4d   %.3e      %.3e   %s", round(Int, π / δt), dsz, dE, ratio))
    flush(stdout)
    global prev = dE
end
