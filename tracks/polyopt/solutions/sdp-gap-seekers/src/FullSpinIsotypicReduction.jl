module FullSpinIsotypicReduction

using SHA
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
    V4Character,
    canonical_real_equalities
using ..ReducedPrimalGapAssembly:
    ReducedPSDBlock
using ..ConjugationSymmetryReduction:
    conjugation_odd,
    conjugation_real_block_entry
using ..SpinAxisInvolutionReduction:
    SpinAxisReducedPSDBlock,
    spin_axis_involution
using ..FullSpinPermutationReduction:
    SPIN_AXIS_PERMUTATIONS,
    full_spin_permutation,
    full_spin_quotient_projection
using ..FullSpinConeReduction:
    FullSpinConeReducedPrimalAssembly

export FULL_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
       FullSpinIsotypicCombinationRow,
       FullSpinIsotypicPSDBlock,
       FullSpinIsotypicReducedPrimalAssembly,
       full_spin_trivial_isotypic_truth,
       full_spin_isotypic_block_entry,
       assemble_full_spin_isotypic_reduced_primal,
       full_spin_isotypic_reduced_assembly_report

const FULL_SPIN_ISOTYPIC_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-v1"
const TRIVIAL_CHARACTER = V4Character(false, false)

"""
One exact row combination in an S3-adapted basis.

Integer coefficients deliberately omit normalization. Every transformation
used below is invertible over the rationals, which is sufficient for an exact
PSD congruence.
"""
struct FullSpinIsotypicCombinationRow
    source_indices::Vector{Int}
    coefficients::Vector{Int}

    function FullSpinIsotypicCombinationRow(
        source_indices::Vector{Int},
        coefficients::Vector{Int},
    )
        isempty(source_indices) &&
            throw(ArgumentError("isotypic row cannot be empty"))
        length(source_indices) == length(coefficients) ||
            throw(ArgumentError("isotypic row index/coefficient mismatch"))
        length(unique(source_indices)) == length(source_indices) ||
            throw(ArgumentError("isotypic row repeats a source index"))
        all(!iszero, coefficients) ||
            throw(ArgumentError("isotypic row contains a zero coefficient"))
        new(source_indices, coefficients)
    end
end

"""
One retained real PSD block after the full-S3 isotypic reduction.

For a trivial V4 source block, `kind` is `:s3_trivial` or
`:s3_standard_representative`. Nontrivial blocks retain their already-proved
`:eigen_plus` or `:eigen_minus` label.
"""
struct FullSpinIsotypicPSDBlock
    source_block::ReducedPSDBlock
    kind::Symbol
    rows::Vector{FullSpinIsotypicCombinationRow}

    function FullSpinIsotypicPSDBlock(
        source_block::ReducedPSDBlock,
        kind::Symbol,
        rows::Vector{FullSpinIsotypicCombinationRow},
    )
        kind in (
            :s3_trivial,
            :s3_standard_representative,
            :eigen_plus,
            :eigen_minus,
        ) || throw(ArgumentError("unsupported full-spin isotypic block kind"))
        isempty(rows) &&
            throw(ArgumentError("empty isotypic PSD blocks must be omitted"))
        all(
            row -> all(
                index -> 1 <= index <= length(source_block.rows),
                row.source_indices,
            ),
            rows,
        ) || throw(ArgumentError("isotypic row index is out of range"))
        new(source_block, kind, rows)
    end
end

function exact_matrix_rank(matrix::Matrix{ExactRational})
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
        rank == min(size(reduced)...) && break
    end
    return rank
end

function combination_basis_rank(
    rows::Vector{FullSpinIsotypicCombinationRow},
    dimension::Int,
)
    matrix = zeros(ExactRational, length(rows), dimension)
    for (row_index, row) in enumerate(rows)
        for (source_index, coefficient) in
            zip(row.source_indices, row.coefficients)
            matrix[row_index, source_index] = coefficient
        end
    end
    return exact_matrix_rank(matrix)
end

function source_blocks_by_family(
    assembly::FullSpinConeReducedPrimalAssembly,
)
    result = Dict{Symbol,ReducedPSDBlock}()
    for block in assembly.positive_blocks
        block.source_block.character == TRIVIAL_CHARACTER || continue
        family = block.source_block.family
        if haskey(result, family)
            result[family] === block.source_block ||
                error("trivial blocks in one family have different sources")
        else
            result[family] = block.source_block
        end
    end
    Set(keys(result)) == Set([:centered, :scalar]) ||
        error("expected centered and scalar trivial-character source blocks")
    return result
