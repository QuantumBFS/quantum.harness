# Exact small-L diagnostics for the Fig. 4 Eq. (24) estimator.
#
# This script is intentionally independent of the production Fig. 4 driver: it
# enumerates Pauli strings, separates the Z2/time-reversal sector used by the
# paper proposal, and compares the exact ratio expectation against the Markov
# chain on that same sector.

using LinearAlgebra
using Printf
using Random
using Statistics

function ed_groundstate(L, h; pbc::Bool=true)
    dim = 2^L
    H = zeros(Float64, dim, dim)
    for s in 0:(dim - 1)
        d = 0.0
        for i in 0:(L - 1)
            d -= h * (1 - 2 * ((s >> i) & 1))
        end
        H[s + 1, s + 1] = d
    end
    bond_stop = pbc ? L - 1 : L - 2
    for i in 0:bond_stop
        j = (i + 1) % L
        mask = (1 << i) | (1 << j)
        for s in 0:(dim - 1)
            H[(s ⊻ mask) + 1, s + 1] -= 1.0
        end
    end
    F = eigen(Symmetric(H))
    return F.values[1], F.vectors[:, 1]
end

function wht!(x::AbstractVector{Float64})
    n = length(x)
    h = 1
    while h < n
        for i in 1:(2h):n
            @inbounds for j in i:(i + h - 1)
                a = x[j]
                b = x[j + h]
                x[j] = a + b
                x[j + h] = a - b
            end
        end
        h *= 2
    end
    return x
end

@inline function pauli_code(xmask::Int, zmask::Int, i::Int)
    xb = (xmask >> i) & 1
    zb = (zmask >> i) & 1
    return xb == 1 ? (zb == 1 ? 2 : 1) : (zb == 1 ? 3 : 0)
end

@inline function pauli_index_from_masks(xmask::Int, zmask::Int, L::Int)
    idx = 0
    place = 1
    for i in 0:(L - 1)
        idx += pauli_code(xmask, zmask, i) * place
        place *= 4
    end
    return idx
end

@inline pauli_index_unrestricted(::Int, ::Int) = true

@inline function tfim_fig4_index_sector(idx0::Int, L::Int)
    xparity = 0
    yparity = 0
    x = idx0
    for _ in 1:L
        code = x & 3
        x >>= 2
        xparity ⊻= (code == 1 || code == 2)
        yparity ⊻= (code == 2)
    end
    return xparity == 0 && yparity == 0
end

function pauli_abs4_table(psi::Vector{Float64}, L::Int; value_filter=pauli_index_unrestricted)
    dim = 2^L
    table = zeros(Float64, 4^L)
    g = Vector{Float64}(undef, dim)
    for xmask in 0:(dim - 1)
        @inbounds for s in 0:(dim - 1)
            g[s + 1] = psi[(s ⊻ xmask) + 1] * psi[s + 1]
        end
        wht!(g)
        @inbounds for zmask in 0:(dim - 1)
            idx0 = pauli_index_from_masks(xmask, zmask, L)
            table[idx0 + 1] = value_filter(idx0, L) ? g[zmask + 1]^4 : 0.0
        end
    end
    return table
end

function split_indices(idx0::Int, L::Int, split_mode::Symbol)
    Lh = L ÷ 2
    left = 0
    right = 0
    lplace = 1
    rplace = 1
    if split_mode == :contiguous
        split = 4^Lh
        return idx0 % split, idx0 ÷ split
    elseif split_mode == :interleaved
        for site in 0:(L - 1)
            code = (idx0 >> (2site)) & 3
            if iseven(site)
                left += code * lplace
                lplace *= 4
            else
                right += code * rplace
                rplace *= 4
            end
        end
        return left, right
    else
        error("unknown split mode: $split_mode")
    end
end

