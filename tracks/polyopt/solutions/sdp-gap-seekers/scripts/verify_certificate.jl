#!/usr/bin/env julia
# Sound certificate verifier (advisor recheck Priority 0).
#
# ONE source of truth: the vector x = a.ray_values. Everything is reconstructed
# from x via explicit index maps -- no separately-exported float matrices. Uses
# only Serialization (read) + LinearAlgebra. Does NOT call JuMP/Mosek/the
# original assembly.
#
# Checks (all must pass for a NUMERICALLY_AUDITED_CANDIDATE):
#   (0) schema/dimension sanity: nvars, nconstraints, block sizes, finite x,
#       index maps in range, declared sizes match actual matrix dims.
#   (1) affine identity:  A*x + affine_constants == 0   (reconstructed from affmap)
#   (2) homogeneous:      all affine_constants are 0 (this model is homogeneous)
#   (3) objective:        c'x > 0   (reconstructed = x[lambda_var_position])
#   (4) cone membership:  every pos/gpos Gram block (rebuilt from x via the index
#                         map) is symmetric and PSD.
# Result is labelled NUMERICALLY_AUDITED_CANDIDATE (never "certified" for a
# SLOW_PROGRESS / floating-point result).

using Serialization, LinearAlgebra

struct AuditResult
    ok::Bool
    label::String
    residual::Float64
    cx::Float64
    pos_min_eig::Vector{Float64}
    gap_min_eig::Vector{Float64}
    notes::Vector{String}
end

function _reconstruct_block(x::Vector{Float64}, idxmap::Matrix{Int})
    n = size(idxmap, 1)
    m = zeros(Float64, n, n)
    @inbounds for j in 1:n, k in 1:n
        m[j, k] = x[idxmap[j, k]]
    end
    return m
end

function audit(a; tol::Float64=1e-6)
    notes = String[]

    # (0) schema / dimension sanity
    nvars = a.nvars
    ncons = a.nconstraints
    length(a.ray_values) == nvars || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
        ["ray_values length $(length(a.ray_values)) != nvars $nvars"])
    all(isfinite, a.ray_values) || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
        ["non-finite entry in ray_values"])
    length(a.affine_constants) == ncons || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
        ["affine_constants length $(length(a.affine_constants)) != ncons $ncons"])
    length(a.c) == nvars || push!(notes, "objective c length != nvars")
    for (k, vp, coef) in a.affine_map
        (1 <= vp <= nvars) || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
            ["affine_map entry references var $vp out of [1,$nvars] (constraint $k)"])
        (1 <= k <= ncons) || push!(notes, "affine_map constraint idx $k out of range")
    end
    a.lambda_var_position in 1:nvars || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
        ["lambda_var_position $(a.lambda_var_position) out of [1,$nvars]"])
    # block index maps: dims match declared sizes, indices in range
    for (i, im) in enumerate(a.pos_var_positions)
        isempty(im) && continue
        size(im, 1) == a.pos_sizes[i] || push!(notes, "pos block $i index-map dim mismatch")
        all(v -> 1 <= v <= nvars, im) || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
            ["pos block $i index map has out-of-range var index"])
    end
    for (l, im) in enumerate(a.gap_var_positions)
        isempty(im) && continue
        size(im, 1) == a.gap_sizes[l] || push!(notes, "gap block $l index-map dim mismatch")
        all(v -> 1 <= v <= nvars, im) || return AuditResult(false, "SCHEMA_FAIL", NaN, NaN, Float64[], Float64[],
            ["gap block $l index map has out-of-range var index"])
    end

    x = a.ray_values

    # (1) affine identity A*x + constants = 0
    cons = copy(a.affine_constants)
    for (k, vp, coef) in a.affine_map
        cons[k] += coef * x[vp]
    end
    resid = isempty(cons) ? 0.0 : maximum(abs, cons)
    aff_ok = resid < tol

    # (2) homogeneous constants
    homog_ok = all(iszero, a.affine_constants)

    # (3) objective c'x > 0  (= x[lambda_var_position])
    cx = dot(a.c, x)
    obj_ok = cx > tol
    # consistency: c'x must equal x[lambda_pos] (c = e_{lambda_pos})
    if abs(cx - x[a.lambda_var_position]) > tol
        push!(notes, "c'x != x[lambda_pos] -- objective/lambda binding inconsistent")
        obj_ok = false
    end

    # (4) cone membership: rebuild Gram blocks from x, check symmetry + PSD
    pos_min_eig = Float64[]
    gap_min_eig = Float64[]
    sym_ok = true
    for (i, im) in enumerate(a.pos_var_positions)
        isempty(im) && continue
        m = _reconstruct_block(x, im)
        if !issymmetric(m)
            push!(notes, "pos block $i NOT symmetric (index-map aliasing broken)")
            sym_ok = false
        end
        push!(pos_min_eig, minimum(eigvals(Symmetric(m))))
    end
    for (l, im) in enumerate(a.gap_var_positions)
        isempty(im) && continue
        m = _reconstruct_block(x, im)
        if !issymmetric(m)
            push!(notes, "gap block $l NOT symmetric")
            sym_ok = false
        end
        push!(gap_min_eig, minimum(eigvals(Symmetric(m))))
    end
    psd_ok = (!isempty(pos_min_eig) ? minimum(pos_min_eig) >= -tol : true) &&
             (!isempty(gap_min_eig)   ? minimum(gap_min_eig)   >= -tol : true)

    ok = aff_ok && homog_ok && obj_ok && psd_ok && sym_ok && isempty(notes)
    # label: never "certified" for a floating-point / SLOW_PROGRESS candidate
    label = if !ok
        "AUDIT_FAIL"
    elseif a.termination == "DUAL_INFEASIBLE" || a.termination == "OPTIMAL"
        "DECISIVE_AUDITED"
    else
        "NUMERICALLY_AUDITED_CANDIDATE"
    end
    return AuditResult(ok, label, resid, cx, pos_min_eig, gap_min_eig, notes)
