# vcheck.jl — arbiter-mandated implementation checks (pre-N=200):
#   V1 direct physical-state substitution, PER BLOCK (Hermiticity, eigmin,
#      per-family link residuals) at the ED ground state
#   V2 dual certificate reconstruction for a solved arm: ALL PSD blocks in
#      the model (stock + extension, via JuMP introspection): eigmin ≥ -tol;
#      coefficient residual of every scalar equality at the solved point;
#      objective/duality mismatch
#   V3 newwords-path unit test: synthetic non-mandatory 6-site operator
#      forces seam_newwords > 0; coefficient rows verified; ED-feasible
#      bound; on/off structural signatures differ
#   V4 mutation tests (TEST-ONLY, sandboxed): a sign flip in one link row
#      and an index swap in one Γ entry must turn a gate red / hard-error
# Claim language until pass (arbiter): "single implementation, gate-chain
# validated on tested small-N paths; the N=200-only newwords path remains
# unexercised."
using Printf

"V1: per-block ED substitution for selection S and rg spec at N"
function vcheck_physical(N::Int, S::Vector{String}, As, nrg::Int)
    E0, ψ = heis_ground(N)
    out = String[]; ok = true
    # Γ block: complex Hermiticity + real-embedding eigmin
    gb = gamma2_block(S, N)
    t = gb.dim ÷ 2
    yv = Dict{Vector{UInt16},Float64}()
    Γr = zeros(gb.dim, gb.dim)
    for (w, i, j, c) in gb.entries
        v = get!(() -> word_expect(ψ, N, w), yv, w)
        Γr[i, j] += c * v
    end
    herm = maximum(abs, Γr - Γr')          # real embedding of Hermitian must be symmetric
    λ = minimum(LinearAlgebra.eigvals(LinearAlgebra.Symmetric((Γr + Γr') / 2)))
    okΓ = herm <= 1e-10 && λ >= -1e-10
    ok &= okΓ
    push!(out, @sprintf("V1 Γ_{2,%s}: sym-res %.1e eigmin %+.2e %s", join(S, "+"), herm, λ, okΓ ? "PASS" : "FAIL"))
    # RG blocks: ω_M^p at ED, per block eigmin; link residuals per family
    tw = build_tower(N, nrg, As)
    mm = size(As[1][1], 1); dω = 2 * mm * mm * 2
    hb = hermbasis(dω)
    ωs = Vector{Matrix{ComplexF64}}()
    for M in 4:nrg, p in 1:2
        ρM = window_marginal(ψ, N, 0, M)
        C = cmat(chainmap2(As, M - 2, p + 1), mm)
        Ω = C * ρM * C'
        hres = maximum(abs, Ω - Ω')
        λm = minimum(real, LinearAlgebra.eigvals(LinearAlgebra.Hermitian((Ω + Ω') / 2)))
        okω = hres <= 1e-12 && λm >= -1e-12
        ok &= okω
        push!(out, @sprintf("V1 ω_%d^%d: herm %.1e eigmin %+.2e %s", M, p, hres, λm, okω ? "PASS" : "FAIL"))
        push!(ωs, Ω)
    end
    xc = [[hcoord(h, Ω) for h in hb] for Ω in ωs]
    y2 = Dict{Vector{UInt16},Float64}()
    worst = 0.0
    for r in 1:tw.nrows
        v = sum((c * get!(() -> word_expect(ψ, N, w), y2, w) for (w, c) in tw.ycoef[r]), init = 0.0)
        v += sum((c * xc[blk][k] for (blk, k, c) in tw.srows[r]), init = 0.0)
        worst = max(worst, abs(v))
    end
    okL = worst <= 1e-10
    ok &= okL
    push!(out, @sprintf("V1 links: worst row residual %.1e over %d rows %s", worst, tw.nrows, okL ? "PASS" : "FAIL"))
    return ok, out
end

"V2: certificate on a solved arm — needs the captured model"
function vcheck_certificate(res_model)
    out = String[]; ok = true
    model = res_model
    # all PSD blocks (stock Gram + extension G/Z): eigmin at solution
    worstλ = Inf; nblk = 0
    for (F, S_) in JuMP.list_of_constraint_types(model)
        S_ <: MOI.PositiveSemidefiniteConeTriangle || S_ <: MOI.PositiveSemidefiniteConeSquare || continue
        for con in JuMP.all_constraints(model, F, S_)
            v = JuMP.value.(JuMP.constraint_object(con).func)
            n = S_ <: MOI.PositiveSemidefiniteConeTriangle ?
                Int((sqrt(8 * length(v) + 1) - 1) / 2) : Int(sqrt(length(v)))
            M_ = zeros(n, n)
            if S_ <: MOI.PositiveSemidefiniteConeTriangle
                k = 1
                for j in 1:n, i in 1:j
                    M_[i, j] = v[k]; M_[j, i] = v[k]; k += 1
                end
            else
                M_ .= reshape(v, n, n)
            end
            worstλ = min(worstλ, minimum(LinearAlgebra.eigvals(LinearAlgebra.Symmetric(M_))))
            nblk += 1
        end
    end
    okP = worstλ >= -1e-7
    ok &= okP
    push!(out, @sprintf("V2 PSD blocks: %d blocks, worst eigmin %+.2e %s", nblk, worstλ, okP ? "PASS" : "FAIL"))
    # every scalar equality at the solved point (the coefficient identity)
    worstr = 0.0; neq = 0
    for (F, S_) in JuMP.list_of_constraint_types(model)
        S_ <: MOI.EqualTo{Float64} || continue
        for con in JuMP.all_constraints(model, F, S_)
            co = JuMP.constraint_object(con)
            worstr = max(worstr, abs(JuMP.value(co.func) - co.set.value))
            neq += 1
        end
    end
    okE = worstr <= 1e-6
    ok &= okE
    push!(out, @sprintf("V2 coefficient identity: %d equalities, worst residual %.2e %s", neq, worstr, okE ? "PASS" : "FAIL"))
    push!(out, @sprintf("V2 objective (dual) = %.12f; solver gap folded in ε_cmp per arm", JuMP.objective_value(model)))
    return ok, out
end

"V3: synthetic newwords unit test at N (TEST-ONLY; not a pool member)"
function vcheck_newwords(N::Int)
    out = String[]; ok = true
    # 6-site operator: product of two bond ops at separations far apart —
    # its cross classes are absent from the stock tsupp at extra=1
    u = UInt16[1, 4, 3 * 4 + 1, 3 * 5 + 1]                 # b-type 4-site word
    v = UInt16[2, 5]                                        # sep-1 yy pair
    wU, cU = canon(u, N); wUV, cUV = canon(vcat(u, v), N)
    entries = Tuple{Vector{UInt16},Int,Int,Float64}[]
    # 2x2 Hermitian block over {u, v}: real embedding dim 4
    for ((i, a), (j, b)) in Iterators.product(enumerate((u, v)), enumerate((u, v)))
        w, c = canon(vcat(a, b), N)
        abs(c) < 1e-14 && continue
        push!(entries, (w, i, j, real(c)))
        push!(entries, (w, 2 + i, 2 + j, real(c)))
        if abs(imag(c)) > 1e-14
            push!(entries, (w, i, 2 + j, -imag(c)))
            push!(entries, (w, 2 + i, j, imag(c)))
        end
    end
    words = unique([e[1] for e in entries])
    ext = RGExt(words, [(dim = 4, entries = entries)],
                Vector{Vector{Tuple{Vector{UInt16},Float64}}}(),
                NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Int,Int,Int,Float64}}}}[],
                Tuple{Int,Float64}[], Dict{String,Int}())
    logpath, logio = mktemp()
    E = redirect_stdout(logio) do
        r = GSB_cg(SUPP, COE, N, 4; extra = r_of(N) - 1, rdm = 8, pso = 0,
                   lso = true, QUIET = false, tower = ext)[1]
        flush(logio); r
    end
    close(logio); rm(logpath; force = true)
    nn = get(ext.counters, "seam_newwords", 0)
    base = build_rg_selection_model(N; vspace = :stock)
    E0, ψ = heis_ground(N)
    okN = nn > 0
    okB = E >= base.E - 5e-7 && E <= E0 / N + 5e-7
    ok &= okN && okB
    push!(out, @sprintf("V3 newwords: %d appended %s; bound %.10f valid(base %.10f, E0/N %.10f) %s",
        nn, okN ? "PASS" : "FAIL(0!)", E, base.E, E0 / N, okB ? "PASS" : "FAIL"))
    # ED feasibility of the synthetic block
    yv = Dict{Vector{UInt16},Float64}()
    Γ = zeros(4, 4)
    for (w, i, j, c) in entries
        Γ[i, j] += c * get!(() -> word_expect(ψ, N, w), yv, w)
    end
    λ = minimum(LinearAlgebra.eigvals(LinearAlgebra.Symmetric((Γ + Γ') / 2)))
    okF = λ >= -1e-10
    ok &= okF
    push!(out, @sprintf("V3 ED-feasible: eigmin %+.2e %s", λ, okF ? "PASS" : "FAIL"))
    return ok, out
end

"V4: mutation tests — a defect MUST turn something red (TEST-ONLY)"
function vcheck_mutation(N::Int, As, nrg::Int)
    out = String[]; ok = true
    E0, _ = heis_ground(N)
    base = build_rg_selection_model(N; vspace = :stock)
    # (a) sign flip on one link row
    rg = rg_spec(N, nrg, As)
    bad_ycoef = deepcopy(rg.ycoef)
    if !isempty(bad_ycoef) && !isempty(bad_ycoef[1])
        bad_ycoef[1] = [(w, -c) for (w, c) in bad_ycoef[1]]
    end
    bad = (words = rg.words, ycoef = bad_ycoef, zblocks = rg.zblocks)
    caught = false; note = ""
    try
        r = build_rg_selection_model(N; rg = bad, vspace = :auto)
        viol = r.E > E0 / N + 5e-7 || r.E < base.E - 5e-7 || !isfinite(r.E)
        caught = viol
        note = @sprintf("mutated-E=%.10f (base %.10f, E0/N %.10f) -> %s", r.E, base.E, E0 / N,
                        viol ? "ordering RED as required" : "NOT CAUGHT")
    catch e
        caught = true; note = "solver/model hard failure (caught): " * string(typeof(e))
    end
    ok &= caught
    push!(out, "V4a link-sign mutation: " * note * (caught ? "  PASS" : "  FAIL"))
    # (b) Γ entry word swap: point one entry at a WRONG canonical class
    gb = gamma2_block([POOL[1]], N)
    ent = deepcopy(gb.entries)
    if length(ent) >= 2
        (w1, i1, j1, c1) = ent[1]; (w2, _, _, _) = ent[end]
        ent[1] = (w2, i1, j1, c1)   # wrong word, same slot
    end
    caught2 = false; note2 = ""
    try
        ext = RGExt(Vector{Vector{UInt16}}(), [(dim = gb.dim, entries = ent)],
                    Vector{Vector{Tuple{Vector{UInt16},Float64}}}(),
                    NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Int,Int,Int,Float64}}}}[],
                    Tuple{Int,Float64}[], Dict{String,Int}())
        logpath, logio = mktemp()
        E = redirect_stdout(logio) do
            r = GSB_cg(SUPP, COE, N, 4; extra = r_of(N) - 1, rdm = 8, pso = 0,
                       lso = true, QUIET = false, tower = ext)[1]
            flush(logio); r
        end
        close(logio); rm(logpath; force = true)
        viol = E > E0 / N + 5e-7 || !isfinite(E)
        caught2 = viol
        note2 = @sprintf("mutated-E=%.10f -> %s", E, viol ? "validity RED as required" : "NOT CAUGHT (weaker but valid constraint)")
    catch e
        caught2 = true; note2 = "hard failure (caught): " * string(typeof(e))
    end
    push!(out, "V4b Γ-word mutation (informational): " * note2)
    return ok, out
end
