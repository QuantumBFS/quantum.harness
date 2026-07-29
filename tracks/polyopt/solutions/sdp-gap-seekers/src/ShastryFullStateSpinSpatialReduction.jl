module ShastryFullStateSpinSpatialReduction

using SHA
using ..SquareJ1J2Prototype:
    PauliWord
using ..GenericGapModel:
    StateMonomial
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    add_term!,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256
using ..ExactSymmetryReduction:
    V4Character,
    canonical_real_equalities
using ..ConjugationSymmetryReduction:
    polynomial_row_rank
using ..FullStateSymmetryReduction:
    FullStateReducedRow,
    FullStatePSDBlock,
    FullStateV4ReducedPrimalAssembly,
    full_state_v4_block_entry
using ..ShastryFullStateSpatialReduction:
    ShastrySpatialMomentQuotient,
    ShastrySpatialPSDBlock,
    ShastryFullStateSpatialReducedPrimalAssembly,
    parse_moment_word,
    spatial_representative,
    shastry_spatial_block_entry

export SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA,
       SpinAxisPermutation,
       SPIN_AXIS_PERMUTATIONS,
       ShastrySpinSpatialMomentQuotient,
       ShastryFullStateSpinSpatialReducedPrimalAssembly,
       full_state_spin_permutation_truth,
       shastry_spin_spatial_reduction_truth,
       shastry_spin_spatial_block_entry,
       assemble_shastry_full_state_spin_spatial_reduced_primal,
       shastry_full_state_spin_spatial_reduced_assembly_report

const SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA =
    "shastry-sutherland-full-state-v4-conjugation-spin-spatial-v1"

const SpinAxisPermutation = NTuple{3,UInt8}
const SPIN_AXIS_PERMUTATIONS = SpinAxisPermutation[
    (0x01, 0x02, 0x03),
    (0x01, 0x03, 0x02),
    (0x02, 0x01, 0x03),
    (0x02, 0x03, 0x01),
    (0x03, 0x01, 0x02),
    (0x03, 0x02, 0x01),
]

const TRIVIAL_CHARACTER = V4Character(false, false)
const AXIS_CHARACTERS = (
    V4Character(false, true),
    V4Character(true, false),
    V4Character(true, true),
)

function permutation_sign(permutation::SpinAxisPermutation)
    inversions = count(
        left > right
        for left_index in 1:2
        for left in (permutation[left_index],)
        for right in permutation[(left_index + 1):3]
    )
    return isodd(inversions) ? -1 : 1
end

function spin_word(
    word::PauliWord,
    permutation::SpinAxisPermutation,
)
    parity = permutation_sign(permutation)
    sign = parity == -1 && isodd(length(word)) ? -1 : 1
    transformed = PauliWord([
        (site, permutation[Int(axis)])
        for (site, axis) in word.ops
    ])
    return sign, transformed
end

function spin_character(
    character::V4Character,
    permutation::SpinAxisPermutation,
)
    character == TRIVIAL_CHARACTER && return character
    source_axis = findfirst(==(character), AXIS_CHARACTERS)
    isnothing(source_axis) &&
        error("unknown nontrivial V4 character")
    return AXIS_CHARACTERS[Int(permutation[something(source_axis)])]
end

function spin_state_monomial(
    monomial::StateMonomial,
    permutation::SpinAxisPermutation,
)
    sign = 1
    state_symbols = PauliWord[]
    for word in monomial.state_symbols
        word_sign, transformed = spin_word(word, permutation)
        sign *= word_sign
        push!(state_symbols, transformed)
    end
    operator_sign, operator_word =
        spin_word(monomial.operator_word, permutation)
    sign *= operator_sign
    return sign, StateMonomial(state_symbols, operator_word)
end

function spin_row(
    row::FullStateReducedRow,
    permutation::SpinAxisPermutation,
)
    sign, source = spin_state_monomial(row.source, permutation)
    return sign, FullStateReducedRow(row.family, source)
end

