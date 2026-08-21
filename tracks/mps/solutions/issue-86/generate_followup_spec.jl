#!/usr/bin/env julia

using JSON
using Dates

include(joinpath(@__DIR__, "src", "Issue86TrackB.jl"))
using .Issue86TrackB

function write_json_atomic(path, payload)
    mkpath(dirname(path))
    temporary = path * ".tmp-" * string(getpid())
    open(temporary, "w") do io
        JSON.print(io, payload, 2)
        println(io)
    end
    mv(temporary, path; force = true)
end

function result_identity(params)
    return (
        params["model"],
        get(params, "sigma", nothing),
        Int(params["L"]),
        Float64(params["gamma"]),
        Int(params["chi"]),
        get(params, "poles", nothing),
        Bool(get(params, "excited", false)),
    )
end

function source_params_by_cell_id(result_directories)
    params_by_id = Dict{String, Dict{String, Any}}()
    for result_directory in result_directories
        spec_path = joinpath(result_directory, "run_spec.json")
        isfile(spec_path) || error("missing run spec: $spec_path")
        spec = JSON.parsefile(spec_path)
        for cell in spec["cells"]
            cell_id = String(cell["cell_id"])
            haskey(params_by_id, cell_id) &&
                error("duplicate source cell id: $cell_id")
            params_by_id[cell_id] = Dict{String, Any}(cell["params"])
        end
    end
    return params_by_id
end

function successful_source_identities(result_directories)
    identities = Set{Tuple}()
    for result_directory in result_directories
        spec = JSON.parsefile(joinpath(result_directory, "run_spec.json"))
        for cell in spec["cells"]
            manifest_path = joinpath(
                result_directory,
                "cells",
                String(cell["cell_id"]),
                "manifest.json",
            )
            manifest = Issue86TrackB._successful_manifest(manifest_path, cell)
            isnothing(manifest) ||
                push!(identities, result_identity(cell["params"]))
        end
    end
    return identities
end

function add_followup_entry!(entries, params, reason, source_cell_id)
    key = result_identity(params)
    if !haskey(entries, key)
        entries[key] = Dict{String, Any}(
            "params" => Dict{String, Any}(params),
            "reasons" => Set{String}(),
            "source_cell_ids" => Set{String}(),
        )
    end
    entry = entries[key]
    push!(entry["reasons"], String(reason))
    push!(entry["source_cell_ids"], String(source_cell_id))
    reason == "convergence_retry" &&
        (entry["params"] = Dict{String, Any}(params))
    return entry
end

