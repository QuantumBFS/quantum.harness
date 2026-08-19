module PrimalGapJuMP

using JuMP
using LinearAlgebra
using ..PrimalGapSymbolics:
    ExactCoefficient,
    ExactLinearPolynomial,
    MomentKey,
    adjoint_polynomial,
    moment_key,
    positive_entry,
    gap_entry
using ..PrimalGapAssembly:
    PrimalAssembly

export ComplexAffineExpression,
       JuMPPrimalModel,
       jump_affine_expression,
       jump_hermitian_matrix,
       build_jump_primal

const ComplexAffineExpression =
    JuMP.GenericAffExpr{ComplexF64,JuMP.VariableRef}

"""
JuMP representation of one exact `PrimalAssembly`.

The model has no optimizer attached and no objective beyond feasibility.
`assembly_sha256` binds it to the exact solver-independent coefficient map.
"""
struct JuMPPrimalModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    stationarity_constraints::Vector{JuMP.ConstraintRef}
    positive_constraint::JuMP.ConstraintRef
    gap_constraint::JuMP.ConstraintRef
    assembly_sha256::String
end

function checked_float(value)
    converted = Float64(value)
    isfinite(converted) ||
        throw(ArgumentError("exact coefficient overflows Float64"))
    iszero(value) || !iszero(converted) ||
        throw(ArgumentError("nonzero exact coefficient underflows Float64"))
    return converted
end

function checked_complex_float(coefficient::ExactCoefficient)
    return ComplexF64(
        checked_float(real(coefficient)),
        checked_float(imag(coefficient)),
    )
end

function moment_index_map(moments::Vector{MomentKey})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("assembly moment inventory contains duplicates"))
    return Dict(key => index for (index, key) in enumerate(moments))
end

"""Convert one exact polynomial to a JuMP complex affine expression."""
function jump_affine_expression(
    polynomial::ExactLinearPolynomial,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    expression = ComplexAffineExpression(0.0 + 0.0im)
    ordered_terms = sort!(
        collect(polynomial.terms);
        by=term -> get(moment_indices, first(term), typemax(Int)),
    )
    for (key, coefficient) in ordered_terms
        index = get(moment_indices, key, 0)
        index > 0 ||
            throw(ArgumentError("polynomial uses an unregistered scalar moment"))
        JuMP.add_to_expression!(
            expression,
            checked_complex_float(coefficient),
            moment_variables[index],
        )
    end
    return expression
end

function require_real_diagonal(
    polynomial::ExactLinearPolynomial,
    role::Symbol,
    index::Int,
)
    all(iszero ∘ imag, values(polynomial.terms)) ||
        error("$role matrix diagonal $index is not exactly real")
    return polynomial
end

"""
Materialize one Hermitian affine matrix from an exact lazy assembly.

Only the upper triangle is assembled independently; the lower triangle is its
explicit affine conjugate. Exact diagonal reality is checked before Float64
conversion.
"""
function jump_hermitian_matrix(
    role::Symbol,
    assembly::PrimalAssembly,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{MomentKey,Int},
)
    role in (:positive, :gap) ||
        throw(ArgumentError("matrix role must be :positive or :gap"))
    basis = role == :positive ?
        assembly.positive_basis.entries :
        assembly.gap_basis.entries
    dimension = length(basis)
    matrix = Matrix{ComplexAffineExpression}(undef, dimension, dimension)

    for row in 1:dimension
        for column in row:dimension
            polynomial = role == :positive ?
                positive_entry(basis[row], basis[column]) :
                gap_entry(
                    basis[row],
                    basis[column],
                    assembly.hamiltonian_terms,
                    assembly.problem.gamma,
                )
            row == column &&
                require_real_diagonal(polynomial, role, row)
            expression = jump_affine_expression(
                polynomial,
                moment_variables,
                moment_indices,
            )
            matrix[row, column] = expression
            if row != column
                matrix[column, row] = conj(expression)
                adjoint_polynomial(polynomial) ==
                    (
                        role == :positive ?
                        positive_entry(basis[column], basis[row]) :
                        gap_entry(
                            basis[column],
                            basis[row],
                            assembly.hamiltonian_terms,
                            assembly.problem.gamma,
                        )
                    ) ||
                    error("$role coefficient map is not exactly Hermitian")
            end
        end
    end
    return matrix
end

function name_constraint!(
    constraint::JuMP.ConstraintRef,
    name::String,
)
    JuMP.set_name(constraint, name)
    return constraint
end

"""
Build the direct primal JuMP feasibility model without attaching or invoking a
solver.

The two complex Hermitian cones are represented by JuMP's
`HermitianPSDCone`; MOI stores their upper-triangular real/imaginary packing.
"""
function build_jump_primal(
    assembly::PrimalAssembly;
    model::JuMP.Model=JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    first(assembly.moments) == moment_key() ||
        error("assembly identity moment is not first")

    moment_indices = moment_index_map(assembly.moments)
    moment_variables = JuMP.@variable(
        model,
        [1:length(assembly.moments)],
        base_name="moment",
    )
    normalization = name_constraint!(
        JuMP.@constraint(model, moment_variables[1] == 1.0),
        "normalization",
    )

    stationarity_constraints = JuMP.ConstraintRef[]
    for (index, equality) in enumerate(assembly.stationarity_equalities)
        all(iszero ∘ imag, values(equality.terms)) ||
            error("stationarity equality $index is not exactly real")
        expression = jump_affine_expression(
            equality,
            moment_variables,
            moment_indices,
        )
        push!(
            stationarity_constraints,
            name_constraint!(
                JuMP.@constraint(model, real(expression) == 0.0),
                "stationarity[$index]",
            ),
        )
    end

    positive_matrix = jump_hermitian_matrix(
        :positive,
        assembly,
        moment_variables,
        moment_indices,
    )
    positive_constraint = name_constraint!(
        JuMP.@constraint(
            model,
            Hermitian(positive_matrix) in JuMP.HermitianPSDCone(),
        ),
        "positive_psd",
    )

    gap_matrix = jump_hermitian_matrix(
        :gap,
        assembly,
        moment_variables,
        moment_indices,
    )
    gap_constraint = name_constraint!(
        JuMP.@constraint(
            model,
            Hermitian(gap_matrix) in JuMP.HermitianPSDCone(),
        ),
        "gap_psd",
    )

    return JuMPPrimalModel(
        model,
        moment_variables,
        normalization,
        stationarity_constraints,
        positive_constraint,
        gap_constraint,
        assembly.assembly_sha256,
    )
end

end
