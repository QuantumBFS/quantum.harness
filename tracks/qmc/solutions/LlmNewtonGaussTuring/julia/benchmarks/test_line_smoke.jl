#===============================================================================
 快速冒烟测试: 着色正确性 + J=0 解析极限 + 世界线一致性
 用法: julia test_line_smoke.jl
===============================================================================#
include(joinpath(@__DIR__, "..", "src", "TIM_lattice_line.jl"))

failed = 0

# 1) 着色正确性
for (lat, Lx, Ly, expect_nc) in ((:honeycomb, 2, 2, 2), (:honeycomb, 4, 4, 2),
                                 (:triangular, 3, 3, 3), (:triangular, 6, 6, 3),
                                 (:triangular, 4, 4, 0), (:triangular, 5, 5, 0))
    N, Nb, z, bond, sb = build_lattice(lat, Lx, Ly)
    colors, classes = color_lattice(lat, Lx, Ly, N, bond)
    ok = verify_coloring(colors, bond)
    nc = length(classes)
    sizes = map(length, classes)
    tag = expect_nc == 0 ? "greedy" : "exact"
    if !ok || (expect_nc > 0 && nc != expect_nc)
        global failed += 1
        println("FAIL coloring $lat $(Lx)x$(Ly): ok=$ok nc=$nc sizes=$sizes")
    else
        println("PASS coloring $lat $(Lx)x$(Ly) [$tag]: nc=$nc sizes=$sizes")
    end
end

# 2) J=0 解析极限: E/N = -Γ tanh(βΓ), mx = tanh(βΓ)
for lat in (:triangular, :honeycomb)
    Γ, β = 1.0, 2.0
    avg, err, U, Uerr, ar, sps = run_line(lat, 3, 3, 0.0, Γ, 0.0, β,
                                          2000, 8000, 20260730; check_every = 500)
    Eex = -Γ * tanh(β * Γ)
    mxex = tanh(β * Γ)
    zE = abs(avg[1] - Eex) / max(err[1], 1e-12)
    zx = abs(avg[2] - mxex) / max(err[2], 1e-12)
    if zE > 4 || zx > 4
        global failed += 1
        println("FAIL J=0 $lat: E/N=$(avg[1])±$(err[1]) vs $Eex (z=$(round(zE,digits=2))), " *
                "mx=$(avg[2])±$(err[2]) vs $mxex (z=$(round(zx,digits=2)))")
    else
        println("PASS J=0 $lat: zE=$(round(zE,digits=2)) zx=$(round(zx,digits=2)) acc=$(round(ar,digits=3))")
    end
end

# 3) 铁磁 + 临界横场附近的一致性长跑 (check_every 全程开)
for (lat, Γ) in ((:triangular, 4.768), (:honeycomb, 2.1325))
    avg, err, U, Uerr, ar, sps = run_line(lat, 3, 3, -1.0, Γ, 0.0, 4.0,
                                          2000, 4000, 7; check_every = 100)
    println("PASS consistency $lat J=-1 Γ=$Γ: E/N=$(round(avg[1],digits=5)) acc=$(round(ar,digits=3)) sps=$(round(sps,digits=1))")
end

# 4) 并行 (nt>1) 与一致性
if Threads.nthreads() >= 2
    for (lat, Lx, Ly) in ((:triangular, 6, 6), (:honeycomb, 4, 4))
        avg, err, U, Uerr, ar, sps = run_line(lat, Lx, Ly, -1.0, 3.0, 0.0, 4.0,
                                              1000, 2000, 11; nt = Threads.nthreads(),
                                              check_every = 100)
        println("PASS parallel $lat nt=$(Threads.nthreads()): E/N=$(round(avg[1],digits=5)) acc=$(round(ar,digits=3))")
    end
else
    println("SKIP parallel test (start julia with -t)")
end

println(failed == 0 ? "ALL SMOKE TESTS PASSED" : "$failed TEST(S) FAILED")
exit(failed == 0 ? 0 : 1)
