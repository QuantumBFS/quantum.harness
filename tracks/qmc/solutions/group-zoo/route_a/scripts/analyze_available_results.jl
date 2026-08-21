using JSON
using LinearAlgebra

include(joinpath(@__DIR__, "aggregate_route_a.jl"))
using .Challenge148

const _PRIMARY_KEY = (:M1, 8, :fixed)

analysis_status(triangle_accepted::Bool, honeycomb_accepted::Bool) =
    triangle_accepted && honeycomb_accepted ?
    (status="pass", verdict_eligible=true) :
    (status="gate-pending", verdict_eligible=false)

function parse_available_args(arguments::Vector{String})
    length(arguments) == 6 || throw(ArgumentError(
        "usage: analyze_available_results.jl --manifest PATH --results DIR --output DIR"))
    arguments[1] == "--manifest" && arguments[3] == "--results" &&
        arguments[5] == "--output" || throw(ArgumentError(
        "usage: analyze_available_results.jl --manifest PATH --results DIR --output DIR"))
    all(!isempty, (arguments[2], arguments[4], arguments[6])) ||
        throw(ArgumentError("analysis paths must be nonempty"))
    return (manifest=arguments[2], results=arguments[4], output=arguments[6])
end

_json_number(value::Real) = isfinite(value) ? Float64(value) : nothing
_fit_key_available(fit::BinderFitResult) = (fit.model, fit.L_min, fit.yt_mode)

function _available_records(manifest_path::String, results_dir::String)
    campaign = _read_campaign_manifest(manifest_path)
    tasks = Dict(task.output_path => task for task in campaign.tasks)
    names = sort!(filter(name -> endswith(name, ".json"), readdir(results_dir)))
    unexpected = sort!(setdiff(names, collect(keys(tasks))))
    isempty(unexpected) || throw(ArgumentError(
        "results directory contains unexpected JSON: $(join(unexpected, ", "))"))
    records = ReplicaBinderData[]
    for name in names
        task = tasks[name]
        result = verify_completed_result(
            joinpath(results_dir, name), task;
            git_commit=campaign.git_commit,
            manifest_hash=campaign.julia_manifest_sha256,
        )
        raw = result["raw_bins"]
        push!(records, ReplicaBinderData(
            task.lattice, task.L, task.h, task.c, task.replica, task_id(task),
            Float64.(raw["m_time2"]), Float64.(raw["m_time4"]),
        ))
    end
    missing = sort!(setdiff(collect(keys(tasks)), names))
    return campaign, records, missing
end

function _window_record(fit::BinderFitResult, lattice::Symbol)
    return (
        lattice=String(lattice),
        model=String(fit.model),
        L_min=fit.L_min,
        yt_mode=String(fit.yt_mode),
        hc=_json_number(fit.parameters.hc),
        reduced_chi2=_json_number(fit.reduced_chi2),
        dof=fit.dof,
        converged=fit.converged,
        accepted=fit.accepted,
        rejection_reasons=fit.rejection_reasons,
        sizes=fit.sizes,
    )
end

function _hc_stderr(fit::BinderFitResult)
    index = findfirst(==(:hc), fit.parameter_names)
    index === nothing && throw(ArgumentError("fit has no critical-field parameter"))
    variance = fit.covariance[index, index]
    return isfinite(variance) && variance >= 0 ? sqrt(variance) : NaN
end

