function _evaluate_exact_row(row::ParametricRow,params::ModelParams)
    result = Dict{Int,Q23}()
    for (index,coefficient) in row
        value = evaluate(coefficient,params)
        iszero(imag(value)) || throw(ArgumentError("exact real conic row acquired an imaginary coefficient"))
        iszero(real(value)) || (result[index]=real(value))
    end
    result
end

function _expr_coefficients_exact(expr::MomentExpr,params::ModelParams,orbit::MomentOrbit)
    realrow,imagrow = _expr_parametric_coefficients(expr,orbit)
    _evaluate_exact_row(realrow,params),_evaluate_exact_row(imagrow,params)
end

function _certificate_equations(template,params,orbit)
    rows = Dict{Int,Q23}[]
    identity = PureStateMonomial()
    rep = isless(adjoint(identity),identity) ? adjoint(identity) : identity
    push!(rows,Dict(orbit.real_index[rep]=>Q23(1)))
    for expression in template.stationarity
        realrow,imagrow = _expr_parametric_coefficients(expression,orbit)
        isempty(realrow) || push!(rows,_evaluate_exact_row(realrow,params))
        isempty(imagrow) || push!(rows,_evaluate_exact_row(imagrow,params))
    end
    rows
end

_rounded_q23(x::Float64) = Q23(rationalize(BigInt,x,tol=1e-12))

function _dual_projection_system(template,params,dualdata)
    orbit = _moment_orbits(template.moment_keys)
    nprimal = _nvariables(orbit)
    equation_rows = _certificate_equations(template,params,orbit)
    multipliers = dualdata["equality_multipliers"]
    matrices = dualdata["psd_matrices"]
    length(multipliers)==length(equation_rows) || throw(ArgumentError("dual equality count mismatch"))
    allblocks = [template.moment_blocks;template.gap_blocks]
    length(matrices)==length(allblocks) || throw(ArgumentError("dual PSD block count mismatch"))
    coordinate_count = length(equation_rows)+sum(
        (2length(block.basis))*(2length(block.basis)+1)÷2 for block in allblocks;init=0,
    )
    max_columns = parse(Int,get(ENV,"ISSUE92_CERTIFICATE_MAX_COLUMNS","5000000"))
    coordinate_count <= max_columns || throw(ArgumentError(
        "certificate projection has $coordinate_count columns, above configured limit $max_columns",
    ))

    columns = Dict{Int,Q23}[]
    initial = Q23[]
    for (row,value) in zip(equation_rows,multipliers)
        push!(columns,copy(row))
        push!(initial,_rounded_q23(value))
    end
    block_columns = UnitRange{Int}[]
    block_shapes = Int[]
    for (block,zfloat) in zip(allblocks,matrices)
        n = length(block.basis)
        size(zfloat)==(2n,2n) || throw(ArgumentError("dual PSD matrix shape mismatch"))
        start = length(columns)+1
        pair_column = Dict{Tuple{Int,Int},Int}()
        for i in 1:2n, j in i:2n
            pair_column[(i,j)] = length(columns)+1
            push!(columns,Dict{Int,Q23}())
            push!(initial,_rounded_q23(zfloat[i,j]))
        end
        push!(block_columns,start:length(columns))
        push!(block_shapes,2n)
        add_at!(p::Int,q::Int,index::Int,value::Q23) = begin
            pair = p<=q ? (p,q) : (q,p)
            column = columns[pair_column[pair]]
            column[index] = get(column,index,Q23(0))+value
        end
        for i in 1:n,j in 1:n
            realrow,imagrow = _expr_coefficients_exact(block.entries[i,j],params,orbit)
            for (index,value) in realrow
                add_at!(i,j,index,value)
                add_at!(n+i,n+j,index,value)
            end
            for (index,value) in imagrow
                add_at!(i,n+j,index,-value)
                add_at!(n+i,j,index,value)
            end
        end
    end
    @assert length(columns)==coordinate_count
    columns,initial,nprimal,length(equation_rows),block_columns,block_shapes
