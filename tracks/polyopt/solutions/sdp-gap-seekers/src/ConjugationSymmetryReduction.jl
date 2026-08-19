module ConjugationSymmetryReduction

using SHA
using ..SquareJ1J2Prototype:
    PauliWord
using ..PrimalGapSymbolics:
    ExactRational,
    ExactLinearPolynomial,
    MomentKey,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256,
    real_part_polynomial
using ..ExactSymmetryReduction:
    canonical_real_equalities
using ..ReducedPrimalGapAssembly:
    ReducedPSDRow,
    ReducedPSDBlock,
    ReducedPrimalAssembly,
    reduced_block_entry

export CONJUGATION_REDUCTION_SCHEMA,
       ConjugationReducedPrimalAssembly,
       conjugation_odd,
       conjugation_sign,
       conjugation_action,
       conjugation_invariant_projection,
       conjugation_real_block_entry,
       conjugation_reduction_truth,
       assemble_conjugation_reduced_primal,
       conjugation_reduced_assembly_report

const CONJUGATION_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-reduction-v1"

"""
Parity under entrywise complex conjugation in the computational basis.

`X` and `Z` are real matrices and `Y` is imaginary, so a canonical Pauli
word acquires one minus sign for every `Y`.
"""
conjugation_odd(word::PauliWord) =
    isodd(count(operation -> operation[2] == 2, word.ops))

"""
Parity of a scalar state-polynomial moment under complex conjugation.

`MomentKey.canonical` contains only site integers, separators, and the axis
letters `X`, `Y`, `Z`, so counting `Y` is an injective way to recover the
product parity without reparsing the words.
"""
conjugation_odd(key::MomentKey) =
    isodd(count(==('Y'), key.canonical))

conjugation_sign(value) = conjugation_odd(value) ? -1 : 1

"""
Antilinear conjugation action on an exact affine moment polynomial.

The coefficient is conjugated and each real scalar moment receives its
computational-basis conjugation sign.
"""
function conjugation_action(polynomial::ExactLinearPolynomial)
    return ExactLinearPolynomial(Dict(
        key => conjugation_sign(key) * conj(coefficient)
        for (key, coefficient) in polynomial.terms
    ))
end

"""Reynolds projection onto conjugation-even scalar moments."""
function conjugation_invariant_projection(
    polynomial::ExactLinearPolynomial,
)
    return ExactLinearPolynomial(Dict(
        key => coefficient
        for (key, coefficient) in polynomial.terms
        if !conjugation_odd(key)
    ))
end

"""
Fixed row phase used to realify a conjugation-invariant Hermitian block.

If `D` is the diagonal matrix of conjugation signs, invariance gives
`M = D * conj(M) * D`. With `P = diag(1 for even rows, i for odd rows)`,
`P' * M * P` is exactly real symmetric.
"""
row_phase(row::ReducedPSDRow) =
    conjugation_odd(row.word) ? Complex{Int}(0, 1) : Complex{Int}(1, 0)

function require_exactly_real(
    polynomial::ExactLinearPolynomial,
    label::String,
)
    all(iszero ∘ imag, values(polynomial.terms)) ||
        error("$label is not exactly real after conjugation gauge")
    return real_part_polynomial(polynomial)
end

