module PrimalGapAssembly

using SHA
using ..SquareJ1J2Prototype:
    PauliWord,
    enumerate_pauli_words
using ..GenericGapModel:
    GapProblem,
    BasisManifest,
    StateMonomial,
    NoStateSymmetry,
    basis_manifest,
    validate_basis_manifest,
    full_state_entries,
    instantiate_terms,
    assembly_plan,
    state_monomial_string
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key,
    moment_key_string,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256,
    real_part_polynomial,
    imag_part_polynomial,
    normalize_real_equality,
    positive_entry,
    stationarity_entry,
    gap_entry

export StationaritySpec,
       PrimalAssembly,
       stationarity_candidates,
       canonical_stationarity_equalities,
       assemble_primal_gap

const PRIMAL_ASSEMBLY_SCHEMA = "primal-gap-assembly-v1"
const BARE_INNER_STATIONARITY_RULE =
    "all bare Pauli operator words through degree 2d-2 on the inner " *
    "patch; identity and exact-zero commutators removed; complex equations " *
    "split into normalized real and imaginary equations; no scalar " *
    "state-symbol multipliers; no symmetry quotient"
const FULL_INNER_STATE_STATIONARITY_RULE =
    "all canonical state-polynomial monomials through degree 2d-2 on the " *
    "inner patch; identity and exact-zero commutators removed; complex " *
    "equations split into normalized real and imaginary equations; no " *
    "symmetry quotient"

"""
Versioned selector for stationarity test monomials.

`:bare_inner_pauli` version 1 deliberately uses only bare operator words. This
is a sound subset of the full stationarity family, but is not complete.

`:full_inner_state` version 1 uses every canonical state-polynomial monomial
through degree `2d-2` on the inner patch.
"""
struct StationaritySpec
    family::Symbol
    version::Int

    function StationaritySpec(
        family::Symbol=:bare_inner_pauli,
        version::Int=1,
    )
        family in (:bare_inner_pauli, :full_inner_state) ||
            throw(ArgumentError("unsupported stationarity family"))
        version == 1 ||
            throw(ArgumentError("unsupported stationarity family version"))
        new(family, version)
    end
end

"""
Solver-independent, exact assembly inventory.

Matrix entries remain lazy: they are reconstructed with `positive_entry` and
`gap_entry`. The manifest stores every scalar moment, canonical stationarity
equality, and a hash over every upper-triangular matrix coefficient map.
"""
struct PrimalAssembly{P,T}
    schema::String
    problem::P
    problem_sha256::String
    positive_basis::BasisManifest
    gap_basis::BasisManifest
    hamiltonian_terms::Vector{T}
    stationarity_spec::StationaritySpec
    stationarity_selection_rule::String
    stationarity_candidates_sha256::String
    stationarity_equalities::Vector{ExactLinearPolynomial}
    stationarity_equalities_sha256::String
    moments::Vector{MomentKey}
    moments_sha256::String
    coefficient_map_sha256::String
    assembly_sha256::String
end

function write_framed!(io::IO, value)
    serialized = string(value)
    write(io, string(ncodeunits(serialized)), ":", serialized)
    return io
end

function fingerprint_records(schema::String, records)
    io = IOBuffer()
    write_framed!(io, schema)
    for record in records
        write_framed!(io, record)
    end
    return bytes2hex(sha256(take!(io)))
end

function remap_word(word::PauliWord, site_ids::Vector{Int})
    return PauliWord([(site_ids[site], axis) for (site, axis) in word.ops])
end

function stationarity_candidates(
    problem::GapProblem,
    spec::StationaritySpec=StationaritySpec(),
)
    site_ids = sort!(copy(problem.patch.inner_ids))
    isempty(site_ids) &&
        throw(ArgumentError("stationarity needs at least one inner site"))
    if spec.family == :bare_inner_pauli && spec.version == 1
        local_words = enumerate_pauli_words(
            length(site_ids),
            2problem.d - 2,
        )
        return StateMonomial[
            StateMonomial(PauliWord[], remap_word(word, site_ids))
            for word in local_words
        ]
    elseif spec.family == :full_inner_state && spec.version == 1
        return full_state_entries(site_ids, 2problem.d - 2)
    end
    error("validated stationarity spec has no implementation")
end

stationarity_selection_rule(spec::StationaritySpec) =
    spec.family == :bare_inner_pauli ?
    BARE_INNER_STATIONARITY_RULE :
    FULL_INNER_STATE_STATIONARITY_RULE

