module ShastryFullStateSpinIsotypicPrimalGapMosek

using Mosek
using SHA
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    moment_degree,
    moment_key,
    polynomial_sha256
using ..PrimalGapJuMP:
    checked_float
using ..ShastryFullStateSpinIsotypicReduction:
    ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block_label,
    shastry_spin_isotypic_block_entry
using ..ShastryFullStateSpinIsotypicDualCertificateMosek:
    su2_rank4_polynomial_projection

export ShastryFullStateSpinIsotypicMosekPrimal,
       build_shastry_full_state_spin_isotypic_mosek_primal,
       optimize_shastry_full_state_spin_isotypic_mosek_primal!

struct ShastryFullStateSpinIsotypicMosekPrimal
    task::Mosek.Task
    moment_variables::Dict{MomentKey,Int32}
    native_psd_blocks::Int
    equality_constraints::Int
    scalar_coefficient_terms::Int
    coefficient_map_sha256::String
    su2_rank4_reduction::Bool
    su2_rank4_eliminated_moments::Int
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

function ensure_moment_variables!(
    task::Mosek.Task,
    moment_variables::Dict{MomentKey,Int32},
    keys,
)
    new_keys = sort!(
        [
            key
            for key in keys
            if !haskey(moment_variables, key)
        ];
        by=key -> (moment_degree(key), key.canonical),
    )
    isempty(new_keys) && return nothing
    first_index = Int(Mosek.getnumvar(task)) + 1
    Mosek.appendvars(task, length(new_keys))
    indices = Int32[
        first_index + offset - 1
        for offset in eachindex(new_keys)
    ]
    identity = moment_key()
    bound_keys = Mosek.Boundkey[
        key == identity ? Mosek.MSK_BK_FX : Mosek.MSK_BK_FR
        for key in new_keys
    ]
    lower = Float64[key == identity ? 1.0 : -Inf for key in new_keys]
    upper = Float64[key == identity ? 1.0 : Inf for key in new_keys]
    Mosek.putvarboundlist(task, indices, bound_keys, lower, upper)
    for (key, index) in zip(new_keys, indices)
        moment_variables[key] = index
    end
    return nothing
end

# MOSEK's svec PSD domain orders the lower triangle column-by-column.
# The symbolic code visits the equivalent upper triangle column-by-column.
function mosek_svec_index(
    dimension::Int,
    row::Int,
    column::Int,
)
    1 <= row <= column <= dimension ||
        throw(BoundsError((dimension, row, column)))
    preceding =
        (row - 1) * (dimension + 1) - (row - 1) * row ÷ 2
    return preceding + column - row + 1
end

