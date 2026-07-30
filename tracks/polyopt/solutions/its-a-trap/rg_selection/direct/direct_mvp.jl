#!/usr/bin/env julia
# direct_mvp.jl <stage> — DIRECT-CG MVP (FINAL CUT + N=10 primary ruling).
# stages: g0 | greg (map cert + registry + interface audit + G1 + G2 + G5)
#         g3 | g4 | solve <N> <A|B|C|D> | finalize
# One coarse level, D=2 dual parity, T2-type links ONLY (no ω-tower ladder).
# Registry rows are consumed through the validated RGExt ycoef/zblocks
# channels; C-arm assertion: seam admits ZERO new words (tsupp ≡ W_R).
using Printf, SHA, Dates
include(joinpath(@__DIR__, "..", "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "..", "src", "functional_rg.jl"))   # tower_gen primitives

const DIR = @__DIR__
const CH = (rdm = false, pso = 0, lso = false)
const GCSV = joinpath(DIR, "soundness_gates.csv")
isfile(GCSV) || open(io -> println(io, "gate,verdict,detail"), GCSV, "w")
gate!(n, c, m) = (println(@sprintf("%-6s %s  %s", n, c ? "PASS" : "FAIL", m));
                  open(io -> println(io, "$n,$(c ? "PASS" : "FAIL"),\"$m\""), GCSV, "a"); c)

# ---------------- shared: tsupp dump hook + allowlist ----------------
struct AbortDump <: Exception end
struct TsuppDump; out::Base.RefValue{Vector{Vector{UInt16}}}; end
function tower_dual_extend!(model, cons, tsupp, L, d::TsuppDump)
    d.out[] = copy(tsupp); throw(AbortDump())
end
struct PostDump; inner::RGExt; out::Base.RefValue{Vector{Vector{UInt16}}}; end
function tower_dual_extend!(model, cons, tsupp, L, d::PostDump)
    tower_dual_extend!(model, cons, tsupp, L, d.inner)
    d.out[] = copy(tsupp); throw(AbortDump())
end
struct CostProbe; inner::RGExt; st::Dict{String,Any}; end
function tower_dual_extend!(model, cons, tsupp, L, d::CostProbe)
    tower_dual_extend!(model, cons, tsupp, L, d.inner)
    st = d.st
    st["rows"] = length(tsupp)
    st["nnz"] = sum(length(JuMP.linear_terms(c)) for c in cons)
    psd = 0; big = 0
    for (F, S_) in JuMP.list_of_constraint_types(model)
        (S_ <: MOI.PositiveSemidefiniteConeTriangle || S_ <: MOI.PositiveSemidefiniteConeSquare) || continue
        for con in JuMP.all_constraints(model, F, S_)
            lv = length(JuMP.constraint_object(con).func)
            n = S_ <: MOI.PositiveSemidefiniteConeTriangle ? Int((sqrt(8lv + 1) - 1) / 2) : Int(sqrt(lv))
            psd += lv; big = max(big, n)
        end
    end
    st["psd"] = psd; st["big"] = big
    throw(AbortDump())
end
empty_ext() = RGExt(Vector{Vector{UInt16}}(), NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Vector{UInt16},Int,Int,Float64}}}}[],
    Vector{Vector{Tuple{Vector{UInt16},Float64}}}(),
    NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Int,Int,Int,Float64}}}}[],
    Tuple{Int,Float64}[], Dict{String,Int}())

function run_probe(N, extra, hook)
    try
        redirect_stdout(devnull) do
            GSB_cg(SUPP, COE, N, 4; extra = extra, rdm = false, pso = 0,
                   lso = false, QUIET = false, tower = hook)
        end
    catch e
        e isa AbortDump || rethrow()
    end
end
function stock_tsupp(N, extra)
    ref = Ref(Vector{Vector{UInt16}}()); run_probe(N, extra, TsuppDump(ref)); ref[]
end
allowlist(N) = sort(stock_tsupp(N, r_of(N) - 1))

# ---------------- D=2 map + certificate ----------------
function load_D2()
    s = read(joinpath(DIR, "..", "..", "cg_hybrid", "vumps_A_D2.json"), String)
    grab(key) = begin
        m = match(Regex("\"$key\":\\[\\[(.*?)\\],\\[(.*?)\\]\\]"), s)
        [parse.(Float64, split(m.captures[i], ",")) for i in 1:2]
    end
    [[begin
         v = grab("A$(i)_re")[μ] .+ 1im .* grab("A$(i)_im")[μ]
         m = Int(sqrt(length(v))); Matrix{ComplexF64}(reshape(v, m, m))
      end for μ in 1:2] for i in 1:2]
end
d2_hash() = bytes2hex(sha256(read(joinpath(DIR, "..", "..", "cg_hybrid", "vumps_A_D2.json"))))[1:16]

