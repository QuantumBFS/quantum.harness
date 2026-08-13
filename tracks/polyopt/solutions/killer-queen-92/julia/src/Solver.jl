struct MomentOrbit
    representatives::Vector{PureStateMonomial}
    real_index::Dict{PureStateMonomial,Int}
    imag_index::Dict{PureStateMonomial,Int}
    orientation::Dict{PureStateMonomial,Int}
end

const ParametricRow = Dict{Int,ParamCoeff}

struct ParametricScalarUpdate
    constraint::Any
    coefficients::ParametricRow
end

struct ParametricPSDUpdate
    constraint::Any
    by_variable::Vector{Vector{Tuple{Int,ParamCoeff}}}
end

mutable struct SolverWorkspace
    model::JuMP.Model
    solver_name::String
    orbit::MomentOrbit
    y::Vector{JuMP.VariableRef}
    equality_constraints::Vector{Any}
    equation_rows::Vector{Tuple{ParametricRow,Float64}}
    scalar_updates::Vector{ParametricScalarUpdate}
    psd_constraints::Vector{Any}
    psd_updates::Vector{ParametricPSDUpdate}
    allblocks::Vector{MatrixBlock}
    block_real_rows::Vector{Matrix{ParametricRow}}
    block_imag_rows::Vector{Matrix{ParametricRow}}
    params::ModelParams
    solve_count::Int
    parameter_update_count::Int
end

function _moment_orbits(keys::Vector{PureStateMonomial})
    allkeys = Set(keys)
    union!(allkeys,adjoint.(keys))
    representatives = PureStateMonomial[]
    real_index = Dict{PureStateMonomial,Int}()
    imag_index = Dict{PureStateMonomial,Int}()
    orientation = Dict{PureStateMonomial,Int}()
    cursor = 0
    for key in sort!(collect(allkeys))
        star = adjoint(key)
        rep = isless(star,key) ? star : key
        haskey(real_index,rep) && continue
        push!(representatives,rep)
        cursor += 1
        real_index[rep] = cursor
        if star != key
            cursor += 1
            imag_index[rep] = cursor
        end
    end
    for key in allkeys
        star = adjoint(key)
        rep = isless(star,key) ? star : key
        orientation[key] = key == rep ? 1 : -1
    end
    MomentOrbit(representatives,real_index,imag_index,orientation)
end

_nvariables(orbit::MomentOrbit) = maximum([values(orbit.real_index)...;values(orbit.imag_index)...];init=0)

_real_part(x::ParamCoeff) = ParamCoeff(aq(real(x.constant)),aq(real(x.t)),aq(real(x.U)),
                                       aq(real(x.mu)),aq(real(x.gamma)))
_imag_part(x::ParamCoeff) = ParamCoeff(aq(imag(x.constant)),aq(imag(x.t)),aq(imag(x.U)),
                                       aq(imag(x.mu)),aq(imag(x.gamma)))
_is_parametric(x::ParamCoeff) = !all(iszero,(x.t,x.U,x.mu,x.gamma))

function _add_coefficient!(row::ParametricRow,index::Int,value::ParamCoeff)
    iszero(value) && return row
    row[index] = get(row,index,ParamCoeff())+value
    iszero(row[index]) && delete!(row,index)
    row
end

"""Real/imaginary moment rows before evaluating any run-time parameter."""
function _expr_parametric_coefficients(expr::MomentExpr,orbit::MomentOrbit)
    realcoeff = ParametricRow()
    imagcoeff = ParametricRow()
    for (key,paramcoefficient) in expr
        star = adjoint(key)
        rep = isless(star,key) ? star : key
        sign = orbit.orientation[key]
        ri = orbit.real_index[rep]
        zr,zi = _real_part(paramcoefficient),_imag_part(paramcoefficient)
        _add_coefficient!(realcoeff,ri,zr)
        _add_coefficient!(imagcoeff,ri,zi)
        if haskey(orbit.imag_index,rep)
            ii = orbit.imag_index[rep]
            _add_coefficient!(realcoeff,ii,-zi*Q23(sign))
            _add_coefficient!(imagcoeff,ii,zr*Q23(sign))
        end
    end
    realcoeff,imagcoeff
end

