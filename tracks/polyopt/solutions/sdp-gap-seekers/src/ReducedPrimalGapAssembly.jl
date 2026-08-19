module ReducedPrimalGapAssembly

using SHA
using ..SquareJ1J2Prototype:
    PauliWord
using ..GenericGapModel:
    StateMonomial
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256,
    gap_entry
using ..PrimalGapAssembly:
    PrimalAssembly
using ..ExactSymmetryReduction:
    V4Character,
    V4_CHARACTERS,
    v4_character,
    v4_invariant_projection,
    manifest_pauli_words,
    bare_row,
    centered_positive_entry,
    scalar_positive_entry,
    positive_reduction_truth,
    gap_facial_reduction_truth,
    invariant_moment_inventory,
    canonical_real_equalities

export ReducedPSDRow,
       ReducedPSDBlock,
       ReducedPrimalAssembly,
       reduced_block_entry,
       assemble_reduced_primal,
       reduced_assembly_report

const REDUCED_ASSEMBLY_SCHEMA = "primal-gap-exact-v4-reduction-v1"

"""One row in an exact reduced PSD block."""
struct ReducedPSDRow
    family::Symbol
    word::PauliWord

    function ReducedPSDRow(family::Symbol, word::PauliWord)
        family in (:centered, :scalar, :gap_active) ||
            throw(ArgumentError("unsupported exact-reduction row family"))
        family == :centered && isempty(word.ops) &&
            throw(ArgumentError("the centered identity row is zero"))
        family == :gap_active && isempty(word.ops) &&
            throw(ArgumentError("an active gap row cannot be identity"))
        new(family, word)
    end
end

"""One character block after exact V4 averaging."""
struct ReducedPSDBlock
    role::Symbol
    family::Symbol
    character::V4Character
    rows::Vector{ReducedPSDRow}

    function ReducedPSDBlock(
        role::Symbol,
        family::Symbol,
        character::V4Character,
        rows::Vector{ReducedPSDRow},
    )
        role in (:positive, :gap) ||
            throw(ArgumentError("reduced block role must be positive or gap"))
        expected_family = role == :positive ?
            (:centered, :scalar) :
            (:gap_active,)
        family in expected_family ||
            throw(ArgumentError("row family is incompatible with block role"))
        isempty(rows) &&
            throw(ArgumentError("empty character blocks must be omitted"))
        all(row -> row.family == family, rows) ||
            throw(ArgumentError("block mixes reduced row families"))
        all(row -> v4_character(row.word) == character, rows) ||
            throw(ArgumentError("block mixes V4 characters"))
        new(role, family, character, rows)
    end
end

