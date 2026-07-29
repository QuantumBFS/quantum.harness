#!/usr/bin/env julia

using JSON
using Plots
using Statistics

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

const REFERENCES = Dict(
    1.75 => (value = 1.5609, error = 0.0003),
    2.0 => (value = 1.4208, error = 0.0002),
)

function write_json(path, payload)
    mkpath(dirname(path))
    open(path, "w") do io
        JSON.print(io, payload, 2)
        println(io)
    end
end

function result_key(row)
    return (
        row["model"], row["sigma"], Int(row["L"]), Float64(row["Gamma"]),
        Int(row["chi"]), row["poles"], get(row, "excited", !isnothing(row["gap"])),
    )
end

function load_rows(inputs)
    selected = Dict{Tuple, Dict{String, Any}}()
    for input in inputs
        input_rows = if isdir(input) && isfile(joinpath(input, "run_spec.json"))
            spec = JSON.parsefile(joinpath(input, "run_spec.json"))
            collect_cell_results(spec, input)
        else
            path = isdir(input) ? joinpath(input, "raw.json") : input
            JSON.parsefile(path)["rows"]
        end
        for raw_row in input_rows
            row = Dict{String, Any}(raw_row)
            key = result_key(row)
            if !haskey(selected, key)
                selected[key] = row
                continue
            end
            old_residual = Float64(get(selected[key], "convergence_residual", Inf))
            new_residual = Float64(get(row, "convergence_residual", Inf))
            new_residual < old_residual && (selected[key] = row)
        end
    end
    return collect(values(selected))
end

function crossing_records(rows)
    records = Dict{String, Any}[]
    groups = Dict{Tuple, Vector{Dict{String, Any}}}()
    for row in rows
        key = (
            row["model"], row["sigma"], Int(row["chi"]),
            isnothing(row["poles"]) ? nothing : Int(row["poles"]),
        )
        push!(get!(groups, key, Dict{String, Any}[]), row)
    end
    for (key, group) in groups
        lengths = sort!(unique(Int(row["L"]) for row in group))
        for L in lengths
            2L in lengths || continue
            bracket = crossing_bracket(
                filter(row -> Int(row["L"]) == L, group),
                filter(row -> Int(row["L"]) == 2L, group),
            )
            isnothing(bracket) && continue
            push!(records, merge(
                Dict{String, Any}(
                    "model" => key[1],
                    "sigma" => key[2],
                    "chi" => key[3],
                    "poles" => key[4],
                    "L" => L,
                    "L_pair" => [L, 2L],
                ),
                bracket,
            ))
        end
    end
    sort!(records; by = row -> (
        string(row["model"]), something(row["sigma"], 0.0), row["chi"],
        something(row["poles"], 0), row["L"],
    ))
    return records
end

function find_crossing(records, sigma, chi, poles, L)
    matches = filter(records) do row
        row["model"] == "long_range" &&
            Float64(row["sigma"]) == sigma &&
            Int(row["chi"]) == chi &&
            Int(row["poles"]) == poles &&
            Int(row["L"]) == L
    end
    return isempty(matches) ? nothing : only(matches)
end

function sigma_audit(records, sigma)
    reference = REFERENCES[sigma]
    baseline = filter(records) do row
        row["model"] == "long_range" &&
            Float64(row["sigma"]) == sigma &&
            Int(row["chi"]) == 64 &&
            Int(row["poles"]) == 16
    end
    missing = String[]
    length(baseline) >= 4 || push!(missing, "four baseline size pairs")
    size_fit = length(baseline) >= 4 ? fit_crossing_sequence(baseline) : nothing
    largest = isempty(baseline) ? nothing : baseline[argmax(Int(row["L"]) for row in baseline)]
    isnothing(largest) && push!(missing, "largest baseline crossing")

    chi_crossing = find_crossing(records, sigma, 128, 16, 32)
    pole_crossing = find_crossing(records, sigma, 64, 12, 32)
    isnothing(chi_crossing) && push!(missing, "chi=128 L=32/64 crossing")
    isnothing(pole_crossing) && push!(missing, "P=12 L=32/64 crossing")

    if !isempty(missing)
        return Dict{String, Any}(
            "sigma" => sigma,
            "reference" => reference.value,
            "reference_error" => reference.error,
            "status" => "insufficient data",
            "missing" => missing,
            "size_fit" => size_fit,
        )
    end

    estimate = Float64(size_fit["Gamma_c"])
    last_crossing = Float64(largest["Gamma_crossing"])
    reduced_estimate = Float64(size_fit["without_smallest"]["Gamma_c"])
    finite_size = maximum(abs.([
        estimate - last_crossing,
        estimate - reduced_estimate,
    ]))
    baseline_3264 = find_crossing(records, sigma, 64, 16, 32)
    isnothing(baseline_3264) &&
        return Dict(
            "sigma" => sigma,
            "status" => "insufficient data",
            "missing" => ["P=16 chi=64 L=32/64 crossing"],
            "size_fit" => size_fit,
        )
    chi_shift = abs(
        Float64(chi_crossing["Gamma_crossing"]) -
        Float64(baseline_3264["Gamma_crossing"])
    )
    mpo_shift = abs(
        Float64(pole_crossing["Gamma_crossing"]) -
        Float64(baseline_3264["Gamma_crossing"])
    )
    budget = conservative_error_budget(
        estimate;
        interpolation = Float64(largest["interpolation_half_width"]),
        finite_size,
        chi = chi_shift,
        mpo = mpo_shift,
        reference = reference.value,
        reference_error = reference.error,
    )
    refined = Float64(largest["Gamma_high"]) - Float64(largest["Gamma_low"]) <= 0.001
    budget["sigma"] = sigma
    budget["size_fit"] = size_fit
    budget["largest_crossing"] = largest
    budget["status"] = budget["covers_reference_interval"] && refined ?
        "formal reproduction" : "finite-size preliminary result"
    budget["crossing_bracket_refined"] = refined
    return budget
