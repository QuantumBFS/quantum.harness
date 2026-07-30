module GenericGapModel

using SHA
using ..SquareJ1J2Prototype:
    Site,
    PauliWord,
    pauli_word,
    enumerate_pauli_words,
    operator_word_count,
    one_symbol_lift_count,
    full_state_basis_count

export PauliInteractionTemplate,
       TranslationInvariantPauliModel,
       LocalPauliTerm,
       LocalPatch,
       GapProblem,
       AssemblyPlan,
       StructuredBasisSpec,
       StateMonomial,
       BasisManifest,
       NoStateSymmetry,
       ExplicitStateSymmetry,
       square_patch_geometry,
       square_j1j2_model,
       shastry_sutherland_model,
       triangular_patch_geometry,
       triangular_heisenberg_model,
       anchor_allowed,
       instantiate_terms,
       validate_model_buffer,
       assembly_plan,
       basis_manifest,
       validate_basis_manifest,
       state_monomial_degree,
       state_monomial_string,
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

"""
One periodically translated local Pauli interaction before a finite patch is
chosen.

`anchor_period` and `anchor_residues` select which lattice sites may anchor a
translate. The default period `(1, 1)` and residue `(0, 0)` recover ordinary
one-site translation invariance.
"""
struct PauliInteractionTemplate{T<:Real}
    offsets::Vector{Site}
    axes::Vector{Symbol}
    coefficient::T
    tag::Symbol
    anchor_period::Site
    anchor_residues::Vector{Site}

    function PauliInteractionTemplate(
        offsets::Vector{Site},
        axes::Vector{Symbol},
        coefficient::T,
        tag::Symbol,
        ;
        anchor_period::Site=Site(1, 1),
        anchor_residues::Vector{Site}=[Site(0, 0)],
    ) where {T<:Real}
        isempty(offsets) && throw(ArgumentError("interaction support cannot be empty"))
        length(offsets) == length(axes) ||
            throw(ArgumentError("one Pauli axis is required per support offset"))
        length(unique(offsets)) == length(offsets) ||
            throw(ArgumentError("interaction template contains a duplicate site"))
        all(axis -> axis in (:X, :Y, :Z), axes) ||
            throw(ArgumentError("Pauli axes must be :X, :Y, or :Z"))
        anchor_period.x >= 1 && anchor_period.y >= 1 ||
            throw(ArgumentError("anchor periods must be positive"))
        isempty(anchor_residues) &&
            throw(ArgumentError("at least one anchor residue is required"))
        canonical_residues = sort(unique(
            Site(
                mod(residue.x, anchor_period.x),
                mod(residue.y, anchor_period.y),
            )
            for residue in anchor_residues
        ))
        new{T}(
            offsets,
            axes,
            coefficient,
            tag,
            anchor_period,
            canonical_residues,
        )
    end
end

"""Periodic translation-invariant finite-range Pauli interaction."""
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
Versioned selection rule for a materialized structured basis.

The `:one_symbol_lift` version 1 family contains every bare Pauli word through
the requested degree and one pure scalar row `ζ(w)` for every nonidentity
word. The deliberately weaker `:bare_weight_one` version 1 family contains
only the identity and single-site bare Pauli words. Both are deterministic,
but neither applies a symmetry quotient. An individual low-degree manifest
can nevertheless equal the full finite inventory; `BasisManifest.is_complete`
records that finite-level fact.
"""
struct StructuredBasisSpec
    family::Symbol
    version::Int

    function StructuredBasisSpec(family::Symbol, version::Int)
        family in (:one_symbol_lift, :bare_weight_one, :bare_operator) ||
            throw(ArgumentError("unsupported structured basis family"))
        version == 1 ||
            throw(ArgumentError("unsupported structured basis family version"))
        new(family, version)
    end
end

"""
Canonical state monomial `ζ(w₁)…ζ(wₖ)v`.