function append_primal_block!(
    task::Mosek.Task,
    moment_variables::Dict{MomentKey,Int32},
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block,
    block_index::Int,
    progress_callback::Function,
    coefficient_fingerprint::Union{Nothing,SHA.SHA2_256_CTX},
    su2_rank4_reduction::Bool,
    su2_rank4_eliminated_moments::Set{MomentKey},
    su2_rank4_projection_cache::Dict{MomentKey,ExactLinearPolynomial},
)
    dimension = length(block.rows)
    triangle_entries = dimension * (dimension + 1) ÷ 2
    first_afe = Int(Mosek.getnumafe(task)) + 1
    Mosek.appendafes(task, triangle_entries)
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
                        "native Mosek primal retained an imaginary coefficient",
                    )
                batch_polynomials[batch_index][column - row + 1] =
                    polynomial
            end
        end

        if su2_rank4_reduction
            for polynomials in batch_polynomials
                for index in eachindex(polynomials)
                    polynomials[index] = su2_rank4_polynomial_projection(
                        polynomials[index],
                        assembly,
                        su2_rank4_eliminated_moments,
                        su2_rank4_projection_cache,
                    )
                end
            end
        end

        batch_moments = Set{MomentKey}()
        for polynomials in batch_polynomials
            for polynomial in polynomials
                union!(batch_moments, keys(polynomial.terms))
            end
        end
        ensure_moment_variables!(
            task,
            moment_variables,
            batch_moments,
        )

        afe_indices = Int64[]
        variable_indices = Int32[]
        coefficients = Float64[]
        batch_triangle_entries =
            sum(dimension - row + 1 for row in rows)
        sizehint!(afe_indices, batch_triangle_entries)
        sizehint!(variable_indices, batch_triangle_entries)
        sizehint!(coefficients, batch_triangle_entries)
        for (batch_index, row) in enumerate(rows)
            for column in row:dimension
                polynomial =
                    batch_polynomials[batch_index][column - row + 1]
                if !isnothing(coefficient_fingerprint)
                    update_fingerprint!(
                        coefficient_fingerprint,
                        string(
                            block_label(block),
                            "[",
                            row,
                            ",",
                            column,
                            "]=",
                            polynomial_sha256(polynomial),
                        ),
                    )
                end
                afe_index = Int64(
                    first_afe +
                    mosek_svec_index(dimension, row, column) -
                    1,
                )
                scale = row == column ? 1.0 : sqrt(2.0)
                for (key, coefficient) in polynomial.terms
                    push!(afe_indices, afe_index)
                    push!(variable_indices, moment_variables[key])
                    push!(
                        coefficients,
                        scale * checked_float(real(coefficient)),
                    )
                end
            end
        end
        Mosek.putafefentrylist(
            task,
            afe_indices,
            variable_indices,
            coefficients,
        )
        scalar_term_count += length(coefficients)
        progress_callback(
            "native primal block $block_index rows " *
            "$first_row:$last_row/$dimension; " *
            "moments=$(length(moment_variables)), " *
            "terms=$scalar_term_count",
        )
    end
    domain =
        Mosek.appendsvecpsdconedomain(task, triangle_entries)
    Mosek.appendaccseq(task, domain, first_afe, nothing)
    return scalar_term_count
end

function append_primal_equalities!(
    task::Mosek.Task,
    moment_variables::Dict{MomentKey,Int32},
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    equalities,
    su2_rank4_reduction::Bool,
    su2_rank4_eliminated_moments::Set{MomentKey},
    su2_rank4_projection_cache::Dict{MomentKey,ExactLinearPolynomial},
)
    isempty(equalities) && return 0
    first_constraint = Int(Mosek.getnumcon(task)) + 1
    Mosek.appendcons(task, length(equalities))
    constraint_indices = Int32[
        first_constraint + offset - 1
        for offset in eachindex(equalities)
    ]
    Mosek.putconboundlistconst(
        task,
        constraint_indices,
        Mosek.MSK_BK_FX,
        0.0,
        0.0,
    )
    scalar_term_count = 0
    for (offset, equality) in enumerate(equalities)
        projected_equality = su2_rank4_reduction ?
            su2_rank4_polynomial_projection(
                equality,
                assembly,
                su2_rank4_eliminated_moments,
                su2_rank4_projection_cache,
            ) :
            equality
        all(iszero ∘ imag, values(projected_equality.terms)) ||
            error("native Mosek primal equality is not exactly real")
        ensure_moment_variables!(
            task,
            moment_variables,
            keys(projected_equality.terms),
        )
        keys_in_order = collect(keys(projected_equality.terms))
        Mosek.putaijlist(
            task,
            fill(
                Int32(first_constraint + offset - 1),
                length(keys_in_order),
            ),
            Int32[moment_variables[key] for key in keys_in_order],
            Float64[
                checked_float(real(projected_equality.terms[key]))
                for key in keys_in_order
            ],
        )
        scalar_term_count += length(keys_in_order)
    end
    return scalar_term_count
end

