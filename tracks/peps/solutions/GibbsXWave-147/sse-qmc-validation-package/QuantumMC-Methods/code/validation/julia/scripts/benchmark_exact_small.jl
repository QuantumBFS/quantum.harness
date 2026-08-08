#!/usr/bin/env julia

using Dates
using QuantumMCMethods
using Statistics

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
const TABLE_DIRECTORY =
    joinpath(REPOSITORY_ROOT, "results", "validation", "tables")
const RUN_DATE = Dates.format(Dates.today(), dateformat"yyyy-mm-dd")
const CSV_PATH = joinpath(TABLE_DIRECTORY, "tfim-sse-exact-small-$RUN_DATE.csv")
const REPORT_PATH = joinpath(TABLE_DIRECTORY, "tfim-sse-exact-small-$RUN_DATE.md")

const WARMUP = parse(Int, get(ENV, "QMC_BENCH_WARMUP", "5000"))
const SWEEPS = parse(Int, get(ENV, "QMC_BENCH_SWEEPS", "100000"))
const BIN_SIZE = parse(Int, get(ENV, "QMC_BENCH_BIN_SIZE", "500"))
const SEEDS = UInt64.(20260727:20260730)

struct ComparisonRow
    case_name::String
    J::Float64
    h::Float64
    beta::Float64
    observable::String
    reference::Float64
    estimate::Float64
    standard_error::Float64
    absolute_difference::Float64
    z_score::Float64
    pass_limit::Float64
    passed::Bool
    max_expansion_order::Int
    cutoff::Int
    cutoff_touched::Bool
end

function combined_estimate(results, selector)
    values = Float64[selector(result).value for result in results]
    within_error = sqrt(sum(selector(result).error^2 for result in results)) /
                   length(results)
    between_error =
        length(results) > 1 ? std(values) / sqrt(length(results)) : 0.0
    return mean(values), max(within_error, between_error)
end

function add_comparison!(rows, case_name, model, beta, observable,
                         reference, results, selector, absolute_tolerance)
    estimate, standard_error = combined_estimate(results, selector)
    difference = abs(estimate - reference)
    z_score = iszero(standard_error) ?
              (iszero(difference) ? 0.0 : Inf) :
              difference / standard_error
    pass_limit = max(5standard_error, absolute_tolerance)
    push!(
        rows,
        ComparisonRow(
            case_name,
            model.J,
            model.h,
            beta,
            observable,
            reference,
            estimate,
            standard_error,
            difference,
            z_score,
            pass_limit,
            difference <= pass_limit,
            maximum(result.max_expansion_order for result in results),
            maximum(result.cutoff for result in results),
            any(result.cutoff_touched for result in results),
        ),
    )
end

function benchmark_case!(rows, case_name, model, beta, reference)
    results = [
        run_sse(
            model,
            beta;
            warmup=WARMUP,
            sweeps=SWEEPS,
            bin_size=BIN_SIZE,
            seed,
            validate_every=1000,
        ) for seed in SEEDS
    ]

    add_comparison!(
        rows, case_name, model, beta, "u", reference.u, results,
        result -> result.energy, 5e-3,
    )
    add_comparison!(
        rows, case_name, model, beta, "c", reference.c, results,
        result -> result.heat_capacity, 1e-2,
    )
    add_comparison!(
        rows, case_name, model, beta, "mx", reference.mx, results,
        result -> result.transverse_magnetization, 5e-3,
    )
    return nothing
end

function git_value(args...)
    try
        return readchomp(`git -C $REPOSITORY_ROOT $args`)
    catch
        return "unavailable"
    end
end

function write_csv(rows)
    open(CSV_PATH, "w") do io
        println(
            io,
            "stage,case,J,h,beta,observable,reference,estimate,standard_error," *
            "absolute_difference,z_score,pass_limit,passed," *
            "max_expansion_order,cutoff,cutoff_touched",
        )
        for row in rows
            println(
                io,
                join(
                    (
                        "SSE_VALIDATION",
                        row.case_name,
                        row.J,
                        row.h,
                        row.beta,
                        row.observable,
                        row.reference,
                        row.estimate,
                        row.standard_error,
                        row.absolute_difference,
                        row.z_score,
                        row.pass_limit,
                        row.passed,
                        row.max_expansion_order,
                        row.cutoff,
                        row.cutoff_touched,
                    ),
                    ",",
                ),
            )
        end
    end
