#!/usr/bin/env julia

using Dates
using JSON
using SHA

const EXPECTED_SIGMAS = (1.75, 2.0)
const EXPECTED_BASELINE_PAIRS = ((8, 16), (16, 32), (24, 48), (32, 64))
const BRACKET_TOLERANCE = 1.0e-3
const ADJACENT_DRIFT_TOLERANCE = 1.0e-4
const COMPUTE_VARIANCE_TOLERANCE = 1.0e-10
const COMPUTE_RESIDUAL_TOLERANCE = 1.0e-8
const FORMAL_STATUS = "formal reproduction of the Track B validation floor"
const PRELIMINARY_STATUS =
    "pipeline validation / finite-size preliminary result"
const ISSUE_URL =
    "https://github.com/QuantumBFS/quantum.harness/issues/86"

function write_json_atomic(path, payload)
    mkpath(dirname(path))
    temporary = path * ".tmp-" * string(getpid())
    try
        open(temporary, "w") do io
            JSON.print(io, payload, 2)
            println(io)
        end
        mv(temporary, path; force = true)
    finally
        isfile(temporary) && rm(temporary; force = true)
    end
    return path
end

function canonical_value(value)
    isnothing(value) && return "n:null"
    value isa Bool && return value ? "b:true" : "b:false"
    value isa Integer && return "i:" * string(value)
    value isa AbstractFloat &&
        return "f:" * string(reinterpret(UInt64, Float64(value)))
    value isa AbstractString && return "s:" * JSON.json(value)
    value isa AbstractVector &&
        return "a:[" * join(canonical_value.(value), ",") * "]"
    if value isa AbstractDict
        keys_sorted = sort!(String.(collect(keys(value))))
        entries = (
            JSON.json(key) * ":" * canonical_value(value[key])
            for key in keys_sorted
        )
        return "d:{" * join(entries, ",") * "}"
    end
    error("unsupported recommendation parameter type $(typeof(value))")
end

function recommendation_cell_id(stage, params)
    digest = first(bytes2hex(sha1(
        "issue86-recommendation-v1|" * canonical_value(params)
    )), 32)
    return "$(stage)-$(digest)"
end

function recommendation_resource_class(params)
    Int(params["chi"]) >= 256 && return "D"
    Int(params["L"]) >= 128 && return "C"
    Int(params["chi"]) >= 128 && return "B"
    return "A"
end

function make_run_spec(run_id, stage, params_rows, compute_commit)
    unique_params = Dict{String, Dict{String, Any}}()
    for params in params_rows
        unique_params[canonical_value(params)] = Dict{String, Any}(params)
    end
    ordered = sort!(
        collect(values(unique_params));
        by = canonical_value,
    )
    cells = [
        Dict{String, Any}(
            "cell_id" => recommendation_cell_id(stage, params),
            "stage" => stage,
            "resource_class" => recommendation_resource_class(params),
            "params" => params,
        )
        for params in ordered
    ]
    return Dict{String, Any}(
        "metadata" => Dict{String, Any}(
            "schema_version" => 1,
            "run_id" => run_id,
            "stage" => stage,
            "jobs_total" => length(cells),
            "created_utc" => string(now(UTC)),
            "code_commit" => compute_commit,
            "automatic_submission" => false,
            "hamiltonian" =>
                "-sum_{i<j} J_L(|i-j|) Z_i Z_j - Gamma sum_i X_i",
            "boundary" => "periodic image sum via Hurwitz zeta",
        ),
        "cells" => cells,
    )
end

function baseline_crossings(records, sigma)
    return sort!(
        filter(records) do row
            row["model"] == "long_range" &&
                Float64(row["sigma"]) == sigma &&
                Int(row["chi"]) == 64 &&
                Int(row["poles"]) == 16
        end;
        by = row -> Int(row["L"]),
    )
end