"""
Build the original reduced moment feasibility SDP directly in a MOSEK task.

Each PSD affine matrix is represented by a native svec affine conic
constraint. Exact symbolic coefficients are generated in bounded row batches
and immediately transferred to MOSEK. This avoids both JuMP's vector-affine
inventory and the scalar equality bridge for every PSD triangle entry.
"""
function build_shastry_full_state_spin_isotypic_mosek_primal(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly;
    threads::Int=Threads.nthreads(),
    time_limit_seconds::Float64=43200.0,
    log_level::Int=1,
    progress_callback::Function=message -> nothing,
    fingerprint_coefficients::Bool=false,
    su2_rank4_reduction::Bool=false,
)
    task = Mosek.maketask()
    Mosek.putstreamfunc(
        task,
        Mosek.MSK_STREAM_LOG,
        message -> begin
            print(stdout, message)
            flush(stdout)
        end,
    )
    Mosek.putintparam(task, Mosek.MSK_IPAR_NUM_THREADS, threads)
    Mosek.putintparam(task, Mosek.MSK_IPAR_LOG, log_level)
    Mosek.putdouparam(
        task,
        Mosek.MSK_DPAR_OPTIMIZER_MAX_TIME,
        time_limit_seconds,
    )
    Mosek.putobjsense(task, Mosek.MSK_OBJECTIVE_SENSE_MINIMIZE)

    moment_variables = Dict{MomentKey,Int32}()
    ensure_moment_variables!(task, moment_variables, (moment_key(),))
    coefficient_fingerprint =
        fingerprint_coefficients ? SHA.SHA2_256_CTX() : nothing
    su2_rank4_eliminated_moments = Set{MomentKey}()
    su2_rank4_projection_cache =
        Dict{MomentKey,ExactLinearPolynomial}()
    if !isnothing(coefficient_fingerprint)
        update_fingerprint!(
            coefficient_fingerprint,
            su2_rank4_reduction ?
            "shastry-full-state-spin-isotypic-su2-rank4-coefficients-v1" :
            "shastry-full-state-spin-isotypic-coefficients-v1",
        )
    end
    scalar_term_count = 0
    blocks = [assembly.positive_blocks; assembly.gap_blocks]
    for (block_index, block) in enumerate(blocks)
        scalar_term_count += append_primal_block!(
            task,
            moment_variables,
            assembly,
            block,
            block_index,
            progress_callback,
            coefficient_fingerprint,
            su2_rank4_reduction,
            su2_rank4_eliminated_moments,
            su2_rank4_projection_cache,
        )
    end
    scalar_term_count += append_primal_equalities!(
        task,
        moment_variables,
        assembly,
        assembly.equalities,
        su2_rank4_reduction,
        su2_rank4_eliminated_moments,
        su2_rank4_projection_cache,
    )
    coefficient_map_sha256 = isnothing(coefficient_fingerprint) ?
        "omitted-streaming-v1" :
        bytes2hex(SHA.digest!(something(coefficient_fingerprint)))
    return ShastryFullStateSpinIsotypicMosekPrimal(
        task,
        moment_variables,
        length(blocks),
        length(assembly.equalities),
        scalar_term_count,
        coefficient_map_sha256,
        su2_rank4_reduction,
        length(su2_rank4_eliminated_moments),
    )
end

function optimize_shastry_full_state_spin_isotypic_mosek_primal!(
    primal::ShastryFullStateSpinIsotypicMosekPrimal,
)
    Mosek.optimize(primal.task)
    Mosek.solutionsummary(primal.task, Mosek.MSK_STREAM_MSG)
    problem_status = Mosek.getprosta(primal.task, Mosek.MSK_SOL_ITR)
    solution_status = Mosek.getsolsta(primal.task, Mosek.MSK_SOL_ITR)
    classification = if solution_status == Mosek.MSK_SOL_STA_OPTIMAL
        "feasible_native_primal"
    elseif solution_status == Mosek.MSK_SOL_STA_PRIM_INFEAS_CER
        "primal_infeasibility_certificate_found"
    else
        "native_primal_numerically_undetermined"
    end
    acc_count = Int(Mosek.getnumacc(primal.task))
    maximum_acc_violation = acc_count == 0 ?
        0.0 :
        maximum(
            Mosek.getpviolacc(
                primal.task,
                Mosek.MSK_SOL_ITR,
                Int64.(1:acc_count),
            ),
        )
    constraint_count = Int(Mosek.getnumcon(primal.task))
    maximum_equality_violation = constraint_count == 0 ?
        0.0 :
        maximum(
            Mosek.getpviolcon(
                primal.task,
                Mosek.MSK_SOL_ITR,
                Int32.(1:constraint_count),
            ),
        )
    return (
        classification=classification,
        problem_status=problem_status,
        solution_status=solution_status,
        maximum_acc_violation=maximum_acc_violation,
        maximum_equality_violation=maximum_equality_violation,
    )
end

end
