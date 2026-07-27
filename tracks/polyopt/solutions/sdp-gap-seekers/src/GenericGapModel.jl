module GenericGapModel

using SHA
using ..SquareJ1J2Prototype:
    Site,
    PauliWord,
    pauli_word,
    operator_word_count,
    one_symbol_lift_count,
    full_state_basis_count

export PauliInteractionTemplate,
       TranslationInvariantPauliModel,
       LocalPauliTerm,
       LocalPatch,
       GapProblem,
       AssemblyPlan,
       NoStateSymmetry,
       ExplicitStateSymmetry,
       square_patch_geometry,
       square_j1j2_model,
       instantiate_terms,
       validate_model_buffer,
       assembly_plan,
       legacy_ncpoly_data

"""Geometry-only local consistency window; it contains no coupling values."""
struct LocalPatch
    name::String
    level::Int
    sites::Vector{Site}
    site_to_id::Dict{Site,Int}
    inner_ids::Vector{Int}
end

function square_patch_geometry(L::Int)
    L >= 1 || throw(ArgumentError("L must be at least 1"))
    sites = sort([Site(x, y) for x in -L:L for y in -L:L])
    site_to_id = Dict(site => i for (i, site) in enumerate(sites))
    inner_ids = [
        site_to_id[site]
        for site in sites
        if max(abs(site.x), abs(site.y)) <= L - 1
    ]
    return LocalPatch("linf-square", L, sites, site_to_id, inner_ids)
end

"""One translated local Pauli interaction before a finite patch is chosen."""
struct PauliInteractionTemplate{T<:Real}
    offsets::Vector{Site}
    axes::Vector{Symbol}
    coefficient::T
    tag::Symbol

    function PauliInteractionTemplate(
        offsets::Vector{Site},
        axes::Vector{Symbol},
        coefficient::T,
        tag::Symbol,
    ) where {T<:Real}
        isempty(offsets) && throw(ArgumentError("interaction support cannot be empty"))
        length(offsets) == length(axes) ||
            throw(ArgumentError("one Pauli axis is required per support offset"))
        length(unique(offsets)) == length(offsets) ||
            throw(ArgumentError("interaction template contains a duplicate site"))
        all(axis -> axis in (:X, :Y, :Z), axes) ||
            throw(ArgumentError("Pauli axes must be :X, :Y, or :Z"))
        new{T}(offsets, axes, coefficient, tag)
    end
end

"""Translation-invariant finite-range Pauli interaction."""
struct TranslationInvariantPauliModel{T<:Real}
    name::String
    templates::Vector{PauliInteractionTemplate{T}}
    interaction_range_linf::Int

    function TranslationInvariantPauliModel(
        name::String,
        templates::Vector{PauliInteractionTemplate{T}},
    ) where {T<:Real}
        isempty(templates) && throw(ArgumentError("model needs at least one interaction"))
        interaction_range = maximum(
            maximum(
                max(abs(a.x - b.x), abs(a.y - b.y))
                for a in template.offsets
                for b in template.offsets
            )
            for template in templates
        )
        new{T}(name, templates, interaction_range)
    end
end

"""One exact local term after translation into a patch."""
struct LocalPauliTerm{T<:Real}
    coefficient::Complex{T}
    word::PauliWord
    tag::Symbol
    anchor::Site
end

abstract type AbstractStateSymmetry end
struct NoStateSymmetry <: AbstractStateSymmetry end

"""
Metadata for a declared restriction on KMS states.

This prototype records but does not yet implement the automorphisms. A solver
must not treat this metadata alone as an applied symmetry.
"""
struct ExplicitStateSymmetry <: AbstractStateSymmetry
    name::String
    generators::Vector{String}

    function ExplicitStateSymmetry(name::String, generators::Vector{String})
        isempty(name) && throw(ArgumentError("symmetry name cannot be empty"))
        isempty(generators) && throw(ArgumentError("symmetry needs explicit generators"))
        new(name, sort(unique(generators)))
    end
