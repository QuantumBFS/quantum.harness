#!/usr/bin/env julia
# Sound certificate verifier for the exported conic instance.
#
# ONE source of truth: the vector x = a.ray_values. Everything is reconstructed
# from x via explicit index maps -- no separately-exported float matrices, and no
# JuMP/Mosek/the original assembly. Uses only Serialization (read) + LinearAlgebra.
#
# NOTE (advisor @491083f): this audits the *exported conic instance*, NOT the
# physical formulation. Whether the exported instance faithfully represents the
# intended TFIM relaxation is a separate (Priority 3) problem/basis manifest.
#
# Checks (all must pass for a positive result):
#   (0) schema completeness: required fields present, schema_version, nvars>0,
#       ncons>=0, exact block inventory (pos/gap map counts == declared sizes),
#       every block has the EXACT declared square dim (incl 0x0), all indices in
#       range, all numeric arrays finite. Every violation -> immediate SCHEMA_FAIL
#       (never throws, never continues into a numerical op).
#   (1) affine identity:  A*x + affine_constants == 0   (rebuilt from affmap)
#   (2) homogeneous:      affine_constants all ~0 (this model is homogeneous)
#   (3) objective:        c'x > 0   (reconstructed = x[lambda_var_position])
#   (4) cone membership:  every declared pos/gap block (rebuilt from x) symmetric + PSD
#
# Closing the "omitted cone block" hole: the verifier now REQUIRES
#   length(pos_var_positions) == length(pos_sizes)
#   size(map_i) == (pos_sizes[i], pos_sizes[i])
# so a malformed artifact cannot drop its block list and pass vacuously.

using Serialization, LinearAlgebra

struct AuditResult
    ok::Bool
    label::String
    residual::Float64       # ||A*x + const||_inf
    homog_residual::Float64 # max|const|
    cx::Float64             # c'x
    pos_min_eig::Vector{Float64}
    gap_min_eig::Vector{Float64}
    notes::Vector{String}
end

const SCHEMA_VERSION = 1
const REQUIRED_FIELDS = (:schema_version, :N, :gamma, :d, :lso, :termination,
    :primal, :dual, :objective, :nvars, :nconstraints, :affine_constants,
    :affine_map, :c, :pos_var_positions, :gap_var_positions, :pos_sizes,
    :gap_sizes, :lambda_var_position, :ray_values)

# schema failures short-circuit: no numerical op runs on a malformed artifact.
_sf(msg) = AuditResult(false, "SCHEMA_FAIL", NaN, NaN, NaN, Float64[], Float64[], [msg])

function _reconstruct_block(x::Vector{Float64}, idxmap::Matrix{Int})
    n = size(idxmap, 1)
    m = zeros(Float64, n, n)
    @inbounds for j in 1:n, k in 1:n
        m[j, k] = x[idxmap[j, k]]
    end
    return m
end

# Validate declared block inventory vs supplied index maps. Returns an error
# String on the first violation, or nothing if the inventory is complete.
function _validate_blocks(var_positions, sizes, nvars, kind)
    length(var_positions) == length(sizes) ||
        return "$kind: $(length(var_positions)) maps != $(length(sizes)) declared sizes"
    all(s -> s isa Integer && s >= 0, sizes) || return "$kind: declared sizes must be non-negative Int"
    for (i, im) in enumerate(var_positions)
        s = sizes[i]
        im isa AbstractMatrix{<:Integer} ||
            return "$kind block $i: index map must be an integer matrix"
        size(im) == (s, s) ||
            return "$kind block $i: size $(size(im)) != declared ($s,$s) -- missing/empty-for-positive/rectangular/extra"
        s == 0 && continue
        all(v -> 1 <= v <= nvars, im) || return "$kind block $i: index-map var out of [1,$nvars]"
    end
    return nothing
end