State-symbol words are sorted because the `ζ(w)` commute. Identity state
symbols are forbidden because `ζ(I)=1`; the operator word may be identity.
"""
struct StateMonomial
    state_symbols::Vector{PauliWord}
    operator_word::PauliWord

    function StateMonomial(
        state_symbols::Vector{PauliWord},
        operator_word::PauliWord,
    )
        any(word -> isempty(word.ops), state_symbols) &&
            throw(ArgumentError("identity state symbols must be removed"))
        symbols = [PauliWord(copy(word.ops)) for word in state_symbols]
        sort!(symbols; by=canonical_word_string)
        new(symbols, PauliWord(copy(operator_word.ops)))
    end
end

Base.:(==)(left::StateMonomial, right::StateMonomial) =
    left.state_symbols == right.state_symbols &&
    left.operator_word == right.operator_word
Base.hash(monomial::StateMonomial, h::UInt) =
    hash(Tuple(monomial.state_symbols), hash(monomial.operator_word, h))

state_monomial_degree(monomial::StateMonomial) =
    length(monomial.operator_word) +
    sum(length, monomial.state_symbols; init=0)

"""Materialized, versioned, solver-independent structured-basis inventory."""
struct BasisManifest
    role::Symbol
    family::Symbol
    family_version::Int
    site_ids::Vector{Int}
    max_degree::Int
    entries::Vector{StateMonomial}
    is_complete::Bool
    selection_rule::String
    sha256::String

    function BasisManifest(
        role::Symbol,
        family::Symbol,
        family_version::Int,
        site_ids::Vector{Int},
        max_degree::Int,
        entries::Vector{StateMonomial},
        is_complete::Bool,
        selection_rule::String,
        sha256::String,
    )
        owned_entries = StateMonomial[
            StateMonomial(entry.state_symbols, entry.operator_word)
            for entry in entries
        ]
        new(
            role,
            family,
            family_version,
            copy(site_ids),
            max_degree,
            owned_entries,
            is_complete,
            selection_rule,
            sha256,
        )
    end
end

"""
Solver-independent problem description.

`basis_mode=:full_count_only` reports the complete formal basis size but does
not allocate it. `:one_symbol` reports the deterministic incomplete count-only
baseline. `:structured` requires an explicit `StructuredBasisSpec` and
materializes its entries and hashes.
"""
struct GapProblem{T<:Real,S<:AbstractStateSymmetry}
    patch::LocalPatch
    model::TranslationInvariantPauliModel{T}
    gamma::T
    d::Int
    basis_mode::Symbol
    basis_spec::Union{Nothing,StructuredBasisSpec}
    symmetry::S

    function GapProblem(
        patch::LocalPatch,
        model::TranslationInvariantPauliModel{T},
        gamma::T,
        d::Int;
        basis_mode::Symbol=:one_symbol,
        basis_spec::Union{Nothing,StructuredBasisSpec}=nothing,
        symmetry::S=NoStateSymmetry(),
    ) where {T<:Real,S<:AbstractStateSymmetry}
        gamma >= zero(T) || throw(ArgumentError("gamma must be nonnegative"))
        d >= 2 || throw(ArgumentError("d must be at least 2 for a degree-two Hamiltonian"))
        basis_mode in (:one_symbol, :full_count_only, :structured) ||
            throw(ArgumentError("unsupported basis mode"))
        if basis_mode == :structured
            isnothing(basis_spec) &&
                throw(ArgumentError(":structured mode requires a basis_spec"))
        elseif !isnothing(basis_spec)
            throw(ArgumentError("basis_spec is only valid in :structured mode"))
        end
        validate_model_buffer(model, patch) ||
            throw(ArgumentError("model interactions escape the declared inner buffer"))
        new{T,S}(patch, model, gamma, d, basis_mode, basis_spec, symmetry)
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
    is_complete::Bool
    positive_basis_sha256::Union{Nothing,String}
    gap_basis_sha256::Union{Nothing,String}
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

"""
Spin-1/2 Shastry-Sutherland model in the Challenge 88 normalization

    H(g) = sum_dimer S_i*S_j + g sum_square_NN S_i*S_j,

