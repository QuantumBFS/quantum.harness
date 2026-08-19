module ShastryFullStateSpatialOracle

using LinearAlgebra
using ..ShastryFullStateSpatialReduction:
    ShastrySpatialPSDBlock,
    ShastryFullStateSpatialReducedPrimalAssembly,
    shastry_spatial_block_entry
using ..ShastrySutherlandPrimalOracle:
    evaluate_dimer_polynomial

export evaluate_shastry_spatial_dimer_primal

function source_primal(
    assembly::ShastryFullStateSpatialReducedPrimalAssembly,
)
    return assembly.source.source.source
end

function evaluate_block(
    assembly::ShastryFullStateSpatialReducedPrimalAssembly,
    block::ShastrySpatialPSDBlock,
)
    primal = source_primal(assembly)
    dimension = length(block.rows)
    matrix = zeros(Float64, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        exact_value = evaluate_dimer_polynomial(
            shastry_spatial_block_entry(
                assembly,
                block,
                block.rows[row],
                block.rows[column],
            ),
            primal.problem.patch,
        )
        iszero(imag(exact_value)) ||
            error("dimer evaluation of a real spatial block is not real")
        value = Float64(real(exact_value))
        matrix[row, column] = value
        matrix[column, row] = value
    end
    return matrix
end

"""
Evaluate the final target-specific exact reduction at the analytic g=0
product of dimer singlets.
"""
function evaluate_shastry_spatial_dimer_primal(
    assembly::ShastryFullStateSpatialReducedPrimalAssembly,
)
    primal = source_primal(assembly)
    primal.problem.model.name == "shastry-sutherland" ||
        throw(ArgumentError("dimer oracle requires Shastry-Sutherland"))
    primal.problem.patch.level == 1 ||
        throw(ArgumentError("dimer oracle is restricted to L=1"))
    primal.problem.d == 2 ||
        throw(ArgumentError("dimer oracle is restricted to d=2"))
    all(
        term -> term.tag != :square || iszero(term.coefficient),
        primal.hamiltonian_terms,
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
        evaluate_dimer_polynomial(equality, primal.problem.patch)
        for equality in assembly.equalities
    ]
    positive_minima = [
        minimum(eigvals(Symmetric(matrix)))
        for matrix in positive_matrices
    ]
    gap_minima = [
        minimum(eigvals(Symmetric(matrix)))
        for matrix in gap_matrices
    ]
    return (
        positive_minima=positive_minima,
        gap_minima=gap_minima,
        positive_minimum=minimum(positive_minima),
        gap_minimum=minimum(gap_minima),
        equality_values=equality_values,
        equalities_exact_zero=all(iszero, equality_values),
    )
end

end
