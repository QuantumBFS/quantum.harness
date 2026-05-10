# Cached Eq.-(24) ratio-chain diagnostic for validation paper Fig 4.
#
#   - Panel (a): c_L = 2 M_2(L/2) − M_2(L), estimated by the Eq.-(24) ratio
#     chain — single Markov chain on Π_{P,2} ∝ |⟨P⟩_L|⁴, accumulating
#         R(P) = |⟨P^(1)⟩_{L/2}|⁴ · |⟨P^(2)⟩_{L/2}|⁴ / |⟨P⟩_L|⁴
#     with c_L = -log⟨R⟩_{Π_{P,2}}. Exact small-L diagnostics must gate this
#     path because the one-sided ratio can be rare-event dominated.
#
#   - Panel (b): m_2(L) = M_2(L)/L, reconstructed via the increment recursion
#         M_2(L) = 2^k · M_2(L_min) − Σ_{j=1..k} 2^{k-j} c_{L_min · 2^j}
#     anchored at L_min = 8 (exact-sum SRE on the ED ground state).
#
# Sign convention (paper Eq. 24 vs Fig 4(a)):
#   The paper writes c_N = log⟨R⟩ in Eq. (24); under the convention
#   c_N = 2 M_2(N/2) − M_2(N), the algebra gives c_N = -log⟨R⟩ (the
#   ratio in Eq. (24) is the inverse of what the convention would give).
#   We use c_N = -log⟨R⟩ here. **At h_c=1, c_L < 0** (Fig 4(a) dips
#   negative): m_2(L) approaches the asymptotic density D_2 from below,
#   so M_2(L) < D_2·L for finite L, hence c_L = M_2(L) - 2·M_2(L/2)·... < 0.
#   Verified against algebraic c_L from tfim_fig4.jl and exact-sum at L=4.
#
# Translation invariance (paper line ~727 / Eq. 24 footnote):
#   We assume PBC + translation invariance, so |ψ_{L/2}⟩ is a single state
#   used to evaluate both P^(1) and P^(2). One DMRG run per (h, L/2).
#
# Run:  julia --project=julia-env scripts/tfim_fig4_paper_grade.jl
# Local prototype scale:  L=16, h={0.95, 1.0, 1.05}, N_S=1e5, ~5 min wall.
# Full paper-scale runs require an independent exact/small-L gate before use.

using ITensors, ITensorMPS
using LinearAlgebra
using Random
using Printf
using Statistics
using JSON
using Plots
using SHA

include(joinpath(@__DIR__, "..", "tools", "cli", "harness_cell_config.jl"))
include(joinpath(@__DIR__, "..", "tools", "cli", "harness_manifest_evidence.jl"))
include(joinpath(@__DIR__, "..", "tools", "cli", "harness_mps_stateprep.jl"))
include(joinpath(@__DIR__, "..", "tools", "cli", "pauli_mps_sampler.jl"))

const SCRIPT_PATH = normpath(@__FILE__)
const SCRIPT_HASH = bytes2hex(sha256(read(SCRIPT_PATH)))
const COMPUTE_MANIFEST_CONTRACT = Dict{String,Any}(
    "required_fields" => Any[
        "protocol_hash", "script_hash", "sources", "claims", "deviations", "artifacts",
        "cL", "se", "accept",
    ],
    "nonempty_fields" => Any["protocol_hash", "script_hash", "sources", "claims", "artifacts"],
    "numeric_fields" => Any["cL", "se", "accept"],
    "optional_numeric_fields" => Any["mean_R"],
)
const PAULI_MATRICES = [
    ComplexF64[1.0 0.0; 0.0 1.0],
    ComplexF64[0.0 1.0; 1.0 0.0],
    ComplexF64[0.0 -1.0im; 1.0im 0.0],
    ComplexF64[1.0 0.0; 0.0 -1.0],
]

function env_list(name::String)
    raw = strip(get(ENV, name, ""))
    isempty(raw) && return String[]
    return [strip(x) for x in split(raw, ';') if !isempty(strip(x))]
end

function list_from_provenance(provenance::AbstractDict, key::String, env_name::String)
    v = get(provenance, key, nothing)
    v === nothing && return env_list(env_name)
    v isa Vector && return [string(x) for x in v]
    return [string(v)]
end

function reproduction_provenance(provenance::AbstractDict=Dict{String,Any}())
    protocol_hash = strip(string(get(provenance, "protocol_hash", get(ENV, "HARNESS_PROTOCOL_HASH", ""))))
    sources = list_from_provenance(provenance, "sources", "HARNESS_SOURCES")
    claims = list_from_provenance(provenance, "claims", "HARNESS_CLAIMS")
    deviations = list_from_provenance(provenance, "deviations", "HARNESS_DEVIATIONS")
    if isempty(protocol_hash) || isempty(sources) || isempty(claims)
        error("Missing reproduction provenance. Set HARNESS_PROTOCOL_HASH, HARNESS_SOURCES, and HARNESS_CLAIMS before running the Eq.-(24) diagnostic.")
    end
    return Dict(
        "protocol_hash" => protocol_hash,
        "script_hash" => SCRIPT_HASH,
        "script_path" => SCRIPT_PATH,
        "sources" => sources,
        "claims" => claims,
        "deviations" => deviations,
    )
end

function validate_compute_manifest!(d::AbstractDict, path::String)
    contract = Dict{String,Any}(string(k) => v for (k, v) in COMPUTE_MANIFEST_CONTRACT)
    contract["equals"] = Any[
        Dict("field"=>"script_hash", "value"=>SCRIPT_HASH),
        Dict("field"=>"artifacts.manifest", "value"=>path),
        Dict("field"=>"artifacts.script", "value"=>SCRIPT_PATH),
    ]
    harness_validate_manifest_contract(d, contract; path=path)
    get(d["artifacts"], "manifest", nothing) == path ||
        error("Compute gate failed for $path: manifest artifact path mismatch")
    get(d["artifacts"], "script", nothing) == SCRIPT_PATH ||
        error("Compute gate failed for $path: script artifact path mismatch")
    return true
end

# ---------------- Hamiltonian + DMRG (PBC) ----------------

function build_tfim(sites, h; pbc::Bool=true)
    L = length(sites)
    os = OpSum()
    for i in 1:(L-1)
        os += -4.0, "Sx", i, "Sx", i+1
    end
    if pbc && L > 2
        os += -4.0, "Sx", L, "Sx", 1
    end
    for i in 1:L
        os += -2.0 * h, "Sz", i
    end
    return MPO(os, sites)
end

function dmrg_groundstate(L, h, chi; cutoff=1e-12, nsweeps=30, pbc::Bool=true,
                          initial_state=nothing)
    sites = siteinds("S=1/2", L; conserve_qns=false)
    H = build_tfim(sites, h; pbc=pbc)
    psi0 = harness_initial_mps(sites, initial_state; default_linkdims=4)
    sched = vcat(fill(min(10, chi), 4), fill(chi, nsweeps - 4))
    energy, psi = dmrg(H, psi0; nsweeps=nsweeps, maxdim=sched, cutoff=cutoff, outputlevel=0)
    return energy, psi, sites
end

# ---------------- ED ground state (small L_min) ----------------

function ed_groundstate(L, h; pbc::Bool=true)
    dim = 2^L
    H = zeros(Float64, dim, dim)
    for s in 0:(dim-1)
        d = 0.0
        for i in 0:(L-1)
            bit = (s >> i) & 1
            d += -h * (1 - 2*bit)
        end
        H[s+1, s+1] = d
    end
    bond_max = pbc ? L-1 : L-2
    for i in 0:bond_max
        j = (i + 1) % L
        mask = (1 << i) | (1 << j)
        for s in 0:(dim-1)
            sp = s ⊻ mask
            H[sp+1, s+1] += -1.0
        end
    end
    F = eigen(Symmetric(H))
    return F.values[1], F.vectors[:, 1]
end

# ---------------- Pauli expectations ----------------

function ed_pauli_expectation(psi::Vector{Float64}, p::Vector{Int}, L::Int)
    dim = length(psi)
    val = 0.0 + 0.0im
    @inbounds for s in 0:(dim-1)
        coeff = 1.0 + 0.0im
        sp = s
        for i in 1:L
            pi_ = p[i]
            bit = (sp >> (i-1)) & 1
            if pi_ == 1
                sp ⊻= (1 << (i-1))
            elseif pi_ == 2
                sp ⊻= (1 << (i-1))
                coeff *= (bit == 0 ? 1im : -1im)
            elseif pi_ == 3
                if bit == 1
                    coeff *= -1
                end
            end
        end
        val += conj(psi[sp+1]) * coeff * psi[s+1]
    end
    return real(val)
end

function mps_pauli_expectation(psi::MPS, p::Vector{Int}, sites)
    Ppsi = copy(psi)
    for i in 1:length(p)
        pi_ = p[i]
        pi_ == 0 && continue
        opname = pi_ == 1 ? "Sx" : (pi_ == 2 ? "Sy" : "Sz")
        Op = 2.0 * op(opname, sites[i])
        T = Op * Ppsi[i]
        noprime!(T)
        Ppsi[i] = T
    end
    return real(inner(psi, Ppsi))
