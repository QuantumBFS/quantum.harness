include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK, Dates

id=parse(Int,get(ENV,"SLURM_ARRAY_TASK_ID",get(ENV,"CELL_ID","1")))
sigmas=(1.75,1.875,2.0,2.5)
Ls=(768,1024,1536,2048)
seeds=(31001,42002)
bcs=Dict(1.75=>0.329136,1.875=>0.336985,2.0=>0.344439,2.5=>0.369446)
meas_by_L=Dict(768=>100_000,1024=>75_000,1536=>35_000,2048=>20_000)

if id <= 32
    idx=id-1
    seed=seeds[idx%2+1]+id; idx÷=2
    L=Ls[idx%4+1]; idx÷=4
    sigma=sigmas[idx%4+1]
    beta=bcs[sigma]
    role="critical"
else
    # 16 narrow-window cells: sigma=(1.875,2.0), L=(1024,2048),
    # offset=(-0.0005,+0.0005), two seeds.
    idx=id-33
    seed=seeds[idx%2+1]+id; idx÷=2
    off=(-0.0005,0.0005)[idx%2+1]; idx÷=2
    L=(1024,2048)[idx%2+1]; idx÷=2
    sigma=(1.875,2.0)[idx%2+1]
    beta=bcs[sigma]+off
    role="crossing"
end

therm=parse(Int,get(ENV,"THERM_SWEEPS","5000"))
meas=parse(Int,get(ENV,"MEAS_SWEEPS",string(meas_by_L[L])))
root=get(ENV,"RUN_ROOT",joinpath(@__DIR__,"..","results","track_a_large_20260728"))
cell=joinpath(root,"cells",lpad(id,3,'0')); mkpath(cell)
r=run_chain(L=L,sigma=sigma,beta=beta,seed=seed,therm=therm,meas=meas,return_blocks=true)

open(joinpath(cell,"summary.csv"),"w") do io
    println(io,"role,"*join(keys(r.summary),","))
    println(io,role*","*join(values(r.summary),","))
end
open(joinpath(cell,"blocks.csv"),"w") do io
    println(io,"block,m2,Rp,C1")
    for i in eachindex(r.block_m2)
        println(io,"$i,$(r.block_m2[i]),$(r.block_rp[i]),$(r.block_c1[i])")
    end
end
open(joinpath(cell,"metadata.txt"),"w") do io
    jobid=get(ENV,"SLURM_JOB_ID","local")
    println(io,"timestamp=$(now())"); println(io,"hostname=$(gethostname())")
    println(io,"julia=$(VERSION)"); println(io,"slurm_job=$jobid")
    println(io,"cell=$id"); println(io,"role=$role")
end
println("SUCCESS cell=$id role=$role L=$L sigma=$sigma beta=$beta seed=$seed meas=$meas Rp=$(r.summary.Rp) Qm=$(r.summary.Qm)")
flush(stdout)
