module ShastryFullStateSpinIsotypicReduction

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
using ..ShastryFullStateSpatialReduction:
    ShastrySpatialPSDBlock
using ..ShastryFullStateSpinSpatialReduction:
    SpinAxisPermutation,
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
       shastry_spin_stabilizer_structure,
       shastry_spin_stabilizer_coefficient_truth,
       shastry_spin_l2_congruence_structure,
       shastry_spin_l2_congruence_truth,
       shastry_spin_isotypic_block_entry,
       assemble_shastry_full_state_spin_isotypic_reduced_primal,
       shastry_full_state_spin_isotypic_reduced_assembly_report

const SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA =
    "shastry-sutherland-full-state-spin-isotypic-v1"
const TRIVIAL_CHARACTER = V4Character(false, false)
const CoefficientRowPayload = NamedTuple{
    (:moments, :bytes),
    Tuple{Set{MomentKey},Vector{UInt8}},
}

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
        kind in (
            :s3_trivial,
            :s3_standard,
            :v4_orbit_representative,
            :s3_stabilizer_plus_l2,
            :s3_stabilizer_minus_l1,
        ) ||
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

function nontrivial_character_stabilizer(block::ShastrySpatialPSDBlock)
    character = block.source_block.character
    character == TRIVIAL_CHARACTER &&
        throw(ArgumentError("the trivial character has no selected stabilizer"))
    identity = first(SPIN_AXIS_PERMUTATIONS)
    candidates = SpinAxisPermutation[
        permutation
        for permutation in SPIN_AXIS_PERMUTATIONS
        if permutation != identity &&
           spin_character(character, permutation) == character
    ]
    length(candidates) == 1 ||
        error("a nontrivial V4 character does not have one S3 stabilizer")
    return only(candidates)
end

"""
Split one nontrivial-V4 row space under its order-two S3 stabilizer.

The plus rows carry the off-diagonal component of spin `l=2`; the minus rows
carry spin `l=1`. This routine proves only the signed-involution row
decomposition. Coefficient cross-zero and continuous-spin cone congruence are
separate truth gates.
"""
function stabilizer_isotypic_rows(block::ShastrySpatialPSDBlock)
    permutation = nontrivial_character_stabilizer(block)
    targets, signs = spatial_row_action(block, block, permutation)
    all(targets[targets[index]] == index for index in eachindex(targets)) ||
        error("nontrivial-character stabilizer is not an involution")
    all(
        signs[index] * signs[targets[index]] == 1
        for index in eachindex(signs)
    ) || error("nontrivial-character stabilizer has inconsistent signs")

    visited = falses(length(block.rows))
    plus = ShastrySpinIsotypicRow[]
    minus = ShastrySpinIsotypicRow[]
    for start in eachindex(block.rows)
        visited[start] && continue
        target = targets[start]
        if target == start
            destination = signs[start] == 1 ? plus : minus
            push!(destination, ShastrySpinIsotypicRow([start], [1]))
            visited[start] = true
            continue
        end
        visited[target] && error("stabilizer row orbits overlap")
        gauge = signs[start]
        push!(
            plus,
            ShastrySpinIsotypicRow([start, target], [1, gauge]),
        )
        push!(
            minus,
            ShastrySpinIsotypicRow([start, target], [1, -gauge]),
        )
        visited[start] = true
        visited[target] = true
    end
    length(block.rows) == length(plus) + length(minus) ||
        error("stabilizer eigenspace dimensions do not span the source")
    return (plus=plus, minus=minus, permutation=permutation)
end

"""Inventory the exact S3-stabilizer split before coefficient work."""
function shastry_spin_stabilizer_structure(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
)
    standard_dimensions = Dict{Tuple{Symbol,Symbol,Symbol},Int}()
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        block.source_block.character == TRIVIAL_CHARACTER || continue
        decomposition = trivial_isotypic_rows(block)
        standard_dimensions[block_group_key(block)] =
            length(decomposition.standard_minus)
    end

    records = NamedTuple[]
    dimensions_match = true
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        block.source_block.character == TRIVIAL_CHARACTER && continue
        decomposition = stabilizer_isotypic_rows(block)
        key = block_group_key(block)
        standard_dimension = get(standard_dimensions, key, 0)
        dimensions_match &= length(decomposition.plus) == standard_dimension
        character = block.source_block.character
        push!(records, (
            role=block.source_block.role,
            family=block.source_block.family,
            character_rx=character.rx,
            character_ry=character.ry,
            spatial_parity=block.parity,
            source_dimension=length(block.rows),
            spin_l2_plus_dimension=length(decomposition.plus),
            spin_l1_minus_dimension=length(decomposition.minus),
            standard_l2_dimension=standard_dimension,
        ))
    end
    return (
        exact=dimensions_match && !isempty(records),
        dimensions_match=dimensions_match,
        records=records,
    )