end

function _matvec(columns::Vector{Dict{Int,Q23}},x::Vector{Q23},nrows::Int)
    length(columns)==length(x) || throw(DimensionMismatch())
    result = fill(Q23(0),nrows)
    for (column,value) in zip(columns,x)
        iszero(value) && continue
        for (row,coefficient) in column
            result[row] += coefficient*value
        end
    end
    result
end

function _sparse_axpy!(target::Dict{Int,Q23},scale::Q23,source::Dict{Int,Q23})
    iszero(scale) && return target
    for (index,value) in source
        updated = get(target,index,Q23(0))+scale*value
        iszero(updated) ? delete!(target,index) : (target[index]=updated)
    end
    target
end

function _sparse_scale!(target::Dict{Int,Q23},scale::Q23)
    for index in collect(keys(target))
        value = target[index]*scale
        iszero(value) ? delete!(target,index) : (target[index]=value)
    end
    target
end

"""Solve `columns * x = rhs` by exact sparse column elimination.

Columns with the fewest nonzeros are considered first, which favors direct
moment/Gram corrections and limits fill.  The returned correction is sparse
in the dual coordinates.  Excluded columns are held fixed during projection.
"""
function _solve_exact_sparse_columns(columns::Vector{Dict{Int,Q23}},rhs::Vector{Q23};
                                     excluded::Set{Int}=Set{Int}())
    basis_vectors = Dict{Int,Dict{Int,Q23}}()
    basis_combinations = Dict{Int,Dict{Int,Q23}}()
    order = sort!([index for index in eachindex(columns)
                   if !(index in excluded) && !isempty(columns[index])];
                  by=index->(length(columns[index]),index))
    for column_index in order
        vector = copy(columns[column_index])
        combination = Dict(column_index=>Q23(1))
        while !isempty(vector)
            pivot = minimum(keys(vector))
            if haskey(basis_vectors,pivot)
                factor = vector[pivot]
                _sparse_axpy!(vector,-factor,basis_vectors[pivot])
                _sparse_axpy!(combination,-factor,basis_combinations[pivot])
            else
                scale = inv(vector[pivot])
                _sparse_scale!(vector,scale)
                _sparse_scale!(combination,scale)
                basis_vectors[pivot] = vector
                basis_combinations[pivot] = combination
                break
            end
        end
        length(basis_vectors)==length(rhs) && break
    end

    remainder = Dict(index=>value for (index,value) in enumerate(rhs) if !iszero(value))
    correction = Dict{Int,Q23}()
    while !isempty(remainder)
        pivot = minimum(keys(remainder))
        haskey(basis_vectors,pivot) || return nothing
        factor = remainder[pivot]
        _sparse_axpy!(remainder,-factor,basis_vectors[pivot])
        _sparse_axpy!(correction,factor,basis_combinations[pivot])
    end
    correction
end

function _q23_big(x::Q23,precision::Int=256)
    setprecision(BigFloat,precision) do
        q(v) = BigFloat(numerator(v))/BigFloat(denominator(v))
        q(x.a)+q(x.b)*sqrt(BigFloat(2))+q(x.c)*sqrt(BigFloat(3))+q(x.d)*sqrt(BigFloat(6))
    end
end