function _evaluate_coefficient(coefficient::ParamCoeff,params::ModelParams)
    value = evaluate(coefficient,params)
    iszero(imag(value)) || throw(ArgumentError("real conic row acquired an imaginary coefficient"))
    Float64(real(value))
end

function _evaluate_row(row::ParametricRow,params::ModelParams;drop_zeros::Bool=true)
    result = Dict{Int,Float64}()
    for (index,coefficient) in row
        value = _evaluate_coefficient(coefficient,params)
        (!drop_zeros || !iszero(value)) && (result[index]=value)
    end
    result
end

function _expr_coefficients(expr::MomentExpr,params::ModelParams,orbit::MomentOrbit)
    realrow,imagrow = _expr_parametric_coefficients(expr,orbit)
    _evaluate_row(realrow,params),_evaluate_row(imagrow,params)
end

function _affexpr(coefficients::Dict{Int,Float64},variables)
    expression = JuMP.AffExpr(0.0)
    for (index,coefficient) in coefficients
        JuMP.add_to_expression!(expression,coefficient,variables[index])
    end
    expression
end

_parametric_affexpr(row::ParametricRow,params::ModelParams,variables) =
    _affexpr(_evaluate_row(row,params),variables)

_negate_row(row::ParametricRow) = ParametricRow(index=>-coefficient for (index,coefficient) in row)

function _psd_updates(rows::Vector{ParametricRow},nvariables::Int)
    by_variable = [Tuple{Int,ParamCoeff}[] for _ in 1:nvariables]
    for (row_index,row) in enumerate(rows), (variable_index,coefficient) in row
        _is_parametric(coefficient) || continue
        push!(by_variable[variable_index],(row_index,coefficient))
    end
    by_variable
end

function _make_optimizer(solver::Symbol,quiet::Bool)
    if solver == :clarabel
        model = JuMP.Model(Clarabel.Optimizer)
        JuMP.set_optimizer_attribute(model,"verbose",!quiet)
        direct_setting = lowercase(get(ENV,"ISSUE92_CLARABEL_DIRECT_SOLVER",""))
        # Loading Pardiso activates Clarabel's `:auto` MKL preference.  Keep
        # the historical QDLDL backend unless a run explicitly opts in.
        direct_solver = isempty(direct_setting) ? :qdldl : Symbol(direct_setting)
        direct_solver in (:auto,:qdldl,:cholmod,:mkl) || throw(ArgumentError(
            "ISSUE92_CLARABEL_DIRECT_SOLVER must be auto, qdldl, cholmod, or mkl",
        ))
        if direct_solver == :mkl
            Pardiso.mkl_is_available() ||
                throw(ArgumentError("MKL Pardiso is not available"))
        end
        if direct_solver != :auto
            JuMP.set_optimizer_attribute(model,"direct_solve_method",direct_solver)
        end
        max_threads = parse(Int,get(ENV,"ISSUE92_CLARABEL_MAX_THREADS",string(Threads.nthreads())))
        max_threads > 0 || throw(ArgumentError("ISSUE92_CLARABEL_MAX_THREADS must be positive"))
        JuMP.set_optimizer_attribute(model,"max_threads",max_threads)
        solver_suffix = isempty(direct_setting) ? "" : ";$(direct_solver),$(max_threads)t"
        profile = lowercase(get(ENV,"ISSUE92_CLARABEL_PROFILE","production-default"))
        if profile in ("presentation-fast","deadline-balanced")
            default_iterations = profile == "presentation-fast" ? "60" : "100"
            default_time_limit = profile == "presentation-fast" ? "600" : "900"
            JuMP.set_optimizer_attribute(
                model,"max_iter",parse(Int,get(ENV,"ISSUE92_CLARABEL_MAX_ITER",default_iterations)),
            )
            JuMP.set_optimizer_attribute(
                model,"time_limit",parse(Float64,get(ENV,"ISSUE92_CLARABEL_TIME_LIMIT",default_time_limit)),
            )
            tolerance = profile == "presentation-fast" ? 1e-5 : 2e-7
            feasibility_tolerance = profile == "presentation-fast" ? 1e-6 : 2e-7
            JuMP.set_optimizer_attribute(model,"tol_gap_abs",tolerance)
            JuMP.set_optimizer_attribute(model,"tol_gap_rel",tolerance)
            JuMP.set_optimizer_attribute(model,"tol_feas",feasibility_tolerance)
            JuMP.set_optimizer_attribute(model,"tol_infeas_abs",feasibility_tolerance)
            JuMP.set_optimizer_attribute(model,"tol_infeas_rel",feasibility_tolerance)
            return model,"Clarabel[$profile$solver_suffix]"
        elseif profile != "production-default"
            throw(ArgumentError(
                "ISSUE92_CLARABEL_PROFILE must be production-default, presentation-fast, or deadline-balanced",
            ))
        end
        return model,isempty(direct_setting) ? "Clarabel" : "Clarabel[$(direct_solver),$(max_threads)t]"
    elseif solver == :mosek
        try
            @eval import MosekTools
        catch error
            throw(ArgumentError("MosekTools is not installed in this environment: $(sprint(showerror,error))"))
        end
        model = JuMP.Model(MosekTools.Optimizer)
        quiet && JuMP.set_silent(model)
        return model,"Mosek"
    end
    throw(ArgumentError("solver must be :clarabel or :mosek"))
