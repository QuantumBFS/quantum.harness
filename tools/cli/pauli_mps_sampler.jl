using LinearAlgebra
using Printf
using Random
using Statistics

function pauli_mps_tensor(A::Array{ComplexF64,3})
    s_dim, l_dim, r_dim = size(A)
    @assert s_dim == 2
    B = zeros(ComplexF64, 4, l_dim * l_dim, r_dim * r_dim)
    scale = inv(sqrt(2.0))
    for code in 0:3
        P = PAULI_MATRICES[code + 1]
        for lb in 1:l_dim, lk in 1:l_dim, rb in 1:r_dim, rk in 1:r_dim
            v = 0.0 + 0.0im
            for s in 1:2, t in 1:2
                v += conj(A[s, lb, rb]) * P[s, t] * A[t, lk, rk]
            end
            B[code + 1, (lb - 1) * l_dim + lk, (rb - 1) * r_dim + rk] = scale * v
        end
    end
    return B
end

function pauli_mps_tensors(psi, sites)
    return [pauli_mps_tensor(A) for A in mps_dense_arrays(psi, sites)]
end

function pauli_mps_amplitude(Bs::Vector{Array{ComplexF64,3}}, p::Vector{Int})
    @assert length(Bs) == length(p)
    env = ComplexF64[1.0]
    for i in eachindex(Bs)
        B = @view Bs[i][p[i] + 1, :, :]
        env = vec(transpose(env) * B)
    end
    @assert length(env) == 1
    return env[1]
end

function pauli_mps_squared_logweight(Bs::Vector{Array{ComplexF64,3}}, p::Vector{Int})
    a2 = abs2(pauli_mps_amplitude(Bs, p))
    return a2 == 0.0 ? -Inf : 2 * log(a2)
end

function compress_pauli_mps(Bs::Vector{Array{ComplexF64,3}}, maxdim::Int, cutoff::Float64)
    L = length(Bs)
    out = Vector{Array{ComplexF64,3}}(undef, L)
    carry = ones(ComplexF64, 1, 1)
    trunc_err = 0.0
    for i in 1:L
        B = Bs[i]
        d, l_dim, r_dim = size(B)
        keep_left = size(carry, 1)
        @assert size(carry, 2) == l_dim
        merged = zeros(ComplexF64, d, keep_left, r_dim)
        for code in 1:d, a in 1:keep_left, r in 1:r_dim
            v = 0.0 + 0.0im
            for l in 1:l_dim
                v += carry[a, l] * B[code, l, r]
            end
            merged[code, a, r] = v
        end
        mat = reshape(merged, d * keep_left, r_dim)
        if i < L
            F = svd(mat)
            keep = min(maxdim, length(F.S))
            while keep > 1 && F.S[keep] < cutoff
                keep -= 1
            end
            trunc_err += sum(abs2, F.S[(keep + 1):end]; init=0.0)
            out[i] = reshape(F.U[:, 1:keep], d, keep_left, keep)
            carry = Diagonal(F.S[1:keep]) * F.Vt[1:keep, :]
        else
            out[i] = reshape(mat, d, keep_left, r_dim)
        end
    end
    return out, trunc_err
end

struct PauliMPSBornSampler
    Bs::Vector{Array{ComplexF64,3}}
    right::Vector{Matrix{ComplexF64}}
    norm::Float64
end

function PauliMPSBornSampler(Bs::Vector{Array{ComplexF64,3}})
    L = length(Bs)
    right = Vector{Matrix{ComplexF64}}(undef, L + 1)
    right[L + 1] = ones(ComplexF64, 1, 1)
    for i in L:-1:1
        _, l_dim, _ = size(Bs[i])
        env = zeros(ComplexF64, l_dim, l_dim)
        for code in 0:3
            Bα = @view Bs[i][code + 1, :, :]
            env .+= Bα * right[i + 1] * Bα'
        end
        right[i] = env
    end
    norm = real(right[1][1, 1])
    norm > 0 || error("Pauli-MPS Born norm must be positive, got $norm")
    return PauliMPSBornSampler(Bs, right, norm)
