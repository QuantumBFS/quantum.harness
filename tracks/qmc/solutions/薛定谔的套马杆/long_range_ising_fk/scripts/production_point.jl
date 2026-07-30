include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK, Dates
id=parse(Int,get(ENV,"SLURM_ARRAY_TASK_ID",get(ENV,"CELL_ID","1")))
sigmas=(1.75,1.875,2.0,2.5); Ls=(64,128,256,512)
offsets=(-0.002,0.0,0.002); seeds=(11001,22002)
bcs=Dict(1.75=>0.329136,1.875=>0.336985,2.0=>0.344439,2.5=>0.369446)
idx=id-1; seed=seeds[idx%2+1]+id; idx÷=2
off=offsets[idx%3+1]; idx÷=3
L=Ls[idx%4+1]; idx÷=4
sigma=sigmas[idx%4+1]; beta=bcs[sigma]+off
root=get(ENV,"RUN_ROOT",joinpath(@__DIR__,"..","results","track_a_20260727"))
cell=joinpath(root,"cells",lpad(id,3,'0')); mkpath(cell)
therm=parse(Int,get(ENV,"THERM_SWEEPS","10000"))
meas=parse(Int,get(ENV,"MEAS_SWEEPS","100000"))
r=run_chain(L=L,sigma=sigma,beta=beta,seed=seed,therm=therm,meas=meas,return_blocks=true)
open(joinpath(cell,"summary.csv"),"w") do io
    println(io,join(keys(r.summary),","))
    println(io,join(values(r.summary),","))
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
end
println("SUCCESS cell=$id L=$L sigma=$sigma beta=$beta seed=$seed Rp=$(r.summary.Rp) Qm=$(r.summary.Qm)")
flush(stdout)