end

function _build_model(template::HierarchyTemplate,params::ModelParams;
                      solver::Symbol=:clarabel,quiet::Bool=true)
    model,solver_name = _make_optimizer(solver,quiet)
    orbit = _moment_orbits(template.moment_keys)
    JuMP.@variable(model,y[1:_nvariables(orbit)])
    equality_constraints = Any[]
    equation_rows = Tuple{ParametricRow,Float64}[]
    scalar_updates = ParametricScalarUpdate[]
    identity = PureStateMonomial()
    identity_rep = isless(adjoint(identity),identity) ? adjoint(identity) : identity
    normalization_row = ParametricRow(orbit.real_index[identity_rep]=>ParamCoeff(1))
    push!(equality_constraints,JuMP.@constraint(model,_parametric_affexpr(normalization_row,params,y)==1.0))
    push!(equation_rows,(normalization_row,1.0))
    for expression in template.stationarity
        realrow,imagrow = _expr_parametric_coefficients(expression,orbit)
        for row in (realrow,imagrow)
            isempty(row) && continue
            constraint = JuMP.@constraint(model,_parametric_affexpr(row,params,y)==0.0)
            push!(equality_constraints,constraint)
            push!(equation_rows,(row,0.0))
            any(_is_parametric,values(row)) &&
                push!(scalar_updates,ParametricScalarUpdate(constraint,row))
        end
    end
    psd_constraints = Any[]
    psd_updates = ParametricPSDUpdate[]
    block_real_rows = Matrix{ParametricRow}[]
    block_imag_rows = Matrix{ParametricRow}[]
    allblocks = [template.moment_blocks;template.gap_blocks]
    for block in allblocks
        n = length(block.basis)
        realrows = Matrix{ParametricRow}(undef,n,n)
        imagrows = Matrix{ParametricRow}(undef,n,n)
        realmatrix = Matrix{JuMP.AffExpr}(undef,n,n)
        imagmatrix = Matrix{JuMP.AffExpr}(undef,n,n)
        for i in 1:n,j in 1:n
            realrows[i,j],imagrows[i,j] = _expr_parametric_coefficients(block.entries[i,j],orbit)
            realmatrix[i,j] = _parametric_affexpr(realrows[i,j],params,y)
            imagmatrix[i,j] = _parametric_affexpr(imagrows[i,j],params,y)
        end
        push!(block_real_rows,realrows)
        push!(block_imag_rows,imagrows)
        embedding = [realmatrix -imagmatrix; imagmatrix realmatrix]
        constraint = JuMP.@constraint(model,LinearAlgebra.Symmetric(embedding) in JuMP.PSDCone())
        push!(psd_constraints,constraint)

        parametric_embedding = Matrix{ParametricRow}(undef,2n,2n)
        for i in 1:n,j in 1:n
            parametric_embedding[i,j] = realrows[i,j]
            parametric_embedding[i,n+j] = _negate_row(imagrows[i,j])
            parametric_embedding[n+i,j] = imagrows[i,j]
            parametric_embedding[n+i,n+j] = realrows[i,j]
        end
        triangle_rows = ParametricRow[parametric_embedding[i,j] for j in 1:2n for i in 1:j]
        updates = _psd_updates(triangle_rows,length(y))
        any(update->!isempty(update),updates) &&
            push!(psd_updates,ParametricPSDUpdate(constraint,updates))
    end
    JuMP.@objective(model,Min,0.0)
    @assert length(y) == template.metadata["real_scalar_variable_count"]
    @assert length(equality_constraints) == template.metadata["equality_count"]
    @assert length(psd_constraints) ==
            template.metadata["moment_psd_block_count"]+template.metadata["gap_psd_block_count"]
    SolverWorkspace(model,solver_name,orbit,y,equality_constraints,equation_rows,scalar_updates,
                    psd_constraints,psd_updates,allblocks,block_real_rows,block_imag_rows,params,0,0)