end

function verify(path::AbstractString; tol::Float64=1e-6, verbose::Bool=true)
    a = open(path) do io
        deserialize(io)
    end
    r = audit(a; tol=tol)
    if verbose
        println("=== Sound certificate audit (one-x binding) ===")
        println("artifact: $path")
        println("N=$(a.N) gamma=$(a.gamma) d=$(a.d)  | nvars=$(a.nvars) ncons=$(a.nconstraints)")
        println("solver: $(a.termination) / $(a.primal) / $(a.dual)")
        println("affine_map entries: $(length(a.affine_map))  block sizes: pos=$(a.pos_sizes) gap=$(a.gap_sizes)")
        println("--- checks (reconstructed from the single ray x) ---")
        println("  (1) A*x + const residual = ", r.residual, "  (<$tol? ", r.residual < tol, ")")
        println("  (3) c'x (objective)      = ", r.cx, "  (>$tol? ", r.cx > tol, ")  [== x[lambda_pos]]")
        println("  (4) pos min eig (rebuilt)= ", round.(r.pos_min_eig, digits=6))
        println("      gap min eig (rebuilt)= ", round.(r.gap_min_eig, digits=6))
        isempty(r.notes) || println("  notes: ", r.notes)
        println("==================================================")
        println("RESULT: ", r.ok ? r.label : "AUDIT_FAIL")
        if r.ok && r.label == "NUMERICALLY_AUDITED_CANDIDATE"
            println("  (floating-point + $(a.termination): numerical candidate, NOT a rigorous proof;")
            println("   rational/interval post-processing needed for strict certification.)")
        end
    end
    return r
end

if abspath(PROGRAM_FILE) == @__FILE__
    if length(ARGS) < 1
        println(stderr, "usage: julia verify_certificate.jl <artifact.jls> [--test]")
        exit(2)
    end
    r = verify(ARGS[1])
    exit(r.ok ? 0 : 1)
end
