"""
Tensor-network contraction backends for Born-weight computation.

Two backends (workflow section 3):

1. Dense -- exact 2^L x 2^L transfer-matrix multiplication.  Used for
   validation on small L (<= 12) and as the reference implementation.

2. Boundary MPS -- sequential row-MPO application with SVD truncation.
   Maintains a normalized boundary MPS |b_y>, accumulates log-norms.
   Scales to large L at controlled cost O(L * chi^2 * D_mpo * d^2).

Free energy per row:  Phi_L = -(1/L_y) log Z_m
"""

using LinearAlgebra

# ------------------------------------------------------------------
# Dense backend
# ------------------------------------------------------------------

"""
    dense_logZ(model, config) -> Float64

Exact log Z_m by forming each row transfer matrix and multiplying.
For periodic BC in y: Z = Tr(T_Ly * ... * T_1).
For open BC in y:     Z = <u| T_Ly * ... * T_1 |v>  with u, v = all-ones.
"""
function dense_logZ(model::BornModel, config::Configuration)
    L = config.L
    Ly = config.Ly
    d = physical_dim(model)
    N = d^L

    Ts = [build_row_transfer_dense(model, config, y) for y in 1:Ly]

    conv = convention(model)
    if conv.bc_y == :periodic
        # Z = Tr(prod T_y) — log-space to avoid overflow
        P = copy(Ts[1])
        log_scale = 0.0
        for y in 2:Ly
            P = Ts[y] * P
            s = maximum(abs.(P))
            if s == 0.0
                @warn "dense_logZ: zero matrix at step $y"
                return NaN + conv.log_offset
            end
            P ./= s
            log_scale += log(s)
        end
        Z = tr(P)
        if Z <= 0
            @warn "dense_logZ: Z = $Z <= 0, using |Z|"
            Z = abs(Z)
        end
        return log(Z) + log_scale + conv.log_offset
    else
        # Open BC: Z = u' * (prod T_y) * v  with u, v = all-ones
        # Log-space: normalize at each step to avoid overflow
        v = ones(Float64, N)
        log_scale = 0.0
        for y in 1:Ly
            v = Ts[y] * v
            s = sum(v)
            if s == 0.0
                @warn "dense_logZ: zero sum at step $y"
                return NaN + conv.log_offset
            end
            v ./= s
            log_scale += log(abs(s))
        end
        return log_scale + conv.log_offset
    end
end

"""
    dense_free_energy(model, config) -> Float64

Free energy per row: Phi_L = -log Z_m / L_y.
"""
function dense_free_energy(model::BornModel, config::Configuration)
    logZ = dense_logZ(model, config)
    conv = convention(model)
    return free_energy_per_row(conv, logZ, config.Ly)
end

# ------------------------------------------------------------------
# Boundary MPS backend
# ------------------------------------------------------------------

"""
Simple left-canonical MPS: vector of 3-index tensors A[x][l, s, r]
where l=left bond, s=physical, r=right bond.
"""
mutable struct BoundaryMPS
    tensors::Vector{Array{Float64,3}}
    log_norm::Float64
end

"""Initialize a random boundary MPS with bond dimension chi."""
function init_boundary_mps(L::Int, d::Int, chi::Int; rng=Random.default_rng())
    tensors = Vector{Array{Float64,3}}(undef, L)
    for x in 1:L
        dl = x == 1 ? 1 : chi
        dr = x == L ? 1 : chi
        A = randn(rng, dl, d, dr)
        A ./= norm(A)
        tensors[x] = A
    end
    return BoundaryMPS(tensors, 0.0)
end

"""Initialize a uniform (product-state) boundary MPS."""
function init_product_boundary_mps(L::Int, d::Int)
    tensors = Vector{Array{Float64,3}}(undef, L)
    for x in 1:L
        A = ones(1, d, 1)
        tensors[x] = A
    end
    return BoundaryMPS(tensors, 0.0)
end