"""Exact-field PSD check by symmetrically pivoted Schur complements.

A positive diagonal pivot gives an exact congruence between the current block
and that pivot plus its Schur complement.  If no positive diagonal remains,
the block is PSD exactly when it is the zero matrix.  Selecting the largest
floating diagonal only controls expression growth; every sign and update is
performed in Q(sqrt(2),sqrt(3)).
"""
function _exact_psd(matrix::Matrix{Q23})
    n = size(matrix,1)
    matrix == transpose(matrix) || return false,-Inf
    working = copy(matrix)
    for k in 1:n
        pivot_index = 0
        pivot_magnitude = -Inf
        for i in k:n
            diagonal_sign = _q23_sign(working[i,i])
            diagonal_sign < 0 && return false,-Inf
            if diagonal_sign > 0
                magnitude = abs(Float64(working[i,i]))
                if pivot_index == 0 || magnitude > pivot_magnitude
                    pivot_index = i
                    pivot_magnitude = magnitude
                end
            end
        end
        if pivot_index == 0
            for i in k:n,j in i:n
                iszero(working[i,j]) || return false,-Inf
            end
            return true,0.0
        end
        if pivot_index != k
            for j in 1:n
                working[k,j],working[pivot_index,j] = working[pivot_index,j],working[k,j]
            end
            for i in 1:n
                working[i,k],working[i,pivot_index] = working[i,pivot_index],working[i,k]
            end
        end
        pivot_inverse = inv(working[k,k])
        column = Q23[working[i,k] for i in k+1:n]
        scaled_column = Q23[value*pivot_inverse for value in column]
        for local_i in eachindex(column),local_j in local_i:length(column)
            i = k+local_i
            j = k+local_j
            updated = working[i,j]-scaled_column[local_i]*column[local_j]
            working[i,j] = working[j,i] = updated
        end
        for i in k+1:n
            working[i,k] = working[k,i] = Q23(0)
        end
    end
    true,0.0
end

"""Rigorous fixed-precision LDL test for a strictly positive exact matrix.

Each exact algebraic entry is enclosed in a 256-bit Arb interval.  If every
interval pivot is strictly positive, interval arithmetic proves positive
definiteness and hence PSD.  A nonpositive or zero-containing pivot is only
inconclusive: callers must retain the exact-field LDL fallback so singular
positive-semidefinite matrices are still handled without weakening rigor.
"""
function _arb_strictly_positive_definite(matrix::Matrix{Q23};precision::Int=256)
    n = size(matrix,1)
    matrix == transpose(matrix) || return false
    zero_arb() = Arblib.Arb(0;prec=precision)
    l = [zero_arb() for _ in 1:n, _ in 1:n]
    diagonal = [zero_arb() for _ in 1:n]
    for k in 1:n
        pivot = _q23_arb(matrix[k,k],precision)
        for j in 1:k-1
            pivot -= l[k,j]*l[k,j]*diagonal[j]
        end
        Arblib.ispositive(pivot) || return false
        diagonal[k] = pivot
        for i in k+1:n
            remainder = _q23_arb(matrix[i,k],precision)
            for j in 1:k-1
                remainder -= l[i,j]*l[k,j]*diagonal[j]
            end
            l[i,k] = remainder/pivot
        end
    end
    true
end

"""Try to prove non-PSD with an exact quadratic witness chosen numerically.

The floating eigensolve is used only to choose integer vectors.  A negative
answer is returned solely when exact Q(sqrt(2),sqrt(3)) arithmetic proves
`v' * matrix * v < 0`; failure to find such a vector is inconclusive.  This
cheap rejection path avoids a large exact-field LDL when projection has made
a Gram block genuinely indefinite, while never accepting a PSD block.
"""
function _exact_negative_witness(matrix::Matrix{Q23})
    n = size(matrix,1)
    n == 0 && return false
    floating = Matrix{Float64}(undef,n,n)
    for j in 1:n,i in 1:n
        floating[i,j] = Float64(matrix[i,j])
    end
    all(isfinite,floating) || return false
    decomposition = LinearAlgebra.eigen(LinearAlgebra.Symmetric(floating))
    direction = @view decomposition.vectors[:,1]
    for scale in (big(2)^10,big(2)^20,big(2)^30)
        vector = BigInt[round(BigInt,BigFloat(value)*scale) for value in direction]
        all(iszero,vector) && continue
        quadratic = Q23(0)
        for i in 1:n
            quadratic += matrix[i,i]*(vector[i]*vector[i])
            for j in i+1:n
                quadratic += matrix[i,j]*(2*vector[i]*vector[j])
            end
        end
        _q23_sign(quadratic) < 0 && return true
    end
    false