function crossing_for(records, sigma, L)
    matches = filter(baseline_crossings(records, sigma)) do row
        Int(row["L"]) == L
    end
    return isempty(matches) ? nothing : last(matches)
end

function pair_tuple(row)
    pair = row["L_pair"]
    return (Int(pair[1]), Int(pair[2]))
end

function systematic_budget_passes(audit)
    components = get(audit, "components", Dict{String, Any}())
    all(haskey(components, key) for key in (
        "chi", "finite_size", "interpolation", "mpo"
    )) || return false
    all(isfinite(Float64(components[key])) &&
        Float64(components[key]) >= 0 for key in keys(components)) ||
        return false
    total_error = Float64(get(audit, "total_error", NaN))
    isfinite(total_error) || return false
    component_total = sum(Float64(components[key]) for key in (
        "chi", "finite_size", "interpolation", "mpo"
    ))
    return total_error + 100eps(Float64) >= component_total
end

function evaluate_validation(summary, current_crossings, previous_crossings)
    per_sigma = Dict{String, Any}()
    pairs_complete = true
    bracket_refined = true
    adjacent_stable = true
    references_covered = true
    systematics_included = true

    for sigma in EXPECTED_SIGMAS
        current = baseline_crossings(current_crossings, sigma)
        found_pairs = Set(pair_tuple(row) for row in current)
        complete = all(pair in found_pairs for pair in EXPECTED_BASELINE_PAIRS)
        largest = crossing_for(current_crossings, sigma, 32)
        previous_largest = crossing_for(previous_crossings, sigma, 32)
        width = isnothing(largest) ? Inf :
            Float64(largest["Gamma_high"]) - Float64(largest["Gamma_low"])
        movement = isnothing(largest) || isnothing(previous_largest) ? Inf :
            abs(
                Float64(largest["Gamma_crossing"]) -
                Float64(previous_largest["Gamma_crossing"])
            )
        audit = summary["sigma_audits"][string(sigma)]
        reference_covered = Bool(get(
            audit, "covers_reference_interval", false
        ))
        systematics = systematic_budget_passes(audit)
        pairs_complete &= complete
        bracket_refined &= width <= BRACKET_TOLERANCE
        adjacent_stable &= movement < ADJACENT_DRIFT_TOLERANCE
        references_covered &= reference_covered
        systematics_included &= systematics
        per_sigma[string(sigma)] = Dict{String, Any}(
            "expected_pairs" => [collect(pair) for pair in EXPECTED_BASELINE_PAIRS],
            "found_pairs" => [collect(pair) for pair in sort!(collect(found_pairs))],
            "pairs_complete" => complete,
            "largest_crossing" => largest,
            "largest_bracket_width" => width,
            "largest_bracket_pass" => width <= BRACKET_TOLERANCE,
            "previous_largest_crossing" => previous_largest,
            "adjacent_round_movement" => movement,
            "adjacent_round_pass" => movement < ADJACENT_DRIFT_TOLERANCE,
            "reference_covered" => reference_covered,
            "systematic_error_budget_pass" => systematics,
        )
    end

    convergence = summary["convergence_audit"]
    variance_tolerance = Float64(get(
        convergence,
        "normalized_variance_tolerance",
        COMPUTE_VARIANCE_TOLERANCE,
    ))
    residual_tolerance = Float64(get(
        convergence,
        "residual_tolerance",
        COMPUTE_RESIDUAL_TOLERANCE,
    ))
    convergence_passes =
        Bool(get(convergence, "passes", false)) &&
        isempty(get(convergence, "failures", Any[])) &&
        variance_tolerance <= COMPUTE_VARIANCE_TOLERANCE &&
        residual_tolerance <= COMPUTE_RESIDUAL_TOLERANCE
    gates = Dict{String, Bool}(
        "baseline_pairs" => pairs_complete,
        "largest_crossing_bracket" => bracket_refined,
        "adjacent_round_drift" => adjacent_stable,
        "reference_intervals" => references_covered,
        "systematic_error_budget" => systematics_included,
        "nn_audit" => get(summary["nn_audit"], "status", "") == "pass",
        "authoritative_convergence" => convergence_passes,
        "adaptive_queue_empty" => Int(get(summary, "adaptive_cells", -1)) == 0,
    )
    status = all(values(gates)) ? FORMAL_STATUS : PRELIMINARY_STATUS
    return status, gates, per_sigma
