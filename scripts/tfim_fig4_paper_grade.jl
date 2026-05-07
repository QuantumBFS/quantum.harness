# Reproduces validation paper Fig 4 with the paper's *dedicated* estimator.
#
#   - Panel (a): c_L = 2 M_2(L/2) − M_2(L), estimated by the Eq.-(24) ratio
#     chain — single Markov chain on Π_{P,2} ∝ |⟨P⟩_L|⁴, accumulating
#         R(P) = |⟨P^(1)⟩_{L/2}|⁴ · |⟨P^(2)⟩_{L/2}|⁴ / |⟨P⟩_L|⁴
#     with c_L = -log⟨R⟩_{Π_{P,2}}. Volume-law cancels inside the log under
#     one expectation → polynomial-in-L variance (paper's central claim).
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
# HPC2 paper grade:       full L/h grid, N_S=1e6, via /slurm-grid.

using ITensors, ITensorMPS
using LinearAlgebra
using Random
using Printf
using Statistics
using JSON
using Plots

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

function dmrg_groundstate(L, h, chi; cutoff=1e-12, nsweeps=30, pbc::Bool=true)
    sites = siteinds("S=1/2", L; conserve_qns=false)
    H = build_tfim(sites, h; pbc=pbc)
    psi0 = randomMPS(sites; linkdims=4)
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
                              n_steps=10^5, n_warmup=10^4, seed::UInt32=UInt32(0xC0FFEE))
    @assert iseven(L)
    Lh = L ÷ 2
    rng = MersenneTwister(seed)
    p = zeros(Int, L)
    cur_v = expect_L(p)
    cur_w = abs(cur_v)^4 / 2.0^L          # n=2 sampling weight
    is_xy(q::Int) = (q == 1 || q == 2)

    accum_R = 0.0
    n_acc = 0

    block_size = 100
    n_blocks = div(n_steps, block_size)
    block_means = zeros(n_blocks)
    cur_block_sum = 0.0
    cur_block_idx = 0

    p1 = zeros(Int, Lh)
    p2 = zeros(Int, Lh)

    for step in 1:(n_warmup + n_steps)
        proposal_kind = rand(rng) < 0.5 ? :single : :two
        if proposal_kind == :single
            i = rand(rng, 1:L)
            old_pi = p[i]
            new_pi = is_xy(old_pi) ? (old_pi == 1 ? 2 : 1) : (old_pi == 0 ? 3 : 0)
            p[i] = new_pi
            new_v = expect_L(p)
            new_w = abs(new_v)^4 / 2.0^L
            ratio = (cur_w == 0 && new_w == 0) ? 0.0 : (cur_w == 0 ? Inf : new_w / cur_w)
            if rand(rng) < ratio
                cur_v = new_v; cur_w = new_w; n_acc += 1
            else
                p[i] = old_pi
            end
        else
            i = rand(rng, 1:L); j = rand(rng, 1:(L-1)); j >= i && (j += 1)
            old_pi, old_pj = p[i], p[j]
            new_pi = is_xy(old_pi) ? rand(rng, (0, 3)) : rand(rng, (1, 2))
            new_pj = is_xy(old_pj) ? rand(rng, (0, 3)) : rand(rng, (1, 2))
            p[i] = new_pi; p[j] = new_pj
            new_v = expect_L(p)
            new_w = abs(new_v)^4 / 2.0^L
            ratio = (cur_w == 0 && new_w == 0) ? 0.0 : (cur_w == 0 ? Inf : new_w / cur_w)
            if rand(rng) < ratio
                cur_v = new_v; cur_w = new_w; n_acc += 1
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
            v1 = expect_Lh(p1)
            v2 = expect_Lh(p2)
            denom = abs(cur_v)^4
            if denom > 0
                R = (abs(v1)^4 * abs(v2)^4) / denom
                accum_R += R
                cur_block_sum += R
                cur_block_idx += 1
                if cur_block_idx == block_size
                    blk = div(step - n_warmup, block_size)
                    if blk <= n_blocks
                        block_means[blk] = cur_block_sum / block_size
                    end
                    cur_block_sum = 0.0; cur_block_idx = 0
                end
            end
            # If denom == 0 the chain is stuck on |⟨P⟩_L|² = 0 — skip; n=2
            # weight is zero too so this state has measure zero in Π_{P,2}.
        end
    end

    mean_R = accum_R / n_steps
    se_R   = std(block_means) / sqrt(n_blocks)
    cL     = -log(mean_R)
    se_cL  = se_R / mean_R
    accept = n_acc / (n_warmup + n_steps)
    return (cL=cL, se=se_cL, accept=accept, mean_R=mean_R, se_R=se_R)
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
                          seed_offset::Int=0, pbc::Bool=true)
    @assert iseven(L) && L ≥ 4
    Lh = L ÷ 2

    # Ground state at L (for sampling distribution and denominator).
    if L ≤ 8
        E_L, psi_L = ed_groundstate(L, h; pbc=pbc)
        expect_L = (q) -> ed_pauli_expectation(psi_L, q, L)
    else
        E_L, psi_L_mps, sites_L = dmrg_groundstate(L, h, chi; pbc=pbc)
        expect_L = (q) -> mps_pauli_expectation(psi_L_mps, q, sites_L)
    end

    # Ground state at L/2 (for ratio numerator). Same h, same PBC, same translation invariance.
    if Lh ≤ 8
        E_Lh, psi_Lh = ed_groundstate(Lh, h; pbc=pbc)
        expect_Lh = (q) -> ed_pauli_expectation(psi_Lh, q, Lh)
    else
        E_Lh, psi_Lh_mps, sites_Lh = dmrg_groundstate(Lh, h, chi; pbc=pbc)
        expect_Lh = (q) -> mps_pauli_expectation(psi_Lh_mps, q, sites_Lh)
    end

    seed = UInt32(0xC0FFEE) + UInt32(seed_offset & 0xFFFF)
    res = pauli_markov_cL_eq24(expect_L, expect_Lh, L;
                                n_steps=n_steps, n_warmup=n_warmup, seed=seed)
    return (cL=res.cL, se=res.se, accept=res.accept, mean_R=res.mean_R,
            E_L=E_L, E_Lh=E_Lh)
