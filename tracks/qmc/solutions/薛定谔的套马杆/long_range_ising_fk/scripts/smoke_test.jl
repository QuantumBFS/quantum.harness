include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK, Printf
out=length(ARGS)>0 ? ARGS[1] : joinpath(@__DIR__,"..","results","smoke.csv")
mkpath(dirname(out))
open(out,"w") do io
    println(io,"L,sigma,beta,seed,therm,meas,mean_abs_m,mean_m2,mean_m4,Qm,chi,R0,R2,Rp,mean_C1,se_m2,se_Rp,tau_m2,blocks,runtime_s,sumJ")
    for L in (8,16,32), beta in (0.326985,0.336985,0.346985), seed in (101,202)
        r=run_chain(L=L,sigma=1.875,beta=beta,seed=seed,therm=1000,meas=5000)
        println(io,join(values(r),","))
        @printf("L=%d beta=%.6f seed=%d Qm=%.5f Rp=%.5f chi=%.3f time=%.2fs\n",L,beta,seed,r.Qm,r.Rp,r.chi,r.runtime_s)
        flush(stdout); flush(io)
    end
end
