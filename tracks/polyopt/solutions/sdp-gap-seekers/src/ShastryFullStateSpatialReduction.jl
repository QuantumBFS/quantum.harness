module ShastryFullStateSpatialReduction

using SHA
using ..SquareJ1J2Prototype:
    Site,
    PauliWord
using ..GenericGapModel:
    StateMonomial,
    state_monomial_string
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    add_term!,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256
using ..ExactSymmetryReduction:
    canonical_real_equalities
using ..ConjugationSymmetryReduction:
    polynomial_row_rank
using ..FullStateSymmetryReduction:
    FullStateReducedRow,
    FullStatePSDBlock,
    FullStateRealReducedPrimalAssembly,
    full_state_real_block_entry

export SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
       ShastrySpatialMomentQuotient,
       ShastrySpatialCombinationRow,
       ShastrySpatialPSDBlock,
       ShastryFullStateSpatialReducedPrimalAssembly,
       shastry_spatial_word,
       shastry_spatial_state_monomial,
       shastry_spatial_reduction_truth,
       shastry_spatial_block_entry,
       assemble_shastry_full_state_spatial_reduced_primal,
       shastry_full_state_spatial_reduced_assembly_report

const SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA =
    "shastry-sutherland-full-state-v4-conjugation-spatial-reflection-v1"

source_primal(assembly::FullStateRealReducedPrimalAssembly) =
    assembly.source.source

shastry_spatial_site(site::Site) = Site(-site.y, -site.x)

function require_shastry_d2(
    assembly::FullStateRealReducedPrimalAssembly,
)
    primal = source_primal(assembly)
    primal.problem.model.name == "shastry-sutherland" ||
        throw(ArgumentError("spatial reducer is restricted to Shastry-Sutherland"))
    primal.problem.d == 2 ||
        throw(ArgumentError("spatial reducer is restricted to d=2"))
    return primal
end

function shastry_spatial_site_map(
    assembly::FullStateRealReducedPrimalAssembly,
)
    patch = require_shastry_d2(assembly).problem.patch
    site_map = Int[]
    for site in patch.sites
        reflected = shastry_spatial_site(site)
        haskey(patch.site_to_id, reflected) ||
            error("anti-diagonal reflection leaves the square window")
        push!(site_map, patch.site_to_id[reflected])
    end
    all(site_map[site_map[index]] == index for index in eachindex(site_map)) ||
        error("Shastry spatial site map is not an involution")
    return site_map
end

function shastry_spatial_word(
    word::PauliWord,
    site_map::Vector{Int},
)
    transformed = [
        (site_map[site], axis)
        for (site, axis) in word.ops
    ]
    sort!(transformed; by=first)
    return PauliWord(transformed)
end

function shastry_spatial_state_monomial(
    row::StateMonomial,
    site_map::Vector{Int},
)
    return StateMonomial(
        shastry_spatial_word.(row.state_symbols, Ref(site_map)),
        shastry_spatial_word(row.operator_word, site_map),
    )
end

function shastry_spatial_row(
    row::FullStateReducedRow,
    site_map::Vector{Int},
)
    return FullStateReducedRow(
        row.family,
        shastry_spatial_state_monomial(row.source, site_map),
    )
end

const AXIS_CODE = Dict('X' => UInt8(1), 'Y' => UInt8(2), 'Z' => UInt8(3))

function parse_moment_word(serialized::AbstractString)
    isempty(serialized) &&
        throw(ArgumentError("state-symbol word cannot be empty"))
    operations = Tuple{Int,UInt8}[]
    for factor in split(serialized, ';')
        matched = match(r"^([0-9]+)([XYZ])$", factor)
        isnothing(matched) &&
            error("malformed canonical moment factor: $factor")
        site_text, axis_text = something(matched).captures
        push!(
            operations,
            (
                parse(Int, site_text),
                AXIS_CODE[only(axis_text)],
            ),
        )
    end
    return PauliWord(operations)
end

function shastry_spatial_moment(
    key::MomentKey,
    site_map::Vector{Int},
)
    isempty(key.canonical) && return moment_key()
    words = PauliWord[
        shastry_spatial_word(
            parse_moment_word(serialized),
            site_map,
        )
        for serialized in split(key.canonical, '|')
    ]
    reflected = moment_key(words)
    moment_degree(reflected) == moment_degree(key) ||
        error("Shastry spatial reflection changed moment degree")
    return reflected
end

struct ShastrySpatialMomentQuotient
    action::Dict{MomentKey,MomentKey}
    representatives::Dict{MomentKey,MomentKey}
    moments::Vector{MomentKey}