where `S_i*S_j = (X_i X_j + Y_i Y_j + Z_i Z_j) / 4`.

The two dimer templates are anchored on residues `(0, 0)` and `(0, 1)`
modulo `(2, 2)`. They form the standard orthogonal-dimer covering; every
infinite-lattice site belongs to exactly one dimer.
"""
function shastry_sutherland_model(g::T) where {T<:Real}
    C = typeof(g / 4)
    converted_g = convert(C, g)
    templates = PauliInteractionTemplate{C}[]

    for displacement in (Site(1, 0), Site(0, 1)), axis in (:X, :Y, :Z)
        push!(
            templates,
            PauliInteractionTemplate(
                [Site(0, 0), displacement],
                [axis, axis],
                converted_g / convert(C, 4),
                :square,
            ),
        )
    end

    for (anchor_residue, displacement) in (
        (Site(0, 0), Site(-1, 1)),
        (Site(0, 1), Site(1, 1)),
    ), axis in (:X, :Y, :Z)
        push!(
            templates,
            PauliInteractionTemplate(
                [Site(0, 0), displacement],
                [axis, axis],
                one(C) / convert(C, 4),
                :dimer;
                anchor_period=Site(2, 2),
                anchor_residues=[anchor_residue],
            ),
        )
    end

    return TranslationInvariantPauliModel("shastry-sutherland", templates)
end

"""
Triangular-lattice local-consistency window.

The triangular lattice is realized on the same integer coordinate grid as the
square lattice (a square lattice plus one diagonal), so its local-consistency
window is the same L∞ ball `{-L..L}^2` with inner sites `{max(|x|,|y|) <= L-1}`.
Only the lattice connectivity (the model bonds) differs from the square case;
the patch itself is geometry-only and carries no coupling values.
"""
function triangular_patch_geometry(L::Int)
    L >= 1 || throw(ArgumentError("L must be at least 1"))
    sites = sort([Site(x, y) for x in -L:L for y in -L:L])
    site_to_id = Dict(site => i for (i, site) in enumerate(sites))
    inner_ids = [
        site_to_id[site]
        for site in sites
        if max(abs(site.x), abs(site.y)) <= L - 1
    ]
    return LocalPatch("linf-triangular", L, sites, site_to_id, inner_ids)
end

"""
Spin-1/2 triangular-lattice Heisenberg antiferromagnet in the Challenge 88
normalization

    H = J1 sum_<ij> S_i*S_j,   S_i*S_j = (X_i X_j + Y_i Y_j + Z_i Z_j) / 4,

with antiferromagnetic `J1 = 1`. The three positive nearest-neighbor directions
of the triangular lattice on the integer grid are `(1,0)`, `(0,1)`, `(1,-1)`;
translation invariance generates the remaining three, counting each bond once.
This is the canonical geometrically-frustrated (120 deg order) case. The
Hamiltonian is globally spin-rotation invariant, so the full-spin isotypic
reduction transfers exactly.
"""
function triangular_heisenberg_model(j1::Rational=1//1)
    C = Rational{BigInt}
    converted_j1 = convert(C, j1)
    templates = PauliInteractionTemplate{C}[]
    for (tag, displacement, coupling) in (
        (:J1, Site(1, 0), converted_j1),
        (:J1, Site(0, 1), converted_j1),
        (:J1, Site(1, -1), converted_j1),
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
    return TranslationInvariantPauliModel("triangular-heisenberg", templates)
end

translate(anchor::Site, offset::Site) =
    Site(anchor.x + offset.x, anchor.y + offset.y)

function anchor_allowed(template::PauliInteractionTemplate, anchor::Site)
    residue = Site(
        mod(anchor.x, template.anchor_period.x),
        mod(anchor.y, template.anchor_period.y),
    )
    return residue in template.anchor_residues
end

function instantiate_terms(
    model::TranslationInvariantPauliModel{T},
    patch::LocalPatch,
) where {T<:Real}
    terms = LocalPauliTerm{T}[]
    for anchor in patch.sites, template in model.templates
        anchor_allowed(template, anchor) || continue
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
            anchor_allowed(template, anchor) || continue
            translated_support = [
                translate(anchor, offset)
                for offset in template.offsets
            ]
            all(site -> site in outer, translated_support) || return false
        end
    end
    return true
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

function state_monomial_string(monomial::StateMonomial)
    state_part = join(canonical_word_string.(monomial.state_symbols), "|")
    return "zeta=[" * state_part * "];op=" *
           canonical_word_string(monomial.operator_word)
end

function state_monomial_sort_key(monomial::StateMonomial)
    return (
        state_monomial_degree(monomial),
        length(monomial.state_symbols),
        join(canonical_word_string.(monomial.state_symbols), "|"),
        canonical_word_string(monomial.operator_word),
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

const PROBLEM_FINGERPRINT_SCHEMA = "gap-problem-fingerprint-v2"

"""
Write one injectively framed UTF-8 field for the problem fingerprint.

