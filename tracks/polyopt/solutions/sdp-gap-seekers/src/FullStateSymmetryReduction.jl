module FullStateSymmetryReduction

using SHA
using ..SquareJ1J2Prototype:
    PauliWord
using ..GenericGapModel:
    StateMonomial,
    state_monomial_degree,
    state_monomial_string
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key,
    moment_degree,
    positive_entry,
    gap_entry,
    polynomial_sha256,
    real_part_polynomial
using ..PrimalGapAssembly:
    PrimalAssembly
using ..ExactSymmetryReduction:
    V4Character,
    V4_CHARACTERS,
    v4_character,
    v4_invariant_projection,
    canonical_real_equalities
using ..ConjugationSymmetryReduction:
    conjugation_action,
    conjugation_invariant_projection,
    equality_space_is_invariant

export FULL_STATE_V4_REDUCTION_SCHEMA,
       FULL_STATE_REAL_REDUCTION_SCHEMA,
       FullStateReducedRow,
       FullStatePSDBlock,
       FullStateV4ReducedPrimalAssembly,
       FullStateRealReducedPrimalAssembly,
       scalarized_row,
       full_state_centered_entry,
       full_state_v4_block_entry,
       full_state_real_block_entry,
       full_state_v4_reduction_truth,
       full_state_conjugation_reduction_truth,
       assemble_full_state_v4_reduced_primal,
       assemble_full_state_real_reduced_primal,
       full_state_v4_reduced_assembly_report,
       full_state_real_reduced_assembly_report

const FULL_STATE_V4_REDUCTION_SCHEMA =
    "primal-gap-full-state-exact-v4-reduction-v1"
const FULL_STATE_REAL_REDUCTION_SCHEMA =
    "primal-gap-full-state-exact-v4-conjugation-real-reduction-v1"

"""
One row after the general centered/scalar congruence.

For a source row `q*v`, `:centered` represents
`q*(v-zeta(v)I)`. `:scalar` represents an original pure scalar row, and
`:gap_active` retains a nonidentity gap row.
"""
struct FullStateReducedRow
    family::Symbol
    source::StateMonomial

    function FullStateReducedRow(
        family::Symbol,
        source::StateMonomial,
    )
        family in (:centered, :scalar, :gap_active) ||
            throw(ArgumentError("unsupported full-state row family"))
        operator_is_identity = isempty(source.operator_word.ops)
        family == :scalar && !operator_is_identity &&
            throw(ArgumentError("a scalar row must have identity operator part"))
        family in (:centered, :gap_active) && operator_is_identity &&
            throw(ArgumentError("an active row needs a nonidentity operator part"))
        new(
            family,
            StateMonomial(source.state_symbols, source.operator_word),
        )
    end
end

Base.:(==)(left::FullStateReducedRow, right::FullStateReducedRow) =
    left.family == right.family && left.source == right.source
Base.hash(row::FullStateReducedRow, seed::UInt) =
    hash(row.source, hash(row.family, seed))

struct FullStatePSDBlock
    role::Symbol
    family::Symbol
    character::V4Character
    rows::Vector{FullStateReducedRow}

    function FullStatePSDBlock(
        role::Symbol,
        family::Symbol,
        character::V4Character,
        rows::Vector{FullStateReducedRow},
    )
        role in (:positive, :gap) ||
            throw(ArgumentError("full-state block role must be positive or gap"))
        expected_families = role == :positive ?
            (:centered, :scalar) :
            (:gap_active,)
        family in expected_families ||
            throw(ArgumentError("row family is incompatible with block role"))
        isempty(rows) &&
            throw(ArgumentError("empty full-state blocks must be omitted"))
        all(row -> row.family == family, rows) ||
            throw(ArgumentError("full-state block mixes row families"))
        all(row -> v4_character(row.source) == character, rows) ||
            throw(ArgumentError("full-state block mixes V4 characters"))
        new(role, family, character, rows)
    end
end

