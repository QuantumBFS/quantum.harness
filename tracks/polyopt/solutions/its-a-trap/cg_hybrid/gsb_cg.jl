# GSB_cg — the ONE sanctioned fork of QMBCertify's GSB (Plan v2, M0).
#
# Strategy: textual fork at load time, not a hand copy. We read the GSB
# function source from the PINNED package file (sha256-checked), apply
# exactly three mechanical transformations, and eval the result here:
#   (1) rename  GSB  ->  GSB_cg_raw
#   (2) append kwarg  tower=nothing  to the signature
#   (3) insert ONE hook line immediately before the coefficient-matching
#       constraint  @constraint(model, con, cons==zeros(length(tsupp)))
#       (the RECON.md seam between bound_gsp.jl:578 and :579):
#           tower === nothing || tower_dual_extend!(model, cons, tsupp, L, tower)
# Stock GSB and the package source are untouched; with tower === nothing the
# execution path is character-identical to stock (M0-C regression gate
# verifies |E_adapter − E_GSB| ≤ 1e-8 at N=10/14 × {CONFIG A, rdm=8}).
#
# Supported envelope (RECON.md M0-B item 6): lattice="chain",
# correlation=false, energy=[], SU2_symmetry=false, writetofile=false.
# GSB_cg throws outside it.
#
# ---------------------------------------------------------------------------
# tower INTERFACE CONTRACT (consumer side; the generator in tower.jl must
# emit exactly this; THEOREM_CONTRACT §4 fixes the math):
#   tower.nrows    :: Int — number of REAL equality rows A_y y + A_ω ω = b
#   tower.ycoef    :: Vector{Vector{Tuple{Vector{UInt16},Float64}}}
#                     per row: (canonical word, coefficient) pairs — the
#                     (A_yᵀ μ)_w contribution. Every word MUST resolve in
#                     tsupp (hard error otherwise — never silently dropped).
#   tower.zblocks  :: Vector of (dim::Int, entries::Vector{NTuple{4,...}})
#                     per dual block Z: entries (i, j, row, c) meaning
#                     Z[i,j] += c * μ[row]; generator bakes in the sign so
#                     that the constraint posted here is Z ⪰ 0 (real
#                     symmetric embedding of the Hermitian block).
#   tower.brows    :: Vector{Tuple{Int,Float64}} — inhomogeneous rows
#                     (row, b): contributes b·μ[row] to the Max objective.
#                     Emit explicitly; never assumed empty.
# ---------------------------------------------------------------------------

using JuMP, Mosek, MosekTools
using LinearAlgebra, SparseArrays   # GSB body references Symmetric etc.
using QMBCertify
using SHA

# The exact source this fork is valid against (commit be63c27):
const GSB_SRC = joinpath(dirname(pathof(QMBCertify)), "bound_gsp.jl")
const GSB_SRC_SHA256 = "bc33d5913868e4556651408495b93543e19cf704699ccabc4b5b4ad37f2ab96c"

# internal helpers the pasted body calls unqualified (RECON.md inventory)
const bfind       = QMBCertify.bfind
const get_basis   = QMBCertify.get_basis
const slabel      = QMBCertify.slabel
const update!     = QMBCertify.update!
const filter_mons = QMBCertify.filter_mons
const reduce4     = QMBCertify.reduce4
const posepsd8!   = QMBCertify.posepsd8!
const posepsd9!   = QMBCertify.posepsd9!
const posepsd10!  = QMBCertify.posepsd10!
import QMBCertify: reduce!, mosek_para, qmb_data
const MOI = JuMP.MOI