Both tag and value are byte-length-prefixed, so delimiters inside model names,
symmetry names, or generators cannot collide with field boundaries.
"""
function write_fingerprint_field!(
    io::IO,
    tag::AbstractString,
    value,
)
    tag_string = String(tag)
    value_string = string(value)
    write(
        io,
        "F",
        string(ncodeunits(tag_string)),
        ":",
        tag_string,
        string(ncodeunits(value_string)),
        ":",
        value_string,
    )
    return io
end

function write_symmetry_fingerprint!(io::IO, ::NoStateSymmetry)
    write_fingerprint_field!(io, "symmetry.kind", "none")
    return io
end

function write_symmetry_fingerprint!(
    io::IO,
    symmetry::ExplicitStateSymmetry,
)
    write_fingerprint_field!(io, "symmetry.kind", "explicit")
    write_fingerprint_field!(io, "symmetry.name", symmetry.name)
    write_fingerprint_field!(
        io,
        "symmetry.generator_count",
        length(symmetry.generators),
    )
    for (index, generator) in enumerate(symmetry.generators)
        write_fingerprint_field!(
            io,
            "symmetry.generator[$index]",
            generator,
        )
    end
    return io
end

"""Return a canonical, validated copy of site IDs into one outer patch."""
function canonical_patch_site_ids(
    site_ids::Vector{Int},
    outer_site_count::Int,
)
    canonical_ids = sort!(copy(site_ids))
    length(unique(canonical_ids)) == length(canonical_ids) ||
        throw(ArgumentError("patch site IDs must be unique"))
    all(site -> 1 <= site <= outer_site_count, canonical_ids) ||
        throw(ArgumentError("patch site IDs must index the outer patch"))
    return canonical_ids
end

function problem_fingerprint(
    problem::GapProblem,
    terms;
    positive_basis_sha256::Union{Nothing,String}=nothing,
    gap_basis_sha256::Union{Nothing,String}=nothing,
)
    io = IOBuffer()
    write_fingerprint_field!(io, "schema", PROBLEM_FINGERPRINT_SCHEMA)
    write_fingerprint_field!(io, "model.name", problem.model.name)
    write_fingerprint_field!(
        io,
        "model.interaction_range_linf",
        problem.model.interaction_range_linf,
    )
    write_fingerprint_field!(io, "patch.name", problem.patch.name)
    write_fingerprint_field!(io, "patch.level", problem.patch.level)
    write_fingerprint_field!(io, "gamma", problem.gamma)
    write_fingerprint_field!(io, "degree", problem.d)
    write_fingerprint_field!(io, "basis.mode", problem.basis_mode)
    if isnothing(problem.basis_spec)
        write_fingerprint_field!(io, "basis.spec.kind", "none")
    else
        write_fingerprint_field!(io, "basis.spec.kind", "structured")
        write_fingerprint_field!(
            io,
            "basis.spec.family",
            problem.basis_spec.family,
        )
        write_fingerprint_field!(
            io,
            "basis.spec.version",
            problem.basis_spec.version,
        )
    end
    write_fingerprint_field!(
        io,
        "basis.positive_sha256.present",
        !isnothing(positive_basis_sha256),
    )
    if !isnothing(positive_basis_sha256)
        write_fingerprint_field!(
            io,
            "basis.positive_sha256",
            positive_basis_sha256,
        )
    end
    write_fingerprint_field!(
        io,
        "basis.gap_sha256.present",
        !isnothing(gap_basis_sha256),
    )
    if !isnothing(gap_basis_sha256)
        write_fingerprint_field!(io, "basis.gap_sha256", gap_basis_sha256)
    end
    write_symmetry_fingerprint!(io, problem.symmetry)

    write_fingerprint_field!(
        io,
        "patch.outer_site_count",
        length(problem.patch.sites),
    )
    for (index, site) in enumerate(problem.patch.sites)
        write_fingerprint_field!(io, "patch.outer_site[$index].x", site.x)
        write_fingerprint_field!(io, "patch.outer_site[$index].y", site.y)
    end
    canonical_inner_ids = canonical_patch_site_ids(
        problem.patch.inner_ids,
        length(problem.patch.sites),
    )
    write_fingerprint_field!(
        io,
        "patch.inner_site_count",
        length(canonical_inner_ids),
    )
    for (index, site_id) in enumerate(canonical_inner_ids)
        site = problem.patch.sites[site_id]
        write_fingerprint_field!(io, "patch.inner_site[$index].x", site.x)
        write_fingerprint_field!(io, "patch.inner_site[$index].y", site.y)
    end

    write_fingerprint_field!(io, "term_count", length(terms))
    for (index, term) in enumerate(terms)
        write_fingerprint_field!(io, "term[$index].tag", term.tag)
        write_fingerprint_field!(io, "term[$index].anchor.x", term.anchor.x)
        write_fingerprint_field!(io, "term[$index].anchor.y", term.anchor.y)
        write_fingerprint_field!(
            io,
            "term[$index].coefficient.real",
            real(term.coefficient),
        )
        write_fingerprint_field!(
            io,
            "term[$index].coefficient.imag",
            imag(term.coefficient),
        )
        write_fingerprint_field!(
            io,
            "term[$index].word",
            canonical_word_string(term.word),
        )
    end
    return bytes2hex(sha256(take!(io)))
end

function remap_word(word::PauliWord, site_ids::Vector{Int})
    return PauliWord([(site_ids[site], axis) for (site, axis) in word.ops])
end

function one_symbol_entries(site_ids::Vector{Int}, max_degree::Int)
    isempty(site_ids) && throw(ArgumentError("structured basis needs at least one site"))
    issorted(site_ids) || throw(ArgumentError("structured basis site IDs must be sorted"))
    length(unique(site_ids)) == length(site_ids) ||
        throw(ArgumentError("structured basis site IDs must be unique"))
    all(site -> site > 0, site_ids) ||
        throw(ArgumentError("structured basis site IDs must be positive"))
    max_degree >= 0 || throw(ArgumentError("basis degree must be nonnegative"))

    local_words = enumerate_pauli_words(length(site_ids), max_degree)
    words = [remap_word(word, site_ids) for word in local_words]
    entries = StateMonomial[]
    identity = PauliWord()
    for word in words
        push!(entries, StateMonomial(PauliWord[], word))
        isempty(word.ops) || push!(entries, StateMonomial([word], identity))
    end
    sort!(entries; by=state_monomial_sort_key)
    return entries
end

const ONE_SYMBOL_LIFT_V1_SELECTION_RULE =
    "all bare Pauli words through max_degree plus one pure scalar " *
    "zeta(w) row for each nonidentity word; no multi-zeta rows; " *
    "no symmetry quotient"

const BARE_WEIGHT_ONE_V1_SELECTION_RULE =
    "identity plus all bare Pauli words of support weight one when " *
    "max_degree is at least one; no state-symbol rows; no symmetry quotient"

const BARE_OPERATOR_V1_SELECTION_RULE =
    "all bare Pauli operator words through max_degree; no state-symbol " *
    "rows; no symmetry quotient"

function bare_operator_entries(
    site_ids::Vector{Int},
    max_degree::Int,
)
    isempty(site_ids) &&
        throw(ArgumentError("structured basis needs at least one site"))
    issorted(site_ids) ||
        throw(ArgumentError("structured basis site IDs must be sorted"))
    length(unique(site_ids)) == length(site_ids) ||
        throw(ArgumentError("structured basis site IDs must be unique"))
    all(site -> site > 0, site_ids) ||
        throw(ArgumentError("structured basis site IDs must be positive"))
    max_degree >= 0 ||
        throw(ArgumentError("basis degree must be nonnegative"))

    local_words = enumerate_pauli_words(length(site_ids), max_degree)
    entries = StateMonomial[
        StateMonomial(PauliWord[], remap_word(word, site_ids))
        for word in local_words
    ]
    sort!(entries; by=state_monomial_sort_key)
    return entries
end

function bare_weight_one_entries(
    site_ids::Vector{Int},
    max_degree::Int,
)
    isempty(site_ids) &&
        throw(ArgumentError("structured basis needs at least one site"))
    issorted(site_ids) ||
        throw(ArgumentError("structured basis site IDs must be sorted"))
    length(unique(site_ids)) == length(site_ids) ||
        throw(ArgumentError("structured basis site IDs must be unique"))
    all(site -> site > 0, site_ids) ||
        throw(ArgumentError("structured basis site IDs must be positive"))
    max_degree >= 0 ||
        throw(ArgumentError("basis degree must be nonnegative"))

    local_words = enumerate_pauli_words(
        length(site_ids),
        min(max_degree, 1),
    )
    entries = StateMonomial[
        StateMonomial(PauliWord[], remap_word(word, site_ids))
        for word in local_words
    ]
    sort!(entries; by=state_monomial_sort_key)
    return entries
end

function structured_basis_contents(
    spec::StructuredBasisSpec,
    site_ids::Vector{Int},
    max_degree::Int,
)
    if spec.family == :one_symbol_lift && spec.version == 1
        entries = one_symbol_entries(site_ids, max_degree)
        selected_count = BigInt(length(entries))
        expected_selected_count =
            one_symbol_lift_count(length(site_ids), max_degree)
        selected_count == expected_selected_count ||
            error("one-symbol materialization disagrees with its exact count")
        # The selector is a proved subset of the full formal inventory:
        # bare rows are the k=0 sector and pure ζ(w) rows are the one-symbol,
        # identity-operator sector. Equal finite counts therefore prove equal
        # finite inventories without materializing the much larger full basis.
        is_complete =
            selected_count ==
            full_state_basis_count(length(site_ids), max_degree)
        return (
            entries,
            is_complete,
            ONE_SYMBOL_LIFT_V1_SELECTION_RULE,
        )
    elseif spec.family == :bare_weight_one && spec.version == 1
        entries = bare_weight_one_entries(site_ids, max_degree)
        selected_count = BigInt(length(entries))
        expected_selected_count = operator_word_count(
            length(site_ids),
            min(max_degree, 1),
        )
        selected_count == expected_selected_count ||
            error("bare-weight-one materialization disagrees with its exact count")
        is_complete =
            selected_count ==
            full_state_basis_count(length(site_ids), max_degree)
        return (
            entries,
            is_complete,
            BARE_WEIGHT_ONE_V1_SELECTION_RULE,
        )
    elseif spec.family == :bare_operator && spec.version == 1
        entries = bare_operator_entries(site_ids, max_degree)
        selected_count = BigInt(length(entries))
        expected_selected_count =
            operator_word_count(length(site_ids), max_degree)
        selected_count == expected_selected_count ||
            error("bare-operator materialization disagrees with its exact count")
        is_complete =
            selected_count ==
            full_state_basis_count(length(site_ids), max_degree)
        return (
            entries,
            is_complete,
            BARE_OPERATOR_V1_SELECTION_RULE,
        )
    end
    error("validated structured basis spec has no implementation")
end

function manifest_fingerprint(
    spec::StructuredBasisSpec,
    role::Symbol,
    site_ids::Vector{Int},
    max_degree::Int,
    is_complete::Bool,
    selection_rule::String,
    entries::Vector{StateMonomial},
)
    lines = String[
        "schema=structured-basis-manifest-v1",
        "family=" * string(spec.family),
        "family_version=" * string(spec.version),
        "role=" * string(role),
        "site_ids=" * join(site_ids, ","),
        "max_degree=" * string(max_degree),
        "is_complete=" * string(is_complete),
        "symmetry_applied=false",
        "selection_rule=" * selection_rule,
    ]
    append!(
        lines,
        (
            "entry[" * string(index) * "]=" * state_monomial_string(entry)
            for (index, entry) in enumerate(entries)
        ),
    )
    return bytes2hex(sha256(join(lines, "\n")))
end

"""
Materialize the positive or gap basis selected by a structured problem.