"""
Split complex stationarity expressions into real equations, discard exact
zeros, normalize nonzero scalar multiples, and remove duplicates.
"""
function canonical_stationarity_equalities(
    candidates::Vector{StateMonomial},
    hamiltonian_terms::AbstractVector,
)
    by_serialization = Dict{String,ExactLinearPolynomial}()
    for candidate in candidates
        expression = stationarity_entry(candidate, hamiltonian_terms)
        for component in (
            real_part_polynomial(expression),
            imag_part_polynomial(expression),
        )
            iszero(component) && continue
            normalized = normalize_real_equality(component)
            serialized = canonical_polynomial_string(normalized)
            by_serialization[serialized] = normalized
        end
    end
    serializations = sort!(collect(keys(by_serialization)))
    return ExactLinearPolynomial[
        by_serialization[serialized]
        for serialized in serializations
    ]
end

function add_polynomial_moments!(
    moments::Set{MomentKey},
    polynomial::ExactLinearPolynomial,
)
    union!(moments, keys(polynomial.terms))
    return moments
end

function record_matrix_entry!(
    coefficient_records::Vector{String},
    moments::Set{MomentKey},
    role::Symbol,
    row::Int,
    column::Int,
    polynomial::ExactLinearPolynomial,
)
    add_polynomial_moments!(moments, polynomial)
    push!(
        coefficient_records,
        string(role, "[", row, ",", column, "]=") *
        polynomial_sha256(polynomial),
    )
    return nothing
end

function moment_inventory_sha256(moments::Vector{MomentKey})
    records = String[
        string(index, "=", moment_key_string(key), ";degree=", moment_degree(key))
        for (index, key) in enumerate(moments)
    ]
    return fingerprint_records("primal-moment-inventory-v1", records)
end

function assembly_fingerprint(
    problem_sha256::String,
    positive_basis_sha256::String,
    gap_basis_sha256::String,
    stationarity_spec::StationaritySpec,
    stationarity_candidates_sha256::String,
    stationarity_equalities_sha256::String,
    moments_sha256::String,
    coefficient_map_sha256::String,
)
    records = String[
        "problem_sha256=" * problem_sha256,
        "positive_basis_sha256=" * positive_basis_sha256,
        "gap_basis_sha256=" * gap_basis_sha256,
        "stationarity_family=" * string(stationarity_spec.family),
        "stationarity_version=" * string(stationarity_spec.version),
        "stationarity_candidates_sha256=" * stationarity_candidates_sha256,
        "stationarity_equalities_sha256=" * stationarity_equalities_sha256,
        "moments_sha256=" * moments_sha256,
        "coefficient_map_sha256=" * coefficient_map_sha256,
    ]
    return fingerprint_records(PRIMAL_ASSEMBLY_SCHEMA, records)
end

function keep_structural_moment(
    symbols::Vector{PauliWord},
    moment_filter::Symbol,
)
    moment_filter == :all && return true
    moment_filter == :v4_conjugation_even ||
        throw(ArgumentError("unsupported structural moment filter"))
    x_odd = false
    y_odd = false
    z_odd = false
    for word in symbols
        for (_, axis) in word.ops
            axis == 1 && (x_odd = !x_odd)
            axis == 2 && (y_odd = !y_odd)
            axis == 3 && (z_odd = !z_odd)
        end
    end
    return !x_odd && !y_odd && !z_odd
end

function structural_moment_inventory(
    problem::GapProblem,
    moment_filter::Symbol,
)
    site_ids = collect(eachindex(problem.patch.sites))
    max_degree = 2problem.d
    local_words = enumerate_pauli_words(length(site_ids), max_degree)
    state_words = PauliWord[
        remap_word(word, site_ids)
        for word in local_words
        if !isempty(word.ops)
    ]

    bucket_count = max(1, 8Threads.nthreads())
    buckets = [MomentKey[] for _ in 1:bucket_count]
    Threads.@threads :dynamic for bucket_index in eachindex(buckets)
        bucket = buckets[bucket_index]
        for root_index in
            bucket_index:bucket_count:length(state_words)
            root = state_words[root_index]
            selected = PauliWord[root]
            function enumerate_from!(
                first_index::Int,
                degree::Int,
            )
                keep_structural_moment(selected, moment_filter) &&
                    push!(bucket, moment_key(selected))
                for index in first_index:length(state_words)
                    word = state_words[index]
                    next_degree = degree + length(word)
                    next_degree > max_degree && break
                    push!(selected, word)
                    enumerate_from!(index, next_degree)
                    pop!(selected)
                end
                return nothing
            end
            enumerate_from!(root_index, length(root))
        end
    end

    ordered_moments = MomentKey[moment_key()]
    for bucket in buckets
        append!(ordered_moments, bucket)
    end
    sort!(
        ordered_moments;
        by=key -> (moment_degree(key), key.canonical),
    )
    return ordered_moments
end

