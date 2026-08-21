using Carlo
using Carlo.JobTools
using Carlo.ResultTools
using DataFrames
using JSON
import StochasticSeriesExpansion as SSE

include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
using .Challenge148

const RUN_ROOT = joinpath(@__DIR__, "..", "runs", "c1_validation")

function validation_cases()
    return [
        (lattice = :triangle, L = 3, h = 4.76811, seed = 148001),
        (lattice = :honeycomb, L = 2, h = 2.13250, seed = 148002),
    ]
end

function write_ed_reference(cases)
    records = Dict{String,Any}[]
    for case in cases
        geometry = lattice_geometry(case.lattice, case.L)
        beta = beta_for_aspect(case.h, case.L; c = 1.0)
        result = ed_thermal_observables(geometry; J = 1.0, h = case.h, beta)
        push!(
            records,
            Dict(
                "lattice" => String(case.lattice),
                "L" => case.L,
                "N" => geometry.nsites,
                "J" => 1.0,
                "h_input" => case.h,
                "h_simulated" => abs(case.h),
                "c" => 1.0,
                "beta" => beta,
                "T" => 1 / beta,
                "energy_per_site" => result.energy_per_site,
                "m2" => result.m2,
                "m4" => result.m4,
                "binder_ratio" => result.binder_ratio,
            ),
        )
    end
    open(joinpath(RUN_ROOT, "ed_reference.json"), "w") do io
        JSON.print(io, records, 2)
    end
end

function make_job(cases)
    tm = TaskMaker()
    tm.sweeps = 10_000
    tm.thermalization = 2_000
    tm.binsize = 100
    tm.model = TFIMModel
    tm.J = 1.0
    tm.c = 1.0
    tm.measure = [:magnetization]

    for case in cases
        tm.lattice = case.lattice
        tm.L = case.L
        tm.h = case.h
        tm.T = abs(case.h) / case.L
        tm.seed = case.seed
        task(tm)
    end

    return JobInfo(
        joinpath(RUN_ROOT, "qmc"),
        SSE.MC;
        run_time = "00:10:00",
        checkpoint_time = "02:00",
        tasks = make_tasks(tm),
    )
end

function main()
    mkpath(RUN_ROOT)
    cases = validation_cases()
    write_ed_reference(cases)
    job = make_job(cases)
    Carlo.start(Carlo.SingleScheduler, job)
    results_path = joinpath(RUN_ROOT, "qmc.results.json")
    results = DataFrame(ResultTools.dataframe(results_path))
    show(results; allcols = true)
    println()
    println("ED reference: ", joinpath(RUN_ROOT, "ed_reference.json"))
    println("QMC results:  ", results_path)
end

main()