The positive basis uses the outer-patch site IDs through degree `d`; the gap
basis uses the actual inner-patch site IDs through degree `d-1`. No symmetry
metadata is applied at this stage.
"""
function basis_manifest(problem::GapProblem, role::Symbol)
    problem.basis_mode == :structured ||
        throw(ArgumentError("basis manifests require :structured mode"))
    role in (:positive, :gap) ||
        throw(ArgumentError("basis role must be :positive or :gap"))
    spec = problem.basis_spec
    isnothing(spec) && error("validated structured problem lost its basis spec")

    candidate_site_ids = role == :positive ?
        collect(eachindex(problem.patch.sites)) :
        problem.patch.inner_ids
    site_ids = canonical_patch_site_ids(
        candidate_site_ids,
        length(problem.patch.sites),
    )
    isempty(site_ids) &&
        throw(ArgumentError("structured basis needs at least one site"))
    max_degree = role == :positive ? problem.d : problem.d - 1

    entries, is_complete, selection_rule =
        structured_basis_contents(spec, site_ids, max_degree)

    fingerprint = manifest_fingerprint(
        spec,
        role,
        site_ids,
        max_degree,
        is_complete,
        selection_rule,
        entries,
    )
    return BasisManifest(
        role,
        spec.family,
        spec.version,
        site_ids,
        max_degree,
        entries,
        is_complete,
        selection_rule,
        fingerprint,
    )
end

"""
Recompute all structural invariants and the SHA-256 of a basis manifest.

