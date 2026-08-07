include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK, Dates

cell_id=get(ENV,"NN_CELL_ID","cell-local")
L=parse(Int,get(ENV,"NN_L","64"))
seed=parse(Int,get(ENV,"NN_SEED","73001"))
beta=parse(Float64,get(ENV,"NN_BETA",string(log(1+sqrt(2))/2)))
therm=parse(Int,get(ENV,"NN_THERM","1000"))
meas=parse(Int,get(ENV,"NN_MEAS","10000"))
blocks=parse(Int,get(ENV,"NN_BLOCKS","50"))
progress_every=max(1,meas÷20)
root=get(ENV,"RUN_ROOT",joinpath(@__DIR__,"..","results","nn_large_20260730"))
cell=joinpath(root,"cells",cell_id)
mkpath(cell)

println("START cell=$cell_id model=nearest_neighbor L=$L beta=$beta seed=$seed therm=$therm meas=$meas blocks=$blocks")
flush(stdout)
r=run_nn_chain(L=L,beta=beta,seed=seed,therm=therm,meas=meas,
               blocks=blocks,progress_every=progress_every,return_blocks=true)

open(joinpath(cell,"summary.csv"),"w") do io
    println(io,join(keys(r.summary),","))
    println(io,join(values(r.summary),","))
end
open(joinpath(cell,"blocks.csv"),"w") do io
    println(io,"block,m2,m4,Qm,chi,Rp,C1")
    for i in eachindex(r.block_m2)
        println(io,"$i,$(r.block_m2[i]),$(r.block_m4[i]),$(r.block_qm[i]),$(r.block_chi[i]),$(r.block_rp[i]),$(r.block_c1[i])")
    end
end
open(joinpath(cell,"metadata.txt"),"w") do io
    println(io,"timestamp=$(now())")
    println(io,"hostname=$(gethostname())")
    println(io,"julia=$(VERSION)")
    println(io,"slurm_job=$(get(ENV,"SLURM_JOB_ID","local"))")
    println(io,"slurm_array_task=$(get(ENV,"SLURM_ARRAY_TASK_ID","local"))")
    println(io,"cell=$cell_id")
    println(io,"model=nearest_neighbor")
    println(io,"hamiltonian=H=-sum_<ij> s_i s_j")
    println(io,"coupling_J=1")
    println(io,"boundary=periodic_square_torus")
    println(io,"beta=$beta")
    println(io,"L=$L")
    println(io,"seed=$seed")
    println(io,"thermalization_sweeps=$therm")
    println(io,"measurement_sweeps=$meas")
    println(io,"blocks=$blocks")
end
println("SUCCESS cell=$cell_id L=$L seed=$seed Qm=$(r.summary.Qm) Rp=$(r.summary.Rp) chi=$(r.summary.chi) tau_m2=$(r.summary.tau_m2) runtime_s=$(r.summary.runtime_s)")
flush(stdout)
