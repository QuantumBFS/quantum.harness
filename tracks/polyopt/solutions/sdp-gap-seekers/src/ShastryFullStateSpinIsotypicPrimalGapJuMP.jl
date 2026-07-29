module ShastryFullStateSpinIsotypicPrimalGapJuMP

using JuMP
using LinearAlgebra
using SHA
using ..PrimalGapSymbolics:
    ExactCoefficient,
    ExactLinearPolynomial,
    MomentKey,
    canonical_polynomial_string,
    moment_degree,
    moment_key,
    polynomial_sha256
using ..PrimalGapJuMP:
    checked_float,
    jump_affine_expression
using ..ShastryFullStateSpinIsotypicReduction:
    SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
    ShastrySpinIsotypicPSDBlock,
    ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block_label,
    fingerprint_records,
    shastry_spin_isotypic_block_entry

export ShastryFullStateSpinIsotypicJuMPPrimalModel,
       ShastryFullStateSpinIsotypicStreamingJuMPPrimalModel,
       shastry_full_state_spin_isotypic_block_name,
       build_shastry_full_state_spin_isotypic_jump_primal,
       build_shastry_full_state_spin_isotypic_streaming_jump_primal

struct ShastryFullStateSpinIsotypicJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    equality_constraints::Vector{JuMP.ConstraintRef}
    psd_constraints::Vector{JuMP.ConstraintRef}
    assembly_sha256::String
end

struct ShastryFullStateSpinIsotypicStreamingJuMPPrimalModel
    model::JuMP.Model
    moment_variables::Dict{MomentKey,JuMP.VariableRef}
    psd_constraint_indices::Vector{Any}
    coefficient_map_sha256::String
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

function update_fingerprint!(
    context::SHA.SHA2_256_CTX,
    record::AbstractString,
)
    serialized = string(record)
    SHA.update!(
        context,
        codeunits(string(ncodeunits(serialized), ":", serialized)),
    )
    return context
end

function streaming_moment_variable!(
    model::JuMP.Model,
    variables::Dict{MomentKey,JuMP.VariableRef},
    key::MomentKey,
)
    return get!(variables, key) do
        variable = JuMP.@variable(model)
        JuMP.set_name(
            variable,
            "shastry_spin_isotypic_moment[$(length(variables) + 1)]",
        )
        return variable
    end
end

function streaming_real_expression(
    polynomial::ExactLinearPolynomial,
    model::JuMP.Model,
    variables::Dict{MomentKey,JuMP.VariableRef},
)
    all(iszero ∘ imag, values(polynomial.terms)) ||
        error("streaming expression retained an imaginary coefficient")
    expression = JuMP.AffExpr(0.0)
    for (key, coefficient) in polynomial.terms
        JuMP.add_to_expression!(
            expression,
            checked_float(real(coefficient)),
            streaming_moment_variable!(model, variables, key),
        )
    end
    return expression
end

