"""
Born-weighted measured toric code for the weak self-dual critical point.

Implements:
  - Toric code PEPS transfer matrix for angle-θ measurements
  - Sequential Born sampling (exact for small L, MCMC for large L)
  - Lyapunov spectrum extraction for scaling dimensions Delta_m
  - Finite-size scaling for c_eff

The toric code ground state in the Z basis is a sum over closed-loop
configurations (B_p = +1).  Measuring each edge at angle θ from Z gives:

  <m|TC> = Σ_{closed loops s} Π_e M(m_e, s_e)

where M(m,s) is the measurement overlap matrix.  This sum is computed
via a transfer matrix on the 2^L-dimensional Z2 flux space.

At θ = π/4 (self-dual point), the Born-correlated disorder produces
c_eff ≈ 0.447 (arXiv:2502.14034).

Transfer matrix for row y:
  B_y(σ, σ') = D_v(σ) × Core(σ, σ')

where:
  D_v(σ) = Π_x M(m^v_x, σ_x)           [diagonal, vertical edge weights]
  Core(σ, σ') = δ(Σσ=Σσ') × Σ_{h0} Π_x M(m^h_x, h0 ⊕ H_x)

  H_x(σ,σ') = Σ_{j≤x} (σ_j ⊕ σ'_j) mod 2   [cumulative XOR]

The amplitude: <m|TC> = <0|B_1 B_2 ... B_Ly|0>  [open BC]
The Born weight: Z_m = |<m|TC>|^2

For c_eff, we use Φ_L = -gamma_0 where gamma_0 is the leading Lyapunov
exponent of the AMPLITUDE transfer matrices {B_y}.  The Born average
<gamma_0> over measurement outcomes gives the disorder-averaged free energy.
"""

using Random, LinearAlgebra, Statistics, Printf

# ====================================================================
# Measurement matrix
# ====================================================================

"""
Measurement overlap matrix M(m, s) = <m_θ|s> where |s> is Z-basis and
|m_θ> is the measurement basis at angle θ from Z on the Bloch sphere.

  M(0, 0) =  cos(θ/2)     M(0, 1) =  sin(θ/2)
  M(1, 0) =  sin(θ/2)     M(1, 1) = -cos(θ/2)

At θ=0: Z measurement (M = identity up to sign)
At θ=π/2: X measurement (M = Hadamard / √2)
At θ=π/4: self-dual point
"""
function measurement_matrix(theta::Real)
    c = cos(theta / 2)
    s = sin(theta / 2)
    return [c s; s -c]
end

# ====================================================================
# Amplitude transfer matrix builder
# ====================================================================

"""
Build the 2^L × 2^L amplitude transfer matrix for one row.

  B_y(σ, σ') = D_v(σ) × Core(σ, σ')

where D_v is diagonal (vertical measurement weights on incoming state)
and Core encodes the vertex constraint and horizontal measurement weights.
"""
function build_tc_row_transfer(L::Int, theta::Real,
                                mh_row::Vector{Int},  # L horizontal outcomes
                                mv_row::Vector{Int})  # L vertical outcomes (incoming)
    N = 2^L
    M = measurement_matrix(theta)
    B = zeros(Float64, N, N)

    for sigma_idx in 0:(N-1)
        sigma = [(sigma_idx >> (x-1)) & 1 for x in 1:L]

        # Diagonal weight from vertical edges (on incoming state)
        dv = 1.0
        for x in 1:L
            dv *= M[mv_row[x] + 1, sigma[x] + 1]
        end
        if dv == 0.0
            continue
        end

        sigma_parity = sum(sigma) % 2

        for sp_idx in 0:(N-1)
            sp = [(sp_idx >> (x-1)) & 1 for x in 1:L]
            sp_parity = sum(sp) % 2

            # Vertex constraint: Σ(σ ⊕ σ') = 0 mod 2
            if sigma_parity != sp_parity
                continue
            end

            # Cumulative XOR: H_x = Σ_{j≤x} (σ_j ⊕ σ'_j)
            H = zeros(Int, L)
            acc = 0
            for x in 1:L
                acc ⊻= (sigma[x] ⊻ sp[x])
                H[x] = acc
            end

            # Sum over gauge choice h0 ∈ {0,1}
            core_val = 0.0
            for h0 in 0:1
                w = 1.0
                for x in 1:L
                    hx = h0 ⊻ H[x]
                    w *= M[mh_row[x] + 1, hx + 1]
                end
                core_val += w
            end

            B[sigma_idx + 1, sp_idx + 1] = dv * core_val
        end
    end
    return B