Manifest entries contain arrays for compatibility with the existing Pauli-word
code. A caller that mutates those arrays invalidates the stored hash. This
one-argument method proves internal consistency with the manifest's own
declared role/sites/degree; it does not prove that those declarations belong
to a particular `GapProblem`. Assembly code must use the contextual
three-argument method below.
"""
function validate_basis_manifest(manifest::BasisManifest)
    try
        spec = StructuredBasisSpec(manifest.family, manifest.family_version)
        manifest.role in (:positive, :gap) || return false
        isempty(manifest.site_ids) && return false
        issorted(manifest.site_ids) || return false
        length(unique(manifest.site_ids)) == length(manifest.site_ids) || return false
        all(site -> site > 0, manifest.site_ids) || return false
        manifest.max_degree >= 0 || return false
        length(unique(manifest.entries)) == length(manifest.entries) || return false
        issorted(manifest.entries; by=state_monomial_sort_key) || return false
        all(
            entry -> state_monomial_degree(entry) <= manifest.max_degree,
            manifest.entries,
        ) || return false
        expected_entries, expected_is_complete, expected_selection_rule =
            structured_basis_contents(
                spec,
                manifest.site_ids,
                manifest.max_degree,
            )
        manifest.entries == expected_entries || return false
        manifest.is_complete == expected_is_complete || return false
        manifest.selection_rule == expected_selection_rule || return false
        site_set = Set(manifest.site_ids)
        all(
            entry -> all(
                factor -> factor[1] in site_set,
                Iterators.flatten((
                    entry.operator_word.ops,
                    (word.ops for word in entry.state_symbols)...,
                )),
            ),
            manifest.entries,
        ) || return false
        expected = manifest_fingerprint(
            spec,
            manifest.role,
            manifest.site_ids,
            manifest.max_degree,
            manifest.is_complete,
            manifest.selection_rule,
            manifest.entries,
        )
        return expected == manifest.sha256
    catch
        return false
    end
end

"""
Validate a manifest against the basis required by one problem and role.