end

function row_orbits(block::ReducedPSDBlock)
    indices = Dict(
        row.word => index
        for (index, row) in enumerate(block.rows)
    )
    length(indices) == length(block.rows) ||
        error("trivial source block contains duplicate row words")
    visited = falses(length(block.rows))
    orbits = Vector{Vector{Int}}()
    actions_unsigned = true
    for start in eachindex(block.rows)
        visited[start] && continue
        orbit = Set{Int}()
        for permutation in SPIN_AXIS_PERMUTATIONS
            sign, target =
                full_spin_permutation(block.rows[start].word, permutation)
            actions_unsigned &= sign == 1
            haskey(indices, target) ||
                error("trivial source block is not closed under full S3")
            push!(orbit, indices[target])
        end
        ordered = sort!(collect(orbit))
        all(!visited[index] for index in ordered) ||
            error("full-S3 row orbits overlap")
        for index in ordered
            visited[index] = true
        end
        push!(orbits, ordered)
    end
    sort!(orbits; by=first)
    return orbits, actions_unsigned
end

function isotypic_rows(block::ReducedPSDBlock)
    orbits, actions_unsigned = row_orbits(block)
    trivial = FullSpinIsotypicCombinationRow[]
    standard_plus = FullSpinIsotypicCombinationRow[]
    standard_minus = FullSpinIsotypicCombinationRow[]
    singleton_count = 0
    triple_count = 0
    involution_exact = true

    for orbit in orbits
        if length(orbit) == 1
            singleton_count += 1
            push!(
                trivial,
                FullSpinIsotypicCombinationRow(copy(orbit), [1]),
            )
            continue
        end
        length(orbit) == 3 ||
            error("unexpected trivial-character S3 row-orbit size")
        triple_count += 1
        fixed = Int[]
        exchanged = Int[]
        for index in orbit
            sign, target =
                spin_axis_involution(block.rows[index].word)
            haskey(
                Dict(
                    block.rows[source_index].word => source_index
                    for source_index in orbit
                ),
                target,
            ) || error("row orbit is not closed under the fixed involution")
            target_index = findfirst(
                source_index -> block.rows[source_index].word == target,
                orbit,
            )
            isnothing(target_index) &&
                error("fixed-involution target is missing")
            mapped = orbit[something(target_index)]
            involution_exact &= sign == 1
            if mapped == index
                push!(fixed, index)
            else
                push!(exchanged, index)
            end
        end
        length(fixed) == 1 && length(exchanged) == 2 ||
            error("unexpected involution action inside an S3 row orbit")
        sort!(exchanged)
        fixed_index = only(fixed)
        push!(
            trivial,
            FullSpinIsotypicCombinationRow(copy(orbit), ones(Int, 3)),
        )
        push!(
            standard_plus,
            FullSpinIsotypicCombinationRow(
                [exchanged; fixed_index],
                [1, 1, -2],
            ),
        )
        push!(
            standard_minus,
            FullSpinIsotypicCombinationRow(exchanged, [1, -1]),
        )
    end

    return (
        trivial=trivial,
        standard_plus=standard_plus,
        standard_minus=standard_minus,
        orbit_sizes=length.(orbits),
        singleton_count=singleton_count,
        triple_count=triple_count,
        actions_unsigned=actions_unsigned,
        involution_exact=involution_exact,
    )
end

function combined_block_entry(
    assembly::FullSpinConeReducedPrimalAssembly,
    source_block::ReducedPSDBlock,
    left::FullSpinIsotypicCombinationRow,
    right::FullSpinIsotypicCombinationRow,
)
    polynomial = ExactLinearPolynomial()
    conjugation_source = assembly.source.source.source
    for (left_position, left_index) in enumerate(left.source_indices)
        for (right_position, right_index) in enumerate(right.source_indices)
            source_entry = conjugation_real_block_entry(
                conjugation_source,
                source_block,
                source_block.rows[left_index],
                source_block.rows[right_index],
            )
            scale =
                left.coefficients[left_position] *
                right.coefficients[right_position]
            for (key, coefficient) in source_entry.terms
                add_term!(polynomial, key, scale * coefficient)
            end
        end
    end
    projected = full_spin_quotient_projection(
        polynomial,
        assembly.source.quotient,
    )
    all(iszero ∘ imag, values(projected.terms)) ||
        error("full-spin isotypic block entry is not exactly real")
    return projected
