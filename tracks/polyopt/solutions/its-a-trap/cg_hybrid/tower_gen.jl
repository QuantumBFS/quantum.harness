# tower_gen.jl — GENERATOR: emit the ω-tower constraint rows in the dual
# consumption format defined by gsb_cg.jl's interface contract.
#
# Math (THEOREM_CONTRACT §2/§4). Primal tower rows over (y, ω):
#     R y + S x = 0,     ω_M ⪰ 0            (x = Hermitian coords of ω_4..ω_n)
# where the rows are the (T2) boundary links and (T3) tower links, expanded in
# a Hermitian basis of each link's target space (so every row is REAL).
# (T1) needs no rows: Tr_L ρ3(y) = ρ2(y) holds IDENTICALLY in y after
# QMBCertify's translation canonicalization. ρ2, ρ3 ⪰ 0 (T0/T4's ρ part) are
# implied by the rdm ≥ 8 blocks of the shared κ-baseline (ρ3 = Tr ρ8(y) is a
# y-identity, and PSD survives partial trace) — hybrid arms therefore REQUIRE
# rdm ∈ {8,10}; build_tower is not valid standing alone.
#
# Conic duality (KKT, derived — not guessed):
#     L = h'y − λ(y_∅−1) − ⟨G, A(y)⟩ − μ'(Ry + Sx) − ⟨Z, ω(x)⟩
#     ∂y:  cons[w] += (R'μ)_w        →  tower.ycoef  (coefficients of R)
#     ∂x:  Z_M = mat_M(−S'μ) ⪰ 0     →  tower.zblocks (MINUS sign baked in)
# All rows homogeneous (the y_∅ coefficient rides in ycoef via the empty
# word, tsupp[1]) → tower.brows = [] emitted explicitly.
#
# Word conventions (read from QMBCertify src, commit be63c27):
#   * code = 3*(site−1) + a, a ∈ {1,2,3} ↔ (σx, σy, σz); word = sorted codes
#   * reduce!(w; L, lattice="chain", realify=true) → (canonical, coef):
#     raw_moment = coef * canonical_moment; coef = 0 for sign-symmetry zeros
#     (odd count of any Pauli label); reduce4 canonicalizes over translation,
#     mirror AND the S₃ Pauli-label permutation (Heisenberg/J1-J2 symmetric
#     sector — part of F_base, shared by both arms).
#   * tsupp[1] = UInt16[]; bfind returns nothing on miss (consumer hard-errors).
#
# Include order: after `using JuMP, Mosek, MosekTools, QMBCertify`
# (tower_lib.jl's ceq!/newmodel reference JuMP macros at load).

include(joinpath(@__DIR__, "tower_lib.jl"))

const PMATS = [σx, σy, σz]

# ---------------------------------------------------- Hermitian bases -------
struct HB; typ::Symbol; i::Int; j::Int; end   # :d diag, :s sym, :a antisym

hermbasis(d::Int) = vcat(
    [HB(:d, i, i) for i in 1:d],
    [HB(:s, i, j) for i in 1:d for j in i+1:d],
    [HB(:a, i, j) for i in 1:d for j in i+1:d])

"matrix of basis element: E_ii | E_ij+E_ji | i(E_ij−E_ji)"
function hbmat(h::HB, d::Int)
    M = zeros(ComplexF64, d, d)
    if h.typ == :d
        M[h.i, h.i] = 1
    elseif h.typ == :s
        M[h.i, h.j] = 1; M[h.j, h.i] = 1
    else
        M[h.i, h.j] = im; M[h.j, h.i] = -im
    end
    return M
end

"real coordinate of Hermitian X on basis element h (X = Σ coords·hbmat)"
hcoord(h::HB, X) = h.typ == :d ? real(X[h.i, h.i]) :
                   h.typ == :s ? real(X[h.i, h.j]) : imag(X[h.i, h.j])

# ------------------------------------------------------ ρ3 word groups ------
"""ρ3(y) = Σ_w y_w · groups[w] over canonical words w (incl. the empty word).
Each raw 3-site Pauli word contributes (coef/8)·(its matrix) to its canonical
class; sign-symmetry zero classes are dropped."""
function rho3_groups(L::Int)
    groups = Dict{Vector{UInt16},Matrix{ComplexF64}}()
    for b1 in 0:3, b2 in 0:3, b3 in 0:3
        b = (b1, b2, b3)
        codes = UInt16[3 * (t - 1) + b[t] for t in 1:3 if b[t] > 0]
        w, c = reduce!(copy(codes); L = L, lattice = "chain", realify = true)
        c == 0 && continue
        @assert abs(imag(c)) < 1e-14 "unexpected complex reduce! coef for distinct-site word"
        Wm = kron((t == 0 ? σI : PMATS[t] for t in b)...)
        G = get!(() -> zeros(ComplexF64, 8, 8), groups, w)
        G .+= (real(c) / 8) .* Wm
    end
    return groups
