struct SDPResult
    formulation::Symbol
    objective::Float64
    basis::Vector{NCWord}
    sectors::Dict{UInt64,Vector{Int}}
    moments::Dict{NCWord,ComplexF64}
    free_moment_count::Int
    coordinate_count::Int
    moment_matrix::Matrix{ComplexF64}
    minimum_eigenvalue::Float64
    localizer_minimum_eigenvalues::Vector{Float64}
    coordinate_consistency_residual::Float64
    hermiticity_residual::Float64
    equality_residual::Float64
    localizer_residual::Float64
    objective_residual::Float64
    moment_cone_sizes::Vector{Int}
    localizer_cone_sizes::Vector{Vector{Int}}
    block_cubic_proxy::Float64
    compile_seconds::Float64
    model_build_seconds::Float64
    optimize_seconds::Float64
    solver_solve_seconds::Float64
    barrier_iterations::Int
    jump_variable_count::Int
    jump_constraint_count::Int
    termination_status::MOI.TerminationStatusCode
    primal_status::MOI.ResultStatusCode
end

function _strict_mosek_model()
    model = Model(MosekTools.Optimizer)
    set_silent(model)
    for (attribute, value) in (
        ("MSK_DPAR_INTPNT_CO_TOL_PFEAS", 1.0e-9),
        ("MSK_DPAR_INTPNT_CO_TOL_DFEAS", 1.0e-9),
        ("MSK_DPAR_INTPNT_CO_TOL_REL_GAP", 1.0e-9),
        ("MSK_DPAR_INTPNT_CO_TOL_INFEAS", 1.0e-10),
    )
        set_optimizer_attribute(model, attribute, value)
    end
    return model
end

function _jump_parts(form::AffineForm, coordinates)
    real_part = AffExpr(real(form.constant))
    imaginary_part = AffExpr(imag(form.constant))
    for (index, coefficient) in form.terms
        add_to_expression!(real_part, real(coefficient), coordinates[index])
        add_to_expression!(imaginary_part, imag(coefficient), coordinates[index])
    end
    return real_part, imaginary_part
end

function _realified_psd!(model, pencil, coordinates)
    n = length(pencil)
    real_parts = Matrix{AffExpr}(undef, n, n)
    imaginary_parts = Matrix{AffExpr}(undef, n, n)
    for i in 1:n, j in 1:n
        real_parts[i, j], imaginary_parts[i, j] = _jump_parts(pencil[i][j], coordinates)
    end
    block = [real_parts -imaginary_parts; imaginary_parts real_parts]
    @constraint(model, Symmetric(block) in PSDCone())
    return nothing
end

_evaluate(form::AffineForm, coordinates) =
    form.constant + sum(coefficient * coordinates[index] for (index, coefficient) in form.terms; init=0.0 + 0.0im)

function _matrix_values(pencil, coordinates)
    n = length(pencil)
    return ComplexF64[_evaluate(pencil[i][j], coordinates) for i in 1:n, j in 1:n]
end

