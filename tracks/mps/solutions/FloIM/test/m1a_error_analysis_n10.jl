include(joinpath(@__DIR__, "..", "src", "augmented_tempo.jl"))

using .AugmentedTEMPO, UniformTEMPO, LinearAlgebra, KrylovKit, SparseArrays, Printf

const σx = ComplexF64[0 1; 1 0]
const σz = ComplexF64[1 0; 0 -1]
const I2 = Matrix{ComplexF64}(I, 2, 2)

const N = 10
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

const δref = π / 960
function ed_reference()
    nref = round(Int, T_MAX / δref)
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
    return sz1, E
end

function run_tebd(δt, maxdim)
    pt0 = UniformPTMPO(2, δt)
    G_half = bond_superop(exp(-1im * J * kron(σz, σz) * δt / 2))
    n = round(Int, T_MAX / δt)
    meas(amps, vl, t) = begin
        ts = capped_mps(amps, vl)
        (sz=sz_all(ts), E=energy_ising(ts, h_onsite(t), J))
    end
    times, rec = run_chain(pt0, N, h_onsite, G_half, n; cutoff=1e-13, maxdim=maxdim, measure=meas)
    sz1 = [r.sz[1] for r in rec]
    E = [r.E for r in rec]
    return collect(times), sz1, E
end

szref, Eref = ed_reference()
println("ED reference done"); flush(stdout)
ref_at(t) = (szref[round(Int, t / δref) + 1], Eref[round(Int, t / δref) + 1])

for (tag, δt, md) in [("δt=π/60,  χ=256 (M1a baseline)", π / 60, 256),
                      ("δt=π/120, χ=256", π / 120, 256),
                      ("δt=π/60,  χ=512", π / 60, 512)]
    times, sz1, E = run_tebd(δt, md)
    dsz = maximum(abs(sz1[i] - ref_at(times[i])[1]) for i in 1:length(times))
    dE = maximum(abs(E[i] - ref_at(times[i])[2]) for i in 1:length(times))
    println("$tag : max|Δ⟨σz_1⟩| = $(round(dsz, sigdigits=3)) , max|ΔE| = $(round(dE, sigdigits=3))")
    flush(stdout)
end