function exact_sector_stats(abs4_L::Vector{Float64}, abs4_H::Vector{Float64}, L::Int;
                            split_mode::Symbol=:contiguous,
                            sector_filter=tfim_fig4_index_sector)
    Lh = L ÷ 2
    rows = []
    for sector in (:all, :filtered)
        Z = 0.0
        mean_num = 0.0
        second_num = 0.0
        log_num = 0.0
        log_second_num = 0.0
        max_R = 0.0
        n = 0
        for idx0 in 0:(length(abs4_L) - 1)
            sector == :filtered && !sector_filter(idx0, L) && continue
            denom = abs4_L[idx0 + 1]
            denom == 0.0 && continue
            i1, i2 = split_indices(idx0, L, split_mode)
            num = abs4_H[i1 + 1] * abs4_H[i2 + 1]
            R = num / denom
            logR = log(R)
            Z += denom
            mean_num += num
            second_num += num * R
            log_num += denom * logR
            log_second_num += denom * logR^2
            max_R = max(max_R, R)
            n += 1
        end
        mean_R = mean_num / Z
        var_R = second_num / Z - mean_R^2
        mean_logR = log_num / Z
        var_logR = log_second_num / Z - mean_logR^2
        push!(rows, (sector=sector, support=n, Z=Z, mean_R=mean_R,
                    cL=-log(mean_R), sd_R=sqrt(max(var_R, 0.0)),
                    iid_se_cL_1e6=sqrt(max(var_R, 0.0) / 1e6) / mean_R,
                    max_R=max_R, neg_mean_logR=-mean_logR,
                    iid_se_neg_mean_logR_1e6=sqrt(max(var_logR, 0.0) / 1e6)))
    end
    return rows
end

function exact_dual_stats(abs4_L::Vector{Float64}, abs4_H::Vector{Float64}, L::Int;
                          split_mode::Symbol=:contiguous,
                          sector_filter=tfim_fig4_index_sector)
    Lh = L ÷ 2
    Zq = 0.0
    mean_num = 0.0
    second_num = 0.0
    max_R = 0.0
    support = 0
    for idx0 in 0:(length(abs4_L) - 1)
        !sector_filter(idx0, L) && continue
        i1, i2 = split_indices(idx0, L, split_mode)
        num = abs4_H[i1 + 1] * abs4_H[i2 + 1]
        num == 0.0 && continue
        denom = abs4_L[idx0 + 1]
        R = denom / num
        Zq += num
        mean_num += denom
        second_num += denom * R
        max_R = max(max_R, R)
        support += 1
    end
    mean_R = mean_num / Zq
    var_R = second_num / Zq - mean_R^2
    return (support=support, Z=Zq, mean_R=mean_R, cL=log(mean_R),
            sd_R=sqrt(max(var_R, 0.0)),
            iid_se_cL_1e6=sqrt(max(var_R, 0.0) / 1e6) / mean_R,
            max_R=max_R)
end

function tolerance_sweep(abs4_L::Vector{Float64}, abs4_H::Vector{Float64}, L::Int;
                         sector_filter=tfim_fig4_index_sector)
    maxw = maximum(abs4_L)
    rows = []
    for exponent in (-28, -24, -20, -16, -12)
        tol = maxw * 10.0^exponent
        Z = 0.0
        mean_num = 0.0
        second_num = 0.0
        dropped_weight = 0.0
        dropped_num = 0.0
        support = 0
        for idx0 in 0:(length(abs4_L) - 1)
            !sector_filter(idx0, L) && continue
            denom = abs4_L[idx0 + 1]
            i1, i2 = split_indices(idx0, L, :contiguous)
            num = abs4_H[i1 + 1] * abs4_H[i2 + 1]
            if denom <= tol
                dropped_weight += denom
                dropped_num += num
                continue
            end
            R = num / denom
            Z += denom
            mean_num += num
            second_num += num * R
            support += 1
        end
        mean_R = mean_num / Z
        var_R = second_num / Z - mean_R^2
        push!(rows, (tol=tol, exponent=exponent, support=support,
                    cL=-log(mean_R), mean_R=mean_R,
                    iid_se_cL_1e6=sqrt(max(var_R, 0.0) / 1e6) / mean_R,
                    dropped_weight=dropped_weight, dropped_num=dropped_num))
    end
    return rows
end