function audit(a; tol::Float64=1e-6)
    # ---- (0) schema validation: every violation -> immediate SCHEMA_FAIL ----
    for f in REQUIRED_FIELDS
        hasproperty(a, f) || return _sf("missing required field :$f")
    end
    a.schema_version == SCHEMA_VERSION ||
        return _sf("schema_version $(a.schema_version) != supported $SCHEMA_VERSION")

    nvars = a.nvars
    ncons = a.nconstraints
    (nvars isa Integer && nvars > 0) || return _sf("nvars=$nvars must be a positive Int")
    (ncons isa Integer && ncons >= 0) || return _sf("nconstraints=$ncons must be a non-negative Int")

    length(a.ray_values) == nvars ||
        return _sf("ray_values length $(length(a.ray_values)) != nvars $nvars")
    all(isfinite, a.ray_values) || return _sf("non-finite entry in ray_values")

    length(a.affine_constants) == ncons ||
        return _sf("affine_constants length $(length(a.affine_constants)) != ncons $ncons")
    all(isfinite, a.affine_constants) || return _sf("non-finite affine constant")

    length(a.c) == nvars ||
        return _sf("objective c length $(length(a.c)) != nvars $nvars")
    all(isfinite, a.c) || return _sf("non-finite objective entry")

    for (k, vp, coef) in a.affine_map
        (k isa Integer && 1 <= k <= ncons) ||
            return _sf("affine_map constraint idx $k out of [1,$ncons]")
        (vp isa Integer && 1 <= vp <= nvars) ||
            return _sf("affine_map var idx $vp out of [1,$nvars]")
        isfinite(coef) || return _sf("non-finite affine coefficient")
    end

    (a.lambda_var_position isa Integer && 1 <= a.lambda_var_position <= nvars) ||
        return _sf("lambda_var_position $(a.lambda_var_position) out of [1,$nvars]")

    # block-inventory completeness -- the central Priority 0A fix
    err = _validate_blocks(a.pos_var_positions, a.pos_sizes, nvars, "pos")
    err === nothing || return _sf(err)
    err = _validate_blocks(a.gap_var_positions, a.gap_sizes, nvars, "gap")
    err === nothing || return _sf(err)

    x = a.ray_values
    notes = String[]

    # ---- (1) affine identity  A*x + constants = 0 ----
    cons = copy(a.affine_constants)
    for (k, vp, coef) in a.affine_map
        cons[k] += coef * x[vp]
    end
    resid = isempty(cons) ? 0.0 : maximum(abs, cons)
    aff_ok = resid < tol

    # ---- (2) homogeneous constants (verify the EXPORTED constants ~0) ----
    homog_resid = isempty(a.affine_constants) ? 0.0 : maximum(abs, a.affine_constants)
    homog_ok = homog_resid < tol

    # ---- (3) objective c'x > 0, bound to x[lambda_var_position] ----
    cx = dot(a.c, x)
    obj_ok = cx > tol
    if abs(cx - x[a.lambda_var_position]) > tol
        push!(notes, "c'x != x[lambda_pos] -- objective/lambda binding inconsistent")
        obj_ok = false
    end

    # ---- (4) cone membership: rebuild every declared >0 block from x ----
    pos_min_eig = Float64[]
    gap_min_eig = Float64[]
    sym_ok = true
    for (i, im) in enumerate(a.pos_var_positions)
        a.pos_sizes[i] == 0 && continue
        m = _reconstruct_block(x, im)
        if !issymmetric(m)
            push!(notes, "pos block $i NOT symmetric (index-map aliasing broken)")
            sym_ok = false
        end
        push!(pos_min_eig, minimum(eigvals(Symmetric(m))))
    end
    for (l, im) in enumerate(a.gap_var_positions)
        a.gap_sizes[l] == 0 && continue
        m = _reconstruct_block(x, im)
        if !issymmetric(m)
            push!(notes, "gap block $l NOT symmetric")
            sym_ok = false
        end
        push!(gap_min_eig, minimum(eigvals(Symmetric(m))))
    end
    pos_min = isempty(pos_min_eig) ? 0.0 : minimum(pos_min_eig)
    gap_min = isempty(gap_min_eig) ? 0.0 : minimum(gap_min_eig)
    psd_ok = pos_min >= -tol && gap_min >= -tol

    # ---- classification ----
    checks_pass = aff_ok && homog_ok && obj_ok && psd_ok && sym_ok && isempty(notes)
    label = if !checks_pass
        "AUDIT_FAIL"
    elseif a.termination == "DUAL_INFEASIBLE"
        "DECISIVE_AUDITED"
    elseif a.termination == "OPTIMAL"
        # OPTIMAL + a valid positive improving ray is a status/data contradiction:
        # a homogeneous model with an improving ray has no finite optimum.
        "STATUS_CONTRADICTION"
    else
        "NUMERICALLY_AUDITED_CANDIDATE"
    end
    ok = label in ("DECISIVE_AUDITED", "NUMERICALLY_AUDITED_CANDIDATE")
    return AuditResult(ok, label, resid, homog_resid, cx, pos_min_eig, gap_min_eig, notes)
end

function verify(path::AbstractString; tol::Float64=1e-6, verbose::Bool=true)
    a = open(path) do io
        deserialize(io)
    end
    r = audit(a; tol=tol)
    if verbose
        println("=== Sound certificate audit (one-x binding, schema-complete) ===")
        println("artifact: $path")
        println("N=$(a.N) gamma=$(a.gamma) d=$(a.d)  | nvars=$(a.nvars) ncons=$(a.nconstraints)")
        println("solver: $(a.termination) / $(a.primal) / $(a.dual)")
        println("affine_map entries: $(length(a.affine_map))  declared blocks: pos=$(a.pos_sizes) gap=$(a.gap_sizes)")
        println("--- checks (reconstructed from the single ray x) ---")
        println("  (1) ||A*x+const||_inf       = ", r.residual, "  (<$tol? ", isfinite(r.residual) && r.residual < tol, ")")
        println("  (2) max|const| (homogeneous)= ", r.homog_residual, "  (<$tol? ", isfinite(r.homog_residual) && r.homog_residual < tol, ")")
        println("  (3) c'x (objective)         = ", r.cx, "  (>$tol? ", isfinite(r.cx) && r.cx > tol, ")  [== x[lambda_pos]]")
        println("  (4) pos min eig (rebuilt)   = ", round.(r.pos_min_eig, digits=6))
        println("      gap min eig (rebuilt)   = ", round.(r.gap_min_eig, digits=6))
        isempty(r.notes) || println("  notes: ", r.notes)
        println("==================================================")
        println("RESULT: ", r.ok ? r.label : r.label)
        if r.ok && r.label == "NUMERICALLY_AUDITED_CANDIDATE"
            println("  (floating-point + $(a.termination): numerical candidate, NOT a rigorous proof;")
            println("   rational/interval post-processing needed for strict certification.)")
        elseif r.label == "STATUS_CONTRADICTION"
            println("  (OPTIMAL + positive improving ray is inconsistent for a homogeneous model;")
            println("   needs investigation -- not a decisive certificate.)")
        end
    end
    return r
end

if abspath(PROGRAM_FILE) == @__FILE__
    if length(ARGS) < 1
        println(stderr, "usage: julia verify_certificate.jl <artifact.jls>")
        exit(2)
    end
    r = verify(ARGS[1])
    exit(r.ok ? 0 : 1)
end
