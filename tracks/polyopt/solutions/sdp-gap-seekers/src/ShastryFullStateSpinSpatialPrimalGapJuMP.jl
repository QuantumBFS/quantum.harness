module ShastryFullStateSpinSpatialPrimalGapJuMP

using JuMP
using LinearAlgebra
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key
using ..PrimalGapJuMP:
    jump_affine_expression
using ..ShastryFullStateSpatialReduction:
    ShastrySpatialPSDBlock
using ..ShastryFullStateSpinSpatialReduction:
    ShastryFullStateSpinSpatialReducedPrimalAssembly,
    shastry_spin_spatial_block_entry

export ShastryFullStateSpinSpatialJuMPPrimalModel,
       shastry_full_state_spin_spatial_block_name,
       build_shastry_full_state_spin_spatial_jump_primal

struct ShastryFullStateSpinSpatialJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    equality_constraints::Vector{JuMP.ConstraintRef}
    psd_constraints::Vector{JuMP.ConstraintRef}
    assembly_sha256::String
end

function shastry_full_state_spin_spatial_block_name(
    block::ShastrySpatialPSDBlock,
)
    source = block.source_block
    return join(
        (
            "shastry_l1d2_spin_spatial",
            source.role,
            source.family,
            "rx" * string(Int(source.character.rx)),
            "ry" * string(Int(source.character.ry)),
            block.parity,
            "real_psd",
        ),
        "_",
    )
end

function moment_index_map(moments::Vector{MomentKey})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("spin-spatial moment inventory contains duplicates"))
    return Dict(key => index for (index, key) in enumerate(moments))
end

function jump_real_block(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly,
    block::ShastrySpatialPSDBlock,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    dimension = length(block.rows)
    matrix = Matrix{JuMP.AffExpr}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        polynomial = shastry_spin_spatial_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        all(iszero ∘ imag, values(polynomial.terms)) ||
            error("spin-spatial block retained an imaginary coefficient")
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
        error("spin-spatial equality $index is not exactly real")
    expression = real(jump_affine_expression(
        equality,
        moment_variables,
        moment_indices,
    ))
    return JuMP.@constraint(
        model,
        expression == 0.0,
        base_name="shastry_l1d2_spin_spatial_equality[$index]",
    )
end

function build_shastry_full_state_spin_spatial_jump_primal(
    assembly::ShastryFullStateSpinSpatialReducedPrimalAssembly;
    model::JuMP.Model=JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    first(assembly.moments) == moment_key() ||
        error("spin-spatial identity moment is not first")

    moment_indices = moment_index_map(assembly.moments)
    moment_variables = JuMP.@variable(
        model,
        [1:length(assembly.moments)],
        base_name="shastry_l1d2_spin_spatial_moment",
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
                base_name=shastry_full_state_spin_spatial_block_name(block),
            ),
        )
    end

    return ShastryFullStateSpinSpatialJuMPPrimalModel(
        model,
        moment_variables,
        normalization,
        equality_constraints,
        psd_constraints,
        assembly.assembly_sha256,
    )
end

end