struct FullStateV4ReducedPrimalAssembly{A}
    schema::String
    source::A
    positive_blocks::Vector{FullStatePSDBlock}
    gap_blocks::Vector{FullStatePSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

struct FullStateRealReducedPrimalAssembly{A}
    schema::String
    source::A
    positive_blocks::Vector{FullStatePSDBlock}
    gap_blocks::Vector{FullStatePSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

identity_word() = PauliWord()

"""Move the operator word of a row into its commuting state-symbol multiset."""
function scalarized_row(row::StateMonomial)
    isempty(row.operator_word.ops) && return row
    return StateMonomial(
        [row.state_symbols; row.operator_word],
        identity_word(),
    )
end

"""
Exact entry between `q*(v-zeta(v))` and `r*(w-zeta(w))`.

This is the general state-polynomial version of the one-symbol centered
covariance congruence.
"""
function full_state_centered_entry(
    left::StateMonomial,
    right::StateMonomial,
)
    isempty(left.operator_word.ops) &&
        throw(ArgumentError("left centered row has identity operator"))
    isempty(right.operator_word.ops) &&
        throw(ArgumentError("right centered row has identity operator"))
    left_scalar = scalarized_row(left)
    right_scalar = scalarized_row(right)
    return positive_entry(left, right) -
           positive_entry(left, right_scalar) -
           positive_entry(left_scalar, right) +
           positive_entry(left_scalar, right_scalar)
end

function full_state_centered_scalar_entry(
    centered::StateMonomial,
    scalar::StateMonomial,
)
    isempty(centered.operator_word.ops) &&
        throw(ArgumentError("centered row has identity operator"))
    isempty(scalar.operator_word.ops) ||
        throw(ArgumentError("scalar row has nonidentity operator"))
    return positive_entry(centered, scalar) -
           positive_entry(scalarized_row(centered), scalar)
end

function raw_block_entry(
    source::PrimalAssembly,
    block::FullStatePSDBlock,
    left::FullStateReducedRow,
    right::FullStateReducedRow,
)
    left.family == block.family && right.family == block.family ||
        throw(ArgumentError("row does not belong to the requested block"))
    if block.family == :centered
        return full_state_centered_entry(left.source, right.source)
    elseif block.family == :scalar
        return positive_entry(left.source, right.source)
    end
    return gap_entry(
        left.source,
        right.source,
        source.hamiltonian_terms,
        source.problem.gamma,
    )
end

function full_state_v4_block_entry(
    assembly::FullStateV4ReducedPrimalAssembly,
    block::FullStatePSDBlock,
    left::FullStateReducedRow,
    right::FullStateReducedRow,
)
    polynomial = raw_block_entry(assembly.source, block, left, right)
    projected = v4_invariant_projection(polynomial)
    projected == polynomial ||
        error("same-character full-state block entry was not V4 invariant")
    return projected
end

state_conjugation_odd(row::StateMonomial) =
    isodd(
        count(operation -> operation[2] == 2, row.operator_word.ops) +
        sum(
            word -> count(operation -> operation[2] == 2, word.ops),
            row.state_symbols;
            init=0,
        ),
    )

row_phase(row::FullStateReducedRow) =
    state_conjugation_odd(row.source) ?
    Complex{Int}(0, 1) :
    Complex{Int}(1, 0)

function require_exactly_real(
    polynomial::ExactLinearPolynomial,
    label::String,
)
    all(iszero ∘ imag, values(polynomial.terms)) ||
        error("$label is not exactly real after conjugation gauge")
    return real_part_polynomial(polynomial)
end

function full_state_real_block_entry(
    assembly::FullStateRealReducedPrimalAssembly,
    block::FullStatePSDBlock,
    left::FullStateReducedRow,
    right::FullStateReducedRow,
)
    base = full_state_v4_block_entry(
        assembly.source,
        block,
        left,
        right,
    )
    projected = conjugation_invariant_projection(base)
    gauged = conj(row_phase(left)) * row_phase(right) * projected
    return require_exactly_real(
        gauged,
        string(block.role, "/", block.family),
    )
end

function character_blocks(
    role::Symbol,
    family::Symbol,
    rows::Vector{FullStateReducedRow},
)
    blocks = FullStatePSDBlock[]
    for character in V4_CHARACTERS
        selected = filter(
            row -> v4_character(row.source) == character,
            rows,
        )
        isempty(selected) && continue
        push!(
            blocks,
            FullStatePSDBlock(role, family, character, selected),
        )
    end
    return blocks
end

function gap_facial_data(source::PrimalAssembly)
    null_rows = filter(
        row -> isempty(row.operator_word.ops),
        source.gap_basis.entries,
    )
    active_rows = filter(
        row -> !isempty(row.operator_word.ops),
        source.gap_basis.entries,
    )
    null_block_zero = all(
        iszero(
            gap_entry(
                left,
                right,
                source.hamiltonian_terms,
                source.problem.gamma,
            ),
        )
        for left in null_rows
        for right in null_rows
    )
    cross_polynomials = ExactLinearPolynomial[
        gap_entry(
            null,
            active,
            source.hamiltonian_terms,
            source.problem.gamma,
        )
        for null in null_rows
        for active in active_rows
    ]
    return (
        null_rows=null_rows,
        active_rows=active_rows,
        null_block_zero=null_block_zero,
        cross_polynomials=cross_polynomials,
    )
end

function add_polynomial_moments!(
    moments::Set{MomentKey},
    polynomial::ExactLinearPolynomial,
)
    union!(moments, keys(polynomial.terms))
    return moments
end

function ordered_moments(moments::Set{MomentKey})
    ordered = sort!(
        collect(moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(ordered) == moment_key() ||
        error("identity moment is not first")
    return ordered
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

character_label(character::V4Character) =
    string("rx", Int(character.rx), "-ry", Int(character.ry))

function block_label(block::FullStatePSDBlock)
    return join(
        (
            block.role,
            block.family,
            character_label(block.character),
        ),
        "/",
    )
end

function row_label(row::FullStateReducedRow)
    return string(row.family, ":", state_monomial_string(row.source))
end

function assembly_fingerprint(
    schema::String,
    source_sha256::String,
    blocks::Vector{FullStatePSDBlock},
    equalities::Vector{ExactLinearPolynomial},
    moments::Vector{MomentKey},
    coefficient_map_sha256::String,
)
    records = String[
        "source=" * source_sha256,
        "coefficient_map=" * coefficient_map_sha256,
        "moments=" * fingerprint_records(
            "full-state-reduced-moments-v1",
            (
                string(moment_degree(key), ":", key.canonical)
                for key in moments
            ),
        ),
    ]
    for block in blocks
        push!(records, "block=" * block_label(block))
        append!(records, ("row=" * row_label(row) for row in block.rows))
    end
    append!(
        records,
        (
            "equality=" * polynomial_sha256(polynomial)
            for polynomial in equalities
        ),
    )
    return fingerprint_records(schema, records)
end

function full_state_v4_reduction_truth(source::PrimalAssembly)
    hamiltonian_invariant = all(
        term -> v4_character(term.word) == V4Character(false, false),
        source.hamiltonian_terms,
    )
    positive_entries = source.positive_basis.entries
    centered = filter(row -> !isempty(row.operator_word.ops), positive_entries)
    scalar = filter(row -> isempty(row.operator_word.ops), positive_entries)
    scalar_inventory = Set(scalar)
    scalar_targets_present = all(
        scalarized_row(row) in scalar_inventory
        for row in centered
    )
    congruence_dimension_exact =
        length(centered) + length(scalar) == length(positive_entries)
    centered_scalar_zero = all(
        iszero(full_state_centered_scalar_entry(left, right))
        for left in centered
        for right in scalar
    )
    facial = gap_facial_data(source)
    return (
        exact=hamiltonian_invariant &&
              scalar_targets_present &&
              congruence_dimension_exact &&
              centered_scalar_zero &&
              facial.null_block_zero,
        hamiltonian_invariant=hamiltonian_invariant,
        scalar_targets_present=scalar_targets_present,
        congruence_dimension_exact=congruence_dimension_exact,
        centered_scalar_cross_zero=centered_scalar_zero,
        gap_null_block_zero=facial.null_block_zero,
        original_positive_dimension=length(positive_entries),
        centered_dimension=length(centered),
        scalar_dimension=length(scalar),
        original_gap_dimension=length(source.gap_basis.entries),
        active_gap_dimension=length(facial.active_rows),
        null_gap_dimension=length(facial.null_rows),
    )
end

function assemble_full_state_v4_reduced_primal(
    source::PrimalAssembly;
    verify_truth::Bool=true,
)
    truth = full_state_v4_reduction_truth(source)
    verify_truth && !truth.exact &&
        error("full-state V4 reduction truth check failed")

    positive_entries = source.positive_basis.entries
    centered_rows = FullStateReducedRow[
        FullStateReducedRow(:centered, row)
        for row in positive_entries
        if !isempty(row.operator_word.ops)
    ]
    scalar_rows = FullStateReducedRow[
        FullStateReducedRow(:scalar, row)
        for row in positive_entries
        if isempty(row.operator_word.ops)
    ]
    facial = gap_facial_data(source)
    gap_rows = FullStateReducedRow[
        FullStateReducedRow(:gap_active, row)
        for row in facial.active_rows
    ]
    positive_blocks = vcat(
        character_blocks(:positive, :centered, centered_rows),
        character_blocks(:positive, :scalar, scalar_rows),
    )
    gap_blocks = character_blocks(:gap, :gap_active, gap_rows)

    projected_equalities = ExactLinearPolynomial[
        v4_invariant_projection(polynomial)
        for polynomial in vcat(
            source.stationarity_equalities,
            facial.cross_polynomials,
        )
    ]
    equalities = canonical_real_equalities(projected_equalities)

    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    provisional = FullStateV4ReducedPrimalAssembly(
        FULL_STATE_V4_REDUCTION_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )
    for block in [positive_blocks; gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = full_state_v4_block_entry(
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
    ordered = ordered_moments(moments)
    coefficient_sha256 = fingerprint_records(
        "full-state-v4-upper-triangle-v1",
        coefficient_records,
    )
    final_sha256 = assembly_fingerprint(
        FULL_STATE_V4_REDUCTION_SCHEMA,
        source.assembly_sha256,
        [positive_blocks; gap_blocks],
        equalities,
        ordered,
        coefficient_sha256,
    )
    return FullStateV4ReducedPrimalAssembly(
        FULL_STATE_V4_REDUCTION_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        ordered,
        coefficient_sha256,
        final_sha256,
    )
end

function full_state_conjugation_reduction_truth(
    source::FullStateV4ReducedPrimalAssembly,
)
    hamiltonian_invariant = all(
        term ->
            (
                isodd(count(operation -> operation[2] == 2, term.word.ops)) ?
                -1 :
                1
            ) * conj(term.coefficient) == term.coefficient,
        source.source.hamiltonian_terms,
    )
    coefficient_covariant = true
    realified_coefficients_real = true
    coefficient_count = 0
    for block in [source.positive_blocks; source.gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            left = block.rows[row]
            right = block.rows[column]
            polynomial = full_state_v4_block_entry(
                source,
                block,
                left,
                right,
            )
            sign = (
                state_conjugation_odd(left.source) ?
                -1 :
                1
            ) * (
                state_conjugation_odd(right.source) ?
                -1 :
                1
            )
            coefficient_covariant &=
                conjugation_action(polynomial) == sign * polynomial
            projected = conjugation_invariant_projection(polynomial)
            gauged = conj(row_phase(left)) * row_phase(right) * projected
            realified_coefficients_real &=
                all(iszero ∘ imag, values(gauged.terms))
            coefficient_count += 1
        end
    end
    equality_invariant = equality_space_is_invariant(source.equalities)
    return (
        exact=hamiltonian_invariant &&
              coefficient_covariant &&
              realified_coefficients_real &&
              equality_invariant,
        hamiltonian_invariant=hamiltonian_invariant,
        coefficient_covariant=coefficient_covariant,
        realified_coefficients_real=realified_coefficients_real,
        equality_space_invariant=equality_invariant,
        coefficient_count=coefficient_count,
    )
end

function assemble_full_state_real_reduced_primal(
    source::FullStateV4ReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = full_state_conjugation_reduction_truth(source)
    verify_truth && !truth.exact &&
        error("full-state conjugation reduction truth check failed")

    equalities = canonical_real_equalities(ExactLinearPolynomial[
        conjugation_invariant_projection(polynomial)
        for polynomial in source.equalities
    ])
    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    provisional = FullStateRealReducedPrimalAssembly(
        FULL_STATE_REAL_REDUCTION_SCHEMA,
        source,
        source.positive_blocks,
        source.gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )
    for block in [source.positive_blocks; source.gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = full_state_real_block_entry(
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
    ordered = ordered_moments(moments)
    coefficient_sha256 = fingerprint_records(
        "full-state-real-upper-triangle-v1",
        coefficient_records,
    )
    final_sha256 = assembly_fingerprint(
        FULL_STATE_REAL_REDUCTION_SCHEMA,
        source.assembly_sha256,
        [source.positive_blocks; source.gap_blocks],
        equalities,
        ordered,
        coefficient_sha256,
    )
    return FullStateRealReducedPrimalAssembly(
        FULL_STATE_REAL_REDUCTION_SCHEMA,
        source,
        source.positive_blocks,
        source.gap_blocks,
        equalities,
        ordered,
        coefficient_sha256,
        final_sha256,
    )
end

function triangle_entries(blocks::Vector{FullStatePSDBlock})
    return sum(
        length(block.rows) * (length(block.rows) + 1) ÷ 2
        for block in blocks
    )
end

function full_state_v4_reduced_assembly_report(
    assembly::FullStateV4ReducedPrimalAssembly,
)
    return (
        source_moments=length(assembly.source.moments),
        reduced_moments=length(assembly.moments),
        positive_block_dimensions=length.(getfield.(
            assembly.positive_blocks,
            :rows,
        )),
        gap_block_dimensions=length.(getfield.(
            assembly.gap_blocks,
            :rows,
        )),
        equality_count=length(assembly.equalities),
        hermitian_triangle_entries=triangle_entries([
            assembly.positive_blocks;
            assembly.gap_blocks
        ]),
    )
end

function full_state_real_reduced_assembly_report(
    assembly::FullStateRealReducedPrimalAssembly,
)
    return (
        source_moments=length(assembly.source.source.moments),
        v4_moments=length(assembly.source.moments),
        real_moments=length(assembly.moments),
        positive_block_dimensions=length.(getfield.(
            assembly.positive_blocks,
            :rows,
        )),
        gap_block_dimensions=length.(getfield.(
            assembly.gap_blocks,
            :rows,
        )),
        equality_count=length(assembly.equalities),
        real_triangle_entries=triangle_entries([
            assembly.positive_blocks;
            assembly.gap_blocks
        ]),
    )
end

end