end

"""
Replay every `l=1`/`l=2` cross coefficient inside each nontrivial character.

This is deliberately separate from the cheap row-structure gate: matching
eigenspace dimensions does not authorize a PSD block split. A passing result
proves the affine matrix is block diagonal after the existing exact
spin/spatial moment quotient, without identifying different V4 characters.
"""
function shastry_spin_stabilizer_coefficient_truth(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
)
    blocks = ShastrySpatialPSDBlock[
        block
        for block in [assembly.positive_blocks; assembly.gap_blocks]
        if block.source_block.character != TRIVIAL_CHARACTER
    ]
    decompositions = stabilizer_isotypic_rows.(blocks)
    work = Tuple{Int,Int}[
        (block_index, plus_index)
        for (block_index, decomposition) in enumerate(decompositions)
        for plus_index in eachindex(decomposition.plus)
    ]
    row_results = Vector{NamedTuple{(:exact, :count),Tuple{Bool,Int}}}(
        undef,
        length(work),
    )
    Threads.@threads :dynamic for work_index in eachindex(work)
        block_index, plus_index = work[work_index]
        block = blocks[block_index]
        decomposition = decompositions[block_index]
        plus_row = decomposition.plus[plus_index]
        exact = true
        for minus_row in decomposition.minus
            exact &= iszero(
                combined_block_entry(
                    assembly,
                    block,
                    plus_row,
                    minus_row,
                ),
            )
        end
        row_results[work_index] = (
            exact=exact,
            count=length(decomposition.minus),
        )
    end

    block_exact = trues(length(blocks))
    block_counts = zeros(Int, length(blocks))
    for (work_index, (block_index, _)) in enumerate(work)
        result = row_results[work_index]
        block_exact[block_index] &= result.exact
        block_counts[block_index] += result.count
    end
    records = NamedTuple[]
    for (block_index, block) in enumerate(blocks)
        source = block.source_block
        character = source.character
        push!(records, (
            role=source.role,
            family=source.family,
            character_rx=character.rx,
            character_ry=character.ry,
            spatial_parity=block.parity,
            cross_zero=block_exact[block_index],
            cross_entry_count=block_counts[block_index],
        ))
    end
    return (
        exact=all(block_exact),
        cross_zero=all(block_exact),
        cross_entry_count=sum(block_counts),
        records=records,
    )
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

spin_blind_word_signature(word) =
    Tuple(site for (site, _) in word.ops)

function spin_blind_full_row_signature(row)
    state_symbols = sort!(
        spin_blind_word_signature.(row.source.state_symbols);
        by=string,
    )
    return (
        family=row.family,
        state_symbols=Tuple(state_symbols),
        operator_word=spin_blind_word_signature(row.source.operator_word),
    )
end

function spin_blind_spatial_row_signature(
    block::ShastrySpatialPSDBlock,
    row,
)
    combined = Dict{Any,Int}()
    for (source_index, coefficient) in
        zip(row.source_indices, row.coefficients)
        signature = spin_blind_full_row_signature(
            block.source_block.rows[source_index],
        )
        combined[signature] = get(combined, signature, 0) + coefficient
    end
    filter!(pair -> !iszero(last(pair)), combined)
    isempty(combined) && error("spin-blind spatial row cancels exactly")
    records = sort!(
        collect(combined);
        by=pair -> string(first(pair)),
    )
    coefficients = Int[last(pair) for pair in records]
    divisor = foldl(gcd, abs.(coefficients); init=0)
    divisor > 0 || error("spin-blind spatial row has zero divisor")
    coefficients .÷= divisor
    first(coefficients) < 0 && (coefficients .*= -1)
    return Tuple(
        (first(record), coefficient)
        for (record, coefficient) in zip(records, coefficients)
    )