# ------------------------------------------------------- the dual extension --
"""Insert the ω-tower's dual terms (THEOREM_CONTRACT §4) into the SOHS model.
Called at the RECON seam, before `con` is posted."""
function tower_dual_extend!(model, cons, tsupp, L, tower)
    μ = @variable(model, [1:tower.nrows])
    # y-side adjoint: cons[w] += (A_yᵀ μ)_w
    for (r, pairs) in enumerate(tower.ycoef)
        for (w, c) in pairs
            Locb = bfind(tsupp, w)
            Locb === nothing && error("tower word $(w) not in tsupp — generator/basis mismatch (hard error by contract)")
            add_to_expression!(cons[Locb], c, μ[r])
        end
    end
    # new PSD dual blocks: Z ⪰ 0, Z affine in μ (sign baked in by generator)
    for blk in tower.zblocks
        Z = [AffExpr(0.0) for _ in 1:blk.dim, _ in 1:blk.dim]
        for (i, j, r, c) in blk.entries
            add_to_expression!(Z[i, j], c, μ[r])
            i != j && add_to_expression!(Z[j, i], c, μ[r])
        end
        @constraint(model, Symmetric(Z) in PSDCone())
    end
    # inhomogeneous rows: objective gains Σ b·μ (explicit; never assumed 0)
    if !isempty(tower.brows)
        extra = sum(b * μ[r] for (r, b) in tower.brows)
        @objective(model, Max, objective_function(model) + extra)
    end
    return μ
end

# ------------------------------------------------ load-time textual fork ----
function _build_fork()
    src = read(GSB_SRC, String)
    sha = bytes2hex(sha256(src))
    if GSB_SRC_SHA256 != "PIN_ME" && sha != GSB_SRC_SHA256
        error("bound_gsp.jl sha256 = $sha does not match the pinned $(GSB_SRC_SHA256); refork deliberately or fix the checkout")
    end
    # extract the GSB function text: from its signature to the `end` right
    # after `return objv,data`
    i0 = findfirst("function GSB(", src)
    i0 === nothing && error("GSB signature not found")
    itail = findfirst("return objv,data", src)
    itail === nothing && error("GSB tail not found")
    iend = findnext("\nend", src, last(itail))
    body = src[first(i0):(first(iend)+3)]

    # (1) rename
    body = replace(body, "function GSB(" => "function GSB_cg_raw(")
    # (2) tower kwarg — anchor: the signature's final default argument
    sig_anchor = "mosek_setting=mosek_para())"
    occursin(sig_anchor, body) || error("signature anchor not found — package changed; re-audit the fork")
    body = replace(body, sig_anchor => "mosek_setting=mosek_para(), tower=nothing)"; count = 1)
    # (3) the ONE hook line at the seam
    con_anchor = "@constraint(model, con, cons==zeros(length(tsupp)))"
    occursin(con_anchor, body) || error("seam anchor not found — package changed; re-audit the fork")
    body = replace(body,
        con_anchor => "tower === nothing || tower_dual_extend!(model, cons, tsupp, L, tower)\n    " * con_anchor;
        count = 1)
    return body, sha
end

const _FORK_BODY, _FORK_SHA = _build_fork()
eval(Meta.parseall(_FORK_BODY))
@info "GSB_cg_raw forked" sha256 = _FORK_SHA

# --------------------------------------------------- envelope-guard wrapper --
function GSB_cg(supp, coe, L, d; lattice = "chain", correlation = false,
                energy = [], SU2_symmetry = false, writetofile = false,
                tower = nothing, kwargs...)
    # HARD GUARD (final-plan amendment 2 / ten-corrections law): a tower may
    # only be attached when a validated gate record exists next to this file.
    if tower !== nothing
        gate = joinpath(@__DIR__, "hybrid_test.out")
        isfile(gate) || error("tower=on without gate record: $(gate) missing — run hybrid_test.jl first")
        startswith(readline(gate), "hybrid_test.jl  PASS") ||
            error("tower=on but gate record is not PASS — no coupled run permitted")
    end
    lattice == "chain"      || error("GSB_cg envelope: lattice=chain only")
    correlation == false    || error("GSB_cg envelope: correlation unsupported")
    isempty(energy)         || error("GSB_cg envelope: energy window unsupported")
    SU2_symmetry == false   || error("GSB_cg envelope: SU2_symmetry unsupported")
    writetofile == false    || error("GSB_cg envelope: writetofile unsupported")
    return GSB_cg_raw(supp, coe, L, d; lattice, correlation, energy,
                      SU2_symmetry, writetofile, tower, kwargs...)
end
