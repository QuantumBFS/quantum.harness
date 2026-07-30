#!/usr/bin/env julia

using JSON
using LinearAlgebra
using Plots
using Statistics

const ENERGY_TOLERANCE = 1.0e-8
const CORRELATION_TOLERANCE = 1.0e-6

csv_value(value) = isnothing(value) ? "" : string(value)

function write_table(path, columns, rows)
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in rows
            println(io, join((csv_value(get(row, column, nothing)) for column in columns), ","))
        end
    end
end

function crossing(rows_L, rows_2L)
    left = Dict(Float64(row["Gamma"]) => Float64(row["correlation_ratio"]) for row in rows_L)
    right = Dict(Float64(row["Gamma"]) => Float64(row["correlation_ratio"]) for row in rows_2L)
    gammas = sort!(collect(intersect(keys(left), keys(right))))
    length(gammas) >= 2 || return nothing
    differences = [left[gamma] - right[gamma] for gamma in gammas]
    for i in 1:(length(gammas) - 1)
        differences[i] == 0 && return gammas[i]
        differences[i] * differences[i + 1] > 0 && continue
        x1, x2 = gammas[i], gammas[i + 1]
        y1, y2 = differences[i], differences[i + 1]
        return x1 - y1 * (x2 - x1) / (y2 - y1)
    end
    return nothing
end

function fit_dynamic_exponent(rows)
    selected = filter(row -> row["model"] == "nn" && !isnothing(row["gap"]), rows)
    isempty(selected) && return nothing
    by_length = Dict{Int, Dict{String, Any}}()
    for row in selected
        L = Int(row["L"])
        gamma_distance = abs(Float64(row["Gamma"]) - 1)
        previous_distance = haskey(by_length, L) ?
            abs(Float64(by_length[L]["Gamma"]) - 1) : Inf
        if !haskey(by_length, L) || gamma_distance < previous_distance ||
                (gamma_distance == previous_distance && Int(row["chi"]) > Int(by_length[L]["chi"]))
            by_length[L] = row
        end
    end
    length(by_length) >= 3 || return nothing
    lengths = sort!(collect(keys(by_length)))
    gaps = [Float64(by_length[L]["gap"]) for L in lengths]
    all(>(0), gaps) || return nothing
    design = hcat(ones(length(lengths)), log.(Float64.(lengths)))
    coefficients = design \ log.(gaps)
    predicted = design * coefficients
    fit = Dict(
        "z" => -coefficients[2],
        "intercept" => coefficients[1],
        "lengths" => lengths,
        "gaps" => gaps,
        "log_rmse" => sqrt(mean(abs2, log.(gaps) - predicted)),
    )
    if length(lengths) >= 4
        reduced_design = design[2:end, :]
        reduced_coefficients = reduced_design \ log.(gaps[2:end])
        fit["without_smallest"] = Dict(
            "z" => -reduced_coefficients[2],
            "lengths" => lengths[2:end],
        )
    end
    return fit
end

function validation_audit(rows)
    audits = Dict{String, Any}[]
    for row in rows
        isnothing(row["ed_energy_relative_error"]) && continue
        energy_error = Float64(row["ed_energy_relative_error"])
        correlation_error = Float64(row["correlation_ratio_absolute_error"])
        push!(audits, Dict(
            "model" => row["model"], "sigma" => row["sigma"], "L" => row["L"],
            "Gamma" => row["Gamma"], "chi" => row["chi"], "poles" => row["poles"],
            "energy_relative_error" => energy_error,
            "correlation_absolute_error" => correlation_error,
            "passes_ed_gate" => energy_error < ENERGY_TOLERANCE &&
                correlation_error < CORRELATION_TOLERANCE,
        ))
    end

    long_range = filter(row -> row["model"] == "long_range", audits)
    max_pole_rows = Dict{Tuple, Dict{String, Any}}()
    for row in long_range
        key = (row["sigma"], row["L"], row["Gamma"], row["chi"])
        if !haskey(max_pole_rows, key) || Int(row["poles"]) > Int(max_pole_rows[key]["poles"])
            max_pole_rows[key] = row
        end
    end
    max_pole_passes = !isempty(max_pole_rows) &&
        all(row["passes_ed_gate"] for row in values(max_pole_rows))

    return Dict(
        "energy_relative_tolerance" => ENERGY_TOLERANCE,
        "correlation_absolute_tolerance" => CORRELATION_TOLERANCE,
        "rows" => audits,
        "largest_pole_rows_pass" => max_pole_passes,
    )
end

function pole_drift_rows(rows)
    drift = Dict{String, Any}[]
    for row in rows
        row["model"] == "long_range" || continue
        mpo_error = row["mpo_error"]
        push!(drift, Dict(
            "sigma" => row["sigma"], "L" => row["L"], "Gamma" => row["Gamma"],
            "chi" => row["chi"], "poles" => row["poles"],
            "mpo_max_relative" => mpo_error["max_relative"],
            "energy_relative_error" => row["ed_energy_relative_error"],
            "correlation_absolute_error" => row["correlation_ratio_absolute_error"],
        ))
    end
    sort!(drift; by = row -> (
        Float64(row["sigma"]), Int(row["L"]), Float64(row["Gamma"]),
        Int(row["chi"]), Int(row["poles"])
    ))
    return drift
end