This closes the trust boundary left intentionally open by the self-contained
validator: a manifest can be internally valid after consistently relabelling
its role, site set, or degree, yet still be the wrong input for an assembly.
"""
function validate_basis_manifest(
    manifest::BasisManifest,
    problem::GapProblem,
    expected_role::Symbol,
)
    try
        problem.basis_mode == :structured || return false
        expected_role in (:positive, :gap) || return false
        validate_basis_manifest(manifest) || return false
        expected = basis_manifest(problem, expected_role)
        return (
            manifest.role == expected.role &&
            manifest.family == expected.family &&
            manifest.family_version == expected.family_version &&
            manifest.site_ids == expected.site_ids &&
            manifest.max_degree == expected.max_degree &&
            manifest.entries == expected.entries &&
            manifest.is_complete == expected.is_complete &&
            manifest.selection_rule == expected.selection_rule &&
            manifest.sha256 == expected.sha256
        )
    catch
        return false
    end
end

function assembly_plan(problem::GapProblem)
    validate_model_buffer(problem.model, problem.patch) ||
        throw(ArgumentError("model interactions escape the declared inner buffer"))
    terms = instantiate_terms(problem.model, problem.patch)
    outer_sites = length(problem.patch.sites)
    inner_sites = length(problem.patch.inner_ids)
    positive_basis_sha256 = nothing
    gap_basis_sha256 = nothing

    if problem.basis_mode == :one_symbol
        positive_dimension = one_symbol_lift_count(outer_sites, problem.d)
        gap_dimension = one_symbol_lift_count(inner_sites, problem.d - 1)
        is_complete = false
    elseif problem.basis_mode == :full_count_only
        positive_dimension = full_state_basis_count(outer_sites, problem.d)
        gap_dimension = full_state_basis_count(inner_sites, problem.d - 1)
        is_complete = true
    else
        positive_manifest = basis_manifest(problem, :positive)
        gap_manifest = basis_manifest(problem, :gap)
        validate_basis_manifest(positive_manifest, problem, :positive) ||
            error("positive basis manifest failed contextual validation")
        validate_basis_manifest(gap_manifest, problem, :gap) ||
            error("gap basis manifest failed contextual validation")
        positive_dimension = BigInt(length(positive_manifest.entries))
        gap_dimension = BigInt(length(gap_manifest.entries))
        is_complete = positive_manifest.is_complete && gap_manifest.is_complete
        positive_basis_sha256 = positive_manifest.sha256
        gap_basis_sha256 = gap_manifest.sha256
    end

    return AssemblyPlan(
        outer_sites,
        inner_sites,
        length(terms),
        positive_dimension,
        gap_dimension,
        problem.basis_mode,
        is_complete,
        positive_basis_sha256,
        gap_basis_sha256,
        !(problem.symmetry isa NoStateSymmetry),
        problem_fingerprint(
            problem,
            terms;
            positive_basis_sha256=positive_basis_sha256,
            gap_basis_sha256=gap_basis_sha256,
        ),
    )
end

"""
Produce the support/coefficient arrays expected by upstream `ncpoly` without
loading SpectralGap or a solver.

This is a compatibility adapter only. It does not build a state-polynomial
basis, impose symmetry, or solve an SDP. It currently accepts only real
Hamiltonian coefficients, which covers the Heisenberg models used here.
General complex-coefficient Pauli models need an explicit Hermitian
symmetrization step before this legacy adapter.
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