function _solve_moment_sdp(ir, formulation::Symbol, moment_pencils, localizer_pencils;
                           compile_seconds::Float64=0.0)
    build_start = time_ns()
    model = _strict_mosek_model()
    @variable(model, coordinates[1:ir.coordinate_count])
    for pencil in moment_pencils
        _realified_psd!(model, pencil, coordinates)
    end
    for pencils in localizer_pencils, pencil in pencils
        _realified_psd!(model, pencil, coordinates)
    end
    for equality in ir.equalities
        real_part, imaginary_part = _jump_parts(equality, coordinates)
        @constraint(model, real_part == 0.0)
        @constraint(model, imaginary_part == 0.0)
    end
    objective, imaginary_objective = _jump_parts(ir.objective, coordinates)
    isempty(imaginary_objective.terms) && iszero(imaginary_objective.constant) ||
        error("compiled objective is not strictly real")
    ir.problem.sense == :Max ? @objective(model, Max, objective) : @objective(model, Min, objective)
    model_build_seconds = (time_ns() - build_start) / 1.0e9
    optimize_start = time_ns()
    optimize!(model)
    optimize_seconds = (time_ns() - optimize_start) / 1.0e9

    termination = termination_status(model)
    primal = primal_status(model)
    termination in (MOI.OPTIMAL, MOI.ALMOST_OPTIMAL) ||
        error("Mosek did not solve $(ir.problem.name): $(termination), $(primal)")
    values = value.(coordinates)
    moments = Dict(word => _evaluate(form, values)
                   for (word, form) in zip(ir.moment_words, ir.moment_forms))
    matrix = _matrix_values(ir.moment_matrix, values)
    localizer_matrices = [_matrix_values(localizer.pencil, values) for localizer in ir.localizers]
    localizer_eigenvalues = [eigmin(Hermitian((localizer + localizer') / 2))
                             for localizer in localizer_matrices]
    equality_residual = maximum(abs.(_evaluate.(ir.equalities, Ref(values))); init=0.0)
    hermiticity_residual = norm(matrix - matrix', Inf)
    for localizer in localizer_matrices
        hermiticity_residual = max(hermiticity_residual, norm(localizer - localizer', Inf))
    end
    coordinate_residual = 0.0
    for word in ir.moment_words
        adjoint = star_word(ir.problem.backend, word)
        coordinate_residual = max(coordinate_residual,
            abs(adjoint.phase * moments[adjoint.word] - conj(moments[word])))
    end
    reconstructed_objective = _evaluate(ir.objective, values)
    objective_residual = max(abs(imag(reconstructed_objective)),
                             abs(objective_value(model) - real(reconstructed_objective)))
    localizer_residual = max(0.0, -minimum(localizer_eigenvalues; init=Inf))
    characters = [word_character(word, ir.problem.generator_characters) for word in ir.basis]
    sectors = _character_sectors(ir.basis, ir.problem.generator_characters)
    moment_cone_sizes = length.(moment_pencils)
    localizer_cone_sizes = [length.(pencils) for pencils in localizer_pencils]
    dense_cubic = length(ir.basis)^3 +
                  sum((length(localizer.basis)^3 for localizer in ir.localizers); init=0)
    reduced_cubic = sum(moment_cone_sizes .^ 3; init=0) +
                    sum((sum(sizes .^ 3; init=0) for sizes in localizer_cone_sizes); init=0)
    block_cubic_proxy = dense_cubic / reduced_cubic
    solver_solve_seconds = solve_time(model)
    iteration_count = barrier_iterations(model)
    jump_variable_count = num_variables(model)
    jump_constraint_count = sum((num_constraints(model, function_type, set_type)
        for (function_type, set_type) in list_of_constraint_types(model)); init=0)

    return SDPResult(formulation, objective_value(model), collect(ir.basis), sectors,
                     moments, length(ir.moment_words), ir.coordinate_count, matrix,
                     eigmin(Hermitian((matrix + matrix') / 2)), localizer_eigenvalues,
                     coordinate_residual, hermiticity_residual, equality_residual,
                     localizer_residual, objective_residual, moment_cone_sizes,
                     localizer_cone_sizes, block_cubic_proxy, compile_seconds,
                     model_build_seconds, optimize_seconds, solver_solve_seconds,
                     iteration_count, jump_variable_count, jump_constraint_count,
                     termination, primal)
end

function solve_moment_sdp(ir::CompiledDenseIR; formulation::Symbol=:dense,
                          compile_seconds::Float64=0.0)
    formulation == :dense || throw(ArgumentError("dense IR requires :dense formulation"))
    moment_pencils = [ir.moment_matrix]
    localizer_pencils = [[localizer.pencil] for localizer in ir.localizers]
    return _solve_moment_sdp(ir, formulation, moment_pencils, localizer_pencils;
                             compile_seconds=compile_seconds)
end

function solve_moment_sdp(ir::CompiledSymmetryIR; formulation::Symbol=:symmetry,
                          compile_seconds::Float64=0.0)
    formulation == :symmetry || throw(ArgumentError("symmetry IR requires :symmetry formulation"))
    moment_pencils = [block.pencil for block in ir.moment_blocks]
    localizer_pencils = [[block.pencil for block in localizer.blocks]
                         for localizer in ir.localizers]
    return _solve_moment_sdp(ir, formulation, moment_pencils, localizer_pencils;
                             compile_seconds=compile_seconds)
end

function solve_moment_sdp(ir::CompiledSU2IR; formulation::Symbol=:su2,
                          compile_seconds::Float64=0.0)
    formulation == :su2 || throw(ArgumentError("SU(2) IR requires :su2 formulation"))
    moment_pencils = [block.pencil for block in ir.moment_blocks]
    localizer_pencils = [[block.pencil for block in localizer.blocks]
                         for localizer in ir.localizers]
    return _solve_moment_sdp(ir, formulation, moment_pencils, localizer_pencils;
                             compile_seconds=compile_seconds)
end

function _compile_timed(problem, compiler)
    start = time_ns()
    ir = compiler(problem)
    return ir, (time_ns() - start) / 1.0e9
end

function solve_moment_sdp(problem::NCProblem; formulation::Symbol=:dense)
    if formulation == :dense
        ir, compile_seconds = _compile_timed(problem, compile_dense)
        return solve_moment_sdp(ir; formulation=formulation, compile_seconds=compile_seconds)
    elseif formulation == :symmetry
        ir, compile_seconds = _compile_timed(problem, compile_symmetry)
        return solve_moment_sdp(ir; formulation=formulation, compile_seconds=compile_seconds)
    elseif formulation == :su2
        ir, compile_seconds = _compile_timed(problem, compile_su2)
        return solve_moment_sdp(ir; formulation=formulation, compile_seconds=compile_seconds)
    end
    throw(ArgumentError("formulation must be :dense, :symmetry, or :su2"))
end

function evaluate_moment(result::SDPResult, backend::StarAlgebraBackend, raw_word)
    word = raw_word isa NCWord ? raw_word : NCWord(Tuple(Int.(raw_word)))
    reduced = reduce_word(backend, word)
    return reduced.phase * result.moments[reduced.word]
end
