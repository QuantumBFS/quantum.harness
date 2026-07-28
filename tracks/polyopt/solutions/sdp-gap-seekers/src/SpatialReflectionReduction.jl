module SpatialReflectionReduction

using SHA
using ..SquareJ1J2Prototype:
    Site,
    PauliWord
using ..PrimalGapSymbolics:
    ExactRational,
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
using ..FullSpinIsotypicReduction:
    FullSpinIsotypicCombinationRow,
    FullSpinIsotypicPSDBlock,
    FullSpinIsotypicReducedPrimalAssembly,
    full_spin_isotypic_block_entry

export SPATIAL_REFLECTION_REDUCTION_SCHEMA,
       SpatialReflectionMomentQuotient,
       SpatialReflectionCombinationRow,
       SpatialReflectionPSDBlock,
       SpatialReflectionReducedPrimalAssembly,
       spatial_reflection_word,
       spatial_reflection_polynomial_action,
       spatial_reflection_quotient_projection,
       spatial_reflection_reduction_truth,
       spatial_reflection_block_entry,
       assemble_spatial_reflection_reduced_primal,
       spatial_reflection_reduced_assembly_report

const SPATIAL_REFLECTION_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-spatial-reflection-v1"

source_primal(assembly::FullSpinIsotypicReducedPrimalAssembly) =
    assembly.source.source.source.source.source.source

spatial_reflection(site::Site) = Site(-site.y, -site.x)

function spatial_reflection_site_map(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
)
    patch = source_primal(assembly).problem.patch
    site_map = Int[]
    for site in patch.sites
        reflected = spatial_reflection(site)
        haskey(patch.site_to_id, reflected) ||
            error("anti-diagonal reflection leaves the local window")
        push!(site_map, patch.site_to_id[reflected])
    end
    all(site_map[site_map[index]] == index for index in eachindex(site_map)) ||
        error("spatial site map is not an involution")
    return site_map
end

function spatial_reflection_word(
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

function spatial_reflection_moment(
    key::MomentKey,
    site_map::Vector{Int},
)
    isempty(key.canonical) && return moment_key()
    words = PauliWord[
        spatial_reflection_word(
            parse_moment_word(serialized),
            site_map,
        )
        for serialized in split(key.canonical, '|')
    ]
    reflected = moment_key(words)
    moment_degree(reflected) == moment_degree(key) ||
        error("spatial reflection changed moment degree")
    return reflected
end

"""Unsigned order-two quotient of the full-spin isotypic moment inventory."""
struct SpatialReflectionMomentQuotient
    action::Dict{MomentKey,MomentKey}
    representatives::Dict{MomentKey,MomentKey}
    moments::Vector{MomentKey}
end

function build_spatial_reflection_moment_quotient(
    moments::Vector{MomentKey},
    site_map::Vector{Int},
)
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("source moment inventory contains duplicates"))
    inventory = Set(moments)
    action = Dict{MomentKey,MomentKey}()
    for key in moments
        target = spatial_reflection_moment(key, site_map)
        target in inventory ||
            error("moment inventory is not closed under spatial reflection")
        action[key] = target
    end
    all(action[action[key]] == key for key in moments) ||
        error("spatial moment action is not an involution")

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
    return SpatialReflectionMomentQuotient(
        action,
        representatives,
        ordered,
    )
end