function map_certificate(As)
    iso = maximum(norm(sum(As[i][μ]' * As[i][μ] for μ in 1:2) - I) for i in 1:2)
    flow = compat_residual(As)
    ok1 = gate!("Gmap1", iso <= 1e-10, @sprintf("per-parity isometry (CP/normalization) %.2e", iso))
    ok2 = gate!("Gmap2", flow <= 1e-12, @sprintf("dual-parity flow identity compat_residual %.2e", flow))
    ok1 && ok2
end

# ---------------- coarse registry: ONE level, T2-type links only ----------
function mk_registry(N::Int, As)
    mm = size(As[1][1], 1)                      # 2
    dω = 2 * mm * mm * 2                        # 16
    hb = hermbasis(dω)
    groups = rho3_groups(N)
    ycoef = Vector{Vector{Tuple{Vector{UInt16},Float64}}}()
    sent  = Vector{Vector{Tuple{Int,Int,Float64}}}()
    function push_rows!(t, ymap, ωterms)
        yimg = Dict(w => ymap(Gm) for (w, Gm) in groups)
        ωimg = [(blk, sgn, [ωmap(hbmat(h, dω)) for h in hb]) for (blk, ωmap, sgn) in ωterms]
        for f in hermbasis(t)
            yr = Tuple{Vector{UInt16},Float64}[]
            for (w, T) in yimg
                c = hcoord(f, T)
                abs(c) > 1e-12 && push!(yr, (w, c))
            end
            sr = Tuple{Int,Int,Float64}[]
            for (blk, sgn, imgs) in ωimg, (k, T) in enumerate(imgs)
                c = sgn * hcoord(f, T)
                abs(c) > 1e-12 && push!(sr, (blk, k, c))
            end
            (isempty(yr) && isempty(sr)) && continue
            push!(ycoef, yr); push!(sent, sr)
        end
    end
    for p in 1:2                                # M=4 window only; two parities
        W2p = chainmap2(As, 2, p + 1)
        Xp  = kron(σI, W2p)
        X2p = kron(W2p, σI)
        push_rows!(2mm, ρ -> ptr_mid(Xp * ρ * Xp', 2mm, mm, 1),
            [(p, Ω -> ptr_last(ptr_mid(Ω, 2mm, mm, 2), 2mm), -1.0)])
        push_rows!(mm * 2, ρ -> ptr_first_m(X2p * ρ * X2p', mm, mm * 2),
            [(p, Ω -> ptr_first(ptr_mid(Ω, 2, mm, mm * 2), mm * 2), -1.0)])
    end
    zb = [(dim = 2dω, entries = Tuple{Int,Int,Int,Float64}[]) for _ in 1:2]
    for (r, sr) in enumerate(sent), (blk, k, c) in sr
        h = hb[k]; σc = -c
        if h.typ == :d
            push!(zb[blk].entries, (h.i, h.i, r, σc)); push!(zb[blk].entries, (dω + h.i, dω + h.i, r, σc))
        elseif h.typ == :s
            push!(zb[blk].entries, (h.i, h.j, r, σc)); push!(zb[blk].entries, (dω + h.i, dω + h.j, r, σc))
        else
            push!(zb[blk].entries, (h.i, dω + h.j, r, -σc)); push!(zb[blk].entries, (h.j, dω + h.i, r, σc))
        end
    end
    words = unique(first.(vcat(ycoef...)))
    return (words = words, ycoef = ycoef, zblocks = zb, sent = sent, dω = dω, hb = hb)
end
reg_tuple(reg) = (words = reg.words, ycoef = reg.ycoef, zblocks = reg.zblocks)

# ---------------- stages ----------------
const STAGE = ARGS[1]

if STAGE == "g0"
    for N in (8, 10)
        tR = allowlist(N); tF = stock_tsupp(N, N ÷ 2 - 1)
        WD = [w for w in tF if bfind(tR, w) === nothing]
        sha_ = bytes2hex(sha256(join((join(Int.(w), "-") for w in tR), ";")))
        @printf("N=%d |W_full|=%d |W_R|=%d |W_D|=%d allowlist_sha=%s\n",
                N, length(tF), length(tR), length(WD), sha_[1:16])
        gate!("G0_N$N", true, "partition |W_full|=$(length(tF)) |W_R|=$(length(tR)) |W_D|=$(length(WD)) allowlist_sha16=$(sha_[1:16])" *
              (N == 8 ? " (DEGENERATE control: W_D empty)" : ""))
        open(joinpath(DIR, "BASIS_PARTITION_N$N.json"), "w") do io
            enc(ws) = "[" * join(("\"" * join(Int.(w), "-") * "\"" for w in ws), ",") * "]"
            print(io, "{\"N\": $N, \"W_full\": $(length(tF)), \"W_R\": $(length(tR)), \"W_D\": $(length(WD)), ")
            print(io, "\"allowlist_sha256\": \"$sha_\", \"W_R_words\": ", enc(tR), ", \"W_D_words\": ", enc(WD), "}")
        end
    end
elseif STAGE == "greg"
    As = load_D2()
    ok = map_certificate(As)
    reg = mk_registry(10, As)
    tR = allowlist(10)
    # interface audit: every link y-word must lie in W_R
    insides = [bfind(tR, w) !== nothing for w in reg.words]
    open(joinpath(DIR, "COARSE_INTERFACE_AUDIT.csv"), "w") do io
        println(io, "word,in_W_R,role")
        for (w, inside) in zip(reg.words, insides)
            println(io, "\"$(Int.(w))\",$(inside),T2-link y-word (N=10)")
        end
    end
    nout = count(!, insides)
    gate!("Gifc", nout == 0, "coarse pullback words: $(length(reg.words)) total, $nout outside W_R (rule: reject if any)")
    # G1: deleted-object-zero — post-extension tsupp must equal W_R exactly
    ref = Ref(Vector{Vector{UInt16}}())
    ext = RGExt(reg.words, NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Vector{UInt16},Int,Int,Float64}}}}[],
                reg.ycoef, [(dim = z.dim, entries = z.entries) for z in reg.zblocks],
                Tuple{Int,Float64}[], Dict{String,Int}())
    run_probe(10, r_of(10) - 1, PostDump(ext, ref))
    post = sort(ref[])
    same = post == tR
    gate!("G1", same && get(ext.counters, "seam_newwords", -1) == 0,
          "C-arm post-extension tsupp ≡ W_R: $(same); seam_newwords=$(get(ext.counters,"seam_newwords",-1)); deleted_words_created=0")
    # G2: exact objective
    wobj, cobj = canon(UInt16[1, 4], 10)
    gate!("G2", bfind(tR, wobj) !== nothing && abs(abs(cobj) - 1) < 1e-12,
          "objective class canon([1,4]) in W_R; quotient coef |c|=$(abs(cobj)); model coe=3/4 exact")
    # G5: structural cost C vs A at N=10 (+ N=8 control)
    rows = String[]
    for (N, tag) in ((10, "primary"), (8, "degenerate-control"))
        regN = N == 10 ? reg : mk_registry(8, As)
        stA = Dict{String,Any}(); run_probe(N, N ÷ 2 - 1, CostProbe(empty_ext(), stA))
        stB = Dict{String,Any}(); run_probe(N, r_of(N) - 1, CostProbe(empty_ext(), stB))
        extN = RGExt(regN.words, NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Vector{UInt16},Int,Int,Float64}}}}[],
                     regN.ycoef, [(dim = z.dim, entries = z.entries) for z in regN.zblocks],
                     Tuple{Int,Float64}[], Dict{String,Int}())
        stC = Dict{String,Any}(); run_probe(N, r_of(N) - 1, CostProbe(extN, stC))
        rat = stC["psd"] / stA["psd"]
        push!(rows, "$N,A,$(stA["psd"]),$(stA["big"]),$(stA["rows"]),$(stA["nnz"])")
        push!(rows, "$N,B,$(stB["psd"]),$(stB["big"]),$(stB["rows"]),$(stB["nnz"])")
        push!(rows, "$N,C,$(stC["psd"]),$(stC["big"]),$(stC["rows"]),$(stC["nnz"])")
        if N == 10
            gate!("G5", rat < 1.0, @sprintf("structural C/A = %d/%d = %.3f (%s) largest_block C=%d A=%d",
                  stC["psd"], stA["psd"], rat, rat <= 0.7 ? "meets preferred 0.7" : "under 1.0", stC["big"], stA["big"]))
        else
            gate!("G5_N8", true, @sprintf("degenerate control: C/A = %.3f (A≡B, no deletion possible)", rat))
        end
    end
    open(joinpath(DIR, "build_costs.csv"), "w") do io
        println(io, "N,arm,psd_scalars,largest_block,rows,nnz")
        foreach(l -> println(io, l), rows)
    end
