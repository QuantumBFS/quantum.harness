module ShastryFullStateSpinIsotypicDualCertificateMosek

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

export ShastryFullStateSpinIsotypicMosekDualCertificate,
       build_shastry_full_state_spin_isotypic_mosek_dual_certificate,
       optimize_shastry_full_state_spin_isotypic_mosek_dual_certificate!

struct ShastryFullStateSpinIsotypicMosekDualCertificate
    task::Mosek.Task
    moment_constraints::Dict{MomentKey,Int32}
    native_psd_blocks::Int
    equality_multipliers::Int
    scalar_coefficient_terms::Int
    coefficient_map_sha256::String
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

function ensure_moment_constraints!(
    task::Mosek.Task,
    moment_constraints::Dict{MomentKey,Int32},
    keys,
)
    new_keys = sort!(
        [
            key
            for key in keys
            if !haskey(moment_constraints, key)
        ];
        by=key -> (moment_degree(key), key.canonical),
    )
    isempty(new_keys) && return nothing
    first_index = Int(Mosek.getnumcon(task)) + 1
    Mosek.appendcons(task, length(new_keys))
    indices = Int32[
        first_index + offset - 1
        for offset in eachindex(new_keys)
    ]
    identity = moment_key()
    bounds = Float64[
        key == identity ? -1.0 : 0.0
        for key in new_keys
    ]
    Mosek.putconboundlist(
        task,
        indices,
        fill(Mosek.MSK_BK_FX, length(indices)),
        bounds,
        bounds,
    )
    for (key, index) in zip(new_keys, indices)
        moment_constraints[key] = index
    end
    return nothing
end

function append_block_triplets!(
    task::Mosek.Task,
    moment_constraints::Dict{MomentKey,Int32},
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
    block,
    block_index::Int,
    progress_callback::Function,
    coefficient_fingerprint::Union{Nothing,SHA.SHA2_256_CTX},
)
    dimension = length(block.rows)
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
                        "native Mosek dual retained an imaginary coefficient",
                    )
                batch_polynomials[batch_index][column - row + 1] =
                    polynomial
            end
        end

        batch_moments = Set{MomentKey}()
        for polynomials in batch_polynomials
            for polynomial in polynomials
                union!(batch_moments, keys(polynomial.terms))
            end
        end
        ensure_moment_constraints!(
            task,
            moment_constraints,
            batch_moments,
        )

        constraint_indices = Int32[]
        block_indices = Int32[]
        matrix_rows = Int32[]
        matrix_columns = Int32[]
        coefficients = Float64[]
        triangle_entries = sum(dimension - row + 1 for row in rows)
        sizehint!(constraint_indices, triangle_entries)
        sizehint!(block_indices, triangle_entries)
        sizehint!(matrix_rows, triangle_entries)
        sizehint!(matrix_columns, triangle_entries)
        sizehint!(coefficients, triangle_entries)
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
                for (key, coefficient) in polynomial.terms
                    push!(
                        constraint_indices,
                        moment_constraints[key],
                    )
                    push!(block_indices, Int32(block_index))
                    # MOSEK stores the lower triangle. Supplying the matrix
                    # entry itself gives the correct trace inner product:
                    # off-diagonal entries are doubled by <A, Z>.
                    push!(matrix_rows, Int32(column))
                    push!(matrix_columns, Int32(row))
                    push!(
                        coefficients,
                        checked_float(real(coefficient)),
                    )
                end
            end
        end
        Mosek.putbarablocktriplet(
            task,
            constraint_indices,
            block_indices,
            matrix_rows,
            matrix_columns,
            coefficients,
        )
        scalar_term_count += length(coefficients)
        progress_callback(
            "native Mosek block $block_index rows " *
            "$first_row:$last_row/$dimension; " *
            "moments=$(length(moment_constraints)), " *
            "terms=$scalar_term_count",
        )
    end
    return scalar_term_count
end