"""
One exact real-symmetric block entry after conjugation averaging and gauge.
"""
function conjugation_real_block_entry(
    assembly,
    block::ReducedPSDBlock,
    left::ReducedPSDRow,
    right::ReducedPSDRow,
)
    base = reduced_block_entry(
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

function polynomial_row_rank(
    polynomials::Vector{ExactLinearPolynomial},
)
    isempty(polynomials) && return 0
    all(
        polynomial ->
            all(iszero ∘ imag, values(polynomial.terms)),
        polynomials,
    ) || throw(ArgumentError("row-rank check requires real polynomials"))
    keys_union = Set{MomentKey}()
    for polynomial in polynomials
        union!(keys_union, keys(polynomial.terms))
    end
    ordered_keys = sort!(
        collect(keys_union);
        by=key -> (moment_degree(key), key.canonical),
    )
    matrix = zeros(ExactRational, length(polynomials), length(ordered_keys))
    indices = Dict(key => index for (index, key) in enumerate(ordered_keys))
    for (row, polynomial) in enumerate(polynomials)
        for (key, coefficient) in polynomial.terms
            matrix[row, indices[key]] = real(coefficient)
        end
    end

    rank = 0
    for column in axes(matrix, 2)
        pivot = findfirst(
            row -> !iszero(matrix[row, column]),
            (rank + 1):size(matrix, 1),
        )
        isnothing(pivot) && continue
        pivot_row = rank + pivot
        rank += 1
        if pivot_row != rank
            matrix[rank, :], matrix[pivot_row, :] =
                copy(matrix[pivot_row, :]), copy(matrix[rank, :])
        end
        pivot_value = matrix[rank, column]
        matrix[rank, :] ./= pivot_value
        for row in axes(matrix, 1)
            row == rank && continue
            scale = matrix[row, column]
            iszero(scale) && continue
            matrix[row, :] .-= scale .* matrix[rank, :]
        end
        rank == size(matrix, 1) && break
    end
    return rank
end

function equality_space_is_invariant(
    equalities::Vector{ExactLinearPolynomial},
)
    transformed = conjugation_action.(equalities)
    all(
        polynomial ->
            all(iszero ∘ imag, values(polynomial.terms)),
        transformed,
    ) || return false
    return polynomial_row_rank(equalities) ==
           polynomial_row_rank([equalities; transformed])
end

"""
Exhaustive exact covariance gates for the antiunitary reduction.

The Hamiltonian, every V4-reduced PSD coefficient, and the complete affine
equality row space are checked under computational-basis conjugation.
"""
function conjugation_reduction_truth(
    source::ReducedPrimalAssembly,
)
    hamiltonian_invariant = all(
        term ->
            conjugation_sign(term.word) * conj(term.coefficient) ==
            term.coefficient,
        source.source.hamiltonian_terms,
    )

    coefficient_covariant = true
    coefficient_count = 0
    realified_coefficients_real = true
    for block in [source.positive_blocks; source.gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            left = block.rows[row]
            right = block.rows[column]
            polynomial = reduced_block_entry(
                source,
                block,
                left,
                right,
            )
            expected =
                (conjugation_sign(left.word) *
                 conjugation_sign(right.word)) * polynomial
            coefficient_covariant &=
                conjugation_action(polynomial) == expected

            projected = conjugation_invariant_projection(polynomial)
            gauged =
                conj(row_phase(left)) * row_phase(right) * projected
            realified_coefficients_real &=
                all(iszero ∘ imag, values(gauged.terms))
            coefficient_count += 1
        end
    end

    equality_space_invariant =
        equality_space_is_invariant(source.equalities)
    return (
        exact=hamiltonian_invariant &&
              coefficient_covariant &&
              realified_coefficients_real &&
              equality_space_invariant,
        hamiltonian_invariant=hamiltonian_invariant,
        coefficient_covariant=coefficient_covariant,
        coefficient_count=coefficient_count,
        realified_coefficients_real=realified_coefficients_real,
        equality_space_invariant=equality_space_invariant,
    )
end

"""
Exact real-cone representation of the V4-reduced finite relaxation.

Feasibility is preserved in both directions: any feasible functional can be
averaged with its computational-basis conjugate, and an invariant feasible
functional is already feasible in the source relaxation.
"""
struct ConjugationReducedPrimalAssembly{A}
    schema::String
    source::A
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
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

function conjugation_reduced_equalities(
    source::ReducedPrimalAssembly,
)
    projected = ExactLinearPolynomial[
        conjugation_invariant_projection(equality)
        for equality in source.equalities
    ]
    return canonical_real_equalities(projected)
end

function assemble_conjugation_reduced_primal(
    source::ReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ? conjugation_reduction_truth(source) : nothing
    if verify_truth
        something(truth).exact ||
            error("conjugation exact-reduction truth check failed")
    end

    equalities = conjugation_reduced_equalities(source)
    moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    provisional = ConjugationReducedPrimalAssembly(
        CONJUGATION_REDUCTION_SCHEMA,
        source,
        equalities,
        MomentKey[],
        "",
        "",
    )
    for block in [source.positive_blocks; source.gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = conjugation_real_block_entry(
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
                        block.character.rx,
                        block.character.ry,
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
    expected_moments = filter(
        key -> !conjugation_odd(key),
        source.moments,
    )
    ordered_moments == expected_moments ||
        error(
            "real coefficient maps do not reproduce the " *
            "conjugation-invariant inventory",
        )

    coefficient_sha256 = fingerprint_records(
        "conjugation-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "conjugation-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    final_sha256 = fingerprint_records(
        CONJUGATION_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "equalities=" * equality_sha256,
            "moments=" * join(
                (key.canonical for key in ordered_moments),
                "\n",
            ),
            "coefficients=" * coefficient_sha256,
        ],
    )
    return ConjugationReducedPrimalAssembly(
        CONJUGATION_REDUCTION_SCHEMA,
        source,
        equalities,
        ordered_moments,
        coefficient_sha256,
        final_sha256,
    )
end

triangle_count(dimension::Int) =
    dimension * (dimension + 1) ÷ 2

function conjugation_reduced_assembly_report(
    assembly::ConjugationReducedPrimalAssembly,
)
    positive_dimensions = [
        length(block.rows)
        for block in assembly.source.positive_blocks
    ]
    gap_dimensions = [
        length(block.rows)
        for block in assembly.source.gap_blocks
    ]
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_moments=length(assembly.source.source.moments),
        v4_moments=length(assembly.source.moments),
        real_moments=length(assembly.moments),
        eliminated_conjugation_odd_moments=
            length(assembly.source.moments) - length(assembly.moments),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        real_psd_triangle_entries=sum(triangle_count, all_dimensions),
        generic_hermitian_bridge_triangle_entries=sum(
            dimension -> triangle_count(2dimension),
            positive_dimensions,
        ),
        coefficient_map_sha256=assembly.coefficient_map_sha256,
        assembly_sha256=assembly.assembly_sha256,
    )
end

end