end

function _update_parameters!(workspace::SolverWorkspace,params::ModelParams)
    workspace.params == params && return workspace
    for update in workspace.scalar_updates
        for (variable_index,coefficient) in update.coefficients
            _is_parametric(coefficient) || continue
            JuMP.set_normalized_coefficient(
                update.constraint,workspace.y[variable_index],
                _evaluate_coefficient(coefficient,params),
            )
        end
    end
    for update in workspace.psd_updates
        for (variable_index,entries) in enumerate(update.by_variable)
            isempty(entries) && continue
            coefficients = Tuple{Int64,Float64}[
                (Int64(row_index),_evaluate_coefficient(coefficient,params))
                for (row_index,coefficient) in entries
            ]
            JuMP.set_normalized_coefficient(
                update.constraint,workspace.y[variable_index],coefficients,
            )
        end
    end
    # Clarabel accepts MOI.MultirowChange after a solve but can retain stale
    # internal cone data.  Reset only the attached optimizer so the next
    # optimize! copies the already-updated JuMP cache.  The symbolic variables,
    # constraints, coefficient maps, and objective workspace remain live.
    MathOptInterface.Utilities.reset_optimizer(workspace.model)
    workspace.params = params
    workspace.parameter_update_count += 1
    workspace
end

function _set_objective!(workspace::SolverWorkspace,template::HierarchyTemplate,
                         params::ModelParams,objective,sense::Symbol)
    if objective === nothing
        JuMP.set_objective_sense(workspace.model,MathOptInterface.MIN_SENSE)
        JuMP.set_objective_function(workspace.model,JuMP.AffExpr(0.0))
        return workspace
    end
    observable = Symbol(objective)
    haskey(template.objectives,observable) || throw(ArgumentError("unknown observable $observable"))
    realrow,imagrow = _expr_coefficients(template.objectives[observable],params,workspace.orbit)
    isempty(imagrow) || maximum(abs,values(imagrow)) <= 1e-12 ||
        throw(ArgumentError("observable $observable is not Hermitian after reduction"))
    sense == :min ? JuMP.set_objective_sense(workspace.model,MathOptInterface.MIN_SENSE) :
    sense == :max ? JuMP.set_objective_sense(workspace.model,MathOptInterface.MAX_SENSE) :
    throw(ArgumentError("sense must be :min or :max"))
    JuMP.set_objective_function(workspace.model,_affexpr(realrow,workspace.y))
    workspace
end

function _workspace!(template::HierarchyTemplate,params::ModelParams;
                     objective=nothing,sense::Symbol=:min,solver::Symbol=:clarabel,quiet::Bool=true)
    key = (solver,quiet)
    workspace = get(template.solver_cache,key,nothing)
    if workspace === nothing
        workspace = _build_model(template,params;solver=solver,quiet=quiet)
        template.solver_cache[key] = workspace
    else
        workspace isa SolverWorkspace || error("invalid cached solver workspace")
        _update_parameters!(workspace,params)
    end
    _set_objective!(workspace,template,params,objective,sense)
end