end

pauli_mps_born_norm(s::PauliMPSBornSampler) = s.norm

function sample_pauli_string(s::PauliMPSBornSampler, rng::AbstractRNG)
    L = length(s.Bs)
    p = zeros(Int, L)
    left = ones(ComplexF64, 1, 1)
    for i in 1:L
        weights = zeros(Float64, 4)
        left_candidates = Vector{Matrix{ComplexF64}}(undef, 4)
        for code in 0:3
            Bα = @view s.Bs[i][code + 1, :, :]
            next_left = Bα' * left * Bα
            w = real(tr(next_left * s.right[i + 1]))
            weights[code + 1] = max(w, 0.0)
            left_candidates[code + 1] = next_left
        end
        total = sum(weights)
        total > 0 || error("No positive Born conditional weight at site $i")
        threshold = rand(rng) * total
        acc = 0.0
        chosen = 3
        for code in 0:3
            acc += weights[code + 1]
            if threshold <= acc
                chosen = code
                break
            end
        end
        p[i] = chosen
        left = left_candidates[chosen + 1]
    end
    return p
end

function log_mean_with_block_se(xs::Vector{Float64}, n_blocks::Int)
    n = length(xs)
    block = n ÷ n_blocks
    block < 1 && error("n_samples=$n is too small for n_blocks=$n_blocks")
    logs = Float64[]
    for b in 1:n_blocks
        lo = (b - 1) * block + 1
        hi = b == n_blocks ? n : b * block
        push!(logs, log(mean(@view xs[lo:hi])))
    end
    return log(mean(xs)), length(logs) > 1 ? std(logs) / sqrt(length(logs)) : 0.0
end

function pauli_mps_born_direct_logz4(Bs::Vector{Array{ComplexF64,3}};
                                     n_samples::Int=100_000,
                                     seed=0xD1EC7,
                                     n_blocks::Int=20,
                                     progress_label=nothing)
    sampler = PauliMPSBornSampler(Bs)
    rng = MersenneTwister(UInt32(seed))
    vals = Vector{Float64}(undef, n_samples)
    progress_every = max(1, n_samples ÷ n_blocks)
    for k in 1:n_samples
        p = sample_pauli_string(sampler, rng)
        vals[k] = abs2(pauli_mps_amplitude(Bs, p))
        if progress_label !== nothing && (k == n_samples || k % progress_every == 0)
            running_mean = mean(@view vals[1:k])
            running_logz4 = log(pauli_mps_born_norm(sampler)) + log(running_mean)
            @printf("      [%s sample %d/%d] logZ4=%+.8f mean_abs2=%.6e\n",
                    string(progress_label), k, n_samples, running_logz4, running_mean)
            flush(stdout)
        end
    end
    log_mean, se = log_mean_with_block_se(vals, n_blocks)
    return (
        logz4=log(pauli_mps_born_norm(sampler)) + log_mean,
        se=se,
        n_samples=n_samples,
        n_blocks=n_blocks,
        born_norm=pauli_mps_born_norm(sampler),
        mean_abs2=mean(vals),
    )
end

function pauli_mps_born_direct_cL(Bfull::Vector{Array{ComplexF64,3}},
                                  Bhalf::Vector{Array{ComplexF64,3}};
                                  n_samples::Int=100_000,
                                  seed=0xD1EC7,
                                  n_blocks::Int=20,
                                  progress_label=nothing)
    full_label = progress_label === nothing ? nothing : "$(progress_label) full"
    half_label = progress_label === nothing ? nothing : "$(progress_label) half"
    full = pauli_mps_born_direct_logz4(Bfull; n_samples=n_samples, seed=seed,
                                       n_blocks=n_blocks,
                                       progress_label=full_label)
    half = pauli_mps_born_direct_logz4(Bhalf; n_samples=n_samples,
                                       seed=UInt32(seed) + UInt32(0x9E37),
                                       n_blocks=n_blocks,
                                       progress_label=half_label)
    return (
        cL=full.logz4 - 2 * half.logz4,
        se=sqrt(full.se^2 + 4 * half.se^2),
        logz4_full=full.logz4,
        logz4_half=half.logz4,
        n_samples=n_samples,
        n_blocks=n_blocks,
        born_norm_full=full.born_norm,
        born_norm_half=half.born_norm,
        mean_abs2_full=full.mean_abs2,
        mean_abs2_half=half.mean_abs2,
        expectation_backend="pauli_mps_born_direct_sampling",
    )
