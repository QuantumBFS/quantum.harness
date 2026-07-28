module ContinuousSpinConeReduction

using SHA
using ..PrimalGapSymbolics:
    ExactRational,
    ExactLinearPolynomial,
    MomentKey,
    moment_key,
    canonical_polynomial_string,
    polynomial_sha256
using ..FullSpinIsotypicReduction:
    FullSpinIsotypicCombinationRow,
    FullSpinIsotypicPSDBlock
using ..ContinuousSpinMomentReduction:
    ContinuousSpinReducedPrimalAssembly,
    continuous_spin_block_entry

export CONTINUOUS_SPIN_CONE_REDUCTION_SCHEMA,
       ContinuousSpinConeReducedPrimalAssembly,
       continuous_spin_l2_cone_redundancy_truth,
       continuous_spin_cone_block_entry,
       assemble_continuous_spin_cone_reduced_primal,
       continuous_spin_cone_reduced_assembly_report

const CONTINUOUS_SPIN_CONE_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-continuous-spin-l2-cone-v1"

function row_site_signature(
    block::FullSpinIsotypicPSDBlock,
    row::FullSpinIsotypicCombinationRow,
)
    source_rows = block.source_block.rows
    signatures = [
        Tuple(first.(source_rows[index].word.ops))
        for index in row.source_indices
    ]
    length(unique(signatures)) == 1 ||
        error("one spin-adapted row mixes spatial skeletons")
    signature = only(unique(signatures))
    length(signature) == 2 ||
        error("an l=2 row does not have Pauli rank two")
    length(unique(signature)) == 2 ||
        error("an l=2 row repeats one physical site")
    return signature
end

function row_axis_signature(
    block::FullSpinIsotypicPSDBlock,
    row::FullSpinIsotypicCombinationRow,
)
    source_rows = block.source_block.rows
    signature = Dict{Tuple{UInt8,UInt8},Int}()
    for (index, coefficient) in
        zip(row.source_indices, row.coefficients)
        axes = Tuple(last.(source_rows[index].word.ops))
        length(axes) == 2 ||
            error("an l=2 row component does not have Pauli rank two")
        signature[axes] = get(signature, axes, 0) + coefficient
    end
    filter!(pair -> !iszero(last(pair)), signature)
    return signature
end

function diagonal_l2_orientation(signature)
    canonical = Dict(
        (UInt8(1), UInt8(1)) => 1,
        (UInt8(3), UInt8(3)) => -1,
    )
    signature == canonical && return 1
    signature == Dict(key => -value for (key, value) in canonical) &&
        return -1
    return 0
end

function offdiagonal_l2_orientation(signature)
    canonical = Dict(
        (UInt8(1), UInt8(3)) => 1,
        (UInt8(3), UInt8(1)) => 1,
    )
    signature == canonical && return 1
    signature == Dict(key => -value for (key, value) in canonical) &&
        return -1
    return 0
end

component_squared_norm(signature) =
    sum(abs2, values(signature); init=0)
end

function blocks_for_family(
    assembly::ContinuousSpinReducedPrimalAssembly,
    family::Symbol,
)
    blocks = filter(
        block ->
            block.source_block.role == :positive &&
            block.source_block.family == family,
        assembly.positive_blocks,
    )
    standard = filter(
        block -> block.kind == :s3_standard_representative,
        blocks,
    )
    tensor = filter(
        block ->
            block.kind == :eigen_plus &&
            length(block.rows) == 36,
        blocks,
    )
    length(standard) == 1 ||
        error("expected one S3-standard l=2 block for $family")
    length(tensor) == 1 ||
        error("expected one off-diagonal l=2 block for $family")
    return only(standard), only(tensor)
end

function rows_by_site_signature(block::FullSpinIsotypicPSDBlock)
    result = Dict{Tuple{Int,Int},Int}()
    for (index, row) in enumerate(block.rows)
        signature = row_site_signature(block, row)
        haskey(result, signature) &&
            error("an l=2 block repeats a spatial skeleton")
        result[signature] = index
    end
    return result
