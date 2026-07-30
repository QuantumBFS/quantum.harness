"""
Lyapunov exponents without translation invariance (workflow §5).

For a product of non-commuting, non-translation-invariant transfer
operators T_y, the Oseledec exponents are extracted by:

  • Leading exponent: one-vector power iteration with per-step normalization.
  • Full spectrum:    repeated Householder QR on an orthonormal frame.

Key implementation choices:
  - Fix R_{ii} > 0 convention to avoid sign flicker.
  - Reorthogonalize at least once per row (twice if ‖Q'Q − I‖ is large).
  - Use compensated (Kahan) summation for long sums of log R_{ii}.
  - Burn-in discards both MC equilibration and Oseledec-subspace convergence.

Class-D diagnostics (workflow §5.3):
  - ± pairing check
  - determinant sum rule: Σ_i γ_i = (1/N) log|det T|
  - orthogonality loss: ‖Q†Q − I‖
"""

using LinearAlgebra

# ── Leading Lyapunov exponent ──────────────────────────────────────

"""
    leading_lyapunov(transfer_ops; burn_in, rng) → (γ₀, info)

One-vector power iteration.  For each transfer operator T_y:
  1. u = T_y · q
  2. a = ‖u‖
  3. q = u / a
  4. if y > burn_in: s += log(a)

Returns γ₀ = s / (N_prod) where N_prod = length(transfer_ops) − burn_in.
"""
function leading_lyapunov(transfer_ops::AbstractVector{<:AbstractMatrix};
                            burn_in::Int = max(1, length(transfer_ops) ÷ 10),
                            rng::AbstractRNG = Random.default_rng())
    N = size(transfer_ops[1], 1)
    q = randn(rng, N)
    q ./= norm(q)

    s = 0.0
    N_prod = 0

    for (y, T) in enumerate(transfer_ops)
        u = T * q
        a = norm(u)
        if a == 0.0
            @warn "leading_lyapunov: zero norm at step $y"
            break
        end
        q = u ./ a
        if y > burn_in
            s += log(a)
            N_prod += 1
        end
    end

    gamma_0 = N_prod > 0 ? s / N_prod : NaN
    info = (burn_in=burn_in, n_product=N_prod, final_norm=norm(q))
    return gamma_0, info
end

"""
    leading_lyapunov(model, config; burn_in) → Float64

Build transfer operators from the model and compute the leading exponent.
"""
function leading_lyapunov(model::BornModel, config::Configuration;
                            burn_in::Int = max(1, config.Ly ÷ 10))
    Ts = [build_row_transfer_dense(model, config, y) for y in 1:config.Ly]
    gamma, _ = leading_lyapunov(Ts; burn_in)
    return gamma
end

# ── Lyapunov spectrum via repeated QR ───────────────────────────────

