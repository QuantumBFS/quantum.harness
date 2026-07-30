using Test, Random
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

@testset "exact nearest-neighbor FK" begin
    L=8
    spins=ones(Int,L^2)
    u=WindingUF(L^2)
    flips=fill(Int8(-1),L^2)
    wr,c1=nearest_neighbor_sweep!(spins,0.0,MersenneTwister(101),u,flips)
    @test wr[1] && !wr[2]
    @test c1==1

    fill!(spins,1)
    wr,c1=nearest_neighbor_sweep!(spins,Inf,MersenneTwister(102),u,flips)
    @test wr[2] && wr[3] && wr[4]
    @test c1==L^2

    r=run_nn_chain(L=L,seed=103,therm=500,meas=5000,blocks=20)
    @test r.model=="nearest_neighbor"
    @test r.sumJ==4.0
    @test 0.78<r.Qm<0.92
    @test abs(r.Rp)<0.15
end