end

function cross_zero(
    assembly::FullSpinConeReducedPrimalAssembly,
    source_block::ReducedPSDBlock,
    left_rows::Vector{FullSpinIsotypicCombinationRow},
    right_rows::Vector{FullSpinIsotypicCombinationRow},
)
    exact = true
    count = 0
    for left in left_rows, right in right_rows
        exact &= iszero(combined_block_entry(
            assembly,
            source_block,
            left,
            right,
        ))
        count += 1
    end
    return exact, count
end

"""
Exhaustively prove the remaining trivial-character full-S3 row reduction.

For every three-row axis orbit, the integer basis
`t=(1,1,1)`, `w=(1,1,-2)`, `m=(1,-1,0)` splits the natural S3 row
representation into its trivial line and two orthogonal standard-irrep
directions. Exact full-S3 coefficient projection makes all three cross blocks
zero and gives `W = 3M`. Hence the complete source block is PSD exactly when
the `t` block and one retained `m` block are PSD.
"""
function full_spin_trivial_isotypic_truth(
    assembly::FullSpinConeReducedPrimalAssembly,
)
    sources = source_blocks_by_family(assembly)
    row_actions_unsigned = true
    conjugation_rows_even = true
    involution_exact = true
    cross_blocks_zero = true
    standard_blocks_proportional = true
    bases_invertible = true
    singleton_orbit_count = 0
    triple_orbit_count = 0
    cross_entry_count = 0
    standard_relation_entry_count = 0
    source_dimensions = Int[]
    trivial_dimensions = Int[]
    standard_dimensions = Int[]
    basis_dimensions = Int[]
    orbit_sizes = Dict{Symbol,Vector{Int}}()

    for family in (:centered, :scalar)
        source_block = sources[family]
        decomposition = isotypic_rows(source_block)
        push!(source_dimensions, length(source_block.rows))
        push!(trivial_dimensions, length(decomposition.trivial))
        push!(standard_dimensions, length(decomposition.standard_minus))
        singleton_orbit_count += decomposition.singleton_count
        triple_orbit_count += decomposition.triple_count
        row_actions_unsigned &= decomposition.actions_unsigned
        involution_exact &= decomposition.involution_exact
        conjugation_rows_even &= all(
            !conjugation_odd(row.word)
            for row in source_block.rows
        )
        orbit_sizes[family] = sort(decomposition.orbit_sizes)

        all_rows = [
            decomposition.trivial;
            decomposition.standard_plus;
            decomposition.standard_minus
        ]
        basis_rank = combination_basis_rank(
            all_rows,
            length(source_block.rows),
        )
        push!(basis_dimensions, basis_rank)
        bases_invertible &= basis_rank == length(source_block.rows)

        for (left, right) in (
            (decomposition.trivial, decomposition.standard_plus),
            (decomposition.trivial, decomposition.standard_minus),
            (decomposition.standard_plus, decomposition.standard_minus),
        )
            exact, count = cross_zero(
                assembly,
                source_block,
                left,
                right,
            )
            cross_blocks_zero &= exact
            cross_entry_count += count
        end

        length(decomposition.standard_plus) ==
            length(decomposition.standard_minus) ||
            error("standard isotypic multiplicities differ")
        dimension = length(decomposition.standard_minus)
        for row in 1:dimension, column in row:dimension
            plus_entry = combined_block_entry(
                assembly,
                source_block,
                decomposition.standard_plus[row],
                decomposition.standard_plus[column],
            )
            minus_entry = combined_block_entry(
                assembly,
                source_block,
                decomposition.standard_minus[row],
                decomposition.standard_minus[column],
            )
            standard_blocks_proportional &= plus_entry == 3 * minus_entry
            standard_relation_entry_count += 1
        end
    end

    expected_orbits =
        orbit_sizes[:centered] == fill(3, 36) &&
        orbit_sizes[:scalar] == [1; fill(3, 36)]
    exact =
        source_dimensions == [108, 109] &&
        trivial_dimensions == [36, 37] &&
        standard_dimensions == [36, 36] &&
        singleton_orbit_count == 1 &&
        triple_orbit_count == 72 &&
        expected_orbits &&
        row_actions_unsigned &&
        conjugation_rows_even &&
        involution_exact &&
        cross_blocks_zero &&
        standard_blocks_proportional &&
        bases_invertible
    return (
        exact=exact,
        source_dimensions=source_dimensions,
        trivial_dimensions=trivial_dimensions,
        standard_dimensions=standard_dimensions,
        singleton_orbit_count=singleton_orbit_count,
        triple_orbit_count=triple_orbit_count,
        orbit_sizes=orbit_sizes,
        row_actions_unsigned=row_actions_unsigned,
        conjugation_rows_even=conjugation_rows_even,
        involution_exact=involution_exact,
        cross_blocks_zero=cross_blocks_zero,
        cross_entry_count=cross_entry_count,
        standard_blocks_proportional=standard_blocks_proportional,
        standard_proportionality_factor=3,
        standard_relation_entry_count=standard_relation_entry_count,
        bases_invertible=bases_invertible,
        basis_dimensions=basis_dimensions,
    )