end

# ====================================================================
# Born amplitude computation
# ====================================================================

"""
Compute the Born amplitude <m|TC> = <0|B_1...B_Ly|0> in log space.
Uses sequential matrix-vector products with normalization.
"""
function tc_log_amplitude(L::Int, theta::Real,
                           mh::Matrix{Int}, mv::Matrix{Int}, Ly::Int)
    N = 2^L
    v = zeros(Float64, N)
    v[1] = 1.0  # |0> state

    log_scale = 0.0

    for y in 1:Ly
        B = build_tc_row_transfer(L, theta, mh[:, y], mv[:, y])
        v = B * v
        s = maximum(abs.(v))
        if s == 0.0
            return -Inf  # amplitude is exactly zero
        end
        v ./= s
        log_scale += log(s)
    end

    amp = v[1]  # <0|v> = v[1] for open BC
    if amp == 0.0
        return -Inf
    end
    return log_scale + log(abs(amp))
end

"""
Born weight Z_m = |<m|TC>|^2, returned as log Z_m.
"""
function tc_log_born_weight(L::Int, theta::Real,
                             mh::Matrix{Int}, mv::Matrix{Int}, Ly::Int)
    log_amp = tc_log_amplitude(L, theta, mh, mv, Ly)
    if log_amp == -Inf
        return -Inf
    end
    return 2.0 * log_amp
end

# ====================================================================
# Sequential Born sampling (exact, for small L ≤ 6)
# ====================================================================

"""
Sample measurement outcomes from the Born distribution P(m) ∝ |<m|TC>|^2.

Uses sequential row-by-row sampling with exact conditional probabilities.
At each row, enumerates all 2^{2L} possible outcomes and samples from
the exact conditional Born distribution.

Feasible for L ≤ 6 (2^{12} = 4096 outcomes per row).
"""
function sample_tc_born_exact(L::Int, theta::Real, Ly::Int;
                                rng::AbstractRNG = MersenneTwister())
    N = 2^L
    M_mat = measurement_matrix(theta)

    # Forward boundary state (starts at |0>)
    psi = zeros(Float64, N)
    psi[1] = 1.0

    mh = zeros(Int, L, Ly)
    mv = zeros(Int, L, Ly)

    n_outcomes = 2^(2L)

    for y in 1:Ly
        weights = Float64[]
        outcomes_mh = Vector{Vector{Int}}()
        outcomes_mv = Vector{Vector{Int}}()

        # Enumerate all possible row outcomes
        for oid in 0:(n_outcomes - 1)
            # Split oid into L horizontal + L vertical bits
            mh_row = [(oid >> (x - 1)) & 1 for x in 1:L]
            mv_row = [(oid >> (L + x - 1)) & 1 for x in 1:L]

            B = build_tc_row_transfer(L, theta, mh_row, mv_row)
            psi_new = B * psi

            if y < Ly
                # Weight = ||psi_new||^2 (will be projected later)
                w = sum(psi_new .^ 2)
            else
                # Last row: project onto |0>
                w = psi_new[1]^2
            end

            if w > 0
                push!(weights, w)
                push!(outcomes_mh, copy(mh_row))
                push!(outcomes_mv, copy(mv_row))
            end
        end

        if isempty(weights)
            error("No valid outcomes at row $y")
        end

        # Normalize and sample
        total = sum(weights)
        weights ./= total
        idx = _sample_categorical(rng, weights)

        mh[:, y] = outcomes_mh[idx]
        mv[:, y] = outcomes_mv[idx]

        # Update boundary state
        B = build_tc_row_transfer(L, theta, mh[:, y], mv[:, y])
        psi = B * psi
        nrm = norm(psi)
        if nrm > 0
            psi ./= nrm
        end
    end

    return mh, mv
end

# ====================================================================
# MCMC Born sampling (for any L)
# ====================================================================

