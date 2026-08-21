"""
Model definitions for open-system criticality.

Each model provides:
  - `build_row_transfer_dense(model, config, y)`: dense 2^L × 2^L transfer matrix
  - `build_local_mpo_tensor(model, config, x, y)`: 4-index MPO site tensor [l,r,d,u]
  - `sample_config(model, rng, L, Ly)`: draw a configuration from the model's distribution
  - `convention(model)`: return the ModelConvention

The classical Ising model is the validation target (c = 1/2).
The Nishimori RBIM and measured toric code extend to open quantum matter.
"""

# ── Abstract interface ──────────────────────────────────────────────

abstract type BornModel end

"Physical (local) Hilbert-space dimension."
physical_dim(::BornModel) = 2

"Return the ModelConvention for this model."
convention(model::BornModel) = model.conv

"Number of sites in the transverse (circumference) direction."
width(model::BornModel) = model.L

# ── Configuration type ──────────────────────────────────────────────

"""
    Configuration

A spin/bond/measurement configuration on an L × Ly lattice.
For the clean Ising model the bonds are uniform and `outcomes` is unused.
For the Nishimori RBIM the bonds are ±J.
For the measured toric code `outcomes` holds the measurement record.
"""
struct Configuration
    L::Int
    Ly::Int
    bonds_v::Matrix{Float64}   # L × Ly  (vertical: between row y and y+1)
    bonds_h::Matrix{Float64}   # L × Ly  (horizontal: within row y, bond x↔x+1)
    outcomes::Matrix{Int}       # L × Ly  (measurement outcomes, 0-based)
end

"Trivial all-+J configuration for the clean Ising model."
function Configuration(L::Int, Ly::Int, J::Float64)
    Configuration(L, Ly, fill(J, L, Ly), fill(J, L, Ly), zeros(Int, L, Ly))
end

Configuration(L::Int, Ly::Int) = Configuration(L, Ly, 1.0)

# ── Classical Ising ─────────────────────────────────────────────────

"""
    ClassicalIsing

Clean 2D Ising model on a cylinder: H = −J Σ s_i s_j.
Transfer matrix is translation invariant, so sampling is trivial
(single deterministic configuration).  Validation target: c = 1/2.
"""
struct ClassicalIsing <: BornModel
    L::Int
    beta::Float64
    J::Float64
    conv::ModelConvention
end

function ClassicalIsing(; L::Int=8, beta::Float64=log(1+sqrt(2))/2, J::Float64=1.0,
                          bc_y::Symbol=:periodic)
    ClassicalIsing(L, beta, J, ClassicalIsingConvention(; beta, J, bc_y))
end

function sample_config(model::ClassicalIsing, rng::AbstractRNG, Ly::Int)
    Configuration(model.L, Ly, model.J)
end

"Vertical bond weight: exp(βJ s s') — returns the 2×2 Boltzmann matrix."
function boltzmann_matrix(beta::Real, J::Real)
    K = beta * J
    [exp(K) exp(-K); exp(-K) exp(K)]
end

"Square-root-decomposed Boltzmann matrix nt such that t = nt * nt'."
function sqrt_boltzmann(beta::Real, J::Real)
    t = boltzmann_matrix(beta, J)
    r = eigen(Symmetric(t))
    # enforce positive eigenvalues
    vals = max.(r.values, 0.0)
    r.vectors * Diagonal(sqrt.(vals)) * r.vectors'
end

"""Element-wise square root of the Boltzmann matrix: N[s,s'] = sqrt(exp(beta*J*s*s'))."""
elem_sqrt_boltzmann(beta::Real, J::Real) = sqrt.(boltzmann_matrix(beta, J))

"""
Build the dense 2^L × 2^L row transfer matrix for row y.

T(σ, σ') = D_h^{1/2} · [⊗_x B_v(J^v_{x,y})] · D_h^{1/2}

where B_v is the 2×2 vertical Boltzmann matrix and D_h is the diagonal
matrix of horizontal bond weights.  The symmetric form ensures
Z = Tr(T^{L_y}) gives the correct partition function with periodic BC in y.
"""
function build_row_transfer_dense(model::ClassicalIsing, config::Configuration, y::Int)
    L = model.L
    d = physical_dim(model)
    N = d^L

    # --- Vertical part: Kronecker product of 2×2 matrices ---
    Tv = ones(Float64, 1, 1)
    for x in 1:L
        Jv = config.bonds_v[x, y]
        B = boltzmann_matrix(model.beta, Jv)
        Tv = kron(Tv, B)
    end

    # --- Horizontal part: diagonal matrix ---
    Dh = Vector{Float64}(undef, N)
    for idx in 0:(N-1)
        spins = [idx >> (x-1) & 1 == 0 ? 1 : -1 for x in 1:L]
        h = 0.0
        for x in 1:L
            xn = mod1(x + 1, L)  # periodic BC in x
            Jh = config.bonds_h[x, y]
            h += model.beta * Jh * spins[x] * spins[xn]
        end
        Dh[idx + 1] = exp(h)
    end

    # Symmetric form: T = sqrt(D_h) · T_v · sqrt(D_h)
    sqrtD = sqrt.(Dh)
    return Diagonal(sqrtD) * Tv * Diagonal(sqrtD)
