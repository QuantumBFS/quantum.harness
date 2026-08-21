using JSON
using Statistics

include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
using .Challenge148

const RUN_ROOT = joinpath(@__DIR__, "..", "runs", "c1_cwa_pilot")
const THERMALIZATION = 5_000
const SWEEPS = 50_000
const BASE_BINSIZE = 20
const CHAINS = 4

estimate_dict(estimate) = Dict(
    "mean" => estimate.mean,
    "stderr" => estimate.stderr,
    "bins" => estimate.bins,
)

function write_json(path, value)
    open(path, "w") do io
        JSON.print(io, value, 2)
    end
end

function run_case(lattice::Symbol, h::Float64, chain::Int)
    L = 8
    geometry = lattice_geometry(lattice, L)
    beta = beta_for_aspect(h, L; c = 1.0)
    seed = 148_400 + 10chain + (lattice === :triangle ? 1 : 2)
    elapsed = @elapsed result = run_cwa(
        geometry;
        J = 1.0,
        h,
        beta,
        thermalization = THERMALIZATION,
        sweeps = SWEEPS,
        binsize = BASE_BINSIZE,
        seed,
    )

    record = Dict(
        "algorithm" => "continuous-time Swendsen-Wang worldline cluster",
        "lattice" => String(lattice),
        "L" => L,
        "N" => geometry.nsites,
        "J" => 1.0,
        "h_input" => h,
        "h_simulated" => abs(h),
        "c" => 1.0,
        "beta" => beta,
        "T" => 1 / beta,
        "chain" => chain,
        "seed" => seed,
        "thermalization" => THERMALIZATION,
        "sweeps" => SWEEPS,
        "base_binsize" => BASE_BINSIZE,
        "elapsed_seconds" => elapsed,
        "estimates" => Dict(
            "energy_per_site" => estimate_dict(result.energy_per_site),
            "m_time2" => estimate_dict(result.m_time2),
            "m_time4" => estimate_dict(result.m_time4),
            "binder_time" => estimate_dict(result.binder_time),
            "m_equal2" => estimate_dict(result.m_equal2),
            "m_equal4" => estimate_dict(result.m_equal4),
            "binder_equal" => estimate_dict(result.binder_equal),
            "mean_cuts" => estimate_dict(result.mean_cuts),
        ),
        "bins" => Dict(String(name) => values for (name, values) in pairs(result.bins)),
    )
    path = joinpath(RUN_ROOT, "$(lattice)_L8_chain$(chain).json")
    write_json(path, record)
    println(
        (
            lattice,
            chain,
            elapsed_seconds = elapsed,
            binder_time = result.binder_time.mean,
            binder_time_error = result.binder_time.stderr,
        ),
    )
    return result, record
end

function summarize_lattice(lattice::Symbol, chain_results)
    energy = reduce(vcat, [result.bins.energy_per_site for result in chain_results])
    m2 = reduce(vcat, [result.bins.m_time2 for result in chain_results])
    m4 = reduce(vcat, [result.bins.m_time4 for result in chain_results])
    stability = Dict{String,Any}()
    for factor in (1, 5, 10, 25)
        rebinned_energy = rebin_series(energy, factor)
        rebinned_m2 = rebin_series(m2, factor)
        rebinned_m4 = rebin_series(m4, factor)
        stability[string(BASE_BINSIZE * factor)] = Dict(
            "energy_per_site" => estimate_dict(
                Challenge148.binned_estimate(rebinned_energy),
            ),
            "binder_time" => estimate_dict(binder_from_bins(rebinned_m2, rebinned_m4)),
        )
    end
    return Dict(
        "lattice" => String(lattice),
        "L" => 8,
        "chains" => CHAINS,
        "total_measurement_sweeps" => CHAINS * SWEEPS,
        "base_binsize" => BASE_BINSIZE,
        "chain_binder_time" => [estimate_dict(result.binder_time) for result in chain_results],
        "binning_stability" => stability,
    )
end

function main()
    mkpath(RUN_ROOT)
    all_records = Dict{Symbol,Vector{Any}}(:triangle => Any[], :honeycomb => Any[])
    all_results = Dict{Symbol,Vector{Any}}(:triangle => Any[], :honeycomb => Any[])
    for chain in 1:CHAINS
        for (lattice, h) in ((:triangle, 4.76811), (:honeycomb, 2.13250))
            result, record = run_case(lattice, h, chain)
            push!(all_results[lattice], result)
            push!(all_records[lattice], record)
        end
    end

    summary = Dict(
        "julia_version" => string(VERSION),
        "triangle" => summarize_lattice(:triangle, all_results[:triangle]),
        "honeycomb" => summarize_lattice(:honeycomb, all_results[:honeycomb]),
    )
    write_json(joinpath(RUN_ROOT, "summary.json"), summary)
    println("summary: ", joinpath(RUN_ROOT, "summary.json"))
end

main()