function analyze_available_results(manifest_path::String, results_dir::String, output_dir::String)
    isdir(output_dir) || mkpath(output_dir)
    campaign, records, missing = _available_records(manifest_path, results_dir)
    groups = Challenge148._replica_groups(records)
    triangle_fits = enumerate_binder_fits(Challenge148._binder_points(groups, :triangle, 1.0))
    honeycomb_fits = enumerate_binder_fits(Challenge148._binder_points(groups, :honeycomb, 1.0))
    triangle = Dict(_fit_key_available(fit) => fit for fit in triangle_fits)
    honeycomb = Dict(_fit_key_available(fit) => fit for fit in honeycomb_fits)
    triangle_primary = triangle[_PRIMARY_KEY]
    honeycomb_primary = honeycomb[_PRIMARY_KEY]
    gate = analysis_status(triangle_primary.accepted, honeycomb_primary.accepted)

    triangle_hc = triangle_primary.parameters.hc
    honeycomb_hc = honeycomb_primary.parameters.hc
    ratio = triangle_hc / honeycomb_hc
    triangle_sigma = _hc_stderr(triangle_primary)
    honeycomb_sigma = _hc_stderr(honeycomb_primary)
    ratio_sigma = hypot(
        triangle_sigma / honeycomb_hc,
        triangle_hc * honeycomb_sigma / honeycomb_hc^2,
    )

    matched = NamedTuple[]
    for key in sort!(collect(intersect(Set(keys(triangle)), Set(keys(honeycomb))));
        by=key -> (String(key[1]), key[2], String(key[3])))
        triangle_fit = triangle[key]
        honeycomb_fit = honeycomb[key]
        triangle_fit.accepted && honeycomb_fit.accepted || continue
        push!(matched, (
            model=String(key[1]), L_min=key[2], yt_mode=String(key[3]),
            R=triangle_fit.parameters.hc / honeycomb_fit.parameters.hc,
        ))
    end
    matched_ratios = getfield.(matched, :R)

    windows = vcat(
        [_window_record(fit, :triangle) for fit in triangle_fits],
        [_window_record(fit, :honeycomb) for fit in honeycomb_fits],
    )
    summary = (
        schema_version=1,
        kind="route_a_available_result_analysis",
        status=gate.status,
        verdict_eligible=gate.verdict_eligible,
        conclusion=gate.verdict_eligible ?
            "primary frozen fits passed" :
            "no Challenge #148 verdict: at least one frozen primary fit failed",
        completed_tasks=length(records),
        expected_tasks=length(campaign.tasks),
        missing_outputs=missing,
        provenance=(
            campaign_id=campaign.campaign_id,
            campaign_checksum=campaign.campaign_checksum,
            git_commit=campaign.git_commit,
            julia_manifest_sha256=campaign.julia_manifest_sha256,
        ),
        primary_diagnostic=(
            label="diagnostic only; rejected fits cannot support the verdict",
            triangle_hc=triangle_hc,
            triangle_hc_covariance_stderr=_json_number(triangle_sigma),
            triangle_accepted=triangle_primary.accepted,
            triangle_rejection_reasons=triangle_primary.rejection_reasons,
            triangle_reduced_chi2=_json_number(triangle_primary.reduced_chi2),
            honeycomb_hc=honeycomb_hc,
            honeycomb_hc_covariance_stderr=_json_number(honeycomb_sigma),
            honeycomb_accepted=honeycomb_primary.accepted,
            honeycomb_rejection_reasons=honeycomb_primary.rejection_reasons,
            honeycomb_reduced_chi2=_json_number(honeycomb_primary.reduced_chi2),
            R=ratio,
            R_covariance_stderr=_json_number(ratio_sigma),
            sqrt5=sqrt(5),
            Delta=ratio - sqrt(5),
        ),
        stability_diagnostic=(
            accepted_matched_window_count=length(matched),
            accepted_matched_windows=matched,
            R_min=isempty(matched_ratios) ? nothing : minimum(matched_ratios),
            R_max=isempty(matched_ratios) ? nothing : maximum(matched_ratios),
        ),
        fit_windows_file="fit_windows_available.json",
    )
    atomic_write_json(joinpath(output_dir, "fit_windows_available.json"), (
        schema_version=1,
        kind="route_a_available_fit_windows",
        status=gate.status,
        fit_windows=windows,
    ))
    atomic_write_json(joinpath(output_dir, "route_a_available_analysis.json"), summary)
    return summary
end

function _main_available()
    arguments = parse_available_args(copy(ARGS))
    summary = analyze_available_results(
        arguments.manifest, arguments.results, arguments.output)
    println(JSON.json(summary))
    flush(stdout)
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    try
        _main_available()
    catch error
        Base.display_error(stderr, catch_backtrace())
        exit(1)
    end
end