"""
Sample measurement outcomes via Metropolis-Hastings MCMC.
Proposes single-edge flips and accepts/rejects based on Born weight ratio.
"""
function sample_tc_born_mcmc(L::Int, theta::Real, Ly::Int;
                               rng::AbstractRNG = MersenneTwister(),
                               n_sweeps::Int = 100, burn_in::Int = 20,
                               thin::Int = 1)
    # Initialize with random outcomes
    mh = rand(rng, 0:1, L, Ly)
    mv = rand(rng, 0:1, L, Ly)

    logZ_current = tc_log_born_weight(L, theta, mh, mv, Ly)

    samples_mh = Vector{Matrix{Int}}()
    samples_mv = Vector{Matrix{Int}}()

    n_edges = 2 * L * Ly
    accepted = 0
    proposed = 0

    for sweep in 1:(burn_in + n_sweeps)
        for _ in 1:n_edges
            # Propose flipping a random edge
            is_horizontal = rand(rng, Bool)
            x = rand(rng, 1:L)
            y = rand(rng, 1:Ly)

            # Flip
            if is_horizontal
                mh[x, y] = 1 - mh[x, y]
            else
                mv[x, y] = 1 - mv[x, y]
            end

            logZ_new = tc_log_born_weight(L, theta, mh, mv, Ly)

            # Metropolis acceptance (Born weight ratio)
            delta = logZ_new - logZ_current
            if delta >= 0 || log(rand(rng)) < delta
                logZ_current = logZ_new
                accepted += 1
            else
                # Reject: flip back
                if is_horizontal
                    mh[x, y] = 1 - mh[x, y]
                else
                    mv[x, y] = 1 - mv[x, y]
                end
            end
            proposed += 1
        end

        if sweep > burn_in && (sweep - burn_in) % thin == 0
            push!(samples_mh, copy(mh))
            push!(samples_mv, copy(mv))
        end
    end

    acc_rate = accepted / proposed
    return samples_mh, samples_mv, acc_rate
end

# ====================================================================
# Leading Lyapunov exponent (on-the-fly, memory-efficient)
# ====================================================================

"""
Compute the leading Lyapunov exponent of the amplitude transfer matrices.
Builds each row transfer matrix on-the-fly and discards after use.
"""
function tc_leading_lyapunov(L::Int, theta::Real,
                              mh::Matrix{Int}, mv::Matrix{Int}, Ly::Int;
                              burn_in::Int = max(1, Ly ÷ 10))
    N = 2^L
    q = randn(N)
    q ./= norm(q)

    s = 0.0
    n_prod = 0

    for y in 1:Ly
        B = build_tc_row_transfer(L, theta, mh[:, y], mv[:, y])
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

"""
Compute k Lyapunov exponents via Householder QR (on-the-fly).
"""
function tc_lyapunov_spectrum(L::Int, theta::Real,
                               mh::Matrix{Int}, mv::Matrix{Int}, Ly::Int, k::Int;
                               burn_in::Int = max(1, Ly ÷ 10))
    N = 2^L
    Q = Matrix(qr(randn(N, k)).Q)
    s = zeros(k)
    n_prod = 0

    for y in 1:Ly
        B = build_tc_row_transfer(L, theta, mh[:, y], mv[:, y])
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
# Helper: categorical sampling
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
# Main benchmark: weak self-dual point
# ====================================================================

const ALPHA = 1.0
const THETA_SELF_DUAL = pi / 4  # self-dual measurement angle
const NK = 6  # Lyapunov exponents to compute
const LY_FACTOR = 10

function nsamples_for(L::Int)
    L <= 4 && return 100
    L <= 8 && return 20
    return 10
end

println("=" ^ 70)
println("Weak Self-Dual Point: Measured Toric Code Born Weight")
println("  θ = π/4 (self-dual), α = 1.0")
println("  Target: c_eff ≈ 0.447 (arXiv:2502.14034)")
println("=" ^ 70)

Ls = [4, 6, 8]
if length(ARGS) > 0
    Ls = parse.(Int, split(ARGS[1], ","))
end

results_dir = joinpath(@__DIR__, "results")
mkpath(results_dir)

summary_file = joinpath(results_dir, "self_dual_summary.txt")
summary_io = open(summary_file, "w")

function logprintln(args...)
    println(args...)
    println(summary_io, args...)
    flush(stdout)
    flush(summary_io)
end

mean_neg_g0 = Float64[]
err_neg_g0 = Float64[]
mean_Deltas = Vector{Vector{Float64}}()

