module ShastryFullStateSpinIsotypicReduction

using SHA
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
using ..ShastryFullStateSpatialReduction:
    ShastrySpatialPSDBlock
using ..ShastryFullStateSpinSpatialReduction:
    SPIN_AXIS_PERMUTATIONS,
    ShastryFullStateSpinSpatialReducedPrimalAssembly,
    spin_character,
    spin_row,
    shastry_spin_spatial_block_entry

export SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
       ShastrySpinIsotypicRow,
       ShastrySpinIsotypicPSDBlock,
       ShastryFullStateSpinIsotypicReducedPrimalAssembly,
       shastry_spin_isotypic_truth,
       shastry_spin_isotypic_block_entry,
       assemble_shastry_full_state_spin_isotypic_reduced_primal,
       shastry_full_state_spin_isotypic_reduced_assembly_report

const SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA =
    "shastry-sutherland-full-state-spin-isotypic-v1"
const TRIVIAL_CHARACTER = V4Character(false, false)

struct ShastrySpinIsotypicRow
    source_indices::Vector{Int}
    coefficients::Vector{Int}

    function ShastrySpinIsotypicRow(
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
        new(copy(source_indices), copy(coefficients))
    end
end

struct ShastrySpinIsotypicPSDBlock
    source_block::ShastrySpatialPSDBlock
    kind::Symbol
    rows::Vector{ShastrySpinIsotypicRow}

    function ShastrySpinIsotypicPSDBlock(
        source_block::ShastrySpatialPSDBlock,
        kind::Symbol,
        rows::Vector{ShastrySpinIsotypicRow},
    )
        kind in (:s3_trivial, :s3_standard, :v4_orbit_representative) ||
            throw(ArgumentError("unsupported spin-isotypic block kind"))
        isempty(rows) &&
            throw(ArgumentError("empty spin-isotypic PSD block"))
        all(
            row -> all(
                index -> 1 <= index <= length(source_block.rows),
                row.source_indices,
            ),
            rows,
        ) || throw(ArgumentError("isotypic row index leaves source block"))
        new(source_block, kind, rows)
    end
end

function normalized_combination(
    indices::Vector{Int},
    coefficients::Vector{Int},
)
    pairs = sort!(collect(zip(indices, coefficients)); by=first)
    row_sign = sign(first(pairs)[2])
    normalized =
        [(index, row_sign * coefficient) for (index, coefficient) in pairs]
    key = Tuple(normalized)
    return row_sign, key
end

function spatial_row_action(
    source::ShastrySpatialPSDBlock,
    target::ShastrySpatialPSDBlock,
    permutation,
)
    target_source_indices = Dict(
        row => index
        for (index, row) in enumerate(target.source_block.rows)
    )
    target_rows = Dict{Any,Int}()
    for (index, row) in enumerate(target.rows)
        row_sign, key =
            normalized_combination(row.source_indices, row.coefficients)
        row_sign == 1 ||
            error("target spatial row is not canonically signed")
        haskey(target_rows, key) &&
            error("target spatial block contains duplicate rows")
        target_rows[key] = index
    end

    targets = Int[]
    signs = Int[]
    for row in source.rows
        mapped_indices = Int[]
        mapped_coefficients = Int[]
        for (source_index, coefficient) in
            zip(row.source_indices, row.coefficients)
            sign, mapped = spin_row(
                source.source_block.rows[source_index],
                permutation,
            )
            haskey(target_source_indices, mapped) ||
                error("spin action leaves target source-row inventory")
            push!(mapped_indices, target_source_indices[mapped])
            push!(mapped_coefficients, sign * coefficient)
        end
        row_sign, key =
            normalized_combination(mapped_indices, mapped_coefficients)
        haskey(target_rows, key) ||
            error("spin action leaves target spatial-row inventory")
        push!(targets, target_rows[key])
        push!(signs, row_sign)
    end
    length(unique(targets)) == length(source.rows) ||
        error("spin row action is not a permutation")
    return targets, signs
end

function apply_signed_action(
    coefficients::Vector{Int},
    targets::Vector{Int},
    signs::Vector{Int},
)
    result = zeros(Int, length(coefficients))
    for index in eachindex(coefficients)
        result[targets[index]] += signs[index] * coefficients[index]
    end
    return result
end

function primitive_vector(coefficients::Vector{Int})
    divisor = foldl(gcd, abs.(coefficients); init=0)
    divisor > 0 || error("cannot normalize a zero vector")
    result = coefficients .÷ divisor
    first_nonzero = findfirst(!iszero, result)
    result[something(first_nonzero)] < 0 && (result .*= -1)
    return result
end

function trivial_isotypic_rows(block::ShastrySpatialPSDBlock)
    actions = [
        spatial_row_action(block, block, permutation)
        for permutation in SPIN_AXIS_PERMUTATIONS
    ]
    dimension = length(block.rows)
    visited = falses(dimension)
    trivial = ShastrySpinIsotypicRow[]
    standard_plus = ShastrySpinIsotypicRow[]
    standard_minus = ShastrySpinIsotypicRow[]
    orbit_sizes = Int[]

    for start in 1:dimension
        visited[start] && continue
        orbit = sort!(unique(targets[start] for (targets, _) in actions))
        all(!visited[index] for index in orbit) ||
            error("spin row orbits overlap")
        visited[orbit] .= true
        push!(orbit_sizes, length(orbit))

        projected = zeros(Int, dimension)
        for (targets, signs) in actions
            projected[targets[start]] += signs[start]
        end
        projected = primitive_vector(projected)
        all(
            apply_signed_action(projected, targets, signs) == projected
            for (targets, signs) in actions
        ) || error("constructed trivial row is not S3 invariant")
        all(index in orbit || iszero(projected[index]) for index in 1:dimension) ||
            error("trivial projector escaped its row orbit")

        if length(orbit) == 1
            only_coefficient = projected[only(orbit)]
            abs(only_coefficient) == 1 ||
                error("unexpected singleton trivial normalization")
            push!(
                trivial,
                ShastrySpinIsotypicRow(copy(orbit), [only_coefficient]),
            )
            continue
        end
        length(orbit) == 3 ||
            error("target L=1,d=2 block has a non-1/3 spin orbit")

        transposition_targets, transposition_signs = actions[2]
        fixed = [
            index
            for index in orbit
            if transposition_targets[index] == index
        ]
        length(fixed) == 1 ||
            error("transposition does not fix exactly one row in triple orbit")
        fixed_index = only(fixed)
        transposition_signs[fixed_index] == 1 ||
            error("fixed row carries the sign irrep")
        exchanged = sort!(setdiff(orbit, fixed))
        left, right = exchanged
        transposition_targets[left] == right ||
            error("transposition does not exchange the remaining rows")

        coefficients = projected[orbit]
        all(abs(coefficient) == 1 for coefficient in coefficients) ||
            error("unexpected signed-permutation trivial vector")
        c_left = projected[left]
        c_right = projected[right]
        c_fixed = projected[fixed_index]
        transposition_signs[left] * c_left == c_right ||
            error("trivial gauge is inconsistent with transposition")

        push!(
            trivial,
            ShastrySpinIsotypicRow(copy(orbit), coefficients),
        )
        push!(
            standard_plus,
            ShastrySpinIsotypicRow(
                [left, right, fixed_index],
                [c_left, c_right, -2c_fixed],
            ),
        )
        push!(
            standard_minus,
            ShastrySpinIsotypicRow(
                [left, right],
                [c_left, -c_right],
            ),
        )
    end
    return (
        trivial=trivial,
        standard_plus=standard_plus,
        standard_minus=standard_minus,
        orbit_sizes=sort!(orbit_sizes),
    )
end

function identity_rows(block::ShastrySpatialPSDBlock)
    return ShastrySpinIsotypicRow[
        ShastrySpinIsotypicRow([index], [1])
        for index in eachindex(block.rows)
    ]
end

function combined_block_entry(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
    block::ShastrySpatialPSDBlock,
    left::ShastrySpinIsotypicRow,
    right::ShastrySpinIsotypicRow,
)
    polynomial = ExactLinearPolynomial()
    for (left_index, left_coefficient) in
        zip(left.source_indices, left.coefficients)
        for (right_index, right_coefficient) in
            zip(right.source_indices, right.coefficients)
            source = shastry_spin_spatial_block_entry(
                assembly,
                block,
                block.rows[left_index],
                block.rows[right_index],
            )
            scale = left_coefficient * right_coefficient
            for (key, coefficient) in source.terms
                add_term!(polynomial, key, scale * coefficient)
            end
        end
    end
    all(iszero ∘ imag, values(polynomial.terms)) ||
        error("spin-isotypic entry is not exactly real")
    return polynomial
end

function block_group_key(block::ShastrySpatialPSDBlock)
    source = block.source_block
    return (source.role, source.family, block.parity)
end

function retained_blocks(blocks::Vector{ShastrySpatialPSDBlock})
    result = ShastrySpinIsotypicPSDBlock[]
    for block in blocks
        if block.source_block.character == TRIVIAL_CHARACTER
            decomposition = trivial_isotypic_rows(block)
            push!(
                result,
                ShastrySpinIsotypicPSDBlock(
                    block,
                    :s3_trivial,
                    decomposition.trivial,
                ),
            )
            isempty(decomposition.standard_minus) || push!(
                result,
                ShastrySpinIsotypicPSDBlock(
                    block,
                    :s3_standard,
                    decomposition.standard_minus,
                ),
            )
        else
            push!(
                result,
                ShastrySpinIsotypicPSDBlock(
                    block,
                    :v4_orbit_representative,
                    identity_rows(block),
                ),
            )
        end
    end
    return result
end

function nontrivial_orbit_truth(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
    blocks::Vector{ShastrySpatialPSDBlock},
)
    exact = true
    comparison_count = 0
    by_group =
        Dict{Tuple{Symbol,Symbol,Symbol},Vector{ShastrySpatialPSDBlock}}()
    for block in blocks
        block.source_block.character == TRIVIAL_CHARACTER && continue
        push!(get!(by_group, block_group_key(block), ShastrySpatialPSDBlock[]), block)
    end
    for group in values(by_group)
        length(group) == 3 ||
            error("nontrivial V4-character orbit does not have size three")
        representative = first(group)
        for block in group[2:end]
            permutation_index = findfirst(
                permutation ->
                    spin_character(block.source_block.character, permutation) ==
                    representative.source_block.character,
                SPIN_AXIS_PERMUTATIONS,
            )
            isnothing(permutation_index) &&
                error("cannot map V4 character to retained representative")
            targets, signs = spatial_row_action(
                block,
                representative,
                SPIN_AXIS_PERMUTATIONS[something(permutation_index)],
            )
            for row in eachindex(block.rows)
                for column in row:length(block.rows)
                    source_entry = shastry_spin_spatial_block_entry(
                        assembly,
                        block,
                        block.rows[row],
                        block.rows[column],
                    )
                    target_entry = shastry_spin_spatial_block_entry(
                        assembly,
                        representative,
                        representative.rows[targets[row]],
                        representative.rows[targets[column]],
                    )
                    exact &=
                        source_entry ==
                        (signs[row] * signs[column]) * target_entry
                    comparison_count += 1
                end
            end
        end
    end
    return exact, comparison_count
end

function trivial_block_truth(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
    block::ShastrySpatialPSDBlock,
)
    decomposition = trivial_isotypic_rows(block)
    cross_zero = true
    standard_proportional = true
    cross_count = 0
    proportional_count = 0
    for (left_rows, right_rows) in (
        (decomposition.trivial, decomposition.standard_plus),
        (decomposition.trivial, decomposition.standard_minus),
        (decomposition.standard_plus, decomposition.standard_minus),
    )
        for left in left_rows, right in right_rows
            cross_zero &=
                iszero(combined_block_entry(assembly, block, left, right))
            cross_count += 1
        end
    end
    length(decomposition.standard_plus) ==
        length(decomposition.standard_minus) ||
        error("standard multiplicities differ")
    for row in eachindex(decomposition.standard_minus)
        for column in row:length(decomposition.standard_minus)
            plus_entry = combined_block_entry(
                assembly,
                block,
                decomposition.standard_plus[row],
                decomposition.standard_plus[column],
            )
            minus_entry = combined_block_entry(
                assembly,
                block,
                decomposition.standard_minus[row],
                decomposition.standard_minus[column],
            )
            standard_proportional &= plus_entry == 3 * minus_entry
            proportional_count += 1
        end
    end
    return (
        exact=cross_zero &&
              standard_proportional &&
              length(block.rows) ==
                  length(decomposition.trivial) +
                  2 * length(decomposition.standard_minus),
        cross_zero=cross_zero,
        standard_proportional=standard_proportional,
        cross_count=cross_count,
        proportional_count=proportional_count,
        orbit_sizes=decomposition.orbit_sizes,
        source_dimension=length(block.rows),
        trivial_dimension=length(decomposition.trivial),
        standard_dimension=length(decomposition.standard_minus),
    )
end

function shastry_spin_isotypic_truth(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
)
    trivial_blocks = filter(
        block -> block.source_block.character == TRIVIAL_CHARACTER,
        [assembly.positive_blocks; assembly.gap_blocks],
    )
    trivial_reports = Vector{Any}(undef, length(trivial_blocks))
    Threads.@threads :dynamic for index in eachindex(trivial_blocks)
        trivial_reports[index] =
            trivial_block_truth(assembly, trivial_blocks[index])
    end
    positive_blocks = retained_blocks(assembly.positive_blocks)
    gap_blocks = retained_blocks(assembly.gap_blocks)
    dimensions = sort!(
        [
            length(block.rows)
            for block in [positive_blocks; gap_blocks]
        ];
        rev=true,
    )
    exact =
        all(report.exact for report in trivial_reports)
    return (
        exact=exact,
        trivial_blocks_exact=all(report.exact for report in trivial_reports),
        retained_block_dimensions=dimensions,
        trivial_reports=trivial_reports,
    )
end

struct ShastryFullStateSpinIsotypicReducedPrimalAssembly{A,T}
    schema::String
    source::A
    truth::T
    positive_blocks::Vector{ShastrySpinIsotypicPSDBlock}
    gap_blocks::Vector{ShastrySpinIsotypicPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function shastry_spin_isotypic_block_entry(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block::ShastrySpinIsotypicPSDBlock,
    left::ShastrySpinIsotypicRow,
    right::ShastrySpinIsotypicRow,
)
    return combined_block_entry(
        assembly.source,
        block.source_block,
        left,
        right,
    )
end

function fingerprint_records(schema::String, records)
    io = IOBuffer()
    for record in (schema, records...)
        serialized = string(record)
        write(io, string(ncodeunits(serialized)), ":", serialized)
    end
    return bytes2hex(sha256(take!(io)))
end

function block_label(block::ShastrySpinIsotypicPSDBlock)
    source = block.source_block.source_block
    return join(
        (
            source.role,
            source.family,
            Int(source.character.rx),
            Int(source.character.ry),
            block.source_block.parity,
            block.kind,
        ),
        "/",
    )
end

function assemble_shastry_full_state_spin_isotypic_reduced_primal(
    source::ShastryFullStateSpinSpatialReducedPrimalAssembly;
    verify_truth::Bool=true,
    materialize_coefficients::Bool=true,
)
    truth = verify_truth ? shastry_spin_isotypic_truth(source) : nothing
    verify_truth && !something(truth).exact &&
        error("Shastry spin-isotypic truth gate failed")
    positive_blocks = retained_blocks(source.positive_blocks)
    gap_blocks = retained_blocks(source.gap_blocks)
    equalities = canonical_real_equalities(copy(source.equalities))
    if !materialize_coefficients
        block_records = String[
            string(
                block_label(block),
                ":dimension=",
                length(block.rows),
            )
            for block in [positive_blocks; gap_blocks]
        ]
        assembly_sha256 = fingerprint_records(
            SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
            [
                "source=" * source.assembly_sha256,
                "coefficient_map=deferred-structural-v1",
                "blocks=" * join(block_records, "\n"),
                "equalities=" * join(
                    canonical_polynomial_string.(equalities),
                    "\n",
                ),
            ],
        )
        return ShastryFullStateSpinIsotypicReducedPrimalAssembly(
            SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
            source,
            truth,
            positive_blocks,
            gap_blocks,
            equalities,
            MomentKey[],
            "deferred-structural-v1",
            assembly_sha256,
        )
    end
    provisional = ShastryFullStateSpinIsotypicReducedPrimalAssembly(
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
        source,
        truth,
        positive_blocks,
        gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )
    used_moments = Set{MomentKey}([moment_key()])
    all_blocks = [positive_blocks; gap_blocks]
    block_moments =
        [Set{MomentKey}() for _ in eachindex(all_blocks)]
    block_records = [String[] for _ in eachindex(all_blocks)]
    Threads.@threads :dynamic for block_index in eachindex(all_blocks)
        block = all_blocks[block_index]
        local_moments = block_moments[block_index]
        local_records = block_records[block_index]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = shastry_spin_isotypic_block_entry(
                provisional,
                block,
                block.rows[row],
                block.rows[column],
            )
            union!(local_moments, keys(polynomial.terms))
            push!(
                local_records,
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
    coefficient_records = String[]
    for block_index in eachindex(all_blocks)
        union!(used_moments, block_moments[block_index])
        append!(coefficient_records, block_records[block_index])
    end
    for equality in equalities
        union!(used_moments, keys(equality.terms))
    end
    moments = sort!(
        collect(used_moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(moments) == moment_key() ||
        error("identity moment is not first after spin-isotypic reduction")
    coefficient_sha256 = fingerprint_records(
        "shastry-full-state-spin-isotypic-coefficients-v1",
        coefficient_records,
    )
    assembly_sha256 = fingerprint_records(
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "coefficient_map=" * coefficient_sha256,
            "moments=" * join((key.canonical for key in moments), "\n"),
            "equalities=" * join(
                canonical_polynomial_string.(equalities),
                "\n",
            ),
        ],
    )
    return ShastryFullStateSpinIsotypicReducedPrimalAssembly(
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
        source,
        truth,
        positive_blocks,
        gap_blocks,
        equalities,
        moments,
        coefficient_sha256,
        assembly_sha256,
    )
end

triangle(dimension::Int) = dimension * (dimension + 1) ÷ 2

function shastry_full_state_spin_isotypic_reduced_assembly_report(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_moments=length(assembly.source.moments),
        spin_isotypic_moments=length(assembly.moments),
        eliminated_unused_moments=
            length(assembly.source.moments) - length(assembly.moments),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        psd_triangle_entries=sum(triangle, dimensions),
        maximum_side=maximum(dimensions),
    )
end

end