end

function harness_check_ids(checks)
    checks isa AbstractVector || error("symmetry_checks must be a list")
    return [string(check["id"]) for check in checks]
end

function mps_constraint_evidence(checks, states::AbstractDict; default_tolerance::Float64)
    checks isa AbstractVector || error("symmetry_checks must be a list")
    evidence = Dict{String,Any}[]
    for check in checks
        check isa AbstractDict || error("Each symmetry check must be an object")
        kind = string(check["kind"])
        kind == "uniform_pauli_expectation" ||
            error("Unsupported MPS symmetry check kind '$kind'")
        target = string(check["target"])
        haskey(states, target) || error("Unknown symmetry-check target '$target'")
        state = states[target]
        code = Int(check["pauli_code"])
        value = mps_pauli_expectation(state.psi, fill(code, length(state.sites)), state.sites)
        item = Dict{String,Any}(
            "id" => string(check["id"]),
            "kind" => kind,
            "target" => target,
            "pauli_code" => code,
            "observable" => Dict("type"=>"uniform_pauli_code", "pauli_code"=>code,
                                 "length"=>length(state.sites)),
            "value" => value,
            "tolerance" => Float64(get(check, "tolerance", default_tolerance)),
        )
        if haskey(check, "expected_abs")
            item["expected_abs"] = Float64(check["expected_abs"])
        elseif haskey(check, "expected")
            item["expected"] = Float64(check["expected"])
        else
            error("Symmetry check '$(check["id"])' must declare expected or expected_abs")
        end
        item["status"] = harness_evidence_computed_status(item)
        push!(evidence, item)
    end
    harness_validate_evidence(evidence; required_ids=harness_check_ids(checks))
    return evidence
end

# Cached MPS expectation backend.
#
# Store dense MPS tensors plus left/right Pauli environments for the current
# string. Candidate local updates are evaluated by contracting only the changed
# interval between cached environments; accepted updates refresh the affected
# environment ranges. This is the MPS analog of cached TTN link operators: the
# chain state owns reusable contraction state instead of rebuilding P|ψ⟩.
mutable struct CachedMPSPauliExpectation
    arrays::Vector{Array{ComplexF64, 3}}
    p::Vector{Int}
    left::Vector{Matrix{ComplexF64}}
    right::Vector{Matrix{ComplexF64}}
end

function mps_dense_arrays(psi_in::MPS, sites)
    psi = copy(psi_in)
    orthogonalize!(psi, 1)
    L = length(psi)
    arrays = Vector{Array{ComplexF64, 3}}(undef, L)
    for i in 1:L
        T = psi[i]
        s_idx = sites[i]
        l_idx = i == 1 ? nothing : commonind(psi[i-1], psi[i])
        r_idx = i == L ? nothing : commonind(psi[i], psi[i+1])
        s_dim = dim(s_idx)
        l_dim = l_idx === nothing ? 1 : dim(l_idx)
        r_dim = r_idx === nothing ? 1 : dim(r_idx)
        A = zeros(ComplexF64, s_dim, l_dim, r_dim)
        if i == 1 && i == L
            for s in 1:s_dim
                A[s, 1, 1] = T[s_idx => s]
            end
        elseif i == 1
            for s in 1:s_dim, r in 1:r_dim
                A[s, 1, r] = T[s_idx => s, r_idx => r]
            end
        elseif i == L
            for s in 1:s_dim, l in 1:l_dim
                A[s, l, 1] = T[l_idx => l, s_idx => s]
            end
        else
            for s in 1:s_dim, l in 1:l_dim, r in 1:r_dim
                A[s, l, r] = T[l_idx => l, s_idx => s, r_idx => r]
            end
        end
        arrays[i] = A
    end
    return arrays
end

function apply_forward_env(left::Matrix{ComplexF64}, A::Array{ComplexF64,3}, code::Int)
    P = PAULI_MATRICES[code + 1]
    _, _, r_dim = size(A)
    out = zeros(ComplexF64, r_dim, r_dim)
    for s in 1:2, t in 1:2
        coeff = P[s, t]
        coeff == 0 && continue
        As = @view A[s, :, :]
        At = @view A[t, :, :]
        out .+= coeff .* (adjoint(As) * left * At)
    end
    return out
end

function apply_backward_env(right::Matrix{ComplexF64}, A::Array{ComplexF64,3}, code::Int)
    P = PAULI_MATRICES[code + 1]
    _, l_dim, _ = size(A)
    out = zeros(ComplexF64, l_dim, l_dim)
    for s in 1:2, t in 1:2
        coeff = P[s, t]
        coeff == 0 && continue
        As = @view A[s, :, :]
        At = @view A[t, :, :]
        out .+= coeff .* (conj.(As) * right * transpose(At))
    end
    return out
end

interval_value(env::Matrix{ComplexF64}, right::Matrix{ComplexF64}) = real(sum(env .* right))

function rebuild_cached_envs!(cache::CachedMPSPauliExpectation)
    L = length(cache.p)
    cache.left[1] = ones(ComplexF64, 1, 1)
    for i in 1:L
        cache.left[i + 1] = apply_forward_env(cache.left[i], cache.arrays[i], cache.p[i])
    end
    cache.right[L + 1] = ones(ComplexF64, 1, 1)
    for i in L:-1:1
        cache.right[i] = apply_backward_env(cache.right[i + 1], cache.arrays[i], cache.p[i])
    end
    return cache
end

function refresh_cached_envs!(cache::CachedMPSPauliExpectation, lo::Int, hi::Int)
    L = length(cache.p)
    for i in lo:L
        cache.left[i + 1] = apply_forward_env(cache.left[i], cache.arrays[i], cache.p[i])
    end
    for i in hi:-1:1
        cache.right[i] = apply_backward_env(cache.right[i + 1], cache.arrays[i], cache.p[i])
    end
    return cache
end

function CachedMPSPauliExpectation(psi::MPS, sites; p=zeros(Int, length(psi)))
    arrays = mps_dense_arrays(psi, sites)
    L = length(arrays)
    cache = CachedMPSPauliExpectation(arrays, copy(p),
                                      [zeros(ComplexF64, 0, 0) for _ in 1:(L + 1)],
                                      [zeros(ComplexF64, 0, 0) for _ in 1:(L + 1)])
    return rebuild_cached_envs!(cache)
end

function set_cached_pauli!(cache::CachedMPSPauliExpectation, site::Int, code::Int)
    old = cache.p[site]
    old == code && return old
    cache.p[site] = code
    refresh_cached_envs!(cache, site, site)
    return old
end

function set_cached_paulis!(cache::CachedMPSPauliExpectation, i::Int, code_i::Int, j::Int, code_j::Int)
    old_i = cache.p[i]
    old_j = cache.p[j]
    if i == j
        cache.p[i] = code_j
        refresh_cached_envs!(cache, i, i)
        return old_i, old_j
    end
    cache.p[i] = code_i
    cache.p[j] = code_j
    refresh_cached_envs!(cache, min(i, j), max(i, j))
    return old_i, old_j
end

function set_pauli_string!(cache::CachedMPSPauliExpectation, p::Vector{Int})
    @assert length(p) == length(cache.p)
    cache.p .= p
    return rebuild_cached_envs!(cache)
end

function cached_candidate_value(cache::CachedMPSPauliExpectation, i::Int, code_i::Int)
    env = apply_forward_env(cache.left[i], cache.arrays[i], code_i)
    return interval_value(env, cache.right[i + 1])
end

function cached_candidate_value(cache::CachedMPSPauliExpectation, i::Int, code_i::Int, j::Int, code_j::Int)
    lo, hi = min(i, j), max(i, j)
    env = cache.left[lo]
    for k in lo:hi
        code = k == i ? code_i : (k == j ? code_j : cache.p[k])
        env = apply_forward_env(env, cache.arrays[k], code)
    end
    return interval_value(env, cache.right[hi + 1])
end

cached_pauli_value(cache::CachedMPSPauliExpectation) = real(cache.left[end][1, 1])

@inline pauli_unrestricted_sector(::Vector{Int}) = true

@inline function pauli_even_xy_even_y_sector(p::Vector{Int})
    x_parity = false
    y_parity = false
    @inbounds for code in p
        x_parity ⊻= (code == 1 || code == 2)
        y_parity ⊻= (code == 2)
    end
    return !x_parity && !y_parity
end

@inline tfim_fig4_pauli_sector(p::Vector{Int}) = pauli_even_xy_even_y_sector(p)

function pauli_sector_allows_after(allowed, p::Vector{Int}, i::Int, code_i::Int)
    old_i = p[i]
    p[i] = code_i
    ok = allowed(p)
    p[i] = old_i
    return ok
end

function pauli_sector_allows_after(allowed, p::Vector{Int}, i::Int, code_i::Int, j::Int, code_j::Int)
    old_i = p[i]
    old_j = p[j]
    p[i] = code_i
    p[j] = code_j
    ok = allowed(p)
    p[i] = old_i
    p[j] = old_j
    return ok
end