end

function adaptive_sweeps(records)
    sweeps = Any[]
    for row in records
        row["model"] == "long_range" || continue
        sigma = Float64(row["sigma"])
        chi = Int(row["chi"])
        poles = Int(row["poles"])
        L = Int(row["L"])
        selected = (chi == 64 && poles == 16) ||
            (L == 32 && ((chi == 64 && poles == 12) ||
                         (chi == 128 && poles == 16)))
        selected || continue
        width = Float64(row["Gamma_high"]) - Float64(row["Gamma_low"])
        width > 0.001 || continue
        midpoint = (Float64(row["Gamma_high"]) + Float64(row["Gamma_low"])) / 2
        push!(sweeps, Dict{String, Any}(
            "model" => "long_range",
            "sigmas" => [sigma],
            "lengths" => [L, 2L],
            "gammas" => [midpoint],
            "chis" => [chi],
            "poles" => [poles],
            "tolerance" => 1.0e-9,
            "maxiter" => chi >= 128 ? 50 : 40,
            "excited" => false,
            "seed" => 86,
        ))
    end
    return sweeps
end

function write_crossing_table(path, records)
    columns = [
        "model", "sigma", "chi", "poles", "L", "L_pair",
        "Gamma_low", "Gamma_high", "Gamma_crossing", "interpolation_half_width",
    ]
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in records
            println(io, join((get(row, column, "") for column in columns), ","))
        end
    end
end

function plot_size_drift(output_directory, records, audits)
    for sigma in sort!(collect(keys(REFERENCES)))
        baseline = filter(records) do row
            row["model"] == "long_range" &&
                Float64(row["sigma"]) == sigma &&
                Int(row["chi"]) == 64 &&
                Int(row["poles"]) == 16
        end
        isempty(baseline) && continue
        lengths = Float64[row["L"] for row in baseline]
        values = Float64[row["Gamma_crossing"] for row in baseline]
        plot_object = scatter(
            lengths, values;
            xlabel = "L in (L,2L)",
            ylabel = "Gamma crossing",
            label = "P=16, chi=64",
            title = "finite-size drift: sigma=$sigma",
        )
        hline!(
            plot_object, [REFERENCES[sigma].value];
            linestyle = :dash, label = "literature",
        )
        audit = audits[string(sigma)]
        if haskey(audit, "size_fit") && !isnothing(audit["size_fit"])
            fit = audit["size_fit"]
            grid = range(minimum(lengths), maximum(lengths); length = 200)
            fitted = fit["Gamma_c"] .+ fit["amplitude"] .* grid .^ (-fit["omega"])
            plot!(plot_object, grid, fitted; label = "power correction fit")
        end
        savefig(plot_object, joinpath(output_directory, "finite_size_sigma$(sigma).png"))
    end
end

