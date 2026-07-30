module SpatialReflectionPrimalGapJuMP

using JuMP
using LinearAlgebra
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey
using ..PrimalGapJuMP:
    jump_affine_expression
using ..SpatialReflectionReduction:
    SpatialReflectionPSDBlock,
    SpatialReflectionReducedPrimalAssembly,
    spatial_reflection_block_entry

export SpatialReflectionJuMPPrimalModel,
       spatial_reflection_block_name,
       build_spatial_reflection_reduced_jump_primal

struct SpatialReflectionJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    equality_constraints::Vector{JuMP.ConstraintRef}
    psd_constraints::Vector{JuMP.ConstraintRef}
    assembly_sha256::String
end

function spatial_reflection_block_name(block::SpatialReflectionPSDBlock)
    source = block.source_block
    v4 = source.source_block
    return join(
        (
            "spatial_reflection",
            v4.role,
            v4.family,
            "rx" * string(Int(v4.character.rx)),
            "ry" * string(Int(v4.character.ry)),
            source.kind,
            block.kind,
            "real_psd",
        ),
        "_",
    )
end

function moment_index_map(moments::Vector{MomentKey})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("spatial moment inventory contains duplicates"))
    return Dict(key => index for (index, key) in enumerate(moments))
end

function jump_real_block(
    assembly::SpatialReflectionReducedPrimalAssembly,
    block::SpatialReflectionPSDBlock,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    dimension = length(block.rows)
    matrix = Matrix{JuMP.AffExpr}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        polynomial = spatial_reflection_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        all(iszero ∘ imag, values(polynomial.terms)) ||
            error("spatial block retained an imaginary coefficient")
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
        error("spatial equality $index is not exactly real")
    expression = real(jump_affine_expression(
        equality,
        moment_variables,
        moment_indices,
    ))
    return JuMP.@constraint(
        model,
        expression == 0.0,
        base_name="spatial_reflection_equality[$index]",
    )
end

function build_spatial_reflection_reduced_jump_primal(
    assembly::SpatialReflectionReducedPrimalAssembly;
    model::JuMP.Model=JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))

    moment_indices = moment_index_map(assembly.moments)
    moment_variables = JuMP.@variable(
        model,
        [1:length(assembly.moments)],
        base_name="spatial_reflection_invariant_moment",
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
    for block in [assembly.positive_blocks; assembly.gap_blocks]
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
                base_name=spatial_reflection_block_name(block),
            ),
        )
    end

    return SpatialReflectionJuMPPrimalModel(
        model,
        moment_variables,
        normalization,
        equality_constraints,
        psd_constraints,
        assembly.assembly_sha256,
    )
end

end
