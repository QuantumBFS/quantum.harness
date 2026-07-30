"""
Self-dual point: WHT-optimized Born sampler + SVD Lyapunov spectrum.

Uses Walsh-Hadamard Transform for O(N log N) matrix-vector products
instead of building full N x N Core matrices during sampling.

Usage: julia --project=@. scripts/self_dual_optimized.jl L [nsamp] [ly_factor]
"""

using Random, LinearAlgebra, Statistics, Printf

const THETA = pi / 4
const NK = 8

# ====================================================================
# WHT
# ====================================================================

function wht!(f::Vector{Float64})
    n = length(f); h = 1
    while h < n
        @inbounds for i in 1:2h:n
            for j in i:(i+h-1)
                x = f[j]; y = f[j + h]
                f[j] = x + y; f[j + h] = x - y
            end
        end
        h *= 2
    end
    return f
end

wht(f::Vector{Float64}) = wht!(copy(f))

function measurement_matrix(theta::Real)
    c = cos(theta / 2)
    s = sin(theta / 2)
    return [c s; s -c]
end

# ====================================================================
# Precomputation
# ====================================================================

struct Precomputed
    L::Int
    N::Int
    C_all::Vector{Vector{Float64}}
    Chat_all::Vector{Vector{Float64}}
    Chat_sq_all::Vector{Vector{Float64}}
    dv_all::Matrix{Float64}
    D_all::Matrix{Float64}
end

function precompute(L::Int, M_mat::Matrix{Float64})::Precomputed
    N = 2^L
    C_all = Vector{Vector{Float64}}(undef, N)
    Chat_all = Vector{Vector{Float64}}(undef, N)
    Chat_sq_all = Vector{Vector{Float64}}(undef, N)

    for hid in 0:(N-1)
        mh_row = Int[(hid >> (x-1)) & 1 for x in 1:L]
        C = zeros(Float64, N)
        for g in 0:(N-1)
            if isodd(count_ones(g))
                continue
            end
            val = 0.0
            for h0 in 0:1
                w = 1.0
                acc = 0
                for x in 1:L
                    gx = (g >> (x-1)) & 1
                    acc = xor(acc, gx)
                    w *= M_mat[mh_row[x] + 1, xor(h0, acc) + 1]
                end
                val += w
            end
            C[g + 1] = val
        end
        Chat = wht(C)
        C_all[hid + 1] = C
        Chat_all[hid + 1] = Chat
        Chat_sq_all[hid + 1] = abs2.(Chat)
    end

    dv_all = Matrix{Float64}(undef, N, N)
    D_all = Matrix{Float64}(undef, N, N)
    for vid in 0:(N-1)
        mv_row = Int[(vid >> (x-1)) & 1 for x in 1:L]
        dv = ones(Float64, N)
        for s in 0:(N-1)
            for x in 1:L
                sx = (s >> (x-1)) & 1
                dv[s + 1] *= M_mat[mv_row[x] + 1, sx + 1]
            end
        end
        dv_all[vid + 1, :] = dv
        D_all[vid + 1, :] = abs2.(dv)
    end

    return Precomputed(L, N, C_all, Chat_all, Chat_sq_all, dv_all, D_all)
end

# ====================================================================
# WHT-optimized Born sampler
# ====================================================================

function sample_categorical(rng::AbstractRNG, weights::Vector{Float64})
    total = sum(weights)
    r = rand(rng) * total
    cum = 0.0
    for (i, w) in enumerate(weights)
        cum += w
        if r <= cum
            return i
        end
    end
    return length(weights)
end