function spatial_reflection_polynomial_action(
    polynomial::ExactLinearPolynomial,
    quotient::SpatialReflectionMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(quotient.action, key) ||
            error("polynomial moment is outside the spatial action")
        add_term!(result, quotient.action[key], coefficient)
    end
    return result
end

function spatial_reflection_quotient_projection(
    polynomial::ExactLinearPolynomial,
    quotient::SpatialReflectionMomentQuotient,
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

function combination_signature(
    source_indices::Vector{Int},
    coefficients::Vector{Int},
)
    entries = Dict{Int,Int}()
    for (source_index, coefficient) in zip(source_indices, coefficients)
        updated = get(entries, source_index, 0) + coefficient
        if iszero(updated)
            delete!(entries, source_index)
        else
            entries[source_index] = updated
        end
    end
    return Tuple(sort!(collect(entries); by=first))
end

combination_signature(row::FullSpinIsotypicCombinationRow) =
    combination_signature(row.source_indices, row.coefficients)

function reflected_combination_signature(
    block::FullSpinIsotypicPSDBlock,
    row::FullSpinIsotypicCombinationRow,
    site_map::Vector{Int},
)
    source_indices = Dict(
        source_row.word => index
        for (index, source_row) in enumerate(block.source_block.rows)
    )
    transformed_indices = Int[]
    for source_index in row.source_indices
        target_word = spatial_reflection_word(
            block.source_block.rows[source_index].word,
            site_map,
        )
        haskey(source_indices, target_word) ||
            error("source row inventory is not spatially closed")
        push!(transformed_indices, source_indices[target_word])
    end
    return combination_signature(
        transformed_indices,
        row.coefficients,
    )
end

function spatial_row_action(
    block::FullSpinIsotypicPSDBlock,
    site_map::Vector{Int},
)
    signatures = Dict(
        combination_signature(row) => index
        for (index, row) in enumerate(block.rows)
    )
    length(signatures) == length(block.rows) ||
        error("isotypic block contains duplicate combination rows")
    indices = Int[]
    signs = Int[]
    for row in block.rows
        target = reflected_combination_signature(block, row, site_map)
        if haskey(signatures, target)
            push!(indices, signatures[target])
            push!(signs, 1)
            continue
        end
        negative = Tuple(
            source_index => -coefficient
            for (source_index, coefficient) in target
        )
        haskey(signatures, negative) ||
            error("isotypic block is not closed under spatial reflection")
        push!(indices, signatures[negative])
        push!(signs, -1)
    end
    for index in eachindex(indices)
        target = indices[index]
        indices[target] == index &&
            signs[index] * signs[target] == 1 ||
            error("spatial row action is not an involution")
    end
    return signs, indices
end

"""One row in a spatial-reflection eigenspace basis."""
struct SpatialReflectionCombinationRow
    source_indices::Vector{Int}
    coefficients::Vector{Int}

    function SpatialReflectionCombinationRow(
        source_indices::Vector{Int},
        coefficients::Vector{Int},
    )
        length(source_indices) == length(coefficients) ||
            throw(ArgumentError("spatial row index/coefficient mismatch"))
        length(source_indices) in (1, 2) ||
            throw(ArgumentError("spatial rows contain one or two terms"))
        length(unique(source_indices)) == length(source_indices) ||
            throw(ArgumentError("spatial row repeats a source index"))
        all(coefficient -> coefficient in (-1, 1), coefficients) ||
            throw(ArgumentError("spatial row coefficients must be ±1"))
        new(source_indices, coefficients)
    end
end

struct SpatialReflectionPSDBlock
    source_block::FullSpinIsotypicPSDBlock
    kind::Symbol
    rows::Vector{SpatialReflectionCombinationRow}

    function SpatialReflectionPSDBlock(
        source_block::FullSpinIsotypicPSDBlock,
        kind::Symbol,
        rows::Vector{SpatialReflectionCombinationRow},
    )
        kind in (:spatial_plus, :spatial_minus) ||
            throw(ArgumentError("unsupported spatial block kind"))
        isempty(rows) &&
            throw(ArgumentError("empty spatial PSD blocks must be omitted"))
        all(
            row -> all(
                index -> 1 <= index <= length(source_block.rows),
                row.source_indices,
            ),
            rows,
        ) || throw(ArgumentError("spatial row index is out of range"))
        new(source_block, kind, rows)
    end
end

function spatial_eigenspace_blocks(
    block::FullSpinIsotypicPSDBlock,
    site_map::Vector{Int},
)
    signs, permutation = spatial_row_action(block, site_map)
    visited = falses(length(block.rows))
    plus = SpatialReflectionCombinationRow[]
    minus = SpatialReflectionCombinationRow[]
    for index in eachindex(block.rows)
        visited[index] && continue
        target = permutation[index]
        if target == index
            destination = signs[index] == 1 ? plus : minus
            push!(
                destination,
                SpatialReflectionCombinationRow([index], [1]),
            )
            visited[index] = true
            continue
        end
        visited[target] &&
            error("spatial row orbit was visited before its representative")
        sign = signs[index]
        push!(
            plus,
            SpatialReflectionCombinationRow([index, target], [1, sign]),
        )
        push!(
            minus,
            SpatialReflectionCombinationRow([index, target], [1, -sign]),
        )
        visited[index] = true
        visited[target] = true
    end
    result = SpatialReflectionPSDBlock[]
    isempty(plus) || push!(
        result,
        SpatialReflectionPSDBlock(block, :spatial_plus, plus),
    )
    isempty(minus) || push!(
        result,
        SpatialReflectionPSDBlock(block, :spatial_minus, minus),
    )
    return result
end

function combined_spatial_block_entry(
    source::FullSpinIsotypicReducedPrimalAssembly,
    quotient::SpatialReflectionMomentQuotient,
    block::SpatialReflectionPSDBlock,
    left::SpatialReflectionCombinationRow,
    right::SpatialReflectionCombinationRow,
)
    polynomial = ExactLinearPolynomial()
    for (left_position, left_index) in enumerate(left.source_indices)
        for (right_position, right_index) in enumerate(right.source_indices)
            entry = full_spin_isotypic_block_entry(
                source,
                block.source_block,
                block.source_block.rows[left_index],
                block.source_block.rows[right_index],
            )
            scale =
                left.coefficients[left_position] *
                right.coefficients[right_position]
            for (key, coefficient) in entry.terms
                add_term!(polynomial, key, scale * coefficient)
            end
        end
    end
    projected = spatial_reflection_quotient_projection(
        polynomial,
        quotient,
    )
    all(iszero ∘ imag, values(projected.terms)) ||
        error("spatial block entry is not exactly real")
    return projected
end

function hamiltonian_is_invariant(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    site_map::Vector{Int},
)
    original = Dict{PauliWord,Any}()
    reflected = Dict{PauliWord,Any}()
    for term in source_primal(assembly).hamiltonian_terms
        original[term.word] =
            get(original, term.word, zero(term.coefficient)) +
            term.coefficient
        target = spatial_reflection_word(term.word, site_map)
        reflected[target] =
            get(reflected, target, zero(term.coefficient)) +
            term.coefficient
    end
    return original == reflected
end

function coefficient_covariance(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    quotient::SpatialReflectionMomentQuotient,
    site_map::Vector{Int},
)
    exact = true
    count = 0
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        signs, indices = spatial_row_action(block, site_map)
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = full_spin_isotypic_block_entry(
                assembly,
                block,
                block.rows[row],
                block.rows[column],
            )
            target = full_spin_isotypic_block_entry(
                assembly,
                block,
                block.rows[indices[row]],
                block.rows[indices[column]],
            )
            exact &=
                spatial_reflection_polynomial_action(
                    polynomial,
                    quotient,
                ) == signs[row] * signs[column] * target
            count += 1
        end
    end
    return exact, count
end

function equality_space_is_invariant(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    quotient::SpatialReflectionMomentQuotient,
)
    transformed = ExactLinearPolynomial[
        spatial_reflection_polynomial_action(equality, quotient)
        for equality in assembly.equalities
    ]
    return polynomial_row_rank(assembly.equalities) ==
           polynomial_row_rank([assembly.equalities; transformed])
end

function split_basis_rank(blocks::Vector{SpatialReflectionPSDBlock})
    isempty(blocks) && return 0
    dimension = length(first(blocks).source_block.rows)
    rows = reduce(vcat, getfield.(blocks, :rows))
    matrix = zeros(ExactRational, length(rows), dimension)
    for (row_index, row) in enumerate(rows)
        for (source_index, coefficient) in
            zip(row.source_indices, row.coefficients)
            matrix[row_index, source_index] = coefficient
        end
    end
    reduced = copy(matrix)
    rank = 0
    for column in axes(reduced, 2)
        pivot = findfirst(
            row -> !iszero(reduced[row, column]),
            (rank + 1):size(reduced, 1),
        )
        isnothing(pivot) && continue
        pivot_row = rank + something(pivot)
        rank += 1
        if pivot_row != rank
            reduced[rank, :], reduced[pivot_row, :] =
                copy(reduced[pivot_row, :]), copy(reduced[rank, :])
        end
        pivot_value = reduced[rank, column]
        reduced[rank, :] ./= pivot_value
        for row in axes(reduced, 1)
            row == rank && continue
            scale = reduced[row, column]
            iszero(scale) && continue
            reduced[row, :] .-= scale .* reduced[rank, :]
        end
    end
    return rank
end

function spatial_cross_blocks_zero(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    quotient::SpatialReflectionMomentQuotient,
    site_map::Vector{Int},
)
    exact = true
    count = 0
    basis_invertible = true
    basis_dimensions = Int[]
    positive_dimensions = Int[]
    gap_dimensions = Int[]
    for source_block in [assembly.positive_blocks; assembly.gap_blocks]
        blocks = spatial_eigenspace_blocks(source_block, site_map)
        rank = split_basis_rank(blocks)
        push!(basis_dimensions, rank)
        basis_invertible &= rank == length(source_block.rows)
        dimensions = length.(getfield.(blocks, :rows))
        destination = source_block.source_block.role == :positive ?
            positive_dimensions :
            gap_dimensions
        append!(destination, dimensions)
        plus = findfirst(block -> block.kind == :spatial_plus, blocks)
        minus = findfirst(block -> block.kind == :spatial_minus, blocks)
        if isnothing(plus) || isnothing(minus)
            continue
        end
        plus_block = blocks[something(plus)]
        minus_block = blocks[something(minus)]
        for left in plus_block.rows, right in minus_block.rows
            exact &= iszero(combined_spatial_block_entry(
                assembly,
                quotient,
                plus_block,
                left,
                right,
            ))
            count += 1
        end
    end
    return (
        exact=exact,
        entry_count=count,
        bases_invertible=basis_invertible,
        basis_dimensions=basis_dimensions,
        positive_dimensions=positive_dimensions,
        gap_dimensions=gap_dimensions,
    )
end

"""
Exhaustive exact gate for the anti-diagonal spatial reflection.

The map `(x,y) -> (-y,-x)` is tested against the actual finite Hamiltonian
term multiset, moment inventory, every retained isotypic cone coefficient,
and the equality row space. Only after those checks are the stable cone rows
split into reflection eigenspaces.
"""
function spatial_reflection_reduction_truth(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
)
    site_map = spatial_reflection_site_map(assembly)
    quotient = build_spatial_reflection_moment_quotient(
        assembly.moments,
        site_map,
    )
    hamiltonian_invariant = hamiltonian_is_invariant(assembly, site_map)
    covariance_exact, coefficient_count =
        coefficient_covariance(assembly, quotient, site_map)
    equality_invariant =
        equality_space_is_invariant(assembly, quotient)
    split = spatial_cross_blocks_zero(
        assembly,
        quotient,
        site_map,
    )
    exact =
        hamiltonian_invariant &&
        covariance_exact &&
        equality_invariant &&
        split.exact &&
        split.bases_invertible
    return (
        exact=exact,
        site_map=site_map,
        site_map_involutive=all(
            site_map[site_map[index]] == index
            for index in eachindex(site_map)
        ),
        hamiltonian_invariant=hamiltonian_invariant,
        source_moment_count=length(assembly.moments),
        quotient_moment_count=length(quotient.moments),
        eliminated_moment_count=
            length(assembly.moments) - length(quotient.moments),
        coefficient_covariant=covariance_exact,
        coefficient_count=coefficient_count,
        equality_space_invariant=equality_invariant,
        stable_cross_blocks_zero=split.exact,
        stable_cross_entry_count=split.entry_count,
        stable_bases_invertible=split.bases_invertible,
        stable_basis_dimensions=split.basis_dimensions,
        positive_block_dimensions=split.positive_dimensions,
        gap_block_dimensions=split.gap_dimensions,
        quotient=quotient,
    )
end

struct SpatialReflectionReducedPrimalAssembly{A}
    schema::String
    source::A
    quotient::SpatialReflectionMomentQuotient
    positive_blocks::Vector{SpatialReflectionPSDBlock}
    gap_blocks::Vector{SpatialReflectionPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function spatial_reflection_block_entry(
    assembly::SpatialReflectionReducedPrimalAssembly,
    block::SpatialReflectionPSDBlock,
    left::SpatialReflectionCombinationRow,
    right::SpatialReflectionCombinationRow,
)
    return combined_spatial_block_entry(
        assembly.source,
        assembly.quotient,
        block,
        left,
        right,
    )
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

function source_block_label(block::SpatialReflectionPSDBlock)
    source = block.source_block
    v4 = source.source_block
    return join(
        (
            v4.role,
            v4.family,
            "rx" * string(Int(v4.character.rx)),
            "ry" * string(Int(v4.character.ry)),
            source.kind,
            block.kind,
        ),
        ":",
    )
end

function assemble_spatial_reflection_reduced_primal(
    source::FullSpinIsotypicReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ?
        spatial_reflection_reduction_truth(source) :
        nothing
    site_map = verify_truth ?
        something(truth).site_map :
        spatial_reflection_site_map(source)
    quotient = verify_truth ?
        something(truth).quotient :
        build_spatial_reflection_moment_quotient(source.moments, site_map)
    if verify_truth
        something(truth).exact ||
            error("spatial-reflection truth check failed")
    end

    positive_blocks = reduce(
        vcat,
        spatial_eigenspace_blocks(block, site_map)
        for block in source.positive_blocks;
        init=SpatialReflectionPSDBlock[],
    )
    gap_blocks = reduce(
        vcat,
        spatial_eigenspace_blocks(block, site_map)
        for block in source.gap_blocks;
        init=SpatialReflectionPSDBlock[],
    )
    equalities = canonical_real_equalities(ExactLinearPolynomial[
        spatial_reflection_quotient_projection(equality, quotient)
        for equality in source.equalities
    ])
    provisional = SpatialReflectionReducedPrimalAssembly(
        SPATIAL_REFLECTION_REDUCTION_SCHEMA,
        source,
        quotient,
        positive_blocks,
        gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )

    used_moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for block in [positive_blocks; gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = spatial_reflection_block_entry(
                provisional,
                block,
                block.rows[row],
                block.rows[column],
            )
            union!(used_moments, keys(polynomial.terms))
            push!(
                coefficient_records,
                join(
                    (
                        source_block_label(block),
                        row,
                        column,
                        polynomial_sha256(polynomial),
                    ),
                    ":",
                ),
            )
        end
    end
    for equality in equalities
        union!(used_moments, keys(equality.terms))
    end
    moments = sort!(
        collect(used_moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(moments) == moment_key() ||
        error("identity moment is not first after spatial reduction")

    coefficient_sha256 = fingerprint_records(
        "spatial-reflection-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "spatial-reflection-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    block_records = String[
        source_block_label(block) * ":" * string(length(block.rows))
        for block in [positive_blocks; gap_blocks]
    ]
    final_sha256 = fingerprint_records(
        SPATIAL_REFLECTION_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "equalities=" * equality_sha256,
            "moments=" * join(
                (key.canonical for key in moments),
                "\n",
            ),
            "blocks=" * join(block_records, "\n"),
            "coefficients=" * coefficient_sha256,
        ],
    )
    return SpatialReflectionReducedPrimalAssembly(
        SPATIAL_REFLECTION_REDUCTION_SCHEMA,
        source,
        quotient,
        positive_blocks,
        gap_blocks,
        equalities,
        moments,
        coefficient_sha256,
        final_sha256,
    )
end

triangle_count(dimension::Int) =
    dimension * (dimension + 1) ÷ 2

function spatial_reflection_reduced_assembly_report(
    assembly::SpatialReflectionReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_isotypic_moments=length(assembly.source.moments),
        spatial_moments=length(assembly.moments),
        eliminated_spatial_moments=
            length(assembly.source.moments) - length(assembly.moments),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        real_psd_triangle_entries=sum(triangle_count, all_dimensions),
        maximum_psd_side_dimension=maximum(all_dimensions),
        coefficient_map_sha256=assembly.coefficient_map_sha256,
        assembly_sha256=assembly.assembly_sha256,
    )
end

end
