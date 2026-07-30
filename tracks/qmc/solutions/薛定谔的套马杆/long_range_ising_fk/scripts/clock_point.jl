include("../src/LongRangeIsingClock.jl")
using .LongRangeIsingClock, Dates

id = parse(Int, get(ENV, "SLURM_ARRAY_TASK_ID", get(ENV, "CELL_ID", "1")))
sigmas = (1.875, 2.0)
Ls = (64, 128, 256, 512)
seeds = (51001, 62002)
bcs = Dict(1.875=>0.336985, 2.0=>0.344439)
therm_by_L = Dict(64=>50_000, 128=>100_000, 256=>200_000, 512=>300_000)
meas_by_L = Dict(64=>1_000_000, 128=>1_000_000,
                 256=>1_000_000, 512=>1_000_000)

idx = id-1
seed = seeds[idx%2+1] + id
idx ÷= 2
L = Ls[idx%4+1]
idx ÷= 4
sigma = sigmas[idx%2+1]
beta = bcs[sigma]
therm = parse(Int, get(ENV, "THERM_SWEEPS", string(therm_by_L[L])))
meas = parse(Int, get(ENV, "MEAS_SWEEPS", string(meas_by_L[L])))
sample_every = parse(Int, get(ENV, "SAMPLE_EVERY", "1"))
root = get(ENV, "RUN_ROOT",
           joinpath(@__DIR__, "..", "results", "clock_crosscheck_20260729"))
cell = joinpath(root, "cells", lpad(id, 3, '0'))
mkpath(cell)

validation = validate_clock()
r = run_clock(L=L, sigma=sigma, beta=beta, seed=seed, therm=therm,
              meas=meas, sample_every=sample_every)

open(joinpath(cell, "summary.csv"), "w") do io
    println(io, join(keys(r.summary), ","))
    println(io, join(values(r.summary), ","))
end
open(joinpath(cell, "blocks.csv"), "w") do io
    println(io, "block,m2,m4")
    for i in eachindex(r.block_m2)
        println(io, "$i,$(r.block_m2[i]),$(r.block_m4[i])")
    end
end
open(joinpath(cell, "metadata.txt"), "w") do io
    println(io, "timestamp=$(now())")
    println(io, "hostname=$(gethostname())")
    println(io, "julia=$(VERSION)")
    println(io, "slurm_job=$(get(ENV, "SLURM_JOB_ID", "local"))")
    println(io, "cell=$id")
    println(io, "clock_acceptance_test=$(validation.clock_acceptance)")
    println(io, "direct_acceptance_test=$(validation.direct_acceptance)")
    println(io, "validation_tolerance=$(validation.tolerance)")
end
println("SUCCESS cell=$id L=$L sigma=$sigma Qm=$(r.summary.Qm) chi=$(r.summary.chi) tau=$(r.summary.tau_m2)")