for L in Ls
    Ly = LY_FACTOR * L
    nsamp = nsamples_for(L)
    use_exact = (L <= 4)

    logprintln("\n--- L = $L, Ly = $Ly, samples = $nsamp ($(use_exact ? "exact" : "MCMC")) ---")

    neg_g0s = Float64[]
    all_Deltas = Vector{Vector{Float64}}()

    csv_file = joinpath(results_dir, "self_dual_L$(L).csv")
    csv_io = open(csv_file, "w")
    println(csv_io, "sample,gamma0," * join(["d$j" for j in 1:(NK-1)], ","))

    t0 = time()
    for i in 1:nsamp
        rng = MersenneTwister(30000 + i * 37 + L * 11)

        if use_exact
            mh, mv = sample_tc_born_exact(L, THETA_SELF_DUAL, Ly; rng=rng)
        else
            samples_mh, samples_mv, acc = sample_tc_born_mcmc(L, THETA_SELF_DUAL, Ly;
                                                                n_sweeps=3,
                                                                burn_in=1, thin=1)
            if isempty(samples_mh)
                logprintln("  WARNING: no MCMC samples at i=$i")
                continue
            end
            mh, mv = samples_mh[1], samples_mv[1]
        end

        # Leading Lyapunov exponent
        g0 = tc_leading_lyapunov(L, THETA_SELF_DUAL, mh, mv, Ly)
        push!(neg_g0s, -g0)

        # Lyapunov spectrum for scaling dimensions
        gammas = tc_lyapunov_spectrum(L, THETA_SELF_DUAL, mh, mv, Ly, NK)
        Deltas = [L / (2 * pi * ALPHA) * (gammas[1] - gammas[j]) for j in 2:NK]
        push!(all_Deltas, Deltas)

        println(csv_io, "$i,$g0," * join(Deltas, ","))

        if i % 20 == 0 || i == nsamp
            @printf("  [%3d/%3d]  -g0 = %10.5f  D1 = %8.5f  D2 = %8.5f  (%.1fs)\n",
                    i, nsamp, -g0, Deltas[1], Deltas[2], time() - t0)
            flush(stdout)
            flush(csv_io)
        end
    end
    close(csv_io)

    mean_D = [mean([all_Deltas[s][j] for s in 1:length(all_Deltas)]) for j in 1:(NK-1)]
    push!(mean_neg_g0, mean(neg_g0s))
    push!(err_neg_g0, std(neg_g0s) / sqrt(nsamp))
    push!(mean_Deltas, mean_D)

    elapsed = time() - t0
    @printf("  L=%2d done:  -g0 = %12.6f +/- %8.6f  (%.1fs)\n",
            L, mean_neg_g0[end], err_neg_g0[end], elapsed)
    logprintln("  L=$L complete in $(round(elapsed, digits=1))s")
end

# ================================================================
# Finite-size scaling
# ================================================================
logprintln("\n" * "=" ^ 70)
logprintln("Finite-Size Scaling Analysis")
logprintln("=" ^ 70)

# c_eff from -gamma0
include(joinpath(@__DIR__, "..", "src", "OpenCriticality.jl"))
using .OpenCriticality

logprintln("\nc_eff from -gamma0:")
logprintln("  L    -gamma0          err")
for (i, L) in enumerate(Ls)
    @printf("  %2d   %12.6f   %8.6f\n", L, mean_neg_g0[i], err_neg_g0[i])
    logprintln("  $L   $(mean_neg_g0[i])   $(err_neg_g0[i])")
end

c_A = fit_central_charge(Ls, mean_neg_g0, ALPHA; model=:A)[1]
c_B = fit_central_charge(Ls, mean_neg_g0, ALPHA; model=:B)[1]
c_C = fit_central_charge(Ls, mean_neg_g0, ALPHA; model=:C)[1]
logprintln("  Model A:  c_eff = $(round(c_A, digits=6))")
logprintln("  Model B:  c_eff = $(round(c_B, digits=6))")
logprintln("  Model C:  c_eff = $(round(c_C, digits=6))")

# Scaling dimensions Delta_m
logprintln("\nScaling dimensions Delta_m:")
logprintln("  L    Delta_1         Delta_2         Delta_3")
for (i, L) in enumerate(Ls)
    @printf("  %2d   %10.6f   %10.6f   %10.6f\n",
            L, mean_Deltas[i][1], mean_Deltas[i][2], mean_Deltas[i][3])
end

# Extrapolate Delta_m
for j in 1:min(NK-1, 3)
    gaps = [mean_Deltas[i][j] * 2 * pi * ALPHA / Ls[i] for i in 1:length(Ls)]
    if length(Ls) >= 2
        sd = fit_scaling_dimension(gaps, Ls, ALPHA; model=:linear)
        logprintln("  Delta_$j (extrapolated) = $(round(sd.x, digits=6))")
    end
end

logprintln("\n" * "=" ^ 70)
logprintln("  Target: c_eff ≈ 0.447 (arXiv:2502.14034)")
logprintln("=" ^ 70)

close(summary_io)
println("\nResults saved to $results_dir")