end

function retry_params(failure)
    params = Dict{String, Any}(
        "model" => String(failure["model"]),
        "L" => Int(failure["L"]),
        "gamma" => Float64(failure["Gamma"]),
        "chi" => 128,
        "tolerance" => 1.0e-11,
        "maxiter" => 100,
        "excited" => Bool(get(failure, "excited", false)),
        "seed" => 86,
    )
    isnothing(get(failure, "sigma", nothing)) ||
        (params["sigma"] = Float64(failure["sigma"]))
    isnothing(get(failure, "poles", nothing)) ||
        (params["poles"] = Int(failure["poles"]))
    return params
end

function bracket_gammas(audit)
    crossing = audit["largest_crossing"]
    low = Float64(crossing["Gamma_low"])
    high = Float64(crossing["Gamma_high"])
    return sort!(unique([low, (low + high) / 2, high]))
end

function contingency_params(summary; chi, lengths, maxiter)
    params = Dict{String, Any}[]
    for sigma in EXPECTED_SIGMAS
        audit = summary["sigma_audits"][string(sigma)]
        for L in lengths, gamma in bracket_gammas(audit)
            push!(params, Dict{String, Any}(
                "model" => "long_range",
                "sigma" => sigma,
                "L" => L,
                "gamma" => gamma,
                "chi" => chi,
                "poles" => 16,
                "tolerance" => 1.0e-11,
                "maxiter" => maxiter,
                "excited" => false,
                "seed" => 86,
            ))
        end
    end
    return params
end

function reason_row(cell, tier, reason)
    params = cell["params"]
    return Dict{String, Any}(
        "cell_id" => cell["cell_id"],
        "tier" => tier,
        "reason" => reason,
        "resource_class" => cell["resource_class"],
        "model" => params["model"],
        "sigma" => get(params, "sigma", nothing),
        "L" => params["L"],
        "Gamma" => params["gamma"],
        "chi" => params["chi"],
        "poles" => get(params, "poles", nothing),
    )
end

function csv_value(value)
    text = isnothing(value) ? "" : string(value)
    if occursin(',', text) || occursin('"', text) ||
            occursin('\n', text) || occursin('\r', text)
        return "\"" * replace(text, "\"" => "\"\"") * "\""
    end
    return text
end

function write_reason_map(path, rows)
    columns = [
        "cell_id", "tier", "reason", "resource_class", "model",
        "sigma", "L", "Gamma", "chi", "poles",
    ]
    mkpath(dirname(path))
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in rows
            println(io, join((csv_value(row[column]) for column in columns), ","))
        end
    end
end