end

function spin_l2_multiplicity_signature(
    block::ShastrySpinIsotypicPSDBlock,
    row::ShastrySpinIsotypicRow,
)
    signatures = unique(
        spin_blind_spatial_row_signature(
            block.source_block,
            block.source_block.rows[source_index],
        )
        for source_index in row.source_indices
    )
    length(signatures) == 1 || error(
        "one spin-l2 row mixes spin-blind multiplicity signatures",
    )
    return only(signatures)
end

function spin_isotypic_row_norm_squared(
    block::ShastrySpinIsotypicPSDBlock,
    row::ShastrySpinIsotypicRow,
)
    expanded = Dict{Int,Int}()
    for (spatial_index, spin_coefficient) in
        zip(row.source_indices, row.coefficients)
        spatial_row = block.source_block.rows[spatial_index]
        for (source_index, spatial_coefficient) in
            zip(spatial_row.source_indices, spatial_row.coefficients)
            expanded[source_index] =
                get(expanded, source_index, 0) +
                spin_coefficient * spatial_coefficient
        end
    end
    filter!(pair -> !iszero(last(pair)), expanded)
    norm_squared = sum(coefficient^2 for coefficient in values(expanded))
    norm_squared > 0 || error("spin-isotypic row has zero exact norm")
    return norm_squared
end

function exact_positive_rational_square_root(value::ExactRational)
    value > 0 || error("row-norm ratio must be positive")
    numerator_root = isqrt(numerator(value))
    denominator_root = isqrt(denominator(value))
    numerator_root^2 == numerator(value) || return nothing
    denominator_root^2 == denominator(value) || return nothing
    return ExactRational(numerator_root, denominator_root)
end

spin_aware_word_signature(word) =
    Tuple((site, Int(axis)) for (site, axis) in word.ops)

function spin_aware_full_row_signature(row)
    state_symbols = sort!(
        spin_aware_word_signature.(row.source.state_symbols);
        by=string,
    )
    return (
        family=row.family,
        state_symbols=Tuple(state_symbols),
        operator_word=spin_aware_word_signature(row.source.operator_word),
    )
end

function spin_isotypic_expanded_signature(
    block::ShastrySpinIsotypicPSDBlock,
    row::ShastrySpinIsotypicRow,
)
    expanded = Dict{Any,Int}()
    full_rows = block.source_block.source_block.rows
    for (spatial_index, spin_coefficient) in
        zip(row.source_indices, row.coefficients)
        spatial_row = block.source_block.rows[spatial_index]
        for (source_index, spatial_coefficient) in
            zip(spatial_row.source_indices, spatial_row.coefficients)
            signature = spin_aware_full_row_signature(full_rows[source_index])
            expanded[signature] =
                get(expanded, signature, 0) +
                spin_coefficient * spatial_coefficient
        end
    end
    filter!(pair -> !iszero(last(pair)), expanded)
    records = sort!(collect(expanded); by=pair -> string(first(pair)))
    return join(
        (string(last(record), "*", first(record)) for record in records),
        ";",
    )
end


function exact_polynomial_ratio(
    target::ExactLinearPolynomial,
    reference::ExactLinearPolynomial,
)
    if iszero(target) && iszero(reference)
        return (compatible=true, informative=false, scale=nothing)
    end
    (iszero(target) || iszero(reference)) &&
        return (compatible=false, informative=true, scale=nothing)
    key = first(sort!(collect(keys(reference.terms))))
    haskey(target.terms, key) ||
        return (compatible=false, informative=true, scale=nothing)
    quotient = target.terms[key] / reference.terms[key]
    iszero(imag(quotient)) ||
        return (compatible=false, informative=true, scale=nothing)
    scale = real(quotient)
    target == scale * reference ||
        return (compatible=false, informative=true, scale=nothing)
    return (compatible=true, informative=true, scale=scale)
end


