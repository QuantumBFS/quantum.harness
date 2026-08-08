#!/usr/bin/env julia

using Carlo
using Carlo.JobTools
using QuantumMCMethods

parse_values(name, default) =
    parse.(Float64, split(get(ENV, name, default), ","))

task_maker = TaskMaker()
task_maker.sweeps = parse(Int, get(ENV, "QMC_SWEEPS", "100000"))
task_maker.thermalization =
    parse(Int, get(ENV, "QMC_THERMALIZATION", "20000"))
task_maker.binsize = parse(Int, get(ENV, "QMC_BINSIZE", "500"))
task_maker.seed = parse(Int, get(ENV, "QMC_SEED", "20260727"))
task_maker.Lx = parse(Int, get(ENV, "QMC_LX", "4"))
task_maker.Ly = parse(Int, get(ENV, "QMC_LY", string(task_maker.Lx)))
task_maker.J = parse(Float64, get(ENV, "QMC_J", "1.0"))
task_maker.validate_every =
    parse(Int, get(ENV, "QMC_VALIDATE_EVERY", "1000"))

for h in parse_values("QMC_H_VALUES", "2.5,3.0,3.5"),
    beta in parse_values("QMC_BETA_VALUES", "0.1,0.5,1.0")
    task(task_maker; h, beta)
end

job = JobInfo(
    get(ENV, "QMC_JOB_PATH", @__FILE__),
    TFIMSSECarlo;
    checkpoint_time=get(ENV, "QMC_CHECKPOINT_TIME", "30:00"),
    run_time=get(ENV, "QMC_RUN_TIME", "15:00"),
    tasks=make_tasks(task_maker),
)

start(job, ARGS)