end

"""
Solver-independent problem description.

`basis_mode=:full_count_only` reports the complete formal basis size but does
not allocate it. `:one_symbol` reports the deterministic incomplete baseline.
"""
struct GapProblem{T<:Real,S<:AbstractStateSymmetry}
    patch::LocalPatch
    model::TranslationInvariantPauliModel{T}
    gamma::T
    d::Int
    basis_mode::Symbol
    symmetry::S

    function GapProblem(
        patch::LocalPatch,
        model::TranslationInvariantPauliModel{T},
        gamma::T,
        d::Int;
        basis_mode::Symbol=:one_symbol,
        symmetry::S=NoStateSymmetry(),
    ) where {T<:Real,S<:AbstractStateSymmetry}
        gamma >= zero(T) || throw(ArgumentError("gamma must be nonnegative"))
        d >= 2 || throw(ArgumentError("d must be at least 2 for a degree-two Hamiltonian"))
        basis_mode in (:one_symbol, :full_count_only) ||
            throw(ArgumentError("unsupported basis mode"))
        validate_model_buffer(model, patch) ||
            throw(ArgumentError("model interactions escape the declared inner buffer"))
        new{T,S}(patch, model, gamma, d, basis_mode, symmetry)
    end
end

"""Pre-solve inventory. It deliberately contains no solver status or bound."""
struct AssemblyPlan
    outer_sites::Int
    inner_sites::Int
    local_terms::Int
    positive_basis_dimension::BigInt
    gap_basis_dimension::BigInt
    basis_mode::Symbol
    symmetry_declared::Bool
    problem_sha256::String
end

function square_j1j2_model(g::T) where {T<:Real}
    # Division by four promotes integer inputs to a usable coefficient type
    # while preserving exact rationals and floating-point inputs.
    C = typeof(g / 4)
    converted_g = convert(C, g)
    templates = PauliInteractionTemplate{C}[]
    for (tag, displacement, coupling) in (
        (:J1, Site(1, 0), one(C)),
        (:J1, Site(0, 1), one(C)),
        (:J2, Site(1, 1), converted_g),
        (:J2, Site(1, -1), converted_g),
    )
        for axis in (:X, :Y, :Z)
            push!(
                templates,
                PauliInteractionTemplate(
                    [Site(0, 0), displacement],
                    [axis, axis],
                    coupling / convert(C, 4),
                    tag,
                ),
            )
        end
    end
    return TranslationInvariantPauliModel("square-j1-j2", templates)
end

translate(anchor::Site, offset::Site) =
    Site(anchor.x + offset.x, anchor.y + offset.y)

function instantiate_terms(
    model::TranslationInvariantPauliModel{T},
    patch::LocalPatch,
) where {T<:Real}
    terms = LocalPauliTerm{T}[]
    for anchor in patch.sites, template in model.templates
        support = [translate(anchor, offset) for offset in template.offsets]
        all(site -> haskey(patch.site_to_id, site), support) || continue
        factors = [
            (patch.site_to_id[support[i]], template.axes[i])
            for i in eachindex(support)
        ]
        phase, word = pauli_word(factors)
        push!(
            terms,
            LocalPauliTerm(
                Complex{T}(phase.re * template.coefficient,
                           phase.im * template.coefficient),
                word,
                template.tag,
                anchor,
            ),
        )
    end
    sort!(terms; by=canonical_term_string)
    length(unique(canonical_term_string.(terms))) == length(terms) ||
        error("interaction instantiation produced duplicate terms")
    return terms
end

