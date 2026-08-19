module ConjugationReducedPrimalGapJuMP

using JuMP
using LinearAlgebra
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key
using ..PrimalGapJuMP:
    jump_affine_expression
using ..ReducedPrimalGapAssembly:
    ReducedPSDBlock
using ..ConjugationSymmetryReduction:
    ConjugationReducedPrimalAssembly,
    conjugation_real_block_entry

export ConjugationReducedJuMPPrimalModel,
       conjugation_block_name,
       build_conjugation_reduced_jump_primal

"""JuMP model using real symmetric cones after exact conjugation reduction."""
struct ConjugationReducedJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    equality_constraints::Vector{JuMP.ConstraintRef}
    psd_constraints::Vector{JuMP.ConstraintRef}
    assembly_sha256::String
end

character_label(block::ReducedPSDBlock) =
    string(
        "rx",
        Int(block.character.rx),
        "_ry",
        Int(block.character.ry),
    )

conjugation_block_name(block::ReducedPSDBlock) =
    join(
        (
            block.role,
            block.family,
            character_label(block),
            "real_psd",
        ),
        "_",
    )

function moment_index_map(moments::Vector{MomentKey})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("real reduced moment inventory contains duplicates"))
    return Dict(key => index for (index, key) in enumerate(moments))
end

function jump_real_block(
    assembly::ConjugationReducedPrimalAssembly,
    block::ReducedPSDBlock,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    dimension = length(block.rows)
    matrix = Matrix{JuMP.AffExpr}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        polynomial = conjugation_real_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        all(iszero ∘ imag, values(polynomial.terms)) ||
            error("real block entry retained an imaginary coefficient")
        expression = real(jump_affine_expression(
            polynomial,
            moment_variables,
            moment_indices,
        ))
        matrix[row, column] = expression
        matrix[column, row] = expression
    end
    return matrix
end

function add_real_equality!(
    model::JuMP.Model,
    equality::ExactLinearPolynomial,
    index::Int,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    all(iszero ∘ imag, values(equality.terms)) ||
        error("real reduced equality $index is not exactly real")
    expression = real(jump_affine_expression(
        equality,
        moment_variables,
        moment_indices,
    ))
    return JuMP.@constraint(
        model,
        expression == 0.0,
        base_name="conjugation_reduced_equality[$index]",
    )
end

"""
Build the exact conjugation-reduced feasibility model without an optimizer.
"""
function build_conjugation_reduced_jump_primal(
    assembly::ConjugationReducedPrimalAssembly;
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
        base_name="conjugation_even_moment",
    )
    normalization = JuMP.@constraint(
        model,
        moment_variables[1] == 1.0,
        base_name="normalization",
    )

    equality_constraints = JuMP.ConstraintRef[]
    for (index, equality) in enumerate(assembly.equalities)
        push!(
            equality_constraints,
            add_real_equality!(
                model,
                equality,
                index,
                moment_variables,
                moment_indices,
            ),
        )
    end

    psd_constraints = JuMP.ConstraintRef[]
    for block in [
        assembly.source.positive_blocks;
        assembly.source.gap_blocks
    ]
        matrix = jump_real_block(
            assembly,
            block,
            moment_variables,
            moment_indices,
        )
        push!(
            psd_constraints,
            JuMP.@constraint(
                model,
                Symmetric(matrix) in JuMP.PSDCone(),
                base_name=conjugation_block_name(block),
            ),
        )
    end

    return ConjugationReducedJuMPPrimalModel(
        model,
        moment_variables,
        normalization,
        equality_constraints,
        psd_constraints,
        assembly.assembly_sha256,
    )
end

end