function chain_sector(abs4_L::Vector{Float64}, abs4_H::Vector{Float64}, L::Int;
                      n_steps=200_000, n_warmup=10_000, seed=0xBEEF,
                      apply_sector_filter=true, split_mode::Symbol=:contiguous,
                      proposal::Symbol=:paper,
                      sector_filter=tfim_fig4_index_sector)
    @assert proposal in (:paper, :paper_generators, :group)
    Lh = L ÷ 2
    place = [4^i for i in 0:(L - 1)]
    rng = MersenneTwister(UInt32(seed))
    p = zeros(Int, L)
    idx0 = 0
    cur_w = abs4_L[1]
    accum_R = 0.0
    n_R = 0
    n_acc = 0
    for step in 1:(n_warmup + n_steps)
        single_move = if proposal == :paper_generators
            rand(rng) <= 2 / (L + 1)
        else
            rand(rng) < 0.5
        end
        if single_move
            i = rand(rng, 1:L)
            old = p[i]
            new = old ⊻ 3
            new_idx0 = idx0 + (new - old) * place[i]
            if !apply_sector_filter || sector_filter(new_idx0, L)
                new_w = abs4_L[new_idx0 + 1]
                ratio = cur_w == 0 ? (new_w == 0 ? 0.0 : Inf) : new_w / cur_w
                if rand(rng) < ratio
                    p[i] = new
                    idx0 = new_idx0
                    cur_w = new_w
                    n_acc += 1
                end
            end
        else
            i = rand(rng, 1:L)
            j = rand(rng, 1:(L - 1))
            j >= i && (j += 1)
            oi, oj = p[i], p[j]
            if proposal == :paper || proposal == :paper_generators
                ni, nj = oi ⊻ 1, oj ⊻ 1
            else
                ni = (oi == 1 || oi == 2) ? rand(rng, (0, 3)) : rand(rng, (1, 2))
                nj = (oj == 1 || oj == 2) ? rand(rng, (0, 3)) : rand(rng, (1, 2))
            end
            new_idx0 = idx0 + (ni - oi) * place[i] + (nj - oj) * place[j]
            if !apply_sector_filter || sector_filter(new_idx0, L)
                new_w = abs4_L[new_idx0 + 1]
                ratio = cur_w == 0 ? (new_w == 0 ? 0.0 : Inf) : new_w / cur_w
                if rand(rng) < ratio
                    p[i] = ni
                    p[j] = nj
                    idx0 = new_idx0
                    cur_w = new_w
                    n_acc += 1
                end
            end
        end
        if step > n_warmup && cur_w > 0
            i1, i2 = split_indices(idx0, L, split_mode)
            R = abs4_H[i1 + 1] * abs4_H[i2 + 1] / cur_w
            accum_R += R
            n_R += 1
        end
    end
    mean_R = accum_R / n_R
    return (mean_R=mean_R, cL=-log(mean_R), accept=n_acc / (n_steps + n_warmup),
            n_recorded=n_R, apply_sector_filter=apply_sector_filter)
end

function exact_bridge_samples(abs4_L::Vector{Float64}, abs4_H::Vector{Float64}, L::Int;
                              n_samples::Int=20_000, seed=0xA11CE,
                              split_mode::Symbol=:contiguous)
    q = similar(abs4_L)
    @inbounds for idx0 in 0:(length(abs4_L) - 1)
        i1, i2 = split_indices(idx0, L, split_mode)
        q[idx0 + 1] = abs4_H[i1 + 1] * abs4_H[i2 + 1]
    end
    Zf = sum(abs4_L)
    Zg = sum(q)
    Zf > 0 && Zg > 0 || error("Bridge estimator needs nonzero normalizers")

    rng = MersenneTwister(UInt32(seed))
    cdf_f = cumsum(abs4_L ./ Zf)
    cdf_g = cumsum(q ./ Zg)
    cdf_f[end] = 1.0
    cdf_g[end] = 1.0

    f_on_f = Vector{Float64}(undef, n_samples)
    g_on_f = Vector{Float64}(undef, n_samples)
    f_on_g = Vector{Float64}(undef, n_samples)
    g_on_g = Vector{Float64}(undef, n_samples)
    for k in 1:n_samples
        i = searchsortedfirst(cdf_f, rand(rng))
        j = searchsortedfirst(cdf_g, rand(rng))
        f_on_f[k] = abs4_L[i]
        g_on_f[k] = q[i]
        f_on_g[k] = abs4_L[j]
        g_on_g[k] = q[j]
    end

    # Meng-Wong bridge update. This fixed-point form returns r = Z_f / Z_g,
    # so c_L = log(r).
    sp = 0.5
    sg = 0.5
    r = 1.0
    for _ in 1:100
        num = mean(f_on_g ./ (sp .* f_on_g .+ sg .* r .* g_on_g))
        den = mean(g_on_f ./ (sp .* f_on_f .+ sg .* r .* g_on_f))
        r_new = num / den
        abs(log(r_new / r)) < 1e-10 && (r = r_new; break)
        r = r_new
    end
    return (cL=log(r), exact_cL=log(Zf / Zg), ratio=Zf / Zg,
            n_samples=n_samples, split_mode=split_mode)
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

