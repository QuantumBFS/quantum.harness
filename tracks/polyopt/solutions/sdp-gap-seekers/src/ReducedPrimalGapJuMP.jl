module ReducedPrimalGapJuMP

using JuMP
using LinearAlgebra
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key
using ..PrimalGapJuMP:
    ComplexAffineExpression,
    jump_affine_expression
using ..ExactSymmetryReduction:
    V4Character
using ..ReducedPrimalGapAssembly:
    ReducedPrimalAssembly,
    ReducedPSDBlock,
    reduced_block_entry

export ReducedJuMPPrimalModel,
       build_reduced_jump_primal

"""JuMP model of the exact V4/facially reduced primal relaxation."""
struct ReducedJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    equality_constraints::Vector{JuMP.ConstraintRef}
    psd_constraints::Vector{JuMP.ConstraintRef}
    assembly_sha256::String
end

character_label(character::V4Character) =
    string("rx", Int(character.rx), "_ry", Int(character.ry))

block_name(block::ReducedPSDBlock) =
    join(
        (
            block.role,
            block.family,
            character_label(block.character),
        ),
        "_",
    )

function moment_index_map(moments::Vector{MomentKey})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("reduced moment inventory contains duplicates"))
    return Dict(key => index for (index, key) in enumerate(moments))
end

function require_real_diagonal(
    polynomial::ExactLinearPolynomial,
    name::String,
    index::Int,
)
    all(iszero ∘ imag, values(polynomial.terms)) ||
        error("$name diagonal $index is not exactly real")
    return polynomial
end

function jump_reduced_block(
    assembly::ReducedPrimalAssembly,
    block::ReducedPSDBlock,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    dimension = length(block.rows)
    name = block_name(block)
    matrix = Matrix{ComplexAffineExpression}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        polynomial = reduced_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        row == column &&
            require_real_diagonal(polynomial, name, row)
        expression = jump_affine_expression(
            polynomial,
            moment_variables,
            moment_indices,
        )
        matrix[row, column] = expression
        row == column || (matrix[column, row] = conj(expression))
    end
    return matrix
end

"""
Build the exact reduced feasibility model without attaching an optimizer.

All reductions were applied to the exact coefficient maps before Float64
conversion. The assembly hash binds this model to its unreduced source.
"""
function build_reduced_jump_primal(
    assembly::ReducedPrimalAssembly;
    model::JuMP.Model=JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    first(assembly.moments) == moment_key() ||
        error("identity moment must be first")

    moment_indices = moment_index_map(assembly.moments)
    moment_variables = JuMP.@variable(
        model,
        [1:length(assembly.moments)],
        base_name="moment",
    )
    normalization = JuMP.@constraint(
        model,
        moment_variables[1] == 1.0,
        base_name="normalization",
    )

    equality_constraints = JuMP.ConstraintRef[]
    for (index, equality) in enumerate(assembly.equalities)
        all(iszero ∘ imag, values(equality.terms)) ||
            error("reduced equality $index is not exactly real")
        expression = jump_affine_expression(
            equality,
            moment_variables,
            moment_indices,
        )
        push!(
            equality_constraints,
            JuMP.@constraint(
                model,
                real(expression) == 0.0,
                base_name="reduced_equality[$index]",
            ),
        )
    end

    psd_constraints = JuMP.ConstraintRef[]
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        matrix = jump_reduced_block(
            assembly,
            block,
            moment_variables,
            moment_indices,
        )
        push!(
            psd_constraints,
            JuMP.@constraint(
                model,
                Hermitian(matrix) in JuMP.HermitianPSDCone(),
                base_name=block_name(block) * "_psd",
            ),
        )
    end

    return ReducedJuMPPrimalModel(
        model,
        moment_variables,
        normalization,
        equality_constraints,
        psd_constraints,
        assembly.assembly_sha256,
    )
end

end
