# depth admission for C10 (v4 §4): ED substitution of the n=10 tower at the
# largest ED-feasible size N=14 (Lemma-1 requires n <= N-1). Every link
# residual checked; structural counts recorded.
using Printf, Dates
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))
include(joinpath(@__DIR__, "src", "vcheck.jl"))
As = load_D4()
ok, msgs = vcheck_physical(14, String[], As, 10)
open(joinpath(@__DIR__, "results", "depth_admit_n10.txt"), "w") do io
    println(io, "depth_admit n=10 @N=14 ", ok ? "PASS" : "FAIL", " $(now())")
    foreach(l -> println(io, l), msgs)
end
foreach(println, msgs)
println(ok ? "ADMIT n=10 PASS" : "ADMIT n=10 FAIL")
exit(ok ? 0 : 1)