end

struct FullSpinIsotypicReducedPrimalAssembly{A}
    schema::String
    source::A
    positive_blocks::Vector{FullSpinIsotypicPSDBlock}
    gap_blocks::Vector{FullSpinIsotypicPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function full_spin_isotypic_block_entry(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    block::FullSpinIsotypicPSDBlock,
    left::FullSpinIsotypicCombinationRow,
    right::FullSpinIsotypicCombinationRow,
)
    return combined_block_entry(
        assembly.source,
        block.source_block,
        left,
        right,
    )
end

function converted_block(block::SpinAxisReducedPSDBlock)
    return FullSpinIsotypicPSDBlock(
        block.source_block,
        block.kind,
        FullSpinIsotypicCombinationRow[
            FullSpinIsotypicCombinationRow(
                copy(row.source_indices),
                copy(row.coefficients),
            )
            for row in block.rows
        ],
    )
end

function isotypic_positive_blocks(
    source::FullSpinConeReducedPrimalAssembly,
)
    result = FullSpinIsotypicPSDBlock[]
    emitted_trivial = Set{Symbol}()
    for block in source.positive_blocks
        source_block = block.source_block
        if source_block.character != TRIVIAL_CHARACTER
            push!(result, converted_block(block))
            continue
        end
        family = source_block.family
        family in emitted_trivial && continue
        decomposition = isotypic_rows(source_block)
        push!(
            result,
            FullSpinIsotypicPSDBlock(
                source_block,
                :s3_trivial,
                decomposition.trivial,
            ),
        )
        push!(
            result,
            FullSpinIsotypicPSDBlock(
                source_block,
                :s3_standard_representative,
                decomposition.standard_minus,
            ),
        )
        push!(emitted_trivial, family)
    end
    emitted_trivial == Set([:centered, :scalar]) ||
        error("did not emit both trivial-character positive families")
    return result
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

function block_label(block::FullSpinIsotypicPSDBlock)
    source = block.source_block
    return join(
        (
            source.role,
            source.family,
            "rx" * string(Int(source.character.rx)),
            "ry" * string(Int(source.character.ry)),
            block.kind,
        ),
        ":",
    )
end

function assemble_full_spin_isotypic_reduced_primal(
    source::FullSpinConeReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ?
        full_spin_trivial_isotypic_truth(source) :
        nothing
    if verify_truth
        something(truth).exact ||
            error("full-spin trivial isotypic truth check failed")
    end

    positive_blocks = isotypic_positive_blocks(source)
    gap_blocks = converted_block.(source.gap_blocks)
    equalities = canonical_real_equalities(copy(source.equalities))
    provisional = FullSpinIsotypicReducedPrimalAssembly(
        FULL_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
        source,
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
            polynomial = full_spin_isotypic_block_entry(
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
                        block_label(block),
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
        error("identity moment is not first after isotypic reduction")

    coefficient_sha256 = fingerprint_records(
        "full-spin-isotypic-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "full-spin-isotypic-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    block_records = String[
        block_label(block) * ":" * string(length(block.rows))
        for block in [positive_blocks; gap_blocks]
    ]
    final_sha256 = fingerprint_records(
        FULL_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
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
    return FullSpinIsotypicReducedPrimalAssembly(
        FULL_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
        source,
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

function full_spin_isotypic_reduced_assembly_report(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_full_spin_moments=length(assembly.source.moments),
        isotypic_moments=length(assembly.moments),
        eliminated_unused_moments=
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