end

function exact_permutation_rank(
    source::Dict{Tuple{Int,Int},Int},
    target::Dict{Tuple{Int,Int},Int},
)
    Set(keys(source)) == Set(keys(target)) ||
        error("l=2 blocks have different spatial skeletons")
    dimension = length(source)
    matrix = zeros(ExactRational, dimension, dimension)
    for signature in keys(source)
        matrix[source[signature], target[signature]] = 1
    end

    rank = 0
    for column in axes(matrix, 2)
        pivot = findfirst(
            row -> !iszero(matrix[row, column]),
            (rank + 1):size(matrix, 1),
        )
        isnothing(pivot) && continue
        selected = rank + something(pivot)
        rank += 1
        if selected != rank
            matrix[rank, :], matrix[selected, :] =
                copy(matrix[selected, :]), copy(matrix[rank, :])
        end
        for row in (rank + 1):size(matrix, 1)
            iszero(matrix[row, column]) && continue
            matrix[row, :] .-= matrix[rank, :]
        end
    end
    return rank
end

"""
Prove exact redundancy of the second octahedral copy of each l=2 cone.

Each rank-two row skeleton carries the `SO(3)` decomposition
`l=0 + l=1 + l=2`.  The preceding discrete decomposition represents `l=2`
twice: its diagonal component `XX-ZZ` in the S3-standard block and its
off-diagonal component `XZ+ZX` in the stable nontrivial-character block.
Both component rows have the same exact Euclidean norm.  After the continuous
spin moment projection, Schur invariance therefore makes their multiplicity
matrices identical.  The checks below replay that equality entry by entry and
also prove that the spatial-skeleton row correspondence has full rank.
"""
function continuous_spin_l2_cone_redundancy_truth(
    assembly::ContinuousSpinReducedPrimalAssembly,
)
    dimensions = Int[]
    row_map_ranks = Int[]
    component_rows_canonical = true
    component_squared_norms = Int[]
    coefficient_congruence_exact = true
    entry_count = 0
    nonzero_entry_count = 0

    for family in (:centered, :scalar)
        standard, tensor = blocks_for_family(assembly, family)
        length(standard.rows) == length(tensor.rows) ||
            error("paired l=2 cone dimensions differ for $family")
        dimension = length(standard.rows)
        push!(dimensions, dimension)

        standard_rows = rows_by_site_signature(standard)
        tensor_rows = rows_by_site_signature(tensor)
        push!(
            row_map_ranks,
            exact_permutation_rank(standard_rows, tensor_rows),
        )

        standard_orientations = Dict(
            signature => diagonal_l2_orientation(
                row_axis_signature(
                    standard,
                    standard.rows[index],
                ),
            )
            for (signature, index) in standard_rows
        )
        tensor_orientations = Dict(
            signature => offdiagonal_l2_orientation(
                row_axis_signature(
                    tensor,
                    tensor.rows[index],
                ),
            )
            for (signature, index) in tensor_rows
        )
        component_rows_canonical &=
            all(!iszero, values(standard_orientations)) &&
            all(!iszero, values(tensor_orientations))
        append!(
            component_squared_norms,
            component_squared_norm(
                row_axis_signature(standard, row),
            )
            for row in standard.rows
        )
        append!(
            component_squared_norms,
            component_squared_norm(
                row_axis_signature(tensor, row),
            )
            for row in tensor.rows
        )

        ordered_signatures = sort!(collect(keys(standard_rows)))
        for left_position in eachindex(ordered_signatures)
            left_signature = ordered_signatures[left_position]
            for right_position in left_position:length(ordered_signatures)
                right_signature = ordered_signatures[right_position]
                standard_entry = continuous_spin_block_entry(
                    assembly,
                    standard,
                    standard.rows[standard_rows[left_signature]],
                    standard.rows[standard_rows[right_signature]],
                )
                tensor_entry = continuous_spin_block_entry(
                    assembly,
                    tensor,
                    tensor.rows[tensor_rows[left_signature]],
                    tensor.rows[tensor_rows[right_signature]],
                )
                left_gauge =
                    standard_orientations[left_signature] *
                    tensor_orientations[left_signature]
                right_gauge =
                    standard_orientations[right_signature] *
                    tensor_orientations[right_signature]
                coefficient_congruence_exact &=
                    standard_entry ==
                    (left_gauge * right_gauge) * tensor_entry
                nonzero_entry_count += !iszero(standard_entry)
                entry_count += 1
            end
        end
    end

    exact =
        dimensions == [36, 36] &&
        row_map_ranks == dimensions &&
        component_rows_canonical &&
        all(==(2), component_squared_norms) &&
        coefficient_congruence_exact &&
        nonzero_entry_count > 0
    return (
        exact=exact,
        duplicate_cone_dimensions=dimensions,
        row_map_ranks=row_map_ranks,
        component_rows_canonical=component_rows_canonical,
        component_squared_norms=sort!(unique(component_squared_norms)),
        coefficient_congruence_exact=coefficient_congruence_exact,
        coefficient_entry_count=entry_count,
        nonzero_coefficient_entry_count=nonzero_entry_count,
        proportionality_factor=ExactRational(1),
    )