"""
Try an exact signed permutation and rational rescaling of only the rows whose
naive norm ratios are nonunit. Ordinary rows remain fixed. This is a complete
PSD congruence proof when it succeeds: ordinary/ordinary entries have already
passed, candidate construction checks every exceptional/ordinary entry, and
the final backtracking check replays every exceptional/exceptional entry.
"""
function exceptional_spin_l2_permutation_congruence(
    assembly,
    group,
    norm_ratios::Vector{ExactRational};
    project::Function=identity,
)
    exceptional_targets = findall(!=(one(ExactRational)), norm_ratios)
    isempty(exceptional_targets) && return (
        exact=false,
        solution_count=0,
        exceptional_target_rows="",
        exceptional_reference_rows="",
        candidate_inventory="",
        solution_inventory="",
        target_signatures="",
        reference_signatures="",
    )
    ordinary_targets = setdiff(eachindex(norm_ratios), exceptional_targets)
    exceptional_references = sort!(group.mapping[exceptional_targets])

    target_cross = Dict{Tuple{Int,Int},ExactLinearPolynomial}()
    reference_cross = Dict{Tuple{Int,Int},ExactLinearPolynomial}()
    for target_row in exceptional_targets, ordinary_row in ordinary_targets
        target_cross[(target_row, ordinary_row)] = project(
            shastry_spin_isotypic_block_entry(
                assembly,
                group.target,
                group.target.rows[target_row],
                group.target.rows[ordinary_row],
            ),
        )
    end
    for reference_row in exceptional_references,
        ordinary_row in ordinary_targets
        reference_cross[(reference_row, ordinary_row)] = project(
            shastry_spin_isotypic_block_entry(
                assembly,
                group.reference,
                group.reference.rows[reference_row],
                group.reference.rows[group.mapping[ordinary_row]],
            ),
        )
    end

    target_special = Dict{Tuple{Int,Int},ExactLinearPolynomial}()
    reference_special = Dict{Tuple{Int,Int},ExactLinearPolynomial}()
    for (position, left) in enumerate(exceptional_targets),
        right in exceptional_targets[position:end]
        target_special[(min(left, right), max(left, right))] = project(
            shastry_spin_isotypic_block_entry(
                assembly,
                group.target,
                group.target.rows[left],
                group.target.rows[right],
            ),
        )
    end
    for (position, left) in enumerate(exceptional_references),
        right in exceptional_references[position:end]
        reference_special[(min(left, right), max(left, right))] = project(
            shastry_spin_isotypic_block_entry(
                assembly,
                group.reference,
                group.reference.rows[left],
                group.reference.rows[right],
            ),
        )
    end

    candidates = Dict{Int,Vector{NamedTuple{(:reference, :scale),Tuple{Int,ExactRational}}}}()
    for target_row in exceptional_targets
        row_candidates = NamedTuple{(:reference, :scale),Tuple{Int,ExactRational}}[]
        for reference_row in exceptional_references
            candidate_scale = nothing
            compatible = true
            for ordinary_row in ordinary_targets
                relation = exact_polynomial_ratio(
                    target_cross[(target_row, ordinary_row)],
                    reference_cross[(reference_row, ordinary_row)],
                )
                if !relation.compatible
                    compatible = false
                    break
                elseif relation.informative
                    if isnothing(candidate_scale)
                        candidate_scale = relation.scale
                    elseif candidate_scale != relation.scale
                        compatible = false
                        break
                    end
                end
            end
            compatible && !isnothing(candidate_scale) &&
                !iszero(something(candidate_scale)) || continue
            target_diagonal = target_special[(target_row, target_row)]
            reference_diagonal =
                reference_special[(reference_row, reference_row)]
            target_diagonal ==
                something(candidate_scale)^2 * reference_diagonal || continue
            push!(
                row_candidates,
                (reference=reference_row, scale=something(candidate_scale)),
            )
        end
        candidates[target_row] = row_candidates
    end

    ordered_targets = sort!(copy(exceptional_targets))
    selected_references = Dict{Int,Int}()
    selected_scales = Dict{Int,ExactRational}()
    used_references = Set{Int}()
    solutions = String[]
    function search(position::Int)
        length(solutions) >= 2 && return
        if position > length(ordered_targets)
            for (left_position, left) in enumerate(ordered_targets),
                right in ordered_targets[left_position:end]
                reference_left = selected_references[left]
                reference_right = selected_references[right]
                target_entry = target_special[(min(left, right), max(left, right))]
                reference_entry = reference_special[
                    (min(reference_left, reference_right),
                     max(reference_left, reference_right))
                ]
                target_entry ==
                    selected_scales[left] * selected_scales[right] *
                    reference_entry || return
            end
            push!(
                solutions,
                join(
                    (
                        string(
                            target,
                            "=>",
                            selected_references[target],
                            "@",
                            selected_scales[target],
                        )
                        for target in ordered_targets
                    ),
                    ",",
                ),
            )
            return
        end
        target = ordered_targets[position]
        for candidate in candidates[target]
            candidate.reference in used_references && continue
            pair_compatible = all(
                target_special[(min(target, previous), max(target, previous))] ==
                candidate.scale * selected_scales[previous] *
                reference_special[
                    (
                        min(candidate.reference, selected_references[previous]),
                        max(candidate.reference, selected_references[previous]),
                    )
                ]
                for previous in keys(selected_references)
            )
            pair_compatible || continue
            selected_references[target] = candidate.reference
            selected_scales[target] = candidate.scale
            push!(used_references, candidate.reference)
            search(position + 1)
            delete!(used_references, candidate.reference)
            delete!(selected_references, target)
            delete!(selected_scales, target)
        end
    end
    search(1)

    candidate_inventory = join(
        (
            string(
                target,
                "=>",
                join(
                    (
                        string(candidate.reference, "@", candidate.scale)
                        for candidate in candidates[target]
                    ),
                    "|",
                ),
            )
            for target in ordered_targets
        ),
        ",",
    )
    target_signatures = join(
        (
            string(
                target,
                "=",
                spin_isotypic_expanded_signature(
                    group.target,
                    group.target.rows[target],
                ),
            )
            for target in ordered_targets
        ),
        "\n",
    )
    reference_signatures = join(
        (
            string(
                reference,
                "=",
                spin_isotypic_expanded_signature(
                    group.reference,
                    group.reference.rows[reference],
                ),
            )
            for reference in exceptional_references
        ),
        "\n",
    )
    return (
        exact=!isempty(solutions),
        solution_count=length(solutions),
        exceptional_target_rows=join(ordered_targets, ","),
        exceptional_reference_rows=join(exceptional_references, ","),
        candidate_inventory=candidate_inventory,
        solution_inventory=join(solutions, ";"),
        target_signatures=target_signatures,
        reference_signatures=reference_signatures,
    )
