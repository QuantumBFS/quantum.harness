include(joinpath(@__DIR__, "FiniteAbelianNCMoment.jl"))
using .FiniteAbelianNCMoment
using JSON
using LinearAlgebra

function result_record(problem, dense, reduced)
    block_sizes = sort!(length.(collect(values(reduced.sectors))); rev=true)
    return Dict(
        "name" => problem.name,
        "order" => problem.order,
        "basis_size" => length(dense.basis),
        "dense_free_moment_count" => dense.free_moment_count,
        "reduced_free_moment_count" => reduced.free_moment_count,
        "block_sizes" => block_sizes,
        "dense_objective" => dense.objective,
        "reduced_objective" => reduced.objective,
        "objective_difference" => abs(dense.objective - reduced.objective),
        "dense_minimum_eigenvalue" => dense.minimum_eigenvalue,
        "reduced_minimum_eigenvalue" => reduced.minimum_eigenvalue,
        "maximum_equality_residual" => max(dense.equality_residual, reduced.equality_residual),
        "maximum_objective_residual" => max(dense.objective_residual, reduced.objective_residual),
        "psd_block_cubic_proxy" => reduced.block_cubic_proxy,
    )
end

function main(arguments)
    output_path = isempty(arguments) ? nothing : only(arguments)
    records = Dict{String,Any}[]
    for problem in (chsh_z2(order=1), pauli_z2xz2(order=2))
        dense = solve_moment_sdp(problem; formulation=:dense)
        reduced = solve_moment_sdp(problem; formulation=:reduced)
        push!(records, result_record(problem, dense, reduced))
    end
    report = Dict(
        "solver" => "Mosek via JuMP/MosekTools",
        "formulations" => ["dense original affine PSD hierarchy without symmetry zeros", "group-averaged character-sector affine PSD blocks"],
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
