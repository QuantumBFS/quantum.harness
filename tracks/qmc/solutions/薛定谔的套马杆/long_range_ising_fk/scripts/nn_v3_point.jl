include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK
using Printf

length(ARGS) == 5 || error("usage: nn_v3_point.jl L seed therm meas output_dir")
L=parse(Int,ARGS[1])
seed=parse(Int,ARGS[2])
therm=parse(Int,ARGS[3])
meas=parse(Int,ARGS[4])
outdir=ARGS[5]
mkpath(outdir)

r=run_nn_chain(L=L,seed=seed,therm=therm,meas=meas,nb=100,return_blocks=true)
s=r.summary

open(joinpath(outdir,"summary.csv"),"w") do io
    println(io,"L,beta,seed,therm,meas,mean_m2,mean_m4,Qm,chi,R0,R2,Rp,mean_C1,blocks,runtime_s")
    println(io,join((s.L,s.beta,s.seed,s.therm,s.meas,s.mean_m2,s.mean_m4,
                     s.Qm,s.chi,s.R0,s.R2,s.Rp,s.mean_C1,s.blocks,s.runtime_s),","))
end
open(joinpath(outdir,"blocks.csv"),"w") do io
    println(io,"block,m2,m4,R0,R2,C1")
    for i in eachindex(r.block_m2)
        println(io,join((i,r.block_m2[i],r.block_m4[i],r.block_r0[i],
                         r.block_r2[i],r.block_c1[i]),","))
    end
end
open(joinpath(outdir,"metadata.txt"),"w") do io
    println(io,"status=success")
    println(io,"kernel=exact_nearest_neighbor_fk")
    println(io,"boundary=periodic")
    println(io,"J=1")
    println(io,"beta=$(s.beta)")
    println(io,"julia=$(VERSION)")
end
@printf("NN V3 L=%d seed=%d Qm=%.8f Rp=%.8f chi=%.8f runtime_s=%.2f\n",
        L,seed,s.Qm,s.Rp,s.chi,s.runtime_s)
flush(stdout)