end

function spin_l2_congruence_groups(assembly)
    blocks = [assembly.positive_blocks; assembly.gap_blocks]
    references = Dict{Tuple{Symbol,Symbol,Symbol},Any}()
    targets = Dict{Tuple{Symbol,Symbol,Symbol},Vector{Any}}()
    for block in blocks
        key = block_group_key(block.source_block)
        if block.kind == :s3_standard
            haskey(references, key) &&
                error("multiple S3-standard blocks in one l2 group")
            references[key] = block
        elseif block.kind == :s3_stabilizer_plus_l2
            push!(get!(targets, key, Any[]), block)
        end
    end
    isempty(targets) && error("no nontrivial-character l2 cones found")
    groups = NamedTuple[]
    target_count = 0
    for key in sort!(collect(keys(targets)); by=string)
        haskey(references, key) ||
            error("nontrivial l2 cones have no S3-standard reference")
        reference = references[key]
        reference_by_signature = Dict{Any,Int}()
        for (row_index, row) in enumerate(reference.rows)
            signature = spin_l2_multiplicity_signature(reference, row)
            haskey(reference_by_signature, signature) && error(
                "S3-standard l2 multiplicity signatures are not unique",
            )
            reference_by_signature[signature] = row_index
        end
        group_targets = sort!(
            targets[key];
            by=block -> (
                block.source_block.source_block.character.rx,
                block.source_block.source_block.character.ry,
            ),
        )
        length(group_targets) == 3 || error(
            "an l2 congruence group does not contain three nontrivial characters",
        )
        for target in group_targets
            length(target.rows) == length(reference.rows) || error(
                "l2 target and S3-standard dimensions differ",
            )
            mapping = Int[]
            for row in target.rows
                signature = spin_l2_multiplicity_signature(target, row)
                haskey(reference_by_signature, signature) || error(
                    "l2 target signature has no S3-standard reference",
                )
                push!(mapping, reference_by_signature[signature])
            end
            length(unique(mapping)) == length(mapping) || error(
                "l2 target-to-reference row map is not bijective",
            )
            character = target.source_block.source_block.character
            push!(groups, (
                role=key[1],
                family=key[2],
                spatial_parity=key[3],
                character_rx=character.rx,
                character_ry=character.ry,
                reference=reference,
                target=target,
                mapping=mapping,
            ))
            target_count += 1
        end
    end
    return groups, target_count