function spin_moment(
    key::MomentKey,
    permutation::SpinAxisPermutation,
)
    isempty(key.canonical) && return 1, moment_key()
    sign = 1
    words = PauliWord[]
    for serialized in split(key.canonical, '|')
        word_sign, transformed =
            spin_word(parse_moment_word(serialized), permutation)
        sign *= word_sign
        push!(words, transformed)
    end
    target = moment_key(words)
    moment_degree(target) == moment_degree(key) ||
        error("spin permutation changed moment degree")
    return sign, target
end

function build_spin_actions(moments::Vector{MomentKey})
    inventory = Set(moments)
    actions = Vector{Dict{MomentKey,Tuple{Int,MomentKey}}}()
    for permutation in SPIN_AXIS_PERMUTATIONS
        action = Dict{MomentKey,Tuple{Int,MomentKey}}()
        for key in moments
            sign, target = spin_moment(key, permutation)
            target in inventory ||
                error("moment inventory is not closed under spin permutations")
            action[key] = (sign, target)
        end
        push!(actions, action)
    end
    return actions
end

function spin_polynomial_action(
    polynomial::ExactLinearPolynomial,
    action::Dict{MomentKey,Tuple{Int,MomentKey}},
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(action, key) ||
            error("polynomial moment is outside the spin action")
        sign, target = action[key]
        add_term!(result, target, sign * coefficient)
    end
    return result
end

function hamiltonian_spin_invariant(
    source::FullStateV4ReducedPrimalAssembly,
)
    terms = source.source.hamiltonian_terms
    original = Dict{PauliWord,Any}()
    for term in terms
        original[term.word] =
            get(original, term.word, zero(term.coefficient)) +
            term.coefficient
    end
    for permutation in SPIN_AXIS_PERMUTATIONS
        transformed = Dict{PauliWord,Any}()
        for term in terms
            sign, word = spin_word(term.word, permutation)
            transformed[word] =
                get(transformed, word, zero(term.coefficient)) +
                sign * term.coefficient
        end
        transformed == original || return false
    end
    return true
end

block_key(block::FullStatePSDBlock) = (
    block.role,
    block.family,
    block.character.rx,
    block.character.ry,
)

"""
Exhaustive coefficient gate before conjugation realification.

At this layer every proper spin-axis permutation is a signed row
permutation, so the covariance identity is checked without inferring any
complex phase gauge.
"""
function full_state_spin_permutation_truth(
    source::FullStateV4ReducedPrimalAssembly,
)
    actions = build_spin_actions(source.moments)
    blocks = [source.positive_blocks; source.gap_blocks]
    by_key = Dict(block_key(block) => block for block in blocks)
    coefficient_covariant = true
    coefficient_count = 0
    row_actions_close = true

    for (
        permutation_index,
        permutation,
    ) in enumerate(SPIN_AXIS_PERMUTATIONS)
        action = actions[permutation_index]
        for block in blocks
            target_character =
                spin_character(block.character, permutation)
            key = (
                block.role,
                block.family,
                target_character.rx,
                target_character.ry,
            )
            haskey(by_key, key) ||
                error("spin-covariance target block is missing")
            target = by_key[key]
            target_indices = Dict(
                row => index
                for (index, row) in enumerate(target.rows)
            )
            row_targets = Int[]
            row_signs = Int[]
            for row in block.rows
                sign, transformed = spin_row(row, permutation)
                if !haskey(target_indices, transformed)
                    row_actions_close = false
                    error("spin-covariance target row is missing")
                end
                push!(row_targets, target_indices[transformed])
                push!(row_signs, sign)
            end
            for row in eachindex(block.rows)
                for column in row:length(block.rows)
                    polynomial = full_state_v4_block_entry(
                        source,
                        block,
                        block.rows[row],
                        block.rows[column],
                    )
                    transformed =
                        spin_polynomial_action(polynomial, action)
                    expected =
                        (row_signs[row] * row_signs[column]) *
                        full_state_v4_block_entry(
                            source,
                            target,
                            target.rows[row_targets[row]],
                            target.rows[row_targets[column]],
                        )
                    coefficient_covariant &= transformed == expected
                    coefficient_count += 1
                end
            end
        end
    end

    transformed_equalities = ExactLinearPolynomial[
        spin_polynomial_action(equality, action)
        for action in actions
        for equality in source.equalities
    ]
    equality_invariant =
        polynomial_row_rank(source.equalities) ==
        polynomial_row_rank([source.equalities; transformed_equalities])
    hamiltonian_invariant = hamiltonian_spin_invariant(source)
    return (
        exact=hamiltonian_invariant &&
              row_actions_close &&
              coefficient_covariant &&
              equality_invariant,
        hamiltonian_invariant=hamiltonian_invariant,
        row_actions_close=row_actions_close,
        coefficient_covariant=coefficient_covariant,
        coefficient_count=coefficient_count,
        equality_space_invariant=equality_invariant,
    )
end

struct ShastrySpinSpatialMomentQuotient
    actions::Vector{Dict{MomentKey,MomentKey}}
    representatives::Dict{MomentKey,MomentKey}
    moments::Vector{MomentKey}
    spatial_quotient::ShastrySpatialMomentQuotient
    representative_cache::Vector{Dict{MomentKey,MomentKey}}
    cache_locks::Vector{ReentrantLock}
end

function representative_cache()
    bucket_count = max(64, 8Threads.nthreads())
    return (
        [Dict{MomentKey,MomentKey}() for _ in 1:bucket_count],
        [ReentrantLock() for _ in 1:bucket_count],
    )
end

function build_spin_spatial_actions(
    source::ShastryFullStateSpatialReducedPrimalAssembly,
)
    inventory = Set(source.moments)
    source_inventory = Set(source.source.moments)
    actions = Vector{Dict{MomentKey,MomentKey}}()
    for permutation in SPIN_AXIS_PERMUTATIONS
        action = Dict{MomentKey,MomentKey}()
        for key in source.moments
            sign, transformed = spin_moment(key, permutation)
            sign == 1 ||
                error("V4-invariant spatial moment acquired a spin sign")
            transformed in source_inventory ||
                error("pre-spatial inventory is not spin closed")
            target = spatial_representative(source.quotient, transformed)
            target in inventory ||
                error("spin-spatial action leaves the spatial inventory")
            action[key] = target
        end
        length(unique(values(action))) == length(source.moments) ||
            error("spin-spatial action is not a permutation")
        push!(actions, action)
    end
    return actions
end

function build_spin_spatial_moment_quotient(
    source::ShastryFullStateSpatialReducedPrimalAssembly,
    ;
    materialize::Bool=true,
)
    if !materialize
        cache, locks = representative_cache()
        return ShastrySpinSpatialMomentQuotient(
            Vector{Dict{MomentKey,MomentKey}}(),
            Dict{MomentKey,MomentKey}(),
            MomentKey[],
            source.quotient,
            cache,
            locks,
        )
    end
    actions = build_spin_spatial_actions(source)
    representatives = Dict{MomentKey,MomentKey}()
    representative_set = Set{MomentKey}()
    for key in source.moments
        orbit = MomentKey[action[key] for action in actions]
        representative = minimum(orbit)
        representatives[key] = representative
        push!(representative_set, representative)
    end
    ordered = sort!(
        collect(representative_set);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(ordered) == moment_key() ||
        error("identity moment is not first after spin-spatial quotient")
    cache, locks = representative_cache()
    return ShastrySpinSpatialMomentQuotient(
        actions,
        representatives,
        ordered,
        source.quotient,
        cache,
        locks,
    )
end

function spin_spatial_representative(
    quotient::ShastrySpinSpatialMomentQuotient,
    key::MomentKey,
)
    haskey(quotient.representatives, key) &&
        return quotient.representatives[key]
    isempty(quotient.spatial_quotient.site_map) &&
        error("polynomial moment is outside the spin-spatial quotient")
    bucket_index =
        mod(hash(key), UInt(length(quotient.representative_cache))) + 1
    bucket = quotient.representative_cache[bucket_index]
    cache_lock = quotient.cache_locks[bucket_index]
    cached = lock(cache_lock) do
        get(bucket, key, nothing)
    end
    isnothing(cached) || return cached
    representatives = MomentKey[]
    for permutation in SPIN_AXIS_PERMUTATIONS
        sign, transformed = spin_moment(key, permutation)
        sign == 1 ||
            error("V4-invariant spatial moment acquired a spin sign")
        push!(
            representatives,
            spatial_representative(
                quotient.spatial_quotient,
                transformed,
            ),
        )
    end
    representative = minimum(representatives)
    return lock(cache_lock) do
        get!(bucket, key, representative)
    end
end

function spin_spatial_polynomial_action(
    polynomial::ExactLinearPolynomial,
    action::Dict{MomentKey,MomentKey},
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(action, key) ||
            error("polynomial moment is outside the spin-spatial action")
        add_term!(result, action[key], coefficient)
    end
    return result
end

function spin_spatial_quotient_projection(
    polynomial::ExactLinearPolynomial,
    quotient::ShastrySpinSpatialMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        add_term!(
            result,
            spin_spatial_representative(quotient, key),
            coefficient,
        )
    end
    return result
end

struct ShastryFullStateSpinSpatialReducedPrimalAssembly{A,T}
    schema::String
    source::A
    quotient::ShastrySpinSpatialMomentQuotient
    truth::T
    positive_blocks::Vector{ShastrySpatialPSDBlock}
    gap_blocks::Vector{ShastrySpatialPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function shastry_spin_spatial_block_entry(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
    block::ShastrySpatialPSDBlock,
    left,
    right,
)
    polynomial = shastry_spatial_block_entry(
        assembly.source,
        block,
        left,
        right,
    )
    return spin_spatial_quotient_projection(
        polynomial,
        assembly.quotient,
    )
end

function shastry_spin_spatial_reduction_truth(
    source::ShastryFullStateSpatialReducedPrimalAssembly;
    verify_source_covariance::Bool=true,
    quotient::Union{Nothing,ShastrySpinSpatialMomentQuotient}=nothing,
)
    source_truth = verify_source_covariance ?
        full_state_spin_permutation_truth(source.source.source) :
        nothing
    selected_quotient = isnothing(quotient) ?
        build_spin_spatial_moment_quotient(source) :
        quotient
    transformed_equalities = ExactLinearPolynomial[
        spin_spatial_polynomial_action(equality, action)
        for action in selected_quotient.actions
        for equality in source.equalities
    ]
    equality_invariant =
        polynomial_row_rank(source.equalities) ==
        polynomial_row_rank([source.equalities; transformed_equalities])
    source_exact =
        !verify_source_covariance || something(source_truth).exact
    return (
        exact=source_exact && equality_invariant,
        source_covariance_exact=source_exact,
        source_truth=source_truth,
        equality_space_invariant=equality_invariant,
        source_moments=length(source.moments),
        quotient_moments=length(selected_quotient.moments),
        eliminated_moments=
            length(source.moments) - length(selected_quotient.moments),
    )
end

function add_polynomial_moments!(
    moments::Set{MomentKey},
    polynomial::ExactLinearPolynomial,
)
    union!(moments, keys(polynomial.terms))
    return moments
end

function fingerprint_records(schema::String, records)
    io = IOBuffer()
    serialized_schema = string(schema)
    write(io, string(ncodeunits(serialized_schema)), ":", serialized_schema)
    for record in records
        serialized = string(record)
        write(io, string(ncodeunits(serialized)), ":", serialized)
    end
    return bytes2hex(sha256(take!(io)))
end

function block_label(block::ShastrySpatialPSDBlock)
    source = block.source_block
    return join(
        (
            source.role,
            source.family,
            Int(source.character.rx),
            Int(source.character.ry),
            block.parity,
        ),
        "/",
    )
end

function assemble_shastry_full_state_spin_spatial_reduced_primal(
    source::ShastryFullStateSpatialReducedPrimalAssembly;
    verify_truth::Bool=true,
    verify_source_covariance::Bool=true,
    materialize_coefficients::Bool=true,
)
    quotient = build_spin_spatial_moment_quotient(
        source;
        materialize=materialize_coefficients || verify_truth,
    )
    truth = verify_truth ?
        shastry_spin_spatial_reduction_truth(
            source;
            verify_source_covariance=verify_source_covariance,
            quotient=quotient,
        ) :
        nothing
    verify_truth && !something(truth).exact &&
        error("Shastry full-state spin-spatial truth gate failed")
    equalities = canonical_real_equalities(ExactLinearPolynomial[
        spin_spatial_quotient_projection(polynomial, quotient)
        for polynomial in source.equalities
    ])
    if !materialize_coefficients
        ordered = quotient.moments
        coefficient_sha256 = "deferred-structural-v1"
        final_sha256 = fingerprint_records(
            SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA,
            [
                "source=" * source.assembly_sha256,
                "coefficient_map=" * coefficient_sha256,
                "moments=" * fingerprint_records(
                    "shastry-full-state-spin-spatial-moments-v1",
                    (key.canonical for key in ordered),
                ),
                "equalities=" * fingerprint_records(
                    "shastry-full-state-spin-spatial-equalities-v1",
                    (
                        canonical_polynomial_string(polynomial)
                        for polynomial in equalities
                    ),
                ),
            ],
        )
        return ShastryFullStateSpinSpatialReducedPrimalAssembly(
            SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA,
            source,
            quotient,
            truth,
            source.positive_blocks,
            source.gap_blocks,
            equalities,
            ordered,
            coefficient_sha256,
            final_sha256,
        )
    end

    provisional = ShastryFullStateSpinSpatialReducedPrimalAssembly(
        SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA,
        source,
        quotient,
        truth,
        source.positive_blocks,
        source.gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )
    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for block in [source.positive_blocks; source.gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = shastry_spin_spatial_block_entry(
                provisional,
                block,
                block.rows[row],
                block.rows[column],
            )
            add_polynomial_moments!(moments, polynomial)
            push!(
                coefficient_records,
                string(
                    block_label(block),
                    "[",
                    row,
                    ",",
                    column,
                    "]=",
                    polynomial_sha256(polynomial),
                ),
            )
        end
    end
    for equality in equalities
        add_polynomial_moments!(moments, equality)
    end
    ordered = sort!(
        collect(moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    ordered == quotient.moments ||
        error("spin-spatial coefficient maps do not reproduce quotient inventory")
    coefficient_sha256 = fingerprint_records(
        "shastry-full-state-spin-spatial-coefficients-v1",
        coefficient_records,
    )
    final_sha256 = fingerprint_records(
        SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "coefficient_map=" * coefficient_sha256,
            "moments=" * fingerprint_records(
                "shastry-full-state-spin-spatial-moments-v1",
                (key.canonical for key in ordered),
            ),
            "equalities=" * fingerprint_records(
                "shastry-full-state-spin-spatial-equalities-v1",
                (
                    canonical_polynomial_string(polynomial)
                    for polynomial in equalities
                ),
            ),
        ],
    )
    return ShastryFullStateSpinSpatialReducedPrimalAssembly(
        SHASTRY_FULL_STATE_SPIN_SPATIAL_REDUCTION_SCHEMA,
        source,
        quotient,
        truth,
        source.positive_blocks,
        source.gap_blocks,
        equalities,
        ordered,
        coefficient_sha256,
        final_sha256,
    )
end

function shastry_full_state_spin_spatial_reduced_assembly_report(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
)
    positive_dimensions =
        length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_moments=length(assembly.source.moments),
        spin_spatial_moments=length(assembly.moments),
        eliminated_spin_moments=
            length(assembly.source.moments) - length(assembly.moments),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        psd_triangle_entries=sum(
            dimension * (dimension + 1) ÷ 2
            for dimension in all_dimensions
        ),
        maximum_side=maximum(all_dimensions),
    )
end

end