function main(args)
    length(args) == 1 || error("usage: julia analyze.jl RESULT_DIR")
    result_directory = abspath(args[1])
    payload = JSON.parsefile(joinpath(result_directory, "raw.json"))
    rows = payload["rows"]

    crossing_rows = Dict{String, Any}[]
    groups = Dict{Tuple, Vector{Dict{String, Any}}}()
    for row in rows
        key = (
            row["model"], row["sigma"], Int(row["chi"]),
            row["poles"] === nothing ? nothing : Int(row["poles"])
        )
        push!(get!(groups, key, Dict{String, Any}[]), row)
    end
    for (key, group) in groups
        lengths = sort!(unique(Int(row["L"]) for row in group))
        for L in lengths
            2L in lengths || continue
            value = crossing(
                filter(row -> Int(row["L"]) == L, group),
                filter(row -> Int(row["L"]) == 2L, group),
            )
            isnothing(value) || push!(crossing_rows, Dict(
                "model" => key[1], "sigma" => key[2], "chi" => key[3],
                "poles" => key[4], "L_pair" => [L, 2L], "Gamma_crossing" => value,
            ))
        end
    end

    z_fit = fit_dynamic_exponent(rows)
    validation = validation_audit(rows)
    drift_rows = pole_drift_rows(rows)
    gate_failed = !validation["largest_pole_rows_pass"]
    status = gate_failed ?
        "pipeline validation; largest-pole MPO-ED gate failed, so larger scans must stop" :
        (isempty(crossing_rows) ?
            "pipeline validation; more common Gamma points are required" :
            "finite-size preliminary result")
    summary = Dict(
        "crossings" => crossing_rows,
        "nn_dynamic_exponent_fit" => z_fit,
        "validation" => validation,
        "status" => status,
    )
    open(joinpath(result_directory, "summary.json"), "w") do io
        JSON.print(io, summary, 2)
        println(io)
    end
    write_table(
        joinpath(result_directory, "crossings.csv"),
        ["model", "sigma", "chi", "poles", "L_pair", "Gamma_crossing"],
        crossing_rows,
    )
    write_table(
        joinpath(result_directory, "pole_drift.csv"),
        [
            "sigma", "L", "Gamma", "chi", "poles", "mpo_max_relative",
            "energy_relative_error", "correlation_absolute_error",
        ],
        drift_rows,
    )

    for (key, group) in groups
        length(unique(row["Gamma"] for row in group)) >= 2 || continue
        plot_object = plot(
            xlabel = "Gamma", ylabel = "xi/L", legend = :best,
            title = "$(key[1]) sigma=$(key[2]) chi=$(key[3]) poles=$(key[4])",
        )
        for L in sort!(unique(Int(row["L"]) for row in group))
            subset = sort!(
                filter(row -> Int(row["L"]) == L, group);
                by = row -> Float64(row["Gamma"])
            )
            plot!(
                plot_object, Float64[row["Gamma"] for row in subset],
                Float64[row["correlation_ratio"] for row in subset];
                marker = :circle, label = "L=$L",
            )
        end
        filename = replace(
            "crossing_$(key[1])_sigma$(key[2])_chi$(key[3])_p$(key[4]).png",
            "nothing" => "na",
        )
        savefig(plot_object, joinpath(result_directory, filename))
    end

    if !isnothing(z_fit)
        lengths = Float64.(z_fit["lengths"])
        gaps = Float64.(z_fit["gaps"])
        plot_object = scatter(
            lengths, gaps; xscale = :log10, yscale = :log10,
            xlabel = "L", ylabel = "gap", label = "DMRG",
            title = "NN gap scaling: z=$(round(z_fit["z"], digits=4))",
        )
        reference = gaps[1] .* (lengths ./ lengths[1]) .^ (-z_fit["z"])
        plot!(plot_object, lengths, reference; label = "power-law fit")
        savefig(plot_object, joinpath(result_directory, "nn_gap_scaling.png"))
    end

    drift_groups = Dict{Tuple, Vector{Dict{String, Any}}}()
    for row in drift_rows
        key = (row["sigma"], row["L"], row["Gamma"], row["chi"])
        push!(get!(drift_groups, key, Dict{String, Any}[]), row)
    end
    for (key, group) in drift_groups
        length(group) >= 2 || continue
        poles = Int[row["poles"] for row in group]
        plot_object = plot(
            poles, Float64[row["mpo_max_relative"] for row in group];
            marker = :circle, yscale = :log10, label = "coupling",
            xlabel = "poles", ylabel = "absolute/relative error",
            title = "pole drift: sigma=$(key[1]) L=$(key[2])",
        )
        plot!(
            plot_object, poles, Float64[row["energy_relative_error"] for row in group];
            marker = :square, label = "E0 vs ED",
        )
        plot!(
            plot_object, poles, Float64[row["correlation_absolute_error"] for row in group];
            marker = :diamond, label = "xi/L vs ED",
        )
        hline!(plot_object, [ENERGY_TOLERANCE]; linestyle = :dash, label = "E0 gate")
        hline!(
            plot_object, [CORRELATION_TOLERANCE];
            linestyle = :dot, label = "xi/L gate",
        )
        filename = "pole_drift_sigma$(key[1])_L$(key[2])_chi$(key[4]).png"
        savefig(plot_object, joinpath(result_directory, filename))
    end

    println("analysis written to $result_directory")
end

main(ARGS)