end

# ------------------------------------------------------- the generator ------
"""build_tower(L, n, A) → NamedTuple matching gsb_cg.jl's tower contract.
L = ring size, n = tower top level (Lemma 1: n ≤ L−1), A = uMPS tensors
(vector of two m×m matrices). ω blocks: M = 4..n, each (2m²·2)-dim Hermitian.
Link maps copied VERBATIM from the gate-validated tower.jl E_cg (G1–G4)."""
function build_tower(L::Int, n::Int, A::Vector{Matrix{ComplexF64}})
    mm = size(A[1], 1)
    dω = 2 * mm * mm * 2
    @assert 4 <= n <= L - 1 "Lemma 1 requires n_tower ≤ N−1 (got n=$n, N=$L)"
    W2 = chainmap(A, 2)
    X  = kron(σI, W2)                    # T2-left conjugation
    X2 = kron(W2, σI)                    # T2-right conjugation
    Bm = bmat(A); BmL = bmat_left(A)
    TR = kron(Matrix{ComplexF64}(I, 2mm, 2mm), Bm)
    TL = kron(BmL, Matrix{ComplexF64}(I, mm * 2, mm * 2))
    groups = rho3_groups(L)
    nblk = n - 3
    hb = hermbasis(dω)

    ycoef = Vector{Vector{Tuple{Vector{UInt16},Float64}}}()
    sent  = Vector{Vector{Tuple{Int,Int,Float64}}}()   # S rows: (blk, k, coef)

    # one link equation → t² real rows; ymap/ωmaps are Hermiticity-preserving
    function push_rows!(t, ymap, ωterms)
        yimg = ymap === nothing ? nothing :
               Dict(w => ymap(Gm) for (w, Gm) in groups)
        ωimg = [(blk, sgn, [ωmap(hbmat(h, dω)) for h in hb]) for (blk, ωmap, sgn) in ωterms]
        for f in hermbasis(t)
            yr = Tuple{Vector{UInt16},Float64}[]
            if yimg !== nothing
                for (w, T) in yimg
                    c = hcoord(f, T)
                    abs(c) > 1e-12 && push!(yr, (w, c))
                end
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

    # (T2) boundary links: + y-image − ω4-trace  (tower.jl lines, verbatim maps)
    push_rows!(2mm, ρ -> ptr_mid(X * ρ * X', 2mm, mm, 1),
        [(1, Ω -> ptr_last(ptr_mid(Ω, 2mm, mm, 2), 2mm), -1.0)])
    push_rows!(mm * 2, ρ -> ptr_first_m(X2 * ρ * X2', mm, mm * 2),
        [(1, Ω -> ptr_first(ptr_mid(Ω, 2, mm, mm * 2), mm * 2), -1.0)])
    # (T3) tower links: + 𝓡/𝓛(ω_M) − trace(ω_{M+1})
    for M in 4:(n - 1)
        blk = M - 3
        push_rows!(2mm, nothing,
            [(blk,     Ω -> ptr_last_m(TR * Ω * TR', 2mm, mm),                +1.0),
             (blk + 1, Ω -> ptr_last_m(ptr_last(Ω, 2mm * mm), 2mm, mm),      -1.0)])
        push_rows!(mm * 2, nothing,
            [(blk,     Ω -> ptr_first_m(TL * Ω * TL', mm, mm * 2),            +1.0),
             (blk + 1, Ω -> ptr_first_m(ptr_first(Ω, mm * mm * 2), mm, mm * 2), -1.0)])
    end

    # dual blocks: Z_blk = real-embed(mat(−S'μ)) ⪰ 0, dim 2dω; upper triangle
    # only (consumer symmetrizes): Re → (i,j) & (dω+i,dω+j); Im part of the
    # antisym element i(E_ij−E_ji): embed [Re −Im; Im Re] → (i,dω+j) = −Im,
    # (j,dω+i) = +Im.
    zb = [(dim = 2dω, entries = Tuple{Int,Int,Int,Float64}[]) for _ in 1:nblk]
    for (r, sr) in enumerate(sent), (blk, k, c) in sr
        h = hb[k]; σc = -c                      # the KKT minus sign
        if h.typ == :d
            push!(zb[blk].entries, (h.i, h.i, r, σc))
            push!(zb[blk].entries, (dω + h.i, dω + h.i, r, σc))
        elseif h.typ == :s
            push!(zb[blk].entries, (h.i, h.j, r, σc))
            push!(zb[blk].entries, (dω + h.i, dω + h.j, r, σc))
        else
            push!(zb[blk].entries, (h.i, dω + h.j, r, -σc))
            push!(zb[blk].entries, (h.j, dω + h.i, r, σc))
        end
    end

    nwords = length(unique(first.(vcat(ycoef...))))
    @info "tower built" L n nrows = length(ycoef) nblocks = nblk zdim = 2dω y_words = nwords
    # srows = the raw S rows (blk, k, coef) — used only by oracle_check;
    # the gsb_cg.jl consumer reads nrows/ycoef/zblocks/brows and ignores it.
    return (nrows = length(ycoef), ycoef = ycoef, zblocks = zb,
            brows = Tuple{Int,Float64}[], srows = sent)
end

# ------------------------------------------------- ED primal-row oracle -----
"dense ED of the Heisenberg N-ring (site 1 = MSB, matching window_marginal)"
function heis_ground(N::Int)
    H = zeros(Float64, 2^N, 2^N)
    for i in 1:N
        j = i % N + 1
        for P in PMATS
            ops = [k == i || k == j ? P : σI for k in 1:N]
            H .+= 0.25 .* real.(kron(ops...))
        end
    end
    F = eigen(Symmetric(H))
    return F.values[1], F.vectors[:, 1]
end

"⟨ψ| word |ψ⟩ for a QMBCertify code word, on the N-ring state ψ"
function word_expect(ψ::Vector{Float64}, N::Int, w::Vector{UInt16})
    ops = [σI for _ in 1:N]
    for code in w
        site = div(Int(code) - 1, 3) + 1
        ops[site] = PMATS[mod1(Int(code), 3)]
    end
    op = kron(ops...)
    return real(dot(ψ, op * ψ))
end

"""Oracle: the emitted rows must be satisfied by the physical ED assignment
(y from ground-state moments, ω_M = 𝒞_M(ρ_M)) to ≤ tol. Validates R AND S in
the exact numeric conventions the consumer will see. Also cross-checks the
reduce! moment interpretation and the ρ3(y) reconstruction."""
function oracle_check(L::Int, n::Int, A::Vector{Matrix{ComplexF64}}; tol = 1e-10)
    tw = build_tower(L, n, A)
    mm = size(A[1], 1); dω = 2 * mm * mm * 2
    hb = hermbasis(dω)
    E0, ψ = heis_ground(L)

    # reduce! interpretation: ⟨raw⟩ == coef·⟨canonical⟩ for all 64 raw words
    worst_red = 0.0
    for b1 in 0:3, b2 in 0:3, b3 in 0:3
        b = (b1, b2, b3)
        codes = UInt16[3 * (t - 1) + b[t] for t in 1:3 if b[t] > 0]
        w, c = reduce!(copy(codes); L = L, lattice = "chain", realify = true)
        lhs = word_expect(ψ, L, codes)
        rhs = c == 0 ? 0.0 : real(c) * word_expect(ψ, L, w)
        worst_red = max(worst_red, abs(lhs - rhs))
    end

    # y values + ρ3 reconstruction
    groups = rho3_groups(L)
    y = Dict(w => word_expect(ψ, L, w) for w in keys(groups))
    ρ3 = window_marginal(ψ, L, 0, 3)
    worst_rec = maximum(abs, sum(y[w] .* G for (w, G) in groups) - ρ3)

    # ω from the physical marginals
    ωs = Vector{Matrix{ComplexF64}}()
    for M in 4:n
        ρM = window_marginal(ψ, L, 0, M)
        C = cmat(chainmap(A, M - 2), mm)
        push!(ωs, C * ρM * C')
    end
    xcoords = [[hcoord(h, Ω) for h in hb] for Ω in ωs]

    # row residuals: R y + S x over the physical assignment
    worst_row = 0.0
    for r in 1:tw.nrows
        v = sum((c * y[w] for (w, c) in tw.ycoef[r]), init = 0.0)
        v += sum((c * xcoords[blk][k] for (blk, k, c) in tw.srows[r]), init = 0.0)
        worst_row = max(worst_row, abs(v))
    end
    return (E0 = E0, worst_reduce = worst_red, worst_reconstruct = worst_rec,
            worst_row = worst_row,
            pass = worst_red <= tol && worst_rec <= tol && worst_row <= tol)
end