function _primal_diagnostics(build,template,params)
    values = JuMP.value.(build.y)
    residual = 0.0
    for (row,rhs) in build.equation_rows
        evaluated = _evaluate_row(row,params)
        residual = max(residual,abs(sum(coefficient*values[index] for (index,coefficient) in evaluated;init=0.0)-rhs))
    end
    minimum_eigenvalue = Inf
    for (block,block_real_rows,block_imag_rows) in
        zip(build.allblocks,build.block_real_rows,build.block_imag_rows)
        n = length(block.basis)
        matrix = zeros(ComplexF64,n,n)
        for i in 1:n,j in 1:n
            realrow = _evaluate_row(block_real_rows[i,j],params)
            imagrow = _evaluate_row(block_imag_rows[i,j],params)
            re = sum(coefficient*values[index] for (index,coefficient) in realrow;init=0.0)
            im = sum(coefficient*values[index] for (index,coefficient) in imagrow;init=0.0)
            matrix[i,j] = complex(re,im)
        end
        minimum_eigenvalue = min(minimum_eigenvalue,minimum(eigvals(Hermitian((matrix+matrix')/2))))
    end
    residual,minimum_eigenvalue,values
end

function _extract_dual(build)
    dualdata = Dict{String,Any}()
    try
        dualdata["equality_multipliers"] = Float64[JuMP.dual(c) for c in build.equality_constraints]
        dualdata["psd_matrices"] = [Matrix{Float64}(JuMP.dual(c)) for c in build.psd_constraints]
        dualdata["available"] = true
    catch error
        dualdata["available"] = false
        dualdata["error"] = sprint(showerror,error)
    end
    dualdata
end

function _dual_diagnostics(build,template,params,objective,sense,primal_objective,dualdata)
    get(dualdata,"available",false) || return Inf,-Inf
    try
        multipliers = dualdata["equality_multipliers"]
        matrices = dualdata["psd_matrices"]
        length(multipliers)==length(build.equation_rows) ||
            throw(ArgumentError("dual equality count mismatch"))
        length(matrices)==length(build.allblocks) ||
            throw(ArgumentError("dual PSD block count mismatch"))

        dual_stationarity = zeros(Float64,length(build.y))
        rhs_dual = 0.0
        for ((row,rhs),multiplier) in zip(build.equation_rows,multipliers)
            for (index,coefficient) in _evaluate_row(row,params)
                dual_stationarity[index] += multiplier*coefficient
            end
            rhs_dual += rhs*multiplier
        end

        minimum_dual_eigenvalue = Inf
        for (block,block_real_rows,block_imag_rows,zraw) in
            zip(build.allblocks,build.block_real_rows,build.block_imag_rows,matrices)
            n = length(block.basis)
            size(zraw)==(2n,2n) || throw(ArgumentError("dual PSD matrix shape mismatch"))
            z = (zraw+transpose(zraw))/2
            minimum_dual_eigenvalue = min(
                minimum_dual_eigenvalue,
                minimum(eigvals(LinearAlgebra.Symmetric(z))),
            )
            # MOI uses the trace inner product for the triangular PSD cone.
            # Summing the full symmetric embedding supplies the required
            # factor of two on every off-diagonal coefficient.
            for i in 1:n,j in 1:n
                realrow = _evaluate_row(block_real_rows[i,j],params)
                imagrow = _evaluate_row(block_imag_rows[i,j],params)
                realweight = z[i,j]+z[n+i,n+j]
                imagweight = -z[i,n+j]+z[n+i,j]
                for (index,coefficient) in realrow
                    dual_stationarity[index] += realweight*coefficient
                end
                for (index,coefficient) in imagrow
                    dual_stationarity[index] += imagweight*coefficient
                end
            end
        end

        objective_row = Dict{Int,Float64}()
        if objective !== nothing
            objective_row,imaginary = _expr_coefficients(
                template.objectives[Symbol(objective)],params,build.orbit,
            )
            isempty(imaginary) || maximum(abs,values(imaginary)) <= 1e-12 ||
                throw(ArgumentError("observable objective has a nonzero imaginary row"))
        end
        objective_sense = sense == :min ? 1.0 : sense == :max ? -1.0 :
            throw(ArgumentError("sense must be :min or :max"))
        stationarity_residual = maximum(
            abs(get(objective_row,index,0.0)-objective_sense*dual_stationarity[index])
            for index in eachindex(dual_stationarity);
            init=0.0,
        )
        dual_objective = objective_sense*rhs_dual
        jump_dual_objective = JuMP.dual_objective_value(build.model)
        objective_scale = 1+max(abs(primal_objective),abs(dual_objective))
        gap_residual = abs(primal_objective-dual_objective)/objective_scale
        objective_residual = abs(jump_dual_objective-dual_objective)/objective_scale
        cone_residual = max(0.0,-minimum_dual_eigenvalue)
        residual = max(stationarity_residual,gap_residual,objective_residual,cone_residual)
        dualdata["stationarity_residual"] = stationarity_residual
        dualdata["minimum_psd_eigenvalue"] = minimum_dual_eigenvalue
        dualdata["dual_objective"] = dual_objective
        dualdata["jump_dual_objective"] = jump_dual_objective
        dualdata["normalized_primal_dual_gap"] = gap_residual
        residual,minimum_dual_eigenvalue
    catch error
        dualdata["diagnostic_error"] = sprint(showerror,error)
        Inf,-Inf
    end
end

function _solve(template::HierarchyTemplate,params::ModelParams;
                objective=nothing,sense=:min,solver=:clarabel,quiet=true)
    started = time()
    progress = get(ENV,"ISSUE92_SOLVE_PROGRESS","0") == "1"
    report_progress(message) = if progress
        println("solver progress: $message")
        flush(stdout)
    end
    try
        phase_started = time()
        build = _workspace!(template,params;objective=objective,sense=sense,solver=solver,quiet=quiet)
        report_progress("workspace ready in $(round(time()-phase_started;digits=2))s")
        phase_started = time()
        JuMP.optimize!(build.model)
        build.solve_count += 1
        status = JuMP.termination_status(build.model)
        optimize_seconds = time()-phase_started
        report_progress("optimizer returned $(status) in $(round(optimize_seconds;digits=2))s")
        elapsed = time()-started
        raw = string(status)
        if status in (MathOptInterface.OPTIMAL,MathOptInterface.ALMOST_OPTIMAL)
            phase_started = time()
            residual,mineig,values = _primal_diagnostics(build,template,params)
            primal_diagnostic_seconds = time()-phase_started
            report_progress("primal diagnostics finished in $(round(primal_diagnostic_seconds;digits=2))s")
            objective_value = objective === nothing ? 0.0 : JuMP.objective_value(build.model)
            phase_started = time()
            dualdata = _extract_dual(build)
            dualresidual,dual_mineig = _dual_diagnostics(
                build,template,params,objective,sense,objective_value,dualdata,
            )
            dual_diagnostic_seconds = time()-phase_started
            dualdata["phase_seconds"] = Dict(
                "optimizer"=>optimize_seconds,
                "primal_diagnostics"=>primal_diagnostic_seconds,
                "dual_extraction_and_diagnostics"=>dual_diagnostic_seconds,
            )
            report_progress("dual diagnostics finished in $(round(dual_diagnostic_seconds;digits=2))s")
            primal_acceptable = residual <= 1e-6 && mineig >= -1e-6
            dual_acceptable = dualresidual <= 1e-6 && dual_mineig >= -1e-6
            acceptable = primal_acceptable && (objective === nothing || dual_acceptable)
            classification = acceptable ? :FEASIBLE : :UNKNOWN
            reported_objective = objective === nothing ? nothing : objective_value
            certificate_class = acceptable ?
                (objective === nothing ? :PRIMAL_CHECKED : :PRIMAL_DUAL_CHECKED) :
                :FAILED_RESIDUAL_CHECK
            message = acceptable ?
                (objective === nothing ?
                    "primal residual and PSD checks passed" :
                    "primal/dual residual, PSD, and objective-gap checks passed") :
                "solver optimum failed an independent primal or dual check"
            primaldata = Dict{String,Any}("moments"=>values,"params"=>params)
            if objective !== nothing
                primaldata["objective"] = Symbol(objective)
                primaldata["sense"] = Symbol(sense)
            end
            return SolveRecord(classification,raw,build.solver_name,elapsed,reported_objective,
                               residual,dualresidual,mineig,certificate_class,message,
                               primaldata,dualdata)
        elseif status in (MathOptInterface.INFEASIBLE,MathOptInterface.ALMOST_INFEASIBLE,
                          MathOptInterface.INFEASIBLE_OR_UNBOUNDED)
            dualdata = _extract_dual(build)
            candidate = SolveRecord(:UNKNOWN,raw,build.solver_name,elapsed,nothing,NaN,NaN,NaN,
                                    :FLOATING_CANDIDATE,"floating infeasibility requires independent certificate verification",
                                    Dict("params"=>params),dualdata)
            report = verify_certificate(template,candidate)
            dualdata["certificate_report"] = _certificate_report_dict(report)
            if report.classification == :VERIFIED_EXCLUSION
                return SolveRecord(:EXCLUDED,raw,build.solver_name,elapsed,nothing,NaN,
                                   report.max_affine_residual,report.min_eigenvalue_lower,:VERIFIED_EXACT_PROJECTED,
                                   report.message,Dict("params"=>params),dualdata)
            end
            return candidate
        end
        SolveRecord(:UNKNOWN,raw,build.solver_name,elapsed,nothing,NaN,NaN,NaN,:NO_CERTIFICATE,
                    "solver did not return a classifiable result",Dict("params"=>params),Dict{String,Any}())
    catch error
        SolveRecord(:UNKNOWN,"ERROR",String(solver),time()-started,nothing,NaN,NaN,NaN,:NO_CERTIFICATE,
                    sprint(showerror,error),Dict("params"=>params),Dict{String,Any}())
    end
end

solve_feasibility(template::HierarchyTemplate,params::ModelParams;kwargs...) =
    _solve(template,params;objective=nothing,kwargs...)

function solve_observable(template::HierarchyTemplate,params::ModelParams,observable,sense;
                          exact_certificate::Bool=false,kwargs...)
    record = _solve(
        template,params;objective=Symbol(observable),sense=Symbol(lowercase(String(sense))),kwargs...,
    )
    exact_certificate || return record
    report = verify_certificate(template,record)
    record.dual["certificate_report"] = _certificate_report_dict(report)
    certificate_class = report.classification in (:VERIFIED_LOWER_BOUND,:VERIFIED_UPPER_BOUND) ?
        :VERIFIED_EXACT_PROJECTED_BOUND : :EXACT_PROJECTION_FAILED
    SolveRecord(
        record.classification,record.raw_status,record.solver,record.runtime_seconds,
        record.objective,record.primal_residual,record.dual_residual,record.min_psd_eigenvalue,
        certificate_class,report.message,record.primal,record.dual,
    )
end

function bisect_gap(template::HierarchyTemplate,params::ModelParams;tolerance=0.005,solver=:clarabel,quiet=true,
                    checkpoint=(bracket,record)->nothing,
                    resume_records::Vector{SolveRecord}=SolveRecord[],trial_solver=nothing)
    unit = Float64(params.U)
    target_width = tolerance*unit
    records = SolveRecord[]
    resume_cursor = Ref(1)
    solve_trial = trial_solver === nothing ?
        trial_params->solve_feasibility(template,trial_params;solver=solver,quiet=quiet) : trial_solver
    function next_record(gamma,bracket)
        trial_params = ModelParams(params.t,params.U,params.mu,_exact_parameter(gamma))
        if resume_cursor[] <= length(resume_records)
            record = resume_records[resume_cursor[]]
            recorded_params = get(record.primal,"params",nothing)
            recorded_params == trial_params || throw(ArgumentError(
                "resumed gap history is not a deterministic prefix: expected gamma=$(trial_params.gamma)",
            ))
            resume_cursor[] += 1
        else
            record = solve_trial(trial_params)
            get(record.primal,"params",nothing) == trial_params || throw(ArgumentError(
                "gap trial solver did not preserve its exact ModelParams",
            ))
            checkpoint(bracket,record)
        end
        push!(records,record)
        record
    end
    lower = 0.0
    upper = 1.0*unit
    atzero = next_record(0.0,(lower,upper))
    atzero.classification == :FEASIBLE ||
        return GapBracket(lower,upper,target_width,records,false,"gamma=0 was not verified feasible")
    while true
        trial = next_record(upper,(lower,upper))
        if trial.classification == :EXCLUDED
            break
        elseif trial.classification == :FEASIBLE
            lower = upper
            upper *= 2
            upper <= 8unit || return GapBracket(lower,8unit,target_width,records,false,"no verified exclusion through 8U")
        else
            return GapBracket(lower,upper,target_width,records,false,"UNKNOWN at upper-bracket trial; endpoints were not moved")
        end
    end
    while upper-lower > target_width
        midpoint = (lower+upper)/2
        trial = next_record(midpoint,(lower,upper))
        if trial.classification == :FEASIBLE
            lower = midpoint
        elseif trial.classification == :EXCLUDED
            upper = midpoint
        else
            return GapBracket(lower,upper,target_width,records,false,"UNKNOWN during bisection; endpoints were not moved")
        end
    end
    GapBracket(lower,upper,target_width,records,true,"verified bracket reached requested width")
end
