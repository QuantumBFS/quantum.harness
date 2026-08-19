module ShastrySutherlandPrimalOracle

using LinearAlgebra
using ..SquareJ1J2Prototype: PauliWord, pauli_word
using ..GenericGapModel: StateMonomial
using ..PrimalGapSymbolics:
    MomentKey,
    ExactLinearPolynomial,
    positive_entry,
    gap_entry
using ..PrimalGapAssembly: PrimalAssembly
using ..ShastrySutherlandOracle: dimer_product_moment

export pauli_word_from_canonical,
       evaluate_dimer_moment,
       evaluate_dimer_polynomial,
       evaluate_dimer_primal

const AXIS_SYMBOL = Dict('X' => :X, 'Y' => :Y, 'Z' => :Z)

"""Invert the canonical Pauli-word serialization used by `MomentKey`."""
function pauli_word_from_canonical(canonical::AbstractString)
    canonical == "I" && return PauliWord()
    factors = Tuple{Int,Symbol}[]
    for serialized_factor in split(canonical, ';')
        match_result = match(r"^([1-9][0-9]*)([XYZ])$", serialized_factor)
        isnothing(match_result) &&
            throw(ArgumentError("invalid canonical Pauli factor"))
        push!(
            factors,
            (
                parse(Int, match_result.captures[1]),
                AXIS_SYMBOL[only(match_result.captures[2])],
            ),
        )
    end
    _, word = pauli_word(factors)
    return word
end

"""
Evaluate one scalar state-polynomial moment in the point functional induced by
the infinite product of dimer singlets.
"""
function evaluate_dimer_moment(key::MomentKey, patch)
    isempty(key.canonical) && return 1
    value = 1
    for serialized_word in split(key.canonical, '|')
        value *= dimer_product_moment(
            pauli_word_from_canonical(serialized_word),
            patch,
        )
        iszero(value) && return 0
    end
    return value
end

function evaluate_dimer_polynomial(
    polynomial::ExactLinearPolynomial,
    patch,
)
    return sum(
        coefficient * evaluate_dimer_moment(key, patch)
        for (key, coefficient) in polynomial.terms;
        init=0//1 + 0//1 * im,
    )
end

function evaluated_matrix(
    entries::Vector{StateMonomial},
    entry_function,
    patch,
)
    dimension = length(entries)
    matrix = zeros(ComplexF64, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        value = ComplexF64(evaluate_dimer_polynomial(
            entry_function(entries[row], entries[column]),
            patch,
        ))
        matrix[row, column] = value
        matrix[column, row] = conj(value)
    end
    return matrix
end

"""
Evaluate an exact primal assembly at the known `g=0` dimer-product state.

The returned eigenvalues are numerical diagnostics of exact symbolic entries;
the stationarity residuals themselves remain exact.
"""
function evaluate_dimer_primal(assembly::PrimalAssembly)
    assembly.problem.model.name == "shastry-sutherland" ||
        throw(ArgumentError("dimer primal oracle requires Shastry-Sutherland"))
    all(
        term -> term.tag != :square || iszero(term.coefficient),
        assembly.hamiltonian_terms,
    ) || throw(ArgumentError("dimer product is a ground-state oracle only at g=0"))

    patch = assembly.problem.patch
    positive = evaluated_matrix(
        assembly.positive_basis.entries,
        positive_entry,
        patch,
    )
    gap = evaluated_matrix(
        assembly.gap_basis.entries,
        (left, right) -> gap_entry(
            left,
            right,
            assembly.hamiltonian_terms,
            assembly.problem.gamma,
        ),
        patch,
    )
    stationarity = [
        evaluate_dimer_polynomial(equality, patch)
        for equality in assembly.stationarity_equalities
    ]

    return (
        positive_matrix=positive,
        gap_matrix=gap,
        positive_min_eigenvalue=minimum(eigvals(Hermitian(positive))),
        gap_min_eigenvalue=minimum(eigvals(Hermitian(gap))),
        stationarity_values=stationarity,
        stationarity_exact_zero=all(iszero, stationarity),
    )
end

end
