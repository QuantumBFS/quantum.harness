module ShastryFullStateSpinIsotypicDualCertificateJuMP

using JuMP
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_degree,
    moment_key
using ..PrimalGapJuMP:
    checked_float
using ..ShastryFullStateSpinIsotypicReduction:
    ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    shastry_spin_isotypic_block_entry

export ShastryFullStateSpinIsotypicDualCertificateModel,
       build_shastry_full_state_spin_isotypic_dual_certificate

struct ShastryFullStateSpinIsotypicDualCertificateModel
    model::JuMP.Model
    moment_constraints::Dict{MomentKey,Any}
    psd_constraint_indices::Vector{Any}
    equality_multiplier_variables::Vector{JuMP.MOI.VariableIndex}
    scalar_term_count::Int
end

function append_certificate_term!(
    terms_by_moment::Dict{
        MomentKey,
        Vector{JuMP.MOI.ScalarAffineTerm{Float64}},
    },
    key::MomentKey,
    coefficient,
    variable::JuMP.MOI.VariableIndex,
)
    push!(
        get!(
            terms_by_moment,
            key,
            JuMP.MOI.ScalarAffineTerm{Float64}[],
        ),
        JuMP.MOI.ScalarAffineTerm(
            checked_float(coefficient),
            variable,
        ),
    )
    return nothing
end

function block_certificate_terms!(
    terms_by_moment::Dict{
        MomentKey,
        Vector{JuMP.MOI.ScalarAffineTerm{Float64}},
    },
    model::JuMP.Model,
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block,
)
    dimension = length(block.rows)
    backend = JuMP.backend(model)
    variables, constraint_index =
        JuMP.MOI.add_constrained_variables(
            backend,
            JuMP.MOI.PositiveSemidefiniteConeTriangle(dimension),
        )
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
    scalar_term_count = 0
    for first_row in 1:row_batch_size:dimension
        last_row = min(dimension, first_row + row_batch_size - 1)
        rows = collect(first_row:last_row)
        batch_polynomials = [
            Vector{ExactLinearPolynomial}(undef, dimension - row + 1)
            for row in rows
        ]
        Threads.@threads :dynamic for batch_index in eachindex(rows)
            row = rows[batch_index]
            for column in row:dimension
                polynomial = shastry_spin_isotypic_block_entry(
                    assembly,
                    block,
                    block.rows[row],
                    block.rows[column],
                )
                all(iszero ∘ imag, values(polynomial.terms)) ||
                    error(
                        "dual certificate retained an imaginary coefficient",
                    )
                batch_polynomials[batch_index][column - row + 1] =
                    polynomial
            end
        end
        for (batch_index, row) in enumerate(rows)
            for column in row:dimension
                output_index = column * (column - 1) ÷ 2 + row
                polynomial =
                    batch_polynomials[batch_index][column - row + 1]
                for (key, coefficient) in polynomial.terms
                    append_certificate_term!(
                        terms_by_moment,
                        key,
                        real(coefficient),
                        variables[output_index],
                    )
                    scalar_term_count += 1
                end
            end
        end
    end
    return constraint_index, scalar_term_count
end

"""
Build a native conic Farkas certificate for infeasibility of the primal
moment SDP.

For primal constraints `A_b(y) ⪰ 0`, `y_identity = 1`, and `E*y = 0`,
the model searches for `Z_b ⪰ 0` and free equality multipliers `u` such
that

    sum_b <A_{b,j}, Z_b> + delta(j, identity) + (E' * u)_j = 0

for every scalar moment `j`. Feasibility is therefore an explicit certificate
that the original fixed-gamma primal is infeasible. The PSD variables are
native solver matrix variables; unlike the bridged primal this formulation
does not introduce one auxiliary scalar equality per PSD triangle entry.
"""
function build_shastry_full_state_spin_isotypic_dual_certificate(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly;
    model::JuMP.Model,
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    backend = JuMP.backend(model)
    terms_by_moment = Dict{
        MomentKey,
        Vector{JuMP.MOI.ScalarAffineTerm{Float64}},
    }()
    psd_indices = Any[]
    scalar_term_count = 0
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        constraint_index, block_term_count =
            block_certificate_terms!(
                terms_by_moment,
                model,
                assembly,
                block,
            )
        push!(psd_indices, constraint_index)
        scalar_term_count += block_term_count
    end

    equality_multipliers = JuMP.MOI.VariableIndex[]
    for equality in assembly.equalities
        multiplier = JuMP.MOI.add_variable(backend)
        push!(equality_multipliers, multiplier)
        for (key, coefficient) in equality.terms
            iszero(imag(coefficient)) ||
                error("dual certificate equality is not exactly real")
            append_certificate_term!(
                terms_by_moment,
                key,
                real(coefficient),
                multiplier,
            )
            scalar_term_count += 1
        end
    end

    identity = moment_key()
    get!(
        terms_by_moment,
        identity,
        JuMP.MOI.ScalarAffineTerm{Float64}[],
    )
    moment_constraints = Dict{MomentKey,Any}()
    ordered_moments = sort!(
        collect(keys(terms_by_moment));
        by=key -> (moment_degree(key), key.canonical),
    )
    for key in ordered_moments
        function_object = JuMP.MOI.ScalarAffineFunction(
            terms_by_moment[key],
            key == identity ? 1.0 : 0.0,
        )
        moment_constraints[key] = JuMP.MOI.add_constraint(
            backend,
            function_object,
            JuMP.MOI.EqualTo(0.0),
        )
    end
    return ShastryFullStateSpinIsotypicDualCertificateModel(
        model,
        moment_constraints,
        psd_indices,
        equality_multipliers,
        scalar_term_count,
    )
end

end
