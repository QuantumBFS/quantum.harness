#!/usr/bin/env julia

using TOML

const ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(ROOT, "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

function convergence_cli(args=ARGS)
    length(args) == 1 ||
        error("usage: run_convergence.jl <output_dir>")
    output = abspath(args[1])
    mkpath(output)

    axes_path = joinpath(output, "convergence_plan.csv")
    open(axes_path, "w") do io
        println(io, "axis,quick,validation,production,status")
        rows = (
            ("dt", "pi/12", "pi/60", "from validation plateau"),
            ("compression", "1e-3", "1e-7", "from validation plateau"),
            ("eigensolver", "1e-8", "1e-10", "no looser than 1e-10"),
            ("tau_max", "256 steps", "1024 steps", "tail diagnostics pass"),
            ("delta_omega", "FFT grid", "FFT/direct cross-check", "from tau_max"),
            ("omega_max", "grid-limited", "20", "integral plateau"),
            ("nmax", "8", "20", "delta-weight plateau"),
        )
        for (axis, quick, validation, production) in rows
            println(io, join((axis, quick, validation, production, "pending"), ","))
        end
    end

    estimates = Dict{String, Any}()
    for (name, χ, M, K, points) in (
        ("quick", 16, 12, 256, 3),
        ("validation", 96, 120, 1024, 6),
        ("production", 235, 120, 4096, 191),
    )
        estimate = estimate_resources(
            bond_dimension=χ,
            period_steps=M,
            correlation_lag_steps=K,
            frequency_points=points,
        )
        estimates[name] = Dict(
            "bond_dimension" => χ,
            "augmented_dimension" => estimate.augmented_dimension,
            "dense_floquet_bytes" => estimate.dense_floquet_bytes,
            "estimated_peak_bytes" => estimate.estimated_peak_bytes,
            "estimated_wall_seconds" => estimate.estimated_wall_seconds,
            "execution" => String(estimate.execution),
        )
    end
    resource_path = joinpath(output, "resource_estimates.toml")
    open(resource_path, "w") do io
        TOML.print(io, estimates)
    end
    println("convergence plan: $(axes_path)")
    println("resource estimates: $(resource_path)")
    flush(stdout)
    return (; axes_path, resource_path)
end

if abspath(PROGRAM_FILE) == @__FILE__
    convergence_cli()
end
