"""
Weak self-dual point: measured toric code Born-weight sampling.

Optimized with two-stage decomposition:
  Stage 1: P(mh) ~ ||Core_mh * psi||^2  (enumerate 2^L horizontal outcomes)
  Stage 2: P(mv|mh) ~ ||D_v * phi||^2    (enumerate 2^L vertical outcomes)

At theta=pi/4, sum_mv D_v^2 = I, so the marginal factorizes.

Feasible for L <= 8 (2^8 = 256 outcomes per stage).
"""

using Random, LinearAlgebra, Statistics, Printf

# ====================================================================
# Measurement matrix
# ====================================================================

function measurement_matrix(theta::Real)
    c = cos(theta / 2)
    s = sin(theta / 2)
    return [c s; s -c]
end

# ====================================================================
# Core operator: depends only on horizontal outcomes mh
# ====================================================================

"""
Build the core operator Core_mh (2^L x 2^L) for a given horizontal outcome row.

Core(sigma, sigma') = delta(parity) * sum_{h0} prod_x M(mh_x, h0 XOR H_x)

where H_x = cumulative XOR of (sigma XOR sigma') up to site x.
"""
function build_core_operator(L::Int, M_mat::Matrix{Float64}, mh_row::Vector{Int})
    N = 2^L
    Core = zeros(Float64, N, N)

    for si in 0:(N-1)
        sigma = [(si >> (x-1)) & 1 for x in 1:L]
        sigma_parity = sum(sigma) % 2

        for spi in 0:(N-1)
            sp = [(spi >> (x-1)) & 1 for x in 1:L]
            sp_parity = sum(sp) % 2

            # Parity constraint
            if sigma_parity != sp_parity
                continue
            end

            # Cumulative XOR
            H = zeros(Int, L)
            acc = 0
            for x in 1:L
                acc = xor(acc, xor(sigma[x], sp[x]))
                H[x] = acc
            end

            # Sum over gauge choice h0
            val = 0.0
            for h0 in 0:1
                w = 1.0
                for x in 1:L
                    hx = xor(h0, H[x])
                    w *= M_mat[mh_row[x] + 1, hx + 1]
                end
                val += w
            end

            Core[si + 1, spi + 1] = val
        end
    end
    return Core
end

# ====================================================================
# Vertical diagonal operator
# ====================================================================

"""
Build the diagonal D_v vector (length 2^L) for given vertical outcomes.
D_v(sigma) = prod_x M(mv_x, sigma_x)
"""
function build_dv_vector(L::Int, M_mat::Matrix{Float64}, mv_row::Vector{Int})
    N = 2^L
    dv = ones(Float64, N)
    for idx in 0:(N-1)
        for x in 1:L
            sx = (idx >> (x-1)) & 1
            dv[idx + 1] *= M_mat[mv_row[x] + 1, sx + 1]
        end
    end
    return dv
end

# ====================================================================
# Full row transfer matrix (for Lyapunov computation)
# ====================================================================

function build_tc_row_transfer(L::Int, M_mat::Matrix{Float64},
                                mh_row::Vector{Int}, mv_row::Vector{Int})
    N = 2^L
    Core = build_core_operator(L, M_mat, mh_row)
    dv = build_dv_vector(L, M_mat, mv_row)
    return Diagonal(dv) * Core
end

# ====================================================================
# Two-stage exact Born sampler
# ====================================================================