end

@inline squared_pauli_matrix(Bα) = kron(Bα, Bα)

struct SquaredPauliMPSSampler
    Bs::Vector{Array{ComplexF64,3}}
    Cs::Vector{Array{ComplexF64,3}}
    right::Vector{Matrix{ComplexF64}}
    norm::Float64
end

function SquaredPauliMPSSampler(Bs::Vector{Array{ComplexF64,3}})
    L = length(Bs)
    Cs = Vector{Array{ComplexF64,3}}(undef, L)
    for i in 1:L
        _, l_dim, r_dim = size(Bs[i])
        C = zeros(ComplexF64, 4, l_dim^2, r_dim^2)
        for code in 0:3
            C[code + 1, :, :] .= squared_pauli_matrix(@view Bs[i][code + 1, :, :])
        end
        Cs[i] = C
    end
    right = Vector{Matrix{ComplexF64}}(undef, L + 1)
    right[L + 1] = ones(ComplexF64, 1, 1)
    for i in L:-1:1
        _, l_dim, _ = size(Cs[i])
        env = zeros(ComplexF64, l_dim, l_dim)
        for code in 0:3
            Cα = @view Cs[i][code + 1, :, :]
            env .+= Cα * right[i + 1] * Cα'
        end
        right[i] = env
    end
    norm = real(right[1][1, 1])
    norm > 0 || error("Squared Pauli-MPS norm must be positive, got $norm")
    return SquaredPauliMPSSampler(Bs, Cs, right, norm)
end

pauli_squared_mps_norm(s::SquaredPauliMPSSampler) = s.norm

function sample_pauli_string(s::SquaredPauliMPSSampler, rng::AbstractRNG)
    L = length(s.Bs)
    p = zeros(Int, L)
    left = ones(ComplexF64, 1, 1)
    for i in 1:L
        weights = zeros(Float64, 4)
        left_candidates = Vector{Matrix{ComplexF64}}(undef, 4)
        for code in 0:3
            Cα = @view s.Cs[i][code + 1, :, :]
            next_left = Cα' * left * Cα
            w = real(tr(next_left * s.right[i + 1]))
            weights[code + 1] = max(w, 0.0)
            left_candidates[code + 1] = next_left
        end
        total = sum(weights)
        total > 0 || error("No positive conditional weight at site $i")
        threshold = rand(rng) * total
        acc = 0.0
        chosen = 3
        for code in 0:3
            acc += weights[code + 1]
            if threshold <= acc
                chosen = code
                break
            end
        end
        p[i] = chosen
        left = left_candidates[chosen + 1]
    end
    return p
end

function logaddexp(a::Float64, b::Float64)
    a == -Inf && return b
    b == -Inf && return a
    m = max(a, b)
    return m + log(exp(a - m) + exp(b - m))
end