function add_streaming_real_psd_constraint!(
    model::JuMP.Model,
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block::ShastrySpinIsotypicPSDBlock,
    variables::Dict{MomentKey,JuMP.VariableRef},
    coefficient_fingerprint::SHA.SHA2_256_CTX,
)
    dimension = length(block.rows)
    triangle_entries = dimension * (dimension + 1) ÷ 2
    terms = JuMP.MOI.VectorAffineTerm{Float64}[]
    constants = zeros(Float64, triangle_entries)
    row_batch_size = max(
        1,
        parse(
            Int,
            get(
                ENV,
                "SHASTRY_STREAM_ROW_BATCH",
                string(Threads.nthreads()),
            ),
        ),
    )
    for first_row in 1:row_batch_size:dimension
        last_row = min(dimension, first_row + row_batch_size - 1)
        rows = collect(first_row:last_row)
        batch_polynomials = [
            Vector{ExactLinearPolynomial}(undef, dimension - row + 1)
            for row in rows
        ]
        batch_hashes = [
            Vector{String}(undef, dimension - row + 1)
            for row in rows
        ]
        Threads.@threads :dynamic for batch_index in eachindex(rows)
            row = rows[batch_index]
            for column in row:dimension
                local_index = column - row + 1
                polynomial = shastry_spin_isotypic_block_entry(
                    assembly,
                    block,
                    block.rows[row],
                    block.rows[column],
                )
                all(iszero ∘ imag, values(polynomial.terms)) ||
                    error(
                        "streaming PSD block retained an imaginary coefficient",
                    )
                batch_polynomials[batch_index][local_index] =
                    polynomial
                batch_hashes[batch_index][local_index] =
                    polynomial_sha256(polynomial)
            end
        end
        for (batch_index, row) in enumerate(rows)
            for column in row:dimension
                local_index = column - row + 1
                polynomial =
                    batch_polynomials[batch_index][local_index]
                output_index = column * (column - 1) ÷ 2 + row
                for (key, coefficient) in polynomial.terms
                    variable =
                        streaming_moment_variable!(model, variables, key)
                    push!(
                        terms,
                        JuMP.MOI.VectorAffineTerm(
                            output_index,
                            JuMP.MOI.ScalarAffineTerm(
                                checked_float(real(coefficient)),
                                JuMP.index(variable),
                            ),
                        ),
                    )
                end
                update_fingerprint!(
                    coefficient_fingerprint,
                    string(
                        block_label(block),
                        "[",
                        row,
                        ",",
                        column,
                        "]=",
                        batch_hashes[batch_index][local_index],
                    ),
                )
            end
        end
    end
    function_object =
        JuMP.MOI.VectorAffineFunction(terms, constants)
    index = JuMP.MOI.add_constraint(
        JuMP.backend(model),
        function_object,
        JuMP.MOI.PositiveSemidefiniteConeTriangle(dimension),
    )
    JuMP.MOI.set(
        JuMP.backend(model),
        JuMP.MOI.ConstraintName(),
        index,
        shastry_full_state_spin_isotypic_block_name(block),
    )
    return index
end

"""
Build the reduced real SDP in one coefficient pass.

The target may be a `JuMP.direct_model`, so each completed PSD block can move
straight into the solver backend. The returned fingerprints are byte-for-byte
compatible with the materialized assembly and provide the exact L=1
regression gate without retaining one String per triangle entry.
"""
function build_shastry_full_state_spin_isotypic_streaming_jump_primal(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly;
    model::JuMP.Model=JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))

    variables = Dict{MomentKey,JuMP.VariableRef}()
    identity =
        streaming_moment_variable!(model, variables, moment_key())
    JuMP.@constraint(
        model,
        identity == 1.0,
        base_name="normalization",
    )
    for (index, equality) in enumerate(assembly.equalities)
        expression = streaming_real_expression(
            equality,
            model,
            variables,
        )
        JuMP.@constraint(
            model,
            expression == 0.0,
            base_name="shastry_l1d2_spin_isotypic_equality[$index]",
        )
    end

    coefficient_fingerprint = SHA.SHA2_256_CTX()
    update_fingerprint!(
        coefficient_fingerprint,
        "shastry-full-state-spin-isotypic-coefficients-v1",
    )
    psd_indices = Any[]
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        push!(
            psd_indices,
            add_streaming_real_psd_constraint!(
                model,
                assembly,
                block,
                variables,
                coefficient_fingerprint,
            ),
        )
    end
    coefficient_sha256 =
        bytes2hex(SHA.digest!(coefficient_fingerprint))
    moments = sort!(
        collect(keys(variables));
        by=key -> (moment_degree(key), key.canonical),
    )
    assembly_sha256 = fingerprint_records(
        SHASTRY_FULL_STATE_SPIN_ISOTYPIC_REDUCTION_SCHEMA,
        [
            "source=" * assembly.source.assembly_sha256,
            "coefficient_map=" * coefficient_sha256,
            "moments=" * join((key.canonical for key in moments), "\n"),
            "equalities=" * join(
                canonical_polynomial_string.(assembly.equalities),
                "\n",
            ),
        ],
    )
    return ShastryFullStateSpinIsotypicStreamingJuMPPrimalModel(
        model,
        variables,
        psd_indices,
        coefficient_sha256,
        assembly_sha256,
    )
end

end
