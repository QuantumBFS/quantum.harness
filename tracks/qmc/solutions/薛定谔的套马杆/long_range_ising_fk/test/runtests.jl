using Test
include("../src/LongRangeIsingFK.jl")
using .LongRangeIsingFK

@testset "geometry and normalization" begin
    @test minimum_delta(7,8)==-1
    @test minimum_delta(4,8)==-4
    for L in (4,8,16), s in (1.75,1.875,2.0)
        @test coupling_sum(Geometry(L,s)) ≈ 4 atol=2e-14
    end
end

@testset "winding union-find" begin
    L=4
    u=WindingUF(L^2); add_edge!(u,1,2,1,0,L); @test wrapping(u)[1]
    u=WindingUF(L^2)
    for x in 0:L-1; add_edge!(u,x+1,mod(x+1,L)+1,1,0,L); end
    @test wrapping(u)[3] && !wrapping(u)[4]
    u=WindingUF(L^2)
    for y in 0:L-1; add_edge!(u,1+y*L,1+mod(y+1,L)*L,0,1,L); end
    @test !wrapping(u)[3] && wrapping(u)[4]
    u=WindingUF(L^2)
    for x in 0:L-1; add_edge!(u,x+1,mod(x+1,L)+1,1,0,L); end
    for y in 0:L-1; add_edge!(u,1+y*L,1+mod(y+1,L)*L,0,1,L); end
    @test wrapping(u)[2]
    u=WindingUF(L^2); add_edge!(u,4,1,1,0,L); @test wrapping(u)[1]
    u=WindingUF(L^2)
    add_edge!(u,1,3,-2,0,L); add_edge!(u,3,1,-2,0,L)
    @test wrapping(u)[3]
end

@testset "direct and fast FK sanity" begin
    a=run_chain(L=4,sigma=1.875,beta=0.336985,seed=11,therm=500,meas=4000,algorithm=:direct)
    b=run_chain(L=4,sigma=1.875,beta=0.336985,seed=12,therm=500,meas=4000,algorithm=:fast)
    @test abs(a.mean_m2-b.mean_m2)<0.06
    @test abs(a.Qm-b.Qm)<0.08
    @test abs(a.Rp-b.Rp)<0.12
end