"""
Check the exact paper requirement behind the inner patch: every translate of
every interaction template touching an inner site is fully contained in the
outer patch.
"""
function validate_model_buffer(
    model::TranslationInvariantPauliModel,
    patch::LocalPatch,
)
    outer = Set(patch.sites)
    for inner_id in patch.inner_ids
        inner_site = patch.sites[inner_id]
        for template in model.templates, touching_offset in template.offsets
            anchor = Site(
                inner_site.x - touching_offset.x,
                inner_site.y - touching_offset.y,
            )
            translated_support = [
                translate(anchor, offset)
                for offset in template.offsets
            ]
            all(site -> site in outer, translated_support) || return false
        end
    end
    return true
end

function symmetry_string(symmetry::NoStateSymmetry)
    return "none"
end

function symmetry_string(symmetry::ExplicitStateSymmetry)
    return symmetry.name * ":" * join(symmetry.generators, "|")
end

function canonical_word_string(word::PauliWord)
    axis_names = ("X", "Y", "Z")
    return isempty(word.ops) ? "I" : join(
        (
            string(site) * axis_names[Int(axis)]
            for (site, axis) in word.ops
        ),
        ";",
    )
end

function canonical_term_string(term::LocalPauliTerm)
    return join(
        (
            string(term.tag),
            string(term.anchor.x),
            string(term.anchor.y),
            string(real(term.coefficient)),
            string(imag(term.coefficient)),
            canonical_word_string(term.word),
        ),
        ",",
    )
end

function problem_fingerprint(problem::GapProblem, terms)
    lines = String[
        "model=" * problem.model.name,
        "interaction_range_linf=" * string(problem.model.interaction_range_linf),
        "patch=" * problem.patch.name,
        "L=" * string(problem.patch.level),
        "gamma=" * string(problem.gamma),
        "d=" * string(problem.d),
        "basis=" * string(problem.basis_mode),
        "symmetry=" * symmetry_string(problem.symmetry),
    ]
    append!(
        lines,
        (
            "outer_site=" * string(site.x) * "," * string(site.y)
            for site in problem.patch.sites
        ),
    )
    append!(
        lines,
        (
            "inner_site=" *
            string(problem.patch.sites[site_id].x) * "," *
            string(problem.patch.sites[site_id].y)
            for site_id in problem.patch.inner_ids
        ),
    )
    append!(lines, canonical_term_string.(terms))
    return bytes2hex(sha256(join(lines, "\n")))
end

function assembly_plan(problem::GapProblem)
    validate_model_buffer(problem.model, problem.patch) ||
        throw(ArgumentError("model interactions escape the declared inner buffer"))
    terms = instantiate_terms(problem.model, problem.patch)
    outer_sites = length(problem.patch.sites)
    inner_sites = length(problem.patch.inner_ids)

    if problem.basis_mode == :one_symbol
        positive_dimension = one_symbol_lift_count(outer_sites, problem.d)
        gap_dimension = one_symbol_lift_count(inner_sites, problem.d - 1)
    else
        positive_dimension = full_state_basis_count(outer_sites, problem.d)
        gap_dimension = full_state_basis_count(inner_sites, problem.d - 1)
    end

    return AssemblyPlan(
        outer_sites,
        inner_sites,
        length(terms),
        positive_dimension,
        gap_dimension,
        problem.basis_mode,
        !(problem.symmetry isa NoStateSymmetry),
        problem_fingerprint(problem, terms),
    )
end

"""
Produce the support/coefficient arrays expected by upstream `ncpoly` without
loading SpectralGap or a solver.

This is a compatibility adapter only. It does not build a state-polynomial
basis, impose symmetry, or solve an SDP.
"""
function legacy_ncpoly_data(problem::GapProblem)
    terms = instantiate_terms(problem.model, problem.patch)
    all(iszero ∘ imag ∘ (term -> term.coefficient), terms) ||
        throw(ArgumentError("legacy ncpoly supports only real coefficients"))
    supports = [
        [3 * (site - 1) + Int(axis) for (site, axis) in term.word.ops]
        for term in terms
    ]
    coefficients = Float64[Float64(real(term.coefficient)) for term in terms]
    return supports, coefficients
end

end
