# moment_bundles.jl — O_S rows, V(S) product classes, Γ_{2,S} dual entries.
# THEOREM_CONTRACT_RG_SELECTION §1/§2/§5. Pauli words are Hermitian, so
# u†v = concat(u,v) up to the algebra phase returned by reduce! —
# ⟨u†v⟩ = c·y_[w] with y real and |c|=1 phase (contract §5 realization).

"O_S row operators: mandatory 2-site representatives (sep 1..r) ∪ closures(S)"
function O_rows(S::Vector{String}, N::Int)
    rows = Vector{Vector{UInt16}}()
    for s in 1:r_of(N), a in 1:1        # S3 quotient: one component rep
        w, c = canon(UInt16[a, 3 * s + a], N)
        abs(c) > 1e-14 && !(w in rows) && push!(rows, w)
    end
    for b in S, w in bundle_closure(b, N)
        w in rows || push!(rows, w)
    end
    return rows
end

"""Γ_{2,S} dual gram block in the REAL EMBEDDING [[R,-I],[I,R]] (t=|O_S|):
entries (word, i, j, coef) meaning cons[word] += coef*G[i,j]; plus the list
of product classes (candidate newwords)."""
function gamma2_block(S::Vector{String}, N::Int)
    O = O_rows(S, N)
    t = length(O)
    entries = Tuple{Vector{UInt16},Int,Int,Float64}[]
    prods = Vector{Vector{UInt16}}()
    for i in 1:t, j in 1:t
        w, c = canon(vcat(O[i], O[j]), N)
        abs(c) < 1e-14 && continue
        w in prods || push!(prods, w)
        re, im_ = real(c), imag(c)
        if abs(re) > 1e-14
            push!(entries, (w, i, j, re))            # R block (1,1)
            push!(entries, (w, t + i, t + j, re))    # R block (2,2)
        end
        if abs(im_) > 1e-14
            push!(entries, (w, i, t + j, -im_))      # -I block (1,2)
            push!(entries, (w, t + i, j, im_))       # +I block (2,1)
        end
    end
    return (dim = 2t, entries = entries, rows = O, prods = prods)
end

"""Full V_pool extension word set at N (neutrality gate + training arms):
product classes over O_{pool} (all bundles)."""
vpool_words(N::Int) = gamma2_block(collect(POOL), N).prods