function build_followup_spec(
        formal_directory,
        result_directories;
        run_id,
        stage,
    )
    summary = JSON.parsefile(joinpath(formal_directory, "formal_summary.json"))
    adaptive = JSON.parsefile(
        joinpath(formal_directory, "adaptive_run_spec.json")
    )
    params_by_id = source_params_by_cell_id(result_directories)
    successful_identities = successful_source_identities(result_directories)
    entries = Dict{Tuple, Dict{String, Any}}()
    deferred_quality = Dict{String, Any}[]
    convergence_retry_source_cells = 0

    for cell in adaptive["cells"]
        add_followup_entry!(
            entries,
            Dict{String, Any}(cell["params"]),
            "adaptive",
            cell["cell_id"],
        )
    end

    for failure in summary["convergence_audit"]["failures"]
        residual = Float64(get(
            failure, "convergence_residual", Inf
        ))
        variance = Float64(get(
            failure, "normalized_ground_variance", Inf
        ))
        source_cell_id = get(failure, "cell_id", nothing)
        isnothing(source_cell_id) &&
            error("convergence failure is missing cell_id provenance")
        haskey(params_by_id, source_cell_id) ||
            error("source cell id not found in run specs: $source_cell_id")
        if residual < 1.0e-8 && variance >= 1.0e-10
            push!(deferred_quality, Dict{String, Any}(
                "source_cell_id" => source_cell_id,
                "model" => get(failure, "model", nothing),
                "sigma" => get(failure, "sigma", nothing),
                "L" => get(failure, "L", nothing),
                "Gamma" => get(failure, "Gamma", nothing),
                "chi" => get(failure, "chi", nothing),
                "poles" => get(failure, "poles", nothing),
                "excited" => get(failure, "excited", false),
                "normalized_ground_variance" => variance,
                "convergence_residual" => residual,
                "reason" => "finite_chi_limit",
                "recommended_action" => "chi128_manual_review",
            ))
            continue
        end
        residual >= 1.0e-8 || continue
        params = copy(params_by_id[source_cell_id])
        params["tolerance"] = 1.0e-11
        params["maxiter"] = 80
        params["seed"] = 86
        add_followup_entry!(
            entries, params, "convergence_retry", source_cell_id
        )
        convergence_retry_source_cells += 1
    end
    completed_adaptive_cells_skipped = 0
    for key in collect(keys(entries))
        entry = entries[key]
        if key in successful_identities &&
                entry["reasons"] == Set(["adaptive"])
            delete!(entries, key)
            completed_adaptive_cells_skipped += 1
        end
    end

    ordered_entries = sort!(
        collect(values(entries));
        by = entry -> Issue86TrackB._canonical_cell_value(entry["params"]),
    )
    cells = Dict{String, Any}[]
    reasons = Dict{String, Any}[]
    for entry in ordered_entries
        params = entry["params"]
        cell_id = Issue86TrackB._cell_id(stage, params)
        cell_resource_class = resource_class(params)
        push!(cells, Dict{String, Any}(
            "cell_id" => cell_id,
            "stage" => String(stage),
            "resource_class" => cell_resource_class,
            "params" => params,
        ))
        push!(reasons, Dict{String, Any}(
            "cell_id" => cell_id,
            "resource_class" => cell_resource_class,
            "reason" => join(sort!(collect(entry["reasons"])), "+"),
            "source_cell_id" =>
                join(sort!(collect(entry["source_cell_ids"])), ";"),
            "model" => params["model"],
            "sigma" => get(params, "sigma", nothing),
            "L" => params["L"],
            "Gamma" => params["gamma"],
            "chi" => params["chi"],
            "poles" => get(params, "poles", nothing),
            "excited" => get(params, "excited", false),
            "tolerance" => params["tolerance"],
            "maxiter" => params["maxiter"],
            "seed" => params["seed"],
        ))
    end
    cell_ids = [cell["cell_id"] for cell in cells]
    length(unique(cell_ids)) == length(cell_ids) ||
        error("follow-up run spec contains duplicate cell ids")

    spec = Dict{String, Any}(
        "metadata" => Dict{String, Any}(
            "schema_version" => 1,
            "run_id" => String(run_id),
            "stage" => String(stage),
            "jobs_total" => length(cells),
            "created_utc" => string(now(UTC)),
            "code_commit" => Issue86TrackB._git_revision(),
            "hamiltonian" =>
                "-sum_{i<j} J_L(|i-j|) Z_i Z_j - Gamma sum_i X_i",
            "boundary" => "periodic image sum via Hurwitz zeta",
            "formal_source" => abspath(formal_directory),
            "result_sources" => abspath.(result_directories),
            "adaptive_source_cells" => length(adaptive["cells"]),
            "completed_adaptive_cells_skipped" =>
                completed_adaptive_cells_skipped,
            "convergence_failure_source_cells" =>
                length(summary["convergence_audit"]["failures"]),
            "convergence_retry_source_cells" =>
                convergence_retry_source_cells,
            "deferred_quality_source_cells" => length(deferred_quality),
        ),
        "cells" => cells,
    )
    sort!(deferred_quality; by = row -> String(row["source_cell_id"]))
    return spec, reasons, deferred_quality
end

function csv_value(value)
    text = isnothing(value) ? "" : string(value)
    if occursin(',', text) || occursin('"', text) ||
            occursin('\n', text) || occursin('\r', text)
        return "\"" * replace(text, "\"" => "\"\"") * "\""
    end
    return text
end

function write_reason_csv(path, reasons)
    columns = [
        "cell_id", "resource_class", "reason", "source_cell_id",
        "model", "sigma", "L", "Gamma", "chi", "poles", "excited",
        "tolerance", "maxiter", "seed",
    ]
    mkpath(dirname(path))
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in reasons
            println(io, join((csv_value(row[column]) for column in columns), ","))
        end
    end
end

function write_deferred_quality_csv(path, rows)
    columns = [
        "source_cell_id", "model", "sigma", "L", "Gamma", "chi", "poles",
        "excited", "normalized_ground_variance", "convergence_residual",
        "reason", "recommended_action",
    ]
    mkpath(dirname(path))
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in rows
            println(io, join((csv_value(row[column]) for column in columns), ","))
        end
    end
end

function main(args)
    length(args) >= 6 || error(
        "usage: generate_followup_spec.jl FORMAL_DIR RUN_SPEC.json " *
        "REASON.csv RUN_ID STAGE RESULT_DIR [...]"
    )
    formal_directory = abspath(args[1])
    output_spec = abspath(args[2])
    reason_csv = abspath(args[3])
    run_id = args[4]
    stage = args[5]
    result_directories = abspath.(args[6:end])
    spec, reasons, deferred_quality = build_followup_spec(
        formal_directory, result_directories; run_id, stage
    )
    write_json_atomic(output_spec, spec)
    write_reason_csv(reason_csv, reasons)
    write_deferred_quality_csv(
        joinpath(dirname(reason_csv), "deferred_quality.csv"),
        deferred_quality,
    )
    class_counts = Dict(
        class => count(cell -> cell["resource_class"] == class, spec["cells"])
        for class in ("A", "B", "C", "D")
    )
    println(
        "wrote $(length(spec["cells"])) follow-up cells to $output_spec; " *
        "classes=$class_counts; deferred_quality=$(length(deferred_quality))"
    )
    flush(stdout)
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main(ARGS)