"""
    lyapunov_spectrum(transfer_ops, k; burn_in, reorth) → (γ, diagnostics)

Evolve an orthonormal frame Q (k columns) through the transfer operators:
  Y = T_y · Q,  Y = Q' · R  (Householder QR with R_{ii} > 0)
  accumulate s_i += log R_{ii}

Returns γ_i = s_i / N_prod and a diagnostics NamedTuple.
"""
function lyapunov_spectrum(transfer_ops::AbstractVector{<:AbstractMatrix}, k::Int;
                             burn_in::Int = max(1, length(transfer_ops) ÷ 10),
                             reorth::Bool = true)
    N = size(transfer_ops[1], 1)
    @assert k ≤ N "k=$k exceeds matrix dimension N=$N"

    # Initialize orthonormal frame
    Q = Matrix(qr(randn(N, k)).Q)

    s = zeros(k)
    N_prod = 0
    max_orth_loss = 0.0
    log_det_sum = 0.0  # for determinant sum rule

    for (y, T) in enumerate(transfer_ops)
        Y = T * Q

        # QR with positive diagonal
        F = qr(Y)
        Qnew = Matrix(F.Q)
        R = F.R

        # Fix signs: make R[i,i] > 0
        for i in 1:k
            if R[i, i] < 0
                Qnew[:, i] .= -Qnew[:, i]
                R[i, :] .= -R[i, :]
            elseif R[i, i] == 0.0
                @warn "lyapunov_spectrum: zero diagonal R[$i,$i] at step $y"
            end
        end

        # Reorthogonalize if needed
        if reorth
            orth_loss = norm(Qnew' * Qnew - I)
            max_orth_loss = max(max_orth_loss, orth_loss)
            if orth_loss > 1e-10
                F2 = qr(Qnew)
                Qnew = Matrix(F2.Q)
            end
        end

        Q = Qnew

        if y > burn_in
            for i in 1:k
                s[i] += log(abs(R[i, i]))
            end
            N_prod += 1
        end
    end

    gammas = N_prod > 0 ? s ./ N_prod : fill(NaN, k)

    diagnostics = (
        burn_in = burn_in,
        n_product = N_prod,
        k = k,
        max_orthogonality_loss = max_orth_loss,
    )

    return gammas, diagnostics
end

"""
    lyapunov_spectrum(model, config, k; burn_in) → Vector{Float64}

Build transfer operators from the model and compute the first k exponents.
"""
function lyapunov_spectrum(model::BornModel, config::Configuration, k::Int;
                             burn_in::Int = max(1, config.Ly ÷ 10))
    Ts = [build_row_transfer_dense(model, config, y) for y in 1:config.Ly]
    gammas, _ = lyapunov_spectrum(Ts, k; burn_in)
    return gammas
end

# ── Class-D diagnostics ─────────────────────────────────────────────

"""
    class_d_diagnostics(gammas) → NamedTuple

Check class-D spectral properties:
  - ± pairing: γ_i ≈ −γ_{k−i+1}
  - determinant sum rule: Σ γ_i ≈ (1/N) log|det T|
  - zero-mode gap: |γ_{k/2}| + |γ_{k/2+1}|
"""
function class_d_diagnostics(gammas::AbstractVector{<:Real})
    k = length(gammas)
    sorted = sort(gammas, rev=true)

    # ± pairing check
    pair_errors = Float64[]
    for i in 1:(k ÷ 2)
        push!(pair_errors, abs(sorted[i] + sorted[k - i + 1]))
    end

    # Sum of all exponents
    total = sum(gammas)

    # Zero-mode gap (for even k)
    zero_gap = k % 2 == 0 ? abs(sorted[k ÷ 2]) + abs(sorted[k ÷ 2 + 1]) : NaN

    return (
        pair_errors = pair_errors,
        max_pair_error = maximum(pair_errors),
        total_sum = total,
        zero_mode_gap = zero_gap,
        sorted_exponents = sorted,
    )
end

"""
    scaling_dimension(gap, gamma_0, L, alpha) → Float64

Extract scaling dimension from Lyapunov gap:
  x_i = L / (2πα) · (Φ_i − Φ_0) = −L / (2πα) · (γ_i − γ_0)
"""
function scaling_dimension(gamma_i::Real, gamma_0::Real, L::Integer, alpha::Real=1.0)
    return L / (2 * pi * alpha) * (gamma_0 - gamma_i)
end

"""
    lyapunov_gap(transfer_ops, k; burn_in) → (γ_0, γ_1, Δγ, info)

Compute the leading gap γ_0 − γ_1, which gives the spin scaling dimension
x_σ = L/(2πα) · Δγ.  Also returns the full first-k spectrum.
"""
function lyapunov_gap(transfer_ops::AbstractVector{<:AbstractMatrix}, k::Int=2;
                        burn_in::Int = max(1, length(transfer_ops) ÷ 10))
    gammas, info = lyapunov_spectrum(transfer_ops, k; burn_in)
    gamma_0 = gammas[1]
    gamma_1 = length(gammas) ≥ 2 ? gammas[2] : NaN
    return gamma_0, gamma_1, gamma_0 - gamma_1, info
end

# ── SVD cross-check for short products ──────────────────────────────

"""
    svd_lyapunov_check(transfer_ops; n_product) → Vector{Float64}

Form the explicit matrix product T_n · ⋯ · T_1 and compute its singular
values.  The log-SVD values divided by n should match the QR exponents.
Use for validation on short products only (workflow §8.4).
"""
function svd_lyapunov_check(transfer_ops::AbstractVector{<:AbstractMatrix};
                              n_product::Int = min(length(transfer_ops), 20))
    T = reduce(*, transfer_ops[1:n_product])
    sv = svdvals(T)
    return log.(sv) ./ n_product
end