function sample_row_optimized(pc::Precomputed, psi::Vector{Float64},
                               rng::AbstractRNG; is_last::Bool=false)
    N = pc.N
    L = pc.L

    psi_hat = wht(psi)
    psi_hat_sq = abs2.(psi_hat)

    # Stage 1: sample horizontal outcomes
    if is_last
        weights_h = Float64[abs(dot(pc.Chat_all[hid + 1], psi_hat))^2 for hid in 0:(N-1)]
    else
        weights_h = Float64[dot(pc.Chat_sq_all[hid + 1], psi_hat_sq) for hid in 0:(N-1)]
    end

    total_h = sum(weights_h)
    if total_h == 0
        error("Zero total weight in stage 1")
    end
    weights_h ./= total_h
    hidx = sample_categorical(rng, weights_h)

    # Compute phi = Core * psi via WHT
    Chat_h = pc.Chat_all[hidx]
    phi = wht(Chat_h .* psi_hat)
    phi ./= N

    # Stage 2: sample vertical outcomes
    phi_sq = abs2.(phi)
    if is_last
        weights_v = Float64[(pc.dv_all[vid + 1, 1] * phi[1])^2 for vid in 0:(N-1)]
    else
        weights_v = pc.D_all * phi_sq
    end

    total_v = sum(weights_v)
    if total_v == 0
        error("Zero total weight in stage 2")
    end
    weights_v ./= total_v
    vidx = sample_categorical(rng, weights_v)

    # Update boundary state
    dv = pc.dv_all[vidx, :]
    psi_new = dv .* phi
    nrm = norm(psi_new)
    if nrm > 0
        psi_new ./= nrm
    end

    mh_row = Int[((hidx - 1) >> (x-1)) & 1 for x in 1:L]
    mv_row = Int[((vidx - 1) >> (x-1)) & 1 for x in 1:L]

    return mh_row, mv_row, psi_new
end

function sample_full_optimized(pc::Precomputed, Ly::Int; rng::AbstractRNG=MersenneTwister())
    N = pc.N
    L = pc.L
    psi = zeros(Float64, N)
    psi[1] = 1.0
    mh_mat = zeros(Int, L, Ly)
    mv_mat = zeros(Int, L, Ly)
    for y in 1:Ly
        mh_row, mv_row, psi = sample_row_optimized(pc, psi, rng; is_last=(y == Ly))
        mh_mat[:, y] = mh_row
        mv_mat[:, y] = mv_row
    end
    return mh_mat, mv_mat
end

# ====================================================================
# Transfer matrix product + SVD
# ====================================================================

function build_transfer_product(pc::Precomputed, mh_mat::Matrix{Int}, mv_mat::Matrix{Int})
    N = pc.N
    L = pc.L
    Ly = size(mh_mat, 2)
    P = Matrix{Float64}(I, N, N)
    for y in 1:Ly
        hid = sum(mh_mat[x, y] << (x-1) for x in 1:L)
        vid = sum(mv_mat[x, y] << (x-1) for x in 1:L)
        C_h = pc.C_all[hid + 1]
        dv = pc.dv_all[vid + 1, :]
        # Build Core matrix: Core[s+1, sp+1] = C_h[xor(s,sp)+1]
        Core_mat = zeros(Float64, N, N)
        for s in 0:(N-1)
            @inbounds for sp in 0:(N-1)
                Core_mat[s+1, sp+1] = C_h[xor(s, sp) + 1]
            end
        end
        # B = Diagonal(dv) * Core, P = B * P
        P = (Diagonal(dv) * Core_mat) * P
    end
    return P
end

function compute_spectrum(pc::Precomputed, mh_mat::Matrix{Int}, mv_mat::Matrix{Int}, Ly::Int)
    P = build_transfer_product(pc, mh_mat, mv_mat)
    sv_P = svd(P).S
    nk = min(NK, length(sv_P))
    gammas = log.(sv_P[1:nk]) ./ Ly
    return gammas
end

# ====================================================================
# Main
# ====================================================================

println("=" ^ 70)
println("Self-Dual Point: WHT-optimized Born sampler + SVD Lyapunov")
println("  theta = pi/4, NK = 8")
println("=" ^ 70)

Ls = [4, 6]
if length(ARGS) > 0
    Ls = parse.(Int, split(ARGS[1], ","))