end

struct ContinuousSpinConeReducedPrimalAssembly{A}
    schema::String
    source::A
    positive_blocks::Vector{FullSpinIsotypicPSDBlock}
    gap_blocks::Vector{FullSpinIsotypicPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function continuous_spin_cone_block_entry(
    assembly::ContinuousSpinConeReducedPrimalAssembly,
    block::FullSpinIsotypicPSDBlock,
    left::FullSpinIsotypicCombinationRow,
    right::FullSpinIsotypicCombinationRow,
)
    return continuous_spin_block_entry(
        assembly.source,
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

function assemble_continuous_spin_cone_reduced_primal(
    source::ContinuousSpinReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ?
        continuous_spin_l2_cone_redundancy_truth(source) :
        nothing
    if verify_truth
        something(truth).exact ||
            error("continuous-spin l=2 cone-redundancy truth gate failed")
    end

    positive_blocks = filter(
        block -> block.kind != :s3_standard_representative,
        source.positive_blocks,
    )
    gap_blocks = copy(source.gap_blocks)
    equalities = copy(source.equalities)
    provisional = ContinuousSpinConeReducedPrimalAssembly(
        CONTINUOUS_SPIN_CONE_REDUCTION_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        source.moments,
        "",
        "",
    )

    used_moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for block in [positive_blocks; gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = continuous_spin_cone_block_entry(
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
    used_moments == Set(source.moments) ||
        error("continuous-spin cone reduction left unused moment pivots")

    coefficient_sha256 = fingerprint_records(
        "continuous-spin-l2-cone-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "continuous-spin-l2-cone-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    block_records = String[
        block_label(block) * ":" * string(length(block.rows))
        for block in [positive_blocks; gap_blocks]
    ]
    final_sha256 = fingerprint_records(
        CONTINUOUS_SPIN_CONE_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "equalities=" * equality_sha256,
            "moments=" * join(
                (key.canonical for key in source.moments),
                "\n",
            ),
            "blocks=" * join(block_records, "\n"),
            "coefficients=" * coefficient_sha256,
        ],
    )
    return ContinuousSpinConeReducedPrimalAssembly(
        CONTINUOUS_SPIN_CONE_REDUCTION_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        source.moments,
        coefficient_sha256,
        final_sha256,
    )
end

triangle_count(dimension::Int) =
    dimension * (dimension + 1) ÷ 2

function continuous_spin_cone_reduced_assembly_report(
    assembly::ContinuousSpinConeReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    dimensions = [positive_dimensions; gap_dimensions]
    return (
        continuous_spin_moments=length(assembly.moments),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        real_psd_triangle_entries=sum(triangle_count, dimensions),
        maximum_psd_side_dimension=maximum(dimensions),
        coefficient_map_sha256=assembly.coefficient_map_sha256,
        assembly_sha256=assembly.assembly_sha256,
    )
end

end