"""
Apply a row transfer MPO to a boundary MPS, then SVD-compress.

Step 1: Apply MPO to each site, producing B[l_comb, u, r_comb]
  where l_comb = l_mps * l_mpo, r_comb = r_mpo * r_mps
Step 2: Left-to-right SVD sweep with truncation to bond dimension chi.
"""
function apply_mpo_and_compress!(
        mps::BoundaryMPS,
        mpo::Vector{Array{Float64,4}},
        chi::Int,
        tol::Float64
    )::Float64
    L = length(mps.tensors)
    d = size(mps.tensors[1], 2)

    # --- Step 1: apply MPO -> 3-index tensor B[l, u, r] ---
    applied = Vector{Array{Float64,3}}(undef, L)
    for x in 1:L
        A = mps.tensors[x]   # [l_mps, s, r_mps]
        W = mpo[x]           # [l_mpo, r_mpo, s, u]
        dl_mps, _, dr_mps = size(A)
        dl_mpo, dr_mpo, _, du = size(W)
        l_comb = dl_mps * dl_mpo
        r_comb = dr_mpo * dr_mps
        B = zeros(l_comb, du, r_comb)
        for s in 1:d
            for lmps in 1:dl_mps, lmpo in 1:dl_mpo
                li = (lmps - 1) * dl_mpo + lmpo
                for uo in 1:du, rmpo in 1:dr_mpo, rmps in 1:dr_mps
                    ri = (rmps - 1) * dr_mpo + rmpo
                    B[li, uo, ri] += A[lmps, s, rmps] * W[lmpo, rmpo, s, uo]
                end
            end
        end
        applied[x] = B
    end

    # --- Step 2: left-to-right SVD compression ---
    new_tensors = Vector{Array{Float64,3}}(undef, L)
    log_norm_accum = 0.0
    SV = nothing  # S * V' from previous site

    for x in 1:L
        B = applied[x]
        l, u, r = size(B)

        # Absorb SV from previous site into left bond
        if SV !== nothing
            # SV is [k_prev, l], B is [l, u, r] -> [k_prev, u, r]
            B = reshape(SV * reshape(B, l, u * r), size(SV, 1), u, r)
            l = size(SV, 1)
        end

       if x == L
           # Last site: extract Frobenius norm to prevent overflow.
           # The trace contraction is multilinear in the site tensors,
           # so rescaling by the norm is exact: the factor is tracked
           # in log_norm_accum and recovered in boundary_mps_logZ.
           nrm = norm(B)
           if nrm > 0
               new_tensors[x] = B ./ nrm
               log_norm_accum += log(nrm)
           else
               new_tensors[x] = B
           end
       else
           # Reshape to [l*u, r] and SVD
           M = reshape(B, l * u, r)
           F = svd(M)
           U, S, Vt = F.U, F.S, F.Vt
 
           # Truncate to chi
           k = min(chi, length(S))
           if tol > 0 && S[1] > 0
               while k > 1 && S[k] < tol * S[1]
                   k -= 1
               end
           end
 
           # Extract leading singular value as norm to keep tensors O(1).
           # This prevents overflow and improves truncation stability.
           if S[1] > 0
               log_norm_accum += log(S[1])
               S = S ./ S[1]
           end
 
           # New site tensor: U[:, 1:k] reshaped to [l, u, k]
           new_tensors[x] = reshape(U[:, 1:k], l, u, k)
 
           # S * V' for next site: [k, r]
           SV = Diagonal(S[1:k]) * Vt[1:k, :]
       end
    end

    mps.tensors .= new_tensors
    mps.log_norm += log_norm_accum
    return log_norm_accum
end

"""
    boundary_mps_logZ(model, config; chi, tol) -> Float64

Approximate log Z_m via boundary MPS contraction with bond dimension chi.
"""
function boundary_mps_logZ(model::BornModel, config::Configuration;
                             chi::Int=20, tol::Float64=1e-12)
    L = config.L
    Ly = config.Ly
    d = physical_dim(model)

    bmps = init_product_boundary_mps(L, d)

    for y in 1:Ly
        mpo = [build_local_mpo_tensor(model, config, x, y) for x in 1:L]
        apply_mpo_and_compress!(bmps, mpo, chi, tol)
    end

    conv = convention(model)
    if conv.bc_x == :periodic
        final_val = _trace_mps(bmps)
    else
        final_val = _overlap_product(bmps, L, d)
    end

    if final_val <= 0
        final_val = abs(final_val)
    end

    return bmps.log_norm + log(final_val) + conv.log_offset
end

"""Compute the trace of an MPS (contract first left bond with last right bond)."""
function _trace_mps(mps::BoundaryMPS)
    L = length(mps.tensors)
    # E[dl, dr] = sum_s A1[dl, s, dr]
    A = mps.tensors[1]
    dl, d, dr = size(A)
    E = reshape(sum(A, dims=2), dl, dr)
    for x in 2:L
        A = mps.tensors[x]
        dl2, d2, dr2 = size(A)
        Asum = reshape(sum(A, dims=2), dl2, dr2)
        E = E * Asum  # [dl_prev, dr_prev] * [dr_prev=dl2, dr2]
    end
    # E is [dl_1, dr_L]; trace contracts dl_1 with dr_L
    if size(E, 1) == size(E, 2)
        return tr(E)
    else
        return sum(E)
    end
end

"""Overlap of MPS with a uniform product state |s> = 1/sqrt(d) each."""
function _overlap_product(mps::BoundaryMPS, L::Int, d::Int)
    phys_vec = ones(d)
    # E[dl, dr] = sum_s A[dl, s, dr] * v[s]
    A = mps.tensors[1]
    dl, _, dr = size(A)
    E = dropdims(sum(A .* reshape(phys_vec, 1, d, 1), dims=2), dims=2)
    for x in 2:L
        A = mps.tensors[x]
        dl2, _, dr2 = size(A)
        Ar = dropdims(sum(A .* reshape(phys_vec, 1, d, 1), dims=2), dims=2)
        E = E * Ar
    end
    # E is [dl_1, dr_L]; contract with all-ones on both ends
    return sum(E)
end

"""
    boundary_mps_free_energy(model, config; chi, tol) -> Float64
"""
function boundary_mps_free_energy(model::BornModel, config::Configuration;
                                    chi::Int=20, tol::Float64=1e-12)
    logZ = boundary_mps_logZ(model, config; chi, tol)
    conv = convention(model)
    return free_energy_per_row(conv, logZ, config.Ly)
end

# ------------------------------------------------------------------
# PEPSKit cross-check (clean Ising only)
# ------------------------------------------------------------------

"""
    pepskit_infinite_free_energy(model::ClassicalIsing; chi_env, tol) -> Float64

Cross-check: use PEPSKit CTMRG on the infinite Ising partition function.
Must be called from a script with `using PEPSKit`.
"""
function pepskit_infinite_free_energy(model::ClassicalIsing;
                                         chi_env::Int=20, tol::Float64=1e-8)
    error("pepskit_infinite_free_energy must be called from a script with `using PEPSKit`. " *
          "See scripts/benchmark_ising.jl for usage.")
end