@inline function projected_pauli_value(expect_fn, p::Vector{Int}, allowed)
    return allowed(p) ? expect_fn(p) : 0.0
end

@inline function projected_cached_pauli_value(cache::CachedMPSPauliExpectation, allowed)
    return allowed(cache.p) ? cached_pauli_value(cache) : 0.0
end

@inline pauli_is_xy(code::Int) = code == 1 || code == 2
pauli_group_partner(code::Int, rng) = pauli_is_xy(code) ? rand(rng, (0, 3)) : rand(rng, (1, 2))

# ---------------- Eq.-(24) ratio chain (n=2) ----------------
#
# Sampling distribution: Π_{P,2}(P) ∝ |⟨P⟩_L|⁴.
# Metropolis ratio: |new_v|⁴ / |cur_v|⁴.
# Per-step ratio observable:
#   R(P) = |⟨P^(1)⟩_{L/2}|⁴ · |⟨P^(2)⟩_{L/2}|⁴ / |⟨P⟩_L|⁴
# Estimator:
#   c_L = -log⟨R⟩_{Π_{P,2}}
#
# expect_L  : (Vector{Int}) → ⟨P⟩_L
# expect_Lh : (Vector{Int}) → ⟨P_half⟩_{L/2}    (length L/2 vector)

function pauli_markov_cL_eq24(expect_L, expect_Lh, L::Int;
                              n_steps=10^5, n_warmup=10^4, seed::UInt32=UInt32(0xC0FFEE),
                              progress_every=max(1, n_steps ÷ 10),
                              sample_filter=pauli_unrestricted_sector,
                              factor_filter=sample_filter,
                              proposal::Symbol=:paper)
    @assert iseven(L)
    @assert proposal in (:paper, :group)
    Lh = L ÷ 2
    rng = MersenneTwister(seed)
    p = zeros(Int, L)
    cur_v = expect_L(p)
    cur_w = abs(cur_v)^4 / 2.0^L          # n=2 sampling weight
    proposal_name = proposal == :paper ? "paper_multiply_Zi_or_XiXj" : "symmetric_group_kernel"
    multiply_Z(old::Int) = old ⊻ 3
    multiply_X(old::Int) = old ⊻ 1
    @assert sample_filter(p)

    accum_R = 0.0
    n_acc = 0
    n_R = 0

    block_size = max(1_000, n_steps ÷ 100)
    block_means = Float64[]
    cur_block_sum = 0.0
    cur_block_idx = 0

    p1 = zeros(Int, Lh)
    p2 = zeros(Int, Lh)

    for step in 1:(n_warmup + n_steps)
        proposal_kind = rand(rng) < 0.5 ? :single : :two
        if proposal_kind == :single
            i = rand(rng, 1:L)
            old_pi = p[i]
            new_pi = multiply_Z(old_pi)
            p[i] = new_pi
            if sample_filter(p)
                new_v = expect_L(p)
                new_w = abs(new_v)^4 / 2.0^L
                ratio = (cur_w == 0 && new_w == 0) ? 0.0 : (cur_w == 0 ? Inf : new_w / cur_w)
                if rand(rng) < ratio
                    cur_v = new_v; cur_w = new_w; n_acc += 1
                else
                    p[i] = old_pi
                end
            else
                p[i] = old_pi
            end
        else
            i = rand(rng, 1:L); j = rand(rng, 1:(L-1)); j >= i && (j += 1)
            old_pi, old_pj = p[i], p[j]
            if proposal == :paper
                new_pi = multiply_X(old_pi)
                new_pj = multiply_X(old_pj)
            else
                new_pi = pauli_group_partner(old_pi, rng)
                new_pj = pauli_group_partner(old_pj, rng)
            end
            p[i] = new_pi; p[j] = new_pj
            if sample_filter(p)
                new_v = expect_L(p)
                new_w = abs(new_v)^4 / 2.0^L
                ratio = (cur_w == 0 && new_w == 0) ? 0.0 : (cur_w == 0 ? Inf : new_w / cur_w)
                if rand(rng) < ratio
                    cur_v = new_v; cur_w = new_w; n_acc += 1
                else
                    p[i] = old_pi; p[j] = old_pj
                end
            else
                p[i] = old_pi; p[j] = old_pj
            end
        end

        if step > n_warmup
            # Split P into halves; evaluate both on |ψ_{L/2}⟩.
            @inbounds for k in 1:Lh
                p1[k] = p[k]
                p2[k] = p[k + Lh]
            end
            v1 = projected_pauli_value(expect_Lh, p1, factor_filter)
            v2 = projected_pauli_value(expect_Lh, p2, factor_filter)
            denom = abs(cur_v)^4
            if denom > 0
                R = (abs(v1)^4 * abs(v2)^4) / denom
                accum_R += R
                n_R += 1
                cur_block_sum += R
                cur_block_idx += 1
                if cur_block_idx == block_size
                    push!(block_means, cur_block_sum / block_size)
                    cur_block_sum = 0.0; cur_block_idx = 0
                end
                if n_R % progress_every == 0
                    mean_R_now = accum_R / n_R
                    @printf("      [%s sample %d/%d] c_L=%+.6f mean_R=%.6e accept=%.4f blocks=%d\n",
                            proposal_name, n_R, n_steps, -log(mean_R_now), mean_R_now,
                            n_acc / step, length(block_means))
                    flush(stdout)
                end
            end
            # If denom == 0 the chain is stuck on |⟨P⟩_L|² = 0 — skip; n=2
            # weight is zero too so this state has measure zero in Π_{P,2}.
        end
    end

    mean_R = accum_R / n_R
    se_R   = length(block_means) > 1 ? std(block_means) / sqrt(length(block_means)) : NaN
    cL     = -log(mean_R)
    se_cL  = se_R / mean_R
    accept = n_acc / (n_warmup + n_steps)
    return (cL=cL, se=se_cL, accept=accept, mean_R=mean_R, se_R=se_R,
            proposal=proposal_name, block_size=block_size, n_recorded=n_R,
            expectation_backend="stateless_expectation")
end

function pauli_markov_cL_eq24_cached(full_cache::CachedMPSPauliExpectation, expect_Lh, L::Int;
                                     half_cache1=nothing, half_cache2=nothing,
                                     n_steps=10^5, n_warmup=10^4,
                                     seed::UInt32=UInt32(0xC0FFEE),
                                     progress_every=max(1, n_steps ÷ 10),
                                     sample_filter=pauli_unrestricted_sector,
                                     factor_filter=sample_filter,
                                     proposal::Symbol=:paper)
    @assert iseven(L)
    @assert proposal in (:paper, :group)
    Lh = L ÷ 2
    rng = MersenneTwister(seed)
    set_pauli_string!(full_cache, zeros(Int, L))
    half_cache1 !== nothing && set_pauli_string!(half_cache1, zeros(Int, Lh))
    half_cache2 !== nothing && set_pauli_string!(half_cache2, zeros(Int, Lh))

    cur_v = cached_pauli_value(full_cache)
    cur_w = abs(cur_v)^4 / 2.0^L
    proposal_name = proposal == :paper ? "paper_multiply_Zi_or_XiXj" : "symmetric_group_kernel"
    multiply_Z(old::Int) = old ⊻ 3
    multiply_X(old::Int) = old ⊻ 1
    @assert sample_filter(full_cache.p)

    accum_R = 0.0
    n_acc = 0
    n_R = 0
    block_size = max(1_000, n_steps ÷ 100)
    block_means = Float64[]
    cur_block_sum = 0.0
    cur_block_idx = 0
    p1 = zeros(Int, Lh)
    p2 = zeros(Int, Lh)

    function set_half_site!(site::Int, code::Int)
        if half_cache1 !== nothing
            if site <= Lh
                set_cached_pauli!(half_cache1, site, code)
            else
                set_cached_pauli!(half_cache2, site - Lh, code)
            end
        end
        return nothing
    end

    function half_values()
        if half_cache1 !== nothing
            v1 = projected_cached_pauli_value(half_cache1, factor_filter)
            v2 = projected_cached_pauli_value(half_cache2, factor_filter)
            return v1, v2
        end
        @inbounds for k in 1:Lh
            p1[k] = full_cache.p[k]
            p2[k] = full_cache.p[k + Lh]
        end
        v1 = projected_pauli_value(expect_Lh, p1, factor_filter)
        v2 = projected_pauli_value(expect_Lh, p2, factor_filter)
        return v1, v2
    end

    for step in 1:(n_warmup + n_steps)
        proposal_kind = rand(rng) < 0.5 ? :single : :two
        if proposal_kind == :single
            i = rand(rng, 1:L)
            new_i = multiply_Z(full_cache.p[i])
            allowed = pauli_sector_allows_after(sample_filter, full_cache.p, i, new_i)
            new_v = allowed ? cached_candidate_value(full_cache, i, new_i) : cur_v
            j = 0; new_j = 0
        else
            i = rand(rng, 1:L); j = rand(rng, 1:(L-1)); j >= i && (j += 1)
            if proposal == :paper
                new_i = multiply_X(full_cache.p[i])
                new_j = multiply_X(full_cache.p[j])
            else
                new_i = pauli_group_partner(full_cache.p[i], rng)
                new_j = pauli_group_partner(full_cache.p[j], rng)
            end
            allowed = pauli_sector_allows_after(sample_filter, full_cache.p, i, new_i, j, new_j)
            new_v = allowed ? cached_candidate_value(full_cache, i, new_i, j, new_j) : cur_v
        end

        new_w = abs(new_v)^4 / 2.0^L
        ratio = (cur_w == 0 && new_w == 0) ? 0.0 : (cur_w == 0 ? Inf : new_w / cur_w)
        if allowed && rand(rng) < ratio
            if proposal_kind == :single
                set_cached_pauli!(full_cache, i, new_i)
                set_half_site!(i, new_i)
            else
                set_cached_paulis!(full_cache, i, new_i, j, new_j)
                set_half_site!(i, new_i)
                set_half_site!(j, new_j)
            end
            cur_v = new_v; cur_w = new_w; n_acc += 1
        end

        if step > n_warmup
            v1, v2 = half_values()
            denom = abs(cur_v)^4
            if denom > 0
                R = (abs(v1)^4 * abs(v2)^4) / denom
                accum_R += R
                n_R += 1
                cur_block_sum += R
                cur_block_idx += 1
                if cur_block_idx == block_size
                    push!(block_means, cur_block_sum / block_size)
                    cur_block_sum = 0.0; cur_block_idx = 0
                end
                if n_R % progress_every == 0
                    mean_R_now = accum_R / n_R
                    @printf("      [%s cached sample %d/%d] c_L=%+.6f mean_R=%.6e accept=%.4f blocks=%d\n",
                            proposal_name, n_R, n_steps, -log(mean_R_now), mean_R_now,
                            n_acc / step, length(block_means))
                    flush(stdout)
                end
            end
        end
    end

    mean_R = accum_R / n_R
    se_R = length(block_means) > 1 ? std(block_means) / sqrt(length(block_means)) : NaN
    cL = -log(mean_R)
    se_cL = se_R / mean_R
    accept = n_acc / (n_warmup + n_steps)
    backend = half_cache1 === nothing ? "mps_cached_env_full_ed_half" : "mps_cached_env"
    return (cL=cL, se=se_cL, accept=accept, mean_R=mean_R, se_R=se_R,
            proposal=proposal_name, block_size=block_size, n_recorded=n_R,
            expectation_backend=backend)