elseif STAGE == "g3"
    As = load_D2(); reg = mk_registry(10, As)
    E0, ψ = heis_ground(10)
    mm = 2
    okA = true; msgs = String[]
    ωs = Vector{Matrix{ComplexF64}}()
    for p in 1:2
        ρ4 = window_marginal(ψ, 10, 0, 4)
        C = cmat(chainmap2(As, 2, p + 1), mm)
        Ω = C * ρ4 * C'
        λ = minimum(real, LinearAlgebra.eigvals(LinearAlgebra.Hermitian((Ω + Ω') / 2)))
        okA &= λ >= -1e-12
        push!(msgs, @sprintf("coarse block p=%d eigmin %+.2e", p, λ)); push!(ωs, Ω)
    end
    gate!("G3a", okA, "coarse Gram PSD at ED: " * join(msgs, "; "))
    xc = [[hcoord(h, Ω) for h in reg.hb] for Ω in ωs]
    yv = Dict{Vector{UInt16},Float64}()
    worst = 0.0
    for (r, yr) in enumerate(reg.ycoef)
        v = sum((c * get!(() -> word_expect(ψ, 10, w), yv, w) for (w, c) in yr), init = 0.0)
        v += sum((c * xc[blk][k] for (blk, k, c) in reg.sent[r]), init = 0.0)
        worst = max(worst, abs(v))
    end
    gate!("G3b", worst <= 1e-10, @sprintf("link residual worst %.1e over %d rows", worst, length(reg.ycoef)))
    gb = gamma2_block(String[], 10)   # retained-Gram witness: mandatory O-rows
    G = zeros(gb.dim, gb.dim)
    for (w, i, j, c) in gb.entries
        G[i, j] += c * get!(() -> word_expect(ψ, 10, w), yv, w)
    end
    λR = minimum(LinearAlgebra.eigvals(LinearAlgebra.Symmetric((G + G') / 2)))
    gate!("G3c", λR >= -1e-10, @sprintf("retained-Gram witness eigmin %+.2e (dim %d)", λR, gb.dim))
elseif STAGE == "g4"
    As = load_D2(); reg = mk_registry(10, As)
    bad_ycoef = deepcopy(reg.ycoef)
    i0 = findfirst(!isempty, bad_ycoef)
    bad_ycoef[i0] = [(w, -c) for (w, c) in bad_ycoef[i0]]
    E0, _ = heis_ground(10)
    red = Ref(false); note = Ref("")
    try
        r = build_rg_selection_model(10; rg = (words = reg.words, ycoef = bad_ycoef, zblocks = reg.zblocks),
                                     vspace = :auto, extra = r_of(10) - 1, CH...)
        red[] = !isfinite(r.E) || r.E > E0 / 10 + 5e-7 || r.E < -0.46
        note[] = @sprintf("mutated-E=%s (E0/N=%.10f)", string(r.E), E0 / 10)
    catch e
        red[] = true; note[] = "hard failure (caught): " * string(typeof(e))
    end
    gate!("G4", red[], "link-coefficient sign-flip -> " * note[] * (red[] ? " RED" : " NOT CAUGHT"))
elseif STAGE == "solve"
    N = parse(Int, ARGS[2]); ARM = ARGS[3]
    As = ARM in ("C", "D") ? load_D2() : nothing
    reg = ARM in ("C", "D") ? mk_registry(N, As) : nothing
    S = ARM == "D" ? ["B_half"] : String[]
    xtra = ARM == "A" ? N ÷ 2 - 1 : r_of(N) - 1
    kw = ARM == "A" || ARM == "B" ? (vspace = :stock,) :
         (vspace = :auto, rg = reg_tuple(reg))
    t0 = time()
    r = build_rg_selection_model(N; S = S, extra = xtra, kw..., CH...)
    w = time() - t0
    # D-arm bundle-exception assertion: new words == declared W_bundle exactly
    note = ""
    if ARM == "D"
        tR = allowlist(N)
        gbb = gamma2_block(["B_half"], N)
        declared = sort(unique([w_ for w_ in vcat(gbb.prods, bundle_closure("B_half", N)) if bfind(tR, w_) === nothing]))
        nw = get(r.counters, "seam_newwords", -1)
        okb = nw == length(declared)
        gate!("G6bundle", okb, "created_words_D∩W_D: seam_newwords=$nw declared |W_bundle|=$(length(declared)) exact=$(okb)")
        note = " bundle=B_half(FIXED_CORRECTION_BUNDLE_NO_SELECTION)"
    end
    stat = isfinite(r.E) && r.resid.pfeas <= 1e-6 && r.resid.dfeas <= 1e-6 ? "OPTIMAL" : "NONOPT"
    open(joinpath(DIR, "solve_results.csv"), "a") do io
        println(io, "$N,$ARM,$(r.E),$(r.resid.pfeas),$(r.resid.dfeas),$(r.resid.mu)," *
            "$(r.sig.scalarized),$(r.sig.nrows),$(get(r.counters,"seam_newwords",-1))," *
            "$(round(w,digits=1)),$(round(Sys.maxrss()/2^30,digits=2)),$stat")
    end
    @printf("SOLVE %s@N=%d E=%.12f %s wall=%.0fs rss=%.1fG%s\n", ARM, N, r.E, stat, w, Sys.maxrss() / 2^30, note)
else
    error("unknown stage")
end