end

function _reconstruct_dual_matrices(projected,block_columns,block_shapes)
    matrices = Matrix{Q23}[]
    for (range,n) in zip(block_columns,block_shapes)
        matrix = fill(Q23(0),n,n)
        cursor = first(range)
        for i in 1:n,j in i:n
            matrix[i,j]=matrix[j,i]=projected[cursor]
            cursor += 1
        end
        push!(matrices,matrix)
    end
    matrices
end

function _unverified_certificate(message;kind=:NONE)
    CertificateReport(:UNVERIFIED,kind,false,false,false,false,false,256,
                      -Inf,Inf,-Inf,nothing,Inf,message)
end

function _certificate_report_dict(report::CertificateReport)
    Dict(
        "classification"=>String(report.classification),
        "certificate_kind"=>String(report.certificate_kind),
        "projected"=>report.projected,
        "psd_verified"=>report.psd_verified,
        "affine_verified"=>report.affine_verified,
        "margin_verified"=>report.margin_verified,
        "objective_gap_verified"=>report.objective_gap_verified,
        "precision_bits"=>report.precision_bits,
        "min_eigenvalue_lower"=>report.min_eigenvalue_lower,
        "max_affine_residual"=>report.max_affine_residual,
        "farkas_margin_lower"=>report.farkas_margin_lower,
        "certified_objective"=>report.certified_objective,
        "normalized_objective_gap"=>report.normalized_objective_gap,
        "message"=>report.message,
    )
end

function _check_projected_psd(projected,block_columns,block_shapes)
    matrices = _reconstruct_dual_matrices(projected,block_columns,block_shapes)
    psd_ok = true
    minimum_bound = Inf
    for (block_index,matrix) in enumerate(matrices)
        # Strictly positive projected Gram blocks are much faster to certify
        # with fixed-precision interval LDL than with rational expressions
        # whose numerators and denominators can grow to thousands of digits.
        # A numerically selected but exactly checked negative quadratic witness
        # rejects genuinely indefinite blocks before that expensive fallback.
        # Singular/inconclusive blocks still use the original exact-field LDL.
        method = "interval LDL"
        if _arb_strictly_positive_definite(matrix)
            ok,bound = true,0.0
        elseif _exact_negative_witness(matrix)
            method = "exact negative witness"
            ok,bound = false,-Inf
        else
            method = "pivoted exact-field LDL/Schur fallback"
            ok,bound = _exact_psd(matrix)
        end
        _certificate_progress(
            "PSD block $(block_index)/$(length(matrices)) ($(size(matrix,1))x$(size(matrix,2))) " *
            "used $(method): PSD=$(ok)",
        )
        psd_ok &= ok
        minimum_bound = min(minimum_bound,bound)
    end
    psd_ok,minimum_bound,matrices
end

function _preserve_projected_certificate!(dualdata,kind,projected,nequalities,matrices;extra=Dict())
    certificate = Dict{String,Any}(
        "kind"=>String(kind),
        "field"=>"Q(sqrt(2),sqrt(3))",
        "equality_multipliers"=>projected[1:nequalities],
        "psd_matrices"=>matrices,
    )
    merge!(certificate,extra)
    dualdata["projected_certificate"] = certificate
end

function _certificate_progress(message)
    get(ENV,"ISSUE92_SOLVE_PROGRESS","0") == "1" || return
    println("certificate progress: $message")
    flush(stdout)
end