end

function bridge_ratio_estimate(f_on_f::Vector{Float64}, g_on_f::Vector{Float64},
                               f_on_g::Vector{Float64}, g_on_g::Vector{Float64};
                               maxiter::Int=100, tol::Float64=1e-10)
    sp = length(f_on_f) / (length(f_on_f) + length(f_on_g))
    sg = 1.0 - sp
    r = 1.0
    for _ in 1:maxiter
        num = mean(f_on_g ./ (sp .* f_on_g .+ sg .* r .* g_on_g))
        den = mean(g_on_f ./ (sp .* f_on_f .+ sg .* r .* g_on_f))
        r_new = num / den
        abs(log(r_new / r)) < tol && return r_new
        r = r_new
    end
    return r
end

function bridge_block_se(f_on_f::Vector{Float64}, g_on_f::Vector{Float64},
                         f_on_g::Vector{Float64}, g_on_g::Vector{Float64},
                         n_blocks::Int)
    n = min(length(f_on_f), length(f_on_g))
    block = n ÷ n_blocks
    block < 100 && return NaN
    cs = Float64[]
    for b in 1:n_blocks
        lo = (b - 1) * block + 1
        hi = b == n_blocks ? n : b * block
        r = bridge_ratio_estimate(f_on_f[lo:hi], g_on_f[lo:hi],
                                  f_on_g[lo:hi], g_on_g[lo:hi])
        push!(cs, log(r))
    end
    return length(cs) > 1 ? std(cs) / sqrt(length(cs)) : NaN
end

function pauli_bridge_cL_eq24_cached(full_cache::CachedMPSPauliExpectation,
                                     expect_Lh, L::Int;
                                     half_cache1=nothing, half_cache2=nothing,
                                     n_steps=10^5, n_warmup=10^4,
                                     seed::UInt32=UInt32(0xB21D6E),
                                     progress_every=max(1, n_steps ÷ 10),
                                     sample_filter=pauli_unrestricted_sector,
                                     factor_filter=sample_filter,
                                     proposal::Symbol=:paper)
    @assert iseven(L)
    @assert proposal in (:paper, :group)
    Lh = L ÷ 2
    rng = MersenneTwister(seed)
    proposal_name = proposal == :paper ? "bridge_paper_multiply_Zi_or_XiXj" : "bridge_symmetric_group_kernel"
    multiply_Z(old::Int) = old ⊻ 3
    multiply_X(old::Int) = old ⊻ 1

    f_on_f = Float64[]
    g_on_f = Float64[]
    f_on_g = Float64[]
    g_on_g = Float64[]
    sizehint!(f_on_f, n_steps); sizehint!(g_on_f, n_steps)
    sizehint!(f_on_g, n_steps); sizehint!(g_on_g, n_steps)

    p1 = zeros(Int, Lh)
    p2 = zeros(Int, Lh)

    function split_full!(pfull)
        @inbounds for k in 1:Lh
            p1[k] = pfull[k]
            p2[k] = pfull[k + Lh]
        end
    end

    function half_values_from_full()
        if half_cache1 !== nothing
            v1 = projected_cached_pauli_value(half_cache1, factor_filter)
            v2 = projected_cached_pauli_value(half_cache2, factor_filter)
            return v1, v2
        end
        split_full!(full_cache.p)
        return projected_pauli_value(expect_Lh, p1, factor_filter),
               projected_pauli_value(expect_Lh, p2, factor_filter)
    end

    function set_half_site!(site::Int, code::Int)
        if half_cache1 !== nothing
            if site <= Lh
                set_cached_pauli!(half_cache1, site, code)
            else
                set_cached_pauli!(half_cache2, site - Lh, code)
            end
        end
        return nothing
    end

    set_pauli_string!(full_cache, zeros(Int, L))
    half_cache1 !== nothing && set_pauli_string!(half_cache1, zeros(Int, Lh))
    half_cache2 !== nothing && set_pauli_string!(half_cache2, zeros(Int, Lh))
    cur_v = cached_pauli_value(full_cache)
    cur_f = abs(cur_v)^4
    n_acc_f = 0
    for step in 1:(n_warmup + n_steps)
        proposal_kind = rand(rng) < 0.5 ? :single : :two
        if proposal_kind == :single
            i = rand(rng, 1:L)
            new_i = multiply_Z(full_cache.p[i])
            allowed = pauli_sector_allows_after(sample_filter, full_cache.p, i, new_i)
            new_v = allowed ? cached_candidate_value(full_cache, i, new_i) : cur_v
            j = 0; new_j = 0
        else
            i = rand(rng, 1:L)
            j = rand(rng, 1:(L - 1)); j >= i && (j += 1)
            if proposal == :paper
                new_i = multiply_X(full_cache.p[i])
                new_j = multiply_X(full_cache.p[j])
            else
                new_i = pauli_group_partner(full_cache.p[i], rng)
                new_j = pauli_group_partner(full_cache.p[j], rng)
            end
            allowed = pauli_sector_allows_after(sample_filter, full_cache.p, i, new_i, j, new_j)
            new_v = allowed ? cached_candidate_value(full_cache, i, new_i, j, new_j) : cur_v
        end
        new_f = abs(new_v)^4
        ratio = (cur_f == 0 && new_f == 0) ? 0.0 : (cur_f == 0 ? Inf : new_f / cur_f)
        if allowed && rand(rng) < ratio
            if proposal_kind == :single
                set_cached_pauli!(full_cache, i, new_i)
                set_half_site!(i, new_i)
            else
                set_cached_paulis!(full_cache, i, new_i, j, new_j)
                set_half_site!(i, new_i); set_half_site!(j, new_j)
            end
            cur_v = new_v; cur_f = new_f; n_acc_f += 1
        end
        if step > n_warmup
            v1, v2 = half_values_from_full()
            push!(f_on_f, cur_f)
            push!(g_on_f, abs(v1)^4 * abs(v2)^4)
            if length(f_on_f) % progress_every == 0
                @printf("      [%s full-target sample %d/%d] accept=%.4f\n",
                        proposal_name, length(f_on_f), n_steps, n_acc_f / step)
                flush(stdout)
            end
        end
    end

    q1 = zeros(Int, Lh)
    q2 = zeros(Int, Lh)
    qfull = zeros(Int, L)
    set_pauli_string!(full_cache, qfull)
    half_cache1 !== nothing && set_pauli_string!(half_cache1, q1)
    half_cache2 !== nothing && set_pauli_string!(half_cache2, q2)
    v1 = half_cache1 === nothing ? expect_Lh(q1) : cached_pauli_value(half_cache1)
    v2 = half_cache2 === nothing ? expect_Lh(q2) : cached_pauli_value(half_cache2)
    cur_g = abs(v1)^4 * abs(v2)^4
    cur_full_v = cached_pauli_value(full_cache)
    n_acc_g = 0

    function q_half_value(which::Int, p::Vector{Int})
        if half_cache1 === nothing
            return projected_pauli_value(expect_Lh, p, factor_filter)
        end
        return which == 1 ? projected_cached_pauli_value(half_cache1, factor_filter) :
                            projected_cached_pauli_value(half_cache2, factor_filter)
    end

    for step in 1:(n_warmup + n_steps)
        which = rand(rng) < 0.5 ? 1 : 2
        p = which == 1 ? q1 : q2
        offset = which == 1 ? 0 : Lh
        other_v = which == 1 ? v2 : v1
        proposal_kind = rand(rng) < 0.5 ? :single : :two
        if proposal_kind == :single
            i = rand(rng, 1:Lh)
            old_i = p[i]
            new_i = multiply_Z(old_i)
            allowed = pauli_sector_allows_after(factor_filter, p, i, new_i)
            if allowed
                if half_cache1 !== nothing
                    new_half_v = cached_candidate_value(which == 1 ? half_cache1 : half_cache2, i, new_i)
                else
                    p[i] = new_i; new_half_v = expect_Lh(p); p[i] = old_i
                end
                new_g = abs(new_half_v)^4 * abs(other_v)^4
            else
                new_half_v = which == 1 ? v1 : v2
                new_g = cur_g
            end
            j = 0; new_j = 0
        else
            i = rand(rng, 1:Lh)
            j = rand(rng, 1:(Lh - 1)); j >= i && (j += 1)
            old_i, old_j = p[i], p[j]
            if proposal == :paper
                new_i = multiply_X(old_i)
                new_j = multiply_X(old_j)
            else
                new_i = pauli_group_partner(old_i, rng)
                new_j = pauli_group_partner(old_j, rng)
            end
            allowed = pauli_sector_allows_after(factor_filter, p, i, new_i, j, new_j)
            if allowed
                if half_cache1 !== nothing
                    new_half_v = cached_candidate_value(which == 1 ? half_cache1 : half_cache2,
                                                        i, new_i, j, new_j)
                else
                    p[i] = new_i; p[j] = new_j
                    new_half_v = expect_Lh(p)
                    p[i] = old_i; p[j] = old_j
                end
                new_g = abs(new_half_v)^4 * abs(other_v)^4
            else
                new_half_v = which == 1 ? v1 : v2
                new_g = cur_g
            end
        end
        ratio = (cur_g == 0 && new_g == 0) ? 0.0 : (cur_g == 0 ? Inf : new_g / cur_g)
        if allowed && rand(rng) < ratio
            if proposal_kind == :single
                p[i] = new_i
                qfull[offset + i] = new_i
                set_cached_pauli!(full_cache, offset + i, new_i)
                if half_cache1 !== nothing
                    set_cached_pauli!(which == 1 ? half_cache1 : half_cache2, i, new_i)
                end
            else
                p[i] = new_i; p[j] = new_j
                qfull[offset + i] = new_i; qfull[offset + j] = new_j
                set_cached_paulis!(full_cache, offset + i, new_i, offset + j, new_j)
                if half_cache1 !== nothing
                    set_cached_paulis!(which == 1 ? half_cache1 : half_cache2, i, new_i, j, new_j)
                end
            end
            if which == 1
                v1 = new_half_v
            else
                v2 = new_half_v
            end
            cur_g = new_g
            cur_full_v = cached_pauli_value(full_cache)
            n_acc_g += 1
        end
        if step > n_warmup
            push!(f_on_g, abs(cur_full_v)^4)
            push!(g_on_g, cur_g)
            if length(f_on_g) % progress_every == 0
                @printf("      [%s product-target sample %d/%d] accept=%.4f\n",
                        proposal_name, length(f_on_g), n_steps, n_acc_g / step)
                flush(stdout)
            end
        end
    end

    r = bridge_ratio_estimate(f_on_f, g_on_f, f_on_g, g_on_g)
    cL = log(r)
    se = bridge_block_se(f_on_f, g_on_f, f_on_g, g_on_g, 20)
    return (cL=cL, se=se, accept=(n_acc_f + n_acc_g) / (2 * (n_warmup + n_steps)),
            mean_R=1 / r, se_R=NaN, proposal=proposal_name,
            block_size=max(1, n_steps ÷ 20), n_recorded=2 * n_steps,
            expectation_backend="mps_cached_env_bridge")