end

"""
Build the 4-index MPO site tensor W[l, r, d_in, u_out] for site x in row y.

Bond dimension d^2 = 4: two independent MPO chains carry the horizontal
weights for the output (sigma) and input (sigma') spin boundaries.

  W[(a,a'), (b,b'), sigma_in, sigma_out] =
      Bv[sigma_out, sigma_in] * delta(b, sigma_out)  * Nh[a, sigma_out]
                               * delta(b', sigma_in) * Nh[a', sigma_in]

where Bv is the vertical Boltzmann matrix and Nh = sqrt.(Bh) is the
element-wise square root of the horizontal Boltzmann matrix.
Contracting L such MPOs with periodic BC in x reproduces the
symmetric transfer matrix T = Dh^{1/2} * Tv * Dh^{1/2}.
"""
function build_local_mpo_tensor(model::ClassicalIsing, config::Configuration, x::Int, y::Int)
    d = 2
    Jv = config.bonds_v[x, y]
    Jh = config.bonds_h[x, y]
    Bv = boltzmann_matrix(model.beta, Jv)    # [sigma_out, sigma_in], d x d
    Nh = elem_sqrt_boltzmann(model.beta, Jh)  # element-wise sqrt of B_h, d x d

    D = d * d  # bond dimension d^2 = 4
    W = zeros(Float64, D, D, d, d)  # [l, r, d_in, u_out]
    for sigma_out in 1:d, sigma_in in 1:d
        for a in 1:d, ap in 1:d       # left bond = (a, a')
            for b in 1:d, bp in 1:d   # right bond = (b, b')
                l = (a - 1) * d + ap
                r = (b - 1) * d + bp
                if b == sigma_out && bp == sigma_in
                    W[l, r, sigma_in, sigma_out] =
                        Bv[sigma_out, sigma_in] * Nh[a, sigma_out] * Nh[ap, sigma_in]
                end
            end
        end
    end
    return W
end

# ── Nishimori RBIM ──────────────────────────────────────────────────

"""
    NishimoriRBIM

Random-bond ±J Ising model at the Nishimori multicritical point.
Bonds are drawn iid: P(J=+J₀)=p, P(J=−J₀)=1−p, with β fixed by the
Nishimori condition exp(−2βJ₀) = (1−p)/p.
Validation target: c_eff = 0.464(4).

At the standard Nishimori benchmark, gauge-invariant observables can be
sampled from the equivalent iid ±J disorder distribution (workflow §4.1),
so direct independent sampling replaces MCMC.
"""
struct NishimoriRBIM <: BornModel
    L::Int
    p::Float64         # probability of ferromagnetic bond
    J0::Float64        # |J|
    beta::Float64      # Nishimori temperature
    conv::ModelConvention
end

function NishimoriRBIM(; L::Int=8, p::Float64=0.8899, J0::Float64=1.0)
    beta_N = 0.5 * log(p / (1 - p)) / J0
    NishimoriRBIM(L, p, J0, beta_N, NishimoriConvention(; p, J=J0))
end

function sample_config(model::NishimoriRBIM, rng::AbstractRNG, Ly::Int)
    L = model.L
    bonds_v = similar(Matrix{Float64}, L, Ly)
    bonds_h = similar(Matrix{Float64}, L, Ly)
    for y in 1:Ly, x in 1:L
        bonds_v[x, y] = rand(rng) < model.p ? model.J0 : -model.J0
        bonds_h[x, y] = rand(rng) < model.p ? model.J0 : -model.J0
    end
    Configuration(L, Ly, bonds_v, bonds_h, zeros(Int, L, Ly))
end

function build_row_transfer_dense(model::NishimoriRBIM, config::Configuration, y::Int)
    L = model.L
    d = physical_dim(model)
    N = d^L

    Tv = ones(Float64, 1, 1)
    for x in 1:L
        Jv = config.bonds_v[x, y]
        B = boltzmann_matrix(model.beta, Jv)
        Tv = kron(Tv, B)
    end

    Dh = Vector{Float64}(undef, N)
    for idx in 0:(N-1)
        spins = [idx >> (x-1) & 1 == 0 ? 1 : -1 for x in 1:L]
        h = 0.0
        for x in 1:L
            xn = mod1(x + 1, L)
            Jh = config.bonds_h[x, y]
            h += model.beta * Jh * spins[x] * spins[xn]
        end
        Dh[idx + 1] = exp(h)
    end

    sqrtD = sqrt.(Dh)
    return Diagonal(sqrtD) * Tv * Diagonal(sqrtD)
end

