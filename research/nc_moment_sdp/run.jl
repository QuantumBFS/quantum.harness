include(joinpath(@__DIR__, "FiniteAbelianNCMoment.jl"))
using .FiniteAbelianNCMoment
using JSON

function result_record(problem, result; complex_probe=nothing)
    record = Dict{String,Any}(
        "name" => problem.name,
        "order" => problem.order,
        "basis_size" => length(result.basis),
        "real_coordinate_count" => result.coordinate_count,
        "complex_moment_count" => result.free_moment_count,
        "objective" => result.objective,
        "minimum_moment_matrix_eigenvalue" => result.minimum_eigenvalue,
        "minimum_localizer_eigenvalues" => result.localizer_minimum_eigenvalues,
        "coordinate_consistency_residual" => result.coordinate_consistency_residual,
        "hermiticity_residual" => result.hermiticity_residual,
        "equality_residual" => result.equality_residual,
        "localizer_residual" => result.localizer_residual,
        "objective_residual" => result.objective_residual,
        "formulation" => String(result.formulation),
        "moment_cone_sizes" => result.moment_cone_sizes,
        "localizer_cone_sizes" => result.localizer_cone_sizes,
        "block_cubic_proxy" => result.block_cubic_proxy,
        "compile_seconds" => result.compile_seconds,
        "model_build_seconds" => result.model_build_seconds,
        "optimize_seconds" => result.optimize_seconds,
        "solver_solve_seconds" => result.solver_solve_seconds,
        "barrier_iterations" => result.barrier_iterations,
        "jump_variable_count" => result.jump_variable_count,
        "jump_constraint_count" => result.jump_constraint_count,
    )
    if complex_probe !== nothing
        value = evaluate_moment(result, problem.backend, complex_probe)
        record["complex_probe"] = Dict("real" => real(value), "imaginary" => imag(value))
    end
    return record
end

function main(arguments)
    output_path = isempty(arguments) ? nothing : only(arguments)
    instances = [
        (complex_pauli_benchmark(), :dense, (1, 2)),
        (equality_localizer_benchmark(), :dense, nothing),
        (chsh_z2(order=1), :dense, nothing),
        (chsh_z2(order=1), :symmetry, nothing),
        (chsh_z2(order=2), :dense, nothing),
        (chsh_z2(order=2), :symmetry, nothing),
        (chsh_z2(order=3), :dense, nothing),
        (chsh_z2(order=3), :symmetry, nothing),
        (pauli_z2xz2(order=2), :dense, nothing),
        (pauli_z2xz2(order=2), :symmetry, nothing),
        (equality_localizer_benchmark(symmetry=true), :dense, nothing),
        (equality_localizer_benchmark(symmetry=true), :symmetry, nothing),
    ]
    records = Dict{String,Any}[]
    for (problem, formulation, probe) in instances
        result = solve_moment_sdp(problem; formulation=formulation)
        push!(records, result_record(problem, result; complex_probe=probe))
    end
    report = Dict(
        "solver" => "Mosek via JuMP/MosekTools",
        "formulation" => "dense and finite-Abelian block complex Hermitian moment/localizing pencils with strict realification",
        "instances" => records,
    )
    rendered = JSON.json(report, 2)
    if output_path === nothing
        println(rendered)
    else
        open(output_path, "w") do stream
            println(stream, rendered)
        end
        println("wrote $(output_path)")
    end
end

main(ARGS)