"""Find a strictly interior floating dual at a nearby conservative bound.

Optimal SDP duals are commonly singular, so direct rational rounding can
create tiny negative eigenvalues.  This auxiliary SDP fixes the normalization
multiplier to a slightly weaker bound and maximizes a common Gram-matrix
interior margin.  Its output is only a candidate: callers still round it,
project it onto the exact coefficient identity, and run exact PSD checks.
"""
function _interior_observable_projection(columns,target,block_columns,block_shapes,
                                         objective_value::Float64,sense::Symbol)
    max_columns = parse(Int,get(ENV,"ISSUE92_CERTIFICATE_INTERIOR_MAX_COLUMNS","250000"))
    length(columns) <= max_columns || return nothing

    # Reuse the configured Clarabel factory so SCNet certificate projection
    # honors the selected MKL/CHOLMOD/QDLDL backend, thread limit, tolerances,
    # and wall-time profile instead of silently falling back to QDLDL.
    phase_started = time()
    _certificate_progress("assembling strictly-interior observable SDP with $(length(columns)) dual columns")
    model,_ = _make_optimizer(:clarabel,true)
    JuMP.@variable(model,x[1:length(columns)])
    JuMP.@variable(model,interior_margin >= 0)

    row_entries = [Tuple{Int,Float64}[] for _ in eachindex(target)]
    for (column_index,column) in enumerate(columns), (row,coefficient) in column
        push!(row_entries[row],(column_index,Float64(coefficient)))
    end
    for row in eachindex(target)
        expression = JuMP.AffExpr(0.0)
        for (column_index,coefficient) in row_entries[row]
            JuMP.add_to_expression!(expression,coefficient,x[column_index])
        end
        JuMP.@constraint(model,expression==Float64(target[row]))
    end

    for (range,n) in zip(block_columns,block_shapes)
        matrix = Matrix{JuMP.AffExpr}(undef,n,n)
        cursor = first(range)
        for i in 1:n,j in i:n
            entry = JuMP.AffExpr(0.0)
            JuMP.add_to_expression!(entry,1.0,x[cursor])
            matrix[i,j] = matrix[j,i] = entry
            cursor += 1
        end
        for i in 1:n
            JuMP.add_to_expression!(matrix[i,i],-1.0,interior_margin)
        end
        JuMP.@constraint(model,LinearAlgebra.Symmetric(matrix) in JuMP.PSDCone())
    end
    bound_constraint = JuMP.@constraint(model,x[1]==0.0)
    JuMP.@objective(model,Max,interior_margin)
    _certificate_progress("strictly-interior observable SDP assembled in $(round(time()-phase_started;digits=2))s")

    scale = 1+abs(objective_value)
    sense_sign = sense == :min ? 1.0 : -1.0
    for normalized_backoff in (1e-7,5e-7,2e-6,1e-5)
        certified = sense == :min ?
            objective_value-normalized_backoff*scale :
            objective_value+normalized_backoff*scale
        multiplier = sense_sign*certified
        JuMP.set_normalized_rhs(bound_constraint,multiplier)
        phase_started = time()
        _certificate_progress("solving interior SDP at normalized backoff $(normalized_backoff)")
        JuMP.optimize!(model)
        status = JuMP.termination_status(model)
        _certificate_progress("interior SDP returned $(status) in $(round(time()-phase_started;digits=2))s")
        status in (MathOptInterface.OPTIMAL,MathOptInterface.ALMOST_OPTIMAL) || continue
        margin_value = JuMP.value(interior_margin)
        _certificate_progress("interior SDP margin $(margin_value)")
        margin_value > 1e-9 || continue
        phase_started = time()
        initial = Q23[_rounded_q23(JuMP.value(variable)) for variable in x]
        # Fix the bound coordinate to exactly the same rational used in the
        # affine projection; it is excluded from the correction below.
        initial[1] = _rounded_q23(multiplier)
        residual = _matvec(columns,initial,length(target))-target
        correction = _solve_exact_sparse_columns(columns,-residual;excluded=Set([1]))
        correction === nothing && continue
        for (index,value) in correction
            initial[index] += value
        end
        exact_residual = _matvec(columns,initial,length(target))-target
        affine_ok = all(iszero,exact_residual)
        maxres = maximum(abs(Float64(_q23_big(x))) for x in exact_residual;init=0.0)
        psd_ok,minimum_bound,matrices =
            _check_projected_psd(initial,block_columns,block_shapes)
        _certificate_progress(
            "interior exact projection and rigorous PSD check finished in $(round(time()-phase_started;digits=2))s " *
            "(affine=$(affine_ok), PSD=$(psd_ok), lower=$(minimum_bound))",
        )
        affine_ok && psd_ok && return (initial,maxres,minimum_bound,matrices)
    end
    nothing