function exact_bridge_markov(abs4_L::Vector{Float64}, abs4_H::Vector{Float64}, L::Int;
                             n_steps=20_000, n_warmup=10_000, seed=0xB21D6E,
                             proposal::Symbol=:paper,
                             sector_filter=tfim_fig4_index_sector)
    @assert proposal in (:paper, :group)
    Lh = L ÷ 2
    place = [4^i for i in 0:(L - 1)]
    rng = MersenneTwister(UInt32(seed))

    q = similar(abs4_L)
    @inbounds for idx0 in 0:(length(abs4_L) - 1)
        i1, i2 = split_indices(idx0, L, :contiguous)
        q[idx0 + 1] = abs4_H[i1 + 1] * abs4_H[i2 + 1]
    end
    Zf = sum(abs4_L)
    Zg = sum(q)

    f_on_f = Float64[]
    g_on_f = Float64[]
    f_on_g = Float64[]
    g_on_g = Float64[]
    sizehint!(f_on_f, n_steps); sizehint!(g_on_f, n_steps)
    sizehint!(f_on_g, n_steps); sizehint!(g_on_g, n_steps)

    function propose!(p::Vector{Int}, idx0::Int, Lmove::Int, place_move)
        if rand(rng) < 0.5
            i = rand(rng, 1:Lmove)
            old = p[i]
            new = old ⊻ 3
            return idx0 + (new - old) * place_move[i], i, new, 0, 0
        end
        i = rand(rng, 1:Lmove)
        j = rand(rng, 1:(Lmove - 1))
        j >= i && (j += 1)
        oi, oj = p[i], p[j]
        if proposal == :paper
            ni, nj = oi ⊻ 1, oj ⊻ 1
        else
            ni = (oi == 1 || oi == 2) ? rand(rng, (0, 3)) : rand(rng, (1, 2))
            nj = (oj == 1 || oj == 2) ? rand(rng, (0, 3)) : rand(rng, (1, 2))
        end
        return idx0 + (ni - oi) * place_move[i] + (nj - oj) * place_move[j], i, ni, j, nj
    end

    function accept_move!(p, i, ni, j, nj)
        p[i] = ni
        j != 0 && (p[j] = nj)
    end

    p = zeros(Int, L)
    idx0 = 0
    cur_f = abs4_L[1]
    acc_f = 0
    for step in 1:(n_warmup + n_steps)
        new_idx, i, ni, j, nj = propose!(p, idx0, L, place)
        if sector_filter(new_idx, L)
            new_f = abs4_L[new_idx + 1]
            ratio = cur_f == 0 ? (new_f == 0 ? 0.0 : Inf) : new_f / cur_f
            if rand(rng) < ratio
                accept_move!(p, i, ni, j, nj)
                idx0 = new_idx
                cur_f = new_f
                acc_f += 1
            end
        end
        if step > n_warmup
            push!(f_on_f, cur_f)
            push!(g_on_f, q[idx0 + 1])
        end
    end

    p1 = zeros(Int, Lh)
    p2 = zeros(Int, Lh)
    idx1 = 0
    idx2 = 0
    place_h = [4^i for i in 0:(Lh - 1)]
    cur_g = abs4_H[1] * abs4_H[1]
    acc_g = 0
    for step in 1:(n_warmup + n_steps)
        if rand(rng) < 0.5
            new_idx, i, ni, j, nj = propose!(p1, idx1, Lh, place_h)
            if sector_filter(new_idx, Lh)
                new_g = abs4_H[new_idx + 1] * abs4_H[idx2 + 1]
                ratio = cur_g == 0 ? (new_g == 0 ? 0.0 : Inf) : new_g / cur_g
                if rand(rng) < ratio
                    accept_move!(p1, i, ni, j, nj)
                    idx1 = new_idx
                    cur_g = new_g
                    acc_g += 1
                end
            end
        else
            new_idx, i, ni, j, nj = propose!(p2, idx2, Lh, place_h)
            if sector_filter(new_idx, Lh)
                new_g = abs4_H[idx1 + 1] * abs4_H[new_idx + 1]
                ratio = cur_g == 0 ? (new_g == 0 ? 0.0 : Inf) : new_g / cur_g
                if rand(rng) < ratio
                    accept_move!(p2, i, ni, j, nj)
                    idx2 = new_idx
                    cur_g = new_g
                    acc_g += 1
                end
            end
        end
        if step > n_warmup
            idx_full = idx1 + (4^Lh) * idx2
            push!(f_on_g, abs4_L[idx_full + 1])
            push!(g_on_g, cur_g)
        end
    end

    r = bridge_ratio_estimate(f_on_f, g_on_f, f_on_g, g_on_g)
    return (cL=log(r), exact_cL=log(Zf / Zg), n_samples=n_steps,
            accept_f=acc_f / (n_warmup + n_steps),
            accept_g=acc_g / (n_warmup + n_steps))