end

"""Prove a bijective spin-blind multiplicity map for every discrete l=2 cone."""
function shastry_spin_l2_congruence_structure(
    assembly,
)
    groups, target_count = spin_l2_congruence_groups(assembly)
    records = [(
        role=group.role,
        family=group.family,
        spatial_parity=group.spatial_parity,
        character_rx=group.character_rx,
        character_ry=group.character_ry,
        dimension=length(group.mapping),
        mapping_bijective=length(unique(group.mapping)) ==
                           length(group.mapping),
    ) for group in groups]
    return (
        exact=!isempty(records) && target_count == length(records) &&
              all(record.mapping_bijective for record in records),
        target_block_count=target_count,
        records=records,
    )
end

"""
Compare every mapped l=2 coefficient after an optional exact projection.

The target and reference rows may have different exact integer norms. The
tested diagonal congruence uses the positive row scale
`sqrt(target_norm_squared / reference_norm_squared)`. When a scale product is
irrational, the corresponding rational polynomial entries must both vanish.
Opposite-sign matches remain diagnostic only and are never accepted.
"""
function shastry_spin_l2_congruence_truth(
    assembly;
    project::Function=identity,
    progress_callback::Function=message -> nothing,
)
    groups, _ = spin_l2_congruence_groups(assembly)
    records = NamedTuple[]
    exact = true
    for group in groups
        dimension = length(group.mapping)
        norm_ratios = ExactRational[
            ExactRational(
                spin_isotypic_row_norm_squared(
                    group.target,
                    group.target.rows[row],
                ),
                spin_isotypic_row_norm_squared(
                    group.reference,
                    group.reference.rows[group.mapping[row]],
                ),
            )
            for row in 1:dimension
        ]
        ratio_counts = Dict{String,Int}()
        for ratio in norm_ratios
            label = string(ratio)
            ratio_counts[label] = get(ratio_counts, label, 0) + 1
        end
        ratio_inventory = join(
            (
                label * ":" * string(ratio_counts[label])
                for label in sort!(collect(keys(ratio_counts)))
            ),
            ",",
        )
        row_results = Vector{NamedTuple{
            (
                :unit_equal,
                :scaled,
                :zero_irrational,
                :opposite,
                :unmatched,
                :ordinary_failure,
            ),
            Tuple{Int,Int,Int,Int,Int,Int},
        }}(undef, dimension)
        Threads.@threads :dynamic for row in 1:dimension
            unit_equal = 0
            scaled = 0
            zero_irrational = 0
            opposite = 0
            unmatched = 0
            ordinary_failure = 0
            reference_row = group.mapping[row]
            for column in row:dimension
                target_entry = project(
                    shastry_spin_isotypic_block_entry(
                        assembly,
                        group.target,
                        group.target.rows[row],
                        group.target.rows[column],
                    ),
                )
                reference_entry = project(
                    shastry_spin_isotypic_block_entry(
                        assembly,
                        group.reference,
                        group.reference.rows[reference_row],
                        group.reference.rows[group.mapping[column]],
                    ),
                )
                factor = exact_positive_rational_square_root(
                    norm_ratios[row] * norm_ratios[column],
                )
                if isnothing(factor)
                    if iszero(target_entry) && iszero(reference_entry)
                        zero_irrational += 1
                    else
                        unmatched += 1
                        ordinary_failure +=
                            norm_ratios[row] == 1 &&
                            norm_ratios[column] == 1
                    end
                else
                    expected = something(factor) * reference_entry
                    if target_entry == expected
                        if something(factor) == 1
                            unit_equal += 1
                        else
                            scaled += 1
                        end
                    elseif target_entry == -1 * expected
                        opposite += 1
                        ordinary_failure +=
                            norm_ratios[row] == 1 &&
                            norm_ratios[column] == 1
                    else
                        unmatched += 1
                        ordinary_failure +=
                            norm_ratios[row] == 1 &&
                            norm_ratios[column] == 1
                    end
                end
            end
            row_results[row] = (
                unit_equal=unit_equal,
                scaled=scaled,
                zero_irrational=zero_irrational,
                opposite=opposite,
                unmatched=unmatched,
                ordinary_failure=ordinary_failure,
            )
        end
        unit_equal_count =
            sum(result.unit_equal for result in row_results)
        scaled_count = sum(result.scaled for result in row_results)
        zero_irrational_count =
            sum(result.zero_irrational for result in row_results)
        opposite_count = sum(result.opposite for result in row_results)
        unmatched_count = sum(result.unmatched for result in row_results)
        ordinary_failure_count =
            sum(result.ordinary_failure for result in row_results)
        entry_count = unit_equal_count + scaled_count +
                      zero_irrational_count + opposite_count +
                      unmatched_count
        direct_exact = opposite_count == 0 && unmatched_count == 0
        repair = (
            exact=false,
            solution_count=0,
            exceptional_target_rows="",
            exceptional_reference_rows="",
            candidate_inventory="",
            solution_inventory="",
            target_signatures="",
            reference_signatures="",
        )
        if !direct_exact && ordinary_failure_count == 0 &&
           any(!=(one(ExactRational)), norm_ratios)
            repair = exceptional_spin_l2_permutation_congruence(
                assembly,
                group,
                norm_ratios;
                project=project,
            )
        end
        block_exact = direct_exact || repair.exact
        resolved_count = repair.exact ? opposite_count + unmatched_count : 0
        final_opposite_count = repair.exact ? 0 : opposite_count
        final_unmatched_count = repair.exact ? 0 : unmatched_count
        exact &= block_exact
        push!(records, (
            role=group.role,
            family=group.family,
            spatial_parity=group.spatial_parity,
            character_rx=group.character_rx,
            character_ry=group.character_ry,
            dimension=dimension,
            row_norm_ratio_inventory=ratio_inventory,
            exact=block_exact,
            direct_exact=direct_exact,
            entry_count=entry_count,
            unit_equal_count=unit_equal_count,
            scaled_count=scaled_count,
            zero_irrational_count=zero_irrational_count,
            direct_opposite_count=opposite_count,
            direct_unmatched_count=unmatched_count,
            ordinary_failure_count=ordinary_failure_count,
            exceptional_permutation_exact=repair.exact,
            exceptional_solution_count=repair.solution_count,
            exceptional_target_rows=repair.exceptional_target_rows,
            exceptional_reference_rows=repair.exceptional_reference_rows,
            exceptional_candidate_inventory=repair.candidate_inventory,
            exceptional_solution_inventory=repair.solution_inventory,
            exceptional_target_signatures=repair.target_signatures,
            exceptional_reference_signatures=repair.reference_signatures,
            resolved_count=resolved_count,
            opposite_count=final_opposite_count,
            unmatched_count=final_unmatched_count,
        ))
        progress_callback(
            "SO(3) l2 congruence block $(length(records))/$(length(groups)); " *
            "dimension=$dimension, unit_equal=$unit_equal_count, " *
            "scaled=$scaled_count, zero_irrational=$zero_irrational_count, " *
            "direct_opposite=$opposite_count, " *
            "direct_unmatched=$unmatched_count, " *
            "exceptional_permutation=$(repair.exact), " *
            "final_unmatched=$final_unmatched_count",
        )
    end
    return (
        exact=exact && !isempty(records),
        target_block_count=length(records),
        entry_count=sum(record.entry_count for record in records),
        unit_equal_count=
            sum(record.unit_equal_count for record in records),
        scaled_count=sum(record.scaled_count for record in records),
        zero_irrational_count=
            sum(record.zero_irrational_count for record in records),
        direct_opposite_count=
            sum(record.direct_opposite_count for record in records),
        direct_unmatched_count=
            sum(record.direct_unmatched_count for record in records),
        resolved_count=sum(record.resolved_count for record in records),
        opposite_count=sum(record.opposite_count for record in records),
        unmatched_count=sum(record.unmatched_count for record in records),
        records=records,
    )
