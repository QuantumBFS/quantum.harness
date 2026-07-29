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
    block_cubic_proxy::Float64
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

function solve_moment_sdp(ir::CompiledDenseIR; formulation::Symbol=:dense)
    formulation == :dense || throw(ArgumentError("compiled next-stage IR supports only :dense formulation"))
    model = _strict_mosek_model()
    @variable(model, coordinates[1:ir.coordinate_count])
    _realified_psd!(model, ir.moment_matrix, coordinates)
    for localizer in ir.localizers
        _realified_psd!(model, localizer.pencil, coordinates)
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
    optimize!(model)

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
    sectors = Dict{UInt64,Vector{Int}}()
    for (index, character) in enumerate(characters)
        push!(get!(sectors, character, Int[]), index)
    end

    return SDPResult(:dense, objective_value(model), collect(ir.basis), sectors,
                     moments, length(ir.moment_words), ir.coordinate_count, matrix,
                     eigmin(Hermitian((matrix + matrix') / 2)), localizer_eigenvalues,
                     coordinate_residual, hermiticity_residual, equality_residual,
                     localizer_residual, objective_residual, 1.0, termination, primal)
end

solve_moment_sdp(problem::NCProblem; formulation::Symbol=:dense) =
    solve_moment_sdp(compile_dense(problem); formulation=formulation)

function evaluate_moment(result::SDPResult, backend::StarAlgebraBackend, raw_word)
    word = raw_word isa NCWord ? raw_word : NCWord(Tuple(Int.(raw_word)))
    reduced = reduce_word(backend, word)
    return reduced.phase * result.moments[reduced.word]
end