end

function main()
    L = parse(Int, get(ENV, "FIG4_DIAG_L", "8"))
    h = parse(Float64, get(ENV, "FIG4_DIAG_H", "0.80"))
    n_steps = parse(Int, get(ENV, "FIG4_DIAG_NSTEPS", "200000"))
    @assert iseven(L)
    @printf("[exact-sector] L=%d h=%.2f n_steps=%d\n", L, h, n_steps)
    sector_filter = tfim_fig4_index_sector
    _, psiL = ed_groundstate(L, h; pbc=true)
    _, psiH = ed_groundstate(L ÷ 2, h; pbc=true)
    abs4_L = pauli_abs4_table(psiL, L; value_filter=sector_filter)
    abs4_H = pauli_abs4_table(psiH, L ÷ 2; value_filter=sector_filter)
    for split_mode in (:contiguous, :interleaved)
        for row in exact_sector_stats(abs4_L, abs4_H, L; split_mode=split_mode)
            @printf("  exact %-11s %-5s support=%6d c_L=%+.8f mean_R=%.8g sd_R=%.6g iid_se_cL@1e6=%.6f max_R=%.6g\n",
                    string(split_mode), string(row.sector), row.support, row.cL, row.mean_R,
                    row.sd_R, row.iid_se_cL_1e6, row.max_R)
            @printf("          log-estimator check: -E[log R]=%+.8f iid_se@1e6=%.6f\n",
                    row.neg_mean_logR, row.iid_se_neg_mean_logR_1e6)
        end
    end
    dual = exact_dual_stats(abs4_L, abs4_H, L)
    @printf("  dual half-product support=%6d c_L=%+.8f mean_R=%.8g sd_R=%.6g iid_se_cL@1e6=%.6f max_R=%.6g\n",
            dual.support, dual.cL, dual.mean_R, dual.sd_R,
            dual.iid_se_cL_1e6, dual.max_R)
    for row in tolerance_sweep(abs4_L, abs4_H, L)
        @printf("  tol 1e%+d support=%6d c_L=%+.8f iid_se_cL@1e6=%.6f dropped_w=%.3e dropped_num=%.3e\n",
                row.exponent, row.support, row.cL, row.iid_se_cL_1e6,
                row.dropped_weight, row.dropped_num)
    end
    for n_bridge in unique((1_000, 10_000, min(n_steps, 100_000)))
        b = exact_bridge_samples(abs4_L, abs4_H, L; n_samples=n_bridge,
                                 split_mode=:contiguous)
        @printf("  bridge exact-categorical samples=%6d c_L=%+.8f exact=%+.8f diff=%+.3e\n",
                b.n_samples, b.cL, b.exact_cL, b.cL - b.exact_cL)
    end
    bmarkov = exact_bridge_markov(abs4_L, abs4_H, L; n_steps=n_steps,
                                  sector_filter=sector_filter)
    @printf("  bridge exact-markov      samples=%6d c_L=%+.8f exact=%+.8f diff=%+.3e accept_f=%.4f accept_g=%.4f\n",
            bmarkov.n_samples, bmarkov.cL, bmarkov.exact_cL, bmarkov.cL - bmarkov.exact_cL,
            bmarkov.accept_f, bmarkov.accept_g)
    for reject in (false, true)
        r = chain_sector(abs4_L, abs4_H, L; n_steps=n_steps, apply_sector_filter=reject,
                         sector_filter=sector_filter)
        @printf("  chain paper apply_sector_filter=%5s c_L=%+.8f mean_R=%.8g accept=%.4f recorded=%d\n",
                string(reject), r.cL, r.mean_R, r.accept, r.n_recorded)
    end
    r = chain_sector(abs4_L, abs4_H, L; n_steps=n_steps, apply_sector_filter=true,
                     proposal=:group, sector_filter=sector_filter)
    @printf("  chain group apply_sector_filter= true c_L=%+.8f mean_R=%.8g accept=%.4f recorded=%d\n",
            r.cL, r.mean_R, r.accept, r.n_recorded)
    r = chain_sector(abs4_L, abs4_H, L; n_steps=n_steps, apply_sector_filter=true,
                     proposal=:paper_generators, sector_filter=sector_filter)
    @printf("  chain paper_generators apply_sector_filter= true c_L=%+.8f mean_R=%.8g accept=%.4f recorded=%d\n",
            r.cL, r.mean_R, r.accept, r.n_recorded)
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