end

compact(value) = string(round(value; sigdigits=7))

function write_report(rows, elapsed_seconds)
    passed = count(row -> row.passed && !row.cutoff_touched, rows)
    open(REPORT_PATH, "w") do io
        println(io, "# TFIM SSE exact-small benchmark — $RUN_DATE")
        println(io)
        println(io, "Stage: `SSE_VALIDATION`")
        println(io)
        println(io, "Status: [Tested] $passed/$(length(rows)) scalar comparisons passed")
        println(io)
        println(io, "## Run metadata")
        println(io)
        println(io, "- timestamp: `$(Dates.now())`")
        println(io, "- Julia: `$(VERSION)`")
        println(io, "- CPU: `$(Sys.CPU_NAME)`")
        println(io, "- threads: `$(Threads.nthreads())`")
        println(io, "- source HEAD: `$(git_value("rev-parse", "HEAD"))`")
        println(io, "- source state: `$(isempty(git_value("status", "--porcelain")) ? "clean" : "dirty")`")
        println(io, "- seeds: `$(join(SEEDS, ", "))`")
        println(io, "- warmup sweeps per seed: `$WARMUP`")
        println(io, "- measurement sweeps per seed: `$SWEEPS`")
        println(io, "- bin size: `$BIN_SIZE`")
        println(io, "- elapsed seconds: `$(round(elapsed_seconds; digits=3))`")
        println(
            io,
            "- command: `JULIA_PKG_OFFLINE=true JULIA_DEPOT_PATH=/tmp/hq-julia-depot:/home/frank_ubuntu/.julia julia --project=code/validation/julia code/validation/julia/scripts/benchmark_exact_small.jl`",
        )
        println(io)
        println(io, "## Comparisons")
        println(io)
        println(io, "| case | J | h | β | observable | reference | SSE | SE | |Δ|/SE | pass |")
        println(io, "|---|---:|---:|---:|---|---:|---:|---:|---:|:---:|")
        for row in rows
            println(
                io,
                "| $(row.case_name) | $(row.J) | $(row.h) | $(row.beta) | " *
                "$(row.observable) | " *
                "$(compact(row.reference)) | $(compact(row.estimate)) | " *
                "$(compact(row.standard_error)) | $(compact(row.z_score)) | " *
                "$(row.passed && !row.cutoff_touched ? "yes" : "no") |",
            )
        end
        println(io)
        println(io, "Pass rule: `|SSE-reference| ≤ max(5 SE, ε_abs)`, with")
        println(io, "`ε_abs=0.005` for `u,mx` and `ε_abs=0.01` for `c`; any")
        println(io, "measurement-time cutoff touch is an automatic failure.")
        println(io)
        println(io, "Machine-readable values: [`$(basename(CSV_PATH))`]($(basename(CSV_PATH))).")
    end
end

function main()
    mkpath(TABLE_DIRECTORY)
    rows = ComparisonRow[]
    elapsed_seconds = @elapsed begin
        for h in (0.7, 2.5, 3.5), beta in (0.1, 0.5, 1.0)
            model = SquareLatticeTFIM(2, 2; J=1.0, h)
            reference = exact_thermal_observables(model, beta)
            benchmark_case!(rows, "2x2-ed", model, beta, reference)
        end

        for beta in (0.1, 0.7, 1.0)
            model = SquareLatticeTFIM(2, 2; J=0.0, h=1.3)
            reference =
                independent_spin_observables(nsites(model), model.h, beta)
            benchmark_case!(rows, "J0-analytic", model, beta, reference)
        end
    end

    write_csv(rows)
    write_report(rows, elapsed_seconds)
    failed = filter(row -> !row.passed || row.cutoff_touched, rows)
    println("wrote $CSV_PATH")
    println("wrote $REPORT_PATH")
    println("passed $(length(rows) - length(failed))/$(length(rows)) comparisons")
    isempty(failed) || error("exact-small benchmark failed")
end

main()