end

function retained_blocks(
    blocks::Vector{ShastrySpatialPSDBlock};
    stabilizer_split::Bool=false,
    so3_l2_dedup::Bool=false,
)
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
        elseif stabilizer_split
            decomposition = stabilizer_isotypic_rows(block)
            isempty(decomposition.plus) || so3_l2_dedup || push!(
                result,
                ShastrySpinIsotypicPSDBlock(
                    block,
                    :s3_stabilizer_plus_l2,
                    decomposition.plus,
                ),
            )
            isempty(decomposition.minus) || push!(
                result,
                ShastrySpinIsotypicPSDBlock(
                    block,
                    :s3_stabilizer_minus_l1,
                    decomposition.minus,
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
    context = SHA2_256_CTX()
    update_framed!(context, schema)
    for record in records
        update_framed!(context, record)
    end
    return bytes2hex(digest!(context))
end

function write_framed_record!(io::IO, value)
    serialized = string(value)
    write(io, string(ncodeunits(serialized)), ":", serialized)
    return io
end

function update_framed!(context::SHA2_256_CTX, value)
    io = IOBuffer()
    write_framed_record!(io, value)
    update!(context, take!(io))
    return context
end

function coefficient_row_payload(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block::ShastrySpinIsotypicPSDBlock,
    row::Int,
)
    moments = Set{MomentKey}()
    payload = IOBuffer()
    for column in row:length(block.rows)
        polynomial = shastry_spin_isotypic_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        union!(moments, keys(polynomial.terms))
        write_framed_record!(
            payload,
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
    return (moments=moments, bytes=take!(payload))
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
    stabilizer_split::Bool=false,
    so3_l2_dedup::Bool=false,
)
    so3_l2_dedup && !stabilizer_split && error(
        "SO(3) l2 cone deduplication requires the stabilizer split",
    )
    truth = verify_truth ? shastry_spin_isotypic_truth(source) : nothing
    verify_truth && !something(truth).exact &&
        error("Shastry spin-isotypic truth gate failed")
    positive_blocks = retained_blocks(
        source.positive_blocks;
        stabilizer_split=stabilizer_split,
        so3_l2_dedup=so3_l2_dedup,
    )
    gap_blocks = retained_blocks(
        source.gap_blocks;
        stabilizer_split=stabilizer_split,
        so3_l2_dedup=so3_l2_dedup,
    )
    equalities = canonical_real_equalities(copy(source.equalities))
    schema = so3_l2_dedup ?
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA *
        "-nontrivial-stabilizer-so3-l2-dedup-v1" :
        stabilizer_split ?
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA *
        "-nontrivial-stabilizer-v1" :
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA
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
            schema,
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
            schema,
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
        schema,
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
    work = Tuple{Int,Int}[
        (block_index, row)
        for (block_index, block) in enumerate(all_blocks)
        for row in eachindex(block.rows)
    ]
    coefficient_context = SHA2_256_CTX()
    update_framed!(
        coefficient_context,
        "shastry-full-state-spin-isotypic-coefficients-v1",
    )
    batch_size = max(64, 4 * Threads.nthreads())
    for batch_start in firstindex(work):batch_size:lastindex(work)
        batch_stop = min(batch_start + batch_size - 1, lastindex(work))
        payloads = Vector{CoefficientRowPayload}(
            undef,
            batch_stop - batch_start + 1,
        )
        Threads.@threads :dynamic for offset in eachindex(payloads)
            block_index, row = work[batch_start + offset - 1]
            payloads[offset] = coefficient_row_payload(
                provisional,
                all_blocks[block_index],
                row,
            )
        end
        for payload in payloads
            union!(used_moments, payload.moments)
            update!(coefficient_context, payload.bytes)
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
        error("identity moment is not first after spin-isotypic reduction")
    coefficient_sha256 = bytes2hex(digest!(coefficient_context))
    assembly_sha256 = fingerprint_records(
        schema,
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
        schema,
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