end

"""Round and exactly project an infeasibility ray or observable dual bound.

For infeasibility records the target identity is zero and a positive
normalization multiplier is required.  For observable records the target is
the exact signed objective row; the resulting normalization multiplier is a
rigorous lower (`:min`) or upper (`:max`) bound.  The two certificate types
are deliberately disjoint so a feasible solve can never be reinterpreted as
an exclusion.
"""
function verify_certificate(template::HierarchyTemplate,record::SolveRecord)
    observable = get(record.primal,"objective",nothing)
    sense = get(record.primal,"sense",nothing)
    is_observable = observable !== nothing
    if is_observable
        kind = sense == :min ? :LOWER_BOUND : sense == :max ? :UPPER_BOUND : :NONE
        kind == :NONE && return _unverified_certificate(
            "observable record does not preserve a valid optimization sense";kind=kind,
        )
        record.classification == :FEASIBLE || return _unverified_certificate(
            "exact observable projection requires a primal/dual-checked FEASIBLE solve";kind=kind,
        )
    else
        kind = :EXCLUSION
        record.classification == :FEASIBLE && return _unverified_certificate(
            "a FEASIBLE record cannot be checked as an exclusion";kind=kind,
        )
        record.certificate_class in (:FLOATING_CANDIDATE,:VERIFIED_EXACT_PROJECTED) ||
            return _unverified_certificate(
                "record is neither a floating nor a previously verified infeasibility candidate";kind=kind,
            )
    end
    get(record.dual,"available",false) ||
        return _unverified_certificate("no dual data was preserved";kind=kind)
    params = get(record.primal,"params",nothing)
    params isa ModelParams ||
        return _unverified_certificate("record does not preserve exact model parameters";kind=kind)

    try
        phase_started = time()
        _certificate_progress("assembling exact dual coefficient system for $(kind)")
        columns,rounded,nprimal,nequalities,block_columns,block_shapes =
            _dual_projection_system(template,params,record.dual)
        _certificate_progress(
            "exact dual system assembled in $(round(time()-phase_started;digits=2))s " *
            "($(length(columns)) columns, $(nprimal) coefficient rows)",
        )

        target = fill(Q23(0),nprimal)
        if is_observable
            haskey(template.objectives,Symbol(observable)) || throw(ArgumentError(
                "unknown preserved observable $(Symbol(observable))",
            ))
            objective_row,imaginary_row = _expr_coefficients_exact(
                template.objectives[Symbol(observable)],params,_moment_orbits(template.moment_keys),
            )
            all(iszero,values(imaginary_row)) || throw(ArgumentError(
                "observable objective has a nonzero exact imaginary row",
            ))
            sense_sign = sense == :min ? Q23(1) : Q23(-1)
            for (index,value) in objective_row
                target[index] = sense_sign*value
            end
        end

        phase_started = time()
        residual = _matvec(columns,rounded,nprimal)-target
        excluded = is_observable ? Set{Int}() : Set([1])
        correction = _solve_exact_sparse_columns(columns,-residual;excluded=excluded)
        # For an exclusion, first try to preserve the Farkas margin.  Fall
        # back to the full column space only when other coordinates cannot
        # absorb the exact rounding residual.
        !is_observable && correction === nothing &&
            (correction = _solve_exact_sparse_columns(columns,-residual))
        correction === nothing &&
            return _unverified_certificate(
                "dual coefficients could not be projected onto the exact target identity";kind=kind,
            )
        projected = copy(rounded)
        for (index,value) in correction
            projected[index] += value
        end
        _certificate_progress("exact affine projection finished in $(round(time()-phase_started;digits=2))s")

        margin = Q23(0)
        margin_ok = false
        if !is_observable
            margin = projected[1] # normalization is the first equality and has RHS one
            margin_ok = _q23_sign(margin)>0
            if margin_ok
                scale = inv(margin)
                projected .*= scale
                margin = Q23(1)
            end
        end
        exact_residual = _matvec(columns,projected,nprimal)-target
        affine_ok = all(iszero,exact_residual)
        maxres = maximum(abs(Float64(_q23_big(x))) for x in exact_residual;init=0.0)
        phase_started = time()
        psd_ok,minimum_bound,matrices =
            _check_projected_psd(projected,block_columns,block_shapes)
        _certificate_progress(
            "initial rigorous PSD check finished in $(round(time()-phase_started;digits=2))s " *
            "(PSD=$(psd_ok), lower=$(minimum_bound))",
        )

        if !is_observable
            margin_value = Float64(_q23_big(margin))
            verified = affine_ok && psd_ok && margin_ok
            classification = verified ? :VERIFIED_EXCLUSION : :UNVERIFIED
            message = verified ?
                "exact Q(sqrt2,sqrt3) projection, 256-bit Arb interval/exact-fallback PSD LDL, and positive Farkas margin passed" :
                "projected exclusion dual failed an exact affine, PSD, or positive-margin check"
            verified && _preserve_projected_certificate!(
                record.dual,kind,projected,nequalities,matrices;
                extra=Dict("farkas_margin"=>margin),
            )
            return CertificateReport(classification,kind,true,psd_ok,affine_ok,margin_ok,false,256,
                                     minimum_bound,maxres,margin_value,nothing,Inf,message)
        end

        if !psd_ok
            _certificate_progress("initial observable Gram matrices are not exact PSD; starting interior projection")
            interior = _interior_observable_projection(
                columns,target,block_columns,block_shapes,record.objective::Float64,sense,
            )
            if interior !== nothing
                projected,maxres,minimum_bound,matrices = interior
                affine_ok = true
                psd_ok = true
            end
        end

        sense_sign = sense == :min ? Q23(1) : Q23(-1)
        certified_exact = sense_sign*projected[1]
        certified_value = Float64(_q23_big(certified_exact))
        primal_value = record.objective::Float64
        signed_gap = sense == :min ? primal_value-certified_value : certified_value-primal_value
        normalized_gap = signed_gap/(1+max(abs(primal_value),abs(certified_value)))
        gap_ok = normalized_gap >= -1e-6 && normalized_gap <= 1.1e-5
        verified = affine_ok && psd_ok && gap_ok
        classification = verified ?
            (sense == :min ? :VERIFIED_LOWER_BOUND : :VERIFIED_UPPER_BOUND) : :UNVERIFIED
        message = verified ?
            "exact Q(sqrt2,sqrt3) observable identity, 256-bit Arb interval/exact-fallback PSD LDL, and primal/dual agreement passed" :
            "projected observable dual failed an exact affine, PSD, or normalized objective-gap check"
        verified && _preserve_projected_certificate!(
            record.dual,kind,projected,nequalities,matrices;
            extra=Dict(
                "observable"=>Symbol(observable),"sense"=>sense,
                "certified_objective"=>certified_exact,
            ),
        )
        CertificateReport(classification,kind,true,psd_ok,affine_ok,false,gap_ok,256,
                          minimum_bound,maxres,-Inf,certified_value,normalized_gap,message)
    catch error
        _unverified_certificate("certificate checker error: $(sprint(showerror,error))";kind=kind)
    end
end