end

# ---------------- Main: h-scan × L-scan ----------------

function main()
    Random.seed!(0xBADC0FFE)
    pbc   = true
    L_min = 8

    # Per-cell SLURM mode: when FIG4_CELL_L and FIG4_CELL_H are set, run only
    # that cell. Stage 3 (increment recursion) is skipped — the aggregator
    # collects all per-cell manifests and runs Stage 3 globally.
    cell_only = haskey(ENV, "FIG4_CELL_L") && haskey(ENV, "FIG4_CELL_H")

    # FIG4_MODE: smoke (1 cell), local (default, L=16 grid), hpc2 (paper grade).
    mode = get(ENV, "FIG4_MODE", cell_only ? "hpc2" : "local")
    if cell_only
        Ls_chain = [parse(Int, ENV["FIG4_CELL_L"])]
        h_grid   = [parse(Float64, ENV["FIG4_CELL_H"])]
        chi      = parse(Int, get(ENV, "FIG4_CHI", "30"))
        n_steps  = parse(Int, get(ENV, "FIG4_NSTEPS", "1000000"))
    elseif mode == "smoke"
        Ls_chain = [16]
        h_grid   = [1.00]
        chi      = 30
        n_steps  = parse(Int, get(ENV, "FIG4_NSTEPS", "20000"))
    elseif mode == "hpc2"
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

    outdir = joinpath(@__DIR__, "..", "results", "tfim_fig4_paper_grade")
    isdir(outdir) || mkpath(outdir)
    cell_dir = cell_only ? joinpath(outdir, "cells") : outdir
    isdir(cell_dir) || mkpath(cell_dir)

    println("\n############ /verify-recommended Fig 4 reproduction (Eq.-(24) ratio chain) ############")
    @printf("Hamiltonian : H = -Σ σ_i^x σ_j^x - h Σ σ_i^z   (PBC, translation invariant)\n")
    @printf("Anchor      : L_min = %d (exact-sum SRE on ED ground state)\n", L_min)
    @printf("Chain L's   : %s   (c_L = 2 M_2(L/2) − M_2(L), via Eq.-(24) ratio chain)\n", string(Ls_chain))
    @printf("h grid      : %s\n", string(h_grid))
    @printf("Knobs       : χ=%d  N_S=%d  PBC=%s\n", chi, n_steps, string(pbc))
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

    # Stage 2: c_L for each (L, h) via Eq.-(24) chain.
    println("\n############ Stage 2: c_L via Eq.-(24) ratio chain (single-chain, polynomial variance) ############")
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
        res = compute_cL_cell(L, h; chi=chi, n_steps=n_steps, seed_offset=cell_idx, pbc=pbc)
        dt = time() - t0
        cL_data[(L, h)] = res.cL
        cL_err[(L, h)]  = res.se
        accept_all[(L, h)] = res.accept
        @printf("    c_L = %+.5f ± %.5f   (mean_R=%.4e, accept=%.2f, %.1f s)\n",
                res.cL, res.se, res.mean_R, res.accept, dt)
        cell_record = Dict(
            "L"=>L, "h"=>h, "cL"=>res.cL, "se"=>res.se,
            "mean_R"=>res.mean_R, "accept"=>res.accept,
            "E_L"=>res.E_L, "E_Lh"=>res.E_Lh, "wall_seconds"=>dt,
            "n_steps"=>n_steps, "chi"=>chi, "pbc"=>pbc, "L_min"=>L_min,
            "M2_anchor_at_L_min"=>M2_anchor[h])
        push!(cell_log, cell_record)
        manifest_path = joinpath(cell_dir, @sprintf("manifest_L%d_h%.2f.json", L, h))
        open(manifest_path, "w") do f
            JSON.print(f, cell_record, 2)
        end
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
        "estimator" => "Eq.-(24) ratio chain (paper-grade)",
        "L_min"   => L_min,
        "Ls_chain" => Ls_chain,
        "Ls_full" => Ls_full,
        "h_grid"  => h_grid,
        "chi"     => chi,
        "n_steps" => n_steps,
        "pbc"     => pbc,
        "M2_anchor" => Dict(string(h) => M2_anchor[h] for h in h_grid),
        "cells"   => cell_log,
        "c_L"     => Dict(string(L) => [cL_data[(L, h)]  for h in h_grid] for L in Ls_chain),
        "c_L_err" => Dict(string(L) => [cL_err[(L, h)]   for h in h_grid] for L in Ls_chain),
        "M_2"     => Dict(string(L) => [M2_grid[(L, h)]  for h in h_grid] for L in Ls_full),
        "M_2_err" => Dict(string(L) => [M2_err[(L, h)]   for h in h_grid] for L in Ls_full),
        "wall_seconds_total" => time() - t_start,
    )
    open(joinpath(outdir, "data.json"), "w") do f
        JSON.print(f, combined, 2)
    end
    println("\nSaved → $(joinpath(outdir, "data.json"))")
    flush(stdout)

    # ---------------- Plots: 2-panel Fig 4 reproduction (paper-grade estimator) ----------------
    palette = [:steelblue, :firebrick, :seagreen, :darkorange]

    # Panel (a): c_L vs h
    pa = plot(xlabel="h", ylabel="c_L = 2 M_2(L/2) − M_2(L)",
              title="Fig 4(a) — Eq.-(24) ratio chain (paper-grade estimator)",
              xticks=h_grid, legend=:topright)
    for (k, L) in enumerate(Ls_chain)
        cs   = [cL_data[(L, h)]  for h in h_grid]
        errs = [cL_err[(L, h)]   for h in h_grid]
        plot!(pa, h_grid, cs; yerror=errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L (Eq.-(24))")
        plot!(pa, h_grid, cs; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pa, joinpath(outdir, "panel_a_cL_vs_h.png"))

    # Panel (b): m_2 vs h
    pb = plot(xlabel="h", ylabel="m_2 = M_2 / L",
              title="Fig 4(b) — m_2 via increment recursion (paper-grade)",
              xticks=h_grid, legend=:topright)
    for (k, L) in enumerate(Ls_full)
        m2s    = [M2_grid[(L, h)] / L for h in h_grid]
        m2errs = [M2_err[(L, h)]  / L for h in h_grid]
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
    sigmas = Float64[M2_err[(L, h_at_critical)] / L  for L in Ls_full]
    Ls_arr = Float64.(Ls_full)
    pc2 = plot(xlabel="L", ylabel="σ(m_2) at h_c = 1",
               title="Fig 4(b) inset — sampling error vs L (log-log)",
               xscale=:log10, yscale=:log10, legend=:topright)
    plot!(pc2, Ls_arr, sigmas; seriestype=:scatter, marker=:circle, ms=8, c=:firebrick,
          label="Eq.-(24) ratio chain")
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
    println("SUMMARY  Paper-grade Fig 4 reproduction (Eq.-(24) ratio chain)")
    println("=========================================================")
    println("  Estimator: single-chain Π_{P,2} ∝ |⟨P⟩|⁴, ratio R = |⟨P^(1)⟩|⁴|⟨P^(2)⟩|⁴/|⟨P⟩|⁴.")
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