"""
Exact principal representation of the same finite relaxation.

The source assembly is retained as provenance. The reduced moment variables
are the invariant quotient; the positive matrix is split by centered/scalar
families and V4 characters; the gap matrix is facially reduced before the same
character split.
"""
struct ReducedPrimalAssembly{A}
    schema::String
    source::A
    positive_blocks::Vector{ReducedPSDBlock}
    gap_blocks::Vector{ReducedPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function reduced_block_entry(
    assembly::ReducedPrimalAssembly,
    block::ReducedPSDBlock,
    left::ReducedPSDRow,
    right::ReducedPSDRow,
)
    left.family == block.family && right.family == block.family ||
        throw(ArgumentError("row does not belong to the requested block"))
    polynomial = if block.family == :centered
        centered_positive_entry(left.word, right.word)
    elseif block.family == :scalar
        scalar_positive_entry(left.word, right.word)
    else
        gap_entry(
            bare_row(left.word),
            bare_row(right.word),
            assembly.source.hamiltonian_terms,
            assembly.source.problem.gamma,
        )
    end
    projected = v4_invariant_projection(polynomial)
    projected == polynomial ||
        error("same-character block entry was not V4 invariant")
    return projected
end

function character_blocks(
    role::Symbol,
    family::Symbol,
    words::Vector{PauliWord},
)
    blocks = ReducedPSDBlock[]
    for character in V4_CHARACTERS
        selected_words = filter(
            word -> v4_character(word) == character,
            words,
        )
        isempty(selected_words) && continue
        rows = ReducedPSDRow[
            ReducedPSDRow(family, word)
            for word in selected_words
        ]
        push!(
            blocks,
            ReducedPSDBlock(role, family, character, rows),
        )
    end
    return blocks
end

function reduced_equalities(source::PrimalAssembly)
    facial = gap_facial_reduction_truth(source)
    projected = ExactLinearPolynomial[
        v4_invariant_projection(polynomial)
        for polynomial in vcat(
            source.stationarity_equalities,
            facial.cross_polynomials,
        )
    ]
    return canonical_real_equalities(projected)
end

function add_polynomial_moments!(
    moments::Set{MomentKey},
    polynomial::ExactLinearPolynomial,
)
    union!(moments, keys(polynomial.terms))
    return moments
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

function assemble_reduced_primal(
    source::PrimalAssembly;
    verify_truth::Bool=true,
)
    all(
        term -> v4_character(term.word) == V4Character(false, false),
        source.hamiltonian_terms,
    ) || throw(
        ArgumentError(
            "V4 reduction requires an invariant Hamiltonian term inventory",
        ),
    )
    positive_truth = verify_truth ?
        positive_reduction_truth(source.positive_basis) :
        nothing
    facial_truth = gap_facial_reduction_truth(source)
    if verify_truth
        something(positive_truth).exact ||
            error("positive exact-reduction truth check failed")
        facial_truth.exact ||
            error("gap facial-reduction truth check failed")
    end

    words = manifest_pauli_words(source.positive_basis)
    nonidentity_words = filter(word -> !isempty(word.ops), words)
    positive_blocks = vcat(
        character_blocks(:positive, :centered, nonidentity_words),
        character_blocks(:positive, :scalar, words),
    )

    active_words = PauliWord[]
    for row in facial_truth.active_rows
        isempty(row.state_symbols) ||
            throw(ArgumentError("active gap rows must be bare operators"))
        push!(active_words, row.operator_word)
    end
    gap_blocks = character_blocks(:gap, :gap_active, active_words)
    equalities = reduced_equalities(source)

    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    provisional = ReducedPrimalAssembly(
        REDUCED_ASSEMBLY_SCHEMA,
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
            polynomial = reduced_block_entry(
                provisional,
                block,
                block.rows[row],
                block.rows[column],
            )
            add_polynomial_moments!(moments, polynomial)
            push!(
                coefficient_records,
                join(
                    (
                        block.role,
                        block.family,
                        character_label(block.character),
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
        add_polynomial_moments!(moments, equality)
    end

    ordered_moments = sort!(
        collect(moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    expected_inventory = invariant_moment_inventory(source.moments)
    ordered_moments == expected_inventory.moments ||
        error("reduced coefficient maps do not reproduce the invariant inventory")

    coefficient_sha256 = fingerprint_records(
        "reduced-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "reduced-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    block_records = String[
        join(
            (
                block.role,
                block.family,
                character_label(block.character),
                length(block.rows),
            ),
            ":",
        )
        for block in [positive_blocks; gap_blocks]
    ]
    final_sha256 = fingerprint_records(
        REDUCED_ASSEMBLY_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "blocks=" * fingerprint_records("reduced-blocks-v1", block_records),
            "equalities=" * equality_sha256,
            "moments=" * join(
                (key.canonical for key in ordered_moments),
                "\n",
            ),
            "coefficients=" * coefficient_sha256,
        ],
    )

    return ReducedPrimalAssembly(
        REDUCED_ASSEMBLY_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        ordered_moments,
        coefficient_sha256,
        final_sha256,
    )
end

function reduced_assembly_report(assembly::ReducedPrimalAssembly)
    return (
        source_moments=length(assembly.source.moments),
        reduced_moments=length(assembly.moments),
        eliminated_moments=
            length(assembly.source.moments) - length(assembly.moments),
        positive_block_dimensions=[
            length(block.rows)
            for block in assembly.positive_blocks
        ],
        gap_block_dimensions=[
            length(block.rows)
            for block in assembly.gap_blocks
        ],
        equality_count=length(assembly.equalities),
        coefficient_map_sha256=assembly.coefficient_map_sha256,
        assembly_sha256=assembly.assembly_sha256,
    )
end

end