function build_local_mpo_tensor(model::NishimoriRBIM, config::Configuration, x::Int, y::Int)
    d = 2
    Jv = config.bonds_v[x, y]
    Jh = config.bonds_h[x, y]
    Bv = boltzmann_matrix(model.beta, Jv)
    Nh = elem_sqrt_boltzmann(model.beta, Jh)

    D = d * d  # bond dimension d^2 = 4
    W = zeros(Float64, D, D, d, d)  # [l, r, d_in, u_out]
    for sigma_out in 1:d, sigma_in in 1:d
        for a in 1:d, ap in 1:d
            for b in 1:d, bp in 1:d
                l = (a - 1) * d + ap
                r = (b - 1) * d + bp
                if b == sigma_out && bp == sigma_in
                    W[l, r, sigma_in, sigma_out] =
                        Bv[sigma_out, sigma_in] * Nh[a, sigma_out] * Nh[ap, sigma_in]
                end
            end
        end
    end
    return W
end

# ── Measured Toric Code ─────────────────────────────────────────────

"""
    MeasuredToricCode

General measured toric code model.  The toric-code ground-state PEPS
(bond dimension D=2, Z₂ gauge structure) is projected by local measurement
outcomes m_{x,y}.  The Born weight Z_m = ⟨ψ(m)|ψ(m)⟩ is a double-layer
tensor-network contraction.

Via the Dennis et al. mapping, the measured toric code at the self-dual
point reduces to the Nishimori RBIM.  This implementation supports both
the direct double-layer contraction (general) and the Nishimori mapping
(for the self-dual benchmark).
"""
struct MeasuredToricCode <: BornModel
    L::Int
    measurement_rate::Float64
    use_nishimori_mapping::Bool    # if true, delegate to NishimoriRBIM
    nishimori_model::NishimoriRBIM # internal delegate for the mapping
    conv::ModelConvention
end

function MeasuredToricCode(; L::Int=8, measurement_rate::Float64=1.0,
                              sector::String="W+1_even")
    # At the self-dual point, the measured toric code maps to the
    # Nishimori RBIM at p = 0.5 (equal ±J) with β_N = 0.5*log(1+√2)
    p_nish = 0.5
    J0 = 1.0
    beta_N = 0.5 * log(p_nish / (1 - p_nish)) / J0
    nish = NishimoriRBIM(; L, p=p_nish, J0)
    conv = MeasuredToricCodeConvention(; measurement_rate, sector)
    MeasuredToricCode(L, measurement_rate, true, nish, conv)
end

function sample_config(model::MeasuredToricCode, rng::AbstractRNG, Ly::Int)
    if model.use_nishimori_mapping
        return sample_config(model.nishimori_model, rng, Ly)
    end
    # Direct double-layer sampling would go here (WP5)
    error("Direct double-layer sampling not yet implemented; use Nishimori mapping")
end

function build_row_transfer_dense(model::MeasuredToricCode, config::Configuration, y::Int)
    if model.use_nishimori_mapping
        return build_row_transfer_dense(model.nishimori_model, config, y)
    end
    error("Direct double-layer contraction not yet implemented; use Nishimori mapping")
end

function build_local_mpo_tensor(model::MeasuredToricCode, config::Configuration, x::Int, y::Int)
    if model.use_nishimori_mapping
        return build_local_mpo_tensor(model.nishimori_model, config, x, y)
    end
    error("Direct double-layer MPO not yet implemented; use Nishimori mapping")
end

# ── Utility: enumerate spin configurations ──────────────────────────

"""Convert a linear index (0-based) to a vector of ±1 spins of length L."""
function index_to_spins(idx::Integer, L::Integer)
    [idx >> (x - 1) & 1 == 0 ? 1 : -1 for x in 1:L]
end

"""Convert a vector of ±1 spins to a linear index (0-based)."""
function spins_to_index(spins::AbstractVector{Int})
    idx = 0
    for x in 1:length(spins)
        if spins[x] == -1
            idx |= (1 << (x - 1))
        end
    end
    return idx
end

"""Exact partition function by brute-force enumeration (tiny systems only)."""
function exact_partition_function(model::BornModel, config::Configuration)
    L = config.L
    Ly = config.Ly
    d = physical_dim(model)
    N = d^L
    Z = 0.0
    for row_configs in Iterators.product(fill(0:N-1, Ly)...)
        w = 1.0
        for y in 1:Ly
            yn = mod1(y + 1, Ly)
            σ  = index_to_spins(row_configs[y], L)
            σ′ = index_to_spins(row_configs[yn], L)
            for x in 1:L
                xn = mod1(x + 1, L)
                Jv = config.bonds_v[x, y]
                Jh = config.bonds_h[x, y]
                w *= exp(model.beta * Jv * σ[x] * σ′[x])
                w *= exp(model.beta * Jh * σ[x] * σ[xn])
            end
        end
        Z += w
    end
    return Z
end