"""
Build the exact scalar-moment inventory and canonical coefficient-map hashes.

This function performs no optimization and loads no solver. Its cost is
quadratic in the two selected basis dimensions because every upper-triangular
matrix entry is visited once.
"""
function assemble_primal_gap(
    problem::GapProblem;
    stationarity_spec::StationaritySpec=StationaritySpec(),
    materialize_coefficients::Bool=true,
    structural_moment_filter::Symbol=:all,
)
    problem.basis_mode == :structured ||
        throw(ArgumentError("exact primal assembly requires :structured mode"))
    problem.symmetry isa NoStateSymmetry ||
        throw(
            ArgumentError(
                "state-symmetry metadata is not implemented by primal assembly",
            ),
        )

    positive_basis = basis_manifest(problem, :positive)
    gap_basis = basis_manifest(problem, :gap)
    validate_basis_manifest(positive_basis, problem, :positive) ||
        error("positive basis failed contextual validation")
    validate_basis_manifest(gap_basis, problem, :gap) ||
        error("gap basis failed contextual validation")
    plan = assembly_plan(problem)
    hamiltonian_terms = instantiate_terms(problem.model, problem.patch)

    candidates = stationarity_candidates(problem, stationarity_spec)
    candidate_records = state_monomial_string.(candidates)
    candidates_sha256 = fingerprint_records(
        "stationarity-candidates-v1",
        candidate_records,
    )
    equalities = canonical_stationarity_equalities(
        candidates,
        hamiltonian_terms,
    )
    equality_records = canonical_polynomial_string.(equalities)
    equalities_sha256 = fingerprint_records(
        "stationarity-real-equalities-v1",
        equality_records,
    )

    if !materialize_coefficients
        ordered_moments =
            structural_moment_inventory(problem, structural_moment_filter)
        length(unique(ordered_moments)) == length(ordered_moments) ||
            error("structural moment inventory contains duplicates")
        first(ordered_moments) == moment_key() ||
            error("identity moment must be first")
        moments_sha256 = moment_inventory_sha256(ordered_moments)
        coefficient_map_sha256 =
            "deferred-structural-v1/" * string(structural_moment_filter)
        final_sha256 = assembly_fingerprint(
            plan.problem_sha256,
            positive_basis.sha256,
            gap_basis.sha256,
            stationarity_spec,
            candidates_sha256,
            equalities_sha256,
            moments_sha256,
            coefficient_map_sha256,
        )
        term_type = eltype(hamiltonian_terms)
        return PrimalAssembly{
            typeof(problem),
            term_type,
        }(
            PRIMAL_ASSEMBLY_SCHEMA,
            problem,
            plan.problem_sha256,
            positive_basis,
            gap_basis,
            hamiltonian_terms,
            stationarity_spec,
            stationarity_selection_rule(stationarity_spec),
            candidates_sha256,
            equalities,
            equalities_sha256,
            ordered_moments,
            moments_sha256,
            coefficient_map_sha256,
            final_sha256,
        )
    end

    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for row in eachindex(positive_basis.entries)
        for column in row:length(positive_basis.entries)
            record_matrix_entry!(
                coefficient_records,
                moments,
                :positive,
                row,
                column,
                positive_entry(
                    positive_basis.entries[row],
                    positive_basis.entries[column],
                ),
            )
        end
    end
    for row in eachindex(gap_basis.entries)
        for column in row:length(gap_basis.entries)
            record_matrix_entry!(
                coefficient_records,
                moments,
                :gap,
                row,
                column,
                gap_entry(
                    gap_basis.entries[row],
                    gap_basis.entries[column],
                    hamiltonian_terms,
                    problem.gamma,
                ),
            )
        end
    end
    for equality in equalities
        add_polynomial_moments!(moments, equality)
    end

    ordered_moments = sort!(
        collect(moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    all(key -> moment_degree(key) <= 2problem.d, ordered_moments) ||
        error("assembly emitted a scalar moment above degree 2d")
    first(ordered_moments) == moment_key() ||
        error("identity moment must be first")

    moments_sha256 = moment_inventory_sha256(ordered_moments)
    coefficient_map_sha256 = fingerprint_records(
        "primal-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    final_sha256 = assembly_fingerprint(
        plan.problem_sha256,
        positive_basis.sha256,
        gap_basis.sha256,
        stationarity_spec,
        candidates_sha256,
        equalities_sha256,
        moments_sha256,
        coefficient_map_sha256,
    )

    term_type = eltype(hamiltonian_terms)
    return PrimalAssembly{
        typeof(problem),
        term_type,
    }(
        PRIMAL_ASSEMBLY_SCHEMA,
        problem,
        plan.problem_sha256,
        positive_basis,
        gap_basis,
        hamiltonian_terms,
        stationarity_spec,
        stationarity_selection_rule(stationarity_spec),
        candidates_sha256,
        equalities,
        equalities_sha256,
        ordered_moments,
        moments_sha256,
        coefficient_map_sha256,
        final_sha256,
    )
end

end