function bridge_ratio_from_logs(logf_on_f::Vector{Float64}, logg_on_f::Vector{Float64},
                                logf_on_g::Vector{Float64}, logg_on_g::Vector{Float64};
                                maxiter::Int=100, tol::Float64=1e-10)
    sf = length(logf_on_f) / (length(logf_on_f) + length(logf_on_g))
    sg = 1.0 - sf
    log_sf = log(sf)
    log_sg = log(sg)
    log_r = 0.0
    for _ in 1:maxiter
        sum_g = 0.0
        for k in eachindex(logf_on_g)
            logden = logaddexp(log_sf + logf_on_g[k], log_sg + log_r + logg_on_g[k])
            sum_g += logf_on_g[k] == -Inf ? 0.0 : exp(logf_on_g[k] - logden)
        end
        sum_f = 0.0
        for k in eachindex(logg_on_f)
            logden = logaddexp(log_sf + logf_on_f[k], log_sg + log_r + logg_on_f[k])
            sum_f += logg_on_f[k] == -Inf ? 0.0 : exp(logg_on_f[k] - logden)
        end
        log_r_new = log(sum_g / length(logf_on_g)) - log(sum_f / length(logg_on_f))
        abs(log_r_new - log_r) < tol && return exp(log_r_new)
        log_r = log_r_new
    end
    return exp(log_r)
end

function bridge_log_se(logf_on_f::Vector{Float64}, logg_on_f::Vector{Float64},
                       logf_on_g::Vector{Float64}, logg_on_g::Vector{Float64},
                       n_blocks::Int)
    n = min(length(logf_on_f), length(logf_on_g))
    block = n ÷ n_blocks
    block < 100 && return NaN
    cs = Float64[]
    for b in 1:n_blocks
        lo = (b - 1) * block + 1
        hi = b == n_blocks ? n : b * block
        r = bridge_ratio_from_logs(logf_on_f[lo:hi], logg_on_f[lo:hi],
                                   logf_on_g[lo:hi], logg_on_g[lo:hi])
        push!(cs, log(r))
    end
    return length(cs) > 1 ? std(cs) / sqrt(length(cs)) : NaN
end

function pauli_mps_bridge_cL(Bfull::Vector{Array{ComplexF64,3}},
                             Bhalf::Vector{Array{ComplexF64,3}};
                             n_samples::Int=100_000,
                             seed=0xBADC0DE,
                             n_blocks::Int=20)
    L = length(Bfull)
    H = length(Bhalf)
    @assert L == 2H
    full_sampler = SquaredPauliMPSSampler(Bfull)
    half_sampler = SquaredPauliMPSSampler(Bhalf)
    rng = MersenneTwister(UInt32(seed))
    logf_on_f = Vector{Float64}(undef, n_samples)
    logg_on_f = Vector{Float64}(undef, n_samples)
    logf_on_g = Vector{Float64}(undef, n_samples)
    logg_on_g = Vector{Float64}(undef, n_samples)

    p1 = zeros(Int, H)
    p2 = zeros(Int, H)
    for k in 1:n_samples
        pf = sample_pauli_string(full_sampler, rng)
        @inbounds for i in 1:H
            p1[i] = pf[i]
            p2[i] = pf[i + H]
        end
        logf_on_f[k] = pauli_mps_squared_logweight(Bfull, pf)
        logg_on_f[k] = pauli_mps_squared_logweight(Bhalf, p1) +
                       pauli_mps_squared_logweight(Bhalf, p2)

        p1g = sample_pauli_string(half_sampler, rng)
        p2g = sample_pauli_string(half_sampler, rng)
        pg = vcat(p1g, p2g)
        logf_on_g[k] = pauli_mps_squared_logweight(Bfull, pg)
        logg_on_g[k] = pauli_mps_squared_logweight(Bhalf, p1g) +
                       pauli_mps_squared_logweight(Bhalf, p2g)
    end

    ratio = bridge_ratio_from_logs(logf_on_f, logg_on_f, logf_on_g, logg_on_g)
    return (
        cL=log(ratio),
        se=bridge_log_se(logf_on_f, logg_on_f, logf_on_g, logg_on_g, n_blocks),
        ratio=ratio,
        n_samples=n_samples,
        norm_full=pauli_squared_mps_norm(full_sampler),
        norm_half=pauli_squared_mps_norm(half_sampler),
        expectation_backend="pauli_mps_exact_batched_bridge",
    )
end