end

function build_spatial_moment_quotient(
    assembly::FullStateRealReducedPrimalAssembly,
    site_map::Vector{Int},
)
    moments = assembly.moments
    inventory = Set(moments)
    action = Dict{MomentKey,MomentKey}()
    for key in moments
        target = shastry_spatial_moment(key, site_map)
        target in inventory ||
            error("full-state moment inventory is not spatially closed")
        action[key] = target
    end
    all(action[action[key]] == key for key in moments) ||
        error("Shastry spatial moment action is not an involution")

    representatives = Dict{MomentKey,MomentKey}()
    representative_set = Set{MomentKey}()
    for key in moments
        target = action[key]
        representative = isless(target, key) ? target : key
        representatives[key] = representative
        push!(representative_set, representative)
    end
    ordered = sort!(
        collect(representative_set);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(ordered) == moment_key() ||
        error("identity moment is not first after spatial quotient")
    return ShastrySpatialMomentQuotient(
        action,
        representatives,
        ordered,
    )
end

function spatial_polynomial_action(
    polynomial::ExactLinearPolynomial,
    quotient::ShastrySpatialMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(quotient.action, key) ||
            error("polynomial moment is outside the spatial action")
        add_term!(result, quotient.action[key], coefficient)
    end
    return result
end

function spatial_quotient_projection(
    polynomial::ExactLinearPolynomial,
    quotient::ShastrySpatialMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(quotient.representatives, key) ||
            error("polynomial moment is outside the spatial quotient")
        add_term!(
            result,
            quotient.representatives[key],
            coefficient,
        )
    end
    return result
end

struct ShastrySpatialCombinationRow
    source_indices::Vector{Int}
    coefficients::Vector{Int}

    function ShastrySpatialCombinationRow(
        source_indices::Vector{Int},
        coefficients::Vector{Int},
    )
        length(source_indices) == length(coefficients) ||
            throw(ArgumentError("combination indices and coefficients differ"))
        isempty(source_indices) &&
            throw(ArgumentError("spatial combination row cannot be empty"))
        length(unique(source_indices)) == length(source_indices) ||
            throw(ArgumentError("spatial combination repeats a source row"))
        all(!iszero, coefficients) ||
            throw(ArgumentError("spatial combination contains a zero coefficient"))
        new(copy(source_indices), copy(coefficients))
    end
end

struct ShastrySpatialPSDBlock
    source_block::FullStatePSDBlock
    parity::Symbol
    rows::Vector{ShastrySpatialCombinationRow}

    function ShastrySpatialPSDBlock(
        source_block::FullStatePSDBlock,
        parity::Symbol,
        rows::Vector{ShastrySpatialCombinationRow},
    )
        parity in (:plus, :minus) ||
            throw(ArgumentError("spatial block parity must be plus or minus"))
        isempty(rows) &&
            throw(ArgumentError("empty spatial blocks must be omitted"))
        all(
            row -> all(index -> 1 <= index <= length(source_block.rows), row.source_indices),
            rows,
        ) || throw(ArgumentError("spatial row index leaves its source block"))
        new(source_block, parity, rows)
    end
end

struct ShastryFullStateSpatialReducedPrimalAssembly{A}
    schema::String
    source::A
    quotient::ShastrySpatialMomentQuotient
    positive_blocks::Vector{ShastrySpatialPSDBlock}
    gap_blocks::Vector{ShastrySpatialPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function spatial_row_action(
    block::FullStatePSDBlock,
    site_map::Vector{Int},
)
    indices = Dict(
        row => index
        for (index, row) in enumerate(block.rows)
    )
    action = Int[]
    for row in block.rows
        target = shastry_spatial_row(row, site_map)
        haskey(indices, target) ||
            error("full-state PSD row inventory is not spatially closed")
        push!(action, indices[target])
    end
    all(action[action[index]] == index for index in eachindex(action)) ||
        error("spatial PSD-row action is not an involution")
    return action
end

function split_spatial_block(
    block::FullStatePSDBlock,
    site_map::Vector{Int},
)
    action = spatial_row_action(block, site_map)
    visited = falses(length(action))
    plus_rows = ShastrySpatialCombinationRow[]
    minus_rows = ShastrySpatialCombinationRow[]
    for index in eachindex(action)
        visited[index] && continue
        target = action[index]
        visited[index] = true
        visited[target] = true
        if target == index
            push!(
                plus_rows,
                ShastrySpatialCombinationRow([index], [1]),
            )
        else
            first_index, second_index = minmax(index, target)
            push!(
                plus_rows,
                ShastrySpatialCombinationRow(
                    [first_index, second_index],
                    [1, 1],
                ),
            )
            push!(
                minus_rows,
                ShastrySpatialCombinationRow(
                    [first_index, second_index],
                    [1, -1],
                ),
            )
        end
    end
    blocks = ShastrySpatialPSDBlock[]
    isempty(plus_rows) ||
        push!(blocks, ShastrySpatialPSDBlock(block, :plus, plus_rows))
    isempty(minus_rows) ||
        push!(blocks, ShastrySpatialPSDBlock(block, :minus, minus_rows))
    return blocks
end

function shastry_spatial_block_entry(
    assembly::ShastryFullStateSpatialReducedPrimalAssembly,
    block::ShastrySpatialPSDBlock,
    left::ShastrySpatialCombinationRow,
    right::ShastrySpatialCombinationRow,
)
    polynomial = ExactLinearPolynomial()
    for (left_index, left_coefficient) in
        zip(left.source_indices, left.coefficients)
        for (right_index, right_coefficient) in
            zip(right.source_indices, right.coefficients)
            base = full_state_real_block_entry(
                assembly.source,
                block.source_block,
                block.source_block.rows[left_index],
                block.source_block.rows[right_index],
            )
            for (key, coefficient) in base.terms
                add_term!(
                    polynomial,
                    key,
                    left_coefficient * right_coefficient * coefficient,
                )
            end
        end
    end
    return spatial_quotient_projection(polynomial, assembly.quotient)
end

function hamiltonian_reflection_invariant(
    assembly::FullStateRealReducedPrimalAssembly,
    site_map::Vector{Int},
)
    terms = source_primal(assembly).hamiltonian_terms
    original = Dict{PauliWord,Any}()
    reflected = Dict{PauliWord,Any}()
    for term in terms
        original[term.word] =
            get(original, term.word, zero(term.coefficient)) +
            term.coefficient
        target = shastry_spatial_word(term.word, site_map)
        reflected[target] =
            get(reflected, target, zero(term.coefficient)) +
            term.coefficient
    end
    return original == reflected
end

function equality_space_spatially_invariant(
    equalities::Vector{ExactLinearPolynomial},
    quotient::ShastrySpatialMomentQuotient,
)
    transformed = ExactLinearPolynomial[
        spatial_polynomial_action(polynomial, quotient)
        for polynomial in equalities
    ]
    return polynomial_row_rank(equalities) ==
           polynomial_row_rank([equalities; transformed])
end

function shastry_spatial_reduction_truth(
    source::FullStateRealReducedPrimalAssembly,
)
    site_map = shastry_spatial_site_map(source)
    quotient = build_spatial_moment_quotient(source, site_map)
    hamiltonian_invariant =
        hamiltonian_reflection_invariant(source, site_map)
    equality_invariant =
        equality_space_spatially_invariant(source.equalities, quotient)
    row_actions_close = true
    coefficient_covariant = true
    coefficient_count = 0
    split_cross_zero = true
    split_cross_count = 0

    for source_block in [source.positive_blocks; source.gap_blocks]
        action = spatial_row_action(source_block, site_map)
        row_actions_close &= all(
            action[action[index]] == index
            for index in eachindex(action)
        )
        for row in eachindex(source_block.rows)
            for column in row:length(source_block.rows)
                polynomial = full_state_real_block_entry(
                    source,
                    source_block,
                    source_block.rows[row],
                    source_block.rows[column],
                )
                transformed = spatial_polynomial_action(
                    polynomial,
                    quotient,
                )
                target_row = action[row]
                target_column = action[column]
                expected = full_state_real_block_entry(
                    source,
                    source_block,
                    source_block.rows[target_row],
                    source_block.rows[target_column],
                )
                coefficient_covariant &= transformed == expected
                coefficient_count += 1
            end
        end

        split_blocks = split_spatial_block(source_block, site_map)
        plus = findfirst(block -> block.parity == :plus, split_blocks)
        minus = findfirst(block -> block.parity == :minus, split_blocks)
        if !isnothing(plus) && !isnothing(minus)
            provisional = ShastryFullStateSpatialReducedPrimalAssembly(
                SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
                source,
                quotient,
                ShastrySpatialPSDBlock[],
                ShastrySpatialPSDBlock[],
                ExactLinearPolynomial[],
                MomentKey[],
                "",
                "",
            )
            plus_block = split_blocks[something(plus)]
            minus_block = split_blocks[something(minus)]
            for left in plus_block.rows, right in minus_block.rows
                cross = shastry_spatial_block_entry(
                    provisional,
                    plus_block,
                    left,
                    right,
                )
                split_cross_zero &= iszero(cross)
                split_cross_count += 1
            end
        end
    end
    return (
        exact=hamiltonian_invariant &&
              equality_invariant &&
              row_actions_close &&
              coefficient_covariant &&
              split_cross_zero,
        hamiltonian_invariant=hamiltonian_invariant,
        equality_space_invariant=equality_invariant,
        row_actions_close=row_actions_close,
        coefficient_covariant=coefficient_covariant,
        coefficient_count=coefficient_count,
        split_cross_zero=split_cross_zero,
        split_cross_count=split_cross_count,
        source_moments=length(source.moments),
        quotient_moments=length(quotient.moments),
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
    write(
        io,
        string(ncodeunits(serialized_schema)),
        ":",
        serialized_schema,
    )
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

function assemble_shastry_full_state_spatial_reduced_primal(
    source::FullStateRealReducedPrimalAssembly;
    verify_truth::Bool=true,
    materialize_coefficients::Bool=true,
)
    truth = verify_truth ? shastry_spatial_reduction_truth(source) : nothing
    verify_truth && !something(truth).exact &&
        error("Shastry full-state spatial truth gate failed")
    site_map = shastry_spatial_site_map(source)
    quotient = build_spatial_moment_quotient(source, site_map)

    positive_blocks = ShastrySpatialPSDBlock[]
    for block in source.positive_blocks
        append!(positive_blocks, split_spatial_block(block, site_map))
    end
    gap_blocks = ShastrySpatialPSDBlock[]
    for block in source.gap_blocks
        append!(gap_blocks, split_spatial_block(block, site_map))
    end
    equalities = canonical_real_equalities(ExactLinearPolynomial[
        spatial_quotient_projection(polynomial, quotient)
        for polynomial in source.equalities
    ])

    if !materialize_coefficients
        ordered = quotient.moments
        coefficient_sha256 = "deferred-structural-v1"
        final_sha256 = fingerprint_records(
            SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
            [
                "source=" * source.assembly_sha256,
                "coefficient_map=" * coefficient_sha256,
                (
                    "moments=" *
                    fingerprint_records(
                        "shastry-full-state-spatial-moments-v1",
                        (key.canonical for key in ordered),
                    )
                ),
                (
                    "equalities=" *
                    fingerprint_records(
                        "shastry-full-state-spatial-equalities-v1",
                        (
                            canonical_polynomial_string(polynomial)
                            for polynomial in equalities
                        ),
                    )
                ),
            ],
        )
        return ShastryFullStateSpatialReducedPrimalAssembly(
            SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
            source,
            quotient,
            positive_blocks,
            gap_blocks,
            equalities,
            ordered,
            coefficient_sha256,
            final_sha256,
        )
    end

    provisional = ShastryFullStateSpatialReducedPrimalAssembly(
        SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
        source,
        quotient,
        positive_blocks,
        gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )
    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for block in [positive_blocks; gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = shastry_spatial_block_entry(
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
        error("spatial coefficient maps do not reproduce quotient inventory")
    coefficient_sha256 = fingerprint_records(
        "shastry-full-state-spatial-coefficients-v1",
        coefficient_records,
    )
    final_sha256 = fingerprint_records(
        SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "coefficient_map=" * coefficient_sha256,
            (
                "moments=" *
                fingerprint_records(
                    "shastry-full-state-spatial-moments-v1",
                    (key.canonical for key in ordered),
                )
            ),
            (
                "equalities=" *
                fingerprint_records(
                    "shastry-full-state-spatial-equalities-v1",
                    (
                        canonical_polynomial_string(polynomial)
                        for polynomial in equalities
                    ),
                )
            ),
        ],
    )
    return ShastryFullStateSpatialReducedPrimalAssembly(
        SHASTRY_FULL_STATE_SPATIAL_REDUCTION_SCHEMA,
        source,
        quotient,
        positive_blocks,
        gap_blocks,
        equalities,
        ordered,
        coefficient_sha256,
        final_sha256,
    )
end

function shastry_full_state_spatial_reduced_assembly_report(
    assembly::ShastryFullStateSpatialReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(
        assembly.positive_blocks,
        :rows,
    ))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_moments=length(assembly.source.moments),
        spatial_moments=length(assembly.moments),
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
