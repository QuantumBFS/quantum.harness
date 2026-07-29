module ShastryFullStateSpinIsotypicPrimalGapJuMP

using JuMP
using LinearAlgebra
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_key
using ..PrimalGapJuMP:
    jump_affine_expression
using ..ShastryFullStateSpinIsotypicReduction:
    ShastrySpinIsotypicPSDBlock,
    ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    shastry_spin_isotypic_block_entry

export ShastryFullStateSpinIsotypicJuMPPrimalModel,
       shastry_full_state_spin_isotypic_block_name,
       build_shastry_full_state_spin_isotypic_jump_primal

struct ShastryFullStateSpinIsotypicJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    equality_constraints::Vector{JuMP.ConstraintRef}
    psd_constraints::Vector{JuMP.ConstraintRef}
    assembly_sha256::String
end

function shastry_full_state_spin_isotypic_block_name(
    block::ShastrySpinIsotypicPSDBlock,
)
    source = block.source_block.source_block
    return join(
        (
            "shastry_l1d2_spin_isotypic",
            source.role,
            source.family,
            "rx" * string(Int(source.character.rx)),
            "ry" * string(Int(source.character.ry)),
            block.source_block.parity,
            block.kind,
            "real_psd",
        ),
        "_",
    )
end

function jump_real_block(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block::ShastrySpinIsotypicPSDBlock,
    variables::Vector{JuMP.VariableRef},
    indices::Dict{MomentKey,Int},
)
    dimension = length(block.rows)
    matrix = Matrix{JuMP.AffExpr}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        polynomial = shastry_spin_isotypic_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        all(iszero ∘ imag, values(polynomial.terms)) ||
            error("spin-isotypic block retained an imaginary coefficient")
        expression = real(jump_affine_expression(
            polynomial,
            variables,
            indices,
        ))
        matrix[row, column] = expression
        matrix[column, row] = expression
    end
    return matrix
end

function build_shastry_full_state_spin_isotypic_jump_primal(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly;
    model::JuMP.Model=JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    first(assembly.moments) == moment_key() ||
        error("spin-isotypic identity moment is not first")

    indices = Dict(
        key => index
        for (index, key) in enumerate(assembly.moments)
    )
    variables = JuMP.@variable(
        model,
        [1:length(assembly.moments)],
        base_name="shastry_l1d2_spin_isotypic_moment",
    )
    normalization = JuMP.@constraint(
        model,
        variables[1] == 1.0,
        base_name="normalization",
    )
    equalities = JuMP.ConstraintRef[]
    for (index, equality) in enumerate(assembly.equalities)
        expression = real(jump_affine_expression(
            equality,
            variables,
            indices,
        ))
        push!(
            equalities,
            JuMP.@constraint(
                model,
                expression == 0.0,
                base_name="shastry_l1d2_spin_isotypic_equality[$index]",
            ),
        )
    end

    psd_constraints = JuMP.ConstraintRef[]
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        matrix = jump_real_block(assembly, block, variables, indices)
        push!(
            psd_constraints,
            JuMP.@constraint(
                model,
                Symmetric(matrix) in JuMP.PSDCone(),
                base_name=shastry_full_state_spin_isotypic_block_name(block),
            ),
        )
    end
    return ShastryFullStateSpinIsotypicJuMPPrimalModel(
        model,
        variables,
        normalization,
        equalities,
        psd_constraints,
        assembly.assembly_sha256,
    )
end

end