function nn_audit(records, rows)
    crossings = filter(records) do row
        row["model"] == "nn" && Int(row["chi"]) == 64
    end
    largest = isempty(crossings) ? nothing :
        crossings[argmax(Int(row["L"]) for row in crossings)]
    gap_fit = fit_dynamic_exponent(rows)
    gamma_pass = !isnothing(largest) &&
        abs(Float64(largest["Gamma_crossing"]) - 1.0) < 0.005
    z_pass = !isnothing(gap_fit) &&
        0.95 < Float64(gap_fit["z"]) < 1.05 &&
        haskey(gap_fit, "without_smallest") &&
        0.95 < Float64(gap_fit["without_smallest"]["z"]) < 1.05
    return Dict{String, Any}(
        "Gamma_crossing" => isnothing(largest) ? nothing : largest["Gamma_crossing"],
        "gap_fit" => gap_fit,
        "gamma_pass" => gamma_pass,
        "z_pass" => z_pass,
        "status" => gamma_pass && z_pass ? "pass" : "insufficient or outside gate",
    )
end

function convergence_audit(rows)
    failures = Dict{String, Any}[]
    for row in rows
        Int(row["chi"]) >= 64 || continue
        normalized = haskey(row, "normalized_ground_variance") ?
            Float64(row["normalized_ground_variance"]) :
            normalized_energy_variance(
                Float64(row["ground_variance"]), Float64(row["E0"])
            )
        residual = Float64(row["convergence_residual"])
        normalized < 1.0e-10 && residual < 1.0e-8 && continue
        push!(failures, Dict(
            "model" => row["model"],
            "sigma" => row["sigma"],
            "L" => row["L"],
            "Gamma" => row["Gamma"],
            "chi" => row["chi"],
            "poles" => row["poles"],
            "normalized_ground_variance" => normalized,
            "convergence_residual" => residual,
        ))
    end
    return Dict(
        "normalized_variance_tolerance" => 1.0e-10,
        "residual_tolerance" => 1.0e-8,
        "passes" => isempty(failures),
        "failures" => failures,
    )
end

function plot_nn_gap(output_directory, audit)
    fit = audit["gap_fit"]
    isnothing(fit) && return
    lengths = Float64.(fit["lengths"])
    gaps = Float64.(fit["gaps"])
    plot_object = scatter(
        lengths, gaps;
        xscale = :log10,
        yscale = :log10,
        xlabel = "L",
        ylabel = "gap",
        label = "DMRG",
        title = "NN gap scaling: z=$(round(fit["z"], digits = 5))",
    )
    reference = gaps[1] .* (lengths ./ lengths[1]) .^ (-fit["z"])
    plot!(plot_object, lengths, reference; label = "power-law fit")
    savefig(plot_object, joinpath(output_directory, "nn_gap_scaling.png"))
end

function main(args)
    length(args) >= 2 ||
        error("usage: analyze_formal.jl OUTPUT_DIR RESULT_DIR_OR_RAW_JSON [...]")
    output_directory = abspath(args[1])
    inputs = abspath.(args[2:end])
    mkpath(output_directory)

    rows = load_rows(inputs)
    records = crossing_records(rows)
    audits = Dict(string(sigma) => sigma_audit(records, sigma) for sigma in keys(REFERENCES))
    nn = nn_audit(records, rows)
    convergence = convergence_audit(rows)
    sweeps = adaptive_sweeps(records)
    adaptive_spec = build_run_spec(
        Dict("sweeps" => sweeps);
        run_id = "issue-86-adaptive",
        stage = "adaptive",
    )
    long_range_passes = all(
        get(audit, "status", "") == "formal reproduction" for audit in values(audits)
    )
    overall_status = long_range_passes &&
        nn["status"] == "pass" &&
        convergence["passes"] ?
        "formal reproduction" : "pipeline validation / finite-size preliminary result"

    Issue86TrackB._write_json(
        joinpath(output_directory, "raw.json"),
        Dict("metadata" => Dict("source_inputs" => inputs), "rows" => rows),
    )
    Issue86TrackB._write_csv(joinpath(output_directory, "raw.csv"), rows)
    write_json(joinpath(output_directory, "crossings.json"), records)
    write_crossing_table(joinpath(output_directory, "crossings.csv"), records)
    write_json(
        joinpath(output_directory, "formal_summary.json"),
        Dict(
            "status" => overall_status,
            "sigma_audits" => audits,
            "nn_audit" => nn,
            "convergence_audit" => convergence,
            "adaptive_cells" => length(adaptive_spec["cells"]),
        ),
    )
    write_json(joinpath(output_directory, "adaptive_run_spec.json"), adaptive_spec)
    plot_size_drift(output_directory, records, audits)
    plot_nn_gap(output_directory, nn)

    println("formal analysis: $overall_status")
    println("adaptive cells requested: $(length(adaptive_spec["cells"]))")
    flush(stdout)
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main(ARGS)