function build_recommendations(
        formal_directory,
        summary,
        adaptive_spec,
        compute_commit,
    )
    output_directory = joinpath(formal_directory, "next-recommendations")
    mkpath(output_directory)
    adaptive_copy = deepcopy(adaptive_spec)
    adaptive_copy["metadata"]["automatic_submission"] = false
    adaptive_copy["metadata"]["code_commit"] = compute_commit
    adaptive_copy["metadata"]["jobs_total"] = length(adaptive_copy["cells"])

    retry = make_run_spec(
        "issue-86-chi128-retry",
        "chi128-retry",
        [retry_params(failure) for failure in
            summary["convergence_audit"]["failures"]],
        compute_commit,
    )
    l128 = make_run_spec(
        "issue-86-l128-contingency",
        "l128-contingency",
        contingency_params(summary; chi = 128, lengths = (64, 128), maxiter = 120),
        compute_commit,
    )
    chi256 = make_run_spec(
        "issue-86-chi256-last-resort",
        "chi256-last-resort",
        contingency_params(summary; chi = 256, lengths = (64,), maxiter = 140),
        compute_commit,
    )
    specs = Dict(
        "remaining_adaptive" => adaptive_copy,
        "chi128_retry" => retry,
        "l128_contingency" => l128,
        "chi256_last_resort" => chi256,
    )
    filenames = Dict(
        "remaining_adaptive" => "remaining_adaptive_run_spec.json",
        "chi128_retry" => "chi128_retry_run_spec.json",
        "l128_contingency" => "l128_contingency_run_spec.json",
        "chi256_last_resort" => "chi256_last_resort_run_spec.json",
    )
    reasons = Dict{String, Any}[]
    reason_text = Dict(
        "remaining_adaptive" =>
            "refine a crossing bracket still wider than the formal gate",
        "chi128_retry" =>
            "upgrade a remaining variance or residual failure after strict chi=64 retry",
        "l128_contingency" =>
            "test finite-size drift at L=128 if the literature interval remains unresolved",
        "chi256_last_resort" =>
            "last-level bond-dimension check after lower-cost recommendations",
    )
    for tier in keys(specs)
        write_json_atomic(
            joinpath(output_directory, filenames[tier]), specs[tier]
        )
        append!(
            reasons,
            [
                reason_row(cell, tier, reason_text[tier])
                for cell in specs[tier]["cells"]
            ],
        )
    end
    sort!(reasons; by = row -> (row["tier"], row["cell_id"]))
    write_reason_map(joinpath(output_directory, "reason_map.csv"), reasons)

    resource_advice = Dict{String, Any}(
        "A" => Dict(
            "cpus" => 64, "memory_gb" => 240, "wall_hours" => 2,
            "workers" => 8,
        ),
        "B" => Dict(
            "cpus" => 64, "memory_gb" => 240, "wall_hours" => 4,
            "workers" => 4,
        ),
        "C" => Dict(
            "status" => "requires a fresh resource preview before submission",
        ),
        "D" => Dict(
            "status" => "last resort; requires a fresh resource preview before submission",
        ),
    )
    tiers = Dict(
        tier => Dict(
            "cells" => length(spec["cells"]),
            "run_spec" => joinpath("next-recommendations", filenames[tier]),
            "reason" => reason_text[tier],
        )
        for (tier, spec) in specs
    )
    return Dict{String, Any}(
        "automatic_submission" => false,
        "created_utc" => string(now(UTC)),
        "tiers" => tiers,
        "resource_advice" => resource_advice,
        "reason_map" => joinpath("next-recommendations", "reason_map.csv"),
    )
end

function sigma_result_rows(summary, validation)
    rows = Any[]
    for sigma in EXPECTED_SIGMAS
        audit = summary["sigma_audits"][string(sigma)]
        detail = validation["per_sigma"][string(sigma)]
        push!(rows, [
            string(sigma),
            string(audit["estimate"]),
            string(audit["reference"], " ± ", audit["reference_error"]),
            string(detail["largest_bracket_width"]),
            string(detail["adjacent_round_movement"]),
            detail["reference_covered"] ? "yes" : "no",
        ])
    end
    return rows
end

