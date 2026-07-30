include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK
for L in (8,16,32)
    r=run_chain(L=L,sigma=50.0,beta=log(1+sqrt(2))/2,seed=700+L,
                therm=2000,meas=20000)
    println(r); flush(stdout)
end