end

# ---------------- Exact-sum SRE (anchor at L_min) ----------------

function exact_sre_M2_from_expect(expect_fn, L::Int)
    total = 0.0
    p = zeros(Int, L)
    for idx in 0:(4^L - 1)
        x = idx
        for i in 1:L
            p[i] = x & 3
            x >>= 2
        end
        v = expect_fn(p)
        total += v^4
    end
    return -log(total / 2.0^L)
end

# ---------------- Increment recursion ----------------
#
# M_2(L) = 2^k · M_2(L_min) − Σ_{j=1..k} 2^{k-j} · c_{L_min · 2^j}
# Inputs: M_2_min anchor at L_min; vector cs[k] for L = L_min·2^k, k=1..K.
# Returns Dict L → M_2(L) for L = L_min, L_min·2, …, L_min·2^K.

function increment_recursion(M2_min::Float64, L_min::Int, cs::Vector{Float64})
    out = Dict{Int, Float64}()
    out[L_min] = M2_min
    M2_prev = M2_min
    for (k, c) in enumerate(cs)
        L_k = L_min * 2^k
        M2_k = 2 * M2_prev - c
        out[L_k] = M2_k
        M2_prev = M2_k
    end
    return out
end

# ---------------- Per-cell driver ----------------

function compute_cL_cell(L::Int, h::Float64; chi=30, n_steps=10^5, n_warmup=10^4,
                          seed_offset::Int=0, pbc::Bool=true,
                          pauli_sector_filter=tfim_fig4_pauli_sector,
                          proposal::Symbol=:paper,
                          estimator::Symbol=:ratio,
                          initial_state=nothing,
                          symmetry_checks=Any[],
                          sample_blocks::Int=20,
                          pauli_chi::Int=16,
                          pauli_chi_check::Int=0,
                          pauli_chi_tol::Float64=0.02,
                          symmetry_tol::Float64=1e-6)
    @assert iseven(L) && L ≥ 4
    Lh = L ÷ 2
    use_mps_norm = estimator in (:pauli_mps_norm, :pauli_mps_born_direct)

    full_cache = nothing
    half_cache1 = nothing
    half_cache2 = nothing
    psi_L_mps = nothing
    sites_L = nothing
    psi_Lh_mps = nothing
    sites_Lh = nothing

    # Ground state at L (for sampling distribution and denominator).
    if L ≤ 8 && !use_mps_norm
        E_L, psi_L = ed_groundstate(L, h; pbc=pbc)
        expect_L = (q) -> ed_pauli_expectation(psi_L, q, L)
    else
        E_L, psi_L_mps, sites_L = dmrg_groundstate(L, h, chi; pbc=pbc,
                                                   initial_state=initial_state)
        full_cache = CachedMPSPauliExpectation(psi_L_mps, sites_L)
        expect_L = (q) -> mps_pauli_expectation(psi_L_mps, q, sites_L)
    end

    # Ground state at L/2 (for ratio numerator). Same h, same PBC, same translation invariance.
    if Lh ≤ 8 && !use_mps_norm
        E_Lh, psi_Lh = ed_groundstate(Lh, h; pbc=pbc)
        expect_Lh = (q) -> ed_pauli_expectation(psi_Lh, q, Lh)
    else
        E_Lh, psi_Lh_mps, sites_Lh = dmrg_groundstate(Lh, h, chi; pbc=pbc,
                                                      initial_state=initial_state)
        half_cache1 = CachedMPSPauliExpectation(psi_Lh_mps, sites_Lh)
        half_cache2 = CachedMPSPauliExpectation(psi_Lh_mps, sites_Lh)
        expect_Lh = (q) -> mps_pauli_expectation(psi_Lh_mps, q, sites_Lh)
    end

    seed = UInt32(0xC0FFEE) + UInt32(seed_offset & 0xFFFF)
    res = if estimator == :bridge
        full_cache === nothing && error("Bridge estimator currently requires cached MPS full-system backend")
        pauli_bridge_cL_eq24_cached(full_cache, expect_Lh, L;
                                    half_cache1=half_cache1, half_cache2=half_cache2,
                                    n_steps=n_steps, n_warmup=n_warmup, seed=seed,
                                    sample_filter=pauli_sector_filter,
                                    factor_filter=pauli_sector_filter,
                                    proposal=proposal)
    elseif estimator == :pauli_mps_norm
        isempty(symmetry_checks) &&
            error("Pauli-MPS norm estimator requires declared symmetry_checks for the target MPS states")
        symmetry_evidence = mps_constraint_evidence(
            symmetry_checks,
            Dict("full" => (psi=psi_L_mps, sites=sites_L),
                 "half" => (psi=psi_Lh_mps, sites=sites_Lh));
            default_tolerance=symmetry_tol,
        )
        pauli_chi_check = pauli_chi_check > pauli_chi ? pauli_chi_check : 2 * pauli_chi
        raw_B_L = pauli_mps_tensors(psi_L_mps, sites_L)
        raw_B_H = pauli_mps_tensors(psi_Lh_mps, sites_Lh)
        function cL_at_chi(χP::Int)
            B_L, trunc_L = compress_pauli_mps(raw_B_L, χP, 1e-12)
            B_H, trunc_H = compress_pauli_mps(raw_B_H, χP, 1e-12)
            sampler_L = SquaredPauliMPSSampler(B_L)
            sampler_H = SquaredPauliMPSSampler(B_H)
            cL = log(pauli_squared_mps_norm(sampler_L) / pauli_squared_mps_norm(sampler_H)^2)
            return (cL=cL, trunc_L=trunc_L, trunc_H=trunc_H)
        end
        low = cL_at_chi(pauli_chi)
        high = cL_at_chi(pauli_chi_check)
        compression_error = abs(high.cL - low.cL)
        compression_error <= pauli_chi_tol ||
            error("Pauli-MPS compression not converged at L=$L h=$h: |cL(χP=$pauli_chi_check)-cL(χP=$pauli_chi)|=$compression_error > $pauli_chi_tol")
        (cL=high.cL, se=compression_error, accept=1.0, mean_R=exp(-high.cL), se_R=compression_error,
         proposal="compressed_pauli_mps_norm", block_size=0, n_recorded=0,
         expectation_backend="pauli_mps_compressed_norm",
         pauli_trunc_L=high.trunc_L, pauli_trunc_H=high.trunc_H,
         pauli_chi_check=pauli_chi_check, pauli_chi_error=compression_error,
         symmetry_evidence=symmetry_evidence)
    elseif estimator == :pauli_mps_born_direct
        isempty(symmetry_checks) &&
            error("Pauli-MPS Born-direct estimator requires declared symmetry_checks for the target MPS states")
        symmetry_evidence = mps_constraint_evidence(
            symmetry_checks,
            Dict("full" => (psi=psi_L_mps, sites=sites_L),
                 "half" => (psi=psi_Lh_mps, sites=sites_Lh));
            default_tolerance=symmetry_tol,
        )
        pauli_chi_check = pauli_chi_check > pauli_chi ? pauli_chi_check : 2 * pauli_chi
        raw_B_L = pauli_mps_tensors(psi_L_mps, sites_L)
        raw_B_H = pauli_mps_tensors(psi_Lh_mps, sites_Lh)
        function sampled_cL_at_chi(χP::Int)
            B_L, trunc_L = compress_pauli_mps(raw_B_L, χP, 1e-12)
            B_H, trunc_H = compress_pauli_mps(raw_B_H, χP, 1e-12)
            res = pauli_mps_born_direct_cL(B_L, B_H; n_samples=n_steps,
                                           seed=seed,
                                           n_blocks=sample_blocks,
                                           progress_label=@sprintf("born-direct L=%d h=%.2f χP=%d", L, h, χP))
            return (cL=res.cL, se=res.se, trunc_L=trunc_L, trunc_H=trunc_H,
                    born_norm_full=res.born_norm_full, born_norm_half=res.born_norm_half,
                    mean_abs2_full=res.mean_abs2_full, mean_abs2_half=res.mean_abs2_half)
        end
        low = sampled_cL_at_chi(pauli_chi)
        high = sampled_cL_at_chi(pauli_chi_check)
        estimator_shift = abs(high.cL - low.cL)
        shift_noise = sqrt(high.se^2 + low.se^2)
        compression_excess = max(0.0, estimator_shift - 2 * shift_noise)
        compression_excess <= pauli_chi_tol ||
            error("Pauli-MPS Born-direct compression not converged at L=$L h=$h: max(0, |cL(χP=$pauli_chi_check)-cL(χP=$pauli_chi)| - 2σ)=$compression_excess > $pauli_chi_tol (raw shift=$estimator_shift, σ=$shift_noise)")
        se_total = sqrt(high.se^2 + estimator_shift^2)
        (cL=high.cL, se=se_total, accept=1.0, mean_R=nothing, se_R=nothing,
         proposal="pauli_mps_born_direct_sampling", block_size=max(1, n_steps ÷ sample_blocks),
         n_recorded=2 * n_steps, expectation_backend="pauli_mps_born_direct_sampling",
         pauli_trunc_L=high.trunc_L, pauli_trunc_H=high.trunc_H,
         pauli_chi_check=pauli_chi_check, pauli_chi_error=estimator_shift,
         pauli_chi_excess=compression_excess,
         pauli_chi_shift_noise=shift_noise,
         sampling_se=high.se, born_norm_full=high.born_norm_full,
         born_norm_half=high.born_norm_half,
         mean_abs2_full=high.mean_abs2_full, mean_abs2_half=high.mean_abs2_half,
         symmetry_evidence=symmetry_evidence)
    elseif estimator == :ratio && full_cache === nothing
        pauli_markov_cL_eq24(expect_L, expect_Lh, L;
                             n_steps=n_steps, n_warmup=n_warmup, seed=seed,
                             sample_filter=pauli_sector_filter,
                             factor_filter=pauli_sector_filter,
                             proposal=proposal)
    elseif estimator == :ratio
        pauli_markov_cL_eq24_cached(full_cache, expect_Lh, L;
                                    half_cache1=half_cache1, half_cache2=half_cache2,
                                    n_steps=n_steps, n_warmup=n_warmup, seed=seed,
                                    sample_filter=pauli_sector_filter,
                                    factor_filter=pauli_sector_filter,
                                    proposal=proposal)
    else
        error("Unknown Eq.24 estimator: $estimator")
    end
    return (cL=res.cL, se=res.se, accept=res.accept, mean_R=res.mean_R,
            E_L=E_L, E_Lh=E_Lh, proposal=res.proposal,
            block_size=res.block_size, n_recorded=res.n_recorded,
            expectation_backend=res.expectation_backend,
            pauli_trunc_L=get(res, :pauli_trunc_L, nothing),
            pauli_trunc_H=get(res, :pauli_trunc_H, nothing),
            pauli_chi_check=get(res, :pauli_chi_check, nothing),
            pauli_chi_error=get(res, :pauli_chi_error, nothing),
            pauli_chi_excess=get(res, :pauli_chi_excess, nothing),
            pauli_chi_shift_noise=get(res, :pauli_chi_shift_noise, nothing),
            sampling_se=get(res, :sampling_se, nothing),
            born_norm_full=get(res, :born_norm_full, nothing),
            born_norm_half=get(res, :born_norm_half, nothing),
            mean_abs2_full=get(res, :mean_abs2_full, nothing),
            mean_abs2_half=get(res, :mean_abs2_half, nothing),
            symmetry_evidence=get(res, :symmetry_evidence, Any[]),
            initial_state=initial_state)