"""
Build the conic Farkas system directly in a native MOSEK task.

For a primal feasibility problem

    A_b(y) positive semidefinite, y_identity = 1, E*y = 0,

the returned task searches for Z_b positive semidefinite and free u such that

    sum_b <A_{b,j}, Z_b> + (E' * u)_j = -delta(j, identity).

Any feasible point of this task is therefore an infeasibility certificate for
the original fixed-gamma moment relaxation. Coefficients are streamed to
MOSEK in bounded row batches: no JuMP bridge, scalar PSD-entry variables, or
persistent Julia affine-term inventory is created.
"""
function build_shastry_full_state_spin_isotypic_mosek_dual_certificate(
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly;
    threads::Int=Threads.nthreads(),
    time_limit_seconds::Float64=43200.0,
    log_level::Int=1,
    progress_callback::Function=message -> nothing,
    fingerprint_coefficients::Bool=false,
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

    blocks = [assembly.positive_blocks; assembly.gap_blocks]
    Mosek.appendbarvars(
        task,
        Int32[length(block.rows) for block in blocks],
    )
    moment_constraints = Dict{MomentKey,Int32}()
    scalar_term_count = 0
    coefficient_fingerprint =
        fingerprint_coefficients ? SHA.SHA2_256_CTX() : nothing
    if !isnothing(coefficient_fingerprint)
        update_fingerprint!(
            coefficient_fingerprint,
            "shastry-full-state-spin-isotypic-coefficients-v1",
        )
    end
    for (block_index, block) in enumerate(blocks)
        scalar_term_count += append_block_triplets!(
            task,
            moment_constraints,
            assembly,
            block,
            block_index,
            progress_callback,
            coefficient_fingerprint,
        )
    end

    equality_count = length(assembly.equalities)
    if equality_count > 0
        first_variable = Int(Mosek.getnumvar(task)) + 1
        Mosek.appendvars(task, equality_count)
        Mosek.putvarboundsliceconst(
            task,
            first_variable,
            first_variable + equality_count,
            Mosek.MSK_BK_FR,
            -Inf,
            Inf,
        )
        for (offset, equality) in enumerate(assembly.equalities)
            all(iszero ∘ imag, values(equality.terms)) ||
                error("native Mosek dual equality is not exactly real")
            ensure_moment_constraints!(
                task,
                moment_constraints,
                keys(equality.terms),
            )
            variable_index = Int32(first_variable + offset - 1)
            constraint_indices = Int32[
                moment_constraints[key]
                for key in keys(equality.terms)
            ]
            variable_indices =
                fill(variable_index, length(constraint_indices))
            coefficients = Float64[
                checked_float(real(coefficient))
                for coefficient in values(equality.terms)
            ]
            Mosek.putaijlist(
                task,
                constraint_indices,
                variable_indices,
                coefficients,
            )
            scalar_term_count += length(coefficients)
        end
    end
    ensure_moment_constraints!(
        task,
        moment_constraints,
        (moment_key(),),
    )
    coefficient_map_sha256 = isnothing(coefficient_fingerprint) ?
        "omitted-streaming-v1" :
        bytes2hex(SHA.digest!(something(coefficient_fingerprint)))
    return ShastryFullStateSpinIsotypicMosekDualCertificate(
        task,
        moment_constraints,
        length(blocks),
        equality_count,
        scalar_term_count,
        coefficient_map_sha256,
    )
end

function optimize_shastry_full_state_spin_isotypic_mosek_dual_certificate!(
    certificate::ShastryFullStateSpinIsotypicMosekDualCertificate,
)
    Mosek.optimize(certificate.task)
    Mosek.solutionsummary(certificate.task, Mosek.MSK_STREAM_MSG)
    problem_status =
        Mosek.getprosta(certificate.task, Mosek.MSK_SOL_ITR)
    solution_status =
        Mosek.getsolsta(certificate.task, Mosek.MSK_SOL_ITR)
    classification = if solution_status == Mosek.MSK_SOL_STA_OPTIMAL
        "primal_infeasibility_certificate_found"
    elseif solution_status == Mosek.MSK_SOL_STA_PRIM_INFEAS_CER
        "no_dual_certificate_at_this_relaxation"
    else
        "dual_certificate_numerically_undetermined"
    end
    return (
        classification=classification,
        problem_status=problem_status,
        solution_status=solution_status,
    )
end

end