function build_run_document(summary, validation, recommendations)
    status = validation["status"]
    verdict = status == FORMAL_STATUS ? "pass" : "warn"
    return Dict{String, Any}(
        "schema_version" => 1,
        "title" => "Issue 86 Track B long-range TFIM critical-point validation",
        "issue" => Dict("number" => 86, "url" => ISSUE_URL),
        "track" => "MPS",
        "challenge" => "Track B: DMRG critical-point validation",
        "scope" => validation["scope"],
        "model" => Dict(
            "name" => "one-dimensional long-range transverse-field Ising model",
            "hamiltonian" =>
                "-sum_{i<j} J_L(|i-j|) Z_i Z_j - Gamma sum_i X_i",
            "boundary" => "periodic Hurwitz-zeta image sum",
        ),
        "method" => Dict(
            "name" => "finite-system DMRG crossing analysis",
            "tool" => "MPSKit.jl, MPSKitModels.jl, TensorKit.jl",
            "exact" => false,
            "settings" =>
                "SOE-MPO with pole and bond-dimension audits; ED and nearest-neighbour anchors",
            "note" =>
                "Ground-state correlation-ratio crossings were evaluated across paired sizes, then extrapolated with explicit finite-size, bond-dimension, pole-fit, and interpolation contributions.",
        ),
        "result" => Dict(
            "status" => status,
            "verdict" => verdict,
            "gates" => validation["gates"],
            "sigma_audits" => summary["sigma_audits"],
            "nn_audit" => summary["nn_audit"],
        ),
        "figures" => [
            Dict(
                "id" => "finite-size-sigma-1.75",
                "plots" => "Finite-size crossing drift for sigma=1.75",
                "results" => Dict(
                    "figure" => "finite_size_sigma1.75.png",
                    "match" => verdict,
                    "why" =>
                        "The uncertainty interval is compared with Gamma_c=1.5609±0.0003.",
                ),
            ),
            Dict(
                "id" => "finite-size-sigma-2.0",
                "plots" => "Finite-size crossing drift for sigma=2.0",
                "results" => Dict(
                    "figure" => "finite_size_sigma2.0.png",
                    "match" => verdict,
                    "why" =>
                        "The uncertainty interval is compared with Gamma_c=1.4208±0.0002.",
                ),
            ),
            Dict(
                "id" => "nearest-neighbour-anchor",
                "plots" => "Nearest-neighbour gap scaling",
                "results" => Dict(
                    "figure" => "nn_gap_scaling.png",
                    "match" =>
                        summary["nn_audit"]["status"] == "pass" ? "pass" : "warn",
                    "why" =>
                        "The exactly known nearest-neighbour critical point and z=1 scaling anchor the pipeline.",
                ),
            ),
        ],
        "recommendations" => recommendations,
        "provenance" => validation["provenance"],
    )
end

