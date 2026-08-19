module ShastrySutherlandReducedOracle

using LinearAlgebra
using ..ReducedPrimalGapAssembly:
    ReducedPrimalAssembly,
    ReducedPSDBlock,
    reduced_block_entry
using ..ShastrySutherlandPrimalOracle:
    evaluate_dimer_polynomial

export evaluate_reduced_dimer_primal

function evaluate_block(
    assembly::ReducedPrimalAssembly,
    block::ReducedPSDBlock,
)
    dimension = length(block.rows)
    matrix = zeros(ComplexF64, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        value = ComplexF64(evaluate_dimer_polynomial(
            reduced_block_entry(
                assembly,
                block,
                block.rows[row],
                block.rows[column],
            ),
            assembly.source.problem.patch,
        ))
        matrix[row, column] = value
        matrix[column, row] = conj(value)
    end
    return matrix
end

"""
Evaluate every exact-reduction block at the analytic `g=0` dimer state.

This independently checks that the reduced representation preserves the known
positive/gap matrices and all facial-reduction equalities.
"""
function evaluate_reduced_dimer_primal(assembly::ReducedPrimalAssembly)
    source = assembly.source
    source.problem.model.name == "shastry-sutherland" ||
        throw(ArgumentError("dimer oracle requires Shastry-Sutherland"))
    all(
        term -> term.tag != :square || iszero(term.coefficient),
        source.hamiltonian_terms,
    ) || throw(ArgumentError("dimer ground-state oracle requires g=0"))

    positive_matrices = [
        evaluate_block(assembly, block)
        for block in assembly.positive_blocks
    ]
    gap_matrices = [
        evaluate_block(assembly, block)
        for block in assembly.gap_blocks
    ]
    equality_values = [
        evaluate_dimer_polynomial(equality, source.problem.patch)
        for equality in assembly.equalities
    ]

    positive_minima = [
        minimum(eigvals(Hermitian(matrix)))
        for matrix in positive_matrices
    ]
    gap_minima = [
        minimum(eigvals(Hermitian(matrix)))
        for matrix in gap_matrices
    ]
    return (
        positive_matrices=positive_matrices,
        gap_matrices=gap_matrices,
        positive_minima=positive_minima,
        gap_minima=gap_minima,
        positive_minimum=minimum(positive_minima),
        gap_minimum=minimum(gap_minima),
        equality_values=equality_values,
        equalities_exact_zero=all(iszero, equality_values),
    )
end

end