"""
Sample one row of measurement outcomes from the Born distribution.

Stage 1: Enumerate 2^L horizontal outcomes, compute P(mh) ~ ||Core_mh * psi||^2
Stage 2: Given mh, enumerate 2^L vertical outcomes, compute P(mv|mh) ~ ||D_v * phi||^2
"""
function sample_row_born(L::Int, M_mat::Matrix{Float64}, psi::Vector{Float64},
                          rng::AbstractRNG; is_last::Bool=false)
    N = 2^L

    # Stage 1: sample horizontal outcomes mh
    weights_h = Float64[]
    cores = Vector{Matrix{Float64}}()

    for hid in 0:(N-1)
        mh_row = [(hid >> (x-1)) & 1 for x in 1:L]
        Core = build_core_operator(L, M_mat, mh_row)
        phi = Core * psi

        if is_last
            # Last row: project onto |0>
            w = phi[1]^2
        else
            w = sum(phi .^ 2)
        end

        push!(weights_h, w)
        push!(cores, Core)
    end

    # Normalize and sample
    total_h = sum(weights_h)
    if total_h == 0
        error("Zero total weight in stage 1")
    end
    weights_h ./= total_h
    hidx = _sample_categorical(rng, weights_h)
    mh_row = [(hidx - 1 >> (x-1)) & 1 for x in 1:L]

    # Get the sampled core and apply it
    phi = cores[hidx] * psi

    # Stage 2: sample vertical outcomes mv conditioned on mh
    weights_v = Float64[]
    mv_rows = Vector{Vector{Int}}()

    for vid in 0:(N-1)
        mv_row = [(vid >> (x-1)) & 1 for x in 1:L]
        dv = build_dv_vector(L, M_mat, mv_row)

        if is_last
            w = (dv[1] * phi[1])^2
        else
            w = sum((dv .* phi) .^ 2)
        end

        push!(weights_v, w)
        push!(mv_rows, copy(mv_row))
    end

    total_v = sum(weights_v)
    if total_v == 0
        error("Zero total weight in stage 2")
    end
    weights_v ./= total_v
    vidx = _sample_categorical(rng, weights_v)
    mv_row = mv_rows[vidx]

    # Update boundary state
    dv = build_dv_vector(L, M_mat, mv_row)
    psi_new = dv .* phi

    nrm = norm(psi_new)
    if nrm > 0
        psi_new ./= nrm
    end

    return mh_row, mv_row, psi_new
end

# ====================================================================
# Full trajectory sampler
# ====================================================================

function sample_tc_born_two_stage(L::Int, theta::Real, Ly::Int;
                                    rng::AbstractRNG = MersenneTwister())
    M_mat = measurement_matrix(theta)
    N = 2^L

    psi = zeros(Float64, N)
    psi[1] = 1.0  # |0> vacuum

    mh = zeros(Int, L, Ly)
    mv = zeros(Int, L, Ly)

    for y in 1:Ly
        mh_row, mv_row, psi = sample_row_born(L, M_mat, psi, rng;
                                                 is_last=(y == Ly))
        mh[:, y] = mh_row
        mv[:, y] = mv_row
    end

    return mh, mv
end

# ====================================================================
# Lyapunov spectrum (on-the-fly, memory-efficient)
# ====================================================================

function tc_leading_lyapunov(L::Int, M_mat::Matrix{Float64},
                              mh::Matrix{Int}, mv::Matrix{Int}, Ly::Int;
                              burn_in::Int = max(1, div(Ly, 10)))
    N = 2^L
    q = randn(N)
    q ./= norm(q)
    s = 0.0
    n_prod = 0
    for y in 1:Ly
        B = build_tc_row_transfer(L, M_mat, mh[:, y], mv[:, y])
        u = B * q
        a = norm(u)
        if a == 0.0
            return NaN
        end
        q = u ./ a
        if y > burn_in
            s += log(a)
            n_prod += 1
        end
    end
    return n_prod > 0 ? s / n_prod : NaN
end

function tc_lyapunov_spectrum(L::Int, M_mat::Matrix{Float64},
                               mh::Matrix{Int}, mv::Matrix{Int}, Ly::Int, k::Int;
                               burn_in::Int = max(1, div(Ly, 10)))
    N = 2^L
    Q = Matrix(qr(randn(N, k)).Q)
    s = zeros(k)
    n_prod = 0
    for y in 1:Ly
        B = build_tc_row_transfer(L, M_mat, mh[:, y], mv[:, y])
        Y = B * Q
        F = qr(Y)
        Qnew = Matrix(F.Q)
        R = F.R
        for i in 1:k
            if R[i, i] < 0
                Qnew[:, i] .= -Qnew[:, i]
                R[i, :] .= -R[i, :]
            end
        end
        if norm(Qnew' * Qnew - I) > 1e-10
            F2 = qr(Qnew)
            Qnew = Matrix(F2.Q)
        end
        Q = Qnew
        if y > burn_in
            for i in 1:k
                s[i] += log(abs(R[i, i]))
            end
            n_prod += 1
        end
    end
    return n_prod > 0 ? s ./ n_prod : fill(NaN, k)
end

# ====================================================================
# Helper
# ====================================================================

function _sample_categorical(rng::AbstractRNG, weights::Vector{Float64})
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

# ====================================================================
# Main benchmark
# ====================================================================