function build_report_document(run, summary, validation)
    status = validation["status"]
    formal = status == FORMAL_STATUS
    verdict_style = formal ? "good" : "warn"
    result_rows = sigma_result_rows(summary, validation)
    limitations = [
        "The largest computed long-range system is L=64.",
        "Long-range dynamic exponent z and gamma/nu were not measured.",
        "The sigma=1.6 and sigma=1.8 rows required for the full Track B boundary were not computed.",
        "Expansion recommendations are recorded without automatic submission.",
    ]
    return Dict{String, Any}(
        "title" => "Issue 86: Track B long-range TFIM critical points",
        "eyebrow" => "MPS Challenge · Track B validation floor",
        "url" => ISSUE_URL,
        "lede" => formal ?
            "Formal reproduction of the published critical-point validation floor at sigma=1.75 and 2.0." :
            "Validation-floor pipeline completed with a finite-size preliminary scientific status.",
        "sections" => [
            Dict(
                "title" => "Challenge",
                "blocks" => [
                    Dict(
                        "kind" => "text",
                        "text" =>
                            "Issue 86 asks where long-range interactions change the universality of the one-dimensional transverse-field Ising chain. This run targets the published critical-point validation floor for two long-range exponents.",
                    ),
                    Dict(
                        "kind" => "card",
                        "title" => "Significance",
                        "blocks" => [Dict(
                            "kind" => "text",
                            "text" =>
                                "Reliable critical fields anchor later exponent extraction. Reproducing them also tests the finite-size Hamiltonian convention, tensor-network approximation, convergence controls, and recoverable cluster workflow together.",
                        )],
                    ),
                    Dict(
                        "kind" => "kv",
                        "pairs" => [
                            ["Issue", "QuantumBFS/quantum.harness #86"],
                            ["Track", "B · DMRG critical-point validation"],
                            ["Published anchors", "sigma=1.75 and sigma=2.0"],
                            ["Computed sizes", "paired crossings through (32,64)"],
                        ],
                    ),
                ],
            ),
            Dict(
                "title" => "Approach",
                "blocks" => [
                    Dict(
                        "kind" => "badge",
                        "text" => "Controlled tensor-network approximation",
                        "style" => "neutral",
                    ),
                    Dict(
                        "kind" => "kv",
                        "pairs" => [
                            ["Method", run["method"]["name"]],
                            ["Tool", run["method"]["tool"]],
                            ["Interaction", "Hurwitz-zeta periodic image sum"],
                            ["MPO", "sum-of-exponentials representation"],
                        ],
                    ),
                    Dict(
                        "kind" => "equation",
                        "tex" =>
                            "H=-\\sum_{i<j}J_L(|i-j|)Z_iZ_j-\\Gamma\\sum_iX_i",
                    ),
                    Dict(
                        "kind" => "text",
                        "text" =>
                            "The workflow combines ED and nearest-neighbour anchors, finite-size correlation-ratio crossings, strict convergence retries, and explicit chi, pole, interpolation, and finite-size uncertainty components. Each Slurm unit writes an independently recoverable manifest.",
                    ),
                    Dict(
                        "kind" => "table",
                        "columns" => ["Stage", "Purpose", "Maximum scale"],
                        "rows" => [
                            ["Stage 1", "anchors and initial grid", "L=64"],
                            ["Stage 2", "crossing and systematic scans", "L=64"],
                            ["L16 correction", "complete all four size pairs", "L=16"],
                            ["Follow-up", "adaptive points and strict retries", "chi=128"],
                        ],
                    ),
                ],
            ),
            Dict(
                "title" => "Results",
                "blocks" => [
                    Dict(
                        "kind" => "verdict",
                        "status" => verdict_style,
                        "label" => status,
                        "why" =>
                            "The label follows the recorded bracket, drift, reference, uncertainty, NN-anchor, convergence, and adaptive-queue gates.",
                    ),
                    Dict(
                        "kind" => "table",
                        "columns" => [
                            "sigma", "estimate", "published Gamma_c",
                            "largest bracket", "v1→v2 movement",
                            "reference covered",
                        ],
                        "rows" => result_rows,
                        "numeric" => [true, true, true, true, true, false],
                    ),
                    Dict(
                        "kind" => "figures",
                        "items" => [
                            Dict(
                                "src" => "finite_size_sigma1.75.png",
                                "caption" =>
                                    "Finite-size crossing drift for sigma=1.75, with the published critical field shown as the comparison anchor.",
                            ),
                            Dict(
                                "src" => "finite_size_sigma2.0.png",
                                "caption" =>
                                    "Finite-size crossing drift for sigma=2.0, including the full and smallest-size-removed fits.",
                            ),
                        ],
                    ),
                    Dict(
                        "kind" => "figures",
                        "items" => [Dict(
                            "src" => "nn_gap_scaling.png",
                            "caption" =>
                                "Nearest-neighbour gap scaling audit. Agreement with Gamma_c=1 and z=1 validates the analysis route against the exactly known limit.",
                        )],
                    ),
                    Dict(
                        "kind" => "list",
                        "title" => "Declared scope limits",
                        "items" => limitations,
                    ),
                ],
            ),
            Dict(
                "title" => "Highlight",
                "blocks" => [
                    Dict(
                        "kind" => "card",
                        "title" => "What's innovative",
                        "blocks" => [Dict(
                            "kind" => "text",
                            "text" =>
                                "The calculation keeps the finite periodic interaction convention explicit through a Hurwitz-zeta image sum while compressing it into an audited sum-of-exponentials MPO.",
                        )],
                    ),
                    Dict(
                        "kind" => "card",
                        "title" => "Significance of output",
                        "blocks" => [Dict(
                            "kind" => "text",
                            "text" =>
                                "Two published long-range critical fields, the ED checks, and the nearest-neighbour anchor are carried through one quality-aware analysis with visible uncertainty components.",
                        )],
                    ),
                    Dict(
                        "kind" => "card",
                        "title" => "Broader impact",
                        "blocks" => [Dict(
                            "kind" => "text",
                            "text" =>
                                "Per-unit manifests and one-time same-spec recovery make large tensor-network scans auditable and resumable. The remaining z, gamma/nu, sigma, and scale extensions are isolated as explicit recommendations.",
                        )],
                    ),
                ],
            ),
        ],
    )