end

# ---------------- Main: h-scan × L-scan ----------------

function main()
    Random.seed!(0xBADC0FFE)
    pbc   = true
    L_min = 8
    default_outdir = joinpath(@__DIR__, "..", "results", "tfim_fig4_paper_grade")
    cell_context = harness_cell_context(default_run_dir=default_outdir)
    cell_params = cell_context["params"]
    cell_settings = cell_context["settings"]
    provenance = reproduction_provenance(cell_context["provenance"])

    # Generic per-cell mode: a run spec supplies an opaque cell id and params.
    # This script is paper-specific, so it maps params["L"] / params["h"] to
    # its local computation, but the scheduler/orchestrator never needs to know
    # those axis names.
    cell_only = cell_context["spec_path"] !== nothing

    # FIG4_MODE remains only a local convenience path when no generic run spec is supplied.
    mode = get(ENV, "FIG4_MODE", cell_only ? "paper_grade" : "local")
    if cell_only
        Ls_chain = [harness_get_int(cell_params, "L", nothing)]
        h_grid   = [harness_get_float(cell_params, "h", nothing)]
        chi      = harness_get_int(cell_settings, "chi", parse(Int, get(ENV, "FIG4_CHI", "30")))
        n_steps  = harness_get_int(cell_settings, "n_steps", parse(Int, get(ENV, "FIG4_NSTEPS", "1000000")))
        pbc      = harness_get_bool(cell_settings, "pbc", pbc)
    elseif mode == "smoke"
        Ls_chain = [16]
        h_grid   = [1.00]
        chi      = 30
        n_steps  = parse(Int, get(ENV, "FIG4_NSTEPS", "20000"))
    elseif mode == "paper_grade"
        # Paper-grade. χ=30 matches paper Fig 4 caption; N_S=10⁶ matches paper.
        # FIG4_CHI / FIG4_NSTEPS env vars override (e.g., χ=60 if L=128 needs it).
        Ls_chain = [16, 32, 64, 128]
        h_grid   = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]
        chi      = parse(Int, get(ENV, "FIG4_CHI", "30"))
        n_steps  = parse(Int, get(ENV, "FIG4_NSTEPS", "1000000"))
    else  # local — L=16 only at N_S=5e4 gives a clean prototype in ~5 min
        Ls_chain = [16]
        h_grid   = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]
        chi      = 30
        n_steps  = parse(Int, get(ENV, "FIG4_NSTEPS", "50000"))
    end
    proposal = Symbol(harness_get_string(cell_settings, "proposal", get(ENV, "FIG4_PROPOSAL", "paper")))
    @assert proposal in (:paper, :group)
    estimator = Symbol(harness_get_string(cell_settings, "estimator", get(ENV, "FIG4_ESTIMATOR", "ratio")))
    @assert estimator in (:ratio, :bridge, :pauli_mps_norm, :pauli_mps_born_direct)
    pauli_chi = harness_get_int(cell_settings, "pauli_chi", parse(Int, get(ENV, "FIG4_PAULI_CHI", "16")))
    pauli_chi_check = harness_get_int(cell_settings, "pauli_chi_check",
                                      parse(Int, get(ENV, "FIG4_PAULI_CHI_CHECK", string(2 * pauli_chi))))
    pauli_chi_tol = harness_get_float(cell_settings, "pauli_chi_tol",
                                      parse(Float64, get(ENV, "FIG4_PAULI_CHI_TOL", "0.02")))
    symmetry_tol = harness_get_float(cell_settings, "symmetry_tol",
                                     parse(Float64, get(ENV, "FIG4_SYMMETRY_TOL", "1e-6")))
    sample_blocks = harness_get_int(cell_settings, "sample_blocks",
                                    parse(Int, get(ENV, "FIG4_SAMPLE_BLOCKS", "20")))
    initial_state = get(cell_settings, "initial_state", nothing)
    symmetry_checks = get(cell_settings, "symmetry_checks", Any[])
    if estimator in (:pauli_mps_norm, :pauli_mps_born_direct) && initial_state === nothing
        error("estimator=$estimator requires settings.initial_state to declare the target sector's MPS state preparation")
    end
    if estimator in (:pauli_mps_norm, :pauli_mps_born_direct) && isempty(symmetry_checks)
        error("estimator=$estimator requires settings.symmetry_checks to declare target-sector verification")
    end
    settings_deviations = get(cell_settings, "deviations", Any[])
    settings_deviations isa Vector || error("settings.deviations must be a list when present")
    run_deviations = unique([provenance["deviations"]...,
                             [string(x) for x in settings_deviations]...])
    if estimator == :bridge
        allow_bridge = harness_get_bool(cell_settings, "allow_experimental_bridge",
                                        get(ENV, "FIG4_ALLOW_EXPERIMENTAL_BRIDGE", "false") == "true")
        allow_bridge || error("The cached bridge estimator is experimental and failed the L=16,h=0.80 exact gate; set allow_experimental_bridge=true only for diagnostics.")
    end

    outdir = string(cell_context["run_dir"])
    isdir(outdir) || mkpath(outdir)
    cell_dir = cell_only ? joinpath(outdir, "cells", string(cell_context["cell_id"])) : outdir
    isdir(cell_dir) || mkpath(cell_dir)

    estimator_label = harness_get_string(cell_settings, "estimator_label",
                                         replace(string(estimator), "_" => " "))
    estimator_note = harness_get_string(cell_settings, "estimator_note",
                                        "Estimator: $estimator_label.")
    println("\n############ /verify-recommended Fig 4 reproduction ($estimator_label) ############")
    @printf("Hamiltonian : H = -Σ σ_i^x σ_j^x - h Σ σ_i^z   (PBC, translation invariant)\n")
    @printf("Anchor      : L_min = %d (exact-sum SRE on ED ground state)\n", L_min)
    @printf("Chain L's   : %s   (c_L = 2 M_2(L/2) − M_2(L), via %s)\n",
            string(Ls_chain), estimator_label)
    @printf("h grid      : %s\n", string(h_grid))
    @printf("Knobs       : χ=%d  N_S=%d  PBC=%s  proposal=%s  estimator=%s  χ_P=%d→%d  χ_P_tol=%.3g\n",
            chi, n_steps, string(pbc), string(proposal), string(estimator),
            pauli_chi, pauli_chi_check, pauli_chi_tol)
    flush(stdout)

    # Stage 1: M_2 anchor at L_min for every h.
    println("\n############ Stage 1: M_2(L_min=$L_min, h) anchors (exact-sum on ED) ############")
    flush(stdout)
    M2_anchor = Dict{Float64, Float64}()
    for h in h_grid
        E_anchor, psi_anchor = ed_groundstate(L_min, h; pbc=pbc)
        ed_expect_anchor = (q) -> ed_pauli_expectation(psi_anchor, q, L_min)
        M2 = exact_sre_M2_from_expect(ed_expect_anchor, L_min)
        M2_anchor[h] = M2
        @printf("  h=%.2f   M_2(L=%d) = %.6f   m_2 = %.6f\n", h, L_min, M2, M2/L_min)
        flush(stdout)
    end

    # Stage 2: c_L for each (L, h).
    println("\n############ Stage 2: c_L via $estimator_label ############")
    flush(stdout)
    cL_data = Dict{Tuple{Int,Float64}, Float64}()
    cL_err  = Dict{Tuple{Int,Float64}, Float64}()
    accept_all = Dict{Tuple{Int,Float64}, Float64}()
    cell_log = Dict[]

    t_start = time()
    cell_idx = 0
    for L in Ls_chain, h in h_grid
        cell_idx += 1
        @printf("\n--- cell %d/%d:  L=%d (L/2=%d)  h=%.2f ---\n",
                cell_idx, length(Ls_chain)*length(h_grid), L, L÷2, h)
        flush(stdout)
        t0 = time()
        res = compute_cL_cell(L, h; chi=chi, n_steps=n_steps, seed_offset=cell_idx,
                              pbc=pbc, proposal=proposal, estimator=estimator,
                              initial_state=initial_state,
                              symmetry_checks=symmetry_checks,
                              sample_blocks=sample_blocks,
                              pauli_chi=pauli_chi, pauli_chi_check=pauli_chi_check,
                              pauli_chi_tol=pauli_chi_tol, symmetry_tol=symmetry_tol)
        dt = time() - t0
        cL_data[(L, h)] = res.cL
        cL_err[(L, h)]  = res.se
        accept_all[(L, h)] = res.accept
        if res.mean_R === nothing
            @printf("    c_L = %+.5f ± %.5f   (accept=%.2f, %.1f s)\n",
                    res.cL, res.se, res.accept, dt)
        else
            @printf("    c_L = %+.5f ± %.5f   (mean_R=%.4e, accept=%.2f, %.1f s)\n",
                    res.cL, res.se, res.mean_R, res.accept, dt)
        end
        manifest_path = cell_only ? joinpath(cell_dir, "manifest.json") :
                        joinpath(cell_dir, @sprintf("manifest_L%d_h%.2f.json", L, h))
        cell_record = Dict(
            "cell_id"=>string(cell_context["cell_id"]),
            "params"=>Dict("L"=>L, "h"=>h),
            "settings"=>Dict("chi"=>chi, "n_steps"=>n_steps, "pbc"=>pbc,
                              "pauli_chi"=>pauli_chi,
                              "pauli_chi_check"=>pauli_chi_check,
                              "pauli_chi_tol"=>pauli_chi_tol,
                              "symmetry_tol"=>symmetry_tol,
                              "sample_blocks"=>sample_blocks,
                              "initial_state"=>initial_state,
                              "symmetry_checks"=>symmetry_checks,
                              "deviations"=>run_deviations,
                              "estimator_label"=>estimator_label,
                              "estimator_note"=>estimator_note,
                              "proposal_kernel"=>string(proposal),
                              "estimator"=>string(estimator)),
            "status"=>"success",
            "L"=>L, "h"=>h, "cL"=>res.cL, "se"=>res.se,
            "ci95"=>1.96 * res.se,
            "mean_R"=>res.mean_R, "accept"=>res.accept,
            "E_L"=>res.E_L, "E_Lh"=>res.E_Lh, "wall_seconds"=>dt,
            "n_steps"=>n_steps, "chi"=>chi, "pauli_chi"=>pauli_chi,
            "pauli_chi_check"=>pauli_chi_check, "pauli_chi_tol"=>pauli_chi_tol,
            "symmetry_tol"=>symmetry_tol, "sample_blocks"=>sample_blocks,
            "pbc"=>pbc, "L_min"=>L_min,
            "initial_state"=>initial_state,
            "symmetry_checks"=>symmetry_checks,
            "proposal"=>res.proposal, "proposal_kernel"=>string(proposal),
            "estimator"=>string(estimator),
            "estimator_label"=>estimator_label,
            "estimator_note"=>estimator_note,
            "block_size"=>res.block_size,
            "n_recorded"=>res.n_recorded,
            "pauli_trunc_L"=>res.pauli_trunc_L,
            "pauli_trunc_H"=>res.pauli_trunc_H,
            "pauli_chi_error"=>res.pauli_chi_error,
            "pauli_chi_excess"=>res.pauli_chi_excess,
            "pauli_chi_shift_noise"=>res.pauli_chi_shift_noise,
            "sampling_se"=>res.sampling_se,
            "born_norm_full"=>res.born_norm_full,
            "born_norm_half"=>res.born_norm_half,
            "mean_abs2_full"=>res.mean_abs2_full,
            "mean_abs2_half"=>res.mean_abs2_half,
            "symmetry_evidence"=>res.symmetry_evidence,
            "expectation_backend"=>res.expectation_backend,
            "protocol_hash"=>provenance["protocol_hash"],
            "script_hash"=>provenance["script_hash"],
            "script_path"=>provenance["script_path"],
            "sources"=>provenance["sources"],
            "claims"=>provenance["claims"],
            "deviations"=>run_deviations,
            "artifacts"=>Dict("manifest"=>manifest_path, "script"=>SCRIPT_PATH),
            "M2_anchor_at_L_min"=>M2_anchor[h])
        validate_compute_manifest!(cell_record, manifest_path)
        push!(cell_log, cell_record)
        harness_write_json(manifest_path, cell_record)
        flush(stdout)
    end
    println(@sprintf("\nGrid computed in %.1f s.", time() - t_start))
    flush(stdout)

    # Per-cell SLURM mode exits here — Stage 3 / plots / summary belong to the aggregator.
    if cell_only
        @printf("Per-cell mode: manifest written to %s. Aggregator will assemble Stage 3.\n", cell_dir)
        flush(stdout)
        return
    end

    # Stage 3: increment recursion → M_2(L), m_2(L) for each h.
    println("\n############ Stage 3: increment recursion → M_2(L), m_2(L) ############")
    flush(stdout)
    M2_grid = Dict{Tuple{Int,Float64}, Float64}()
    M2_err  = Dict{Tuple{Int,Float64}, Float64}()

    for h in h_grid
        cs   = [cL_data[(L, h)]  for L in Ls_chain]
        cerr = [cL_err[(L, h)]   for L in Ls_chain]
        rec  = increment_recursion(M2_anchor[h], L_min, cs)
        M2_grid[(L_min, h)] = rec[L_min]
        M2_err[(L_min, h)]  = 0.0
        # Error propagation: M_2(L_k) = 2 M_2(L_{k-1}) − c_{L_k}, errors add in quadrature.
        prev_err = 0.0
        for (k, L) in enumerate(Ls_chain)
            M2_grid[(L, h)] = rec[L]
            err_k = sqrt((2*prev_err)^2 + cerr[k]^2)
            M2_err[(L, h)] = err_k
            prev_err = err_k
            @printf("  h=%.2f  L=%2d  M_2 = %.5f ± %.5f   m_2 = %.5f ± %.5f\n",
                    h, L, rec[L], err_k, rec[L]/L, err_k/L)
        end
        flush(stdout)
    end

    # ---------------- /run-report:  data.json ----------------
    Ls_full = [L_min; Ls_chain...]
    combined = Dict(
        "model"   => "1D TFIM",
        "estimator_description" => estimator_label,
        "L_min"   => L_min,
        "Ls_chain" => Ls_chain,
        "Ls_full" => Ls_full,
        "h_grid"  => h_grid,
        "chi"     => chi,
        "pauli_chi" => pauli_chi,
        "pauli_chi_check" => pauli_chi_check,
        "pauli_chi_tol" => pauli_chi_tol,
        "symmetry_tol" => symmetry_tol,
        "sample_blocks" => sample_blocks,
        "n_steps" => n_steps,
        "pbc"     => pbc,
        "initial_state" => initial_state,
        "symmetry_checks" => symmetry_checks,
        "proposal_kernel" => string(proposal),
        "expectation_backends" => sort(unique([string(c["expectation_backend"]) for c in cell_log])),
        "protocol_hash" => provenance["protocol_hash"],
        "script_hash" => provenance["script_hash"],
        "script_path" => provenance["script_path"],
        "sources" => provenance["sources"],
        "claims" => provenance["claims"],
        "deviations" => run_deviations,
        "M2_anchor" => Dict(string(h) => M2_anchor[h] for h in h_grid),
        "cells"   => cell_log,
        "c_L"     => Dict(string(L) => [cL_data[(L, h)]  for h in h_grid] for L in Ls_chain),
        "c_L_err" => Dict(string(L) => [cL_err[(L, h)]   for h in h_grid] for L in Ls_chain),
        "c_L_ci95" => Dict(string(L) => [1.96 * cL_err[(L, h)] for h in h_grid] for L in Ls_chain),
        "M_2"     => Dict(string(L) => [M2_grid[(L, h)]  for h in h_grid] for L in Ls_full),
        "M_2_err" => Dict(string(L) => [M2_err[(L, h)]   for h in h_grid] for L in Ls_full),
        "M_2_ci95" => Dict(string(L) => [1.96 * M2_err[(L, h)] for h in h_grid] for L in Ls_full),
        "wall_seconds_total" => time() - t_start,
    )
    harness_write_json(joinpath(outdir, "data.json"), combined)
    println("\nSaved → $(joinpath(outdir, "data.json"))")
    flush(stdout)

    # ---------------- Plots: 2-panel Fig 4 diagnostic ----------------
    palette = [:steelblue, :firebrick, :seagreen, :darkorange]

    # Panel (a): c_L vs h
    pa = plot(xlabel="h", ylabel="c_L = 2 M_2(L/2) − M_2(L)",
              title="Fig 4(a) — $estimator_label",
              xticks=h_grid, legend=:topright)
    for (k, L) in enumerate(Ls_chain)
        cs   = [cL_data[(L, h)]  for h in h_grid]
        errs = [1.96 * cL_err[(L, h)] for h in h_grid]
        plot!(pa, h_grid, cs; yerror=errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L")
        plot!(pa, h_grid, cs; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pa, joinpath(outdir, "panel_a_cL_vs_h.png"))

    # Panel (b): m_2 vs h
    pb = plot(xlabel="h", ylabel="m_2 = M_2 / L",
              title="Fig 4(b) — m_2 via increment recursion (diagnostic)",
              xticks=h_grid, legend=:topright)
    for (k, L) in enumerate(Ls_full)
        m2s    = [M2_grid[(L, h)] / L for h in h_grid]
        m2errs = [1.96 * M2_err[(L, h)] / L for h in h_grid]
        plot!(pb, h_grid, m2s; yerror=m2errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L")
        plot!(pb, h_grid, m2s; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pb, joinpath(outdir, "panel_b_m2_vs_h.png"))

    pc = plot(pa, pb; layout=(1,2), size=(1100, 450))
    savefig(pc, joinpath(outdir, "fig4_combined.png"))

    # Fig 4(b) inset — σ_{m_2}(L) at h_c=1 on log-log scale.
    # Paper's central methodological claim: errors grow *slower than log L* with this estimator.
    # Reference plotted: 0.05 / sqrt(L), the naive 1/√L (already faster than log L).
    h_at_critical = h_grid[argmin(abs.(h_grid .- 1.0))]
    sigmas = Float64[1.96 * M2_err[(L, h_at_critical)] / L  for L in Ls_full]
    Ls_arr = Float64.(Ls_full)
    pc2 = plot(xlabel="L", ylabel="σ(m_2) at h_c = 1",
               title="Fig 4(b) inset — reported error vs L (log-log)",
               xscale=:log10, yscale=:log10, legend=:topright)
    plot!(pc2, Ls_arr, sigmas; seriestype=:scatter, marker=:circle, ms=8, c=:firebrick,
          label=estimator_label)
    plot!(pc2, Ls_arr, sigmas; ls=:solid, c=:firebrick, lw=1, label="")
    # Reference: naive 1/√L scaling, normalized to the L_min point.
    if !isempty(sigmas) && sigmas[1] > 0
        ref = sigmas[1] .* sqrt(Ls_arr[1] ./ Ls_arr)
        plot!(pc2, Ls_arr, ref; ls=:dash, c=:gray, lw=1, label="∝ 1/√L (ref)")
    end
    savefig(pc2, joinpath(outdir, "panel_b_inset_sigma_vs_L.png"))

    println("Saved plots → panel_a_cL_vs_h.png, panel_b_m2_vs_h.png, panel_b_inset_sigma_vs_L.png, fig4_combined.png")
    flush(stdout)

    # ---------------- Summary ----------------
    println("\n=========================================================")
    println("SUMMARY  Paper-grade Fig 4 reproduction ($estimator_label)")
    println("=========================================================")
    println("  $estimator_note")
    println("  Anchor:    L_min=$L_min via exact-sum SRE on ED ground state.")
    @printf("  Grid:      L_chain = %s × h = %s  (%d cells).\n",
            string(Ls_chain), string(h_grid), length(Ls_chain)*length(h_grid))
    println("  c_L dips negative near h_c=1 (Fig 4(a) verification — minimum, not max):")
    for L in Ls_chain
        cs   = [cL_data[(L, h)] for h in h_grid]
        errs = [cL_err[(L, h)]  for h in h_grid]
        idx_min = argmin(cs)
        @printf("    L=%2d  argmin(c_L) at h=%.2f, c_L = %+.5f ± %.5f\n",
                L, h_grid[idx_min], cs[idx_min], errs[idx_min])
    end
    @printf("\nTotal wall = %.1f s.\n", time() - t_start)
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