end
nsamp_override = 0
if length(ARGS) > 1
    nsamp_override = parse(Int, ARGS[2])
end
ly_factor = 10
if length(ARGS) > 2
    ly_factor = parse(Int, ARGS[3])
end

function nsamples_for(L::Int)
    L <= 4 && return 200
    L <= 6 && return 100
    L <= 8 && return 50
    return 20
end

results_dir = joinpath(@__DIR__, "results")
mkpath(results_dir)

M_mat = measurement_matrix(THETA)

for L in Ls
    N = 2^L
    Ly = ly_factor * L
    nsamp = nsamp_override > 0 ? nsamp_override : nsamples_for(L)

    println("\n--- L = $L, Ly = $Ly, N = $N, samples = $nsamp ---")
    println("Precomputing...")
    t_pre = time()
    pc = precompute(L, M_mat)
    @printf("Precomputation done in %.1f seconds\n", time() - t_pre)

    # Warm up JIT
    println("Warming up JIT...")
    sample_full_optimized(pc, 2; rng=MersenneTwister(0))
    println("JIT warmup done.")

    csv_file = joinpath(results_dir, "self_dual_opt_L$(L).csv")
    open(csv_file, "w") do io
        println(io, "sample,gamma0,gamma1,gamma2,gamma3,gamma4,gamma5,gamma6,gamma7,Phi_L,d1,d2,d3,d4,d5,d6,d7")

        t0 = time()
        Phis = Float64[]
        all_deltas = Vector{Vector{Float64}}()

        for i in 1:nsamp
            rng = MersenneTwister(70000 + i * 37 + L * 11)
            mh, mv = sample_full_optimized(pc, Ly; rng=rng)

            gammas = compute_spectrum(pc, mh, mv, Ly)

           Phi = -2.0 * gammas[1]
            # Phi = -gamma_0: Casimir scaling applies to the amplitude (single-layer)
            # transfer matrix, NOT the Born probability Z_m=|A_m|^2.  Squaring would
            # double c_eff; the physical c_eff comes from the amplitude.  This matches
            # the Ising convention where Phi=-log(Z)/Ly=-gamma_0 gives c=1/2.
            Phi = -gammas[1]
            push!(Phis, Phi)

            deltas = [L / (2 * pi) * (gammas[1] - gammas[j]) for j in 2:length(gammas)]
            push!(all_deltas, deltas)

            println(io, "$i,$(join(round.(gammas, digits=8), ",")),$(round(Phi, digits=8)),$(join(round.(deltas, digits=8), ","))")

            if i % 10 == 0 || i == nsamp
                elapsed = time() - t0
                rate = i / elapsed
                eta = (nsamp - i) / rate
                @printf("  [%3d/%3d]  Phi = %8.4f  g0 = %8.5f  D1 = %8.5f  (%.1fs, ETA %.0fs)\n",
                        i, nsamp, Phi, gammas[1], deltas[1], elapsed, eta)
                flush(stdout)
                flush(io)
            end
        end

        mPhi = mean(Phis)
        sPhi = std(Phis) / sqrt(nsamp)
        @printf("\n  L=%2d:  Phi = %10.6f +/- %8.6f  (f = %.6f)\n",
                L, mPhi, sPhi, mPhi / L)

        mean_deltas = [mean([all_deltas[s][j] for s in 1:nsamp]) for j in 1:(NK-1)]
        err_deltas = [std([all_deltas[s][j] for s in 1:nsamp]) / sqrt(nsamp) for j in 1:(NK-1)]
        println("  Scaling dimensions:")
        for j in 1:min(NK-1, 5)
            @printf("    Delta_%d = %8.5f +/- %8.5f\n", j, mean_deltas[j], err_deltas[j])
        end
        flush(stdout)
    end
end

println("\n" * "=" ^ 70)
println("Done.")
println("=" ^ 70)