end

function finalize_track_b(
        formal_directory,
        previous_directory;
        compute_commit,
        analyzer_sha256,
    )
    summary = JSON.parsefile(joinpath(formal_directory, "formal_summary.json"))
    current_crossings = JSON.parsefile(
        joinpath(formal_directory, "crossings.json")
    )
    previous_crossings = JSON.parsefile(
        joinpath(previous_directory, "crossings.json")
    )
    adaptive_spec = JSON.parsefile(
        joinpath(formal_directory, "adaptive_run_spec.json")
    )
    status, gates, per_sigma = evaluate_validation(
        summary, current_crossings, previous_crossings
    )
    validation = Dict{String, Any}(
        "status" => status,
        "created_utc" => string(now(UTC)),
        "thresholds" => Dict(
            "largest_crossing_bracket" => BRACKET_TOLERANCE,
            "adjacent_round_drift" => ADJACENT_DRIFT_TOLERANCE,
            "normalized_variance" => COMPUTE_VARIANCE_TOLERANCE,
            "residual" => COMPUTE_RESIDUAL_TOLERANCE,
        ),
        "gates" => gates,
        "per_sigma" => per_sigma,
        "scope" => Dict(
            "claim" => "Track B validation-floor reproduction",
            "full_track_b_complete" => false,
            "computed_sigmas" => collect(EXPECTED_SIGMAS),
            "maximum_long_range_size" => 64,
            "not_measured" => [
                "dynamic exponent z for the long-range model",
                "gamma/nu",
                "sigma=1.6",
                "sigma=1.8",
            ],
        ),
        "provenance" => Dict(
            "compute_commit" => compute_commit,
            "analyzer_sha256" => analyzer_sha256,
            "formal_directory" => basename(formal_directory),
            "previous_formal_directory" => basename(previous_directory),
        ),
    )
    recommendations = build_recommendations(
        formal_directory, summary, adaptive_spec, compute_commit
    )
    run = build_run_document(summary, validation, recommendations)
    report = build_report_document(run, summary, validation)
    write_json_atomic(
        joinpath(formal_directory, "validation_summary.json"), validation
    )
    write_json_atomic(
        joinpath(formal_directory, "next-recommendations.json"),
        recommendations,
    )
    write_json_atomic(joinpath(formal_directory, "run.json"), run)
    write_json_atomic(joinpath(formal_directory, "report.json"), report)
    return validation, recommendations, run, report
end

function main(args)
    length(args) == 4 || error(
        "usage: finalize_track_b.jl FORMAL_DIR PREVIOUS_FORMAL_DIR " *
        "COMPUTE_COMMIT ANALYZER_SHA256"
    )
    formal_directory = abspath(args[1])
    previous_directory = abspath(args[2])
    validation, recommendations, _, _ = finalize_track_b(
        formal_directory,
        previous_directory;
        compute_commit = args[3],
        analyzer_sha256 = args[4],
    )
    println("scientific status: $(validation["status"])")
    println(
        "recommendation cells: " *
        join(
            (
                "$tier=$(entry["cells"])"
                for (tier, entry) in sort!(collect(
                    recommendations["tiers"]
                ); by = first)
            ),
            ", ",
        )
    )
    flush(stdout)
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main(ARGS)
